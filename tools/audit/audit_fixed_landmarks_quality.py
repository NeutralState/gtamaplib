#!/usr/bin/env python3
"""
audit_fixed_landmarks_quality.py — For each FIXED landmark, evaluate the
quality of its triangulation by checking:
  - How well do the SOURCE cams' pixels agree with each other?
  - Is the baseline between sources adequate?
  - Are non-source LEAK cams that see the landmark systematically off?

Findings here represent FOUNDATION bugs that propagate to all downstream
camera calibrations.

Usage:
    python3 tools/audit_fixed_landmarks_quality.py
"""

import os
import sys
import math
import re
from collections import defaultdict

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]
import gtamaplib as ml
import gtamapdata as md

LEAK_CAMS = {n for n,d in md.cameras.items()
             if d.get('source') and re.match(r'\d{4}-\d{2}-\d{2}', d['source'])}
FIXED_LMS = {lm for lm,d in md.landmarks_meta.items()
             if d.get('source_cameras') and md.landmarks.get(lm) is not None
             and all(c in LEAK_CAMS for c in d['source_cameras'])}

print(f"LEAK cams: {sum(1 for c in LEAK_CAMS if c in md.cameras)}")
print(f"FIXED landmarks: {len(FIXED_LMS)}")
print()

results = []  # (lm_name, src_residuals_max, src_baseline_min, n_sources, non_src_max, n_non_src_high)

for lm_name in FIXED_LMS:
    lm_xyz = md.landmarks[lm_name]
    sources = md.landmarks_meta[lm_name].get('source_cameras', [])

    # Compute residuals at SOURCE cams
    src_residuals = []
    src_xyzs = []
    for cn in sources:
        if cn not in md.cameras: continue
        cam = ml.get_camera(cn)
        pixel = md.pixels.get(cn, {}).get(lm_name)
        if pixel is None: continue
        try:
            proj = cam.get_pixel(lm_xyz)
            if proj is None: continue
            dx = (float(proj[0]) - pixel[0]) * cam.hfov / cam.w * 60.0
            dy = (float(proj[1]) - pixel[1]) * cam.vfov / cam.h * 60.0
            err = math.sqrt(dx*dx + dy*dy)
            src_residuals.append(err)
            src_xyzs.append(cam.xyz[:2])
        except: pass

    if len(src_residuals) < 2:
        continue

    src_max = max(src_residuals)

    # Min pairwise baseline
    min_baseline = float('inf')
    for i in range(len(src_xyzs)):
        for j in range(i+1, len(src_xyzs)):
            b = math.hypot(src_xyzs[i][0] - src_xyzs[j][0],
                           src_xyzs[i][1] - src_xyzs[j][1])
            min_baseline = min(min_baseline, b)

    # Non-source LEAK cams that see this landmark
    non_src_residuals = []
    for cn, pxs in md.pixels.items():
        if cn in sources: continue
        if cn not in LEAK_CAMS: continue
        if lm_name not in pxs: continue
        cam = ml.get_camera(cn)
        try:
            proj = cam.get_pixel(lm_xyz)
            if proj is None: continue
            pixel = pxs[lm_name]
            dx = (float(proj[0]) - pixel[0]) * cam.hfov / cam.w * 60.0
            dy = (float(proj[1]) - pixel[1]) * cam.vfov / cam.h * 60.0
            err = math.sqrt(dx*dx + dy*dy)
            non_src_residuals.append(err)
        except: pass

    non_src_max = max(non_src_residuals) if non_src_residuals else 0
    n_non_src_high = sum(1 for e in non_src_residuals if e > 30)

    results.append((lm_name, src_max, min_baseline, len(sources),
                    non_src_max, n_non_src_high))

# ── Bad foundations: source residuals high (sources don't agree) ──────────────

print("─" * 100)
print("CATEGORY 1: SOURCES DON'T AGREE (source max residual > 5')")
print("           These landmarks have a bad triangulation — sources should be sub-arcmin")
print("─" * 100)
print(f"  {'#':>3}  {'lm':<40}  {'src max':>8}  {'baseline':>9}  {'n_src':>5}")
print(f"  {'-'*3}  {'-'*40}  {'-'*8}  {'-'*9}  {'-'*5}")
cat1 = sorted([r for r in results if r[1] > 5], key=lambda r: r[1], reverse=True)
for i, (lm, src_max, baseline, n_src, _, _) in enumerate(cat1[:15]):
    print(f"  {i+1:>3}  {lm[:40]:<40}  {src_max:>6.1f}'  {baseline:>7.0f}m  {n_src:>5}")

# ── Co-located sources: triangulation is unreliable ───────────────────────────

print()
print("─" * 100)
print("CATEGORY 2: CO-LOCATED SOURCES (baseline < 200m)")
print("           No real triangulation possible — xyz is along a single direction")
print("─" * 100)
print(f"  {'#':>3}  {'lm':<40}  {'src max':>8}  {'baseline':>9}  {'n_src':>5}")
print(f"  {'-'*3}  {'-'*40}  {'-'*8}  {'-'*9}  {'-'*5}")
cat2 = sorted([r for r in results if r[2] < 200], key=lambda r: r[2])
for i, (lm, src_max, baseline, n_src, _, _) in enumerate(cat2[:15]):
    print(f"  {i+1:>3}  {lm[:40]:<40}  {src_max:>6.1f}'  {baseline:>7.0f}m  {n_src:>5}")

# ── Disagreement with non-source LEAK observers ───────────────────────────────

print()
print("─" * 100)
print("CATEGORY 3: NON-SOURCE LEAK CAMS DISAGREE (non_src max > 30')")
print("           Foundation OK from sources' perspective but other LEAK cams")
print("           reject the position. Could mean:")
print("           a) Imprecise click in the non-source cam (visibility issue)")
print("           b) Multiple physical objects with same name")
print("           c) Source pixels not pointing at exactly the same physical point")
print("─" * 100)
print(f"  {'#':>3}  {'lm':<40}  {'src max':>8}  {'non_src':>8}  {'n_high':>6}")
print(f"  {'-'*3}  {'-'*40}  {'-'*8}  {'-'*8}  {'-'*6}")
cat3 = sorted([r for r in results if r[5] > 0], key=lambda r: r[4], reverse=True)
for i, (lm, src_max, _, _, non_src_max, n_high) in enumerate(cat3[:15]):
    print(f"  {i+1:>3}  {lm[:40]:<40}  {src_max:>6.1f}'  {non_src_max:>6.1f}'  {n_high:>6}")

print()
print("─" * 100)
print("Recommended action priority:")
print("  CATEGORY 1 first: bad triangulation → re-click pixels or change sources")
print("  CATEGORY 2 next:  unreliable triangulation → find external cam to add")
print("  CATEGORY 3 last:  sometimes unfixable (visibility), often acceptable")
