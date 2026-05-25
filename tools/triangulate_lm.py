#!/usr/bin/env python3
"""
triangulate_lm.py — Triangulate a single landmark using priority-based source selection.

Priority order for which cameras to use:
  1. Leak + Leak (xyz/fov ground truth from console)
  2. Leak + Trusted non-leak (tier anchor/high)
  3. Trusted + Trusted (no leak available)
  4. Leak + Other (fallback)
  5. Other (last resort)

The selected pair/group is used to triangulate. Cameras outside the chosen
priority tier are ignored even if they have markings.

The LM xyz is updated based on the triangulation. Cameras DO NOT move.

Default mode is dry-run (shows what would change without modifying files).
Use --apply to actually update landmarks.json.

Usage:
    python3 tools/triangulate_lm.py "1000 Venetian Way (SW)"           # dry-run
    python3 tools/triangulate_lm.py "1000 Venetian Way (SW)" --apply   # write
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

sys.path.insert(0, REPO_DIR)
import gtamaplib as ml


def load_all():
    """Load cameras, pixels, landmarks, tiers."""
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
    cam_tiers = {}
    for n, d in tiers_data.get('cameras', {}).items():
        cam_tiers[n] = d.get('tier') if isinstance(d, dict) else d
    return cameras, pixels, landmarks, cam_tiers


def is_leak_cam(cam_data):
    """A cam is 'leak' if its source matches a date pattern YYYY-MM-DD."""
    if not isinstance(cam_data, dict):
        return False
    src = cam_data.get('source', '') or ''
    return bool(re.match(r'\d{4}-\d{2}-\d{2}', src))


def classify_cam(cam_name, cameras, cam_tiers):
    """Return 'leak', 'trusted_non_leak', or 'other'."""
    c = cameras.get(cam_name, {})
    if is_leak_cam(c):
        return 'leak'
    tier = cam_tiers.get(cam_name)
    if tier in ('anchor', 'high'):
        return 'trusted_non_leak'
    return 'other'


def select_sources(observers_classified):
    """Apply priority hierarchy. Returns (selected_cams, reason_str).

    observers_classified: dict {cam_name: classification}
    """
    leak = [n for n, c in observers_classified.items() if c == 'leak']
    trusted = [n for n, c in observers_classified.items() if c == 'trusted_non_leak']
    other = [n for n, c in observers_classified.items() if c == 'other']

    if len(leak) >= 2:
        return leak, f"2+ leak cams ({len(leak)})"
    if len(leak) >= 1 and len(trusted) >= 1:
        return leak + trusted, f"leak + trusted ({len(leak)}+{len(trusted)})"
    if len(trusted) >= 2:
        return trusted, f"2+ trusted non-leak ({len(trusted)})"
    if len(leak) >= 1:
        # Only 1 leak, no trusted. Fallback to leak + other.
        return leak + other, f"leak + other fallback ({len(leak)}+{len(other)})"
    # No leak. Use whatever we have.
    if len(other) + len(trusted) >= 2:
        return trusted + other, f"untrusted only ({len(trusted)}+{len(other)})"
    return [], "insufficient observers"


def triangulate(selected_cams, lm_name, pixels, cameras, init_xyz):
    """Multi-cam triangulation using the selected cams. Returns (xyz, max_residual_arcmin).

    Returns (None, error_str) on failure.
    """
    try:
        import numpy as np
        from scipy.optimize import minimize
    except ImportError:
        return None, "scipy/numpy not installed"

    rays = []
    for cn in selected_cams:
        if cn not in pixels.get(cn, {}) and lm_name not in pixels.get(cn, {}):
            continue
        try:
            cam = ml.get_camera(cn)
            d = cam.get_landmark_direction(lm_name)
            d = np.asarray(d, dtype=float)
            d = d / np.linalg.norm(d)
            rays.append((cn, np.asarray(cam.xyz, dtype=float), d))
        except Exception as e:
            return None, f"failed to build ray for {cn}: {e}"

    if len(rays) < 2:
        return None, f"not enough rays ({len(rays)})"

    def loss(p):
        p = np.asarray(p)
        total = 0.0
        for _, o, d in rays:
            v = p - o
            dist = np.linalg.norm(v)
            if dist < 1e-3:
                continue
            perp = v - np.dot(v, d) * d
            ang = np.linalg.norm(perp) / dist
            total += ang * ang
        return total

    result = minimize(loss, init_xyz, method='Nelder-Mead',
                      options={'xatol': 1e-3, 'fatol': 1e-12,
                               'maxiter': 10000, 'adaptive': True})
    p_new = result.x

    # Compute max residual in arcmin
    max_res = 0.0
    for _, o, d in rays:
        v = p_new - o
        dist = np.linalg.norm(v)
        if dist < 1e-3:
            continue
        perp = v - np.dot(v, d) * d
        ang_arcmin = math.degrees(np.linalg.norm(perp) / dist) * 60
        max_res = max(max_res, ang_arcmin)

    return p_new.tolist(), max_res


def main():
    parser = argparse.ArgumentParser(description="Triangulate a single LM with priority-based source selection.")
    parser.add_argument('lm_name', help="Name of the landmark to triangulate.")
    parser.add_argument('--apply', action='store_true',
                        help="Actually write the update. Default is dry-run.")
    args = parser.parse_args()

    cameras, pixels, landmarks, cam_tiers = load_all()

    lm = landmarks.get(args.lm_name)
    if lm is None:
        print(f"ERROR: LM '{args.lm_name}' not found in landmarks.json")
        return 1

    if not isinstance(lm, dict):
        print(f"ERROR: LM '{args.lm_name}' has unexpected format")
        return 1

    cur_xyz = lm.get('xyz')
    cur_err = lm.get('error_m')
    cur_sources = lm.get('source_cameras', [])

    print(f"=== {args.lm_name} ===")
    print(f"Current xyz: {cur_xyz}")
    print(f"Current error_m: {cur_err}")
    print(f"Current sources: {cur_sources}")
    print()

    # Find all cams with markings for this LM
    observers = []
    for cam_name, lm_map in pixels.items():
        if args.lm_name in lm_map:
            observers.append(cam_name)

    if not observers:
        print(f"ERROR: No cam has a pixel marking for '{args.lm_name}'")
        print(f"LM not updated, reason: no observers")
        return 1

    # Classify each observer
    observers_classified = {}
    for cam_name in observers:
        cls = classify_cam(cam_name, cameras, cam_tiers)
        observers_classified[cam_name] = cls

    print(f"Observers ({len(observers)}):")
    for cam_name, cls in observers_classified.items():
        print(f"  [{cls:18}] {cam_name}")
    print()

    # Apply priority
    selected, reason = select_sources(observers_classified)
    print(f"Selected sources ({len(selected)}): {selected}")
    print(f"Selection reason: {reason}")
    print()

    if len(selected) < 2:
        print(f"LM not updated, reason: only {len(selected)} cam(s) selected (need >= 2 for triangulation)")
        return 1

    # Triangulate
    init = cur_xyz if cur_xyz else [0.0, 0.0, 0.0]
    new_xyz, max_res = triangulate(selected, args.lm_name, pixels, cameras, init)

    if new_xyz is None:
        print(f"LM not updated, reason: {max_res}")
        return 1

    # Compute diff
    if cur_xyz:
        delta = math.sqrt(sum((new_xyz[i] - cur_xyz[i]) ** 2 for i in range(3)))
    else:
        delta = None

    print(f"Triangulation result:")
    print(f"  New xyz: [{new_xyz[0]:.4f}, {new_xyz[1]:.4f}, {new_xyz[2]:.4f}]")
    print(f"  Max residual: {max_res:.3f} arcmin")
    if delta is not None:
        print(f"  Delta from current: {delta:.3f} m")
    print()

    if not args.apply:
        print("DRY-RUN: not writing. Use --apply to actually update.")
        return 0

    # Apply
    lm['xyz'] = new_xyz
    lm['error_m'] = round(float(max_res), 3)
    lm['source_cameras'] = selected
    landmarks[args.lm_name] = lm

    with open(LANDMARKS_JSON, 'w') as f:
        json.dump(landmarks, f, indent=2)

    print(f"APPLIED: landmarks.json updated.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
