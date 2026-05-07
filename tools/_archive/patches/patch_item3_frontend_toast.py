#!/usr/bin/env python3
"""
patch_item3_frontend_toast.py — Updates the triangulate toast in calib.html
to use the new /api/triangulate response fields (n_cams + worst_cam +
worst_distance_m) instead of the old (cam_a + cam_b).

Run from repo root :
    python3 patch_item3_frontend_toast.py             # dry-run
    python3 patch_item3_frontend_toast.py --apply
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
        shutil.copy(path, path + '.bak_item3_toast')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


CALIB_OLD = '''  document.getElementById('ray-map-info').innerHTML =
    `<span style="color:var(--green)">✓ Triangulated</span> · xyz=[${res.xyz.map(v=>v.toFixed(1)).join(', ')}] · error=${res.error_m}m · from ${res.cam_a} + ${res.cam_b}`;'''

CALIB_NEW = '''  // res now has: xyz, error_m (mean), worst_cam, worst_distance_m, n_cams
  // (was: cam_a, cam_b before item 3 — intersect_rays uses all rays at once)
  const detail = res.worst_cam
    ? `from ${res.n_cams} cams · worst: ${res.worst_cam} (${res.worst_distance_m}m)`
    : `from ${res.n_cams || 'multiple'} cams`;
  document.getElementById('ray-map-info').innerHTML =
    `<span style="color:var(--green)">✓ Triangulated</span> · xyz=[${res.xyz.map(v=>v.toFixed(1)).join(', ')}] · mean error=${res.error_m}m · ${detail}`;'''


if not args.apply:
    print("DRY-RUN")
print("── Patch tools/calib.html ──")
res = patch_file(CALIB_PATH, [
    (CALIB_OLD, CALIB_NEW),
], marker_already_applied='// res now has: xyz, error_m (mean)')
print(f"  → {res}")

if res.startswith('error'):
    sys.exit(1)
elif args.apply:
    print("\n✓ Patch appliqué — hard refresh browser (Cmd+Shift+R)")
else:
    print("\nLance avec --apply pour exécuter.")
