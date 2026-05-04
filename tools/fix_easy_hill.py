#!/usr/bin/env python3
"""
fix_easy_hill.py — Clean up Easy Hill landmark.

Problem identified by investigate_landmark.py:
  - Diner (SE) (A) and Diner (SE) (B) project to (-6260, 4640) — same point
  - Ambrosia 04 (Fires) projects to (4485, 2515) — 11km away!
  - Current xyz (-5710, 3936) is at 875m from the (A)+(B) cluster — landmark
    is wrongly positioned because it was triangulated from (B) + Ambrosia 04
    when those two had different calibrations.

Plan:
  1. DELETE  pixels.json["Ambrosia 04 (Fires)"]["Easy Hill"]   (caduque obs)
  2. RETRIANGULATE Easy Hill from Diner (SE) (A) + Diner (SE) (B)
  3. UPDATE  landmarks.json["Easy Hill"] with new xyz + sources

Run:
    python3 tools/fix_easy_hill.py        # dry run
    python3 tools/fix_easy_hill.py --apply
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
BAD_CAM = "Ambrosia 04 (Fires)"
SRC_A = "Diner (SE) (A)"
SRC_B = "Diner (SE) (B)"

PIXELS_PATH    = os.path.join(GTAMAP_DIR, "gtamapdata", "pixels.json")
LANDMARKS_PATH = os.path.join(GTAMAP_DIR, "gtamapdata", "landmarks.json")

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

# ── Sanity checks ─────────────────────────────────────────────────────────────

if LM not in md.landmarks:
    print(f"ERROR: landmark '{LM}' not found")
    sys.exit(1)

cur_xyz = md.landmarks[LM]
print(f"Current state of {LM}:")
print(f"  xyz = {cur_xyz}")
print(f"  source_cameras = {md.landmarks_meta[LM].get('source_cameras')}")

if BAD_CAM not in md.pixels or LM not in md.pixels[BAD_CAM]:
    print(f"\n⚠ {BAD_CAM} doesn't have a pixel for {LM} — skipping deletion")
    delete_bad = False
else:
    bad_pixel = md.pixels[BAD_CAM][LM]
    print(f"\nObservation to delete: {BAD_CAM} → {LM} at pixel {bad_pixel}")
    delete_bad = True

# Check both src cams have the lm pixel
for src in (SRC_A, SRC_B):
    if src not in md.pixels or LM not in md.pixels[src]:
        print(f"\nERROR: {src} doesn't have pixel for {LM} — cannot retriangulate")
        sys.exit(1)

# ── Retriangulate ─────────────────────────────────────────────────────────────

print(f"\nRetriangulating {LM} from {SRC_A} + {SRC_B}...")
midpoint, point_a, point_b, distance, angular_delta = ml.find_landmark(SRC_A, SRC_B, LM)

print(f"  Triangulation:")
print(f"    midpoint:    ({midpoint[0]:.1f}, {midpoint[1]:.1f}, {midpoint[2]:.1f})")
print(f"    closest on ray A: ({point_a[0]:.1f}, {point_a[1]:.1f}, {point_a[2]:.1f})")
print(f"    closest on ray B: ({point_b[0]:.1f}, {point_b[1]:.1f}, {point_b[2]:.1f})")
print(f"    ray distance: {distance:.2f}m  (smaller = better, ideally < 1m)")
print(f"    angular delta: {angular_delta:.4f}° ({angular_delta * 60:.2f} arcmin)")

new_xyz = [round(float(midpoint[0]), 4),
           round(float(midpoint[1]), 4),
           round(float(midpoint[2]), 4)]

# Check the new position is sensible
import math
move = math.hypot(new_xyz[0] - cur_xyz[0], new_xyz[1] - cur_xyz[1])
print(f"\n  Movement from current xyz: {move:.0f}m")

if angular_delta > 1.0:  # 1 degree = pretty bad triangulation quality
    print(f"\n  ⚠ Triangulation quality poor (delta {angular_delta:.2f}°) — proceeding cautiously")

# ── Plan ──────────────────────────────────────────────────────────────────────

print()
print("Planned changes:")
print(f"  pixels.json:")
if delete_bad:
    print(f"    DELETE  '{BAD_CAM}' → '{LM}' (pixel {bad_pixel})")
print(f"  landmarks.json:")
print(f"    UPDATE  '{LM}'")
print(f"      xyz: {cur_xyz} → {new_xyz}")
print(f"      source_cameras: {md.landmarks_meta[LM].get('source_cameras')} → ['{SRC_A}', '{SRC_B}']")

# ── Apply ─────────────────────────────────────────────────────────────────────

if not args.apply:
    print(f"\n(dry run — re-run with --apply to write changes)")
    sys.exit(0)

print(f"\nApplying...")

# 1. pixels.json — delete bad obs
if delete_bad:
    with open(PIXELS_PATH) as f:
        pixels_data = json.load(f)
    if LM in pixels_data.get(BAD_CAM, {}):
        del pixels_data[BAD_CAM][LM]
        tmp = PIXELS_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(pixels_data, f, indent=2)
        os.replace(tmp, PIXELS_PATH)
        print(f"  ✓ pixels.json: deleted {BAD_CAM} → {LM}")

# 2. landmarks.json — update Easy Hill
with open(LANDMARKS_PATH) as f:
    lm_data = json.load(f)

zone = lm_data[LM].get('zone', 'unknown')
lm_data[LM] = {
    "xyz": new_xyz,
    "source_cameras": [SRC_A, SRC_B],
    "error_m": round(float(distance), 4),
    "zone": zone,
}
tmp = LANDMARKS_PATH + ".tmp"
with open(tmp, "w") as f:
    json.dump(lm_data, f, indent=2)
os.replace(tmp, LANDMARKS_PATH)
print(f"  ✓ landmarks.json: updated {LM}")

print()
print(f"Done. Review with:")
print(f"  git diff gtamapdata/")
