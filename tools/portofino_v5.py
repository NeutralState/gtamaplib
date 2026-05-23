#!/usr/bin/env python3
"""
Portofino V5 refactor - adds:
1. Pyramidal apex on each of 3 peak boxes (turret roofs)
2. Atrium ring visible at CT level (already present, just emphasized)
3. Tiered balcony profile on each branch (3 steps of progressive setback)

Modifies landmarks.json (adds new LMs) and tools/densify_portofino_edges.py
to include the new edges. Run densify after to update calib.html.
"""

import os
import sys
import json
import math
import shutil
import re

REPO = os.path.expanduser('~/Downloads/gtamaplib-main')
sys.path.insert(0, REPO)
import numpy as np
import gtamapdata as md

# ── Source of truth ──
NW = np.array(md.landmarks['Portofino Tower (NW)'], dtype=float)
NE = np.array(md.landmarks['Portofino Tower (NE)'], dtype=float)
S  = np.array(md.landmarks['Portofino Tower (S)'],  dtype=float)
centroid_xy = (NW[:2] + NE[:2] + S[:2]) / 3
BRANCH_PEAKS = {'NW': NW, 'NE': NE, 'S': S}

# Z levels (matching existing landmarks.json structure: B/L/K/M/P)
Z_LEVELS = {
    'B': -15.0,   # ground
    'L': 14.0,    # podium top
    'K': 83.0,    # tower base (top of long body)
    'M': 91.0,    # break-top
    'P': 125.0,   # pent top (base of peak boxes)
}
Z_CT = 137.0   # cylinder top
Z_PB = 125.0   # peak box base
Z_PT = 138.77  # peak box top (flat)
Z_TURRET_APEX = 152.0  # NEW: pyramidal apex above PT (estimated from photos)

# Geometry constants
SIDE_FRONT_BASE = 11.2
R_CYLINDER_BASE = 8.87
PEAK_BOX_SIDE = 8.5

# Tiered balcony setback: 3 progressive tiers on each branch
# Each tier sits between two Z levels and protrudes more outward than the wall plane
# Photo analysis: balconies project ~1-2m beyond the main facade
BALCONY_TIERS = [
    # (tier_name, z, scale_multiplier_relative_to_pentagon_at_that_z)
    # Scale > 1.0 means balcony projects OUTWARD beyond the pentagon wall
    ('T1', 35.0, 1.08),   # tier 1, between L (14) and K (83)
    ('T2', 60.0, 1.06),   # tier 2, mid-tower
    ('T3', 105.0, 1.04),  # tier 3, between M (91) and P (125)
]

# ─── HELPERS ─────────────────────────────────────────────────────────────
def pentagon_corners(peak_xyz, z, scale=1.0):
    """Compute the 4 corners of a pentagonal wing slice at given Z."""
    peak_xy = peak_xyz[:2]
    radial = peak_xy - centroid_xy
    radial_len = np.linalg.norm(radial)
    radial_unit = radial / radial_len
    perp = np.array([-radial_unit[1], radial_unit[0]])
    radial_outward = (scale - 1.0) * radial_len * 0.3
    side_front = SIDE_FRONT_BASE * scale
    inner_radius = R_CYLINDER_BASE * scale
    inner_half = side_front * 0.75
    peak_pos_xy = centroid_xy + radial_unit * (radial_len + radial_outward)
    front_half = side_front / 2
    front_L = peak_pos_xy + perp * front_half
    front_R = peak_pos_xy - perp * front_half
    inner_pos = centroid_xy + radial_unit * inner_radius
    inner_L = inner_pos + perp * inner_half
    inner_R = inner_pos - perp * inner_half
    return {
        'frontL': (float(front_L[0]), float(front_L[1]), z),
        'frontR': (float(front_R[0]), float(front_R[1]), z),
        'innerL': (float(inner_L[0]), float(inner_L[1]), z),
        'innerR': (float(inner_R[0]), float(inner_R[1]), z),
    }

def turret_apex(peak_xyz):
    """Pyramidal apex point at peak_xy, projected upward to Z_TURRET_APEX."""
    peak_xy = peak_xyz[:2]
    return (float(peak_xy[0]), float(peak_xy[1]), Z_TURRET_APEX)

# ─── GENERATE NEW LMs ────────────────────────────────────────────────────
new_lms = {}

# 1. Pyramidal apex for each branch (3 new LMs)
for br_name, peak in BRANCH_PEAKS.items():
    apex = turret_apex(peak)
    new_lms[f'Portofino Tower (apex-{br_name})'] = list(apex)

# 2. Tiered balconies: 4 corners × 3 tiers × 3 branches = 36 new LMs
for tier_name, z, scale in BALCONY_TIERS:
    for br_name, peak in BRANCH_PEAKS.items():
        corners = pentagon_corners(peak, z, scale)
        for c_name, xyz in corners.items():
            new_lms[f'Portofino Tower (balc{tier_name}-{c_name}-{br_name})'] = list(xyz)

