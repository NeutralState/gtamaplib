#!/usr/bin/env python3
"""
refine_camera.py — Refine a single camera's ypr (and optionally hfov) keeping
xyz fixed. Uses only the landmarks where OTHER cameras agree on the position
(consensus landmarks), so the refinement is anchored to high-confidence truth.

This is the right tool when:
  - The camera's position (xyz) is known/correct
  - The orientation (ypr) and/or hfov are off
  - You don't need a full grid search — local refinement is enough

Usage:
    python3 tools/refine_camera.py "Ambrosia 04 (Fires)"
    python3 tools/refine_camera.py "U-Turn (NW)" --no-hfov
    python3 tools/refine_camera.py "Ambrosia 04 (Fires)" --apply

By default the script DOES NOT modify cameras.json — it just prints what the
optimal values would be. Add --apply to write changes.
"""

import argparse
import os
import sys
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

CONSENSUS_THRESHOLD = 5.0  # arcmin — landmarks where ≥1 other cam projects this close

# ── Args ──────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser()
parser.add_argument('cam_name')
parser.add_argument('--apply', action='store_true',
                    help='Write the refined values to cameras.json')
parser.add_argument('--no-hfov', action='store_true',
                    help='Keep hfov fixed (only refine yaw + pitch)')
parser.add_argument('--refine-xyz', action='store_true',
                    help='Also refine x, y, z (allows up to ±xyz_radius m of movement)')
parser.add_argument('--xyz-radius', type=float, default=300.0,
                    help='Max xyz movement in meters when --refine-xyz is set (default: 300)')
args = parser.parse_args()

CAM_NAME = args.cam_name

# ── Build consensus set ───────────────────────────────────────────────────────

print(f"Building consensus landmark set for {CAM_NAME}...")

cam_data = md.cameras.get(CAM_NAME)
if not cam_data or not cam_data.get('xyz'):
    print(f"  ERROR: {CAM_NAME} not found or has no xyz")
    sys.exit(1)

cam_pixels = md.pixels.get(CAM_NAME, {})
if not cam_pixels:
    print(f"  ERROR: {CAM_NAME} has no marked pixels")
    sys.exit(1)

# For each landmark observed by this cam, check if other cams agree on its position
consensus_lms = []  # [(lm_name, n_agreeing_other_cams), ...]
for lm_name, pixel in cam_pixels.items():
    lm_xyz = md.landmarks.get(lm_name)
    if lm_xyz is None:
        continue
    n_agreeing = 0
    for other_cam, other_pixels in md.pixels.items():
        if other_cam == CAM_NAME:
            continue
        if lm_name not in other_pixels:
            continue
        if not md.cameras.get(other_cam, {}).get('xyz'):
            continue
        try:
            oc = ml.get_camera(other_cam)
            proj = oc.get_pixel(lm_xyz)
            if proj is None:
                continue
            opx, opy = other_pixels[lm_name]
            dx = (float(proj[0]) - float(opx)) * oc.hfov / oc.w * 60.0
            dy = (float(proj[1]) - float(opy)) * oc.vfov / oc.h * 60.0
            err = (dx*dx + dy*dy) ** 0.5
            if err < CONSENSUS_THRESHOLD:
                n_agreeing += 1
        except Exception:
            continue
    if n_agreeing >= 1:
        consensus_lms.append((lm_name, n_agreeing))

consensus_lms.sort(key=lambda x: -x[1])

if len(consensus_lms) < 3:
    print(f"  ⚠ Only {len(consensus_lms)} consensus landmarks found — "
          f"refinement may be unreliable.")
    print(f"  Need at least 3, ideally 6+, with ≥2 agreeing other cams.")
else:
    print(f"  Found {len(consensus_lms)} consensus landmarks "
          f"(others agree to within {CONSENSUS_THRESHOLD}'):")
for lm, n in consensus_lms:
    print(f"    {lm}  ({n} other cams agree)")

if len(consensus_lms) < 3:
    sys.exit(1)

# ── Refinement ────────────────────────────────────────────────────────────────

cam = ml.get_camera(CAM_NAME)
xyz = tuple(cam_data['xyz'])
ypr0 = list(cam_data.get('ypr') or [0, 0, 0])
fov0 = cam_data.get('fov') or [60, None]
hfov0 = fov0[0]
size = cam_data.get('size') or [1920, 1080]
if hfov0 is None:
    hfov0 = ml.get_hfov(fov0[1], size) if fov0[1] is not None else 60.0

print(f"\nInitial: yaw={ypr0[0]:.3f}, pitch={ypr0[1]:.3f}, hfov={hfov0:.3f}")

