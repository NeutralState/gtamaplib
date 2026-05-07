#!/usr/bin/env python3
"""
patch_item4_simple_bbox.py — Replace the matrix-transform quad rendering
with a simple bounding-box rendering. Less fancy than the perfect
perspective warp, but works on every quad without weird matrix edge cases.

The image is drawn in the bbox of the projected quad. The frustum lines are
still drawn on top showing the actual frustum shape.
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
        shutil.copy(path, path + '.bak_simple_bbox')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


# Replace the entire complex draw with a simpler bbox-based one
CALIB_OLD_DRAW = '''    // Draw the image inside the quad (if loaded), faded normally, full on hover
    const img = _ocImgCache.get(cone.name);
    if (img) {
      _ocDrawImageInQuad(img, corners, 1.0);
    }'''

CALIB_NEW_DRAW = '''    // Draw the image in the bounding box of the quad (simple, robust).
    const img = _ocImgCache.get(cone.name);
    if (img && img.naturalWidth > 0) {
      const xs = corners.map(c => c[0]);
      const ys = corners.map(c => c[1]);
      const bx = Math.min(...xs);
      const by = Math.min(...ys);
      const bw = Math.max(...xs) - bx;
      const bh = Math.max(...ys) - by;
      if (bw > 4 && bh > 4) {
        ctx.save();
        // Clip to quad shape so image stays inside the cone outline
        ctx.beginPath();
        ctx.moveTo(corners[0][0], corners[0][1]);
        for (let j = 1; j < 4; j++) ctx.lineTo(corners[j][0], corners[j][1]);
        ctx.closePath();
        ctx.clip();
        ctx.drawImage(img, bx, by, bw, bh);
        ctx.restore();
      }
    }'''


if not args.apply:
    print("DRY-RUN")
print("── Patch tools/calib.html ──")
res = patch_file(CALIB_PATH, [
    (CALIB_OLD_DRAW, CALIB_NEW_DRAW),
], marker_already_applied='Draw the image in the bounding box of the quad')
print(f"  → {res}")

if res.startswith('error'):
    sys.exit(1)
elif args.apply:
    print("\n✓ Patch appliqué")
    print("  Hard refresh browser (Cmd+Shift+R) — pas besoin de restart server")
else:
    print("\nLance avec --apply pour exécuter.")
