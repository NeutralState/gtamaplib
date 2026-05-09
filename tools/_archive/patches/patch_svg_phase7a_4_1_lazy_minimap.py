#!/usr/bin/env python3
"""
patch_svg_phase7a_4_1_lazy_minimap.py — drop startup pre-render, render on demand

Phase 7a.4 added a startup pre-render of all 147 minimaps (~3-5s expected,
in practice 30-60s per cam due to PIL re-opening the 56MB native PNG on
every iteration — the actual run was on track for 1-2 hours).

Pivot: drop the startup block entirely. Keep the /api/minimap endpoint
(restored in Phase 7a.4 HUNK 2) but rely on its on-demand render path
that's already there:

    if not os.path.exists(cache_path):
        # Render on demand (fallback for any cam added after startup).
        try:
            _render_minimap_for_cam(cam_name)
        except Exception:
            pass

So the first cam hit takes ~1-2s (one map open + crop + resize + save),
subsequent hits are instant from disk cache. Across a session, the
~147 cams get rendered as the user clicks through them — no upfront
wait.

The 77 minimaps Phase 7a.4 already cached on disk before being killed
are kept (the cache dir is at tools/generated/minimaps/). Future cam
selections of those 77 are instant.

Idempotent. Builds on Phase 7a.4.
Removes: the entire `# ── Phase 7a.4: pre-render minimaps at startup ──`
block (everything from the marker comment through the
`del _t_start_minimaps, _t7a4` line).
Keeps: the `_minimap_safe_name`, `_minimap_cache_path`,
`_render_minimap_for_cam` helpers + the `_MINIMAP_*` constants
(needed by the endpoint).
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_PY = os.path.join(THIS_DIR, 'server.py')
BACKUP = SERVER_PY + '.bak_svg_phase7a_4_1'

SENTINEL = '# Phase 7a.4.1: lazy minimap render (drop startup pre-render block)'
PHASE7A_4_SENTINEL = '# Phase 7a.4: pre-rendered minimaps at startup'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — drop ONLY the startup loop. Keep the helper functions and
# constants (used by the endpoint).
#
# Anchor: from the `import time as _t7a4` line through the closing
# `del _t_start_minimaps, _t7a4` line. Helpers stay.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
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
del _t_start_minimaps, _t7a4"""

HUNK_1_NEW = """\
# Phase 7a.4.1: lazy minimap render (drop startup pre-render block)
# Helpers stay; the startup loop is removed. The endpoint renders on
# demand the first time a cam is requested, then serves from disk
# cache forever after. First-cam hit: ~1-2s. Subsequent: instant.
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
        return None"""


HUNKS = [
    ('SERVER — drop startup pre-render block (keep helpers)', HUNK_1_OLD, HUNK_1_NEW),
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

    if PHASE7A_4_SENTINEL not in src:
        print('ERROR: Phase 7a.4 sentinel not found. Apply Phase 7a.4 first.')
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
    print('Server starts instantly now. First cam click hits the')
    print('on-demand render (~1-2s), subsequent clicks instant from cache.')
    print()
    print('Phase 7a.5 (next) wires the frontend to fetch /api/minimap.')


if __name__ == '__main__':
    main()
