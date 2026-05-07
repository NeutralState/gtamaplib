#!/usr/bin/env python3
"""
bundle_adjust.py — Global bundle adjustment for gtamaplib
Optimizes all non-leak cameras and non-fixed landmarks simultaneously.

Run from gtamaplib-main/:
    python3 tools/bundle_adjust.py

Output: tools/bundle_adjust_result.json
"""

import json
import math
import os
import sys
import numpy as np
from scipy.optimize import least_squares

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

print("gtamaplib loaded ✓")

# ── Identify leak cameras (fixed — exact positions from game engine) ──────────

LEAK_CAMS = {
    'Tennis Stadium (4K)', 'Vice Beach (A)', 'Vice Beach (B)',
    'Metro (SE) (A) (4K)', 'Alley (W)', 'Park', 'Port',
    'Tennis Court (SE)', 'Tennis Court (NE)', 'Tennis Court (N)', 'Tennis Court (SW)',
    'AI World Editor Map (4K)',
    'Diner (W) (A)', 'Diner (W) (B)', 'Diner (N)', 'Diner (NW)', 'Diner (NE)',
    'Diner (E)', 'Diner (SE) (A)', 'Diner (SE) (B)', 'Diner (S)', 'Diner (SW)', 'Diner',
    'Gas Station (Lucia)', 'Gas Station (Jason)',
    'Loading Zone near Prison (SW)', 'Loading Zone near Prison (N)',
    'Ocean near Keys (N)', 'Ocean near Keys (E)', 'House with Boat (X)',
    'Highway (NE)', 'Sidewalk (Jason) (E)', 'Sidewalk (Jason) (S)',
    'Welcome Center (E)', 'Welcome Center (W)', 'Police Chase (A)', 'Police Chase (D)',
    'Airport (X)', 'Car Wash', 'Glitch (A)', 'Grassrivers Postcard (X)',
    'Handlebar (SE)', 'Handlebar (SW)', 'Hedge (B) (X)', 'Hotel (W)',
    'Intersection (W)', 'Penthouse (NE)', 'Penthouse (NW)',
    'Penthouse (SE)', 'Penthouse (SW)', 'Pool', 'Rooftop (SE)',
}

# ── Build optimization problem ────────────────────────────────────────────────

# Cameras to optimize: have pixels, not a leak, have xyz
opt_cam_names = sorted([
    n for n in md.pixels
    if n not in LEAK_CAMS and md.cameras.get(n, {}).get('xyz')
])

# Landmarks to optimize: have xyz, not exclusively from leak cams
opt_lm_names = sorted([
    n for n, data in md.landmarks_meta.items()
    if md.landmarks.get(n) is not None
    and not all(s in LEAK_CAMS for s in data.get('source_cameras', []))
    and data.get('source_cameras')  # must have at least one source
])

# Fixed landmarks: sourced only from leak cams or manual
fixed_lm_names = set(md.landmarks.keys()) - set(opt_lm_names)

print(f"Optimizable cameras: {len(opt_cam_names)}")
print(f"Optimizable landmarks: {len(opt_lm_names)}")
print(f"Fixed landmarks: {len(fixed_lm_names)}")

# Index maps
cam_idx = {n: i for i, n in enumerate(opt_cam_names)}
lm_idx  = {n: i for i, n in enumerate(opt_lm_names)}

N_CAM = len(opt_cam_names)
N_LM  = len(opt_lm_names)
N_VARS = N_CAM * 6 + N_LM * 3
print(f"Total variables: {N_VARS}")

# Build list of observations: (cam_name, lm_name, px, py)
observations = []
for cam_name, cam_pixels in md.pixels.items():
    for lm_name, pixel in cam_pixels.items():
        lm_xyz = md.landmarks.get(lm_name)
        if lm_xyz is None:
            continue
        observations.append((cam_name, lm_name, float(pixel[0]), float(pixel[1])))

print(f"Total observations: {len(observations)}")
print(f"Residuals: {len(observations)*2} (2 per obs)")

# ── Initial parameter vector ───────────────────────────────────────────────────

def pack_params(cam_params, lm_params):
    """Pack camera and landmark params into a flat vector."""
    return np.concatenate([cam_params.ravel(), lm_params.ravel()])

def unpack_params(x):
    cam_params = x[:N_CAM*6].reshape(N_CAM, 6)
    lm_params  = x[N_CAM*6:].reshape(N_LM, 3)
    return cam_params, lm_params

# Initialize from current values
cam_params_init = np.zeros((N_CAM, 6))
for i, cam_name in enumerate(opt_cam_names):
    cam = md.cameras[cam_name]
    xyz = cam.get('xyz') or [0, 0, 0]
    ypr = cam.get('ypr') or [0, 0, 0]
    fov = cam.get('fov') or [60, None]
    cam_params_init[i] = [xyz[0], xyz[1], xyz[2], ypr[0], ypr[1], fov[0]]

