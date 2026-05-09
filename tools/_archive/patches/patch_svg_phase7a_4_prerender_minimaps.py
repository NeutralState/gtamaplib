#!/usr/bin/env python3
"""
patch_svg_phase7a_4_prerender_minimaps.py — pre-render minimaps at startup

Pivot: Phase 7a.1's CSS-only minimap (background-image crop of the 12K
PNG) hits a Safari slow path on macOS — 30-60s before the minimap
renders, even though the underlying PNG loads in <50ms. Switching the
inner element to a real <img> + CSS transform (Phase 7a.1.2) didn't
help; Safari's image-decode pipeline stalls on any large-PNG
manipulation when the visible target is tiny.

Solution: pre-render small per-cam minimap PNGs at server startup,
cache them on disk, serve as static files via a restored /api/minimap
endpoint. Server-side renders are fast (~15ms each at native scale,
small crop), and serving a 50KB PNG to the browser is instant.

Trade-off: server startup gains ~3-5s for ~250 cams. One-time cost,
acceptable for a dev tool.

Architecture:
  - At module load (top of server.py), iterate `md.cameras`, render each
    cam's minimap to `tools/generated/minimaps/<safe_name>.png`. Skip
    if the file already exists and is newer than the cameras.json
    mtime (so restarts are fast — only re-render when data changes).
  - Restore the `/api/minimap` endpoint (Phase 7a.3 dropped it). New
    version is much simpler: just serve the cached PNG file. Returns
    `{cam, image_b64, yaw, ...}` shape so the next patch can re-wire
    the frontend to use it.
  - Phase 7a.5 (next) will revert Phase 7a.1.2 + the CSS-only part of
    Phase 7a.1 to fetch this endpoint instead.

Idempotent. Builds on Phase 7a.3.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_PY = os.path.join(THIS_DIR, 'server.py')
BACKUP = SERVER_PY + '.bak_svg_phase7a_4'

SENTINEL = '# Phase 7a.4: pre-rendered minimaps at startup'
PHASE7A_3_SENTINEL = '# Phase 7a.3: /api/minimap + /api/generate_map + /api/generated_map removed'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — top-level: add the pre-render block after the leak-cams setup.
# Anchor: the existing leak-cams print line.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
print(f"Leak cams: {len(LEAK_CAMS)} · Leak-anchored landmarks: {len(LEAK_ANCHORED_LMS)}")


# ── Item 4 : "Other cams" overlay (canvas-based, no image rendering) ─────────"""

HUNK_1_NEW = """\
print(f"Leak cams: {len(LEAK_CAMS)} · Leak-anchored landmarks: {len(LEAK_ANCHORED_LMS)}")


# ── Phase 7a.4: pre-render minimaps at startup ──────────────────────────────
# Phase 7a.4: pre-rendered minimaps at startup
# Renders one tiny PNG per cam (~480×480) into tools/generated/minimaps/.
# Caches on disk. Re-renders only when cameras.json is newer than the
# cached PNG (so server restarts are fast). The /api/minimap endpoint
# (restored below in HUNK 2) serves these cached files.
import time as _t7a4
_t_start_minimaps = _t7a4.time()
_MINIMAP_CACHE_DIR = os.path.join(TOOL_DIR, 'generated', 'minimaps')
os.makedirs(_MINIMAP_CACHE_DIR, exist_ok=True)
_MINIMAP_RADIUS_M = 350.0
_MINIMAP_SIZE_PX = 480

def _minimap_safe_name(cam_name):
    return ''.join(c if c.isalnum() else '_' for c in cam_name)

def _minimap_cache_path(cam_name):
    return os.path.join(_MINIMAP_CACHE_DIR, f'{_minimap_safe_name(cam_name)}.png')

def _render_minimap_for_cam(cam_name):
    # Render and cache a minimap for one cam. Returns the output path
    # or None on error. Caller checks freshness before calling.
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
        return None

# Decide which cams need (re-)rendering. We compare the cached PNG's
# mtime to the cameras.json mtime — if cameras.json changed, all cached
# PNGs are stale.
_cameras_json = os.path.join(DATA_DIR, 'cameras.json')
_cameras_mtime = os.path.getmtime(_cameras_json) if os.path.exists(_cameras_json) else 0
_to_render = []
for _cam_name, _cam_data in md.cameras.items():
    if _cam_data.get('xyz') is None:
        continue
    _path = _minimap_cache_path(_cam_name)
    if not os.path.exists(_path):
        _to_render.append(_cam_name)
    elif os.path.getmtime(_path) < _cameras_mtime:
        _to_render.append(_cam_name)
if _to_render:
    print(f"Pre-rendering {len(_to_render)} minimaps...")
    # Parallel render — minimap render is mostly PIL crop+resize, which
    # is GIL-bound but I/O-light. ThreadPoolExecutor with 4 workers gives
    # ~2x speedup on macOS for our workload.
    from concurrent.futures import ThreadPoolExecutor as _Pool
    with _Pool(max_workers=4) as _pool:
        list(_pool.map(_render_minimap_for_cam, _to_render))
    print(f"  ...done ({_t7a4.time() - _t_start_minimaps:.1f}s)")
else:
    print("Minimaps cached, skipping re-render.")
del _t_start_minimaps, _t7a4


# ── Item 4 : "Other cams" overlay (canvas-based, no image rendering) ─────────"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — restore the /api/minimap endpoint (much simpler now: serve
# cached PNG). Anchor: the Phase 7a.3 sentinel comment block (which we
# preserve, just replace the surrounding context).
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
        # Phase 7a.3: /api/minimap removed. The minimap is now CSS-only
        # in the frontend (Phase 7a.1) — a background-image crop of
        # the cached /yanis.png.

        elif path == '/api/other_cams_overlay':"""

