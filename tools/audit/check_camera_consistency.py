#!/usr/bin/env python3
"""
check_camera_consistency.py — For each camera, count how often it produces
extremely large reprojection errors across the landmarks it observes.

If a single camera is mis-calibrated, it will be the "outlier camera" for many
landmarks simultaneously. This script ranks cameras by how often they appear
as the worst observation for a given landmark.

Run from gtamaplib-main/:
    python3 tools/check_camera_consistency.py
"""

import os
import sys
from collections import defaultdict

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]
import gtamaplib as ml
import gtamapdata as md

# ── Compute per-obs errors ────────────────────────────────────────────────────

lm_observations = defaultdict(list)  # lm_name -> [(cam_name, error_arcmin), ...]

for cam_name, cam_pixels in md.pixels.items():
    cam_data = md.cameras.get(cam_name, {})
    if not cam_data.get('xyz'):
        continue
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
            lm_observations[lm_name].append((cam_name, err))
        except Exception:
            continue

# ── For each landmark with ≥2 obs, find which cam is the worst ────────────────

# Track per cam:
#   - n_worst: how many times this cam is the WORST observation of a landmark
#              while other cams agree (sub-5 arcmin) — this strongly suggests
#              the cam itself is wrong
#   - errors_when_worst: list of error magnitudes when this cam is the worst
#   - n_obs_total: total observations made by this cam

cam_stats = defaultdict(lambda: {
    'n_worst_among_agreeing': 0,
    'n_obs_total': 0,
    'errors_when_worst': [],
    'all_errors': [],
})

for lm_name, obs_list in lm_observations.items():
    if len(obs_list) < 2:
        for cam_name, err in obs_list:
            cam_stats[cam_name]['n_obs_total'] += 1
            cam_stats[cam_name]['all_errors'].append(err)
        continue

    sorted_obs = sorted(obs_list, key=lambda x: x[1])
    others = sorted_obs[:-1]
    worst_cam, worst_err = sorted_obs[-1]

    # Are the OTHER cams in agreement (sub-5 arcmin)?
    other_max = max(e for _, e in others) if others else 999
    agreeing = other_max < 5.0

    for cam_name, err in obs_list:
        cam_stats[cam_name]['n_obs_total'] += 1
        cam_stats[cam_name]['all_errors'].append(err)

    # Only flag if other cams agree AND this one is much worse
    if agreeing and worst_err > 30.0:
        cam_stats[worst_cam]['n_worst_among_agreeing'] += 1
        cam_stats[worst_cam]['errors_when_worst'].append(worst_err)

# ── Report ────────────────────────────────────────────────────────────────────

ranked = sorted(
    cam_stats.items(),
    key=lambda kv: (kv[1]['n_worst_among_agreeing'], sum(kv[1]['errors_when_worst'])),
    reverse=True,
)

print()
print("─" * 100)
print(f"{'#':>3}  {'camera':<40}  {'#worst':>7} {'#obs':>5}  {'rate':>5}  {'med err':>8}  {'max err':>8}")
print("─" * 100)
print("  '#worst' = number of landmarks where this cam was THE outlier")
print("            while OTHER cams on the same landmark agreed (<5')")
print("─" * 100)

for i, (cam_name, s) in enumerate(ranked[:30]):
    n_worst = s['n_worst_among_agreeing']
    n_total = s['n_obs_total']
    if n_worst == 0 and i > 5:
        break
    rate = (n_worst / n_total * 100) if n_total > 0 else 0
    med_when_worst = sorted(s['errors_when_worst'])[len(s['errors_when_worst'])//2] if s['errors_when_worst'] else 0
    max_when_worst = max(s['errors_when_worst']) if s['errors_when_worst'] else 0
    name = cam_name if len(cam_name) <= 40 else cam_name[:37] + '...'
    print(f"{i+1:>3}  {name:<40}  {n_worst:>7} {n_total:>5}  {rate:>4.0f}%  "
          f"{med_when_worst:>7.0f}'  {max_when_worst:>7.0f}'")

print()
print("If a camera tops this list with high #worst and high rate, its calibration")
print("(xyz, ypr, or hfov) is probably significantly off — fix the camera before")
print("touching any pixels it observes.")
