#!/usr/bin/env python3
"""
audit_leak_consistency.py — Audit observations between LEAK cameras and
FIXED landmarks (those triangulated only from LEAK cams). These observations
form the GROUND TRUTH of the system — they should be sub-arcmin accurate.
Any large error here means the foundation is broken, and everything built
on top will inherit that error.

This is the AUDIT we should have run before anything else. If there are
significant LEAK ↔ LEAK errors, no amount of bundle adjustment or refining
of optimizable cams will fix them.

Run from gtamaplib-main/:
    python3 tools/audit_leak_consistency.py
"""

import os
import sys
import math
from collections import defaultdict

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

# ── Identify LEAK cams (same set as bundle_adjust) ─────────────────────────

LEAK_CAMS = {
    'Tennis Stadium (4K)', 'Vice Beach (A)', 'Vice Beach (B)',
    'Metro (SE) (A) (4K)', 'Alley (W)', 'Park', 'Port',
    'Tennis Court (SE)', 'Tennis Court (NE)', 'Tennis Court (N)', 'Tennis Court (SW)',
    'AI World Editor Map (4K)',
    'Diner (W) (A)', 'Diner (W) (B)', 'Diner (N)', 'Diner (NW)', 'Diner (NE)',
    'Diner (E)', 'Diner (SE) (A)', 'Diner (SE) (B)', 'Diner (S)', 'Diner (SW)', 'Diner',
    'Gas Station (Lucia)', 'Gas Station (Jason)',
    'Loading Zone near Prison (SW)', 'Loading Zone near Prison (N)',
    'Ocean near Keys (N)', 'Ocean near Keys (E)', 'House with Boat (X)',
    'Highway (NE)', 'Sidewalk (Jason) (E)', 'Sidewalk (Jason) (S)',
    'Welcome Center (E)', 'Welcome Center (W)', 'Police Chase (A)', 'Police Chase (D)',
    'Airport (X)', 'Car Wash', 'Glitch (A)', 'Grassrivers Postcard (X)',
    'Handlebar (SE)', 'Handlebar (SW)', 'Hedge (B) (X)', 'Hotel (W)',
    'Intersection (W)', 'Penthouse (NE)', 'Penthouse (NW)',
    'Penthouse (SE)', 'Penthouse (SW)', 'Pool', 'Rooftop (SE)',
}

# FIXED landmarks: those whose source_cameras are all LEAK
fixed_lms = set()
for lm_name, meta in md.landmarks_meta.items():
    if md.landmarks.get(lm_name) is None:
        continue
    sources = meta.get('source_cameras', [])
    if sources and all(s in LEAK_CAMS for s in sources):
        fixed_lms.add(lm_name)

print(f"LEAK cameras: {sum(1 for c in LEAK_CAMS if c in md.cameras)}")
print(f"FIXED landmarks (triangulated only from LEAK): {len(fixed_lms)}")
print()

# ── Compute residuals for LEAK cam → FIXED landmark observations ──────────────

obs_results = []  # (cam, lm, err_arcmin, dist, classification)

for cam_name, pxs in md.pixels.items():
    if cam_name not in LEAK_CAMS:
        continue
    cam_data = md.cameras.get(cam_name, {})
    if not cam_data.get('xyz'):
        continue
    cam = ml.get_camera(cam_name)

    for lm_name, pixel in pxs.items():
        lm_xyz = md.landmarks.get(lm_name)
        if lm_xyz is None:
            continue
        if lm_name not in fixed_lms:
            continue

        try:
            proj = cam.get_pixel(lm_xyz)
            if proj is None:
                obs_results.append((cam_name, lm_name, float('inf'), 0, 'no_proj'))
                continue
            dx = (float(proj[0]) - float(pixel[0])) * cam.hfov / cam.w * 60.0
            dy = (float(proj[1]) - float(pixel[1])) * cam.vfov / cam.h * 60.0
            err = (dx*dx + dy*dy) ** 0.5

            # Distance from cam to landmark
            d = math.sqrt(sum((a-b)**2 for a,b in zip(cam.xyz, lm_xyz)))

            # Classify: is this LEAK <-> LEAK (cam in lm sources) or LEAK -> FIXED?
            sources = md.landmarks_meta[lm_name].get('source_cameras', [])
            if cam_name in sources:
                cls = 'self-source'
            else:
                cls = 'leak->fixed'
            obs_results.append((cam_name, lm_name, err, d, cls))
        except Exception as e:
            obs_results.append((cam_name, lm_name, float('inf'), 0, 'error'))

print(f"Total LEAK→FIXED observations: {len(obs_results)}")

# ── Distribution stats ────────────────────────────────────────────────────────

valid_errors = [r[2] for r in obs_results if r[2] != float('inf')]
valid_errors.sort()
n = len(valid_errors)

if n == 0:
    print("No valid observations. Aborting.")
    sys.exit(0)

