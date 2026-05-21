#!/usr/bin/env python3
"""
densify_portofino_edges.py

Generate a complete, dense PORTOFINO_EDGES JavaScript array from the 135
calibrated Portofino LMs in landmarks.json. Outputs a JS literal that
replaces the existing PORTOFINO_EDGES const in tools/calib.html.

Structure based on actual LMs found:
- Pentagons: B, K, L, M, P levels × 3 branches (NW/NE/S) × 4 corners
- Cylinder: B, K, L, M, P, CT levels × 8 segments (cyl0-cyl7) — total 48 = 6 levels
- Peak boxes: PB, PT levels × 3 branches × 4 corners (pbOL/pbOR/pbIL/pbIR)
"""

import os
import re
import json
import sys
from collections import defaultdict

REPO = os.path.expanduser('~/Downloads/gtamaplib-main')
sys.path.insert(0, REPO)
import gtamapdata as md

# ─── Discover actual structure ────────────────────────────────────────────
pent_levels = set()
pent_branches = set()
pent_corners = set()
pent_lms = {}
cyl_levels = set()
cyl_segs = set()
cyl_lms = {}
pbox_levels = set()
pbox_branches = set()
pbox_corners = set()
pbox_lms = {}

for n in md.landmarks:
    if 'Portofino' not in n:
        continue
    m = re.match(r'Portofino Tower \(([^)]+)\)$', n)
    if not m:
        continue
    inner = m.group(1)
    parts = inner.split('-')

    if len(parts) == 1:
        # Anchors NW/NE/S — skip, they're just refs
        continue

    if parts[0] == 'cyl':
        # cyl-{level}-{seg}
        if len(parts) == 3:
            _, level, seg = parts
            cyl_levels.add(level)
            cyl_segs.add(seg)
            cyl_lms[(level, seg)] = n

    elif parts[0] in ('PB', 'PT'):
        # PB-{corner}-{branch} or PT-{corner}-{branch}
        if len(parts) == 3:
            level, corner, branch = parts
            pbox_levels.add(level)
            pbox_corners.add(corner)
            pbox_branches.add(branch)
            pbox_lms[(level, corner, branch)] = n

    else:
        # {level}-{corner}-{branch} — pentagons
        if len(parts) == 3:
            level, corner, branch = parts
            pent_levels.add(level)
            pent_corners.add(corner)
            pent_branches.add(branch)
            pent_lms[(level, corner, branch)] = n

# Order levels by Z position
def z_of(lm_name):
    return md.landmarks.get(lm_name, [0, 0, 0])[2]

pent_levels_ord = sorted(pent_levels, key=lambda lvl: z_of(pent_lms.get((lvl, 'frontL', 'NW'), '_')))
cyl_levels_ord  = sorted(cyl_levels,  key=lambda lvl: z_of(cyl_lms.get((lvl, 'cyl0'), '_')))
pbox_levels_ord = sorted(pbox_levels, key=lambda lvl: z_of(pbox_lms.get((lvl, 'pbOL', 'NW'), '_')))

print('Structure discovered:')
print(f'  Pentagons: levels {pent_levels_ord} (Z-ordered)')
print(f'             branches {sorted(pent_branches)}, corners {sorted(pent_corners)}')
print(f'  Cylinder:  levels {cyl_levels_ord}, segs {sorted(cyl_segs)}')
print(f'  Peak box:  levels {pbox_levels_ord}, branches {sorted(pbox_branches)}, corners {sorted(pbox_corners)}')

# Show Z elevations
print('\nZ elevations:')
print('  Pentagon levels:')
for lvl in pent_levels_ord:
    z = z_of(pent_lms.get((lvl, 'frontL', 'NW'), '_'))
    print(f'    {lvl}: z={z}')
print('  Cylinder levels:')
for lvl in cyl_levels_ord:
    z = z_of(cyl_lms.get((lvl, 'cyl0'), '_'))
    print(f'    {lvl}: z={z}')
print('  Peak box levels:')
for lvl in pbox_levels_ord:
    z = z_of(pbox_lms.get((lvl, 'pbOL', 'NW'), '_'))
    print(f'    {lvl}: z={z}')

# ─── Build EDGES ──────────────────────────────────────────────────────────
edges = []

# 1) Pentagon vertical edges (each corner through each pair of consecutive levels)
pent_corners_ord = ['frontL', 'frontR', 'innerR', 'innerL']
for branch in sorted(pent_branches):
    for corner in pent_corners_ord:
        for i in range(len(pent_levels_ord) - 1):
            l1, l2 = pent_levels_ord[i], pent_levels_ord[i + 1]
            a = pent_lms.get((l1, corner, branch))
            b = pent_lms.get((l2, corner, branch))
            if a and b:
                edges.append([a, b])

