#!/usr/bin/env python3
"""
gen_missing_thumbs.py — Generate thumbnails for any calibrated cam that has
a matching frame PNG but no thumb JPG yet.

Discovers cams from gtamapdata/cameras.json (only those with xyz).
Looks for frames/{cam_name}.png. Saves docs/thumbs/{cam_name}.jpg at 320x180.

Run from repo root:
    python3 tools/gen_missing_thumbs.py
"""
import os
import json
from pathlib import Path
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
FRAMES = REPO / 'frames'
THUMBS = REPO / 'docs' / 'thumbs'
CAMERAS = REPO / 'gtamapdata' / 'cameras.json'

# Optional: rename map for cams whose frame filename differs from cam_name.
# Format: cam_name (in cameras.json) -> frame filename (without .png).
# Most cams: frame filename == cam_name, so they auto-match.
RENAME_TO_FRAME = {
    # Existing weird mappings (preserved from gen_all_thumbs.py):
    'Motorboats (A)': 'Motorboats (B)',  # (A) frame doesn't exist, use (B)
}

# Optional: cams to thumb under a different filename in docs/thumbs/
# (most cams: thumb filename == cam_name)
RENAME_THUMB = {}


def main():
    cams = json.loads(CAMERAS.read_text())

    THUMBS.mkdir(exist_ok=True)

    candidates = [n for n, c in cams.items() if c.get('xyz')]
    print(f"Cams with xyz: {len(candidates)}")

    generated = 0
    skipped = 0
    no_frame = []

    for cam_name in candidates:
        frame_name = RENAME_TO_FRAME.get(cam_name, cam_name)
        thumb_name = RENAME_THUMB.get(cam_name, cam_name)

        frame_path = FRAMES / f'{frame_name}.png'
        thumb_path = THUMBS / f'{thumb_name}.jpg'

        if not frame_path.exists():
            no_frame.append(cam_name)
            continue

        if thumb_path.exists():
            skipped += 1
            continue

        img = Image.open(frame_path)
        img.thumbnail((320, 180))
        img.convert('RGB').save(thumb_path, 'JPEG', quality=75)
        size_kb = thumb_path.stat().st_size // 1024
        print(f"  Generated: {thumb_name}.jpg ({size_kb}KB)")
        generated += 1

    print(f"\nDone:")
    print(f"  Generated: {generated}")
    print(f"  Skipped (already exists): {skipped}")
    print(f"  No frame PNG: {len(no_frame)}")
    if no_frame and len(no_frame) <= 30:
        print(f"\nCams without frame PNG:")
        for n in no_frame:
            print(f"  - {n}")


if __name__ == '__main__':
    main()