p50 = valid_errors[n//2]
p90 = valid_errors[int(n*0.9)]
p99 = valid_errors[int(n*0.99)] if n >= 100 else valid_errors[-1]
mx  = valid_errors[-1]

print()
print(f"Distribution of LEAK→FIXED errors:")
print(f"  p50 = {p50:6.2f}'    p90 = {p90:6.2f}'    p99 = {p99:6.2f}'    max = {mx:6.2f}'")
print(f"  obs >  10' : {sum(1 for e in valid_errors if e > 10):>4}  ({sum(1 for e in valid_errors if e > 10)/n*100:.0f}%)")
print(f"  obs >  50' : {sum(1 for e in valid_errors if e > 50):>4}  ({sum(1 for e in valid_errors if e > 50)/n*100:.0f}%)")
print(f"  obs > 100' : {sum(1 for e in valid_errors if e > 100):>4}  ({sum(1 for e in valid_errors if e > 100)/n*100:.0f}%)")
print()
print(f"In a properly calibrated system these obs should ALL be sub-5'.")
print(f"Anything above ~5' indicates a foundational bug to fix BEFORE the")
print(f"bundle adjustment can converge cleanly.")

# ── Top offenders ─────────────────────────────────────────────────────────────

print()
print("─" * 100)
print("TOP 30 worst LEAK→FIXED observations (these break the foundation):")
print("─" * 100)
print(f"  {'#':>3}  {'error':>8}  {'cls':<11}  {'cam':<32}  {'landmark':<32}  {'dist':>6}")
print(f"  {'-'*3}  {'-'*8}  {'-'*11}  {'-'*32}  {'-'*32}  {'-'*6}")

obs_results_sorted = sorted([r for r in obs_results if r[2] != float('inf')],
                             key=lambda r: r[2], reverse=True)
for i, (cam, lm, err, d, cls) in enumerate(obs_results_sorted[:30]):
    flag = ' ⚠⚠⚠' if cls == 'self-source' else ''
    print(f"  {i+1:>3}  {err:>6.1f}'   {cls:<11}  {cam[:32]:<32}  {lm[:32]:<32}  {d:>5.0f}m{flag}")

# ── Group by camera (which LEAK cams are most affected) ──────────────────────

print()
print("─" * 100)
print("Per-LEAK-camera error summary:")
print("─" * 100)

cam_summary = defaultdict(lambda: {'n':0, 'errs': []})
for cam, lm, err, _, _ in obs_results:
    if err == float('inf'):
        continue
    cam_summary[cam]['n'] += 1
    cam_summary[cam]['errs'].append(err)

ranked_cams = []
for cam, s in cam_summary.items():
    errs = sorted(s['errs'])
    n_obs = len(errs)
    n_bad = sum(1 for e in errs if e > 10)
    rate_bad = n_bad / n_obs * 100 if n_obs else 0
    median = errs[n_obs//2] if n_obs else 0
    mx = errs[-1] if errs else 0
    ranked_cams.append((cam, n_obs, n_bad, rate_bad, median, mx))

ranked_cams.sort(key=lambda x: x[3], reverse=True)

print(f"  {'cam':<32}  {'obs':>4}  {'>10''':>4}  {'rate':>5}  {'median':>7}  {'max':>7}")
print(f"  {'-'*32}  {'-'*4}  {'-'*4}  {'-'*5}  {'-'*7}  {'-'*7}")
for cam, n_obs, n_bad, rate, median, mx in ranked_cams[:20]:
    flag = '  ⚠' if rate > 30 else ''
    print(f"  {cam[:32]:<32}  {n_obs:>4}  {n_bad:>4}  {rate:>4.0f}%  {median:>6.1f}'  {mx:>6.0f}'{flag}")

# ── Group by landmark ────────────────────────────────────────────────────────

print()
print("─" * 100)
print("Per-FIXED-landmark error summary (top 20 worst):")
print("─" * 100)

lm_summary = defaultdict(lambda: {'n':0, 'errs': []})
for cam, lm, err, _, _ in obs_results:
    if err == float('inf'):
        continue
    lm_summary[lm]['n'] += 1
    lm_summary[lm]['errs'].append(err)

ranked_lms = []
for lm, s in lm_summary.items():
    errs = sorted(s['errs'])
    n_obs = len(errs)
    if n_obs < 1:
        continue
    median = errs[n_obs//2]
    mx = errs[-1]
    if mx > 5:  # only show problematic ones
        ranked_lms.append((lm, n_obs, median, mx))

ranked_lms.sort(key=lambda x: x[3], reverse=True)

print(f"  {'landmark':<40}  {'obs':>4}  {'median':>7}  {'max':>7}")
print(f"  {'-'*40}  {'-'*4}  {'-'*7}  {'-'*7}")
for lm, n_obs, median, mx in ranked_lms[:20]:
    print(f"  {lm[:40]:<40}  {n_obs:>4}  {median:>6.1f}'  {mx:>6.0f}'")

print()
print("Suggested workflow:")
print("  1. Pick the TOP landmark in this list (worst max error)")
print("  2. Run trace_ray_on_map.py to see if it's a name collision or pixel error")
print("  3. Fix the foundation issue")
print("  4. Repeat until LEAK→FIXED median is sub-5'")
print("  5. THEN bundle adjustment will converge cleanly")
