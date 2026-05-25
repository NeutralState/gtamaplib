#!/usr/bin/env python3
"""
refine_cam_ypr.py — Refine the ypr of a single leak camera using
priority-based landmark selection.

Priority order for which landmarks to use:
  1. Anchor LMs only (best — established by 2+ leak cams)
  2. Anchor + High (acceptable — some non-leak triangulation involved)
  3. Anchor + High + Medium (degraded — flag warning)
  4. Insufficient — refuse to calibrate

The cam xyz and fov are FROZEN (ground truth from console). Only ypr moves.
Landmarks DO NOT move. The cam fits the LMs, not the inverse.

Default mode is dry-run. Use --apply to actually update cameras.json.

Usage:
    python3 tools/refine_cam_ypr.py "Tennis Court (SE)"           # dry-run
    python3 tools/refine_cam_ypr.py "Tennis Court (SE)" --apply   # write
"""

import argparse
import json
import math
import os
import re
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(THIS_DIR)
DATA_DIR = os.path.join(REPO_DIR, 'gtamapdata')
GEN_DIR = os.path.join(THIS_DIR, 'generated')

CAMERAS_JSON = os.path.join(DATA_DIR, 'cameras.json')
PIXELS_JSON = os.path.join(DATA_DIR, 'pixels.json')
LANDMARKS_JSON = os.path.join(DATA_DIR, 'landmarks.json')
TIERS_JSON = os.path.join(GEN_DIR, 'confidence_tiers.json')

# Thresholds
GOOD_RMS_ARCMIN = 3.0      # Below this: cam is clearly well-calibrated, auto-apply OK
HIGH_RMS_ARCMIN = 5.0      # Above this: probably stale marking, flag warning

# Per-tier weight in the optimization. Higher = LM has more influence on the fit.
# Anchor LMs are trusted, so they pull the optimization toward themselves.
# Low-tier LMs are barely trusted, so they have small influence (won't drag good LMs).
TIER_WEIGHTS = {
    'anchor': 10.0,
    'high': 5.0,
    'medium': 2.0,
    'low': 0.5,
    'unverified': 0.1,
    'unknown': 0.1,
}
# Multiplier when an LM has at least one leak cam in its source_cameras list.
# Such an LM is anchored by ground-truth xyz/fov, so its position is more trusted.
LEAK_SOURCE_BONUS = 1.5


sys.path.insert(0, REPO_DIR)
import gtamaplib as ml


def load_all():
    with open(CAMERAS_JSON) as f:
        cameras = json.load(f)
    with open(PIXELS_JSON) as f:
        pixels = json.load(f)
    with open(LANDMARKS_JSON) as f:
        landmarks = json.load(f)
    tiers_data = {'cameras': {}, 'landmarks': {}}
    if os.path.exists(TIERS_JSON):
        with open(TIERS_JSON) as f:
            tiers_data = json.load(f)
    lm_tiers = {}
    for n, d in tiers_data.get('landmarks', {}).items():
        lm_tiers[n] = d.get('tier') if isinstance(d, dict) else d
    return cameras, pixels, landmarks, lm_tiers


def is_leak_cam(cam_data):
    """A cam is a 'leak' cam if its source string is a date (YYYY-MM-DD).
    This matches the server.py / UI definition (LEAK_CAMS).
    Note: this is different from `player is not None` — some leak cams have
    player=None but their xyz/fov still come from a dated debug overlay."""
    if not isinstance(cam_data, dict):
        return False
    src = cam_data.get('source', '') or ''
    return bool(re.match(r'\d{4}-\d{2}-\d{2}', src))


def classify_lm(lm_name, lm_tiers):
    """Return tier or 'unknown'."""
    return lm_tiers.get(lm_name, 'unknown')


def compute_lm_weight(lm_name, lm_tiers, landmarks, cameras):
    """Compute weight for this LM in the optimization.

    weight = tier_weight × leak_bonus (if any source is a leak cam)
    """
    tier = lm_tiers.get(lm_name, 'unknown')
    weight = TIER_WEIGHTS.get(tier, 0.1)

    lm = landmarks.get(lm_name, {})
    if isinstance(lm, dict):
        sources = lm.get('source_cameras', [])
        if isinstance(sources, list):
            has_leak_source = any(
                is_leak_cam(cameras.get(s, {}))
                for s in sources
            )
            if has_leak_source:
                weight *= LEAK_SOURCE_BONUS

    return weight


