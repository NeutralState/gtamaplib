#!/usr/bin/env python3
"""
gtamaplib Calibration Tool — server.py
Run: python3 server.py
Open: http://localhost:8765
"""

import json
import math
import threading
import os
import re
import sys
# Threading fix: parallel request handling
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # [EDIT-MODE-V1] portable (was hardcoded ~/Downloads/gtamaplib-main)
DATA_DIR = os.path.join(GTAMAP_DIR, "gtamapdata")
FRAMES_DIR = os.path.join(GTAMAP_DIR, "frames")
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TOOL_DIR)
# [TILES-V1] gtadb.org tile checkout (sparse, vendored, gitignored).
# Tiles are 256x256 JPGs at /vendor/gtadb.org/maps/tiles/6/yanis,13/{z}/{z},{y},{x}.jpg
# 7 zoom levels (0-6). Served via /tiles/{z}/{filename} route.
TILES_DIR = os.path.join(REPO_ROOT, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,13')

sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

# [GETCAM-THREADSAFE-V1] ml.get_camera is functools.lru_cache — NOT thread-safe.
# The server is a ThreadingHTTPServer and many endpoints (minimap, project,
# save, etc.) call get_camera concurrently, while some call cache_clear().
# Under contention the lru_cache returns the WRONG cam's object (proven: a cam
# served another cam's byte-identical minimap). Wrap it once, here, so EVERY
# call site is serialized behind a single reentrant lock. cache_clear/cache_info
# are preserved for the code that uses them.
import threading as _threading
_GETCAM_LOCK = _threading.RLock()
_ml_get_camera_orig = ml.get_camera
def _get_camera_locked(*a, **k):
    with _GETCAM_LOCK:
        return _ml_get_camera_orig(*a, **k)
_get_camera_locked.cache_clear = _ml_get_camera_orig.cache_clear
_get_camera_locked.cache_info = _ml_get_camera_orig.cache_info
ml.get_camera = _get_camera_locked


print("gtamaplib loaded ✓")

# V2: audit-driven sets replace V1's date-regex LEAK_CAMS.
# - LOCKED_XYZ_CAMS: cams whose xyz is HUD-locked (classes A/B/C/Cm and
#   legacy date-source cams without an audit entry). Their triangulating
#   rays are treated as ground truth.
# - XYZ_ANCHORED_LMS: landmarks triangulated from 2+ HUD-locked-xyz cams.
#   Their positions are considered ground truth.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from leak_cam_audit import (
    get_class as _audit_get_class,
    is_triangulation_trusted as _audit_xyz_trusted,
    legacy_cam_names as _audit_legacy_names,
)

LOCKED_XYZ_CAMS = {n for n in md.cameras if _audit_xyz_trusted(n, cameras=md.cameras)}
XYZ_ANCHORED_LMS = {
    lm for lm, meta in md.landmarks_meta.items()
    if md.landmarks.get(lm) is not None
    and len([c for c in meta.get('source_cameras', []) if c in LOCKED_XYZ_CAMS]) >= 2
}

# Back-compat aliases — many downstream callsites still use the V1 names.
# These will be removed once all callers have migrated.
LEAK_CAMS = LOCKED_XYZ_CAMS
LEAK_ANCHORED_LMS = XYZ_ANCHORED_LMS

_legacy_cams = _audit_legacy_names(md.cameras)
print(f"Cams with HUD-locked xyz: {len(LOCKED_XYZ_CAMS)} · "
      f"xyz-anchored landmarks: {len(XYZ_ANCHORED_LMS)}")
if _legacy_cams:
    print(f"  (Includes {len(_legacy_cams)} legacy date-source cam(s) without "
          f"audit entry: {', '.join(_legacy_cams)})")


# ── Phase 7a.4: pre-render minimaps at startup ──────────────────────────────
# Phase 7a.4: pre-rendered minimaps at startup
# Renders one tiny PNG per cam (~480×480) into tools/generated/minimaps/.
# Caches on disk. Re-renders only when cameras.json is newer than the
# cached PNG (so server restarts are fast). The /api/minimap endpoint
# (restored below in HUNK 2) serves these cached files.
# Phase 7a.4.1: lazy minimap render (drop startup pre-render block)
# Helpers stay; the startup loop is removed. The endpoint renders on
# demand the first time a cam is requested, then serves from disk
# cache forever after. First-cam hit: ~1-2s. Subsequent: instant.
_MINIMAP_CACHE_DIR = os.path.join(TOOL_DIR, 'generated', 'minimaps')
# [MINIMAP-THREADLOCK-V1] ml.get_camera is @lru_cache — NOT thread-safe.
# ThreadingHTTPServer runs /api/minimap concurrently, so parallel calls
# corrupted the lru_cache and returned another cam's camera object, making
# _minimap_cache_path point at the WRONG file — a cam served another cam's
# exact image+yaw. Serialize the whole minimap endpoint behind one lock.
_MINIMAP_LOCK = threading.Lock()
os.makedirs(_MINIMAP_CACHE_DIR, exist_ok=True)
_MINIMAP_RADIUS_M = 600.0  # [MINIMAP-ZOOM-V3] 600m
_MINIMAP_SIZE_PX = 480

def _minimap_safe_name(cam_name):
    return ''.join(c if c.isalnum() else '_' for c in cam_name)

def _minimap_cache_path(cam_name):
    # [MINIMAP-CACHEKEY-V1] include position+yaw+radius in the filename so a
    # cam that moved (or the radius changing) can NEVER serve a stale/other
    # cam's cached crop — a different pose => a different file, period.
    try:
        cam = ml.get_camera(cam_name)
        if cam.xyz is not None:
            key = f'{cam.xyz[0]:.0f}_{cam.xyz[1]:.0f}_{float(cam.ypr[0]):.0f}_{int(_MINIMAP_RADIUS_M)}'
        else:
            key = 'noxyz'
    except Exception:
        key = 'err'
    return os.path.join(_MINIMAP_CACHE_DIR, f'{_minimap_safe_name(cam_name)}__{key}.png')

def _render_minimap_for_cam(cam_name):
    # [MINIMAP-TILES-V1] Render a minimap PNG by compositing rlx tiles
    # (vendor/gtadb.org/maps/tiles/6/yanis,13/). Replaces the previous
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
        return None


# ── Item 4 : "Other cams" overlay (canvas-based, no image rendering) ─────────

def _classify_cam(cam_name):
    """Returns 'leak' | 'trailer' | 'screenshot'.

    V2: 'leak' bucket now means "any cam whose xyz is HUD-locked" (classes
    A/B/C/Cm + legacy date-source). The bucket name is retained for
    back-compat with the dashboard CSS; the underlying check is audit-driven."""
    if _audit_xyz_trusted(cam_name, cameras=md.cameras):
        return 'leak'
    src = md.cameras.get(cam_name, {}).get('source', '') or ''
    if src.startswith('Trailer'): return 'trailer'
    return 'screenshot'

def _candidates_for(cam_name, types, max_dist, shared_only):
    """Returns list of (cam_name, dist_m) to overlay on cam_name."""
    cam_xyz = md.cameras.get(cam_name, {}).get('xyz')
    if not cam_xyz:
        return []
    cam_pixels = set(md.pixels.get(cam_name, {}).keys()) if shared_only else None

    out = []
    for other_name, other_data in md.cameras.items():
        if other_name == cam_name: continue
        if not other_data.get('xyz'): continue
        if _classify_cam(other_name) not in types: continue
        ox, oy, oz = other_data['xyz']
        cx, cy, cz = cam_xyz
        dist = ((ox-cx)**2 + (oy-cy)**2 + (oz-cz)**2) ** 0.5
        if dist > max_dist: continue
        if shared_only:
            other_pixels = set(md.pixels.get(other_name, {}).keys())
            if not (cam_pixels & other_pixels): continue
        out.append((other_name, dist))
    out.sort(key=lambda x: -x[1])  # furthest first so closer renders on top
    return out


def get_cam(cam_name, xyz=None, ypr=None, hfov=None):
    cam = ml.get_camera(cam_name)
    if xyz is not None:
        cam.set_xyz(xyz)
    if ypr is not None:
        cam.set_ypr(ypr)
    if hfov is not None:
        cam.set_fov((hfov, None))
    return cam


def compute_projections(cam_name, xyz=None, ypr=None, hfov=None):
    if cam_name not in md.cameras:
        return [], {}

    cam = get_cam(cam_name, xyz, ypr, hfov)
    cam_pixels = md.pixels.get(cam_name, {})
    result = []

    # [VIRTUAL-LMS-V1] Include virtual LMs (no marker, e.g. building wireframes)
    # for known prefixes. They get projected but no marked_pixel/delta.
    VIRTUAL_PREFIXES = ('Portofino Tower (',)
    virtual_lms_to_include = []
    for lm_name in md.landmarks:
        if lm_name in cam_pixels:
            continue
        if any(lm_name.startswith(p) for p in VIRTUAL_PREFIXES):
            virtual_lms_to_include.append(lm_name)

    for lm_name, marked_pixel in cam_pixels.items():
        lm_xyz = md.landmarks.get(lm_name)
        meta = md.landmarks_meta.get(lm_name, {})
        src = meta.get('source_cameras', [])
        err_m = meta.get('error_m')
        is_circular = cam_name in src

        proj = None
        delta = None

        if lm_xyz:
            try:
                proj = cam.get_pixel(lm_xyz)
                if proj is not None:
                    proj = [round(float(proj[0]), 2), round(float(proj[1]), 2)]
                    # Angular error in arcmin
                    dx = proj[0] - marked_pixel[0]
                    dy = proj[1] - marked_pixel[1]
                    deg_per_px_h = cam.hfov / cam.w
                    deg_per_px_v = cam.vfov / cam.h
                    delta = math.sqrt((dx * deg_per_px_h)**2 + (dy * deg_per_px_v)**2) * 60
                    if delta > 500:
                        delta = None
            except Exception:
                pass

        result.append({
            'name': lm_name,
            'marked_pixel': list(marked_pixel),
            'projected': proj,
            'delta': round(delta, 3) if delta is not None else None,
            'has_xyz': lm_xyz is not None,
            'is_circular': is_circular,
            'error_m': err_m,
        })

    # [VIRTUAL-LMS-V1] Add virtual LMs (no marker, only projection)
    for lm_name in virtual_lms_to_include:
        lm_xyz = md.landmarks.get(lm_name)
        proj = None
        if lm_xyz:
            try:
                p = cam.get_pixel(lm_xyz)
                if p is not None:
                    proj = [round(float(p[0]), 2), round(float(p[1]), 2)]
            except Exception:
                pass
        if proj is None:
            continue  # behind camera or projection failed
        result.append({
            'name': lm_name,
            'marked_pixel': None,
            'projected': proj,
            'delta': None,
            'has_xyz': True,
            'is_circular': False,
            'error_m': 0.0,
            'is_virtual': True,
        })

    all_d = [r['delta'] for r in result if r['delta'] is not None]
    indep_d = [r['delta'] for r in result if r['delta'] is not None and not r['is_circular']]

    losses = {
        'total': round(sum(all_d) / len(all_d), 3) if all_d else None,
        'independent': round(sum(indep_d) / len(indep_d), 3) if indep_d else None,
        'n_total': len(all_d),
        'n_independent': len(indep_d),
    }

    return result, losses


def pixel_error(cam, lm_xyz, mp):
    try:
        proj = cam.get_pixel(lm_xyz)
        if proj is None: return 1000.0
        dx = float(proj[0]) - mp[0]
        dy = float(proj[1]) - mp[1]
        return math.sqrt((dx * cam.hfov / cam.w)**2 + (dy * cam.vfov / cam.h)**2) * 60
    except Exception:
        return 1000.0