HUNK_2_NEW = """\
        # Phase 7a.3: /api/minimap removed (CSS-only) — Phase 7a.4 restores
        # it as a static file server for pre-rendered cached PNGs.
        # The Safari slow-path on huge PNG bg-image manipulation forced
        # the pivot back to server-rendered minimaps. See module-top
        # pre-render block.

        elif path == '/api/minimap':
            cam_name = unquote(qs.get('cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400)
                return
            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return
            cache_path = _minimap_cache_path(cam_name)
            if not os.path.exists(cache_path):
                # Render on demand (fallback for any cam added after startup).
                try:
                    _render_minimap_for_cam(cam_name)
                except Exception:
                    pass
            if not os.path.exists(cache_path):
                self.send_json({'error': 'minimap render failed'}, 500)
                return
            try:
                with open(cache_path, 'rb') as f:
                    img_bytes = f.read()
                import base64 as _b64
                img_b64 = _b64.b64encode(img_bytes).decode('ascii')
                self.send_json({
                    'cam': cam_name,
                    'image_b64': img_b64,
                    'yaw': float(cam.ypr[0]) if cam.ypr is not None else 0.0,
                    'radius_m': _MINIMAP_RADIUS_M,
                    'image_size_px': _MINIMAP_SIZE_PX,
                })
            except Exception as e:
                self.send_json({'error': f'minimap read failed: {e}'}, 500)

        elif path == '/api/other_cams_overlay':"""


HUNKS = [
    ('SERVER — pre-render minimaps block at module load', HUNK_1_OLD, HUNK_1_NEW),
    ('SERVER — restore /api/minimap as cache server',     HUNK_2_OLD, HUNK_2_NEW),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--revert', action='store_true')
    args = ap.parse_args()

    if not os.path.exists(SERVER_PY):
        print(f'ERROR: {SERVER_PY} not found.')
        sys.exit(1)

    if args.revert:
        if not os.path.exists(BACKUP):
            print(f'ERROR: no backup at {BACKUP}.')
            sys.exit(1)
        if args.apply:
            shutil.copy(BACKUP, SERVER_PY)
            print(f'✓ Restored {SERVER_PY} from {BACKUP}.')
        else:
            print(f'(dry-run) would restore from {BACKUP}.')
        return

    with open(SERVER_PY, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print('✓ Already patched.')
        return

    if PHASE7A_3_SENTINEL not in src:
        print('ERROR: Phase 7a.3 sentinel not found. Apply Phase 7a.3 first.')
        sys.exit(1)

    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} times (need exactly 1).')
            sys.exit(1)

    new_src = src
    for _label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    delta = new_src.count('\n') - src.count('\n')
    print(f'Will modify {SERVER_PY} ({delta:+d} lines)')
    print(f'  hunks applied: {len(HUNKS)}')

    if not args.apply:
        print('\n(dry-run — re-run with --apply)')
        return

    shutil.copy(SERVER_PY, BACKUP)
    print(f'\n✓ Backup: {BACKUP}')
    tmp = SERVER_PY + '.tmp'
    with open(tmp, 'w') as f:
        f.write(new_src)
    os.replace(tmp, SERVER_PY)
    print(f'✓ Patched {SERVER_PY}')
    print()
    print('Restart server:')
    print('  lsof -ti:8765 | xargs kill -9 ; python3 tools/server.py')
    print()
    print('Expected: ~3-5s "Pre-rendering N minimaps..." on first start;')
    print('         "Minimaps cached, skipping re-render." on subsequent starts.')
    print()
    print('Phase 7a.5 (next) will rewire the frontend to fetch /api/minimap.')


if __name__ == '__main__':
    main()
