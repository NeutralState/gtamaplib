#!/usr/bin/env python3
"""
upgrade_ray_map.py — Improve the /api/ray_map endpoint:
  - Frustum outer bounds: BLACK and thicker (width 4) instead of thin white
  - Landmark rays: per-landmark RGB color (one color per landmark, not per cam)
  - All landmarks shown (no 8 limit)

Run from gtamaplib-main/:
    python3 tools/upgrade_ray_map.py        # dry run
    python3 tools/upgrade_ray_map.py --apply
"""

import argparse
import os
import shutil
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_PATH = os.path.join(GTAMAP_DIR, "tools", "server.py")
BACKUP_PATH = SERVER_PATH + ".bak2"

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

if not os.path.exists(SERVER_PATH):
    print(f"ERROR: {SERVER_PATH} not found"); sys.exit(1)

with open(SERVER_PATH) as f:
    src = f.read()

# Find the block to replace inside /api/ray_map's inner script
OLD_BLOCK = '''color_list = [(255,68,68),(68,170,255),(255,170,0),(170,68,255),(68,255,170)]
for idx2, cn in enumerate(cam_names):
    try:
        cam = ml.get_camera(cn)
        color = color_list[idx2 % len(color_list)]
        m.draw_camera(cam, d=30000)
        cam_pixels = md.pixels.get(cn, {{}})
        drawn = 0
        for ln in cam_pixels:
            if drawn >= 8: break
            try:
                d = cam.get_landmark_direction(ln)
                if d is None: continue
                target_xy = ml.get_point(cam.xyz, d, 30000)[:2]
                m.draw_line((cam.xy, target_xy), color, 2)
                drawn += 1
            except: pass
        if lm_name and lm_name in cam_pixels:
            try:
                d = cam.get_landmark_direction(lm_name)
                if d is not None:
                    target_xy = ml.get_point(cam.xyz, d, 30000)[:2]
                    m.draw_line((cam.xy, target_xy), (255,255,255), 5)
            except: pass
    except Exception as e:
        print(f'Error {{cn}}: {{e}}')'''

NEW_BLOCK = '''# Build per-landmark color palette using HSV-distributed RGB
import colorsys
def landmark_color(idx, total):
    h = (idx * 0.618033988749895) % 1.0  # golden ratio for max separation
    r, g, b = colorsys.hsv_to_rgb(h, 0.85, 1.0)
    return (int(r*255), int(g*255), int(b*255))

# Collect all unique landmarks across all cams to assign stable colors
all_lms = set()
for cn in cam_names:
    all_lms.update(md.pixels.get(cn, {{}}).keys())
lm_to_color = {{ln: landmark_color(i, len(all_lms)) for i, ln in enumerate(sorted(all_lms))}}

# First pass: draw all landmark rays
for cn in cam_names:
    try:
        cam = ml.get_camera(cn)
        cam_pixels = md.pixels.get(cn, {{}})
        for ln in cam_pixels:
            try:
                d = cam.get_landmark_direction(ln)
                if d is None: continue
                target_xy = ml.get_point(cam.xyz, d, 30000)[:2]
                color = lm_to_color.get(ln, (200, 200, 200))
                width = 4 if (lm_name and ln == lm_name) else 2
                m.draw_line((cam.xy, target_xy), color, width)
            except: pass
    except Exception as e:
        print(f'Error rays {{cn}}: {{e}}')

# Second pass: draw camera frustum on top in BLACK (thicker, more visible)
for cn in cam_names:
    try:
        cam = ml.get_camera(cn)
        # frustum edges (black, width 4) — manually drawn since draw_camera uses white
        for x in (0, cam.w):
            edge_dir = cam.get_pixel_direction((x, cam.h / 2))
            target_xy = ml.get_point(cam.xyz, edge_dir, 30000)[:2]
            m.draw_line((cam.xy, target_xy), (0, 0, 0), 4)
        # cam marker
        m.draw_circle(cam.xy, 8, (255, 255, 255), cam.color, 2, cam.name[0])
    except Exception as e:
        print(f'Error frustum {{cn}}: {{e}}')'''

if OLD_BLOCK not in src:
    print("✗ Could not find old ray_map block in server.py")
    print("  Maybe already upgraded, or content has changed.")
    sys.exit(1)

new_src = src.replace(OLD_BLOCK, NEW_BLOCK)

print("Plan:")
print("  - Frustum edges: white width=1 -> BLACK width=4")
print("  - Landmark rays: per-cam color -> per-landmark RGB (golden ratio HSV)")
print("  - Remove 8 landmark limit (show all)")
print("  - Selected landmark (lm_name) ray: width=4, normal color (not white)")
print("  - Backup current to:", BACKUP_PATH)

if not args.apply:
    print("\n(dry run — re-run with --apply to write changes)")
    sys.exit(0)

shutil.copy(SERVER_PATH, BACKUP_PATH)
print(f"\n✓ Backup: {BACKUP_PATH}")

with open(SERVER_PATH, 'w') as f:
    f.write(new_src)
print(f"✓ Updated: {SERVER_PATH}")

print("\nRestart the server:")
print("  lsof -ti :8765 | xargs kill -9")
print("  python3 tools/server.py")
print("\nThen click Optimize again on a camera and check the map output.")
print("\nRevert with: cp", BACKUP_PATH, SERVER_PATH)
