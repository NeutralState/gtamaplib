#!/usr/bin/env python3
"""Portofino V4: corrected z levels and architecture."""
import sys, json, os
sys.path.insert(0, '.')
import numpy as np
import gtamapdata as md

NW = np.array(md.landmarks['Portofino Tower (NW)'])
NE = np.array(md.landmarks['Portofino Tower (NE)'])
S  = np.array(md.landmarks['Portofino Tower (S)'])
centroid_xy = (NW[:2] + NE[:2] + S[:2]) / 3

# Z levels (architecture verticale corrigée)
Z_PEAK_TOP    = 143.0   # top peak boxes (anchored)
Z_CYL_TOP     = 137.0   # top cylindre (2 étages sous)
Z_PENT_TOP    = 125.0   # top pentagones = base peak boxes (7 étages sous le top)
Z_BREAK_TOP   = 85.0    # base pentagones / top break
Z_BASE_TOP    = 75.0    # top base élargie
Z_GROUND      = 0.0

# Pentagon dimensions
SIDE_FRONT_BASE = 11.2
R_CYLINDER_BASE = 8.87
PEAK_BOX_SIDE = 8.5

def pentagon(peak_xyz, z, scale=1.0):
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
        'frontL': (front_L[0], front_L[1], z),
        'frontR': (front_R[0], front_R[1], z),
        'innerL': (inner_L[0], inner_L[1], z),
        'innerR': (inner_R[0], inner_R[1], z),
    }

def peak_box(peak_xyz, z):
    peak_xy = peak_xyz[:2]
    radial = peak_xy - centroid_xy
    radial_unit = radial / np.linalg.norm(radial)
    perp = np.array([-radial_unit[1], radial_unit[0]])
    half = PEAK_BOX_SIDE / 2
    outer = peak_xy + radial_unit * half
    inner = peak_xy - radial_unit * half
    return {
        'pbOL': (outer[0] + perp[0]*half, outer[1] + perp[1]*half, z),
        'pbOR': (outer[0] - perp[0]*half, outer[1] - perp[1]*half, z),
        'pbIL': (inner[0] + perp[0]*half, inner[1] + perp[1]*half, z),
        'pbIR': (inner[0] - perp[0]*half, inner[1] - perp[1]*half, z),
    }

def cylinder(z, scale=1.0):
    R = R_CYLINDER_BASE * scale
    pts = {}
    for i in range(8):
        a = i * np.pi / 4
        x = centroid_xy[0] + R * np.cos(a)
        y = centroid_xy[1] + R * np.sin(a)
        pts[f'cyl{i}'] = (x, y, z)
    return pts

new_lms = {}
BRANCH_PEAKS = {'NW': NW, 'NE': NE, 'S': S}

# Pentagon levels: B (ground), K (base_top=75), L (break_top=85), P (pent_top=125)
PENT_LEVELS = [
    ('B', Z_GROUND,    1.7),   # ground (footprint élargi)
    ('K', Z_BASE_TOP,  1.6),   # base top (juste sous break)
    ('L', Z_BREAK_TOP, 1.0),   # break top (pent base)
    ('P', Z_PENT_TOP,  1.0),   # pent top = base peak boxes
]
for level_code, z, scale in PENT_LEVELS:
    for br_name, peak in BRANCH_PEAKS.items():
        corners = pentagon(peak, z, scale)
        for c_name, xyz in corners.items():
            new_lms[f'Portofino Tower ({level_code}-{c_name}-{br_name})'] = list(xyz)

# Cylinder at all levels including its own top (z=137)
CYL_LEVELS = [
    ('B',  Z_GROUND,    1.7),
    ('K',  Z_BASE_TOP,  1.6),
    ('L',  Z_BREAK_TOP, 1.0),
    ('P',  Z_PENT_TOP,  1.0),
    ('CT', Z_CYL_TOP,   1.0),  # cylinder top
]
for level_code, z, scale in CYL_LEVELS:
    cyl = cylinder(z, scale)
    for c_name, xyz in cyl.items():
        new_lms[f'Portofino Tower (cyl-{level_code}-{c_name})'] = list(xyz)

# Peak boxes: base at z=125, top at z=143
for br_name, peak in BRANCH_PEAKS.items():
    for c_name, xyz in peak_box(peak, Z_PENT_TOP).items():
        new_lms[f'Portofino Tower (PB-{c_name}-{br_name})'] = list(xyz)
    for c_name, xyz in peak_box(peak, Z_PEAK_TOP).items():
        new_lms[f'Portofino Tower (PT-{c_name}-{br_name})'] = list(xyz)

for n in list(new_lms):
    new_lms[n] = [round(float(v), 4) for v in new_lms[n]]

KEEP = {'Portofino Tower (NW)', 'Portofino Tower (NE)', 'Portofino Tower (S)'}
with open('gtamapdata/landmarks.json') as f:
    lms = json.load(f)
to_del = [n for n in list(lms) if 'Portofino Tower' in n and n not in KEEP]
for n in to_del: del lms[n]
print(f'Deleted {len(to_del)} old LMs')
for n, xyz in new_lms.items():
    lms[n] = {'xyz': xyz, 'source_cameras': [], 'error_m': 0.0, 'zone': 'vice_city'}
with open('gtamapdata/landmarks.json.tmp','w') as f: json.dump(lms,f,indent=2)
os.replace('gtamapdata/landmarks.json.tmp', 'gtamapdata/landmarks.json')
total = sum(1 for n in lms if 'Portofino Tower' in n)
print(f'Added {len(new_lms)} new LMs, total: {total}')
