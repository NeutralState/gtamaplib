#!/usr/bin/env python3
"""
fix_boa_fc_collision.py — Resolve a name collision on
'Bank of America Financial Center'.

Visual investigation showed:
  - Beach + Venetian Islands point at the BoA FC at 401 Lincoln Rd (Miami Beach)
  - Airport (X) points at a different BoA FC at 150 W Flagler St (Downtown Miami)
  - The current landmark xyz fell on Vice Beach but is off — needs retriangulation

Plan:
  1. Rename pixels.json['Airport (X)']['Bank of America Financial Center']
     → 'Bank of America Financial Center (Downtown)'
  2. Create landmarks.json['Bank of America Financial Center (Downtown)']
     using ground projection from Airport (X) pixel (single-cam)
  3. Retriangulate the existing 'Bank of America Financial Center' landmark
     using Beach + Venetian Islands only (multi-cam least-squares)

Run:
    python3 tools/fix_boa_fc_collision.py        # dry run
    python3 tools/fix_boa_fc_collision.py --apply
"""

import argparse
import json
import os
import sys

import numpy as np
from scipy.optimize import minimize

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

PIXELS_PATH    = os.path.join(GTAMAP_DIR, "gtamapdata", "pixels.json")
LANDMARKS_PATH = os.path.join(GTAMAP_DIR, "gtamapdata", "landmarks.json")

OLD_NAME = "Bank of America Financial Center"
NEW_DOWNTOWN_NAME = "Bank of America Financial Center (Downtown)"

AIRPORT_CAM = "Airport (X)"
KEEP_CAMS = ["Beach", "Venetian Islands"]

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

# ── Sanity ────────────────────────────────────────────────────────────────────

if OLD_NAME not in md.landmarks:
    print(f"ERROR: '{OLD_NAME}' not found in landmarks.json")
    sys.exit(1)
if NEW_DOWNTOWN_NAME in md.landmarks:
    print(f"ERROR: '{NEW_DOWNTOWN_NAME}' already exists — aborting to avoid overwrite")
    sys.exit(1)
if AIRPORT_CAM not in md.pixels or OLD_NAME not in md.pixels[AIRPORT_CAM]:
    print(f"ERROR: no pixel for '{OLD_NAME}' in '{AIRPORT_CAM}'")
    sys.exit(1)

# ── Step 1: Compute new xyz for BoA FC (Downtown) from Airport (X) pixel ──────

print(f"Step 1: Compute initial xyz for '{NEW_DOWNTOWN_NAME}' from {AIRPORT_CAM}")
airport_cam = ml.get_camera(AIRPORT_CAM)
airport_pixel = md.pixels[AIRPORT_CAM][OLD_NAME]
print(f"  pixel: {airport_pixel}")

# Project to ground (z=0)
ground_pt = airport_cam.get_point_at_zero_elevation(airport_pixel)
if ground_pt is None:
    print(f"  Pixel above horizon — using ray endpoint at 5000m instead")
    direction = airport_cam.get_landmark_direction(OLD_NAME)
    direction = np.asarray(direction, dtype=float)
    end = np.asarray(airport_cam.xyz) + direction * 5000.0
    downtown_xyz = [round(float(end[0]), 4), round(float(end[1]), 4), 0.0]
else:
    downtown_xyz = [round(float(ground_pt[0]), 4),
                    round(float(ground_pt[1]), 4), 0.0]

import math
dist = math.hypot(downtown_xyz[0] - airport_cam.x,
                  downtown_xyz[1] - airport_cam.y)
print(f"  -> initial xyz: ({downtown_xyz[0]:.0f}, {downtown_xyz[1]:.0f}, 0)  (dist={dist:.0f}m from {AIRPORT_CAM})")

# ── Step 2: Retriangulate Beach version using Beach + Venetian Islands ────────

print(f"\nStep 2: Retriangulate '{OLD_NAME}' from {KEEP_CAMS}")

rays = []
for cam_name in KEEP_CAMS:
    if cam_name not in md.pixels or OLD_NAME not in md.pixels[cam_name]:
        print(f"  ERROR: no pixel for '{OLD_NAME}' in '{cam_name}'")
        sys.exit(1)
    cam = ml.get_camera(cam_name)
    direction = cam.get_landmark_direction(OLD_NAME)
    direction = np.asarray(direction, dtype=float)
    direction = direction / np.linalg.norm(direction)
    origin = np.asarray(cam.xyz, dtype=float)
    rays.append((cam_name, origin, direction))

