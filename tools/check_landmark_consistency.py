#!/usr/bin/env python3
"""
check_landmark_consistency.py — Detect landmarks where different cameras seem
to have marked different physical points (e.g. different corners of a building).

For each landmark, compute the angular error each marked pixel would have
against the current xyz position, then flag landmarks where the angular
spread suggests the cameras are not actually looking at the same point.

This is a fast diagnostic — it doesn't run optimization, just reads the
existing camera params and pixel marks.

Run from gtamaplib-main/:
    python3 tools/check_landmark_consistency.py
"""

import os
import sys
from collections import defaultdict

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

# ── Build per-landmark observation list ───────────────────────────────────────

lm_observations = defaultdict(list)  # lm_name -> list of (cam_name, px, py, error_arcmin)

print("Computing per-observation errors...")
n_cams_with_xyz = 0
for cam_name, cam_pixels in md.pixels.items():
    cam_data = md.cameras.get(cam_name, {})
    if not cam_data.get('xyz'):
        continue
    n_cams_with_xyz += 1
    cam = ml.get_camera(cam_name)
    for lm_name, pixel in cam_pixels.items():
        lm_xyz = md.landmarks.get(lm_name)
        if lm_xyz is None:
            continue
        try:
            proj = cam.get_pixel(lm_xyz)
            if proj is None:
                continue
            dx = (float(proj[0]) - float(pixel[0])) * cam.hfov / cam.w * 60.0
            dy = (float(proj[1]) - float(pixel[1])) * cam.vfov / cam.h * 60.0
            err = (dx*dx + dy*dy) ** 0.5
            lm_observations[lm_name].append((cam_name, pixel[0], pixel[1], err))
        except Exception:
            continue

print(f"Scanned {n_cams_with_xyz} calibrated cameras")
print(f"Landmarks with observations: {len(lm_observations)}")

# ── Identify suspicious landmarks ─────────────────────────────────────────────
# A landmark is suspicious if:
#   - It has at least 2 observations (need divergence to detect)
#   - The MIN observation error is high enough to indicate the lm is wrong
#     OR the SPREAD between min and max errors is high (suggests different
#     points being marked across cams).

# Score = sum of squared errors over all observations (same metric as bundle).
suspicious = []
for lm_name, obs_list in lm_observations.items():
    if len(obs_list) < 2:
        continue
    errors = sorted(o[3] for o in obs_list)
    score   = sum(e*e for e in errors)
    err_min = errors[0]
    err_max = errors[-1]
    err_med = errors[len(errors)//2]
    spread  = err_max - err_min

    # Skip clean landmarks
    if err_max < 5.0:
        continue

    suspicious.append({
        'landmark': lm_name,
        'n_obs': len(obs_list),
        'err_min': err_min,
        'err_med': err_med,
        'err_max': err_max,
        'spread':  spread,
        'score':   score,
        'obs':     obs_list,
    })

suspicious.sort(key=lambda d: d['score'], reverse=True)

print(f"Landmarks with worst-error >= 5': {len(suspicious)}")
print()

# ── Print report ──────────────────────────────────────────────────────────────

print("─" * 92)
print(f"{'#':>3}  {'landmark':<40}  {'#obs':>4}  {'min':>6} {'med':>6} {'max':>6} {'spread':>7}  {'note':<10}")
print("─" * 92)

for i, s in enumerate(suspicious[:40]):
    # Heuristic for hint:
    #   - high min  → landmark itself is likely mis-positioned
    #   - high spread + low min → cameras are marking different points
    if s['err_min'] < 5 and s['spread'] > 30:
        hint = 'DIVERGENT'   # different points marked
    elif s['err_min'] > 30:
        hint = 'BAD POS'     # landmark xyz wrong
    elif s['err_min'] > 10:
        hint = 'fuzzy'
    else:
        hint = ''

    name = s['landmark']
    if len(name) > 40: name = name[:37] + '...'
    print(f"{i+1:>3}  {name:<40}  {s['n_obs']:>4}  "
          f"{s['err_min']:>5.1f}' {s['err_med']:>5.1f}' {s['err_max']:>5.1f}' "
          f"{s['spread']:>6.1f}'  {hint:<10}")

print()
print("Legend:")
print("  DIVERGENT  → low min error but high spread = cameras marked different points")
print("               on the same object (e.g. different corners). Consider splitting")
print("               into multiple sub-landmarks (NE), (SW), etc.")
print("  BAD POS    → all cameras report large error = landmark xyz is wrong.")
print("               Re-triangulate from the most trusted cameras.")
print("  fuzzy      → moderate errors, may improve after bundle adjustment.")