def select_lms(visible_classified):
    """Pick the LMs to use for ypr refinement based on priority.

    visible_classified: dict {lm_name: tier}
    Returns (selected_lms, level, warning_str)
    """
    anchor = [n for n, t in visible_classified.items() if t == 'anchor']
    high = [n for n, t in visible_classified.items() if t == 'high']
    medium = [n for n, t in visible_classified.items() if t == 'medium']
    low = [n for n, t in visible_classified.items() if t == 'low']
    unverified = [n for n, t in visible_classified.items() if t == 'unverified']

    if len(anchor) >= 3:
        return anchor, "anchor only (best)", None
    if len(anchor) + len(high) >= 3:
        return anchor + high, "anchor + high", None
    if len(anchor) + len(high) + len(medium) >= 3:
        return anchor + high + medium, "anchor + high + medium", (
            "Using medium-tier LMs — confidence is degraded.")
    # Need at least 3 for a solid 3-dof ypr fit; if we only have 2 we can still try
    total = anchor + high + medium + low + unverified
    if len(total) >= 2:
        return total, "all available (low confidence)", (
            f"Only {len(total)} LMs available, no anchor/high LMs. "
            "Calibration is suspect.")
    return [], "insufficient", f"Only {len(total)} LM(s) available. Cannot calibrate ypr."


def project_pixel(cam, lm_xyz):
    """Project a 3D LM into the cam's pixel space. Returns (px, py) or None if behind."""
    import numpy as np
    o = np.asarray(cam.xyz, dtype=float)
    p = np.asarray(lm_xyz, dtype=float)
    v = p - o
    # Use the cam's projection method
    try:
        return cam.get_pixel(lm_xyz)
    except Exception:
        return None


def compute_residuals(cam_name, ypr, cameras, pixels, landmarks, selected_lms, lm_tiers=None):
    """Given a candidate ypr, compute pixel residuals on the selected LMs.
    Returns (rms_arcmin, max_arcmin, per_lm_arcmin: dict, per_lm_weight: dict).

    Uses gtamaplib's exact projection logic (ZXY euler → quaternion → cam-frame projection).

    If lm_tiers is provided, RMS is computed weighted by tier-derived LM weights.
    Otherwise (legacy), all LMs are weighted equally.
    """
    import numpy as np
    from scipy.spatial.transform import Rotation as Rot

    cam_data = cameras[cam_name]
    xyz = cam_data['xyz']
    fov = cam_data['fov']
    hfov = fov[0]
    cam_size = cam_data['size']
    w, h = cam_size
    aspect = w / h
    if hfov is None:
        vfov = fov[1]
        hfov = math.degrees(2 * math.atan(math.tan(math.radians(vfov) / 2) * aspect))
    # Derive vfov so vertical and horizontal focal are consistent
    vfov = math.degrees(2 * math.atan(math.tan(math.radians(hfov) / 2) / aspect))

    yaw, pitch, roll = ypr
    try:
        q = Rot.from_euler("ZXY", [yaw, pitch, roll], degrees=True)
    except Exception:
        return float('inf'), float('inf'), {}, {}

    cam_xyz = np.array(xyz, dtype=float)

    hfov_r = math.radians(hfov)
    vfov_r = math.radians(vfov)
    tan_h = math.tan(hfov_r / 2)
    tan_v = math.tan(vfov_r / 2)

    per_lm = {}
    per_lm_weight = {}
    weighted_sq_errors = []
    total_weight = 0.0
    for lm_name in selected_lms:
        lm_data = landmarks.get(lm_name)
        if not isinstance(lm_data, dict):
            continue
        lm_xyz = lm_data.get('xyz')
        if not lm_xyz:
            continue
        marked = pixels.get(cam_name, {}).get(lm_name)
        if not marked:
            continue

        delta = np.array(lm_xyz, dtype=float) - cam_xyz
        cam_dir = q.inv().apply(delta)
        if cam_dir[1] <= 0:
            per_lm[lm_name] = float('inf')
            per_lm_weight[lm_name] = 0.0
            continue
        ndc_x = cam_dir[0] / cam_dir[1] / tan_h
        ndc_y = cam_dir[2] / cam_dir[1] / tan_v
        px =      (ndc_x + 1) * 0.5  * w - 0.5
        py = (1 - (ndc_y + 1) * 0.5) * h - 0.5
        if not (math.isfinite(px) and math.isfinite(py)):
            per_lm[lm_name] = float('inf')
            per_lm_weight[lm_name] = 0.0
            continue

        dx = px - marked[0]
        dy = py - marked[1]
        d_px = math.sqrt(dx * dx + dy * dy)
        d_arcmin = d_px / w * hfov * 60
        per_lm[lm_name] = d_arcmin

        if lm_tiers is not None:
            weight = compute_lm_weight(lm_name, lm_tiers, landmarks, cameras)
        else:
            weight = 1.0
        per_lm_weight[lm_name] = weight
        weighted_sq_errors.append(weight * d_arcmin * d_arcmin)
        total_weight += weight

    if not weighted_sq_errors or total_weight <= 0:
        return float('inf'), float('inf'), per_lm, per_lm_weight
    rms = math.sqrt(sum(weighted_sq_errors) / total_weight)
    max_arcmin = max(per_lm.values())
    return rms, max_arcmin, per_lm, per_lm_weight


