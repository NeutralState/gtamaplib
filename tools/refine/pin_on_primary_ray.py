#!/usr/bin/env python3
"""
pin_on_primary_ray.py — Move a landmark's xyz onto the ray of a chosen
PRIMARY camera (the one with the most reliable pixel mark), at the point
along that ray closest to a SECONDARY ray (for triangulation in depth).

Result: PRIMARY's residual becomes 0', SECONDARY's may change slightly.
This is the right move when ONE cam is clearly the reference (e.g. drone
overhead view, close-up clear visibility) and another cam disagrees due
to imprecise pixel marking but provides the depth constraint.

Usage:
    python3 tools/pin_on_primary_ray.py "4937 E Hwy 98 (Gas Station) (SE)" \\
        --primary "AI World Editor Map (4K)" \\
        --secondary "Gas Station (Jason)"
    
    Add --apply to write the change.

If --secondary is not given, the script picks the closest non-primary source.
"""

import argparse
import json
import math
import os
import sys

import numpy as np

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]
import gtamaplib as ml
import gtamapdata as md

LANDMARKS_PATH = os.path.join(GTAMAP_DIR, "gtamapdata", "landmarks.json")

parser = argparse.ArgumentParser()
parser.add_argument('landmark')
parser.add_argument('--primary', required=True,
                    help='Camera whose ray will be the new "exact" ray (residual -> 0)')
parser.add_argument('--secondary', default=None,
                    help='Camera providing depth constraint (default: closest non-primary source)')
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

LM = args.landmark
PRIMARY = args.primary

if LM not in md.landmarks:
    print(f"ERROR: '{LM}' not in landmarks.json"); sys.exit(1)
if PRIMARY not in md.cameras:
    print(f"ERROR: primary cam '{PRIMARY}' not in cameras.json"); sys.exit(1)
if PRIMARY not in md.pixels or LM not in md.pixels[PRIMARY]:
    print(f"ERROR: '{PRIMARY}' has no pixel for '{LM}'"); sys.exit(1)

cur_xyz = md.landmarks[LM]
sources = md.landmarks_meta[LM].get('source_cameras', [])
print(f"Current xyz: {cur_xyz}")
print(f"Current sources: {sources}")

# Determine secondary
if args.secondary:
    SECONDARY = args.secondary
else:
    candidates = [c for c in sources if c != PRIMARY and c in md.cameras]
    if not candidates:
        # Try any cam with this lm pixel
        candidates = [c for c, p in md.pixels.items()
                      if LM in p and c != PRIMARY and c in md.cameras]
    if not candidates:
        print(f"ERROR: no other cam observes this landmark"); sys.exit(1)
    cam_p = ml.get_camera(PRIMARY)
    candidates.sort(key=lambda c: math.hypot(
        md.cameras[c]['xyz'][0] - cam_p.x,
        md.cameras[c]['xyz'][1] - cam_p.y))
    SECONDARY = candidates[0]
    print(f"Auto-selected secondary: {SECONDARY}")

if SECONDARY not in md.pixels or LM not in md.pixels[SECONDARY]:
    print(f"ERROR: '{SECONDARY}' has no pixel for '{LM}'"); sys.exit(1)

cam_p = ml.get_camera(PRIMARY)
cam_s = ml.get_camera(SECONDARY)

# Rays
dp = np.asarray(cam_p.get_landmark_direction(LM), dtype=float)
dp /= np.linalg.norm(dp)
op = np.asarray(cam_p.xyz, dtype=float)

ds = np.asarray(cam_s.get_landmark_direction(LM), dtype=float)
ds /= np.linalg.norm(ds)
os_ = np.asarray(cam_s.xyz, dtype=float)

# Find t_p along PRIMARY's ray closest to SECONDARY's ray
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
t_s = (a*e - b*d_) / denom

p_primary = op + t_p * dp
p_secondary = os_ + t_s * ds
ray_separation = float(np.linalg.norm(p_primary - p_secondary))

new_xyz = [round(float(v), 4) for v in p_primary]
move = math.sqrt(sum((a-b)**2 for a,b in zip(new_xyz, cur_xyz)))

print(f"\nRays separation at closest approach: {ray_separation:.2f}m")
print(f"Proposed xyz (on {PRIMARY} ray): {new_xyz}")
print(f"Movement from current: {move:.2f}m")

# Sanity: warn if proposed point is behind one of the cameras
for cam, name in [(cam_p, PRIMARY), (cam_s, SECONDARY)]:
    v = np.asarray(new_xyz) - np.asarray(cam.xyz)
    d = ds if name == SECONDARY else dp
    forward = np.dot(v, d)
    if forward < 0:
        print(f"⚠ WARNING: proposed point is BEHIND {name} (forward dist = {forward:.0f}m)")

# Residuals
def residual(cam_name, xyz):
    cam = ml.get_camera(cam_name)
    proj = cam.get_pixel(xyz)
    if proj is None: return float('inf')
    pixel = md.pixels[cam_name][LM]
    dx = (proj[0] - pixel[0]) * cam.hfov / cam.w * 60
    dy = (proj[1] - pixel[1]) * cam.vfov / cam.h * 60
    return math.sqrt(dx*dx + dy*dy)

# Show residuals on all observers
all_observers = [c for c, p in md.pixels.items() if LM in p and c in md.cameras]
print(f"\nResiduals comparison (all {len(all_observers)} observers):")
print(f"  {'cam':<32}  {'before':>8}  {'after':>8}  {'dist':>7}")
print(f"  {'-'*32}  {'-'*8}  {'-'*8}  {'-'*7}")
for cn in all_observers:
    before = residual(cn, cur_xyz)
    after = residual(cn, new_xyz)
    cam = ml.get_camera(cn)
    dist = math.hypot(cam.x - new_xyz[0], cam.y - new_xyz[1])
    flag = ''
    if cn == PRIMARY: flag = ' ← PRIMARY'
    elif cn == SECONDARY: flag = ' ← secondary'
    elif cn in sources: flag = ' (existing src)'
    delta = after - before
    delta_str = f' ({delta:+.1f})'
    print(f"  {cn[:32]:<32}  {before:>6.2f}'  {after:>6.2f}'{delta_str:<10}  {dist:>5.0f}m{flag}")

if not args.apply:
    print(f"\n(dry run — re-run with --apply to write to landmarks.json)")
    sys.exit(0)

with open(LANDMARKS_PATH) as f:
    lm_data = json.load(f)
zone = lm_data[LM].get('zone', 'unknown')
new_sources = sorted({PRIMARY, SECONDARY} | set(s for s in sources if s in (PRIMARY, SECONDARY)))
# Keep original sources structure: PRIMARY + SECONDARY (drop others if they were sources)
new_sources = [PRIMARY, SECONDARY] if PRIMARY != SECONDARY else [PRIMARY]
lm_data[LM] = {
    "xyz": new_xyz,
    "source_cameras": new_sources,
    "error_m": None,
    "zone": zone,
}
tmp = LANDMARKS_PATH + ".tmp"
with open(tmp, "w") as f:
    json.dump(lm_data, f, indent=2)
os.replace(tmp, LANDMARKS_PATH)

print(f"\n✓ landmarks.json: updated '{LM}'")
print(f"  xyz: {cur_xyz} → {new_xyz}")
print(f"  sources: {sources} → {new_sources}")
