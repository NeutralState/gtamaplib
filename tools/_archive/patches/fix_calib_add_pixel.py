#!/usr/bin/env python3
"""
fix_calib_add_pixel.py — Fix the bug where clicking on the main canvas to add
a new landmark pixel doesn't pass &new=1, so the landmark entry isn't created
in landmarks.json.

The pxeWrap (zoom editor) flow sends &new=1 correctly. The canvasWrap (main)
flow on line 1094 omits it. We add the same conditional flag here.

Run from gtamaplib-main/:
    python3 tools/fix_calib_add_pixel.py        # dry run
    python3 tools/fix_calib_add_pixel.py --apply
"""

import argparse
import os
import shutil
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(GTAMAP_DIR, "calib_fresh.html")
BACKUP_PATH = HTML_PATH + ".bak_addpx"

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

if not os.path.exists(HTML_PATH):
    print(f"ERROR: {HTML_PATH} not found"); sys.exit(1)

with open(HTML_PATH) as f:
    src = f.read()

OLD = """  // Save pixel
  const res = await fetch(`/api/add_pixel?cam=${encodeURIComponent(currentCam)}&lm=${encodeURIComponent(addPxSelectedLm)}&px=${ix}&py=${iy}`).then(r=>r.json());
  if (res.ok) {
    addPxMode = false;
    document.getElementById('no-img').style.display = 'none';
    canvasWrap.style.cursor = 'crosshair';
    await loadProjections();
  }"""

NEW = """  // Save pixel — pass new=1 if this is a brand-new landmark
  const newFlag = addPxIsNew ? '&new=1' : '';
  const res = await fetch(`/api/add_pixel?cam=${encodeURIComponent(currentCam)}&lm=${encodeURIComponent(addPxSelectedLm)}&px=${ix}&py=${iy}${newFlag}`).then(r=>r.json());
  if (res.ok) {
    addPxMode = false;
    addPxIsNew = false;
    document.getElementById('no-img').style.display = 'none';
    canvasWrap.style.cursor = 'crosshair';
    await loadProjections();
  }"""

if OLD not in src:
    print("✗ Could not find target block in calib_fresh.html")
    print("  Maybe already patched, or content has changed.")
    sys.exit(1)

new_src = src.replace(OLD, NEW)

print("Plan:")
print("  - In canvasWrap click handler (line ~1094):")
print("    Add &new=1 to /api/add_pixel call when addPxIsNew is true")
print("    Reset addPxIsNew flag after success")
print(f"  - Backup: {BACKUP_PATH}")

if not args.apply:
    print("\n(dry run — re-run with --apply to write changes)")
    sys.exit(0)

shutil.copy(HTML_PATH, BACKUP_PATH)
print(f"\n✓ Backup: {BACKUP_PATH}")

with open(HTML_PATH, 'w') as f:
    f.write(new_src)
print(f"✓ Updated: {HTML_PATH}")

print("\nRefresh your browser. Now:")
print("  1. Click + Add")
print("  2. Type a name that doesn't exist yet (e.g. 'WDNA Tower (Mid)')")
print("  3. Click 'Create new: ...' option")
print("  4. Click on the canvas to place the pixel")
print("  → It will now create the landmark in landmarks.json properly.")
print(f"\nRevert with: cp {BACKUP_PATH} {HTML_PATH}")
