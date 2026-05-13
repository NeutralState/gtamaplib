#!/usr/bin/env python3
"""
render_camera.py — Render a camera frame with current xyz/ypr/fov, projecting
all visible landmarks. Same render as find_camera() produces but without
running any optimization — just shows the current state.

Usage:
    python3 tools/render_camera.py "Ambrosia 04 (Fires)"
    python3 tools/render_camera.py "Ambrosia 04 (Fires)" --out my_render.png

Output goes to render_camera_out/<cam_name>.png by default.
"""

import argparse
import os
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml

parser = argparse.ArgumentParser()
parser.add_argument('cam_name')
parser.add_argument('--out', default=None,
                    help='Output PNG path (default: render_camera_out/<cam>.png)')
args = parser.parse_args()

# Render
print(f"Rendering {args.cam_name}...")
cam = ml.get_camera(args.cam_name)
print(f"  xyz  = {cam.xyz}")
print(f"  ypr  = {cam.ypr}")
print(f"  fov  = {cam.fov}")

img = cam.render_all()

# Output path
if args.out:
    out_path = args.out
else:
    os.makedirs('render_camera_out', exist_ok=True)
    safe_name = args.cam_name.replace('/', '_').replace(' ', '_')
    out_path = f'render_camera_out/{safe_name}.png'

img.save(out_path)
print(f"\nSaved: {out_path}")
