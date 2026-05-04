#!/usr/bin/env python3
"""
fix_portofino_nw_on_port_ray.py — Move Portofino Tower (NW) xyz onto Port's
ray (the most precise observer per user's visual judgment), at the point
along Port's ray that is closest to Sidewalk (Jason) (E)'s ray.

Result:
  Port residual: 1.38' -> 0.00'    (perfect)
  Sidewalk Jason E:  0.37' -> 0.74'  (slightly degraded, still sub-pixel)
  Movement: 0.5m

Run:
    python3 tools/fix_portofino_nw_on_port_ray.py        # dry run
    python3 tools/fix_portofino_nw_on_port_ray.py --apply
"""

import argparse
import json
import os
import sys
import numpy as np

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

LM = "Portofino Tower (NW)"
PRIMARY = "Port"
SECONDARY = "Sidewalk (Jason) (E)"

LANDMARKS_PATH = os.path.join(GTAMAP_DIR, "gtamapdata", "landmarks.json")

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

if LM not in md.landmarks:
    print(f"ERROR: '{LM}' not in landmarks.json"); sys.exit(1)

cur_xyz = md.landmarks[LM]
print(f"Current xyz: {cur_xyz}")
print(f"Current sources: {md.landmarks_meta[LM].get('source_cameras')}")

# Get rays
cam_p = ml.get_camera(PRIMARY)
cam_s = ml.get_camera(SECONDARY)

dp = np.asarray(cam_p.get_landmark_direction(LM), dtype=float)
dp /= np.linalg.norm(dp)
op = np.asarray(cam_p.xyz, dtype=float)

ds = np.asarray(cam_s.get_landmark_direction(LM), dtype=float)
ds /= np.linalg.norm(ds)
os_ = np.asarray(cam_s.xyz, dtype=float)

# Find t_p along Port's ray closest to Secondary's ray
w = op - os_
a = np.dot(dp, dp)
b = np.dot(dp, ds)
c = np.dot(ds, ds)
d_ = np.dot(dp, w)
e = np.dot(ds, w)
denom = a*c - b*b
if abs(denom) < 1e-9:
    print("ERROR: rays are parallel"); sys.exit(1)

t_p = (b*e - c*d_) / denom
new_xyz_arr = op + t_p * dp
new_xyz = [round(float(v), 4) for v in new_xyz_arr]

import math
move = math.sqrt(sum((a-b)**2 for a,b in zip(new_xyz, cur_xyz)))

print(f"\nProposed xyz (on Port ray): {new_xyz}")
print(f"Movement: {move:.2f}m")

# Residuals at proposed xyz
def residual(cam_name, xyz):
    cam = ml.get_camera(cam_name)
    proj = cam.get_pixel(xyz)
    pixel = md.pixels[cam_name][LM]
    dx = (proj[0] - pixel[0]) * cam.hfov / cam.w * 60
    dy = (proj[1] - pixel[1]) * cam.vfov / cam.h * 60
    return math.sqrt(dx*dx + dy*dy)

print(f"\nResiduals comparison:")
print(f"  {'cam':<28}  {'before':>8}  {'after':>8}")
for cam_name in [PRIMARY, SECONDARY, 'Amphitheater', 'Tennis Court (SE)']:
    if cam_name in md.pixels and LM in md.pixels[cam_name]:
        before = residual(cam_name, cur_xyz)
        after = residual(cam_name, new_xyz)
        flag = ' ← perfect' if after < 0.01 else ''
        print(f"  {cam_name:<28}  {before:>6.2f}'  {after:>6.2f}'{flag}")

if not args.apply:
    print(f"\n(dry run — re-run with --apply to write changes)")
    sys.exit(0)

with open(LANDMARKS_PATH) as f:
    lm_data = json.load(f)
zone = lm_data[LM].get('zone', 'unknown')
lm_data[LM] = {
    "xyz": new_xyz,
    "source_cameras": [PRIMARY, SECONDARY],
    "error_m": None,
    "zone": zone,
}
tmp = LANDMARKS_PATH + ".tmp"
with open(tmp, "w") as f:
    json.dump(lm_data, f, indent=2)
os.replace(tmp, LANDMARKS_PATH)
print(f"\n✓ landmarks.json: updated '{LM}'")
print(f"  xyz: {cur_xyz} → {new_xyz}")
