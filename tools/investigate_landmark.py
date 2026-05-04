#!/usr/bin/env python3
"""
investigate_landmark.py — For a given landmark, show where each camera's
marked pixel ACTUALLY points at z=0 ground level. If the various ground
points are far apart, the cameras are not looking at the same physical
object — name collision or mislabeling.

Usage:
    python3 tools/investigate_landmark.py "Easy Hill"
    python3 tools/investigate_landmark.py "Easy Inn Sign"
"""

import argparse
import os
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

parser = argparse.ArgumentParser()
parser.add_argument('landmark')
args = parser.parse_args()

LM = args.landmark

if LM not in md.landmarks:
    print(f"Landmark '{LM}' not found")
    sys.exit(1)

cur_xyz = md.landmarks[LM]
print(f"━━━ {LM} ━━━")
print(f"Current xyz in landmarks.json: ({cur_xyz[0]:.0f}, {cur_xyz[1]:.0f}, {cur_xyz[2]:.0f})")
print(f"Source cameras:                 {md.landmarks_meta[LM].get('source_cameras')}")
print()

# Find all cams that have this lm in pixels
cams_with_lm = []
for cam_name, pxs in md.pixels.items():
    if LM in pxs:
        cam_data = md.cameras.get(cam_name)
        if cam_data and cam_data.get('xyz'):
            cams_with_lm.append((cam_name, pxs[LM]))

if not cams_with_lm:
    print("No cameras have pixels for this landmark.")
    sys.exit(0)

print(f"Cameras with marked pixels (n={len(cams_with_lm)}):")
print(f"  {'camera':<28}  {'pixel':<14}  {'ground point at z=0':<30}  {'dist from cur':>12}")
print(f"  {'-'*28}  {'-'*14}  {'-'*30}  {'-'*12}")

ground_points = []
for cam_name, pixel in cams_with_lm:
    cam = ml.get_camera(cam_name)
    try:
        gp = cam.get_point_at_zero_elevation(pixel)
    except Exception:
        gp = None
    if gp is None:
        # Above horizon: print ray direction instead
        try:
            ray_dir = cam.get_landmark_direction(LM)
            ray_str = f"above horizon, dir=({ray_dir[0]:.2f},{ray_dir[1]:.2f},{ray_dir[2]:.2f})"
        except Exception:
            ray_str = "could not compute ray"
        print(f"  {cam_name[:28]:<28}  {str(pixel):<14}  {ray_str}")
    else:
        gx, gy = gp[0], gp[1]
        dist_from_cur = ((gx - cur_xyz[0])**2 + (gy - cur_xyz[1])**2) ** 0.5
        ground_str = f"({gx:.0f}, {gy:.0f})"
        print(f"  {cam_name[:28]:<28}  {str(pixel):<14}  {ground_str:<30}  {dist_from_cur:>10.0f}m")
        ground_points.append((cam_name, gx, gy))

# Compute pairwise distances between ground points to detect divergence
print()
if len(ground_points) >= 2:
    print("Pairwise distances between ground points (z=0 projections):")
    print(f"  {'cam_a':<28}  {'cam_b':<28}  {'distance':>10}")
    print(f"  {'-'*28}  {'-'*28}  {'-'*10}")
    max_dist = 0.0
    for i, (ca, xa, ya) in enumerate(ground_points):
        for cb, xb, yb in ground_points[i+1:]:
            d = ((xa - xb)**2 + (ya - yb)**2) ** 0.5
            max_dist = max(max_dist, d)
            flag = '  ← LARGE GAP' if d > 200 else ''
            print(f"  {ca[:28]:<28}  {cb[:28]:<28}  {d:>9.0f}m{flag}")

    print()
    if max_dist < 50:
        print(f"VERDICT: All cameras agree on a single ground point (max gap {max_dist:.0f}m)")
        print(f"         If errors are still high, the landmark elevation (z) might be off.")
    elif max_dist < 200:
        print(f"VERDICT: Cameras roughly agree (max gap {max_dist:.0f}m). Re-triangulate.")
    else:
        print(f"VERDICT: Cameras disagree by up to {max_dist:.0f}m — NAME COLLISION likely.")
        print(f"         Different cameras have marked pixels on different physical objects")
        print(f"         and called them all '{LM}'. Some pixels need to be renamed or removed.")
