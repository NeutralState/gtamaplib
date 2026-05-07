#!/usr/bin/env python3
"""
patch_item3_ray_map_focused.py — Update /api/ray_map to:
  - When a lm_name is passed: draw ONLY the rays going to that landmark
    (one per source cam) instead of all rays from all pixels of all cams.
  - Color rays based on perpendicular distance from the triangulated point
    (green = good fit, red = outlier — same color scheme as bundle adjust).
  - Camera frustum outer bounds in BLUE (matches Generate Map convention).

Run from repo root :
    python3 patch_item3_ray_map_focused.py             # dry-run
    python3 patch_item3_ray_map_focused.py --apply
"""
import argparse
import os
import shutil
import sys

REPO_ROOT  = os.path.dirname(os.path.abspath(__file__))
SERVER_PATH = os.path.join(REPO_ROOT, 'tools', 'server.py')

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()


def patch_file(path, replacements, marker_already_applied=None):
    with open(path) as f:
        content = f.read()
    if marker_already_applied and marker_already_applied in content:
        return 'already_patched'
    new_content = content
    for old, new in replacements:
        if old not in new_content:
            return f"error: pattern not found:\n{old[:200]}..."
        if new_content.count(old) > 1:
            return f"error: pattern found multiple times: {old[:100]}..."
        new_content = new_content.replace(old, new)
    if args.apply:
        shutil.copy(path, path + '.bak_ray_map_focused')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


SERVER_OLD = '''# Build per-landmark color palette using HSV-distributed RGB
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

SERVER_NEW = '''import numpy as np

# If a target landmark is provided: triangulate it via intersect_rays and
# color each ray by its perpendicular distance from the result (green=good,
# red=bad — same scheme as bundle adjust).
ray_data = []  # list of (cn, target_xy, color, width)
if lm_name:
    rays = []
    valid_cams = []
    for cn in cam_names:
        try:
            cam = ml.get_camera(cn)
            if lm_name not in md.pixels.get(cn, {{}}): continue
            d = cam.get_landmark_direction(lm_name)
            if d is None: continue
            rays.append((tuple(cam.xyz), tuple(d)))
            valid_cams.append(cn)
        except Exception:
            pass

    if len(rays) >= 2:
        try:
            pt, distances = ml.intersect_rays(rays)
            # Determine color from distance: green<0.5m, yellow<2m, red>5m
            def err_color(dist_m):
                if dist_m < 0.5: return (0, 220, 80)       # green
                if dist_m < 2.0: return (200, 220, 60)     # yellow-green
                if dist_m < 5.0: return (255, 165, 0)      # orange
                return (230, 60, 60)                       # red
            for cn, dist in zip(valid_cams, distances):
                cam = ml.get_camera(cn)
                d = cam.get_landmark_direction(lm_name)
                target_xy = ml.get_point(cam.xyz, d, 30000)[:2]
                ray_data.append((cn, target_xy, err_color(float(dist)), 4))
        except Exception as e:
            print(f'intersect_rays failed: {{e}}')

# If no lm_name (or triangulation failed): fallback to old behavior
# (all rays from all cams, but with much lower alpha to keep readable)
if not ray_data:
    import colorsys
    def landmark_color(idx, total):
        h = (idx * 0.618033988749895) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.85, 1.0)
        return (int(r*255), int(g*255), int(b*255))
    all_lms = set()
    for cn in cam_names:
        all_lms.update(md.pixels.get(cn, {{}}).keys())
    lm_to_color = {{ln: landmark_color(i, len(all_lms)) for i, ln in enumerate(sorted(all_lms))}}
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
                    ray_data.append((cn, target_xy, color, width))
                except: pass
        except Exception as e:
            print(f'Error rays {{cn}}: {{e}}')

# Draw the rays
for cn, target_xy, color, width in ray_data:
    try:
        cam = ml.get_camera(cn)
        m.draw_line((cam.xy, target_xy), color, width)
    except Exception:
        pass

# Camera frustum outer bounds in BLUE (matches Generate Map convention)
FRUSTUM_BLUE = (60, 120, 255)
for cn in cam_names:
    try:
        cam = ml.get_camera(cn)
        for x in (0, cam.w):
            edge_dir = cam.get_pixel_direction((x, cam.h / 2))
            target_xy = ml.get_point(cam.xyz, edge_dir, 30000)[:2]
            m.draw_line((cam.xy, target_xy), FRUSTUM_BLUE, 3)
        m.draw_circle(cam.xy, 8, (255, 255, 255), cam.color, 2, cam.name[0])
    except Exception as e:
        print(f'Error frustum {{cn}}: {{e}}')'''


if not args.apply:
    print("DRY-RUN")

print("── Patch tools/server.py ──")
res = patch_file(SERVER_PATH, [
    (SERVER_OLD, SERVER_NEW),
], marker_already_applied='FRUSTUM_BLUE = (60, 120, 255)')
print(f"  → {res}")

if res.startswith('error'):
    sys.exit(1)
elif args.apply:
    print("\n✓ Patch appliqué — restart server :")
    print("  lsof -ti :8765 | xargs kill -9 2>/dev/null && python3 tools/server.py")
else:
    print("\nLance avec --apply pour exécuter.")
