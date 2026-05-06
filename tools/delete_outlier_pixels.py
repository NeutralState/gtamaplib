#!/usr/bin/env python3
"""delete_outlier_pixels.py — Delete pixels listed in /tmp/outlier_pixels.json.
Run AFTER reviewing the output of find_outlier_pixels.py.

Usage:
    python3 tools/delete_outlier_pixels.py        # dry run
    python3 tools/delete_outlier_pixels.py --apply
"""
import argparse, json, os, sys, shutil

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIXELS_PATH = os.path.join(GTAMAP_DIR, 'gtamapdata', 'pixels.json')

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

with open('/tmp/outlier_pixels.json') as f:
    outliers = json.load(f)

with open(PIXELS_PATH) as f:
    pixels = json.load(f)

print(f"Will delete {len(outliers)} pixels:")
for o in outliers:
    cam = o['cam']
    lm = o['lm']
    if cam in pixels and lm in pixels[cam]:
        print(f"  {o['err']:>5.1f}'  {cam} -> {lm}")
    else:
        print(f"  ALREADY GONE: {cam} -> {lm}")

if not args.apply:
    print("\n(dry run — re-run with --apply to delete)")
    sys.exit(0)

shutil.copy(PIXELS_PATH, PIXELS_PATH + '.bak_outlier_delete')
print(f"\nBackup: {PIXELS_PATH}.bak_outlier_delete")

deleted = 0
for o in outliers:
    cam = o['cam']
    lm = o['lm']
    if cam in pixels and lm in pixels[cam]:
        del pixels[cam][lm]
        deleted += 1

with open(PIXELS_PATH, 'w') as f:
    json.dump(pixels, f, indent=2)

print(f"Deleted {deleted} pixels.")