def loss(p):
    p = np.asarray(p)
    total = 0.0
    for _, o, d in rays:
        v = p - o
        dist_v = np.linalg.norm(v)
        if dist_v < 1e-3:
            continue
        proj = np.dot(v, d) * d
        perp = v - proj
        ang = np.linalg.norm(perp) / dist_v
        total += ang * ang
    return total

p0 = np.asarray(md.landmarks[OLD_NAME], dtype=float)
result = minimize(loss, p0, method='Nelder-Mead',
                  options={'xatol': 1e-3, 'fatol': 1e-12,
                           'maxiter': 10000, 'adaptive': True})
new_beach_xyz = [round(float(result.x[0]), 4),
                 round(float(result.x[1]), 4),
                 round(float(result.x[2]), 4)]
beach_move = np.linalg.norm(result.x - p0)
print(f"  Old xyz: {list(md.landmarks[OLD_NAME])}")
print(f"  New xyz: {new_beach_xyz}  (moved {beach_move:.0f}m)")

# Compute residuals at new position
print(f"  Residuals at new position:")
for cam_name, o, d in rays:
    v = result.x - o
    dist_v = np.linalg.norm(v)
    perp = v - np.dot(v, d) * d
    ang_arcmin = math.degrees(np.linalg.norm(perp) / max(dist_v, 1e-9)) * 60
    print(f"    {cam_name:<28}  {ang_arcmin:>6.1f}'  (dist {dist_v:.0f}m)")

# ── Plan ──────────────────────────────────────────────────────────────────────

print()
print("Planned changes:")
print(f"  pixels.json:")
print(f"    rename in '{AIRPORT_CAM}': '{OLD_NAME}' -> '{NEW_DOWNTOWN_NAME}'")
print(f"  landmarks.json:")
print(f"    create '{NEW_DOWNTOWN_NAME}' at {downtown_xyz}, source=['{AIRPORT_CAM}']")
print(f"    update '{OLD_NAME}' xyz: {list(md.landmarks[OLD_NAME])} -> {new_beach_xyz}")
print(f"    keep   '{OLD_NAME}' source_cameras = {KEEP_CAMS}")

# ── Apply ─────────────────────────────────────────────────────────────────────

if not args.apply:
    print(f"\n(dry run — re-run with --apply to write changes)")
    sys.exit(0)

# 1. pixels.json — rename Airport (X) entry
with open(PIXELS_PATH) as f:
    pixels_data = json.load(f)
pixels_data[AIRPORT_CAM][NEW_DOWNTOWN_NAME] = pixels_data[AIRPORT_CAM].pop(OLD_NAME)
tmp = PIXELS_PATH + ".tmp"
with open(tmp, "w") as f:
    json.dump(pixels_data, f, indent=2)
os.replace(tmp, PIXELS_PATH)
print(f"\n✓ pixels.json: renamed '{AIRPORT_CAM}' '{OLD_NAME}' -> '{NEW_DOWNTOWN_NAME}'")

# 2. landmarks.json — update old, create new
with open(LANDMARKS_PATH) as f:
    lm_data = json.load(f)

# Update existing
old_zone = lm_data[OLD_NAME].get('zone', 'unknown')
lm_data[OLD_NAME] = {
    "xyz": new_beach_xyz,
    "source_cameras": KEEP_CAMS,
    "error_m": None,
    "zone": old_zone,
}
print(f"✓ landmarks.json: updated '{OLD_NAME}' xyz")

# Create new
lm_data[NEW_DOWNTOWN_NAME] = {
    "xyz": downtown_xyz,
    "source_cameras": [AIRPORT_CAM],
    "error_m": None,
    "zone": old_zone,
}
print(f"✓ landmarks.json: created '{NEW_DOWNTOWN_NAME}'")

tmp = LANDMARKS_PATH + ".tmp"
with open(tmp, "w") as f:
    json.dump(lm_data, f, indent=2)
os.replace(tmp, LANDMARKS_PATH)

print(f"\nDone. Review with: git diff gtamapdata/")