# 2) Pentagon horizontal edges (quad at each level: frontL-frontR-innerR-innerL-frontL)
for branch in sorted(pent_branches):
    for level in pent_levels_ord:
        for i in range(4):
            c1 = pent_corners_ord[i]
            c2 = pent_corners_ord[(i + 1) % 4]
            a = pent_lms.get((level, c1, branch))
            b = pent_lms.get((level, c2, branch))
            if a and b:
                edges.append([a, b])

# 3) Cylinder vertical edges (each seg through consecutive levels)
cyl_segs_ord = sorted(cyl_segs, key=lambda s: int(s.replace('cyl', '')))
for seg in cyl_segs_ord:
    for i in range(len(cyl_levels_ord) - 1):
        l1, l2 = cyl_levels_ord[i], cyl_levels_ord[i + 1]
        a = cyl_lms.get((l1, seg))
        b = cyl_lms.get((l2, seg))
        if a and b:
            edges.append([a, b])

# 4) Cylinder horizontal rings (cyl0-cyl1-...-cyl7-cyl0 at each level)
for level in cyl_levels_ord:
    for i in range(len(cyl_segs_ord)):
        s1 = cyl_segs_ord[i]
        s2 = cyl_segs_ord[(i + 1) % len(cyl_segs_ord)]
        a = cyl_lms.get((level, s1))
        b = cyl_lms.get((level, s2))
        if a and b:
            edges.append([a, b])

# 5) Peak box vertical edges (each corner PB→PT)
pbox_corners_ord = ['pbOL', 'pbOR', 'pbIR', 'pbIL']
for branch in sorted(pbox_branches):
    for corner in pbox_corners_ord:
        for i in range(len(pbox_levels_ord) - 1):
            l1, l2 = pbox_levels_ord[i], pbox_levels_ord[i + 1]
            a = pbox_lms.get((l1, corner, branch))
            b = pbox_lms.get((l2, corner, branch))
            if a and b:
                edges.append([a, b])

# 6) Peak box horizontal edges at each level (square: pbOL-pbOR-pbIR-pbIL-pbOL)
for branch in sorted(pbox_branches):
    for level in pbox_levels_ord:
        for i in range(4):
            c1 = pbox_corners_ord[i]
            c2 = pbox_corners_ord[(i + 1) % 4]
            a = pbox_lms.get((level, c1, branch))
            b = pbox_lms.get((level, c2, branch))
            if a and b:
                edges.append([a, b])

# 7) BREAK EMPHASIS: Adjacent levels K (z=83) and M (z=91) bracket the break.
# Z order is B(-15) → L(14) → K(83) → M(91) → P(125), so break = K-M transition.
# Skip the broken diagonals — the vertical K→M already shows the break.
# Instead, double-trace horizontal rings at K and M for visual emphasis (already
# in the horizontal pass) — nothing to add here.

# 8) Connect Pentagon P (top of pent) to Peak Box PB (base of peak box) for each branch
# This shows the transition from pentagonal wing → square peak box
for branch in sorted(pent_branches):
    # frontL-P → pbOL-PB; frontR-P → pbOR-PB; innerL-P → pbIL-PB; innerR-P → pbIR-PB
    pairs = [('frontL', 'pbOL'), ('frontR', 'pbOR'), ('innerL', 'pbIL'), ('innerR', 'pbIR')]
    for pc, pbc in pairs:
        a = pent_lms.get(('P', pc, branch))
        b = pbox_lms.get(('PB', pbc, branch))
        if a and b:
            edges.append([a, b])

print(f'\nGenerated {len(edges)} edges')

# ─── Write to calib.html ──────────────────────────────────────────────────
CALIB = os.path.join(REPO, 'tools', 'calib.html')
BACKUP = CALIB + '.bak_portofino_densify'
import shutil
shutil.copy(CALIB, BACKUP)
print(f'Backup: {BACKUP}')

with open(CALIB) as f:
    c = f.read()

# Find PORTOFINO_EDGES = [ ... ];
match = re.search(r'const PORTOFINO_EDGES = \[.*?\];', c, re.DOTALL)
if not match:
    print('ERROR: PORTOFINO_EDGES not found in calib.html')
    sys.exit(1)

# Generate new JS literal
lines = ['const PORTOFINO_EDGES = [']
for a, b in edges:
    lines.append(f"  ['{a}', '{b}'],")
lines.append('];')
new_const = '\n'.join(lines)

c_new = c[:match.start()] + new_const + c[match.end():]

with open(CALIB, 'w') as f:
    f.write(c_new)

print(f'Updated PORTOFINO_EDGES: {len(edges)} edges (was ~135)')
print('Hard refresh browser to see denser wireframe.')
