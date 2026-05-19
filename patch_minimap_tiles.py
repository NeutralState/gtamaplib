"""
Phase 3b — replace _render_minimap_for_cam to use rlx tiles instead of yanis.jpg.

Strategy:
- Same signature, same output path, same disk cache. Client code is unchanged.
- Compute area in world meters around cam (radius 350m).
- Pick tile zoom level that gives the best resolution for 700m → 480px PNG.
  Tile zoom 5 has mppx ≈ 1.0 m/px, so 700m ≈ 700px. Perfect for resize to 480.
  Tile zoom 6 has mppx ≈ 0.5 m/px, so 700m ≈ 1400px — also fine, just more tiles.
  We use zoom 5 for speed (covers area with ~4-9 tiles vs ~16-25 at zoom 6).
- Load needed tiles from vendor/gtadb.org/maps/tiles/6/yanis,12/{z}/{z},{y},{x}.jpg
- Composite into a PIL Image at native tile resolution
- Crop to exactly the requested world area
- Resize to 480×480 LANCZOS
- Save PNG (overwrites old yanis-cropped cache)
- Existing yanis-based cached minimaps are invalidated by deleting them
  (they'll re-render from tiles on next access).

Idempotent: marker comment in the patched function makes re-runs no-op.
"""

import os
import sys

SERVER_PATH = os.path.expanduser('~/Downloads/gtamaplib-main/tools/server.py')
BAK_PATH = SERVER_PATH + '.bak_minimap_tiles'

with open(SERVER_PATH) as f:
    c = f.read()

if '[MINIMAP-TILES-V1]' in c:
    print('Already patched — skipping.')
    sys.exit(0)

with open(BAK_PATH, 'w') as f:
    f.write(c)
print(f'Backup: {BAK_PATH}')

# Locate the existing _render_minimap_for_cam function and replace it.
old_func = '''def _render_minimap_for_cam(cam_name):
    # Render and cache a minimap for one cam. Returns the output path
    # or None on error.
    try:
        cam = ml.get_camera(cam_name)
    except Exception:
        return None
    if cam.xyz is None:
        return None
    cx, cy = float(cam.xyz[0]), float(cam.xyz[1])
    area = (cx - _MINIMAP_RADIUS_M, cy - _MINIMAP_RADIUS_M,
            cx + _MINIMAP_RADIUS_M, cy + _MINIMAP_RADIUS_M)
    try:
        m = ml.get_map('yanis')
        m.open(add_padding=False)  # native scale
        cropped = m.crop(area)
        cropped = cropped.resize((_MINIMAP_SIZE_PX, _MINIMAP_SIZE_PX), 1)  # 1=LANCZOS
        out_path = _minimap_cache_path(cam_name)
        cropped.save(out_path, format='PNG', optimize=True)
        return out_path
    except Exception:
        import traceback as _tb
        _tb.print_exc()
        return None'''

