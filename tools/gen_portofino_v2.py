#!/usr/bin/env python3
"""
Generate complete Portofino mesh:
- 5 z-levels: ground(0), break_top(69), pentagons_base(78), pentagons_top(116), peak_top(143)
- 3 pentagons (NW/NE/S branches) × 5 levels × 5 corners = 75 LMs for pentagons
- 1 cylinder × 5 levels × 8 corners = 40 LMs for cylinder
- 3 peak boxes (small towers at top): 4 corners × 3 boxes × 2 levels (base z=116, top z=143) = 24 LMs
- Total: ~140 LMs (we'll prune redundant ones)
"""
import sys, json, os
sys.path.insert(0, '.')
import numpy as np
import gtamapdata as md

NW = np.array(md.landmarks['Portofino Tower (NW)'])
NE = np.array(md.landmarks['Portofino Tower (NE)'])
S  = np.array(md.landmarks['Portofino Tower (S)'])

centroid_xy = (NW[:2] + NE[:2] + S[:2]) / 3

# Z levels
Z_GROUND       = 0.0
Z_BREAK_TOP    = 69.0
Z_PENT_BASE    = 78.0
Z_PENT_TOP     = 116.0
Z_PEAK_TOP     = 143.0  # peak boxes top

# Pentagon dimensions (m)
SIDE_FRONT = 11.2     # peak-to-corner (front edge of pentagon)
PENTAGON_DEPTH = 13.0  # peak to inner corner (radial direction)
R_CYLINDER = 8.87      # cylinder radius

# Peak box dimensions (m) - small towers at the top of each branch
PEAK_BOX_SIDE = 8.5    # square footprint, side ~8.5m

# === Generate pentagon corners at a given z ===
def pentagon(peak_xyz, z):
    """5 corners: peak, frontL, frontR, innerL, innerR"""
    peak_xy = peak_xyz[:2]
    radial = peak_xy - centroid_xy
    radial_unit = radial / np.linalg.norm(radial)
    perp = np.array([-radial_unit[1], radial_unit[0]])
    
    front_half = SIDE_FRONT / 2
    front_L = peak_xy + perp * front_half
    front_R = peak_xy - perp * front_half
    
    inner_pos = centroid_xy + radial_unit * R_CYLINDER
    inner_half = 8.4  # approx half-side of curved edge
    inner_L = inner_pos + perp * inner_half
    inner_R = inner_pos - perp * inner_half
    
    return {
        'peak':   (peak_xy[0],  peak_xy[1],  z),
        'frontL': (front_L[0],  front_L[1],  z),
        'frontR': (front_R[0],  front_R[1],  z),
        'innerL': (inner_L[0],  inner_L[1],  z),
        'innerR': (inner_R[0],  inner_R[1],  z),
    }

# === Peak box (4 corners) sitting on top of pentagon peak ===
def peak_box(peak_xyz, z):
    """4 corners around the peak (small tower)"""
    peak_xy = peak_xyz[:2]
    radial = peak_xy - centroid_xy
    radial_unit = radial / np.linalg.norm(radial)
    perp = np.array([-radial_unit[1], radial_unit[0]])
    
    half = PEAK_BOX_SIDE / 2
    # 4 corners: outer-L, outer-R, inner-L, inner-R (relative to radial)
    outer = peak_xy + radial_unit * half
    inner = peak_xy - radial_unit * half
    return {
        'pbOL': (outer[0] + perp[0] * half, outer[1] + perp[1] * half, z),
        'pbOR': (outer[0] - perp[0] * half, outer[1] - perp[1] * half, z),
        'pbIL': (inner[0] + perp[0] * half, inner[1] + perp[1] * half, z),
        'pbIR': (inner[0] - perp[0] * half, inner[1] - perp[1] * half, z),
    }

# === Cylinder (8 points around) ===
def cylinder(z):
    pts = {}
    for i in range(8):
        a = i * np.pi / 4  # 0, 45, 90, ...
        x = centroid_xy[0] + R_CYLINDER * np.cos(a)
        y = centroid_xy[1] + R_CYLINDER * np.sin(a)
        pts[f'cyl{i}'] = (x, y, z)
    return pts

# === Generate all LMs ===
new_lms = {}

BRANCH_PEAKS = {'NW': NW, 'NE': NE, 'S': S}
Z_LEVELS = {
    'B':  Z_GROUND,       # base (ground)
    'K':  Z_BREAK_TOP,    # break top
    'P':  Z_PENT_BASE,    # pentagon start
    'T':  Z_PENT_TOP,     # top pentagons = base peak boxes
}

# Pentagons at 4 levels (B, K, P, T) -- not at peak_top because pentagons end at z=116
for level_code, z in Z_LEVELS.items():
    for br_name, peak in BRANCH_PEAKS.items():
        corners = pentagon(peak, z)
        for c_name, xyz in corners.items():
            if c_name == 'peak':
                continue  # we don't want the peak at lower levels (it's the radial point)
            new_lms[f'Portofino Tower ({level_code}-{c_name}-{br_name})'] = list(xyz)

# Peak boxes (2 levels: T=base of peak box, peak_top=top)
for br_name, peak in BRANCH_PEAKS.items():
    box_base = peak_box(peak, Z_PENT_TOP)
    box_top  = peak_box(peak, Z_PEAK_TOP)
    for c_name, xyz in box_base.items():
        new_lms[f'Portofino Tower (PB-{c_name}-{br_name})'] = list(xyz)
    for c_name, xyz in box_top.items():
        new_lms[f'Portofino Tower (PT-{c_name}-{br_name})'] = list(xyz)

# Cylinder at all 5 levels including peak_top (cylinder goes all the way up)
for level_code, z in {**Z_LEVELS, 'CT': Z_PEAK_TOP}.items():
    cyl = cylinder(z)
    for c_name, xyz in cyl.items():
        new_lms[f'Portofino Tower (cyl-{level_code}-{c_name})'] = list(xyz)

# Cleanup floats
for n in list(new_lms):
    new_lms[n] = [round(float(v), 4) for v in new_lms[n]]

# === Apply to landmarks.json ===
# First delete all existing Portofino LMs except the 3 peaks
KEEP = {'Portofino Tower (NW)', 'Portofino Tower (NE)', 'Portofino Tower (S)'}

with open('gtamapdata/landmarks.json') as f:
    lms = json.load(f)

to_del = [n for n in list(lms) if 'Portofino Tower' in n and n not in KEEP]
for n in to_del:
    del lms[n]
print(f'Deleted {len(to_del)} old LMs')

for n, xyz in new_lms.items():
    lms[n] = {'xyz': xyz, 'source_cameras': [], 'error_m': 0.0, 'zone': 'vice_city'}

with open('gtamapdata/landmarks.json.tmp','w') as f: json.dump(lms,f,indent=2)
os.replace('gtamapdata/landmarks.json.tmp', 'gtamapdata/landmarks.json')

total = sum(1 for n in lms if 'Portofino Tower' in n)
print(f'\nAdded {len(new_lms)} new LMs')
print(f'Total Portofino LMs now: {total}')
