#!/usr/bin/env python3
"""
Generate Portofino Tower LMs derived from 3 anchor LMs (NW, NE, S).

Geometry:
- 3-branch star at 120deg around centroid
- 5 z-levels: ground(0), podium(30), break(90), branches_start(110), top(142)
- Each branch has 2 outer corners per level (P+Q at branch tip)
- Plus 4 centroid points (one per non-top level)

Output: writes to gtamapdata/landmarks.json (idempotent: skips existing)
        prints _PORTOFINO_LM_MAP block for bundle_adjust.py
"""
import sys, json, os
sys.path.insert(0, '.')
import numpy as np
import gtamapdata as md

LEVELS = {
    'B':     0.0,    # base/ground
    'P':    30.0,    # podium top
    'M':    90.0,    # mid break
    'H':   110.0,    # high (branches start)
    # top level uses z = peak z (computed per branch)
}

# 3 anchor peaks
NW = np.array(md.landmarks['Portofino Tower (NW)'])
NE = np.array(md.landmarks['Portofino Tower (NE)'])
S  = np.array(md.landmarks['Portofino Tower (S)'])

centroid_xy = (NW[:2] + NE[:2] + S[:2]) / 3
z_top = (NW[2] + NE[2] + S[2]) / 3

# Branch radial vectors (from centroid)
branches = {
    'NW': NW[:2] - centroid_xy,
    'NE': NE[:2] - centroid_xy,
    'S':  S[:2]  - centroid_xy,
}

# Branch width (perpendicular to radial) - estimate from inter-branch gaps
# IRL each branch is ~10m wide; in-game scale matches LMs ~18m apart
# So branch half-width ~5m. Use the average peak-to-peak distance / 4 as proxy
peak_dists = [
    np.linalg.norm(NW[:2] - NE[:2]),
    np.linalg.norm(NE[:2] - S[:2]),
    np.linalg.norm(S[:2]  - NW[:2]),
]
branch_half_width = np.mean(peak_dists) / 4  # ~9m, plausible
print(f'centroid xy: {centroid_xy}')
print(f'z_top mean: {z_top:.2f}')
print(f'branch half-width: {branch_half_width:.2f}m')

# Generate LMs
new_lms = {}
PORTOFINO_MAP_LINES = []

for level_name, z in LEVELS.items():
    # Per-branch outer corners
    for br_name, radial in branches.items():
        radial_unit = radial / np.linalg.norm(radial)
        perp = np.array([-radial_unit[1], radial_unit[0]])  # rotate 90deg
        
        # Branch tip position (extend out from centroid by full radial length)
        tip = centroid_xy + radial
        
        # Two outer corners at the tip (left and right of branch tip)
        left  = tip + perp * branch_half_width
        right = tip - perp * branch_half_width
        
        # LM names: e.g. "Portofino Tower (BL-NW)" = base, left, NW branch
        name_L = f'Portofino Tower ({level_name}L-{br_name})'
        name_R = f'Portofino Tower ({level_name}R-{br_name})'
        
        new_lms[name_L] = [round(float(left[0]), 4),  round(float(left[1]), 4),  round(z, 4)]
        new_lms[name_R] = [round(float(right[0]), 4), round(float(right[1]), 4), round(z, 4)]
    
    # Centroid at this level
    new_lms[f'Portofino Tower ({level_name}-C)'] = [
        round(float(centroid_xy[0]), 4),
        round(float(centroid_xy[1]), 4),
        round(z, 4),
    ]

# Apply to landmarks.json
with open('gtamapdata/landmarks.json') as f:
    lms_json = json.load(f)

added = 0
for name, xyz in new_lms.items():
    if name in lms_json:
        continue
    lms_json[name] = {
        'xyz': xyz,
        'source_cameras': [],
        'error_m': 0.0,
        'zone': 'vice_city',
    }
    added += 1
    PORTOFINO_MAP_LINES.append(f'    "{name}": ({xyz[0]:.4f}, {xyz[1]:.4f}, {xyz[2]:.4f}),')

# Also add NW/NE/S to the map lines (existing peaks)
for n in ['Portofino Tower (NW)', 'Portofino Tower (NE)', 'Portofino Tower (S)']:
    xyz = md.landmarks[n]
    PORTOFINO_MAP_LINES.insert(0, f'    "{n}": ({xyz[0]:.4f}, {xyz[1]:.4f}, {xyz[2]:.4f}),')

with open('gtamapdata/landmarks.json.tmp','w') as f: json.dump(lms_json, f, indent=2)
os.replace('gtamapdata/landmarks.json.tmp', 'gtamapdata/landmarks.json')

print(f'\nAdded {added} new LMs to landmarks.json')
print(f'\nTotal Portofino LMs now: {sum(1 for n in lms_json if "Portofino Tower" in n)}')

# Print the _PORTOFINO_LM_MAP block for bundle_adjust.py
print('\n' + '=' * 60)
print('_PORTOFINO_LM_MAP block (copy into bundle_adjust.py):')
print('=' * 60)
print('_PORTOFINO_LM_MAP = {')
for line in PORTOFINO_MAP_LINES:
    print(line)
print('}')