new_func = '''def _render_minimap_for_cam(cam_name):
    # [MINIMAP-TILES-V1] Render a minimap PNG by compositing rlx tiles
    # (vendor/gtadb.org/maps/tiles/6/yanis,12/). Replaces the previous
    # yanis.jpg-based crop. Same signature, same output path — client
    # code is unaffected.
    #
    # Tile coord system (verbatim from rlx ui/map.js):
    #   MAP_W = 32768, ZERO_X = ZERO_Y = 16384, TILE_SIZE = 256.
    #   World y INCREASES going north; tile pixel y INCREASES going south.
    #   At zoom z, map size in tile pixels = 1024 * 2^z, so
    #     m/pixel = MAP_W / (1024 * 2^z) = 32 / 2^z
    #   z=4 → 2.0 m/px (350m radius = 350px), z=5 → 1.0 m/px (700px),
    #   z=6 → 0.5 m/px (1400px).
    try:
        cam = ml.get_camera(cam_name)
    except Exception:
        return None
    if cam.xyz is None:
        return None

    cx, cy = float(cam.xyz[0]), float(cam.xyz[1])
    radius = _MINIMAP_RADIUS_M

    # Pick zoom level: smallest z whose tile pixels-per-radius >= target.
    # We want at least _MINIMAP_SIZE_PX of source pixels in the radius window
    # so the resize-down doesn't blur. With z=5: 700 source px for 480 target → good.
    TILE_MAP_W = 32768
    TILE_ZERO_X = 16384
    TILE_ZERO_Y = 16384
    TILE_SIZE = 256
    TILE_RANGES = {
        0: [[0, 0], [2, 2]],
        1: [[0, 1], [4, 5]],
        2: [[0, 2], [9, 11]],
        3: [[0, 4], [19, 23]],
        4: [[0, 8], [38, 47]],
        5: [[0, 17], [77, 95]],
        6: [[0, 34], [155, 190]],
    }
    z = 5  # tuned for radius=350m, output 480px (see docstring above)
    mppx = TILE_MAP_W / (1024 * (2 ** z))   # m per tile pixel at zoom z
    # World → tile pixel coords (full pyramid pixel space at zoom z).
    def world_to_tile_px(wx, wy):
        return ((wx + TILE_ZERO_X) / mppx, (TILE_ZERO_Y - wy) / mppx)

    cpx, cpy = world_to_tile_px(cx, cy)
    half_w_px = radius / mppx
    left_px   = cpx - half_w_px
    right_px  = cpx + half_w_px
    top_px    = cpy - half_w_px  # world y north → tile y small
    bottom_px = cpy + half_w_px

    # Which tiles are needed.
    tx_min = int(left_px   // TILE_SIZE)
    tx_max = int((right_px - 1) // TILE_SIZE) if right_px > left_px else tx_min
    ty_min = int(top_px    // TILE_SIZE)
    ty_max = int((bottom_px - 1) // TILE_SIZE) if bottom_px > top_px else ty_min

    [[x0, y0], [x1, y1]] = TILE_RANGES[z]

    try:
        from PIL import Image
    except ImportError:
        return None

    tile_dir = TILES_DIR
    composite_w = (tx_max - tx_min + 1) * TILE_SIZE
    composite_h = (ty_max - ty_min + 1) * TILE_SIZE
    if composite_w <= 0 or composite_h <= 0:
        return None
    composite = Image.new('RGB', (composite_w, composite_h), (10, 10, 12))

    for ty in range(ty_min, ty_max + 1):
        for tx in range(tx_min, tx_max + 1):
            if tx < x0 or tx > x1 or ty < y0 or ty > y1:
                continue  # ocean / out of range → leave background color
            tile_path = os.path.join(tile_dir, str(z), f'{z},{ty},{tx}.jpg')
            if not os.path.exists(tile_path):
                continue
            try:
                tile_img = Image.open(tile_path).convert('RGB')
            except Exception:
                continue
            paste_x = (tx - tx_min) * TILE_SIZE
            paste_y = (ty - ty_min) * TILE_SIZE
            composite.paste(tile_img, (paste_x, paste_y))

    # Crop the composite to the exact radius window.
    crop_left   = int(left_px  - tx_min * TILE_SIZE)
    crop_top    = int(top_px   - ty_min * TILE_SIZE)
    crop_right  = int(right_px - tx_min * TILE_SIZE)
    crop_bottom = int(bottom_px - ty_min * TILE_SIZE)
    # Guard against off-by-one beyond composite size.
    crop_left   = max(0, min(composite_w, crop_left))
    crop_top    = max(0, min(composite_h, crop_top))
    crop_right  = max(crop_left + 1, min(composite_w, crop_right))
    crop_bottom = max(crop_top  + 1, min(composite_h, crop_bottom))

    try:
        cropped = composite.crop((crop_left, crop_top, crop_right, crop_bottom))
        cropped = cropped.resize((_MINIMAP_SIZE_PX, _MINIMAP_SIZE_PX), Image.LANCZOS)
        out_path = _minimap_cache_path(cam_name)
        cropped.save(out_path, format='PNG', optimize=True)
        return out_path
    except Exception:
        import traceback as _tb
        _tb.print_exc()
        return None'''

if old_func not in c:
    print('ERROR: old function signature not found exactly')
    sys.exit(1)

c = c.replace(old_func, new_func, 1)

with open(SERVER_PATH, 'w') as f:
    f.write(c)
print('Patched _render_minimap_for_cam → now uses tiles.')

# Invalidate existing cache so minimaps re-render with tiles.
cache_dir = os.path.expanduser('~/Downloads/gtamaplib-main/tools/generated/minimaps')
if os.path.isdir(cache_dir):
    removed = 0
    for f_name in os.listdir(cache_dir):
        if f_name.endswith('.png'):
            try:
                os.unlink(os.path.join(cache_dir, f_name))
                removed += 1
            except OSError:
                pass
    print(f'Invalidated {removed} cached minimaps — will re-render on next access')
