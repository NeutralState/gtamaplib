#!/usr/bin/env python3
"""
Generate precise Portofino LMs based on measured pentagon dimensions.

Per branch pentagon (5 corners):
- Peak (outer tip): existing LM (NW/NE/S)
- 2 outer corners (left/right of peak, forming the front edge ~13m)
- 2 inner corners (where pentagon meets cylinder, curved ~17m)
"""
import sys, json, os
sys.path.insert(0, '.')
import numpy as np
import gtamapdata as md

# Anchor peaks
NW = np.array(md.landmarks['Portofino Tower (NW)'])
NE = np.array(md.landmarks['Portofino Tower (NE)'])
S  = np.array(md.landmarks['Portofino Tower (S)'])

centroid_xy = (NW[:2] + NE[:2] + S[:2]) / 3
z_top = (NW[2] + NE[2] + S[2]) / 3

# Pentagon dimensions (meters)
SIDE_FRONT = 11.2     # peak-to-corner (the 80px side)
SIDE_SIDE  = 12.0     # corner-to-inner (the ~85-95px sides averaged)
SIDE_INNER = 16.8     # curved side at cylinder (the 120-125px)

# Cylinder radius (estimated): distance from centroid to inner corner of pentagon
# Each pentagon's inner side is tangent to the cylinder
# If pentagon has 16.8m inner side, and the curved side wraps a circle of radius R,
# inner corners are at distance R from centroid
# We'll estimate R from average peak-to-centroid distance minus the pentagon depth

PEAK_DISTS = [np.linalg.norm(p[:2] - centroid_xy) for p in [NW, NE, S]]
avg_peak_dist = np.mean(PEAK_DISTS)
print(f'Average peak distance from centroid: {avg_peak_dist:.2f}m')

# Pentagon "depth" from peak to inner side (approx)
PENTAGON_DEPTH = 13.0   # roughly equivalent to the IRL residence depth

# Cylinder radius
R_CYLINDER = avg_peak_dist - PENTAGON_DEPTH
print(f'Estimated cylinder radius: {R_CYLINDER:.2f}m')

# For each branch, compute the 5 pentagon corners
def pentagon_corners(peak_xyz, centroid_xy, z):
    """Generate 5 corners of the pentagon around a peak."""
    peak_xy = peak_xyz[:2]
    radial = peak_xy - centroid_xy
    radial_dist = np.linalg.norm(radial)
    radial_unit = radial / radial_dist
    perp = np.array([-radial_unit[1], radial_unit[0]])
    
    # Front corners (left/right of peak, perpendicular to radial)
    front_half_width = SIDE_FRONT / 2
    front_L = peak_xy + perp * front_half_width
    front_R = peak_xy - perp * front_half_width
    
    # Inner corners (toward cylinder)
    # Move from front_L/R back along radial by SIDE_SIDE (not exactly, but close)
    # Then the inner corners are on the cylinder
    inner_radius = R_CYLINDER + 2  # slight overlap
    # Project front_L and front_R back along radial until they touch the cylinder
    # Simplification: place inner corners at cylinder edge at perpendicular angle
    inner_half_width = SIDE_INNER / 2
    inner_pos_xy = centroid_xy + radial_unit * R_CYLINDER  # point on cylinder along radial
    inner_L = inner_pos_xy + perp * inner_half_width
    inner_R = inner_pos_xy - perp * inner_half_width
    
    return {
        'peak':    [round(float(peak_xy[0]), 4), round(float(peak_xy[1]), 4), round(z, 4)],
        'frontL':  [round(float(front_L[0]),  4), round(float(front_L[1]),  4), round(z, 4)],
        'frontR':  [round(float(front_R[0]),  4), round(float(front_R[1]),  4), round(z, 4)],
        'innerL':  [round(float(inner_L[0]),  4), round(float(inner_L[1]),  4), round(z, 4)],
        'innerR':  [round(float(inner_R[0]),  4), round(float(inner_R[1]),  4), round(z, 4)],
    }

# Generate pentagons at top z
pentagons = {
    'NW': pentagon_corners(NW, centroid_xy, NW[2]),
    'NE': pentagon_corners(NE, centroid_xy, NE[2]),
    'S':  pentagon_corners(S,  centroid_xy, S[2]),
}

# Cylinder center top
cylinder_top = [round(float(centroid_xy[0]), 4), round(float(centroid_xy[1]), 4), round(z_top, 4)]

# Print results
print()
print('Generated pentagon corners (top level):')
for br_name, p in pentagons.items():
    print(f'  {br_name}:')
    for corner_name, xyz in p.items():
        print(f'    {corner_name}: {xyz}')

print(f'\nCylinder center: {cylinder_top}')

# Output LMs in landmarks.json format
print()
print('=' * 60)
print('New LMs to add:')
print('=' * 60)

new_lms = {}
for br_name, p in pentagons.items():
    for corner in ['frontL', 'frontR', 'innerL', 'innerR']:
        name = f'Portofino Tower ({corner}-{br_name})'
        new_lms[name] = p[corner]
new_lms['Portofino Tower (CC)'] = cylinder_top  # cylinder center

for n, xyz in new_lms.items():
    print(f'  {n}: {xyz}')

print(f'\nTotal new LMs: {len(new_lms)}')
