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


def classify_lm(lm_name, lm_tiers):
    """Return tier or 'unknown'."""
    return lm_tiers.get(lm_name, 'unknown')


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


def compute_residuals(cam_name, ypr, cameras, pixels, landmarks, selected_lms):
    """Given a candidate ypr, compute pixel residuals on the selected LMs.
    Returns (rms_arcmin, max_arcmin, per_lm_arcmin: dict).
    """
    import numpy as np

    cam_data = cameras[cam_name]
    # Build a fresh cam object with the candidate ypr
    xyz = cam_data['xyz']
    fov = cam_data['fov']
    hfov = fov[0]
    if hfov is None:
        # compute from vfov + aspect
        size = cam_data['size']
        vfov = fov[1]
        ratio = size[0] / size[1]
        hfov = math.degrees(2 * math.atan(math.tan(math.radians(vfov) / 2) * ratio))

    # Use md.update_camera + ml.get_camera pattern to get a cam with the new ypr
    # without actually saving. We'll use ml directly.
    # Get a cam, override ypr.
    cam = ml.get_camera(cam_name)
    # Make a copy with new ypr
    cam_size = cam_data['size']

    # We compute manually using rotation matrices
    yaw, pitch, roll = ypr
    yaw_r = math.radians(yaw)
    pitch_r = math.radians(pitch)
    roll_r = math.radians(roll)

    # Z (yaw), then X (pitch), then Y (roll) intrinsic Euler
    # Use the same convention as gtamaplib
    cos_y, sin_y = math.cos(yaw_r), math.sin(yaw_r)
    cos_p, sin_p = math.cos(pitch_r), math.sin(pitch_r)
    cos_r, sin_r = math.cos(roll_r), math.sin(roll_r)

    # Build rotation matrix (from gtamaplib convention)
    # R = Rz(yaw) @ Rx(pitch) @ Ry(roll)
    Rz = np.array([[cos_y, -sin_y, 0], [sin_y, cos_y, 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, cos_p, -sin_p], [0, sin_p, cos_p]])
    Ry = np.array([[cos_r, 0, sin_r], [0, 1, 0], [-sin_r, 0, cos_r]])
    R = Rz @ Rx @ Ry

    # The cam's local axes are columns of R
    # +y is forward (look), +x right, +z up (gtamaplib convention)
    cam_xyz = np.asarray(xyz, dtype=float)
    cam_size_arr = np.asarray(cam_size, dtype=float)
    half_w = cam_size_arr[0] / 2
    half_h = cam_size_arr[1] / 2
    focal = half_w / math.tan(math.radians(hfov / 2))

    per_lm = {}
    sq_errors = []
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

        # Transform LM to cam local frame
        v_world = np.asarray(lm_xyz, dtype=float) - cam_xyz
        v_local = R.T @ v_world
        # Local: x=right, y=forward, z=up
        if v_local[1] <= 0:
            # Behind cam
            per_lm[lm_name] = float('inf')
            continue
        # Project to pixel
        px = half_w + focal * v_local[0] / v_local[1]
        py = half_h - focal * v_local[2] / v_local[1]

        dx = px - marked[0]
        dy = py - marked[1]
        d_px = math.sqrt(dx * dx + dy * dy)
        # Convert to arcmin
        d_arcmin = d_px / cam_size_arr[0] * hfov * 60
        per_lm[lm_name] = d_arcmin
        sq_errors.append(d_arcmin * d_arcmin)

    if not sq_errors:
        return float('inf'), float('inf'), per_lm
    rms = math.sqrt(sum(sq_errors) / len(sq_errors))
    max_arcmin = max(per_lm.values())
    return rms, max_arcmin, per_lm


def optimize_ypr(cam_name, initial_ypr, cameras, pixels, landmarks, selected_lms):
    """Optimize ypr to minimize RMS pixel residuals on selected LMs.
    Returns (best_ypr, final_rms, max_arcmin, per_lm)."""
    try:
        from scipy.optimize import minimize
    except ImportError:
        return None, None, None, None

    def loss_fn(ypr):
        rms, _, _ = compute_residuals(cam_name, list(ypr), cameras, pixels, landmarks, selected_lms)
        return rms

    result = minimize(loss_fn, initial_ypr, method='Nelder-Mead',
                      options={'xatol': 1e-4, 'fatol': 1e-6,
                               'maxiter': 5000, 'adaptive': True})
    best_ypr = list(result.x)
    rms, max_arc, per_lm = compute_residuals(cam_name, best_ypr, cameras, pixels, landmarks, selected_lms)
    return best_ypr, rms, max_arc, per_lm


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

    if cam_data.get('player') is None:
        print(f"ERROR: '{args.cam_name}' is not a leak cam (no player xyz).")
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

    # Compute initial residuals
    init_rms, init_max, init_per_lm = compute_residuals(args.cam_name, cur_ypr, cameras, pixels, landmarks, selected)
    print(f"Initial residuals (using current ypr):")
    print(f"  RMS: {init_rms:.2f} arcmin")
    print(f"  Max: {init_max:.2f} arcmin")
    print()

    # Optimize
    new_ypr, final_rms, final_max, final_per_lm = optimize_ypr(
        args.cam_name, cur_ypr, cameras, pixels, landmarks, selected)
    if new_ypr is None:
        print(f"ERROR: optimization failed (scipy not installed?)")
        return 1

    delta_ypr = [new_ypr[i] - cur_ypr[i] for i in range(3)]
    print(f"Optimized ypr: [{new_ypr[0]:.4f}, {new_ypr[1]:.4f}, {new_ypr[2]:.4f}]")
    print(f"Delta from current: [{delta_ypr[0]:+.4f}, {delta_ypr[1]:+.4f}, {delta_ypr[2]:+.4f}]")
    print(f"Final RMS: {final_rms:.2f} arcmin (was {init_rms:.2f})")
    print(f"Final Max: {final_max:.2f} arcmin (was {init_max:.2f})")
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
