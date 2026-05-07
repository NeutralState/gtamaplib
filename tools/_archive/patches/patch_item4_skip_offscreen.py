#!/usr/bin/env python3
"""
patch_item4_skip_offscreen.py — Skip cones whose apex/corners project to
coordinates way outside the image bounds (means the projected cam is "behind"
the viewer, returning aberrant coords).

Run from repo root :
    python3 patch_item4_skip_offscreen.py             # dry-run
    python3 patch_item4_skip_offscreen.py --apply
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
        shutil.copy(path, path + '.bak_skip_offscreen')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


SERVER_OLD = '''            cones = []
            for other_name, dist in candidates:
                other = md.cameras.get(other_name, {})
                other_xyz = other.get('xyz')
                if not other_xyz:
                    continue
                try:
                    other_cam = ml.get_camera(other_name)
                    apex = cam.get_pixel(other_xyz)
                    if apex is None:
                        continue
                    corners_3d = [
                        ml.get_point(other_cam.xyz, other_cam.get_pixel_direction((0, 0)), d),
                        ml.get_point(other_cam.xyz, other_cam.get_pixel_direction((other_cam.w, 0)), d),
                        ml.get_point(other_cam.xyz, other_cam.get_pixel_direction((other_cam.w, other_cam.h)), d),
                        ml.get_point(other_cam.xyz, other_cam.get_pixel_direction((0, other_cam.h)), d),
                    ]
                    corners_2d = [cam.get_pixel(c) for c in corners_3d]
                    if any(c is None for c in corners_2d):
                        continue'''

SERVER_NEW = '''            cones = []
            # Reject points way outside the image — get_pixel can return aberrant
            # coords for points "behind" the viewer instead of returning None.
            margin = max(cam.w, cam.h) * 2  # allow some overflow but not -16k
            def _onscreen(p):
                if p is None: return False
                x, y = p
                return -margin < x < cam.w + margin and -margin < y < cam.h + margin

            for other_name, dist in candidates:
                other = md.cameras.get(other_name, {})
                other_xyz = other.get('xyz')
                if not other_xyz:
                    continue
                try:
                    other_cam = ml.get_camera(other_name)
                    apex = cam.get_pixel(other_xyz)
                    if not _onscreen(apex):
                        continue
                    corners_3d = [
                        ml.get_point(other_cam.xyz, other_cam.get_pixel_direction((0, 0)), d),
                        ml.get_point(other_cam.xyz, other_cam.get_pixel_direction((other_cam.w, 0)), d),
                        ml.get_point(other_cam.xyz, other_cam.get_pixel_direction((other_cam.w, other_cam.h)), d),
                        ml.get_point(other_cam.xyz, other_cam.get_pixel_direction((0, other_cam.h)), d),
                    ]
                    corners_2d = [cam.get_pixel(c) for c in corners_3d]
                    if not all(_onscreen(c) for c in corners_2d):
                        continue'''


if not args.apply:
    print("═══════════════════════════════════════════════════════════════")
    print("  DRY-RUN")
    print("═══════════════════════════════════════════════════════════════\n")

print("── Patch tools/server.py ──")
res = patch_file(SERVER_PATH, [
    (SERVER_OLD, SERVER_NEW),
], marker_already_applied='def _onscreen(p):')
print(f"  → {res}")

print()
if res.startswith('error'):
    sys.exit(1)
elif args.apply:
    print("✓ Patch appliqué")
    print("\n  Restart server :")
    print("    lsof -ti :8765 | xargs kill -9 2>/dev/null")
    print("    python3 tools/server.py")
    print("  Puis hard refresh browser (Cmd+Shift+R)")
else:
    print("Lance avec --apply pour exécuter.")