lm_params_init = np.zeros((N_LM, 3))
for i, lm_name in enumerate(opt_lm_names):
    xyz = md.landmarks[lm_name]
    lm_params_init[i] = [xyz[0], xyz[1], xyz[2]]

x0 = pack_params(cam_params_init, lm_params_init)

# ── Residual function ──────────────────────────────────────────────────────────

def pixel_residuals(x):
    cam_params, lm_params = unpack_params(x)
    residuals = []

    for cam_name, lm_name, px_marked, py_marked in observations:
        # Get camera params
        if cam_name in cam_idx:
            cp = cam_params[cam_idx[cam_name]]
            xyz = list(cp[:3])
            ypr = [float(cp[3]), float(cp[4]), 0.0]
            hfov = float(cp[5])
        elif cam_name in LEAK_CAMS:
            cam_data = md.cameras[cam_name]
            xyz = list(cam_data.get('xyz') or [0,0,0])
            ypr = list(cam_data.get('ypr') or [0,0,0])
            hfov = (cam_data.get('fov') or [60])[0] or 60.0
        else:
            residuals.extend([0.0, 0.0])
            continue

        # Get landmark xyz
        if lm_name in lm_idx:
            lm_xyz = list(lm_params[lm_idx[lm_name]])
        elif lm_name in md.landmarks and md.landmarks[lm_name] is not None:
            lm_xyz = list(md.landmarks[lm_name])
        else:
            residuals.extend([0.0, 0.0])
            continue

        # Compute projected pixel
        try:
            cam = ml.get_camera(cam_name)
            cam.set_xyz(xyz)
            cam.set_ypr(ypr)
            cam.set_fov((hfov, None))
            proj = cam.get_pixel(lm_xyz)
            if proj is None:
                residuals.extend([100.0, 100.0])
                continue
            # Residuals in angular units (arcmin)
            dx = (float(proj[0]) - px_marked) * hfov / cam.w * 60
            dy = (float(proj[1]) - py_marked) * cam.vfov / cam.h * 60
            residuals.extend([dx, dy])
        except Exception:
            residuals.extend([100.0, 100.0])

    return np.array(residuals)

# ── Compute initial loss ───────────────────────────────────────────────────────

print("\nComputing initial residuals...")
r0 = pixel_residuals(x0)
initial_loss = np.sqrt(np.mean(r0**2))
print(f"Initial RMS loss: {initial_loss:.4f} arcmin")

# ── Run bundle adjustment ──────────────────────────────────────────────────────

print(f"\nRunning bundle adjustment ({N_VARS} variables, {len(r0)} residuals)...")
print("This may take a few minutes...\n")

from scipy.optimize import minimize
def scalar_objective(x):
    r = pixel_residuals(x)
    return float(np.mean(r**2))

result_opt = minimize(
    scalar_objective, x0,
    method='L-BFGS-B',
    options={'maxiter': 500, 'disp': True, 'ftol': 1e-8},
)

class FakeResult:
    x = result_opt.x
    fun = pixel_residuals(result_opt.x)
result = FakeResult()

final_loss = np.sqrt(np.mean(result.fun**2))
print(f"\nFinal RMS loss: {final_loss:.4f} arcmin")
print(f"Improvement: {(initial_loss - final_loss) / initial_loss * 100:.1f}%")

# ── Save results ───────────────────────────────────────────────────────────────

cam_params_final, lm_params_final = unpack_params(result.x)

output = {
    'initial_loss': round(float(initial_loss), 4),
    'final_loss': round(float(final_loss), 4),
    'improvement_pct': round(float((initial_loss - final_loss) / initial_loss * 100), 1),
    'cameras': {},
    'landmarks': {},
}

for i, cam_name in enumerate(opt_cam_names):
    cp = cam_params_final[i]
    output['cameras'][cam_name] = {
        'xyz': [round(float(v), 4) for v in cp[:3]],
        'ypr': [round(float(cp[3]), 4), round(float(cp[4]), 4), 0.0],
        'hfov': round(float(cp[5]), 4),
    }

for i, lm_name in enumerate(opt_lm_names):
    lp = lm_params_final[i]
    output['landmarks'][lm_name] = [round(float(v), 4) for v in lp]

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bundle_adjust_result.json')
with open(out_path, 'w') as f:
    json.dump(output, f, indent=2)

print(f"\nResults saved to: {out_path}")
print(f"  {len(output['cameras'])} cameras optimized")
print(f"  {len(output['landmarks'])} landmarks optimized")
print("\nTo apply results, run: python3 tools/bundle_adjust_apply.py")
