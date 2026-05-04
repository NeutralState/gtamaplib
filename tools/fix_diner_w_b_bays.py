#!/usr/bin/env python3
"""
fix_diner_w_b_bays.py — Rename Bay (A)-(F) in Diner (W) (B) to unique
4-letter Bay names (AAAA-FFFF), and create the corresponding landmarks
with initial xyz computed by projecting the marked pixel ray to ground
level (z=0).

This resolves a naming collision: the original Bay (A)-(F) names belong
to docks 1800m away seen from Port Gellhorn Postcard (X). The pixels
marked in Diner (W) (B) are on different (closer) docks and need their
own landmark identities.

Run from gtamaplib-main/:
    python3 tools/fix_diner_w_b_bays.py        # dry run
    python3 tools/fix_diner_w_b_bays.py --apply
"""

import argparse
import json
import os
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

CAM_NAME = "Diner (W) (B)"
OLD_NAMES = ["Bay (A)", "Bay (B)", "Bay (C)", "Bay (D)", "Bay (E)", "Bay (F)"]
NEW_NAMES = ["Bay (AAAA)", "Bay (BBBB)", "Bay (CCCC)",
             "Bay (DDDD)", "Bay (EEEE)", "Bay (FFFF)"]

PIXELS_PATH    = os.path.join(GTAMAP_DIR, "gtamapdata", "pixels.json")
LANDMARKS_PATH = os.path.join(GTAMAP_DIR, "gtamapdata", "landmarks.json")

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true',
                    help='Write changes to pixels.json and landmarks.json')
args = parser.parse_args()

# ── Compute initial xyz for new landmarks ─────────────────────────────────────
# For each pixel, cast a ray from the camera, intersect with z=0 plane.
# This gives a sensible starting position; bundle adjust will refine.

cam = ml.get_camera(CAM_NAME)
print(f"Camera: {CAM_NAME}")
print(f"  xyz = {cam.xyz}")
print(f"  ypr = {cam.ypr}")

new_lm_xyz = {}
print(f"\nComputing initial xyz for new landmarks (ray cast to z=0):")
for old_name, new_name in zip(OLD_NAMES, NEW_NAMES):
    if old_name not in md.pixels[CAM_NAME]:
        print(f"  ⚠ {old_name} not in pixels for {CAM_NAME} — skipping")
        continue
    pixel = md.pixels[CAM_NAME][old_name]
    # Project pixel to ground
    point = cam.get_point_at_zero_elevation(pixel)
    if point is None:
        print(f"  ⚠ {old_name}: pixel {pixel} ray doesn't hit z=0 (above horizon?) — skipping")
        continue
    new_lm_xyz[new_name] = [round(float(point[0]), 4),
                            round(float(point[1]), 4),
                            0.0]
    dist = ((point[0]-cam.x)**2 + (point[1]-cam.y)**2) ** 0.5
    print(f"  {old_name:<10} px {pixel} -> {new_name:<13} xyz=({point[0]:.0f}, {point[1]:.0f}, 0)  dist={dist:.0f}m")

if len(new_lm_xyz) == 0:
    print("\nNo landmarks to create. Aborting.")
    sys.exit(0)

# ── Plan the changes ──────────────────────────────────────────────────────────

print(f"\nPlanned changes:")
print(f"  pixels.json:")
for old_name, new_name in zip(OLD_NAMES, NEW_NAMES):
    if new_name in new_lm_xyz:
        print(f"    rename in '{CAM_NAME}': {old_name} -> {new_name}")
print(f"  landmarks.json:")
for new_name, xyz in new_lm_xyz.items():
    print(f"    create {new_name} at {xyz}, source_cameras=['{CAM_NAME}']")

# Sanity check — do new names collide with anything existing?
collisions = [n for n in new_lm_xyz if n in md.landmarks]
if collisions:
    print(f"\n⚠ ERROR: new names collide with existing landmarks: {collisions}")
    print(f"  Aborting to avoid data corruption.")
    sys.exit(1)

# ── Apply ─────────────────────────────────────────────────────────────────────

if not args.apply:
    print(f"\n(dry run — re-run with --apply to write changes)")
    sys.exit(0)

print(f"\nApplying changes...")

# 1. Update pixels.json — rename keys in place
with open(PIXELS_PATH) as f:
    pixels_data = json.load(f)

cam_pxs = pixels_data[CAM_NAME]
for old_name, new_name in zip(OLD_NAMES, NEW_NAMES):
    if old_name in cam_pxs and new_name in new_lm_xyz:
        cam_pxs[new_name] = cam_pxs.pop(old_name)
        print(f"  ✓ pixels.json: renamed {old_name} -> {new_name}")

tmp = PIXELS_PATH + ".tmp"
with open(tmp, "w") as f:
    json.dump(pixels_data, f, indent=2)
os.replace(tmp, PIXELS_PATH)

# 2. Update landmarks.json — append new entries
with open(LANDMARKS_PATH) as f:
    lm_data = json.load(f)

for new_name, xyz in new_lm_xyz.items():
    lm_data[new_name] = {
        "xyz": xyz,
        "source_cameras": [CAM_NAME],
        "error_m": None,
        "zone": "port_gellhorn",  # rough guess based on coordinates
    }
    print(f"  ✓ landmarks.json: created {new_name}")

tmp = LANDMARKS_PATH + ".tmp"
with open(tmp, "w") as f:
    json.dump(lm_data, f, indent=2)
os.replace(tmp, LANDMARKS_PATH)

print(f"\nDone. Review with:")
print(f"  git diff gtamapdata/pixels.json gtamapdata/landmarks.json")
