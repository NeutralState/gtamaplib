#!/usr/bin/env python3
"""
prerender_minimaps_fast.py — bulk pre-render all missing minimaps.

The lazy on-demand render in server.py (_render_minimap_for_cam) calls
m.open() each time, which reloads the 56 MB PNG from disk. For a single
click that's fine (~1-2s). For 147 cams in bulk, that's 5+ minutes of
disk I/O alone.

This script opens the source PNG ONCE and reuses the in-memory image
for every cam crop. Total: ~30-60 seconds for 147 cams.

Usage:
  python3 tools/prerender_minimaps_fast.py
"""

import os, sys, time
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import gtamaplib as ml
import gtamapdata as md

# Constants matching server.py's lazy renderer
_MINIMAP_CACHE_DIR = os.path.join(REPO, 'tools', 'generated', 'minimaps')
_MINIMAP_RADIUS_M = 350.0
_MINIMAP_SIZE_PX = 480

os.makedirs(_MINIMAP_CACHE_DIR, exist_ok=True)


def _safe_name(cam_name):
    return ''.join(c if c.isalnum() else '_' for c in cam_name)


def _cache_path(cam_name):
    return os.path.join(_MINIMAP_CACHE_DIR, f'{_safe_name(cam_name)}.png')


def main():
    Image.MAX_IMAGE_PIXELS = None  # 56MB / 20000x20000 PNG

    # Find which cams need rendering
    todo = []
    skipped = 0
    for cam_name, cam_data in md.cameras.items():
        if not cam_data.get('xyz'):
            continue
        if os.path.exists(_cache_path(cam_name)):
            skipped += 1
            continue
        todo.append(cam_name)

    print(f'Cached: {skipped}')
    print(f'To render: {len(todo)}')
    print()

    if not todo:
        print('Nothing to do.')
        return

    # Open the source map ONCE
    print(f'Loading source map (~5-10s)...')
    t0 = time.time()
    m = ml.get_map('yanis')
    m.open(add_padding=False)  # native scale, same as server.py
    print(f'  loaded in {time.time()-t0:.1f}s')
    print()

    # Render all
    print('Rendering minimaps...')
    started = time.time()
    ok = err = 0
    for i, cam_name in enumerate(todo, 1):
        try:
            cam = ml.get_camera(cam_name)
            cx, cy = float(cam.xyz[0]), float(cam.xyz[1])
            area = (cx - _MINIMAP_RADIUS_M, cy - _MINIMAP_RADIUS_M,
                    cx + _MINIMAP_RADIUS_M, cy + _MINIMAP_RADIUS_M)
            cropped = m.crop(area)
            cropped = cropped.resize((_MINIMAP_SIZE_PX, _MINIMAP_SIZE_PX), 1)
            cropped.save(_cache_path(cam_name), format='PNG', optimize=True)
            ok += 1
            if i % 10 == 0 or i == len(todo):
                elapsed = time.time() - started
                rate = i / elapsed
                eta = (len(todo) - i) / rate if rate > 0 else 0
                print(f'  [{i}/{len(todo)}] ok={ok} err={err} · '
                      f'{rate:.1f} cam/s · ETA {eta:.0f}s')
        except Exception as e:
            err += 1
            print(f'  ERR {cam_name}: {e}')

    print()
    print(f'Done in {time.time()-started:.1f}s. ok={ok}, err={err}')
    print(f'Cache now at {len(os.listdir(_MINIMAP_CACHE_DIR))} files.')


if __name__ == '__main__':
    main()
