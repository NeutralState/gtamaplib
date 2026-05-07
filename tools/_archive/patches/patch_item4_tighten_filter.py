#!/usr/bin/env python3
"""
patch_item4_tighten_filter.py — Tightens the on-screen filter from
±2*max_dim margin (which lets through far off-screen cones) to a small
overlap check (the cone must visibly intersect the image).
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
        shutil.copy(path, path + '.bak_tighten_filter')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


SERVER_OLD = '''            cones = []
            # Reject points way outside the image — get_pixel can return aberrant
            # coords for points "behind" the viewer instead of returning None.
            margin = max(cam.w, cam.h) * 2  # allow some overflow but not -16k
            def _onscreen(p):
                if p is None: return False
                x, y = p
                return -margin < x < cam.w + margin and -margin < y < cam.h + margin'''

SERVER_NEW = '''            cones = []
            # Reject points outside (or just barely outside) the image —
            # get_pixel returns aberrant coords for points behind the viewer.
            # The cone must overlap the visible image to be useful.
            margin = max(cam.w, cam.h) * 0.1  # 10% overflow tolerance
            def _onscreen(p):
                if p is None: return False
                x, y = p
                return -margin < x < cam.w + margin and -margin < y < cam.h + margin

            def _quad_overlaps_image(apex, corners):
                """At least one of apex or corners must be inside the image."""
                pts = [apex] + list(corners)
                for p in pts:
                    if p is None: continue
                    x, y = p
                    if 0 <= x <= cam.w and 0 <= y <= cam.h:
                        return True
                return False'''


# Update the call site to use _quad_overlaps_image too
SERVER_OLD_CHECK = '''                    corners_2d = [cam.get_pixel(c) for c in corners_3d]
                    if not all(_onscreen(c) for c in corners_2d):
                        continue'''

SERVER_NEW_CHECK = '''                    corners_2d = [cam.get_pixel(c) for c in corners_3d]
                    if not all(_onscreen(c) for c in corners_2d):
                        continue
                    if not _quad_overlaps_image(apex, corners_2d):
                        continue'''


if not args.apply:
    print("DRY-RUN")
print("── Patch tools/server.py ──")
res = patch_file(SERVER_PATH, [
    (SERVER_OLD, SERVER_NEW),
    (SERVER_OLD_CHECK, SERVER_NEW_CHECK),
], marker_already_applied='_quad_overlaps_image')
print(f"  → {res}")

if res.startswith('error'):
    sys.exit(1)
elif args.apply:
    print("\n✓ Patch appliqué — restart server :")
    print("    lsof -ti :8765 | xargs kill -9 2>/dev/null && python3 tools/server.py")
else:
    print("\nLance avec --apply pour exécuter.")