def optimize_camera(cam_name, xyz, ypr, hfov, leak_mode=False):
    """
    Refines a single camera's xyz + ypr + hfov using scipy.least_squares
    with the trust region reflective method and huber loss. Huber loss
    makes the optimization robust to outlier landmarks (mismarked pixels,
    name collisions, etc.) — these are no longer allowed to dominate
    the gradient and pull the calibration off-target.

    Uses ALL landmarks the camera has pixels for (both independent and
    self-source). Self-source landmarks are included with reduced weight
    since their position partially depends on the camera itself, but
    they still anchor the geometry.
    """
    try:
        from scipy.optimize import least_squares
        import numpy as np
    except ImportError:
        return None, "scipy not installed — run: pip3 install scipy"

    cam_pixels = md.pixels.get(cam_name, {})

    # ── TIER-WEIGHTS-V1 ──
    # Tier-based weights — each LM is weighted by how trustworthy its
    # position is. Unverified LMs are dropped (weight=0). Self-source
    # LMs get ×0.3 to preserve the anti-circular safeguard.
    TIER_WEIGHTS = {
        'anchor':     1.0,
        'high':       0.8,
        'medium':     0.4,
        'low':        0.1,
        'unverified': 0.0,
    }

    # Load tier data if available (graceful fallback if missing)
    _tiers_path = os.path.join(os.path.dirname(__file__), 'generated', 'confidence_tiers.json')
    try:
        with open(_tiers_path) as _f:
            _tier_data = json.load(_f)
        _lm_tiers = {n: (d.get('tier') if isinstance(d, dict) else d)
                     for n, d in _tier_data.get('landmarks', {}).items()}
    except Exception:
        _lm_tiers = {}

    # Build constraint set with tier-based weights
    constraints = []
    for lm, mp in cam_pixels.items():
        lm_xyz = md.landmarks.get(lm)
        if lm_xyz is None:
            continue
        is_self_source = cam_name in md.landmarks_meta.get(lm, {}).get('source_cameras', [])
        tier = _lm_tiers.get(lm, 'unverified')
        base_weight = TIER_WEIGHTS.get(tier, 0.0)
        if base_weight == 0.0:
            continue  # unverified LM — skip entirely
        weight = base_weight * (0.3 if is_self_source else 1.0)
        constraints.append((lm, list(lm_xyz), list(mp), weight, is_self_source))

    n_total = len(constraints)
    n_indep = sum(1 for _, _, _, w, sf in constraints if not sf)
    if n_indep < 3:
        return None, f"Not enough independent landmarks ({n_indep} — need at least 3)"

    # Loss before (RMS over indep only, for human-readable comparison)
    cam_before = get_cam(cam_name, xyz, ypr, hfov)
    indep_errs = [pixel_error(cam_before, c[1], c[2]) for c in constraints if not c[4]]
    loss_before = math.sqrt(sum(e*e for e in indep_errs) / max(1, len(indep_errs)))

    # V1-ROLL: x0 now has 7 params — xyz + yaw + pitch + roll + hfov
    x0 = np.array([xyz[0], xyz[1], xyz[2], ypr[0], ypr[1], ypr[2], hfov], dtype=float)

    # Residual function — returns vector of weighted angular errors (arcmin)
    def residuals(p):
        try:
            # V1-ROLL: roll is now p[5], hfov is p[6]
            cam = get_cam(cam_name, list(p[:3]), [p[3], p[4], p[5]], float(p[6]))
        except Exception:
            return np.full(2 * n_total, 1000.0)
        out = []
        for _, lm_xyz, mp, w, _ in constraints:
            try:
                proj = cam.get_pixel(lm_xyz)
                if proj is None:
                    out.append(500.0); out.append(500.0)
                    continue
                dx = (float(proj[0]) - mp[0]) * cam.hfov / cam.w * 60.0
                dy = (float(proj[1]) - mp[1]) * cam.vfov / cam.h * 60.0
                out.append(w * dx); out.append(w * dy)
            except Exception:
                out.append(500.0); out.append(500.0)
        return np.array(out, dtype=float)

    # Bounds: xyz ±300m, yaw ±90°, pitch ±60°, roll ±5°, hfov 20°-130°
    # V1-ROLL: roll bounded tightly to ±5° — physical camera tilt is rarely larger
    # ── PHYSICAL-BOUNDS-V1 ──
    # Absolute z clipping: never below -5m (sea level + tolerance) or
    # above 500m. This prevents under-constrained cams (e.g. 3 obs) from
    # finding solutions like z=-24m (submarine yacht).
    # LEAK-MODE-V1: when leak_mode=True, xyz + hfov are immutable (leak cams
    # have known positions and FOVs). Only yaw/pitch/roll can adjust.
    if leak_mode:
        eps = 1e-4
        lb = np.array([xyz[0]-eps, xyz[1]-eps, xyz[2]-eps,
                       ypr[0]-90, ypr[1]-60, ypr[2]-5.0, hfov-eps])
        ub = np.array([xyz[0]+eps, xyz[1]+eps, xyz[2]+eps,
                       ypr[0]+90, ypr[1]+60, ypr[2]+5.0, hfov+eps])
    else:
        lb = np.array([xyz[0]-300, xyz[1]-300, max(xyz[2]-50, -5.0),
                       ypr[0]-90, ypr[1]-60, ypr[2]-5.0, 20.0])
        ub = np.array([xyz[0]+300, xyz[1]+300, min(xyz[2]+50, 500.0),
                       ypr[0]+90, ypr[1]+60, ypr[2]+5.0, 130.0])

    try:
        result = least_squares(
            residuals, x0,
            method='trf',
            loss='huber',
            f_scale=10.0,        # huber transition at ~10 arcmin
            max_nfev=200,
            bounds=(lb, ub),
        )
    except Exception as e:
        return None, f"Optimization failed: {e}"

    # Loss after (RMS over indep only)
    # V1-ROLL: roll is at result.x[5], hfov at result.x[6]
    cam_after = get_cam(cam_name, list(result.x[:3]),
                         [result.x[3], result.x[4], result.x[5]],
                         float(result.x[6]))
    indep_errs_after = [pixel_error(cam_after, c[1], c[2]) for c in constraints if not c[4]]
    loss_after = math.sqrt(sum(e*e for e in indep_errs_after) / max(1, len(indep_errs_after)))

    improvement = round((loss_before - loss_after) / loss_before * 100, 1) if loss_before > 0 else 0

    return {
        'xyz': [round(float(v), 4) for v in result.x[:3]],
        # V1-ROLL: roll is now optimized (result.x[5]), hfov moved to result.x[6]
        'ypr': [round(float(result.x[3]), 4), round(float(result.x[4]), 4),
                round(float(result.x[5]), 4)],
        'hfov': round(float(result.x[6]), 4),
        'loss_before': round(loss_before, 4),
        'loss': round(loss_after, 4),
        'improvement_pct': improvement,
        'n_constraints': n_indep,
        'n_total': n_total,
        'success': bool(result.status > 0),
        'method': 'TRF+huber',
    }, None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, mime):
        with open(path, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path in ('/', '/index.html', '/calib.html'):
            self.send_file(os.path.join(TOOL_DIR, 'calib.html'), 'text/html')

        elif path.startswith('/thumbs/'):
            # Serve thumbnails from docs/thumbs/
            fname = unquote(path[len('/thumbs/'):])
            # Basic sanitization
            if '/' in fname or '\\' in fname or '..' in fname:
                self.send_response(400); self.end_headers(); return
            thumb_path = os.path.join(GTAMAP_DIR, 'docs', 'thumbs', fname)
            if os.path.exists(thumb_path):
                self.send_file(thumb_path, 'image/jpeg')
            else:
                self.send_response(404); self.end_headers()

        elif path == '/cam_health.html':
            self.send_file(os.path.join(TOOL_DIR, 'cam_health.html'), 'text/html')

        # [VIEW3D-V1] scene three.js plein ecran (page isolee, lien depuis topbar)
        elif path == '/view3d.html':
            self.send_file(os.path.join(TOOL_DIR, 'view3d.html'), 'text/html')

        elif path.startswith('/threejs/'):
            fname = unquote(path[len('/threejs/'):])
            if '/' in fname or '\\' in fname or '..' in fname:
                self.send_response(400); self.end_headers(); return
            fpath = os.path.join(TOOL_DIR, 'threejs', fname)  # tools/threejs: committable ('vendor/' du .gitignore matche a tous les niveaux)
            if os.path.exists(fpath):
                self.send_file(fpath, 'application/javascript')
            else:
                self.send_response(404); self.end_headers()

        # [TILES-V1] isolated test page for new tile-based map renderer.
        # Not linked from anywhere in the main UI — direct nav only.
        # [YANIS-CLEANUP-V2] map_view_v2 routes removed

        # [TILES-V1] isolated test page for new tile-based map renderer.
        # Not linked from anywhere in the main UI — direct nav only.
        # [YANIS-CLEANUP-V2] map_view_v2 routes removed

        # ── SVG Map Refactor (Phase 1) ─────────────────────────────
        # Two endpoints powering the new full-screen SVG map view.
        # See tools/CLAUDE_CONTEXT.md > "SVG Map View Refactor" for context.

        # [YANIS-CLEANUP-V2] /yanis.jpg endpoint removed

        elif path.startswith('/tiles/'):
            # [TILES-V1] Serve tile JPGs from vendor/gtadb.org/maps/tiles/6/yanis,13/
            # URL pattern: /tiles/{z}/{z},{y},{x}.jpg  (z=0..6)
            # Strict validation: only digits + commas + .jpg, no path traversal.
            tile_rel = path[len('/tiles/'):]  # e.g. "3/3,10,0.jpg"
            # Validate: must match exactly {z}/{z},{y},{x}.jpg with z 0-6
            m = re.match(r'^([0-6])/([0-6]),(\d+),(\d+)\.jpg$', tile_rel)
            if not m:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'invalid tile path')
                return
            z_dir, z_in, y, x = m.groups()
            if z_dir != z_in:
                # Defensive: filename z must match directory z
                self.send_response(404)
                self.end_headers()
                return
            tile_path = os.path.join(TILES_DIR, z_dir, f'{z_in},{y},{x}.jpg')
            if not os.path.exists(tile_path):
                self.send_response(404)
                self.end_headers()
                return
            with open(tile_path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', len(data))
            # Tiles are immutable content — aggressive cache.
            self.send_header('Cache-Control', 'public, max-age=31536000, immutable')
            self.end_headers()
            self.wfile.write(data)

        # [VIEW3D-V1] scene 3D: cams avec coins de frustum calcules par LA LIB
        # (get_pixel_direction aux 4 coins image — zero risque de convention
        # ypr cote JS), LMs, meshes proceduraux, bornes.
        elif path == '/api/scene3d':
            try:
                import json as _json
                from common import get_cam as _get_cam, cam_rms as _cam_rms
                from leak_cam_audit import is_triangulation_trusted as _itt
                with open(os.path.join(REPO_ROOT, 'tools', 'generated', 'confidence_tiers.json')) as _f:
                    _ct = _json.load(_f).get('cameras', {})
                cams3d = []
                for name, cd in md.cameras.items():
                    if not cd.get('xyz'):
                        continue
                    entry = {
                        'name': name, 'xyz': cd['xyz'],
                        'tier': (_ct.get(name) or {}).get('tier'),
                        'rms_arcmin': (lambda r: round(r, 2) if r is not None else None)(_cam_rms(name)),
                        'hud_locked': bool(_itt(name, cameras=md.cameras)),
                        'n_pixels': len([p for p in md.pixels.get(name, {}).values() if p is not None]),
                        # [VIEW3D-RAYS] LMs observes (marking vivant + xyz connu)
                        'obs': [l for l, px in md.pixels.get(name, {}).items()
                                if px is not None and md.landmarks.get(l) is not None],
                        'corners': None,
                    }
                    try:
                        cam = _get_cam(name)
                        w, h = cd['size']
                        dirs = []
                        for px in ((0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1)):
                            d = cam.get_pixel_direction(px)
                            dirs.append([float(v) for v in d] if d is not None else None)
                        if all(d is not None for d in dirs):
                            entry['corners'] = dirs
                    except Exception:
                        pass
                    cams3d.append(entry)
                lms3d = [{'name': n, 'xyz': [float(v) for v in x],
                          'zone': (md.landmarks_meta.get(n) or {}).get('zone'),
                          'zc': bool((md.landmarks_meta.get(n) or {}).get('z_constraint'))}
                         for n, x in md.landmarks.items() if x is not None]
                meshes = {}
                _mp = os.path.join(REPO_ROOT, 'gtamapdata', 'building_meshes_procedural.json')
                if os.path.exists(_mp):
                    with open(_mp) as _f:
                        meshes = _json.load(_f)
                self.send_json({'cameras': cams3d, 'landmarks': lms3d, 'meshes': meshes})
            except Exception as e:
                import traceback; traceback.print_exc()
                self.send_json({'error': str(e)})

        elif path == '/api/map_data':
            # Single dump used by the SVG map view at load time. After this,
            # all interactivity is client-side except for /api/triangulate
            # (which already exists) and a triangulate refresh loop.
            #
            # Transform (world → SVG pixel space):
            #   svg_x = world_x + 16500
            #   svg_y = (-world_y) + 12000     [y_sign = -1]
            # Origin sits at zero=[16500, 12000] in a 20000x20000 viewBox.
            # Y is flipped because SVG pixel-y grows downward while world-y
            # grows northward — confirmed by gtamaputils.find_aiwe() which
            # maps aiwe_top=North and aiwe_bottom=South.
            # TODO(phase1.5): load these from md.maps['yanis'] dynamically
            #   instead of hardcoding (gtamapdata exposes the same values).

            # Cameras: only those with xyz (otherwise they can't be placed
            # on the map). For each we mirror what /api/cameras returns,
            # plus the per-cam color used by /api/other_cams_overlay.
            # [MAP-DESIGN-V1] enrichissement qualite: tier (confidence_tiers
            # genere), rms live (common.cam_rms, formule canonique), statut
            # HUD-locked (leak_cam_audit). La map encode enfin la qualite.
            try:
                import json as _json
                with open(os.path.join(REPO_ROOT, 'tools', 'generated', 'confidence_tiers.json')) as _f:
                    _tiers_data = _json.load(_f)
                _cams_t = _tiers_data.get('cameras', {})
                _cam_tier = {n: (v.get('tier') if isinstance(v, dict) else v) for n, v in _cams_t.items()}
            except Exception:
                _cam_tier = {}
            try:
                from common import cam_rms as _cam_rms
            except Exception:
                _cam_rms = lambda n: None
            try:
                from leak_cam_audit import is_triangulation_trusted as _itt
            except Exception:
                _itt = lambda n, cameras=None: False

            cams_out = []
            for name, cam_data in md.cameras.items():
                if not cam_data.get('xyz'):
                    continue
                cam_pixels = md.pixels.get(name, {})
                n_indep = sum(
                    1 for lm in cam_pixels
                    if md.landmarks.get(lm) is not None
                    and name not in md.landmarks_meta.get(lm, {}).get('source_cameras', [])
                )
                fov = cam_data.get('fov')
                hfov = float(fov[0]) if fov and fov[0] is not None else None
                # Color: the Camera object owns it (used by other_cams_overlay).
                # get_camera is @lru_cache'd in gtamaplib so this is cheap.
                try:
                    color = [int(v) for v in ml.get_camera(name).color]
                except Exception:
                    color = [200, 200, 200]
                cams_out.append({
                    'name': name,
                    'xyz': [float(v) for v in cam_data['xyz']],
                    'ypr': [float(v) for v in cam_data['ypr']] if cam_data.get('ypr') else None,
                    'hfov': hfov,
                    'size': list(cam_data['size']) if cam_data.get('size') else None,
                    'source': cam_data.get('source'),
                    'type': _classify_cam(name),
                    'color': color,
                    'n_pixels': len(cam_pixels),
                    'n_independent': n_indep,
                    'tier': _cam_tier.get(name),                       # [MAP-DESIGN-V1]
                    'rms_arcmin': (lambda _r: round(_r, 2) if _r is not None else None)(_cam_rms(name)),
                    'hud_locked': bool(_itt(name, cameras=md.cameras)),
                })

            # Landmarks: include ALL of them — even those without xyz, since
            # the Map view will offer Triangulate on them. Phase 6 frontend
            # will render unxyz'd LMs differently.
            lms_out = []
            for name, meta in md.landmarks_meta.items():
                xyz = md.landmarks.get(name)
                source_cameras = list(meta.get('source_cameras') or [])
                lms_out.append({
                    'name': name,
                    'xyz': [float(v) for v in xyz] if xyz is not None else None,
                    'source_cameras': source_cameras,
                    'n_sources': len(source_cameras),
                    'error_m': meta.get('error_m'),
                    'zone': meta.get('zone'),
                    'is_leak_anchored': name in LEAK_ANCHORED_LMS,
                    'z_constraint': meta.get('z_constraint'),
                })

            # Sort: stable ordering helps the frontend diff updates and makes
            # the JSON diffable for debugging. Cams by name, lms by name.
            cams_out.sort(key=lambda c: c['name'])
            lms_out.sort(key=lambda l: l['name'])

            self.send_json({
                'transform': {
                    'world_offset': [16500, 12000],
                    'world_scale': 1.0,
                    'y_sign': -1,
                    'svg_size': [20000, 20000],
                    'map_name': 'yanis',
                },
                'cameras': cams_out,
                'landmarks': lms_out,
                'counts': {
                    'cameras': len(cams_out),
                    'landmarks': len(lms_out),
                    'landmarks_with_xyz': sum(1 for l in lms_out if l['xyz'] is not None),
                    'landmarks_leak_anchored': sum(1 for l in lms_out if l['is_leak_anchored']),
                },
            })

        # ── end SVG Map Refactor (Phase 1) ─────────────────────────

        elif path == '/api/building_meshes_procedural':
            # [MESH-FRONTEND-V2] Project procedural mesh edges to pixel space for a given cam.
            cam_name = unquote(qs.get('cam', [''])[0])
            if not cam_name or cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400)
                return
            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return
            mesh_path = os.path.join(GTAMAP_DIR, 'gtamapdata', 'building_meshes_procedural.json')
            if not os.path.exists(mesh_path):
                self.send_json({'meshes': {}})
                return
            try:
                with open(mesh_path) as _f:
                    meshes = json.load(_f)
            except Exception as e:
                self.send_json({'error': f'failed to load: {e}'}, 500)
                return
            result = {}
            iw, ih = cam.size if cam.size else (3840, 2160)
            for building_name, mesh_data in meshes.items():
                world_edges = mesh_data.get('world_edges', [])
                color = mesh_data.get('color', '#ff9d3d')
                projected = []
                for a, b in world_edges:
                    try:
                        pa = cam.get_pixel(a)
                        pb = cam.get_pixel(b)
                        # Skip if both endpoints out of frame (with margin)
                        margin = 200
                        if (pa[0] < -margin and pb[0] < -margin) or \
                           (pa[0] > iw + margin and pb[0] > iw + margin) or \
                           (pa[1] < -margin and pb[1] < -margin) or \
                           (pa[1] > ih + margin and pb[1] > ih + margin):
                            continue
                        projected.append([list(pa), list(pb)])
                    except Exception:
                        continue
                if projected:
                    result[building_name] = {
                        'color': color,
                        'pixel_edges': projected,
                    }
            self.send_json({'meshes': result})

        elif path == '/api/building_meshes':
            # [MESH-FRONTEND-V1] Return building wireframe meshes.
            # Reads gtamapdata/building_meshes.json and expands edges from
            # LM suffixes to full LM names. Skips edges with missing LMs.
            import json as _json
            mesh_path = os.path.join(GTAMAP_DIR, 'gtamapdata', 'building_meshes.json')
            if not os.path.exists(mesh_path):
                self.send_json({'meshes': {}})
                return
            try:
                with open(mesh_path) as _f:
                    meshes = _json.load(_f)
            except Exception as e:
                self.send_json({'error': f'failed to load: {e}'}, 500)
                return
            result = {}
            for building_name, mesh_data in meshes.items():
                if building_name.startswith('_'): continue  # skip _comment
                edges = mesh_data.get('edges')
                if not edges: continue  # no edges defined (e.g. Portofino procedural)
                color = mesh_data.get('color', '#ff9d3d')
                expanded_edges = []
                for a, b in edges:
                    full_a = f'{building_name} ({a})'
                    full_b = f'{building_name} ({b})'
                    if full_a in md.landmarks and full_b in md.landmarks:
                        expanded_edges.append([full_a, full_b])
                if expanded_edges:
                    result[building_name] = {
                        'color': color,
                        'edges': expanded_edges,
                    }
            self.send_json({'meshes': result})

        elif path == '/api/cameras':
            # [TIER-DOTS-V1] tiers pour la liste (lecture seule, pas de calc RMS)
            try:
                import json as _json
                with open(os.path.join(REPO_ROOT, 'tools', 'generated', 'confidence_tiers.json')) as _f:
                    _tiers = _json.load(_f).get('cameras', {})
            except Exception:
                _tiers = {}
            result = []
            for name in sorted(md.cameras):
                data = md.cameras[name]
                has_image = os.path.exists(os.path.join(FRAMES_DIR, f"{name}.png"))
                cam_pixels = md.pixels.get(name, {})
                n_indep = sum(
                    1 for lm in cam_pixels
                    if md.landmarks.get(lm) is not None
                    and name not in md.landmarks_meta.get(lm, {}).get('source_cameras', [])
                )
                result.append({
                    'name': name,
                    'tier': (_tiers.get(name) or {}).get('tier'),
                    'has_image': has_image,
                    'n_pixels': len(cam_pixels),
                    'n_independent': n_indep,
                    'xyz': list(data['xyz']) if data.get('xyz') else None,
                    'ypr': list(data['ypr']) if data.get('ypr') else None,
                    'fov': list(data['fov']) if data.get('fov') else None,
                    'size': list(data['size']) if data.get('size') else None,
                    'source': data.get('source'),
                    # V2: is_leak now means "xyz is HUD-locked". The
                    # constraint_class field exposes the granular V2 class
                    # for richer client-side handling.
                    'is_leak': name in LOCKED_XYZ_CAMS,
                    'constraint_class': _audit_get_class(name, cameras=md.cameras),
                })
            self.send_json(result)


        # Phase 7a.3: /api/generate_map and /api/generated_map removed.
        # The Map view (Phase 3+4 onwards) replaces this server-rendered
        # top-down PNG entirely. The Generate Map button was removed
        # from the frontend in Phase 7a.2.

        # Phase 7a.3: /api/minimap + /api/generate_map + /api/generated_map removed

        elif path == '/api/lm_info':
            # Returns source cameras + all observers for a landmark.
            lm_name = unquote(qs.get('lm', [''])[0])
            if lm_name not in md.landmarks_meta:
                self.send_json({'error': 'unknown landmark'}, 404)
                return
            meta = md.landmarks_meta[lm_name]
            sources = list(meta.get('source_cameras') or [])
            error_m = meta.get('error_m')
            has_xyz = md.landmarks.get(lm_name) is not None

            # Find all cams that have a pixel for this landmark
            observers = []
            for cam_name, pxs in md.pixels.items():
                if lm_name in pxs:
                    observers.append(cam_name)

            # Other observers = those with pixels who are NOT in sources
            others = [c for c in observers if c not in sources]

            self.send_json({
                'lm': lm_name,
                'sources': sorted(sources),
                'others': sorted(others),
                'n_sources': len(sources),
                'n_others': len(others),
                'n_total_observers': len(observers),
                'error_m': error_m,
                'has_xyz': has_xyz,
                'z_constraint': meta.get('z_constraint'),
            })

        elif path == '/api/dependency_graph':
            # Auto-generated camera dependency graph.
            # Returns nodes (cams + LM clusters) and edges (parent → child).
            import statistics as _stats_local
            import json as _json_local

            # Load tiers
            tiers_path = os.path.join(TOOL_DIR, 'generated', 'confidence_tiers.json')
            tiers = {'cameras': {}, 'landmarks': {}}
            if os.path.exists(tiers_path):
                with open(tiers_path) as f:
                    tiers = _json_local.load(f)

            # Zone inference from xyz
            def infer_zone(xyz):
                if not xyz: return 'unknown'
                x, y, z = xyz
                # Heuristic from map layout
                if y > 3000: return 'ambrosia'  # north
                if y < -3000: return 'keys'  # south
                if y < -1500 and x < -3000: return 'grassrivers'
                if y < 0 and x > -1000: return 'keys'  # south
                if x > 500 and y > -1000: return 'port_gellhorn'
                return 'vice'  # center default

            # Manual zone override for known cams
            ZONE_OVERRIDE = {
                'Leonida Keys 01 (Airplane) (X)': 'keys',
                'Leonida Keys Postcard (X)': 'keys',
                'Leonida Keys 05 (Boats)': 'keys',
                'Key Lento': 'keys',
                'Keys': 'keys',
                'Grassrivers 02 (Watson Bay)': 'grassrivers',
                'Prison': 'grassrivers',
                'Ambrosia 01 (Bikers)': 'ambrosia',
                'Ambrosia 02 (Panorama)': 'ambrosia',
                'Ambrosia 04 (Fires)': 'ambrosia',
                'Ambrosia Postcard (X)': 'ambrosia',
                'Chase (2) (A)': 'ambrosia',
                'Chase (2) (B)': 'ambrosia',
                'Port Gellhorn Postcard (X)': 'port_gellhorn',
                'Port Gellhorn 04 (Delights) (X)': 'port_gellhorn',
                'Mount Kalaga National Park 02 (Helicopter) (X)': 'port_gellhorn',
                'Mount Kalaga National Park 04 (Mountain Pass) (X)': 'port_gellhorn',
            }

            # V2: source_type bucket. 'leak' means "xyz is HUD-locked"
            # (audit-driven, includes legacy date-source cams).
            def get_source_type(name):
                if _audit_xyz_trusted(name, cameras=md.cameras):
                    return 'leak'
                src = md.cameras.get(name, {}).get('source', '') or ''
                if src.startswith('Trailer'):
                    return 'trailer'
                if src.startswith('screenshot') or 'screenshot' in src.lower():
                    return 'screenshots'
                return 'other'

            # Build cam metadata
            cam_data = {}
            for name in md.cameras:
                cam = md.cameras[name]
                xyz = cam.get('xyz')
                ypr = cam.get('ypr')
                fov = cam.get('fov') or [None, None]
                src_type = get_source_type(name)
                tier_info = tiers['cameras'].get(name, {})
                tier = tier_info.get('tier', 'unknown')
                zone = ZONE_OVERRIDE.get(name, infer_zone(xyz))

                # Compute RMS from current calibration
                rms = None
                n_obs = 0
                if xyz and name in md.pixels:
                    try:
                        projs, losses = compute_projections(name)
                        if losses['independent'] is not None:
                            rms = round(losses['independent'], 2)
                        elif losses['total'] is not None:
                            rms = round(losses['total'], 2)
                        n_obs = len([p for p in projs if p['delta'] is not None])
                    except Exception:
                        pass

                cam_data[name] = {
                    'name': name,
                    'xyz': xyz,
                    'ypr': ypr,
                    'fov': fov,
                    'source_type': src_type,
                    'source_str': cam.get('source', ''),
                    'tier': tier,
                    'zone': zone,
                    'rms': rms,
                    'n_obs': n_obs,
                }

            # Build edges: for each cam, find parents (cams that triangulated its LMs)
            # An edge (parent_cam, child_cam) means parent_cam is in source_cameras
            # of at least one LM that child_cam observes.
            edges_set = set()
            for child_name in md.cameras:
                if child_name not in md.pixels: continue
                if not md.cameras[child_name].get('xyz'): continue
                # Cams with HUD-locked xyz are not children in the dependency
                # graph — their pose came from the HUD, not from any parent.
                if child_name in LOCKED_XYZ_CAMS: continue

                # Aggregate parents from LMs this cam marks
                parents = set()
                for lm_name in md.pixels[child_name]:
                    lm_meta = md.landmarks_meta.get(lm_name, {})
                    sources = lm_meta.get('source_cameras') or []
                    for s in sources:
                        if s == child_name: continue  # skip self
                        if s in md.cameras: parents.add(s)

                for p in parents:
                    edges_set.add((p, child_name))

            # Aggregate edges by zone clusters (LM clusters)
            # If cam X depends on >=2 cams from same zone, replace with cluster edge
            ZONE_TO_CLUSTER = {
                'vice': 'lm_vc',
                'ambrosia': 'lm_ambrosia',
                'keys': 'lm_keys',
                'grassrivers': 'lm_gv',
                'port_gellhorn': 'lm_pgh',
                'unknown': 'lm_misc',
            }
            CLUSTER_LABELS = {
                'lm_vc': 'Vice City\nlandmarks',
                'lm_ambrosia': 'Ambrosia\nlandmarks',
                'lm_keys': 'Keys & Islands\nlandmarks',
                'lm_gv': 'Grassrivers\nlandmarks',
                'lm_pgh': 'Port Gellhorn\nlandmarks',
                'lm_misc': 'Other\nlandmarks',
            }
            CLUSTER_ZONES = {
                'lm_vc': 'vice',
                'lm_ambrosia': 'ambrosia',
                'lm_keys': 'keys',
                'lm_gv': 'grassrivers',
                'lm_pgh': 'port_gellhorn',
                'lm_misc': 'unknown',
            }

            # Group parents per (child, zone)
            child_zone_parents = {}  # (child, zone) -> set of parents
            for (parent, child) in edges_set:
                zone = cam_data[parent]['zone']
                key = (child, zone)
                if key not in child_zone_parents:
                    child_zone_parents[key] = set()
                child_zone_parents[key].add(parent)

            # Final edges
            final_edges = []
            cluster_used = set()
            for (child, zone), parents in child_zone_parents.items():
                cluster_id = ZONE_TO_CLUSTER.get(zone, 'lm_misc')
                if len(parents) >= 2:
                    # Use cluster edge
                    cluster_used.add(cluster_id)
                    final_edges.append({'from': cluster_id, 'to': child, 'type': 'calib'})
                    # Each parent contributes to cluster
                    for p in parents:
                        # avoid duplicates
                        final_edges.append({'from': p, 'to': cluster_id, 'type': 'lm'})
                else:
                    # Single parent — direct edge
                    for p in parents:
                        final_edges.append({'from': p, 'to': child, 'type': 'calib'})

            # Deduplicate edges
            seen = set()
            dedup_edges = []
            for e in final_edges:
                key = (e['from'], e['to'], e['type'])
                if key in seen: continue
                seen.add(key)
                dedup_edges.append(e)

            # Build nodes list
            nodes = []
            # Cam nodes
            for name, c in cam_data.items():
                # Skip cams with no xyz AND no observations (they're not in tree)
                if not c['xyz'] and c['n_obs'] == 0:
                    continue
                # Skip leak cams that nobody depends on (would be visual noise)
                # Actually, include all that are referenced by other cams or have own xyz
                node_type = c['source_type']
                if node_type == 'leak':
                    node_type = 'leak'
                elif c['tier'] == 'anchor':
                    node_type = 'anchor'
                elif c['tier'] == 'high':
                    node_type = 'high'
                elif c['tier'] == 'medium':
                    node_type = 'medium'
                elif c['tier'] == 'low':
                    node_type = 'low'
                else:
                    node_type = 'unverified'
                nodes.append({
                    'id': name,
                    'label': name,
                    'type': node_type,
                    'zone': c['zone'],
                    'xyz': c['xyz'],
                    'ypr': c['ypr'],
                    'fov': c['fov'],
                    'source_type': c['source_type'],
                    'source_str': c['source_str'],
                    'tier': c['tier'],
                    'rms': c['rms'],
                    'n_obs': c['n_obs'],
                })

            # Cluster nodes
            for cluster_id in cluster_used:
                nodes.append({
                    'id': cluster_id,
                    'label': CLUSTER_LABELS[cluster_id],
                    'type': 'lm_cluster',
                    'zone': CLUSTER_ZONES[cluster_id],
                })

            response = {
                'nodes': nodes,
                'edges': dedup_edges,
                'n_cams': sum(1 for n in nodes if n['type'] != 'lm_cluster'),
                'n_clusters': len(cluster_used),
                'n_edges': len(dedup_edges),
            }
            self.send_json(response)

        elif path == '/api/cam_health':
            # Per-cam health metrics. Reuses compute_projections to get
            # angular residuals from the current calibration state.
            import statistics
            result = []
            for name in sorted(md.cameras):
                if not md.cameras[name].get('xyz'):
                    continue
                try:
                    projs, losses = compute_projections(name)
                except Exception:
                    continue

                errs = [p['delta'] for p in projs if p['delta'] is not None]
                indep_errs = [p['delta'] for p in projs
                              if p['delta'] is not None and not p['is_circular']]

                if not errs:
                    continue

                cam_data = md.cameras[name]
                source = cam_data.get('source') or ''
                # V2: 'LEAK' bucket means xyz is HUD-locked (audit-driven).
                if name in LOCKED_XYZ_CAMS:
                    source_type = 'LEAK'
                elif source.startswith('Trailer 1'):
                    source_type = 'Trailer 1'
                elif source.startswith('Trailer 2') or source == 'Trailer 2':
                    source_type = 'Trailer 2'
                elif source.startswith('Trailer'):
                    source_type = 'Trailer'
                else:
                    source_type = 'screenshots'

                loss_val = losses['independent'] if losses['independent'] is not None else losses['total']
                loss = round(loss_val or 0, 2)
                median_err = round(statistics.median(errs), 2)
                max_err = round(max(errs), 2)
                worst_lm = max(projs, key=lambda p: p['delta'] if p['delta'] is not None else -1)['name']

                if loss > 15 or max_err > 60:
                    status = 'broken'
                elif loss > 5 or median_err > 4 or len(indep_errs) < 4:
                    status = 'suspicious'
                else:
                    status = 'healthy'

                result.append({
                    'name': name,
                    'source_type': source_type,
                    'loss': loss,
                    'median_err': median_err,
                    'max_err': max_err,
                    'worst_lm': worst_lm,
                    'n_pixels': len(projs),
                    'n_indep': len(indep_errs),
                    'status': status,
                })

            status_order = {'broken': 0, 'suspicious': 1, 'healthy': 2}
            result.sort(key=lambda r: (status_order[r['status']], -r['loss']))

            total_pixels = sum(r['n_pixels'] for r in result)
            global_rms = (sum(r['loss']**2 * r['n_pixels'] for r in result) /
                          max(1, total_pixels)) ** 0.5 if result else 0

            summary = {
                'total': len(result),
                'broken': sum(1 for r in result if r['status'] == 'broken'),
                'suspicious': sum(1 for r in result if r['status'] == 'suspicious'),
                'healthy': sum(1 for r in result if r['status'] == 'healthy'),
                'global_rms': round(global_rms, 3),
            }

            self.send_json({'cams': result, 'summary': summary})

        elif path == '/api/project':
            cam_name = unquote(qs.get('cam', [''])[0])
            xyz = [float(qs['x'][0]), float(qs['y'][0]), float(qs['z'][0])] if 'x' in qs else None
