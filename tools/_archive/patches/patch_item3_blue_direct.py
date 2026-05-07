#!/usr/bin/env python3
"""
patch_item3_blue_direct.py — Apply the matched-Generate-Map blue color +
per-cam ray length directly from the state where ray_map_focused was the
last patch applied (i.e. frustum is currently 30000 units long, BLUE = 60,120,255).
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
        shutil.copy(path, path + '.bak_blue_direct')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


SERVER_OLD = '''# Camera frustum outer bounds in BLUE (matches Generate Map convention)
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

SERVER_NEW = '''# Camera frustum outer bounds in BLUE — same color + width as Generate Map.
# Length = distance from cam to target landmark (so each cam's frustum fits
# the relevant scope without crossing the whole map).
FRUSTUM_BLUE = (96, 165, 250)  # exact match with Generate Map's frust_color
for cn in cam_names:
    try:
        cam = ml.get_camera(cn)
        if lm_name:
            target_lm_xyz = md.landmarks.get(lm_name)
            if target_lm_xyz:
                dx = target_lm_xyz[0] - cam.xyz[0]
                dy = target_lm_xyz[1] - cam.xyz[1]
                ray_len = (dx*dx + dy*dy) ** 0.5
            else:
                ray_len = 250
        else:
            ray_len = 250
        for x in (0, cam.w):
            edge_dir = cam.get_pixel_direction((x, cam.h / 2))
            target_xy = ml.get_point(cam.xyz, edge_dir, ray_len)[:2]
            m.draw_line((cam.xy, target_xy), FRUSTUM_BLUE, 2)
        m.draw_circle(cam.xy, 8, (255, 255, 255), cam.color, 2, cam.name[0])
    except Exception as e:
        print(f'Error frustum {{cn}}: {{e}}')'''


if not args.apply:
    print("DRY-RUN")
print("── Patch tools/server.py ──")
res = patch_file(SERVER_PATH, [
    (SERVER_OLD, SERVER_NEW),
], marker_already_applied="FRUSTUM_BLUE = (96, 165, 250)")
print(f"  → {res}")

if res.startswith('error'):
    sys.exit(1)
elif args.apply:
    print("\n✓ Patch appliqué — restart server :")
    print("  lsof -ti :8765 | xargs kill -9 2>/dev/null && python3 tools/server.py")
else:
    print("\nLance avec --apply pour exécuter.")