def optimize_ypr(cam_name, initial_ypr, cameras, pixels, landmarks, selected_lms, lm_tiers=None):
    """Optimize ypr to minimize weighted RMS pixel residuals on selected LMs.
    Returns (best_ypr, final_rms, max_arcmin, per_lm, per_lm_weight)."""
    try:
        from scipy.optimize import minimize
    except ImportError:
        return None, None, None, None, None

    def loss_fn(ypr):
        rms, _, _, _ = compute_residuals(cam_name, list(ypr), cameras, pixels, landmarks, selected_lms, lm_tiers)
        return rms

    result = minimize(loss_fn, initial_ypr, method='Nelder-Mead',
                      options={'xatol': 1e-4, 'fatol': 1e-6,
                               'maxiter': 5000, 'adaptive': True})
    best_ypr = list(result.x)
    rms, max_arc, per_lm, per_lm_weight = compute_residuals(cam_name, best_ypr, cameras, pixels, landmarks, selected_lms, lm_tiers)
    return best_ypr, rms, max_arc, per_lm, per_lm_weight


def main():
    parser = argparse.ArgumentParser(description="Refine ypr of a single leak cam using priority-based LM selection.")
    parser.add_argument('cam_name', help="Name of the camera to refine.")
    parser.add_argument('--apply', action='store_true',
                        help="Actually write the update. Default is dry-run.")
    args = parser.parse_args()

    cameras, pixels, landmarks, lm_tiers = load_all()

    cam_data = cameras.get(args.cam_name)
    if cam_data is None:
        print(f"ERROR: Camera '{args.cam_name}' not found.")
        return 1

    if not is_leak_cam(cam_data):
        print(f"ERROR: '{args.cam_name}' is not a leak cam (source is not a date).")
        print(f"This tool is for leak cams only. Non-leak cams need full xyz/ypr/fov calibration.")
        return 1

    cur_ypr = cam_data.get('ypr')
    cur_xyz = cam_data.get('xyz')
    cur_fov = cam_data.get('fov')

    print(f"=== {args.cam_name} ===")
    print(f"Frozen xyz (from console): {cur_xyz}")
    print(f"Frozen fov (from console): {cur_fov}")
    print(f"Current ypr: {cur_ypr}")
    print()

    # Find visible LMs (those with markings on this cam)
    cam_pixels = pixels.get(args.cam_name, {})
    if not cam_pixels:
        print(f"ERROR: No pixel markings on '{args.cam_name}'.")
        return 1

    visible_classified = {}
    for lm_name in cam_pixels:
        if lm_name not in landmarks:
            continue
        if not isinstance(landmarks[lm_name], dict) or not landmarks[lm_name].get('xyz'):
            continue
        visible_classified[lm_name] = classify_lm(lm_name, lm_tiers)

    if not visible_classified:
        print(f"ERROR: No LMs with positions visible on '{args.cam_name}'.")
        return 1

    print(f"Visible LMs ({len(visible_classified)}):")
    by_tier = {}
    for lm, tier in visible_classified.items():
        by_tier.setdefault(tier, []).append(lm)
    for tier in ['anchor', 'high', 'medium', 'low', 'unverified', 'unknown']:
        if tier in by_tier:
            print(f"  [{tier:10}] {len(by_tier[tier])} LMs")
    print()

    # Apply priority
    selected, level, warning = select_lms(visible_classified)
    print(f"Selected LMs ({len(selected)}): {level}")
    if warning:
        print(f"  WARNING: {warning}")
    print()

    if len(selected) < 2:
        print(f"Cam ypr not refined, reason: insufficient LMs")
        return 1

    # Compute initial residuals (weighted by tier)
    init_rms, init_max, init_per_lm, init_per_weight = compute_residuals(
        args.cam_name, cur_ypr, cameras, pixels, landmarks, selected, lm_tiers)
    print(f"Initial residuals (using current ypr, weighted by tier):")
    print(f"  Weighted RMS: {init_rms:.2f} arcmin")
    print(f"  Max: {init_max:.2f} arcmin")
    print()

    # Optimize (weighted)
    new_ypr, final_rms, final_max, final_per_lm, final_per_weight = optimize_ypr(
        args.cam_name, cur_ypr, cameras, pixels, landmarks, selected, lm_tiers)
    if new_ypr is None:
        print(f"ERROR: optimization failed (scipy not installed?)")
        return 1

    delta_ypr = [new_ypr[i] - cur_ypr[i] for i in range(3)]
    print(f"Optimized ypr: [{new_ypr[0]:.4f}, {new_ypr[1]:.4f}, {new_ypr[2]:.4f}]")
    print(f"Delta from current: [{delta_ypr[0]:+.4f}, {delta_ypr[1]:+.4f}, {delta_ypr[2]:+.4f}]")
    print(f"Final Weighted RMS: {final_rms:.2f} arcmin (was {init_rms:.2f})")
    print(f"Final Max: {final_max:.2f} arcmin (was {init_max:.2f})")
    print()

    # Per-LM details with weights
    print(f"Per-LM residuals (sorted by weight × residual²):")
    sorted_lms = sorted(final_per_lm.items(),
                        key=lambda x: -(final_per_weight.get(x[0], 0) * x[1] * x[1]))
    for lm_name, err in sorted_lms:
        w = final_per_weight.get(lm_name, 0)
        tier = lm_tiers.get(lm_name, 'unknown')
        print(f"  weight={w:5.1f} [{tier:10}] {err:7.2f}'  {lm_name}")
    print()

    # Suggest worst marking if RMS is still high
    if final_rms > HIGH_RMS_ARCMIN:
        sorted_lms = sorted(final_per_lm.items(), key=lambda x: -x[1])
        worst = sorted_lms[0]
        print(f"WARNING: Final RMS {final_rms:.2f}' is still high (> {HIGH_RMS_ARCMIN}').")
        print(f"  Likely stale marking: '{worst[0]}' at {worst[1]:.2f}'")
        print(f"  Suggestion: review and possibly drop this marking, then retry.")
        print()
    elif final_rms < GOOD_RMS_ARCMIN:
        print(f"Final RMS < {GOOD_RMS_ARCMIN}' — calibration looks solid.")
        print()

    if not args.apply:
        print("DRY-RUN: not writing. Use --apply to actually update cameras.json.")
        return 0

    # Apply
    cam_data['ypr'] = new_ypr
    cameras[args.cam_name] = cam_data

    with open(CAMERAS_JSON, 'w') as f:
        json.dump(cameras, f, indent=2)

    print(f"APPLIED: cameras.json updated.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
