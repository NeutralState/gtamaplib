#!/usr/bin/env python3
"""
patch_item3_black_frustums.py — Switch the Ray Map frustum outer bounds
from blue to black. Better visibility in the multi-cam context where
several frustums converge near the landmark.
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
        shutil.copy(path, path + '.bak_black_frustums')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


SERVER_OLD = '''# Camera frustum outer bounds in BLUE — same color + width as Generate Map.
# Length = distance from cam to target landmark (so each cam's frustum fits
# the relevant scope without crossing the whole map).
FRUSTUM_BLUE = (96, 165, 250)  # exact match with Generate Map's frust_color'''

SERVER_NEW = '''# Camera frustum outer bounds in BLACK — better contrast in the multi-cam
# Ray Map context where several frustums converge near the landmark.
# Length = distance from cam to target landmark (so each cam's frustum fits
# the relevant scope without crossing the whole map).
FRUSTUM_BLUE = (0, 0, 0)  # name kept for compatibility, value is now black'''


if not args.apply:
    print("DRY-RUN")
print("── Patch tools/server.py ──")
res = patch_file(SERVER_PATH, [
    (SERVER_OLD, SERVER_NEW),
], marker_already_applied="FRUSTUM_BLUE = (0, 0, 0)")
print(f"  → {res}")

if res.startswith('error'):
    sys.exit(1)
elif args.apply:
    print("\n✓ Patch appliqué — restart server :")
    print("  lsof -ti :8765 | xargs kill -9 2>/dev/null && python3 tools/server.py")
else:
    print("\nLance avec --apply pour exécuter.")
