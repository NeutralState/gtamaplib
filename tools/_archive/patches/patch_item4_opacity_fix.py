#!/usr/bin/env python3
"""
patch_item4_opacity_fix.py — Bumps the in-cone image opacity from 35% to 100%.
Matches rlx's intent ("in the cone") more directly. Hover highlight is now
purely via the frustum lines (thicker + label), not opacity.

Run from repo root :
    python3 patch_item4_opacity_fix.py             # dry-run
    python3 patch_item4_opacity_fix.py --apply
"""
import argparse
import os
import shutil
import sys

REPO_ROOT  = os.path.dirname(os.path.abspath(__file__))
CALIB_PATH = os.path.join(REPO_ROOT, 'tools', 'calib.html')

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

if not os.path.isfile(CALIB_PATH):
    print("✗ Lance depuis la racine de gtamaplib-main/")
    sys.exit(1)


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
        shutil.copy(path, path + '.bak_opacity_fix')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


CALIB_OLD = '''      _ocDrawImageInQuad(img, corners, isHover ? 1.0 : 0.35);'''
CALIB_NEW = '''      _ocDrawImageInQuad(img, corners, 1.0);'''


if not args.apply:
    print("═══════════════════════════════════════════════════════════════")
    print("  DRY-RUN — Lance avec --apply pour exécuter")
    print("═══════════════════════════════════════════════════════════════\n")

print("── Patch tools/calib.html ──")
res = patch_file(CALIB_PATH, [
    (CALIB_OLD, CALIB_NEW),
], marker_already_applied='_ocDrawImageInQuad(img, corners, 1.0);')
print(f"  → {res}")

print()
if res.startswith('error'):
    sys.exit(1)
elif args.apply:
    print("✓ Patch appliqué")
    print("\n  Hard refresh http://localhost:8765/calib.html (Cmd+Shift+R)")
else:
    print("Lance avec --apply pour exécuter.")
