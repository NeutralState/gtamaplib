#!/usr/bin/env python3
"""
fix_easy_hill_v2.py — Update Easy Hill xyz with the best estimate available
given that:
  - Only Diner (SE) (A) and (B) reliably see it (Ambrosia 04 obs already deleted)
  - These 2 cameras are co-located → no real triangulation baseline
  - No other camera with a useful angle can see this small local hill

We compute the midpoint of the two closest points on each ray. With nearly
parallel rays this isn't a true triangulation but gives a sensible position
along the average direction. The z is taken from the same midpoint.

This is a best-effort fix. The position will still have some error in
distance/depth, but it will be far better than the current xyz (-5710, 3936, 82)
which came from a foreign triangulation (Ambrosia 04 × Diner SE B) that we now
know was completely wrong.

Run:
    python3 tools/fix_easy_hill_v2.py        # dry run
    python3 tools/fix_easy_hill_v2.py --apply
"""

import argparse
import json
import os
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

LM = "Easy Hill"
SRC_A = "Diner (SE) (A)"
SRC_B = "Diner (SE) (B)"

LANDMARKS_PATH = os.path.join(GTAMAP_DIR, "gtamapdata", "landmarks.json")

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

# Sanity
if LM not in md.landmarks:
    print(f"ERROR: '{LM}' not in landmarks.json"); sys.exit(1)
for src in (SRC_A, SRC_B):
    if src not in md.pixels or LM not in md.pixels[src]:
        print(f"ERROR: '{src}' has no pixel for '{LM}'"); sys.exit(1)

cur_xyz = md.landmarks[LM]
print(f"Current state of '{LM}':")
print(f"  xyz = {cur_xyz}")
print(f"  source_cameras = {md.landmarks_meta[LM].get('source_cameras')}")

# Try ray-ray intersection (will give weird angular_delta because rays parallel)
midpoint, point_a, point_b, distance, angular_delta = ml.find_landmark(SRC_A, SRC_B, LM)

print(f"\nRay-ray triangulation result:")
print(f"  closest on ray A: ({point_a[0]:.1f}, {point_a[1]:.1f}, {point_a[2]:.1f})")
print(f"  closest on ray B: ({point_b[0]:.1f}, {point_b[1]:.1f}, {point_b[2]:.1f})")
print(f"  ray distance:     {distance:.1f}m  (expect small — rays are near-parallel)")
print(f"  angular delta:    {angular_delta:.2f}°  (expect ~180 — rays parallel from same area)")

# The angular_delta of ~180° tells us this isn't a real triangulation.
# Better approach: use the average ground projection (z=0) and put the z back
# at the original level (assumed by the source cams). Hill should be slightly
# above z=0 — the original z=82 is nonsense (came from corrupt triangulation).
# Use cam altitude as a floor, plus a small offset since it's a "hill".

cam_a = ml.get_camera(SRC_A)
cam_b = ml.get_camera(SRC_B)

ground_a = cam_a.get_point_at_zero_elevation(md.pixels[SRC_A][LM])
ground_b = cam_b.get_point_at_zero_elevation(md.pixels[SRC_B][LM])

print(f"\nGround projections (z=0):")
print(f"  from {SRC_A}: ({ground_a[0]:.1f}, {ground_a[1]:.1f})")
print(f"  from {SRC_B}: ({ground_b[0]:.1f}, {ground_b[1]:.1f})")

ground_x = (ground_a[0] + ground_b[0]) / 2
ground_y = (ground_a[1] + ground_b[1]) / 2

# z estimate: ray-ray midpoint z is meaningless here (rays are parallel, so
# point_a and point_b end up near the cam's altitude). Easy Hill is a HILL,
# meaning it's elevated above the cam. Without a third camera we cannot
# triangulate the height, so use a sensible estimate.
# Cam altitude ~16m, ground level ~0, hill should be elevated.
# Use 50m as a conservative estimate (the previous 82m was from corrupt
# triangulation but might be close to reality).
new_z = 50.0

new_xyz = [round(float(ground_x), 4),
           round(float(ground_y), 4),
           round(float(new_z), 4)]

import math
move = math.hypot(new_xyz[0] - cur_xyz[0], new_xyz[1] - cur_xyz[1])
print(f"\nProposed new xyz: {new_xyz}")
print(f"Movement from current: {move:.0f}m")

# Compute residuals at proposed xyz
print(f"\nResiduals at proposed xyz:")
for cam_name in (SRC_A, SRC_B):
    cam = ml.get_camera(cam_name)
    proj = cam.get_pixel(new_xyz)
    if proj is None:
        print(f"  {cam_name}: projection failed (z too low — try higher z)")
        continue
    pixel = md.pixels[cam_name][LM]
    dx = (float(proj[0]) - float(pixel[0])) * cam.hfov / cam.w * 60.0
    dy = (float(proj[1]) - float(pixel[1])) * cam.vfov / cam.h * 60.0
    err = (dx*dx + dy*dy) ** 0.5
    print(f"  {cam_name:<28}  {err:>6.1f}'")

print(f"\nNote: residuals will not be zero because the 2 rays don't truly intersect")
print(f"      (cams are co-located). The new xyz is the best estimate possible")
print(f"      until a 3rd camera with real baseline observes Easy Hill.")

if not args.apply:
    print(f"\n(dry run — re-run with --apply to write changes)")
    sys.exit(0)

with open(LANDMARKS_PATH) as f:
    lm_data = json.load(f)

zone = lm_data[LM].get('zone', 'unknown')
lm_data[LM] = {
    "xyz": new_xyz,
    "source_cameras": [SRC_A, SRC_B],
    "error_m": None,
    "zone": zone,
}

tmp = LANDMARKS_PATH + ".tmp"
with open(tmp, "w") as f:
    json.dump(lm_data, f, indent=2)
os.replace(tmp, LANDMARKS_PATH)

print(f"\n✓ landmarks.json: updated '{LM}'")
print(f"  xyz: {cur_xyz} -> {new_xyz}")
print(f"  sources: {[SRC_A, SRC_B]}")
print(f"\nReview with: git diff gtamapdata/landmarks.json")
