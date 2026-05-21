#!/usr/bin/env python3
"""
gtamaplib Calibration Tool — server.py
Run: python3 server.py
Open: http://localhost:8765
"""

import json
import math
import os
import re
import sys
# Threading fix: parallel request handling
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

GTAMAP_DIR = os.path.expanduser("~/Downloads/gtamaplib-main")
DATA_DIR = os.path.join(GTAMAP_DIR, "gtamapdata")
FRAMES_DIR = os.path.join(GTAMAP_DIR, "frames")
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TOOL_DIR)
# [TILES-V1] gtadb.org tile checkout (sparse, vendored, gitignored).
# Tiles are 256x256 JPGs at /vendor/gtadb.org/maps/tiles/6/yanis,12/{z}/{z},{y},{x}.jpg
# 7 zoom levels (0-6). Served via /tiles/{z}/{filename} route.
TILES_DIR = os.path.join(REPO_ROOT, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,12')

sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

print("gtamaplib loaded ✓")

# Leak-anchored landmarks: triangulated from 2+ leak cams — positions are ground truth
import re as _re
LEAK_CAMS = {n for n, d in md.cameras.items() if d.get('source') and _re.match(r'\d{4}-\d{2}-\d{2}', d['source'])}
LEAK_ANCHORED_LMS = {
    lm for lm, meta in md.landmarks_meta.items()
    if md.landmarks.get(lm) is not None
    and len([c for c in meta.get('source_cameras', []) if c in LEAK_CAMS]) >= 2
}
print(f"Leak cams: {len(LEAK_CAMS)} · Leak-anchored landmarks: {len(LEAK_ANCHORED_LMS)}")


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
os.makedirs(_MINIMAP_CACHE_DIR, exist_ok=True)
_MINIMAP_RADIUS_M = 350.0
_MINIMAP_SIZE_PX = 480

def _minimap_safe_name(cam_name):
    return ''.join(c if c.isalnum() else '_' for c in cam_name)

def _minimap_cache_path(cam_name):
    return os.path.join(_MINIMAP_CACHE_DIR, f'{_minimap_safe_name(cam_name)}.png')

def _render_minimap_for_cam(cam_name):
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
        return None


# ── Item 4 : "Other cams" overlay (canvas-based, no image rendering) ─────────

def _classify_cam(cam_name):
    """Returns 'leak' | 'trailer' | 'screenshot'."""
    src = md.cameras.get(cam_name, {}).get('source', '') or ''
    if _re.match(r'\d{4}-\d{2}-\d{2}', src): return 'leak'
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

        elif path == '/cam_health.html':
            self.send_file(os.path.join(TOOL_DIR, 'cam_health.html'), 'text/html')

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
            # [TILES-V1] Serve tile JPGs from vendor/gtadb.org/maps/tiles/6/yanis,12/
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

        elif path == '/api/cameras':
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
                    'has_image': has_image,
                    'n_pixels': len(cam_pixels),
                    'n_independent': n_indep,
                    'xyz': list(data['xyz']) if data.get('xyz') else None,
                    'ypr': list(data['ypr']) if data.get('ypr') else None,
                    'fov': list(data['fov']) if data.get('fov') else None,
                    'size': list(data['size']) if data.get('size') else None,
                    'source': data.get('source'),
                    'is_leak': bool(__import__('re').match(r'\d{4}-\d{2}-\d{2}', data.get('source') or '')),
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

        elif path == '/api/cam_health':
            # Per-cam health metrics. Reuses compute_projections to get
            # angular residuals from the current calibration state.
            import statistics
            import re as _re_local
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
                is_leak = bool(_re_local.match(r'\d{4}-\d{2}-\d{2}', source))
                if is_leak:
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
            cam_name = unquote(qs.get('cam', [''])[0])
            xyz = [float(qs['x'][0]), float(qs['y'][0]), float(qs['z'][0])]
            # V1-ROLL: parse roll from query string (defaults to 0 for backward compat)
            ypr = [float(qs['yaw'][0]), float(qs['pitch'][0]),
                   float(qs.get('roll', ['0.0'])[0])]
            hfov = float(qs['hfov'][0])
            # LEAK-MODE-V1: optional flag — xyz and hfov frozen, only yaw/pitch/roll optimize
            leak_mode = qs.get('leak_mode', ['false'])[0].lower() == 'true'
            mode_str = " (LEAK MODE — yaw/pitch/roll only)" if leak_mode else ""
            print(f"Optimizing {cam_name}{mode_str}...")
            res, err = optimize_camera(cam_name, xyz, ypr, hfov, leak_mode=leak_mode)
            if err:
                self.send_json({'error': err}, 400)
            else:
                print(f"  loss={res['loss']} ({res['n_constraints']} constraints)")
                self.send_json(res)

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
                    projections.append({
                        'name': lm_name,
                        'type': 'point',
                        'pixel': [x, y],
                    })
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
                        projections.append({
                            'name': lm_name,
                            'type': 'epipolar',
                            'line': [[x1, y1], [x2, y2]],
                            'source_cam': src_cam_name,
                        })
                    except Exception:
                        continue

            self.send_json({
                'cam': cam_name,
                'cam_size': [target_w, target_h],
                'projections': projections,
            })

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
            UPDATE_LMS_LOSS_THRESHOLD = 10.0  # arcmin — refuse if cam loss exceeds this
            cam_name = unquote(qs.get('cam', [''])[0])
            xyz = [float(qs['x'][0]), float(qs['y'][0]), float(qs['z'][0])]
            # V1-ROLL: parse roll from query string (defaults to 0 for backward compat)
            ypr = [float(qs['yaw'][0]), float(qs['pitch'][0]),
                   float(qs.get('roll', ['0.0'])[0])]
            hfov_val = float(qs['hfov'][0])

            # Safety: refuse if cam loss is too high. A high-loss cam in a bad
            # local minimum will propagate garbage to its observed landmarks.
            try:
                _projs, _losses = compute_projections(cam_name, xyz, ypr, hfov_val)
                _check_loss = _losses.get('independent') if _losses.get('independent') is not None else _losses.get('total')
                if _check_loss is not None and _check_loss > UPDATE_LMS_LOSS_THRESHOLD:
                    self.send_json({
                        'error': f"Cam loss too high ({_check_loss:.2f}' > {UPDATE_LMS_LOSS_THRESHOLD}'). "
                                 f"Refine the cam first or use bundle adjust to avoid propagating errors to landmarks.",
                        'loss': _check_loss,
                        'threshold': UPDATE_LMS_LOSS_THRESHOLD,
                    }, 400)
                    return
            except Exception as _e:
                print(f"Warning: could not check loss before update: {_e}")

            cam = get_cam(cam_name, xyz, ypr, hfov_val)
            cam_pixels = md.pixels.get(cam_name, {})
            updated = []
            skipped = []
            errors = []

            try:
                import numpy as np
                from scipy.optimize import minimize as _minimize
            except ImportError:
                self.send_json({'error': 'scipy not installed'}, 500)
                return

            def multi_cam_triangulate(observers, lm_name, p0):
                """observers = [(cam_name, cam_obj)]. Returns (xyz, max_residual_arcmin) or None."""
                rays = []
                for cn, c in observers:
                    if lm_name not in md.pixels.get(cn, {}):
                        continue
                    d = c.get_landmark_direction(lm_name)
                    d = np.asarray(d, dtype=float)
                    d = d / np.linalg.norm(d)
                    rays.append((cn, np.asarray(c.xyz, dtype=float), d))
                if len(rays) < 2:
                    return None, "not enough rays"

                def loss(p):
                    p = np.asarray(p)
                    total = 0.0
                    for _, o, d in rays:
                        v = p - o
                        dist = np.linalg.norm(v)
                        if dist < 1e-3: continue
                        perp = v - np.dot(v, d) * d
                        ang = np.linalg.norm(perp) / dist
                        total += ang * ang
                    return total

                result = _minimize(loss, p0, method='Nelder-Mead',
                                    options={'xatol':1e-3, 'fatol':1e-12,
                                             'maxiter':10000, 'adaptive':True})

                p_new = result.x
                # Compute max residual in arcmin
                max_res = 0.0
                for _, o, d in rays:
                    v = p_new - o
                    dist = np.linalg.norm(v)
                    if dist < 1e-3: continue
                    perp = v - np.dot(v, d) * d
                    ang_arcmin = math.degrees(np.linalg.norm(perp) / dist) * 60
                    max_res = max(max_res, ang_arcmin)
                return p_new.tolist(), max_res

            for lm_name, marked_pixel in cam_pixels.items():
                src = md.landmarks_meta.get(lm_name, {}).get('source_cameras', [])
                if cam_name not in src:
                    continue  # skip independent landmarks

                other_cams_list = [s for s in src if s != cam_name]

                if not other_cams_list:
                    # Solo — project at zero elevation
                    try:
                        pt = cam.get_point_at_zero_elevation(marked_pixel)
                        if pt is not None:
                            md.update_landmark(lm_name, list(pt),
                                source_cameras=[cam_name],
                                error_m=None,
                                zone=md.landmarks_meta.get(lm_name, {}).get('zone'))
                            updated.append(lm_name)
                    except Exception as e:
                        errors.append(f"{lm_name}: {e}")
                    continue

                # Multi-cam: build observer list
                observers = [(cam_name, cam)]
                for ocn in other_cams_list:
                    if ocn not in md.cameras:
                        continue
                    observers.append((ocn, ml.get_camera(ocn)))

                # Co-location check: if all observers are within 50m of each other,
                # there's no real triangulation baseline — refuse to update.
                xs = [o[1].x for o in observers]
                ys = [o[1].y for o in observers]
                spread = max(max(xs)-min(xs), max(ys)-min(ys))
                if spread < 50:
                    skipped.append(f"{lm_name} (cams co-located within {spread:.0f}m)")
                    continue

                # Initial guess: current xyz, or compute one if missing
                cur_xyz = md.landmarks.get(lm_name)
                if cur_xyz is None:
                    pt = cam.get_point_at_zero_elevation(marked_pixel)
                    if pt is None:
                        errors.append(f"{lm_name}: no init xyz available")
                        continue
                    cur_xyz = list(pt)

                try:
                    new_xyz, max_res = multi_cam_triangulate(observers, lm_name, cur_xyz)
                    if new_xyz is None:
                        errors.append(f"{lm_name}: {max_res}")
                        continue
                    md.update_landmark(lm_name, new_xyz,
                        source_cameras=src,
                        error_m=round(float(max_res), 3),
                        zone=md.landmarks_meta.get(lm_name, {}).get('zone'))
                    updated.append(lm_name)
                except Exception as e:
                    errors.append(f"{lm_name}: {e}")

            print(f"Updated {len(updated)} landmarks for {cam_name}")
            if skipped:
                print(f"  Skipped {len(skipped)}: {skipped[:3]}")
            if errors:
                print(f"  Errors: {errors[:3]}")
            self.send_json({
                'updated': len(updated),
                'skipped': len(skipped),
                'errors': len(errors),
                'names': updated,
                'skipped_names': skipped,
            })

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
                    if lm_name in LEAK_ANCHORED_LMS:
                        threshold = 3 if e['cam'] not in LEAK_CAMS else 999
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

            # Tag leak-anchored outliers
            for o in outliers:
                o['leak_anchored'] = o['lm_name'] in LEAK_ANCHORED_LMS

            outliers.sort(key=lambda x: x['err'], reverse=True)
            # Separate leak-anchored (ground truth) from regular
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
            print(f"Deleted pixel {lm_name} from {cam_name}")
            self.send_json({'ok': True})

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
