#!/usr/bin/env python3
"""
retriangulate_landmark.py — Retriangulate a landmark using ALL cameras that
have marked it (not just 2). Solves for xyz that minimizes the sum of squared
angular distances between each cam's ray and the resulting point.

Use this when find_landmark() (which only takes 2 cams) gives a bad result
because the 2 chosen cams have no baseline (co-located cameras).

Usage:
    python3 tools/retriangulate_landmark.py "Easy Inn Sign"
    python3 tools/retriangulate_landmark.py "Easy Inn Sign" --apply
    python3 tools/retriangulate_landmark.py "Easy Inn Sign" --exclude "Diner (SE) (A)"

The script reports the residual angular error for each cam — if some cams
have huge residuals while others are tiny, those cams probably mark a
DIFFERENT physical object and should be excluded.
"""

import argparse
import json
import os
import sys

import numpy as np
from scipy.optimize import minimize

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

LANDMARKS_PATH = os.path.join(GTAMAP_DIR, "gtamapdata", "landmarks.json")

parser = argparse.ArgumentParser()
parser.add_argument('landmark')
parser.add_argument('--apply', action='store_true')
parser.add_argument('--exclude', action='append', default=[],
                    help='Camera name to exclude (can be repeated)')
args = parser.parse_args()

LM = args.landmark

if LM not in md.landmarks:
    print(f"Landmark '{LM}' not found")
    sys.exit(1)

# ── Find all observing cams ───────────────────────────────────────────────────

observing = []
for cam_name, pxs in md.pixels.items():
    if LM not in pxs:
        continue
    if cam_name in args.exclude:
        continue
    cam_data = md.cameras.get(cam_name)
    if not cam_data or not cam_data.get('xyz'):
        continue
    observing.append((cam_name, pxs[LM]))

if len(observing) < 2:
    print(f"ERROR: only {len(observing)} usable cameras observe {LM} — need at least 2")
    sys.exit(1)

print(f"Retriangulating {LM} from {len(observing)} cameras:")
for cam_name, pixel in observing:
    print(f"  {cam_name:<32}  pixel={pixel}")

# Excluded
excluded_in_pxs = [c for c, _ in [(cn, p) for cn, p in [(cn, md.pixels[cn].get(LM)) for cn in md.pixels if LM in md.pixels[cn]] if p]]
all_observers = set(cn for cn in md.pixels if LM in md.pixels[cn])
excluded = sorted(all_observers - {cn for cn, _ in observing})
if excluded:
    print(f"  Excluded: {excluded}")

# ── Build rays ────────────────────────────────────────────────────────────────

# Each ray = (origin, direction unit vector)
rays = []
for cam_name, _ in observing:
    cam = ml.get_camera(cam_name)
    direction = cam.get_landmark_direction(LM)
    direction = np.asarray(direction, dtype=float)
    direction = direction / np.linalg.norm(direction)
    origin = np.asarray(cam.xyz, dtype=float)
    rays.append((cam_name, origin, direction))

# ── Solve: minimize sum of squared angular errors ─────────────────────────────
# For each ray (o, d), the angular error from a candidate point p is:
#   sin(theta) = |cross(d, (p - o) / |p - o|)|
# We use angle² ≈ sin²(theta) for small angles (= 1 - cos²)
# But for stability we use: residual = (p - o) - dot(p - o, d) * d  (perpendicular component)

def loss(p):
    p = np.asarray(p)
    total = 0.0
    for _, o, d in rays:
        v = p - o
        # Distance from p to the ray
        proj = np.dot(v, d) * d
        perp = v - proj
        # Use angular error (perp / dist) — squared
        dist = np.linalg.norm(v)
        if dist < 1e-3:
            continue
        ang = np.linalg.norm(perp) / dist
        total += ang * ang
    return total

# Initial guess: current xyz
p0 = np.asarray(md.landmarks[LM], dtype=float)
initial_loss = loss(p0)
initial_residuals = []
for cam_name, o, d in rays:
    v = p0 - o
    dist = np.linalg.norm(v)
    perp = v - np.dot(v, d) * d
    ang = np.linalg.norm(perp) / max(dist, 1e-9)
    initial_residuals.append((cam_name, np.degrees(ang) * 60, dist))

print(f"\nInitial xyz: ({p0[0]:.1f}, {p0[1]:.1f}, {p0[2]:.1f})")
print(f"Initial residuals (current state):")
print(f"  {'cam':<32}  {'angle err':>10}  {'distance':>10}")
print(f"  {'-'*32}  {'-'*10}  {'-'*10}")
for cam_name, ang_arcmin, dist in initial_residuals:
    print(f"  {cam_name:<32}  {ang_arcmin:>8.1f}'  {dist:>8.0f}m")

# Solve
result = minimize(loss, p0, method='Nelder-Mead',
                  options={'xatol': 1e-3, 'fatol': 1e-12, 'maxiter': 10000, 'adaptive': True})

p_new = result.x
print(f"\nOptimized xyz: ({p_new[0]:.2f}, {p_new[1]:.2f}, {p_new[2]:.2f})")
move = np.linalg.norm(p_new - p0)
print(f"Movement from initial: {move:.1f}m")

# Final residuals
print(f"\nFinal residuals:")
print(f"  {'cam':<32}  {'angle err':>10}  {'distance':>10}")
print(f"  {'-'*32}  {'-'*10}  {'-'*10}")
final_residuals = []
for cam_name, o, d in rays:
    v = p_new - o
    dist = np.linalg.norm(v)
    perp = v - np.dot(v, d) * d
    ang = np.linalg.norm(perp) / max(dist, 1e-9)
    arcmin = np.degrees(ang) * 60
    final_residuals.append((cam_name, arcmin, dist))
    flag = '  ← outlier' if arcmin > 30 else ''
    print(f"  {cam_name:<32}  {arcmin:>8.1f}'  {dist:>8.0f}m{flag}")

max_residual = max(r[1] for r in final_residuals)
median_residual = sorted(r[1] for r in final_residuals)[len(final_residuals)//2]
print(f"\nMax residual: {max_residual:.1f}'  /  Median: {median_residual:.1f}'")

if max_residual > 60:
    print(f"\n⚠ Some cams disagree strongly. Possible name collision — consider excluding")
    print(f"  outlier cams with --exclude and re-running.")
elif max_residual > 10:
    print(f"\n  Acceptable but not perfect. May indicate slightly off camera calibrations.")
else:
    print(f"\n✓ Excellent convergence — landmark well-defined.")

# ── Apply ─────────────────────────────────────────────────────────────────────

if not args.apply:
    print(f"\n(dry run — re-run with --apply to write to landmarks.json)")
    sys.exit(0)

new_xyz = [round(float(v), 4) for v in p_new]
new_sources = sorted([cn for cn, _ in observing])

with open(LANDMARKS_PATH) as f:
    lm_data = json.load(f)

zone = lm_data[LM].get('zone', 'unknown')
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
print(f"\n✓ landmarks.json: updated {LM}")
print(f"  xyz: {new_xyz}")
print(f"  sources: {new_sources}")