def loss_fn(params, return_residuals=False):
    """
    params layout depends on flags:
       no-hfov, no-xyz : [yaw, pitch]
       hfov,    no-xyz : [yaw, pitch, hfov]
       no-hfov, xyz    : [x, y, z, yaw, pitch]
       hfov,    xyz    : [x, y, z, yaw, pitch, hfov]
    """
    if args.refine_xyz:
        x, y, z, yaw, pitch = params[0], params[1], params[2], params[3], params[4]
        hfov = params[5] if len(params) > 5 else hfov0
        cur_xyz = (x, y, z)
        # Penalty if outside xyz_radius
        dist_sq = (x - xyz[0])**2 + (y - xyz[1])**2 + (z - xyz[2])**2
        penalty = 0.0
        if dist_sq > args.xyz_radius**2:
            penalty = (dist_sq - args.xyz_radius**2) * 1e3
    else:
        cur_xyz = xyz
        yaw, pitch = params[0], params[1]
        hfov = params[2] if len(params) > 2 else hfov0
        penalty = 0.0

    cam.set_xyz(cur_xyz)
    cam.set_ypr((yaw, pitch, 0.0))
    cam.set_fov((hfov, None))
    cam.clear_landmark_directions()
    total = 0.0
    n = 0
    residuals = []
    for lm_name, _ in consensus_lms:
        try:
            proj = cam.get_pixel(md.landmarks[lm_name])
            if proj is None:
                continue
            px, py = cam_pixels[lm_name]
            dx = (float(proj[0]) - float(px)) * cam.hfov / cam.w * 60.0
            dy = (float(proj[1]) - float(py)) * cam.vfov / cam.h * 60.0
            err_sq = dx*dx + dy*dy
            total += err_sq
            n += 1
            residuals.append((lm_name, (err_sq) ** 0.5))
        except Exception:
            continue
    if n == 0:
        return (1e10, []) if return_residuals else 1e10
    rms = (total / n) ** 0.5
    if return_residuals:
        return rms, residuals
    return rms + penalty

# Build initial guess + final guess
def build_x0_with_hfov(use_hfov):
    if args.refine_xyz:
        base = [xyz[0], xyz[1], xyz[2], ypr0[0], ypr0[1]]
    else:
        base = [ypr0[0], ypr0[1]]
    if use_hfov:
        base.append(hfov0)
    return base

# Compute initial loss
x0_init = build_x0_with_hfov(use_hfov=True)
initial_rms, initial_resids = loss_fn(x0_init, return_residuals=True)
print(f"Initial RMS on consensus landmarks: {initial_rms:.2f}'")

# Optimize
x0 = build_x0_with_hfov(use_hfov=not args.no_hfov)

flags = []
if args.refine_xyz: flags.append(f'xyz (±{args.xyz_radius:.0f}m)')
flags.append('yaw, pitch')
if not args.no_hfov: flags.append('hfov')
print(f"\nOptimizing {', '.join(flags)}...")

result = minimize(loss_fn, x0, method='Nelder-Mead',
                  options={'xatol': 1e-5, 'fatol': 1e-6, 'maxiter': 20000, 'adaptive': True})

# Unpack
if args.refine_xyz:
    x_new, y_new, z_new = result.x[0], result.x[1], result.x[2]
    yaw_new, pitch_new = result.x[3], result.x[4]
    hfov_new = result.x[5] if len(result.x) > 5 else hfov0
else:
    x_new, y_new, z_new = xyz
    yaw_new, pitch_new = result.x[0], result.x[1]
    hfov_new = result.x[2] if len(result.x) > 2 else hfov0

# Compute final loss + residuals (using the same param layout)
final_rms, final_resids = loss_fn(result.x, return_residuals=True)

print(f"Final RMS:   {final_rms:.2f}'  (initial was {initial_rms:.2f}')")
print(f"Improvement: {(initial_rms - final_rms) / initial_rms * 100:.1f}%")
print()
if args.refine_xyz:
    print(f"  x     {xyz[0]:>9.2f}  →  {x_new:>9.2f}   (Δ {x_new - xyz[0]:+.2f} m)")
    print(f"  y     {xyz[1]:>9.2f}  →  {y_new:>9.2f}   (Δ {y_new - xyz[1]:+.2f} m)")
    print(f"  z     {xyz[2]:>9.2f}  →  {z_new:>9.2f}   (Δ {z_new - xyz[2]:+.2f} m)")
    dist = ((x_new - xyz[0])**2 + (y_new - xyz[1])**2 + (z_new - xyz[2])**2) ** 0.5
    print(f"  total xyz movement: {dist:.1f} m")
print(f"  yaw   {ypr0[0]:>9.3f}  →  {yaw_new:>9.3f}   (Δ {yaw_new - ypr0[0]:+.3f}°)")
print(f"  pitch {ypr0[1]:>9.3f}  →  {pitch_new:>9.3f}   (Δ {pitch_new - ypr0[1]:+.3f}°)")
if not args.no_hfov:
    print(f"  hfov  {hfov0:>9.3f}  →  {hfov_new:>9.3f}   (Δ {hfov_new - hfov0:+.3f}°)")

print(f"\nPer-landmark residuals (consensus landmarks only):")
print(f"  {'landmark':<40}  {'before':>8}  {'after':>8}")
print(f"  {'-'*40}  {'-'*8}  {'-'*8}")
before = dict(initial_resids)
after  = dict(final_resids)
for lm, _ in consensus_lms:
    b = before.get(lm, 0)
    a = after.get(lm, 0)
    print(f"  {lm[:40]:<40}  {b:>7.1f}'  {a:>7.1f}'")

# ── Apply ─────────────────────────────────────────────────────────────────────

if args.apply:
    print(f"\nApplying changes to cameras.json...")
    new_fov = [round(hfov_new, 4), fov0[1]]
    new_xyz = [round(x_new, 4), round(y_new, 4), round(z_new, 4)] if args.refine_xyz else list(xyz)
    md.update_camera(
        CAM_NAME,
        xyz=new_xyz,
        ypr=[round(yaw_new, 4), round(pitch_new, 4), 0.0],
        fov=new_fov,
    )
    print(f"  Done. Changes written to {os.path.join(GTAMAP_DIR, 'gtamapdata', 'cameras.json')}")
    print(f"  Review with: git diff gtamapdata/cameras.json")
else:
    print(f"\n(dry run — re-run with --apply to write to cameras.json)")
