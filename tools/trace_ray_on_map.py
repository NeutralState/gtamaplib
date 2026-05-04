#!/usr/bin/env python3
"""
trace_ray_on_map.py — Draw a ray on the map from a camera through a marked
pixel. Useful when a pixel is suspected to point at a different object than
what its landmark name suggests. Following the ray on the map shows what
physical objects fall along its path.

Usage:
    python3 tools/trace_ray_on_map.py "Airport (X)" "Bank of America Financial Center"
    python3 tools/trace_ray_on_map.py "Diner (SE) (A)" "Easy Inn Sign" --map yanis

Output: render_camera_out/ray_<cam>_<lm>.png with the ray drawn from the cam
position outward.
"""

import argparse
import os
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

parser = argparse.ArgumentParser()
parser.add_argument('cam_name', nargs='?',
                    help='Single camera name (use --cams for multiple)')
parser.add_argument('landmark')
parser.add_argument('--cams', nargs='+',
                    help='Multiple camera names (overrides cam_name)')
parser.add_argument('--map', default='yanis', help='Map name (default: yanis)')
parser.add_argument('--ray-length', type=float, default=10000.0,
                    help='How far to trace the ray in meters (default: 10000)')
parser.add_argument('--map-radius', type=float, default=6000.0,
                    help='Half-size of map area around camera (default: 6000)')
parser.add_argument('--out', default=None)
args = parser.parse_args()

# Build cam list
if args.cams:
    cam_names = args.cams
elif args.cam_name:
    cam_names = [args.cam_name]
else:
    print("ERROR: provide cam_name or --cams"); sys.exit(1)

lm_name = args.landmark

# Sanity for each cam
ray_colors = [
    (255, 255, 0),   # yellow
    (0, 255, 255),   # cyan
    (255, 0, 255),   # magenta
    (255, 128, 0),   # orange
    (0, 255, 128),   # mint
    (255, 64, 64),   # red
]

m = ml.get_map(args.map)
m.open(scale=1.0, add_padding=True)

# Helper: draw a small cross at a world position
def draw_cross(world_x, world_y, fill, size=20, width=3):
    m.draw_line(((world_x - size, world_y), (world_x + size, world_y)),
                fill=fill, width=width)
    m.draw_line(((world_x, world_y - size), (world_x, world_y + size)),
                fill=fill, width=width)

# Compute area: bounding box around all cams + landmark + buffer
all_x, all_y = [], []
for cam_name in cam_names:
    if cam_name in md.cameras and md.cameras[cam_name].get('xyz'):
        x, y, _ = md.cameras[cam_name]['xyz']
        all_x.append(x)
        all_y.append(y)
if lm_name in md.landmarks:
    lx, ly, _ = md.landmarks[lm_name]
    all_x.append(lx)
    all_y.append(ly)

if not all_x:
    print(f"ERROR: no valid cameras"); sys.exit(1)

cx_map = (min(all_x) + max(all_x)) / 2
cy_map = (min(all_y) + max(all_y)) / 2
spread = max(max(all_x) - min(all_x), max(all_y) - min(all_y))
radius = max(args.map_radius, spread / 2 + 1500)
area = (cx_map - radius, cy_map - radius, cx_map + radius, cy_map + radius)

# Draw landmark current position (white-ish cross)
if lm_name in md.landmarks:
    lx, ly, _ = md.landmarks[lm_name]
    draw_cross(lx, ly, fill=(255, 255, 255), size=40, width=5)
    print(f"Landmark '{lm_name}' xyz = ({lx:.0f}, {ly:.0f}) — drawn as WHITE cross")

# Draw each cam + ray
import math
print()
for i, cam_name in enumerate(cam_names):
    if cam_name not in md.cameras:
        print(f"  ⚠ skip {cam_name}: not found"); continue
    if cam_name not in md.pixels or lm_name not in md.pixels[cam_name]:
        print(f"  ⚠ skip {cam_name}: no pixel for '{lm_name}'"); continue

    cam = ml.get_camera(cam_name)
    pixel = md.pixels[cam_name][lm_name]
    direction = cam.get_landmark_direction(lm_name)
    end_x = cam.x + float(direction[0]) * args.ray_length
    end_y = cam.y + float(direction[1]) * args.ray_length
    color = ray_colors[i % len(ray_colors)]
    color_name = ['YELLOW','CYAN','MAGENTA','ORANGE','MINT','RED'][i % len(ray_colors)]

    # Cam position cross
    draw_cross(cam.x, cam.y, fill=color, size=30, width=4)
    # Ray
    m.draw_line(((cam.x, cam.y), (end_x, end_y)), fill=color, width=2)

    bearing = (math.degrees(math.atan2(float(direction[0]), float(direction[1]))) + 360) % 360
    print(f"  {color_name:<8} {cam_name:<32}  pixel={pixel}  bearing={bearing:.1f}°  cam=({cam.x:.0f},{cam.y:.0f})")

# Output
if args.out:
    out_path = args.out
else:
    os.makedirs('render_camera_out', exist_ok=True)
    safe_lm  = lm_name.replace('/', '_').replace(' ', '_')
    if len(cam_names) == 1:
        safe_cam = cam_names[0].replace('/', '_').replace(' ', '_')
        out_path = f'render_camera_out/ray_{safe_cam}_{safe_lm}.png'
    else:
        out_path = f'render_camera_out/rays_{safe_lm}.png'

m.save(out_path, area)
print(f"\nSaved: {out_path}")
print(f"\nLegend:")
print(f"  WHITE cross  = current landmark xyz in landmarks.json")
print(f"  cam crosses + rays color-coded above")
