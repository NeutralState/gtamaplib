#!/usr/bin/env python3
"""
refine_cam_full.py — Refine xyz+ypr+fov of a single non-leak camera using
tier-weighted LM selection.

Optimizes 7 parameters: x, y, z, yaw, pitch, roll, hfov.
LMs do NOT move — the cam fits the LMs.

Priority order for which landmarks to use:
  1. Anchor LMs only (>= 6)
  2. Anchor + High (combined >= 4, with >= 2 anchor)
  3. All available (>= 4, with >= 2 anchor) — flag warning
  4. Insufficient — refuse

Bounds:
  hfov: 20° to 120° (hard bounds enforced)
  xyz/ypr: unbounded (init is current value, but clamped if absurd)

Per-LM weight in optimization:
  tier_weight: anchor=10, high=5, medium=2, low=0.5, unverified=0.1
  leak_source_bonus: ×1.5 if any leak cam is in LM's source_cameras

Validation:
  - Final RMS < 3 arcmin → calibration looks solid
  - Final RMS 3-10 arcmin → warning, --apply allowed
  - Final RMS > 10 arcmin → warning, requires --force-apply to override

Default mode is dry-run. Use --apply to write (--force-apply if RMS > 10).

Usage:
    python3 tools/refine_cam_full.py "Vice Beach (B)"
    python3 tools/refine_cam_full.py "Vice Beach (B)" --apply
    python3 tools/refine_cam_full.py "Vice Beach (B)" --force-apply
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
GOOD_RMS_ARCMIN = 3.0      # Below this: cam is clearly well-calibrated
HIGH_RMS_ARCMIN = 5.0      # Above this: probably stale marking, flag warning
DANGER_RMS_ARCMIN = 10.0   # Above this: needs --force-apply to write

# Bounds
HFOV_MIN = 20.0
HFOV_MAX = 120.0
HFOV_DEFAULT = 60.0        # Clamp to this if init is absurd

# Tier weighting
TIER_WEIGHTS = {
    'anchor': 10.0,
    'high': 5.0,
    'medium': 2.0,
    'low': 0.5,
    'unverified': 0.1,
    'unknown': 0.1,
}
LEAK_SOURCE_BONUS = 1.5

sys.path.insert(0, REPO_DIR)
import gtamaplib as ml

# V2: per-class constraint awareness via the audit helper.
from leak_cam_audit import (
    get_class,
    is_excluded,
    is_triangulation_trusted,
    get_locked_dof,
    DOF_XYZ, DOF_YPR, DOF_FOV,
)


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
    return lm_tiers.get(lm_name, 'unknown')


def compute_lm_weight(lm_name, lm_tiers, landmarks, cameras):
    """Compute weight for this LM in the optimization."""
    tier = lm_tiers.get(lm_name, 'unknown')
    weight = TIER_WEIGHTS.get(tier, 0.1)

    lm = landmarks.get(lm_name, {})
    if isinstance(lm, dict):
        sources = lm.get('source_cameras', [])
        if isinstance(sources, list):
            has_locked_xyz_source = any(
                is_triangulation_trusted(s, cameras=cameras)
                for s in sources
            )
            if has_locked_xyz_source:
                weight *= LEAK_SOURCE_BONUS

    return weight


def select_lms(visible_classified):
    """Pick the LMs to use for full refinement based on priority.

    For 7-param optimization, we need more LMs than ypr-only (3 params).
    Returns (selected_lms, level, warning_str)
    """
    anchor = [n for n, t in visible_classified.items() if t == 'anchor']
    high = [n for n, t in visible_classified.items() if t == 'high']
    medium = [n for n, t in visible_classified.items() if t == 'medium']
    low = [n for n, t in visible_classified.items() if t == 'low']
    unverified = [n for n, t in visible_classified.items() if t == 'unverified']

    if len(anchor) >= 6:
        return anchor, "anchor only (best)", None
    if len(anchor) + len(high) >= 4 and len(anchor) >= 2:
        return anchor + high, "anchor + high", None
    total = anchor + high + medium + low + unverified
    if len(total) >= 4 and len(anchor) >= 2:
        return total, "all available", (
            f"Only {len(anchor)} anchor LMs available. Including lower tiers — "
            "weighted accordingly, but confidence is degraded.")
    if len(total) >= 4:
        return total, "all available (no anchor)", (
            f"No anchor LMs available, only {len(total)} total. "
            "Calibration is suspect.")
    return [], "insufficient", (
        f"Only {len(total)} LM(s) available. Need >= 4 for 7-param fit.")


def compute_residuals(cam_name, params, cameras, pixels, landmarks, selected_lms, lm_tiers):
    """Given candidate params [x, y, z, yaw, pitch, roll, hfov], compute residuals.
    Returns (rms_arcmin_weighted, max_arcmin, per_lm_arcmin, per_lm_weight).

    Uses gtamaplib's exact projection logic (ZXY euler → quaternion → cam-frame projection).
    """
    import numpy as np
    from scipy.spatial.transform import Rotation as Rot

    cam_data = cameras[cam_name]
    cam_size = cam_data['size']
    # vfov: derive from hfov + aspect ratio (matches what the lib does for refined cams)
    # Actually we need to check if the cam has vfov stored — if so, use it derived from hfov:vfov ratio
    # but during optimization we vary hfov only and derive vfov from aspect.
    
    x, y, z, yaw, pitch, roll, hfov = params

    # Derive vfov from hfov using the cam's aspect ratio
    # This matches gtamaplib's behavior where fov = (hfov, vfov) and vfov is consistent
    w, h = cam_size
    aspect = w / h
    # vfov such that horizontal and vertical focal lengths are equal:
    # focal = (w/2) / tan(hfov/2) = (h/2) / tan(vfov/2)
    # => tan(vfov/2) = (h/w) * tan(hfov/2)
    vfov = math.degrees(2 * math.atan(math.tan(math.radians(hfov) / 2) / aspect))

    # Build quaternion from ZXY euler (matches gtamaplib.get_q)
    try:
        q = Rot.from_euler("ZXY", [yaw, pitch, roll], degrees=True)
    except Exception:
        return float('inf'), float('inf'), {}, {}

    cam_xyz = np.array([x, y, z], dtype=float)

    hfov_r = math.radians(hfov)
    vfov_r = math.radians(vfov)
    tan_h = math.tan(hfov_r / 2)
    tan_v = math.tan(vfov_r / 2)

    if hfov < 1.0 or hfov > 179.0:
        return float('inf'), float('inf'), {}, {}

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

        # Exact gtamaplib projection
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
        # Convert px to arcmin using horizontal fov
        d_arcmin = d_px / w * hfov * 60
        per_lm[lm_name] = d_arcmin

        weight = compute_lm_weight(lm_name, lm_tiers, landmarks, cameras)
        per_lm_weight[lm_name] = weight
        weighted_sq_errors.append(weight * d_arcmin * d_arcmin)
        total_weight += weight

    if not weighted_sq_errors or total_weight <= 0:
        return float('inf'), float('inf'), per_lm, per_lm_weight
    rms = math.sqrt(sum(weighted_sq_errors) / total_weight)
    max_arcmin = max(per_lm.values())
    return rms, max_arcmin, per_lm, per_lm_weight
    return rms, max_arcmin, per_lm, per_lm_weight


def optimize_full(cam_name, initial_params, cameras, pixels, landmarks, selected_lms, lm_tiers,
                  fix_xy=None, z_bounds=None):
    """Optimize 7 params to minimize weighted RMS pixel residuals.
    
    fix_xy: tuple (x, y) — if provided, x and y are frozen at these values
    z_bounds: tuple (z_min, z_max) — if provided, z is constrained to this range
    
    Returns (best_params, final_rms, max_arcmin, per_lm, per_lm_weight)."""
    try:
        from scipy.optimize import minimize
    except ImportError:
        return None, None, None, None, None

    # If xy is fixed, replace them in initial_params
    if fix_xy is not None:
        initial_params = list(initial_params)
        initial_params[0] = fix_xy[0]
        initial_params[1] = fix_xy[1]

    def loss_fn(params):
        params = list(params)
        # Force xy to fixed values if specified
        if fix_xy is not None:
            params[0] = fix_xy[0]
            params[1] = fix_xy[1]
        # Soft barrier for hfov bounds
        hfov = params[6]
        penalty = 0.0
        if hfov < HFOV_MIN:
            penalty += (HFOV_MIN - hfov) ** 2 * 1000
        elif hfov > HFOV_MAX:
            penalty += (hfov - HFOV_MAX) ** 2 * 1000
        # Soft barrier for z bounds
        if z_bounds is not None:
            z = params[2]
            if z < z_bounds[0]:
                penalty += (z_bounds[0] - z) ** 2 * 1000
            elif z > z_bounds[1]:
                penalty += (z - z_bounds[1]) ** 2 * 1000
        rms, _, _, _ = compute_residuals(cam_name, params, cameras, pixels, landmarks, selected_lms, lm_tiers)
        return rms + penalty

    result = minimize(loss_fn, initial_params, method='Nelder-Mead',
                      options={'xatol': 1e-4, 'fatol': 1e-6,
                               'maxiter': 20000, 'adaptive': True})
    best_params = list(result.x)
    # Re-apply xy constraint (Nelder-Mead might have drifted them despite the loss fn)
    if fix_xy is not None:
        best_params[0] = fix_xy[0]
        best_params[1] = fix_xy[1]
    # Clamp z to bounds if needed
    if z_bounds is not None:
        if best_params[2] < z_bounds[0]:
            best_params[2] = z_bounds[0]
        elif best_params[2] > z_bounds[1]:
            best_params[2] = z_bounds[1]
    # Clamp hfov to bounds if optimization drifted outside
    if best_params[6] < HFOV_MIN:
        best_params[6] = HFOV_MIN
    elif best_params[6] > HFOV_MAX:
        best_params[6] = HFOV_MAX
    rms, max_arc, per_lm, per_lm_weight = compute_residuals(cam_name, best_params, cameras, pixels, landmarks, selected_lms, lm_tiers)
    return best_params, rms, max_arc, per_lm, per_lm_weight


def main():
    parser = argparse.ArgumentParser(description="Refine xyz+ypr+fov of a non-leak cam.")
    parser.add_argument('cam_name', help="Name of the camera to refine.")
    parser.add_argument('--apply', action='store_true',
                        help="Write the update (allowed if RMS < 10 arcmin).")
    parser.add_argument('--force-apply', action='store_true',
                        help="Write the update even if RMS > 10 arcmin (use with caution).")
    parser.add_argument('--fix-xy', nargs=2, type=float, metavar=('X', 'Y'), default=None,
                        help="Freeze the cam's x,y position. e.g. --fix-xy 2021.75 921.75")
    parser.add_argument('--z-bounds', nargs=2, type=float, metavar=('MIN', 'MAX'), default=None,
                        help="Constrain z within [MIN, MAX]. e.g. --z-bounds 1 6")
    parser.add_argument('--use-indep-only', action='store_true',
                        help="Only use LMs where this cam is NOT in their source_cameras (independent LMs). "
                             "Matches the server's loss computation (used by the UI's 'indep' score).")
    args = parser.parse_args()

    cameras, pixels, landmarks, lm_tiers = load_all()

    cam_data = cameras.get(args.cam_name)
    if cam_data is None:
        print(f"ERROR: Camera '{args.cam_name}' not found.")
        return 1

    # V2 gating: refine_cam_full does a joint xyz/ypr/fov solve. The right
    # cams for this tool are ones where xyz is NOT HUD-locked (so the solver
    # has freedom on position) — i.e. class D, non-audit ordinary cams, or
    # class Cm when the user passes --no-refine-xyz to freeze xyz.
    #
    # Decision rule:
    #   - Excluded (X): refuse
    #   - Anchor (A, _legacy_date): refuse (nothing to refine)
    #   - xyz is locked (B, C, Cm): only allow if user passes --no-refine-xyz
    #     to acknowledge the constraint
    #   - xyz is free (D, non-audit): allow with default flags
    if is_excluded(args.cam_name, cameras=cameras):
        print(f"ERROR: '{args.cam_name}' is class X_invalid_ground_truth — excluded.")
        return 1
    cls = get_class(args.cam_name, cameras=cameras)
    if cls is not None:
        locked = get_locked_dof(args.cam_name, cameras=cameras)
        if DOF_XYZ in locked and DOF_YPR in locked and DOF_FOV in locked:
            print(f"ERROR: '{args.cam_name}' is class {cls} — all DOF are HUD "
                  f"ground-truth, nothing to refine.")
            return 1
        if DOF_XYZ in locked and DOF_FOV in locked:
            # B or C — only ypr is free, use refine_cam_ypr.py
            print(f"ERROR: '{args.cam_name}' is class {cls} — xyz and fov are "
                  f"HUD-locked, only ypr is refinable.")
            print(f"Use tools/refine_cam_ypr.py for ypr-only refinement.")
            return 1
        if DOF_XYZ in locked:
            # Cm: xyz locked, ypr + fov refinable. Force xyz frozen by setting
            # fix_xy to current (x, y) and z_bounds to a 0-width interval
            # around current z. This honors the HUD-locked xyz regardless of
            # what the user passed.
            cur_xyz_cm = cam_data.get('xyz')
            if cur_xyz_cm is not None:
                if args.fix_xy is None:
                    args.fix_xy = [cur_xyz_cm[0], cur_xyz_cm[1]]
                    print(f"  V2 class {cls}: xyz is HUD-locked, "
                          f"auto-setting --fix-xy {cur_xyz_cm[0]:.3f} {cur_xyz_cm[1]:.3f}")
                if args.z_bounds is None:
                    # ±1cm — effectively zero-width but avoids degenerate solver
                    args.z_bounds = [cur_xyz_cm[2] - 0.01, cur_xyz_cm[2] + 0.01]
                    print(f"  V2 class {cls}: xyz is HUD-locked, "
                          f"auto-setting --z-bounds to lock z={cur_xyz_cm[2]:.3f}")
    # Class D, non-audit cams, or Cm (with xyz now frozen): full solve
    # proceeds with the user's flags.

    cur_xyz = cam_data.get('xyz')
    cur_ypr = cam_data.get('ypr')
    cur_fov = cam_data.get('fov')
    cam_size = cam_data.get('size')

    # Resolve current hfov
    cur_hfov = cur_fov[0]
    if cur_hfov is None and cur_fov[1] is not None:
        ratio = cam_size[0] / cam_size[1]
        cur_hfov = math.degrees(2 * math.atan(math.tan(math.radians(cur_fov[1]) / 2) * ratio))

    print(f"=== {args.cam_name} ===")
    print(f"Current xyz: {cur_xyz}")
    print(f"Current ypr: {cur_ypr}")
    print(f"Current fov (hfov, vfov): {cur_fov}")
    print(f"  Effective hfov: {cur_hfov}")
    print()

    # Clamp init if absurd
    init_hfov = cur_hfov
    if init_hfov is None or init_hfov < HFOV_MIN or init_hfov > HFOV_MAX:
        print(f"WARNING: Init hfov ({init_hfov}) is outside [{HFOV_MIN}, {HFOV_MAX}]°.")
        print(f"  Clamping to default ({HFOV_DEFAULT}°) for optimization.")
        init_hfov = HFOV_DEFAULT

    init_params = list(cur_xyz) + list(cur_ypr) + [init_hfov]

    # Find visible LMs
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

    # Priority selection
    selected, level, warning = select_lms(visible_classified)
    print(f"Selected LMs ({len(selected)}): {level}")
    if warning:
        print(f"  WARNING: {warning}")

    # Optionally filter to independent LMs only (cam not in sources)
    if args.use_indep_only:
        original_count = len(selected)
        selected = [lm for lm in selected
                    if args.cam_name not in (landmarks.get(lm, {}).get('source_cameras', []) or [])]
        print(f"  --use-indep-only: filtered to {len(selected)} LMs (dropped {original_count - len(selected)} circular)")
    print()

    if len(selected) < 4:
        print(f"Cam not refined, reason: insufficient LMs (need >= 4 for 7-param fit)")
        return 1

    # Initial residuals
    init_rms, init_max, init_per_lm, init_per_weight = compute_residuals(
        args.cam_name, init_params, cameras, pixels, landmarks, selected, lm_tiers)
    print(f"Initial residuals:")
    print(f"  Weighted RMS: {init_rms:.2f} arcmin")
    print(f"  Max: {init_max:.2f} arcmin")
    print()

    # Print constraints if any
    fix_xy = tuple(args.fix_xy) if args.fix_xy else None
    z_bounds = tuple(args.z_bounds) if args.z_bounds else None
    if fix_xy or z_bounds:
        print(f"Constraints:")
        if fix_xy:
            print(f"  Fixed xy: ({fix_xy[0]}, {fix_xy[1]})")
        if z_bounds:
            print(f"  Z bounds: [{z_bounds[0]}, {z_bounds[1]}]")
        print()

    # Optimize
    new_params, final_rms, final_max, final_per_lm, final_per_weight = optimize_full(
        args.cam_name, init_params, cameras, pixels, landmarks, selected, lm_tiers,
        fix_xy=fix_xy, z_bounds=z_bounds)
    if new_params is None:
        print(f"ERROR: optimization failed (scipy not installed?)")
        return 1

    new_xyz = new_params[0:3]
    new_ypr = new_params[3:6]
    new_hfov = new_params[6]
    # Derive vfov from hfov + aspect
    ratio = cam_size[0] / cam_size[1]
    new_vfov = math.degrees(2 * math.atan(math.tan(math.radians(new_hfov) / 2) / ratio))

    delta_xyz = [new_xyz[i] - cur_xyz[i] for i in range(3)]
    delta_xyz_norm = math.sqrt(sum(d * d for d in delta_xyz))
    delta_ypr = [new_ypr[i] - cur_ypr[i] for i in range(3)]
    delta_hfov = new_hfov - (cur_hfov if cur_hfov is not None else HFOV_DEFAULT)

    print(f"Optimized:")
    print(f"  xyz: [{new_xyz[0]:.4f}, {new_xyz[1]:.4f}, {new_xyz[2]:.4f}]  (Δ {delta_xyz_norm:.2f} m)")
    print(f"  ypr: [{new_ypr[0]:.4f}, {new_ypr[1]:.4f}, {new_ypr[2]:.4f}]  (Δ [{delta_ypr[0]:+.3f}, {delta_ypr[1]:+.3f}, {delta_ypr[2]:+.3f}])")
    print(f"  hfov: {new_hfov:.4f}°  (Δ {delta_hfov:+.3f}°)")
    print(f"  vfov (derived): {new_vfov:.4f}°")
    print()
    print(f"Final Weighted RMS: {final_rms:.2f} arcmin (was {init_rms:.2f})")
    print(f"Final Max: {final_max:.2f} arcmin (was {init_max:.2f})")
    print()

    # Per-LM details
    print(f"Per-LM residuals (sorted by weight × residual²):")
    sorted_lms = sorted(final_per_lm.items(),
                        key=lambda x: -(final_per_weight.get(x[0], 0) * x[1] * x[1]))
    for lm_name, err in sorted_lms:
        w = final_per_weight.get(lm_name, 0)
        tier = lm_tiers.get(lm_name, 'unknown')
        print(f"  weight={w:5.1f} [{tier:10}] {err:7.2f}'  {lm_name}")
    print()

    # Validation
    apply_allowed = False
    if final_rms < GOOD_RMS_ARCMIN:
        print(f"✓ Final RMS < {GOOD_RMS_ARCMIN}' — calibration looks solid.")
        apply_allowed = True
    elif final_rms < HIGH_RMS_ARCMIN:
        print(f"~ Final RMS {final_rms:.2f}' < {HIGH_RMS_ARCMIN}' — acceptable.")
        apply_allowed = True
    elif final_rms < DANGER_RMS_ARCMIN:
        worst = sorted_lms[0]
        print(f"⚠ Final RMS {final_rms:.2f}' is elevated.")
        print(f"  Worst LM: '{worst[0]}' at {worst[1]:.2f}'")
        print(f"  --apply still allowed but consider reviewing markings.")
        apply_allowed = True
    else:
        worst = sorted_lms[0]
        print(f"✗ Final RMS {final_rms:.2f}' > {DANGER_RMS_ARCMIN}' — calibration is suspect.")
        print(f"  Worst LM: '{worst[0]}' at {worst[1]:.2f}'")
        print(f"  --apply DISABLED. Use --force-apply to override, or review markings first.")
        apply_allowed = False
    print()

    # Decide whether to write
    if not args.apply and not args.force_apply:
        print("DRY-RUN: not writing. Use --apply to write (--force-apply if RMS > 10).")
        return 0

    if args.apply and not apply_allowed and not args.force_apply:
        print(f"REFUSED: RMS {final_rms:.2f}' exceeds {DANGER_RMS_ARCMIN}'. Use --force-apply to override.")
        return 1

    # Apply
    cam_data['xyz'] = new_xyz
    cam_data['ypr'] = new_ypr
    cam_data['fov'] = [new_hfov, new_vfov]
    cameras[args.cam_name] = cam_data

    with open(CAMERAS_JSON, 'w') as f:
        json.dump(cameras, f, indent=2)

    if args.force_apply and not apply_allowed:
        print(f"FORCE-APPLIED: cameras.json updated despite RMS {final_rms:.2f}'. Verify visually.")
    else:
        print(f"APPLIED: cameras.json updated.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