# ── SERVER-ROLL-PATCH-V1 ──
            # V1-ROLL: parse roll from query string (defaults to 0 for backward compat)
            ypr = [float(qs['yaw'][0]), float(qs['pitch'][0]),
                   float(qs.get('roll', ['0.0'])[0])] if 'yaw' in qs else None
            hfov = float(qs['hfov'][0]) if 'hfov' in qs else None

            projs, losses = compute_projections(cam_name, xyz, ypr, hfov)
            cam_data = md.cameras.get(cam_name, {})
            cam = get_cam(cam_name, xyz, ypr, hfov)

            self.send_json({
                'camera': {
                    'xyz': list(cam.xyz),
                    'ypr': list(cam.ypr),
                    'hfov': cam.hfov,
                    'size': list(cam.size),
                    'source': cam_data.get('source'),
                },
                'projections': projs,
                'losses': losses,
            })

        elif path == '/api/verticals':  # ── VERTICALS-V1 ──  # ── VERTICALS-V1-FIX ──
            # Phase 11: project world-vertical lines through the cam and
            # return their pixel coords. Frontend overlays these as yellow
            # lines on the screenshot — if calib is correct, they align
            # with real-world verticals (poles, building edges, etc.).
            cam_name = qs.get('cam', [None])[0]
            if cam_name is None or cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, status=400)
                return
            try:
                xyz = [float(v) for v in qs.get('xyz', ['0,0,0'])[0].split(',')]
                ypr = [float(v) for v in qs.get('ypr', ['0,0,0'])[0].split(',')]
                hfov = float(qs.get('hfov', ['60'])[0])
            except Exception:
                self.send_json({'error': 'bad params'}, status=400)
                return

            import math as _math
            try:
                cam = get_cam(cam_name, xyz, ypr, hfov)
            except Exception as e:
                self.send_json({'error': f'get_cam failed: {e}'}, status=500)
                return

            yaw = ypr[0]
            cx, cy, cz = xyz[0], xyz[1], xyz[2]
            lines = []
            # rlx's algo: sweep degree from yaw-60 to yaw+60, step 0.5
            # For each deg, build vertical line in world at distance 10
            # from cam, from z-10 to z+10 (20m tall).
            deg = yaw - 60.0
            while deg < yaw + 60.0:
                rad = _math.radians(deg + 90.0)
                wx = cx + _math.cos(rad) * 10.0
                wy = cy + _math.sin(rad) * 10.0
                try:
                    p1 = cam.get_pixel((wx, wy, cz - 10.0))
                    p2 = cam.get_pixel((wx, wy, cz + 10.0))
                    if p1 is not None and p2 is not None:
                        lines.append([
                            [float(p1[0]), float(p1[1])],
                            [float(p2[0]), float(p2[1])],
                        ])
                except Exception:
                    pass
                deg += 0.5

            self.send_json({'lines': lines})

        elif path == '/api/optimize':
            # [DECOM-V1] Decommissioned (decision 2026-05-26, executed 2026-07-02):
            # the UI visualizes and marks; solving lives in the CLI.
            self.send_json({'error': 'decommissioned — use tools/refine_cam_full.py / '
                                     'refine_cam_ypr.py / calibrate_session.py'}, 410)

        elif path == '/api/render_loss':
            # [RENDER-LOSS-V1] Generate or load cached loss landscape for a cam.
            # Returns JSON with samples {x, y, loss, color, params}.
            # Optional ?force=true to regenerate (otherwise use cache).
            cam_name = unquote(qs.get('cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400)
                return
            force = qs.get('force', ['false'])[0].lower() == 'true'
            spacing = float(qs.get('spacing', ['10.0'])[0])
            budget = int(qs.get('budget', ['150'])[0])
            max_nfev = int(qs.get('max_nfev', ['100'])[0])
            
            # Cache path
            safe_name = cam_name.replace('/', '_').replace(' ', '_').replace('(', '').replace(')', '')
            cache_dir = os.path.join(os.path.dirname(__file__), 'generated', 'loss_renders')
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f'{safe_name}.json')
            
            if not force and os.path.exists(cache_path):
                with open(cache_path) as f:
                    data = json.load(f)
                print(f"Render loss for {cam_name}: served from cache ({data.get('n_samples', 0)} samples)")
                self.send_json(data)
                return
            
            # Generate
            print(f"Rendering loss for {cam_name} (spacing={spacing}m, budget={budget})...")
            try:
                import render_loss as rl_mod
                data = rl_mod.render_loss_data(cam_name, spacing, budget, max_nfev, verbose=False)
                with open(cache_path, 'w') as f:
                    json.dump(data, f)
                print(f"  done. {data['n_samples']} samples, loss [{data['loss_min']:.2f}, {data['loss_max']:.2f}]'")
                self.send_json(data)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'error': str(e)}, 500)

        elif path == '/api/export_validation':
            cam_name = unquote(qs.get('cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400); return
            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 400); return
            if cam.xyz is None or cam.q is None:
                self.send_json({'error': 'cam not calibrated'}, 400); return
            from PIL import Image, ImageDraw, ImageFont
            import io as _io, math as _math
            frame_path = os.path.join(os.path.dirname(TOOL_DIR), 'frames', cam_name + '.png')
            if not os.path.exists(frame_path):
                self.send_json({'error': 'frame not found'}, 404); return
            base = Image.open(frame_path).convert('RGBA')
            W, H = base.size
            ov = Image.new('RGBA',(W,H),(0,0,0,0)); draw = ImageDraw.Draw(ov)
            INK=(12,12,16)
            TIER_COL={'anchor':(74,222,128),'high':(96,165,250),'medium':(245,158,11),
                      'low':(248,113,113),'unverified':(160,160,180)}
            def dcol(d):
                if d is None: return (130,130,160)
                if d < 1: return (74,222,128)
                if d < 3: return (163,230,53)
                if d < 8: return (245,158,11)
                return (248,113,113)
            def tcolor(bg):
                lum=0.299*bg[0]+0.587*bg[1]+0.114*bg[2]
                return (10,10,12) if lum>140 else (255,255,255)
            def F(sz):
                for fp in ('/System/Library/Fonts/Menlo.ttc','/System/Library/Fonts/Monaco.ttf',
                           '/System/Library/Fonts/SFNSMono.ttf','/System/Library/Fonts/Supplemental/Andale Mono.ttf'):
                    try: return ImageFont.truetype(fp, sz)
                    except Exception: pass
                return ImageFont.load_default()
            flab=F(max(12,int(W/200))); fbar=F(max(16,int(W/120)))
            cam_tier='unverified'
            try:
                with open(os.path.join(TOOL_DIR,'generated','confidence_tiers.json')) as _tf:
                    _tj=json.load(_tf)
                _v=_tj.get('cameras', {}).get(cam_name)
                if isinstance(_v,dict): cam_tier=_v.get('tier','unverified')
                elif isinstance(_v,str): cam_tier=_v
            except Exception: pass
            hfov_deg=cam.fov[0]
            marked=md.pixels.get(cam_name,{})
            pts=[]; deltas=[]
            for lm_name, marker_px in marked.items():
                lm_xyz=md.landmarks.get(lm_name)
                if lm_xyz is None: continue
                proj=cam.get_pixel(list(lm_xyz))
                if proj is None: continue
                px,py=float(proj[0]),float(proj[1])
                mx,my=float(marker_px[0]),float(marker_px[1])
                d=(_math.hypot(px-mx,py-my)/W)*hfov_deg*60.0
                deltas.append(d)
                if -100<mx<W+100 and -100<my<H+100:
                    pts.append([lm_name,mx,my,d])
            pts.sort(key=lambda p:p[1])
            STEM=int(H*0.045); last=-999; tlvl=0; gap=int(W*0.018)
            for nm,px,py,d in pts:
                if px-last<gap: tlvl=(tlvl+1)%3
                else: tlvl=0
                last=px
                col=dcol(d); stem=STEM+tlvl*int(H*0.04)
                draw.ellipse([px-3,py-3,px+3,py+3],fill=col+(255,))
                bb=flab.getbbox(nm); tw=bb[2]-bb[0]; th=bb[3]-bb[1]; padx=6; pady=3
                card=Image.new('RGBA',(tw+padx*2,th+pady*2),(0,0,0,0))
                cd=ImageDraw.Draw(card)
                cd.rounded_rectangle([0,0,tw+padx*2-1,th+pady*2-1],radius=3,fill=col+(255,))
                cd.text((padx,pady-bb[1]),nm,fill=tcolor(col)+(255,),font=flab)
                cv=card.rotate(90,expand=True)
                ty=py-stem
                paste_y=int(ty)-cv.height-2
                if paste_y < 4:
                    ty=py+stem
                    paste_y=int(ty)+2
                draw.line([(px,py),(px,ty)],fill=col+(180,),width=1)
                ov.paste(cv,(int(px)-cv.width//2,paste_y),cv)
            deltas.sort(); med=deltas[len(deltas)//2] if deltas else 0.0
            yp=cam.ypr if (hasattr(cam,'ypr') and cam.ypr is not None) else [0,0,0]
            tcol=TIER_COL.get(cam_tier,(160,160,180))
            WHITE=(214,214,228)
            segs=[("XYZ (%.0f, %.0f, %.1f)   "%(cam.xyz[0],cam.xyz[1],cam.xyz[2]), WHITE),
                  ("YPR (%.1f, %.1f, %.1f)   "%(yp[0],yp[1],yp[2]), WHITE),
                  ("FOV (%.1f, %.1f)    "%(cam.fov[0],cam.fov[1]), WHITE),
                  (cam_tier.upper()+" confidence    ", tcol),
                  ("RMS %.1f'    "%med, WHITE),
                  (cam_name, tcol)]
            total_w=sum(fbar.getbbox(t)[2] for t,_ in segs)
            sidepad=int(W*0.012)
            box_w=total_w+sidepad*2
            barh=max(int(H*0.032),30); by=H-barh-int(H*0.012)
            draw.rounded_rectangle([sidepad,by,sidepad+box_w,by+barh],radius=6,
                                   fill=INK+(236,),outline=tcol+(255,),width=1)
            x=sidepad*2; ty=by+(barh-fbar.getbbox("X")[3])//2 - 1
            for txt,col in segs:
                draw.text((x,ty),txt,fill=col+(255,),font=fbar)
                x+=fbar.getbbox(txt)[2]
            out=Image.alpha_composite(base,ov).convert('RGB')
            buf=_io.BytesIO(); out.save(buf,'PNG'); data=buf.getvalue()
            self.send_response(200)
            self.send_header('Content-Type','image/png')
            self.send_header('Content-Disposition','attachment; filename="'+cam_name+' validation.png"')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers(); self.wfile.write(data)

        elif path == '/api/export_map_validation':
            cam_name = unquote(qs.get('cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400); return
            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 400); return
            if cam.xyz is None or cam.q is None:
                self.send_json({'error': 'cam not calibrated'}, 400); return
            from PIL import Image, ImageDraw, ImageFont
            import io as _io, math as _math
            Image.MAX_IMAGE_PIXELS = None
            cx, cy = float(cam.xyz[0]), float(cam.xyz[1])
            INK=(12,12,16); INK_BG=(18,20,28)
            TIER_COL={'anchor':(74,222,128),'high':(96,165,250),'medium':(245,158,11),
                      'low':(248,113,113),'unverified':(160,160,180)}
            def dcol(d):
                if d is None: return (130,130,160)
                if d < 1: return (74,222,128)
                if d < 3: return (163,230,53)
                if d < 8: return (245,158,11)
                return (248,113,113)
            def tcolor(bg):
                lum=0.299*bg[0]+0.587*bg[1]+0.114*bg[2]
                return (10,10,12) if lum>140 else (255,255,255)
            def F(sz):
                for fp in ('/System/Library/Fonts/Menlo.ttc','/System/Library/Fonts/Monaco.ttf',
                           '/System/Library/Fonts/SFNSMono.ttf','/System/Library/Fonts/Supplemental/Andale Mono.ttf'):
                    try: return ImageFont.truetype(fp, sz)
                    except Exception: pass
                return ImageFont.load_default()
            cam_tier='unverified'
            try:
                with open(os.path.join(TOOL_DIR,'generated','confidence_tiers.json')) as _tf:
                    _tj=json.load(_tf)
                _v=_tj.get('cameras', {}).get(cam_name)
                if isinstance(_v,dict): cam_tier=_v.get('tier','unverified')
                elif isinstance(_v,str): cam_tier=_v
            except Exception: pass
            tcol=TIER_COL.get(cam_tier,(160,160,180))
            hfov_deg=cam.fov[0]
            size=md.cameras[cam_name].get('size') or [1920,1080]
            marked=md.pixels.get(cam_name,{})
            lms=[]; maxd=300.0
            for lm_name, marker_px in marked.items():
                lm_xyz=md.landmarks.get(lm_name)
                if lm_xyz is None: continue
                lx,ly=float(lm_xyz[0]),float(lm_xyz[1])
                maxd=max(maxd,_math.hypot(lx-cx,ly-cy))
                proj=cam.get_pixel(list(lm_xyz))
                if proj is None: d=None
                else:
                    px,py=float(proj[0]),float(proj[1])
                    mxp,myp=float(marker_px[0]),float(marker_px[1])
                    d=(_math.hypot(px-mxp,py-myp)/size[0])*hfov_deg*60.0
                lms.append([lm_name,lx,ly,d])
            R=maxd*1.15
            try:
                mp=ml.get_map('yanis'); mp.open(add_padding=False)
                MAP_PX=mp.size[0] if hasattr(mp,'size') else 20000
            except Exception as e:
                self.send_json({'error':f'map open failed: {e}'},500); return
            p_test = mp.get_map_xy((0.0,0.0)); Xoff=p_test[0]; Yoff=p_test[1]
            WX_MIN=0-Xoff; WX_MAX=MAP_PX-Xoff; WY_MAX=Yoff-0; WY_MIN=Yoff-MAP_PX
            half=R; ctrx,ctry=cx,cy
            if ctrx-half<WX_MIN: ctrx=WX_MIN+half
            if ctrx+half>WX_MAX: ctrx=WX_MAX-half
            if ctry-half<WY_MIN: ctry=WY_MIN+half
            if ctry+half>WY_MAX: ctry=WY_MAX-half
            x0w,y0w,x1w,y1w=ctrx-half,ctry-half,ctrx+half,ctry+half
            try:
                px0,py_a=mp.get_map_xy((x0w,y0w)); px1,py_b=mp.get_map_xy((x1w,y1w))
                px0,px1=sorted((px0,px1)); py0,py1=sorted((py_a,py_b))
                vx0,vy0=max(0,int(px0)),max(0,int(py0))
                vx1,vy1=min(MAP_PX,int(px1)),min(MAP_PX,int(py1))
                req_w=int(px1-px0); req_h=int(py1-py0)
                canvas=Image.new('RGB',(req_w,req_h),INK_BG)
                if vx1>vx0 and vy1>vy0:
                    piece=mp.image.crop((vx0,vy0,vx1,vy1))
                    canvas.paste(piece,(vx0-int(px0),vy0-int(py0)))
            except Exception as e:
                self.send_json({'error':f'map crop failed: {e}'},500); return
            OUT=1500
            crop=canvas.resize((OUT,OUT),Image.BILINEAR).convert('RGBA')
            dark=Image.new('RGBA',(OUT,OUT),(8,10,16,80))
            base=Image.alpha_composite(crop,dark)
            ov=Image.new('RGBA',(OUT,OUT),(0,0,0,0)); draw=ImageDraw.Draw(ov)
            CROP_M=2*R
            def w2c(x,y): return ((x-x0w)/CROP_M*OUT,(y1w-y)/CROP_M*OUT)
            flab=F(max(7,int(OUT/200))); fbar=F(max(13,int(OUT/110)))
            camx,camy=w2c(cx,cy)
            try:
                vdir=cam.get_pixel_direction((size[0]/2.0,size[1]/2.0))
                aim=_math.atan2(float(vdir[1]),float(vdir[0]))
            except Exception:
                aim=_math.radians(90.0)
            halffov=_math.radians(hfov_deg/2.0); clen=CROP_M*1.5
            def cone_pt(a): return w2c(cx+_math.cos(a)*clen, cy+_math.sin(a)*clen)
            draw.polygon([(camx,camy),cone_pt(aim-halffov),cone_pt(aim+halffov)],fill=tcol+(22,),outline=tcol+(70,))
            placed=[]
            def overlaps(b):
                for p in placed:
                    if not (b[2]<p[0] or b[0]>p[2] or b[3]<p[1] or b[1]>p[3]): return True
                return False
            lms_sorted=sorted(lms, key=lambda r:w2c(r[1],r[2])[1])
            for lm_name,lx,ly,d in lms_sorted:
                col=dcol(d); mx,my=w2c(lx,ly)
                draw.line([(camx,camy),(mx,my)],fill=col+(120,),width=1)
                draw.ellipse([mx-2,my-2,mx+2,my+2],fill=col+(220,),outline=(255,255,255,180),width=1)
                vx,vy=mx-camx,my-camy; vn=_math.hypot(vx,vy) or 1; ux,uy=vx/vn,vy/vn
                bb=flab.getbbox(lm_name); tw=bb[2]-bb[0]; th=bb[3]-bb[1]
                lxp,lyp=mx+ux*6,my+uy*6
                bx=lxp-tw-4 if ux<0 else lxp; by=lyp-th/2-2
                bx=max(2,min(bx,OUT-tw-6)); by=max(2,min(by,OUT-th-6))
                tries=0
                while overlaps((bx-2,by-1,bx+tw+3,by+th+3)) and tries<24:
                    by+=th+3; tries+=1
                    if by>OUT-th-6: by=2+tries*4
                placed.append((bx-2,by-1,bx+tw+3,by+th+3))
                draw.rounded_rectangle([bx-2,by-1,bx+tw+3,by+th+3],radius=2,fill=col+(175,))
                draw.text((bx,by),lm_name,fill=tcolor(col)+(255,),font=flab)
            draw.ellipse([camx-5,camy-5,camx+5,camy+5],fill=tcol+(255,),outline=(255,255,255,255),width=2)
            yp=cam.ypr if (hasattr(cam,'ypr') and cam.ypr is not None) else [0,0,0]
            dvals=sorted(x[3] for x in lms if x[3] is not None)
            med=dvals[len(dvals)//2] if dvals else 0.0
            WHITE=(214,214,228)
            segs=[("XYZ (%.0f, %.0f, %.1f)   "%(cam.xyz[0],cam.xyz[1],cam.xyz[2]),WHITE),
                  ("YPR (%.1f, %.1f, %.1f)   "%(yp[0],yp[1],yp[2]),WHITE),
                  (cam_tier.upper()+" confidence   ",tcol),
                  ("RMS %.1f'   "%med,WHITE),(cam_name,tcol)]
            tot=sum(fbar.getbbox(t)[2] for t,_ in segs); sp=int(OUT*0.016)
            bw=tot+sp*2; bh=max(int(OUT*0.022),22); by=OUT-bh-int(OUT*0.016)
            draw.rounded_rectangle([sp,by,sp+bw,by+bh],radius=5,fill=INK+(236,),outline=tcol+(255,),width=1)
            x=sp*2; ty=by+(bh-fbar.getbbox("X")[3])//2-1
            for t,c in segs:
                draw.text((x,ty),t,fill=c+(255,),font=fbar); x+=fbar.getbbox(t)[2]
            out=Image.alpha_composite(base,ov).convert('RGB')
            buf=_io.BytesIO(); out.save(buf,'PNG'); data=buf.getvalue()
            self.send_response(200)
            self.send_header('Content-Type','image/png')
            self.send_header('Content-Disposition','attachment; filename="'+cam_name+' map.png"')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers(); self.wfile.write(data)

        elif path == '/api/lm_projections':
            # [MULTICAM-STEP23] Return all LMs that should appear as ghost
            # markers on this cam's image.
            # [MULTICAM-STEP23-FIX7] Optional filter_cam param: if provided,
            # only return LMs that are marked on filter_cam (so cam1 shows
            # ghosts of LMs marked on cam2, helping verify alignment).
            cam_name = unquote(qs.get('cam', [''])[0])
            filter_cam = unquote(qs.get('filter_cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400)
                return
            try:
                target_cam = ml.get_camera(cam_name)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return
            if target_cam.xyz is None or target_cam.q is None:
                self.send_json({'error': 'cam not calibrated'}, 400)
                return
            target_w, target_h = target_cam.w, target_cam.h
            target_pixels = md.pixels.get(cam_name, {})  # LMs already marked on this cam

            # [MULTICAM-STEP23-FIX] md.landmarks is {name: (x,y,z)} — no source_cameras.
            # Read source_cameras from landmarks.json directly.
            _lm_json_path = os.path.join(os.path.dirname(TOOL_DIR), 'gtamapdata', 'landmarks.json')
            try:
                with open(_lm_json_path) as _f:
                    _lm_meta = json.load(_f)
            except Exception:
                _lm_meta = {}

            # [ASSIST-V1] mode=assist: single-cam marking assistant. No
            # filter_cam; every projectable unmarked LM is returned with a
            # priority score describing what marking it would unlock.
            assist = qs.get('mode', [''])[0] == 'assist'
            _tiers_path = os.path.join(TOOL_DIR, 'generated', 'confidence_tiers.json')
            _lm_tier, _cam_meta = {}, {}
            if assist and os.path.exists(_tiers_path):
                try:
                    with open(_tiers_path) as _f:
                        _t = json.load(_f)
                    _lm_tier = {k: v.get('tier') for k, v in _t.get('landmarks', {}).items()}
                    _cam_meta = _t.get('cameras', {}).get(cam_name, {})
                except Exception:
                    pass
            _cam_n_obs = _cam_meta.get('n_obs', 99)

            def _assist_score(lm_name, n_src):
                lt = _lm_tier.get(lm_name)
                if n_src == 1:
                    return 1, '2nd source -> triangulation'
                if lt in ('anchor', 'high') and _cam_n_obs < 5:
                    return 1, 'anchor for this under-observed cam'
                if lt in ('anchor', 'high'):
                    return 2, 'anchor (useful redundancy)'
                if lt in ('low', 'medium'):
                    return 2, 'one more source -> tier'
                return 3, 'coverage'

            projections = []
            VIRTUAL_PREFIXES = ('Portofino Tower (',)
            # If a filter_cam is given, restrict to LMs marked on it.
            filter_set = None
            if filter_cam and filter_cam in md.cameras:
                filter_set = set(md.pixels.get(filter_cam, {}).keys())
            for lm_name, lm in md.landmarks.items():
                # Skip the few synthetic / virtual LMs
                if any(lm_name.startswith(p) for p in VIRTUAL_PREFIXES):
                    continue
                # [MULTICAM-STEP23-FIX7] Filter to LMs marked on the other pane's cam
                if filter_set is not None and lm_name not in filter_set:
                    continue
                # Skip if already marked on the target cam (no ghost needed)
                if lm_name in target_pixels:
                    continue
                # md.landmarks value is (x, y, z) tuple — that IS the xyz.
                lm_xyz = list(lm) if (isinstance(lm, (tuple, list)) and len(lm) == 3) else None
                meta = _lm_meta.get(lm_name, {})
                src_cams = meta.get('source_cameras', []) if isinstance(meta, dict) else []

                if lm_xyz is not None:
                    # Triangulated -> project as a point
                    try:
                        px = target_cam.get_pixel(lm_xyz)
                    except Exception:
                        continue
                    if px is None:
                        continue
                    x, y = float(px[0]), float(px[1])
                    # Skip if out of frame (with small margin for labels)
                    if x < -50 or x > target_w + 50 or y < -50 or y > target_h + 50:
                        continue
                    _entry = {
                        'name': lm_name,
                        'type': 'point',
                        'pixel': [x, y],
                    }
                    if assist:
                        _p, _r = _assist_score(lm_name, len(src_cams))
                        _entry.update({'priority': _p, 'reason': _r,
                                       'tier': _lm_tier.get(lm_name),
                                       'n_sources': len(src_cams)})
                    projections.append(_entry)
                elif len(src_cams) == 1:
                    # 1 source only -> epipolar line on the target cam
                    src_cam_name = src_cams[0]
                    if src_cam_name == cam_name:
                        continue
                    if src_cam_name not in md.cameras:
                        continue
                    src_pixels = md.pixels.get(src_cam_name, {})
                    if lm_name not in src_pixels:
                        continue
                    try:
                        src_cam = ml.get_camera(src_cam_name)
                        src_pix = src_pixels[lm_name]
                        # Ray from src_cam through this pixel
                        d = src_cam.get_pixel_direction((float(src_pix[0]), float(src_pix[1])))
                        # Sample 2 points along the ray at near + far distances
                        # and project on target_cam.
                        import numpy as _np
                        src_xyz = _np.asarray(src_cam.xyz, dtype=float)
                        d = _np.asarray(d, dtype=float)
                        near_pt = (src_xyz + 50.0 * d).tolist()
                        far_pt  = (src_xyz + 5000.0 * d).tolist()
                        px_near = target_cam.get_pixel(near_pt)
                        px_far  = target_cam.get_pixel(far_pt)
                        if px_near is None or px_far is None:
                            continue
                        x1, y1 = float(px_near[0]), float(px_near[1])
                        x2, y2 = float(px_far[0]), float(px_far[1])
                        # If both endpoints are way outside the frame, skip
                        outside = (
                            (max(x1, x2) < -50 or min(x1, x2) > target_w + 50) or
                            (max(y1, y2) < -50 or min(y1, y2) > target_h + 50)
                        )
                        if outside:
                            continue
                        _entry = {
                            'name': lm_name,
                            'type': 'epipolar',
                            'line': [[x1, y1], [x2, y2]],
                            'source_cam': src_cam_name,
                        }
                        if assist:
                            _entry.update({'priority': 1,
                                           'reason': '2nd source -> triangulation (epipolar line)',
                                           'tier': _lm_tier.get(lm_name),
                                           'n_sources': 1})
                        projections.append(_entry)
                    except Exception:
                        continue

            if assist:
                projections.sort(key=lambda p: (p.get('priority', 3), p['name']))
            self.send_json({
                'cam': cam_name,
                'cam_size': [target_w, target_h],
                'projections': projections,
            })

        # [T3-LINES-V1] persistance des lignes tracees (bootstrap VP)
        elif path == '/api/save_lines':
            try:
                import json as _json
                cam_name = unquote(qs.get('cam', [''])[0])
                if cam_name not in md.cameras:
                    self.send_json({'error': 'invalid cam'}, 400); return
                hlines = _json.loads(unquote(qs.get('hlines', ['null'])[0]))
                vlines = _json.loads(unquote(qs.get('vlines', ['null'])[0]))
                md.update_lines(cam_name, hlines=hlines, vlines=vlines)
                ml.get_camera.cache_clear()
                self.send_json({'ok': True, 'lines': md.lines.get(cam_name, [[], []])})
            except Exception as e:
                self.send_json({'error': str(e)}, 500)

        elif path == '/api/get_lines':
            cam_name = unquote(qs.get('cam', [''])[0])
            self.send_json({'lines': md.lines.get(cam_name, [[], []])})

        # [T3-LINES-V1] solve roll+pitch depuis les vlines (pipeline valide:
        # roll par _get_roll_from_vlines sur probe roll=0, puis pitch par
        # _get_pitch_from_vlines avec le roll resolu)
        elif path == '/api/solve_lines':
            try:
                cam_name = unquote(qs.get('cam', [''])[0])
                cur = md.lines.get(cam_name)
                if not cur or len(cur[1]) < 2:
                    self.send_json({'error': 'need at least 2 vlines'}, 400); return
                cd = md.cameras[cam_name]
                base_ypr = cd.get('ypr') or (0.0, 0.0, 0.0)
                hfov = (cd.get('fov') or (60.0, None))[0]
                # ordre valide (4 poses synthetiques exactes): roll (pure
                # image), puis FOV si hlines (VPs orthogonaux — corrige le
                # pitch des cams au FOV douteux), puis pitch avec les deux.
                probe = ml.Camera(id=99998, name='__PROBE_R', player=None,
                                  xyz=cd.get('xyz') or (0, 0, 0),
                                  ypr=(base_ypr[0], 0.0, 0.0), fov=(hfov, None),
                                  size=cd['size'], source='probe',
                                  lines=[[], list(cur[1])])
                roll = probe._get_roll_from_vlines()
                if roll is None:
                    self.send_json({'error': 'VVP indefini (verticales paralleles?)'}, 400); return
                solved_fov = None
                if len(cur[0]) >= 2:
                    probe_f = ml.Camera(id=99996, name='__PROBE_F', player=None,
                                        xyz=cd.get('xyz') or (0, 0, 0),
                                        ypr=(base_ypr[0], 0.0, roll), fov=(hfov, None),
                                        size=cd['size'], source='probe',
                                        lines=[list(cur[0]), list(cur[1])])
                    out = probe_f._get_fov_from_lines()
                    if out:
                        solved_fov = float(out[0])
                pitch_fov = solved_fov if solved_fov else hfov
                probe2 = ml.Camera(id=99997, name='__PROBE_P', player=None,
                                   xyz=cd.get('xyz') or (0, 0, 0),
                                   ypr=(base_ypr[0], 0.0, roll), fov=(pitch_fov, None),
                                   size=cd['size'], source='probe',
                                   lines=[[], list(cur[1])])
                pitch = probe2._get_pitch_from_vlines()
                # [T3-YAW-CHAIN] orientation complete: si la cam a un xyz et
                # >=1 marking vivant sur un LM a xyz connu, chaque marking
                # implique un yaw (calibrate_yaw sur probe). Moyenne
                # circulaire = yaw; spread = indicateur de sante gratuit
                # (si roll/pitch/fov sont bons, tous les markings pointent
                # le meme yaw). Valide: synthese exacte, spread 0.0000.
                yaw = None; yaw_spread = None; n_yaw = 0
                if cd.get('xyz') and pitch is not None:
                    import math as _math
                    cam_px = md.pixels.get(cam_name, {})
                    usable = [(l, px) for l, px in cam_px.items()
                              if px is not None and md.landmarks.get(l) is not None]
                    yaws = []
                    for l, px in usable:
                        try:
                            yp = ml.Camera(id=99995, name='__PROBE_Y', player=None,
                                           xyz=cd['xyz'],
                                           ypr=(0.0, float(pitch), float(roll)),
                                           fov=(pitch_fov, None), size=cd['size'],
                                           source='probe', pixels={l: tuple(px)})
                            yp.calibrate_yaw(l, lm_point=md.landmarks[l])
                            yaws.append(float(yp.yaw))
                        except Exception:
                            continue
                    if yaws:
                        rad = [_math.radians(y) for y in yaws]
                        yaw = _math.degrees(_math.atan2(
                            sum(map(_math.sin, rad)), sum(map(_math.cos, rad)))) % 360
                        yaw_spread = max(abs((y - yaw + 180) % 360 - 180) for y in yaws)
                        n_yaw = len(yaws)
                self.send_json({'ok': True, 'roll': round(float(roll), 4),
                                'pitch': round(float(pitch), 4) if pitch is not None else None,
                                'hfov': round(solved_fov, 4) if solved_fov else None,
                                'yaw': round(yaw, 4) if yaw is not None else None,
                                'yaw_spread': round(yaw_spread, 3) if yaw_spread is not None else None,
                                'n_yaw_lms': n_yaw,
                                'n_vlines': len(cur[1]), 'n_hlines': len(cur[0])})
            except Exception as e:
                import traceback; traceback.print_exc()
                self.send_json({'error': str(e)}, 500)

        elif path == '/api/save':
            cam_name = unquote(qs.get('cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400)
                return
            xyz = [float(qs['x'][0]), float(qs['y'][0]), float(qs['z'][0])]
            # V1-ROLL: parse roll from query string (defaults to 0 for backward compat)
            ypr = [float(qs['yaw'][0]), float(qs['pitch'][0]),
                   float(qs.get('roll', ['0.0'])[0])]
            hfov_val = float(qs['hfov'][0])
            md.update_camera(cam_name, xyz, ypr, [hfov_val, None])
            ml.get_camera.cache_clear()
            print(f"Saved {cam_name}")
            self.send_json({'ok': True})

        elif path == '/api/update_landmarks':
            # [DECOM-V1] Decommissioned: triangulation = tools/triangulate_lm.py
            self.send_json({'error': 'decommissioned — use tools/triangulate_lm.py'}, 410)

        elif path == '/api/lm_map_crop':
            # [MAP-EVIDENCE-V1] yanis V13 crop centered on the LM. Cyan crosshair
            # = current xyz; optional orange crosshair (x2,y2) = proposed position.
            lm_name = unquote(qs.get('lm', [''])[0])
            xyz = md.landmarks.get(lm_name)
            if xyz is None:
                self.send_json({'error': 'LM without xyz'}, 404); return
            import sys as _sys, io as _io2, math as _m2
            if TOOL_DIR not in _sys.path: _sys.path.insert(0, TOOL_DIR)
            from map_validate import crop_at, MPPX
            from PIL import ImageDraw as _ImageDraw
            wx, wy = xyz[0], xyz[1]
            x2 = qs.get('x2', [None])[0]; y2 = qs.get('y2', [None])[0]
            half = 80.0
            cx, cy = wx, wy
            if x2 is not None and y2 is not None:
                x2, y2 = float(x2), float(y2)
                cx, cy = (wx + x2) / 2, (wy + y2) / 2
                half = max(80.0, _m2.hypot(x2 - wx, y2 - wy) / 2 + 50)
            img = crop_at(cx, cy, half)
            if img is None:
                self.send_json({'error': 'off-map / tiles unavailable'}, 404); return
            d = _ImageDraw.Draw(img)
            def _cross(wxp, wyp, col):
                px = img.width / 2 + (wxp - cx) / MPPX
                py = img.height / 2 - (wyp - cy) / MPPX
                g, L = 10, 26
                for seg in [((px-L,py),(px-g,py)),((px+g,py),(px+L,py)),((px,py-L),(px,py-g)),((px,py+g),(px,py+L))]:
                    d.line(seg, fill=col, width=2)
            # crop_at already draws the CENTER crosshair; if x2 is present the
            # center is the midpoint -> redraw both points explicitly
            if x2 is not None:
                _cross(wx, wy, (0, 230, 255))
                _cross(x2, y2, (245, 158, 11))
            sz = 300
            img = img.resize((sz, sz))
            buf = _io2.BytesIO(); img.save(buf, 'JPEG', quality=82)
            data = buf.getvalue()
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)

        elif path == '/api/map_verdict':
            # [MAP-EVIDENCE-V1] read/write a LM's map-evidence verdict
            lm_name = unquote(qs.get('lm', [''])[0])
            status = qs.get('status', [''])[0]
            import sys as _sys
            if TOOL_DIR not in _sys.path: _sys.path.insert(0, TOOL_DIR)
            from map_validate import load_validated, save_validated
            cur = load_validated()
            if status in ('validated', 'rejected'):
                from datetime import date as _date
                cur[lm_name] = {'status': status, 'date': _date.today().isoformat()}
                save_validated(cur)
            elif status == 'clear':
                cur.pop(lm_name, None)
                save_validated(cur)
            self.send_json({'lm': lm_name, 'verdict': (cur.get(lm_name) or {}).get('status')})

        elif path == '/api/fit_minimal':
            # [PANEL-V2] fit ypr(+roll)+fov with xyz LOCKED at the CLIENT's
            # (possibly unsaved) values. Returns the fitted pose WITHOUT
            # writing — the user reviews residuals then Saves normally.
            cam_name = unquote(qs.get('cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'unknown cam'}, 404); return
            try:
                cx = float(qs.get('x', [''])[0]); cy = float(qs.get('y', [''])[0])
                cz = float(qs.get('z', [''])[0])
            except (ValueError, IndexError):
                self.send_json({'error': 'x, y, z required'}, 400); return
            solve_roll = qs.get('roll', ['0'])[0] == '1'
            sys.path.insert(0, TOOL_DIR)
            import fit_minimal as fm
            obs = fm.gather_obs(cam_name)
            if len(obs) < 2:
                self.send_json({'error': f'only {len(obs)} triangulated marking(s) — need >= 2'}, 400)
                return
            saved = dict(md.cameras[cam_name])
            try:
                st = dict(saved)
                st['xyz'] = [cx, cy, cz]
                # init ypr/fov from client too when provided
                try:
                    st['ypr'] = [float(qs.get('yaw', [saved['ypr'][0]])[0]),
                                 float(qs.get('pitch', [saved['ypr'][1]])[0]),
                                 float(qs.get('rollv', [saved['ypr'][2]])[0])]
                except (ValueError, TypeError):
                    pass
                md.cameras[cam_name] = st
                ypr, fov_val, res = fm.fit(cam_name, obs, solve_roll)
                # effective hfov at the fitted state
                _idx, _ = fm.fov_slot(md.cameras[cam_name])
                cam_fit = fm.make_cam(cam_name, ypr, fov_val)
                self.send_json({'ok': True,
                                'ypr': [round(float(v), 4) for v in ypr],
                                'hfov': round(float(cam_fit.hfov), 4),
                                'residuals': sorted([{'lm': ln, 'arcmin': (None if r == float('inf') else round(r, 2))}
                                                     for r, ln in res], key=lambda x: -(x['arcmin'] or 1e9)),
                                'n_obs': len(obs)})
            finally:
                md.cameras[cam_name] = saved
                try:
                    ml.get_camera.cache_clear()
                except Exception:
                    pass

        elif path == '/api/triage':
            # [TRIAGE-V1] Per-cam categorization with a recommended action.
            # Reproduces the 2026-07-01 polish workflow: isolated-outlier
            # (CC9 pattern) / spread error / under-determined, with estimated gain.
            import math as _m
            zone_filter = unquote(qs.get('zone', [''])[0])
            _excl_path = os.path.join(os.path.dirname(TOOL_DIR), 'gtamapdata', 'excluded_markings.json')
            try:
                with open(_excl_path) as _f:
                    _excl = json.load(_f)
            except Exception:
                _excl = {}
            _tiers_path = os.path.join(TOOL_DIR, 'generated', 'confidence_tiers.json')
            _lm_tiermeta, _zones = {}, {}
            try:
                with open(_tiers_path) as _f:
                    _t = json.load(_f)
                _lm_tiermeta = _t.get('landmarks', {})
            except Exception:
                pass

            def _residuals(cn):
                try:
                    _cam = ml.get_camera(cn)
                except Exception:
                    return None
                if _cam.xyz is None:
                    return None
                out = []
                for _ln, _px in md.pixels.get(cn, {}).items():
                    if _px is None: continue
                    if _ln in (_excl.get(cn) or []): continue
                    _xyz = md.landmarks.get(_ln)
                    if _xyz is None: continue
                    try:
                        _p = _cam.get_pixel(_xyz)
                    except Exception:
                        continue
                    if _p is None: continue
                    _dx = (_p[0]-_px[0]) * _cam.hfov / _cam.w * 60
                    _dy = (_p[1]-_px[1]) * _cam.vfov / _cam.h * 60
                    out.append((_m.hypot(_dx, _dy), _ln))
                return out

            rows = []
            for cn, cd in md.cameras.items():
                if not cd.get('xyz'): continue
                res = _residuals(cn)
                if not res: continue
                res.sort(reverse=True)
                vals = [r[0] for r in res]
                _rms = _m.sqrt(sum(v*v for v in vals)/len(vals))
                if _rms <= 5.0: continue
                n = len(vals)
                worst, worst_lm = res[0]
                med_o = sorted(vals[1:])[len(vals[1:])//2] if n > 1 else 0
                if n <= 3:
                    cat, action, gain = 'under-determined', 'mark (Assist mode)', None
                    detail = f'only {n} obs'
                elif med_o > 0 and worst > max(10.0, 5*med_o):
                    # is the LM itself rotten everywhere? -> quarantine instead
                    _lmm = _lm_tiermeta.get(worst_lm, {})
                    _lm_med = _lmm.get('median_res') or 0
                    _lm_anchor = (_lmm.get('tier') == 'anchor'
                                  or (_lmm.get('n_leak_sources') or 0) >= 2)
                    _mv = {}
                    _mv_path = os.path.join(os.path.dirname(TOOL_DIR), 'gtamapdata', 'map_validated.json')
                    if os.path.exists(_mv_path):
                        try:
                            with open(_mv_path) as _f:
                                _mv = json.load(_f)
                        except Exception:
                            _mv = {}
                    _lm_mapok = (_mv.get(worst_lm) or {}).get('status') == 'validated'
                    rms_sans = _m.sqrt(sum(v*v for v in vals[1:])/max(1, n-1))
                    gain = round(_rms - rms_sans, 1)
                    if _lm_anchor:
                        # anchor/leak = ground truth: if the cam contradicts it,
                        # the CAM is the broken one (Diner/Bay pattern)
                        cat, action, gain = 'spread error', 'refine (per class) — contradicts an anchor', None
                        detail = f'"{worst_lm}" (ANCHOR) {worst:.0f}\' -> cam pose suspect'
                    elif _lm_mapok:
                        cat, action = 'markings to review', 'open the frames in the UI (map-validated LM)'
                        detail = f'"{worst_lm}" {worst:.0f}\' but map-validated position'
                    elif _lm_med and _lm_med > 30:
                        cat, action = 'phantom LM', 'quarantine LM'
                        detail = f'"{worst_lm}" {worst:.0f}\' here, median {_lm_med:.0f}\' everywhere'
                    else:
                        cat, action = 'isolated outlier', 'exclude marking'
                        detail = f'"{worst_lm}" {worst:.0f}\' vs median of others {med_o:.1f}\''
                else:
                    cat, action, gain = 'spread error', 'refine (per class)', None
                    detail = f'worst {worst:.0f}\', median of others {med_o:.1f}\''
                rows.append({'cam': cn, 'rms': round(_rms, 1), 'n_obs': n,
                             'categorie': cat, 'action': action, 'detail': detail,
                             'worst_lm': worst_lm, 'gain_estime': gain})
            _order = {'phantom LM': 0, 'isolated outlier': 1, 'markings to review': 2, 'spread error': 3, 'under-determined': 4}
            rows.sort(key=lambda r: (_order.get(r['categorie'], 9), -(r['gain_estime'] or r['rms'])))
            # [FOSSIL-SCAN-V1] LMs rejected by their own source cams
            try:
                from common import find_fossils
                _fossils = find_fossils()
            except Exception:
                _fossils = []
            self.send_json({'rows': rows, 'n': len(rows), 'fossils': _fossils})

        elif path == '/api/exclude_marking':
            # [TRIAGE-V1] action: exclude a marking (same format as
            # tools/exclude_marking.py)
            _cam = unquote(qs.get('cam', [''])[0])
            _lm = unquote(qs.get('lm', [''])[0])
            if not _cam or not _lm:
                self.send_json({'error': 'cam and lm required'}, 400); return
            _excl_path = os.path.join(os.path.dirname(TOOL_DIR), 'gtamapdata', 'excluded_markings.json')
            try:
                with open(_excl_path) as _f:
                    _d = json.load(_f)
            except Exception:
                _d = {}
            _e = _d.setdefault(_cam, [])
            if _lm not in _e:
                _e.append(_lm)
            with open(_excl_path, 'w') as _f:
                json.dump(_d, _f, indent=2, ensure_ascii=True)
                _f.write('\n')
            self.send_json({'ok': True, 'excluded': [_cam, _lm]})

        elif path == '/api/quarantine_lm':
            # [TRIAGE-V1] action: null the xyz of a known-wrong LM (markings
            # remain in pixels.json for future retriangulation)
            _lm = unquote(qs.get('lm', [''])[0])
            if _lm not in md.landmarks_meta and md.landmarks.get(_lm) is None:
                self.send_json({'error': 'unknown LM or already without xyz'}, 400); return
            md.update_landmark(_lm, None, source_cameras=[], error_m=None)
            self.send_json({'ok': True, 'quarantined': _lm})

        elif path == '/api/suspicious':
            # Find outlier pixels by consensus across cams
            import math as _math

            def _proj_err(cam_data, lm_xyz, marked):
                xyz = cam_data.get('xyz')
                ypr = cam_data.get('ypr')
                fov = cam_data.get('fov')
                size = cam_data.get('size')
                if not all([xyz, ypr, fov, size]): return None
                if not fov[0]: return None
                cx,cy,cz = xyz
                yaw = _math.radians(ypr[0])
                pitch = _math.radians(ypr[1])
                hfov_r = _math.radians(fov[0])
                w,h = size
                vfov_r = 2*_math.atan(_math.tan(hfov_r/2)*h/w)
                dx,dy,dz = lm_xyz[0]-cx, lm_xyz[1]-cy, lm_xyz[2]-cz
                rx = dx*_math.cos(-yaw) - dy*_math.sin(-yaw)
                ry = dx*_math.sin(-yaw) + dy*_math.cos(-yaw)
                ry2 = ry*_math.cos(-pitch) - dz*_math.sin(-pitch)
                rz2 = ry*_math.sin(-pitch) + dz*_math.cos(-pitch)
                if ry2 <= 0: return None
                ppx = w/2 + (rx/ry2)*(w/2)/_math.tan(hfov_r/2)
                ppy = h/2 - (rz2/ry2)*(h/2)/_math.tan(vfov_r/2)
                err = _math.sqrt(((ppx-marked[0])*fov[0]/w)**2 + ((ppy-marked[1])*fov[0]/h)**2)*60
                return round(err, 2)

            # Find landmarks seen by 3+ calibrated cams
            multi = {}
            for cn, cp in md.pixels.items():
                if not md.cameras.get(cn, {}).get('xyz'): continue
                for ln in cp:
                    if ln not in multi: multi[ln] = []
                    multi[ln].append(cn)
            multi3 = {k:v for k,v in multi.items() if len(v) >= 3}

            outliers = []
            for lm_name, cam_list in multi3.items():
                lm_xyz = md.landmarks.get(lm_name)
                if not lm_xyz: continue
                errors = []
                for cn in cam_list:
                    err = _proj_err(md.cameras[cn], lm_xyz, md.pixels[cn][lm_name])
                    if err is not None:
                        errors.append({'cam': cn, 'err': err})
                if len(errors) < 3: continue
                avg = sum(e['err'] for e in errors) / len(errors)
                for e in errors:
                    # V2: relaxed threshold for cams whose xyz is HUD-locked
                    # observing an xyz-anchored landmark (both endpoints
                    # are ground truth, so the cam alignment is more
                    # trustworthy than its projection-residual would suggest).
                    if lm_name in XYZ_ANCHORED_LMS:
                        threshold = 3 if e['cam'] not in LOCKED_XYZ_CAMS else 999
                    else:
                        threshold = max(avg * 3, 10)
                    if e['err'] > threshold:
                        outliers.append({
                            'lm_name': lm_name,
                            'cam_name': e['cam'],
                            'err': e['err'],
                            'avg_err': round(avg, 2),
                            'n_cams': len(errors),
                        })

            # Tag xyz-anchored outliers (kept as `leak_anchored` for JSON
            # back-compat with the UI; semantics is "LM triangulated from
            # 2+ HUD-locked cams").
            for o in outliers:
                o['leak_anchored'] = o['lm_name'] in XYZ_ANCHORED_LMS

            outliers.sort(key=lambda x: x['err'], reverse=True)
            # Separate xyz-anchored (ground truth) from regular
            leak_outliers = [o for o in outliers if o['leak_anchored']]
            self.send_json({
                'outliers': outliers[:50],
                'leak_outliers': leak_outliers[:50],
                'n_leak_anchored': len(leak_outliers),
            })

        elif path == '/api/set_pixel':
            cam_name = unquote(qs.get('cam', [''])[0])
            lm_name  = unquote(qs.get('lm',  [''])[0])
            px_x = float(qs['px'][0])
            px_y = float(qs['py'][0])

            if cam_name not in md.pixels:
                self.send_json({'error': 'invalid cam'}, 400); return
            if lm_name not in md.pixels.get(cam_name, {}):
                self.send_json({'error': 'landmark not in cam pixels'}, 400); return

            # Update pixels.json
            px_path = os.path.join(DATA_DIR, 'pixels.json')
            with open(px_path) as f:
                px_data = json.load(f)
            px_data[cam_name][lm_name] = [px_x, px_y]
            tmp = px_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(px_data, f, indent=2)
            os.replace(tmp, px_path)
            # Update in-memory
            md.pixels[cam_name][lm_name] = (px_x, px_y)
            ml.get_camera.cache_clear()
            print(f"Set pixel {lm_name} in {cam_name}: ({px_x}, {px_y})")
            self.send_json({'ok': True})

        elif path == '/api/set_class':
            cam_name = unquote(qs.get('cam', [''])[0])
            new_class = unquote(qs.get('class', [''])[0])
            from leak_cam_audit import VALID_CLASSES
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400); return
            if new_class not in VALID_CLASSES:
                self.send_json({'error': 'invalid class', 'valid': sorted(VALID_CLASSES)}, 400); return
            audit_path = os.path.join(DATA_DIR, 'leak_cam_audit.json')
            with open(audit_path) as f:
                audit = json.load(f)
            entry = audit.get(cam_name, {})
            entry['constraint_class'] = new_class
            entry.setdefault('has_debug_hud', True)
            audit[cam_name] = entry
            tmp = audit_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(audit, f, indent=2)
            os.replace(tmp, audit_path)
            print(f"Set class {cam_name}: {new_class}")
            self.send_json({'ok': True, 'cam': cam_name, 'class': new_class,
                            'note': 'Re-run compute_confidence_tiers.py to apply.'})

        elif path == '/api/heatmap_data':
            # Return all landmarks with xyz, error, zone for heatmap
            result = []
            for lm_name, xyz in md.landmarks.items():
                if xyz is None: continue
                meta = md.landmarks_meta.get(lm_name, {})
                result.append({
                    'name': lm_name,
                    'x': float(xyz[0]),
                    'y': float(xyz[1]),
                    'z': float(xyz[2]),
                    'error_m': meta.get('error_m'),
                    'zone': meta.get('zone', 'unknown'),
                    'source_cameras': meta.get('source_cameras', []),
                })
            # Also include cameras
            cams = []
            for cam_name, data in md.cameras.items():
                if not data.get('xyz'): continue
                cams.append({
                    'name': cam_name,
                    'x': float(data['xyz'][0]),
                    'y': float(data['xyz'][1]),
                    'source': data.get('source', ''),
                    'has_pixels': cam_name in md.pixels,
                })
            self.send_json({'landmarks': result, 'cameras': cams})

        elif path == '/api/all_landmarks':
            # Return all landmark names that have xyz
            names = sorted(md.landmarks.keys())
            self.send_json({'landmarks': names})

        elif path == '/api/add_pixel':
            cam_name = unquote(qs.get('cam', [''])[0])
            lm_name  = unquote(qs.get('lm',  [''])[0])
            px_x = float(qs['px'][0])
            px_y = float(qs['py'][0])
            is_new = qs.get('new', ['0'])[0] == '1'

            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400); return

            # Create new landmark entry if needed
            if is_new and md.landmarks.get(lm_name) is None:
                md.update_landmark(lm_name, None, source_cameras=[], error_m=None, zone='unknown')
                print(f"Created new landmark: {lm_name}")

            px_path = os.path.join(DATA_DIR, 'pixels.json')
            with open(px_path) as f:
                px_data = json.load(f)
            if cam_name not in px_data:
                px_data[cam_name] = {}
            px_data[cam_name][lm_name] = [px_x, px_y]
            tmp = px_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(px_data, f, indent=2)
            os.replace(tmp, px_path)
            if cam_name not in md.pixels:
                md.pixels[cam_name] = {}
            md.pixels[cam_name][lm_name] = (px_x, px_y)
            ml.get_camera.cache_clear()
            print(f"Added pixel {lm_name} in {cam_name}: ({px_x}, {px_y})")
            self.send_json({'ok': True, 'is_new': is_new})

        elif path == '/api/triangulate':
            lm_name = unquote(qs.get('lm', [''])[0])
            # Find all cams that see this landmark and are calibrated
            source_cams = []
            for cn, cp in md.pixels.items():
                if lm_name not in cp: continue
                if not md.cameras.get(cn, {}).get('xyz'): continue
                source_cams.append(cn)

            if len(source_cams) < 2:
                self.send_json({'error': f'Need 2+ calibrated cams, found {len(source_cams)}'}, 400)
                return

            # Try all pairs and pick best (lowest distance)
            best = None
            for i in range(len(source_cams)):
                for j in range(i+1, len(source_cams)):
                    try:
                        result = ml.find_landmark(source_cams[i], source_cams[j], lm_name)
                        if result is None: continue
                        pt, _, _, d, _ = result
                        if best is None or d < best['error_m']:
                            best = {
                                'xyz': [round(float(v), 4) for v in pt],
                                'error_m': round(float(d), 3),
                                'cam_a': source_cams[i],
                                'cam_b': source_cams[j],
                                'n_cams': len(source_cams),
                            }
                    except Exception as e:
                        pass

            if best is None:
                self.send_json({'error': 'Triangulation failed'}, 400)
                return

            # Save to landmarks. update_landmark() snaps xyz[2] if z_constraint
            # [MAP-EVIDENCE-V1] dry=1: return the proposal without writing
            if qs.get('dry', [''])[0] == '1':
                best['dry'] = True
                self.send_json(best)
                return
            # is set on this landmark (single source of truth — see gtamapdata.py).
            meta = md.landmarks_meta.get(lm_name, {})
            md.update_landmark(lm_name, best['xyz'],
                source_cameras=source_cams,
                error_m=best['error_m'],
                zone=meta.get('zone', 'unknown'))
            # Reflect snap in the response so frontend shows the correct xyz
            zc = meta.get('z_constraint')
            if zc and zc.get('type') == 'fixed':
                best['xyz'][2] = round(float(zc['value']), 4)
                best['z_snapped'] = True
            ml.get_camera.cache_clear()
            print(f"Triangulated {lm_name}: xyz={best['xyz']}, err={best['error_m']}m")
            self.send_json(best)

        elif path == '/api/cam_sources':
            # For a landmark, return all cams that see it and are calibrated
            lm_name = unquote(qs.get('lm', [''])[0])
            sources = []
            for cn, cp in md.pixels.items():
                if lm_name not in cp: continue
                if not md.cameras.get(cn, {}).get('xyz'): continue
                sources.append(cn)
            self.send_json({'cams': sources})

        # Phase 8.2: /api/ray_map removed. Triangulation viz now lives
        # in the Map view (Phase 8.1: showTriangulationOnMap in calib.html).

        elif path == '/api/delete_pixel':
            cam_name = unquote(qs.get('cam', [''])[0])
            lm_name  = unquote(qs.get('lm',  [''])[0])
            if cam_name not in md.pixels or lm_name not in md.pixels.get(cam_name, {}):
                self.send_json({'error': 'not found'}, 400); return
            px_path = os.path.join(DATA_DIR, 'pixels.json')
            with open(px_path) as f:
                px_data = json.load(f)
            del px_data[cam_name][lm_name]
            tmp = px_path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(px_data, f, indent=2)
            os.replace(tmp, px_path)
            del md.pixels[cam_name][lm_name]
            ml.get_camera.cache_clear()
            # [PROVENANCE-V1] keep landmarks_meta coherent: a deleted marking
            # removes this cam from the LM's source_cameras; if no source
            # remains, the xyz is a fossil-blind-spot orphan -> quarantine.
            prov_note = None
            meta = md.landmarks_meta.get(lm_name)
            if meta and cam_name in (meta.get('source_cameras') or []):
                new_src = [c for c in meta['source_cameras'] if c != cam_name]
                if new_src:
                    md.update_landmark(lm_name, md.landmarks.get(lm_name),
                                       source_cameras=new_src,
                                       error_m=meta.get('error_m'))
                    prov_note = f'source dropped ({len(new_src)} left)'
                else:
                    md.update_landmark(lm_name, None, source_cameras=[], error_m=None)
                    prov_note = 'orphaned -> quarantined (xyz=None)'
                print(f"Provenance: {lm_name}: {prov_note}")
            print(f"Deleted pixel {lm_name} from {cam_name}")
            self.send_json({'ok': True, 'provenance': prov_note})

        elif path == '/api/validate_pixel':
            # Just acknowledge — validation state is kept client-side
            self.send_json({'ok': True})

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
            # [MINIMAP-THREADLOCK-V1] hold the lock across get_camera +
            # cache-path + render + read, so concurrent requests can't corrupt
            # the lru_cache or read a file mid-write.
            _MINIMAP_LOCK.acquire()
            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                _MINIMAP_LOCK.release()
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return
            cache_path = _minimap_cache_path(cam_name)
            # [MINIMAP-STALE-V1] The cache was only rendered when the file was
            # ABSENT — so moving/recalibrating a cam left its minimap centered
            # on the OLD position forever. Re-render when cameras.json is newer
            # than the cached PNG (the freshness rule the comment always claimed
            # but the code had lost in the lazy-render refactor).
            _cam_json = os.path.join(DATA_DIR, 'cameras.json')
            _stale = False
            try:
                if os.path.exists(cache_path) and os.path.exists(_cam_json):
                    _stale = os.path.getmtime(_cam_json) > os.path.getmtime(cache_path)
            except OSError:
                _stale = True
            if not os.path.exists(cache_path) or _stale:
                try:
                    _render_minimap_for_cam(cam_name)
                except Exception:
                    pass
            if not os.path.exists(cache_path):
                _MINIMAP_LOCK.release()
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
            finally:
                try:
                    _MINIMAP_LOCK.release()
                except RuntimeError:
                    pass   # already released on an error path

        elif path == '/api/other_cams_overlay':
            cam_name = qs.get('cam', [''])[0]
            if not cam_name or cam_name not in md.cameras:
                self.send_json({'error': 'unknown cam'}, 400)
                return
            try:
                xyz = json.loads(qs.get('xyz', ['null'])[0])
                ypr = json.loads(qs.get('ypr', ['null'])[0])
                hfov = qs.get('hfov', [None])[0]
                hfov = float(hfov) if hfov is not None else None
            except (ValueError, TypeError):
                xyz, ypr, hfov = None, None, None
            types_str = qs.get('types', ['leak,trailer,screenshot'])[0]
            types = set(t.strip() for t in types_str.split(',') if t.strip())
            try:
                max_dist = float(qs.get('max_dist', ['5000'])[0])
            except ValueError:
                max_dist = 5000.0
            shared_only = qs.get('shared_only', ['0'])[0] in ('1', 'true')

            try:
                cam = get_cam(cam_name, xyz, ypr, hfov)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 500)
                return

            candidates = _candidates_for(cam_name, types, max_dist, shared_only)
            d = 25  # frustum extension

            cones = []
            # Reject points outside (or just barely outside) the image —
            # get_pixel returns aberrant coords for points behind the viewer.
            # The cone must overlap the visible image to be useful.
            margin = max(cam.w, cam.h) * 0.1  # 10% overflow tolerance
            def _onscreen(p):
                if p is None: return False
                x, y = p
                return -margin < x < cam.w + margin and -margin < y < cam.h + margin

            def _quad_overlaps_image(apex, corners):
                """At least one of apex or corners must be inside the image."""
                pts = [apex] + list(corners)
                for p in pts:
                    if p is None: continue
                    x, y = p
                    if 0 <= x <= cam.w and 0 <= y <= cam.h:
                        return True
                return False

            for other_name, dist in candidates:
                other = md.cameras.get(other_name, {})
                other_xyz = other.get('xyz')
                if not other_xyz:
                    continue
                try:
                    other_cam = ml.get_camera(other_name)
                    apex = cam.get_pixel(other_xyz)
                    if not _onscreen(apex):
                        continue
                    corners_3d = [
                        ml.get_point(other_cam.xyz, other_cam.get_pixel_direction((0, 0)), d),
                        ml.get_point(other_cam.xyz, other_cam.get_pixel_direction((other_cam.w, 0)), d),
                        ml.get_point(other_cam.xyz, other_cam.get_pixel_direction((other_cam.w, other_cam.h)), d),
                        ml.get_point(other_cam.xyz, other_cam.get_pixel_direction((0, other_cam.h)), d),
                    ]
                    corners_2d = [cam.get_pixel(c) for c in corners_3d]
                    if not all(_onscreen(c) for c in corners_2d):
                        continue
                    if not _quad_overlaps_image(apex, corners_2d):
                        continue
                    color = list(int(v) for v in other_cam.color)
                    cones.append({
                        'name': other_name,
                        'type': _classify_cam(other_name),
                        'dist_m': round(float(dist), 1),
                        'color': color,
                        'apex': [round(float(apex[0]), 2), round(float(apex[1]), 2)],
                        'corners': [[round(float(c[0]), 2), round(float(c[1]), 2)]
                                    for c in corners_2d],
                    })
                except Exception:
                    continue

            self.send_json({
                'cam': cam_name,
                'cones': cones,
                'n_candidates': len(candidates),
                'n_visible': len(cones),
            })

        elif path.startswith('/frame/'):
            cam_name = unquote(path[7:])
            img_path = os.path.join(FRAMES_DIR, f"{cam_name}.png")
            if os.path.exists(img_path):
                self.send_file(img_path, 'image/png')
            else:
                self.send_response(404)
                self.end_headers()

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == '__main__':
    port = 8765
    server = ThreadingHTTPServer(('localhost', port), Handler)
    print(f"\n🗺  gtamaplib Calibration Tool")
    print(f"   http://localhost:{port}")
    print(f"   Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