# Round to 4 decimal places
for n in list(new_lms):
    new_lms[n] = [round(float(v), 4) for v in new_lms[n]]

print(f'Generated {len(new_lms)} new LMs:')
print(f'  - 3 turret apexes')
print(f'  - 36 balcony corners ({len(BALCONY_TIERS)} tiers × 3 branches × 4 corners)')

# ─── WRITE TO landmarks.json ─────────────────────────────────────────────
LANDMARKS = os.path.join(REPO, 'gtamapdata', 'landmarks.json')
BACKUP_LM = LANDMARKS + '.bak_portofino_v5'
shutil.copy(LANDMARKS, BACKUP_LM)
print(f'\nBackup: {BACKUP_LM}')

with open(LANDMARKS) as f:
    lms = json.load(f)

# Delete any existing v5 LMs first (so re-running is idempotent)
to_del = [n for n in list(lms) if 'Portofino Tower (apex-' in n or 'Portofino Tower (balc' in n]
for n in to_del:
    del lms[n]
if to_del:
    print(f'Removed {len(to_del)} existing v5 LMs (re-running)')

for n, xyz in new_lms.items():
    lms[n] = {'xyz': xyz, 'source_cameras': [], 'error_m': 0.0, 'zone': 'vice_city'}

with open(LANDMARKS + '.tmp', 'w') as f:
    json.dump(lms, f, indent=2)
os.replace(LANDMARKS + '.tmp', LANDMARKS)
print(f'Added {len(new_lms)} new LMs to landmarks.json')

# ─── UPDATE densify_portofino_edges.py TO INCLUDE NEW EDGES ──────────────
DENSIFY = os.path.join(REPO, 'tools', 'densify_portofino_edges.py')
BACKUP_D = DENSIFY + '.bak_portofino_v5'
shutil.copy(DENSIFY, BACKUP_D)
print(f'Backup: {BACKUP_D}')

with open(DENSIFY) as f:
    d = f.read()

# Anchor: end of edge generation, before writing
anchor = "print(f'\\nGenerated {len(edges)} edges')"

new_edges_code = '''# ─── V5 ADDITIONS ──────────────────────────────────────────────────
# 9) Pyramidal apex edges: 4 corners of peak box top (PT) up to apex
apex_lms = {br: f'Portofino Tower (apex-{br})' for br in ['NW', 'NE', 'S']}
pbox_corners_pyr = ['pbOL', 'pbOR', 'pbIR', 'pbIL']
for branch in ['NW', 'NE', 'S']:
    apex = apex_lms[branch]
    if apex in md.landmarks:
        for corner in pbox_corners_pyr:
            pt_corner = pbox_lms.get(('PT', corner, branch))
            if pt_corner:
                edges.append([pt_corner, apex])

# 10) Tiered balcony edges
# Each tier has: vertical edges from main pent levels to balcony level,
# horizontal edges on the balcony itself (4-corner quad),
# and tier-to-tier edges connecting balconies vertically
balc_tiers = ['T1', 'T2', 'T3']
balc_corners = ['frontL', 'frontR', 'innerR', 'innerL']

# Horizontal edges at each balcony tier (4-corner quad)
for branch in ['NW', 'NE', 'S']:
    for tier in balc_tiers:
        for i in range(4):
            c1 = balc_corners[i]
            c2 = balc_corners[(i + 1) % 4]
            a = f'Portofino Tower (balc{tier}-{c1}-{branch})'
            b = f'Portofino Tower (balc{tier}-{c2}-{branch})'
            if a in md.landmarks and b in md.landmarks:
                edges.append([a, b])

# Vertical edges connecting adjacent balcony tiers (T1→T2→T3) for each corner
for branch in ['NW', 'NE', 'S']:
    for corner in balc_corners:
        for i in range(len(balc_tiers) - 1):
            t1, t2 = balc_tiers[i], balc_tiers[i + 1]
            a = f'Portofino Tower (balc{t1}-{corner}-{branch})'
            b = f'Portofino Tower (balc{t2}-{corner}-{branch})'
            if a in md.landmarks and b in md.landmarks:
                edges.append([a, b])

# Connect balcony T1 to pentagon L (top of podium), T3 to pentagon M (mid-break)
for branch in ['NW', 'NE', 'S']:
    for corner in balc_corners:
        # T1 corner → L corner (near podium top)
        a = f'Portofino Tower (balcT1-{corner}-{branch})'
        b = pent_lms.get(('L', corner, branch))
        if a in md.landmarks and b:
            edges.append([a, b])
        # T3 corner → P corner (top of pent)
        a = f'Portofino Tower (balcT3-{corner}-{branch})'
        b = pent_lms.get(('P', corner, branch))
        if a in md.landmarks and b:
            edges.append([a, b])

'''

if anchor in d:
    d = d.replace(anchor, new_edges_code + anchor, 1)
    print('Patched densify script with V5 apex + balcony edges')

with open(DENSIFY, 'w') as f:
    f.write(d)

print('\nDone. Now run:')
print('  python3 tools/densify_portofino_edges.py')
print('Then restart server + hard refresh browser.')
