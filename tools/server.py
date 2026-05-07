#!/usr/bin/env python3
"""
gtamaplib Calibration Tool — server.py
Run: python3 server.py
Open: http://localhost:8765
"""

import json
import math
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, unquote

GTAMAP_DIR = os.path.expanduser("~/Downloads/gtamaplib-main")
DATA_DIR = os.path.join(GTAMAP_DIR, "gtamapdata")
FRAMES_DIR = os.path.join(GTAMAP_DIR, "frames")
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))

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


def optimize_camera(cam_name, xyz, ypr, hfov):
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

    # Build constraint set with weight info
    # weight 1.0 for independent, 0.3 for self-source (avoid trivial fit)
    constraints = []
    for lm, mp in cam_pixels.items():
        lm_xyz = md.landmarks.get(lm)
        if lm_xyz is None:
            continue
        is_self_source = cam_name in md.landmarks_meta.get(lm, {}).get('source_cameras', [])
        weight = 0.3 if is_self_source else 1.0
        constraints.append((lm, list(lm_xyz), list(mp), weight, is_self_source))

    n_total = len(constraints)
    n_indep = sum(1 for _, _, _, w, sf in constraints if not sf)
    if n_indep < 3:
        return None, f"Not enough independent landmarks ({n_indep} — need at least 3)"

    # Loss before (RMS over indep only, for human-readable comparison)
    cam_before = get_cam(cam_name, xyz, ypr, hfov)
    indep_errs = [pixel_error(cam_before, c[1], c[2]) for c in constraints if not c[4]]
    loss_before = math.sqrt(sum(e*e for e in indep_errs) / max(1, len(indep_errs)))

    x0 = np.array([xyz[0], xyz[1], xyz[2], ypr[0], ypr[1], hfov], dtype=float)

    # Residual function — returns vector of weighted angular errors (arcmin)
    def residuals(p):
        try:
            cam = get_cam(cam_name, list(p[:3]), [p[3], p[4], 0.0], float(p[5]))
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

    # Bounds: xyz ±300m, yaw ±90°, pitch ±60°, hfov 20°-130°
    lb = np.array([xyz[0]-300, xyz[1]-300, xyz[2]-50,
                   ypr[0]-90, ypr[1]-60, 20.0])
    ub = np.array([xyz[0]+300, xyz[1]+300, xyz[2]+50,
                   ypr[0]+90, ypr[1]+60, 130.0])

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
    cam_after = get_cam(cam_name, list(result.x[:3]),
                         [result.x[3], result.x[4], 0.0], float(result.x[5]))
    indep_errs_after = [pixel_error(cam_after, c[1], c[2]) for c in constraints if not c[4]]
    loss_after = math.sqrt(sum(e*e for e in indep_errs_after) / max(1, len(indep_errs_after)))

    improvement = round((loss_before - loss_after) / loss_before * 100, 1) if loss_before > 0 else 0

    return {
        'xyz': [round(float(v), 4) for v in result.x[:3]],
        'ypr': [round(float(result.x[3]), 4), round(float(result.x[4]), 4), 0.0],
        'hfov': round(float(result.x[5]), 4),
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


        elif path == '/api/generate_map':
            # Generates a top-down map showing rays from a camera to each
            # of its observed landmarks, colored by angular residual.
            cam_name = unquote(qs.get('cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400)
                return
            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return

            cam_pixels = md.pixels.get(cam_name, {})
            if not cam_pixels:
                self.send_json({'error': 'no pixels for this cam'}, 400)
                return

            # Build (lm_xyz, color) list based on angular residual
            cam_xyz = list(cam.xyz)
            rays = []
            for lm_name, marked_pixel in cam_pixels.items():
                lm_xyz = md.landmarks.get(lm_name)
                if lm_xyz is None:
                    continue
                # Angular residual
                try:
                    proj = cam.get_pixel(lm_xyz)
                    if proj is None:
                        color = (140, 140, 140)  # grey for unprojectable
                    else:
                        dx = (float(proj[0]) - marked_pixel[0]) * cam.hfov / cam.w * 60
                        dy = (float(proj[1]) - marked_pixel[1]) * cam.vfov / cam.h * 60
                        err = math.hypot(dx, dy)
                        if err < 3:
                            color = (74, 222, 128)   # green
                        elif err < 10:
                            color = (245, 158, 11)   # yellow/amber
                        else:
                            color = (248, 113, 113)  # red
                except Exception:
                    color = (140, 140, 140)
                rays.append((list(lm_xyz), color, lm_name))

            # Compute crop area: clip to a sensible radius around the cam
            # so a single distant landmark doesn't blow up the whole view.
            # Use median distance × 2.5, capped at MAX_RADIUS.
            import math as _math3
            MAX_RADIUS = 3750.0  # max half-size of view, in meters
            MIN_RADIUS = 800.0   # min, so very local cams still get context
            distances = [_math3.hypot(r[0][0] - cam_xyz[0], r[0][1] - cam_xyz[1])
                         for r in rays]
            if distances:
                distances.sort()
                # Use 75th percentile × 1.5 so we cover most rays comfortably
                # but ignore the 1-2 outlier-distance landmarks that wreck framing.
                p75 = distances[int(len(distances) * 0.75)]
                radius = max(MIN_RADIUS, min(MAX_RADIUS, p75 * 1.2))
            else:
                radius = MIN_RADIUS
            world_size = radius * 2
            cx, cy = cam_xyz[0], cam_xyz[1]
            x_min, x_max = cx - radius, cx + radius
            y_min, y_max = cy - radius, cy + radius
            area = (x_min, y_min, x_max, y_max)

            # Scale for ~1400 px on largest dimension
            target_px = 1400
            scale = target_px / world_size
            scale = max(0.05, min(0.5, scale))

            try:
                m = ml.get_map('yanis')
                m.open(scale=scale, add_padding=False)

                # Draw cam frustum bounds (FOV edges in blue)
                import math as _math
                frust_color = (96, 165, 250)  # blue, matches UI accent
                yaw_rad = _math.radians(cam.ypr[0])
                half_fov = _math.radians(cam.hfov / 2)
                # Match longest ray to landmark
                import math as _math2
                max_dist = max(
                    _math2.hypot(r[0][0] - cam_xyz[0], r[0][1] - cam_xyz[1])
                    for r in rays
                ) if rays else world_size * 0.4
                ray_len = max_dist
                for offset in [-half_fov, half_fov]:
                    ang = yaw_rad + offset
                    end_x = cam_xyz[0] - ray_len * _math.sin(ang)
                    end_y = cam_xyz[1] + ray_len * _math.cos(ang)
                    m.draw_line([(cam_xyz[0], cam_xyz[1]), (end_x, end_y)],
                                fill=frust_color, width=2)

                # Draw rays to landmarks (thinner now)
                for lm_xyz, color, lm_name in rays:
                    line = [(cam_xyz[0], cam_xyz[1]), (lm_xyz[0], lm_xyz[1])]
                    m.draw_line(line, fill=color, width=1)
                # Draw landmark markers (small)
                for lm_xyz, color, lm_name in rays:
                    try:
                        m.draw_landmark(lm_name, r=4)
                    except Exception:
                        pass
                # Draw cam (slightly smaller marker)
                m.draw_camera(cam, r=8, d=80)

                # Save
                out_dir = os.path.join(TOOL_DIR, 'generated')
                os.makedirs(out_dir, exist_ok=True)
                # Sanitize filename
                safe_name = ''.join(c if c.isalnum() else '_' for c in cam_name)
                out_path = os.path.join(out_dir, f'{safe_name}_map.png')
                m.save(out_path, crop=area)

                self.send_json({
                    'ok': True,
                    'url': f'/api/generated_map?cam={cam_name}',
                    'n_rays': len(rays),
                })
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'error': f'render failed: {e}'}, 500)

        elif path == '/api/generated_map':
            cam_name = unquote(qs.get('cam', [''])[0])
            safe_name = ''.join(c if c.isalnum() else '_' for c in cam_name)
            out_path = os.path.join(TOOL_DIR, 'generated', f'{safe_name}_map.png')
            if os.path.exists(out_path):
                self.send_file(out_path, 'image/png')
            else:
                self.send_response(404)
                self.end_headers()


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
            ypr = [float(qs['yaw'][0]), float(qs['pitch'][0]), 0.0] if 'yaw' in qs else None
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

        elif path == '/api/optimize':
            cam_name = unquote(qs.get('cam', [''])[0])
            xyz = [float(qs['x'][0]), float(qs['y'][0]), float(qs['z'][0])]
            ypr = [float(qs['yaw'][0]), float(qs['pitch'][0]), 0.0]
            hfov = float(qs['hfov'][0])
            print(f"Optimizing {cam_name}...")
            res, err = optimize_camera(cam_name, xyz, ypr, hfov)
            if err:
                self.send_json({'error': err}, 400)
            else:
                print(f"  loss={res['loss']} ({res['n_constraints']} constraints)")
                self.send_json(res)

        elif path == '/api/save':
            cam_name = unquote(qs.get('cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400)
                return
            xyz = [float(qs['x'][0]), float(qs['y'][0]), float(qs['z'][0])]
            ypr = [float(qs['yaw'][0]), float(qs['pitch'][0]), 0.0]
            hfov_val = float(qs['hfov'][0])
            md.update_camera(cam_name, xyz, ypr, [hfov_val, None])
            ml.get_camera.cache_clear()
            print(f"Saved {cam_name}")
            self.send_json({'ok': True})

        elif path == '/api/update_landmarks':
            UPDATE_LMS_LOSS_THRESHOLD = 10.0  # arcmin — refuse if cam loss exceeds this
            cam_name = unquote(qs.get('cam', [''])[0])
            xyz = [float(qs['x'][0]), float(qs['y'][0]), float(qs['z'][0])]
            ypr = [float(qs['yaw'][0]), float(qs['pitch'][0]), 0.0]
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

            # Item 3 (rlx roadmap): use closed-form N-rays solver
            # ml.intersect_rays(rays) instead of testing all 2-cam pairs.
            # Inputs: list of (origin, direction) tuples.
            # Outputs: (closest_point, distances) where distances[i] is the
            # perpendicular distance from ray[i] to the closest_point.
            try:
                rays = []
                used_cams = []
                for cn in source_cams:
                    cam = ml.get_camera(cn)
                    direction = cam.get_landmark_direction(lm_name)
                    rays.append((tuple(cam.xyz), tuple(direction)))
                    used_cams.append(cn)

                pt, distances = ml.intersect_rays(rays)
                # error_m = mean perpendicular distance across all rays
                # (gives a "how well do these rays converge" metric similar to
                # find_landmark's pair distance, but using all rays at once)
                error_m = float(distances.mean())
                # max distance per ray = useful for outlier identification
                worst_idx = int(distances.argmax())
                best = {
                    'xyz': [round(float(v), 4) for v in pt],
                    'error_m': round(error_m, 3),
                    'worst_cam': used_cams[worst_idx],
                    'worst_distance_m': round(float(distances[worst_idx]), 3),
                    'n_cams': len(used_cams),
                    'method': 'intersect_rays',
                }
            except Exception as e:
                self.send_json({'error': f'Triangulation failed: {e}'}, 400)
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
            print(f"Triangulated {lm_name}: xyz={best['xyz']}, "
                  f"err={best['error_m']}m (worst: {best['worst_cam']} "
                  f"@ {best['worst_distance_m']}m)")
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

        elif path == '/api/ray_map':
            # Generate map image with rays from specified cameras
            import subprocess, tempfile, base64
            cam_names = qs.get('cams', [''])[0].split(',')
            cam_names = [unquote(c) for c in cam_names if c]
            lm_name = unquote(qs.get('lm', [''])[0]) if 'lm' in qs else None

            script = f"""
import sys
sys.path.insert(0, '{GTAMAP_DIR}')
import gtamaplib as ml
import gtamapdata as md

cam_names = {cam_names!r}
lm_name = {lm_name!r}

xs, ys = [], []
for cn in cam_names:
    try:
        cam = ml.get_camera(cn)
        xs.append(cam.xyz[0])
        ys.append(cam.xyz[1])
    except: pass

if lm_name:
    lm_xyz = md.landmarks.get(lm_name)
    if lm_xyz:
        xs.append(lm_xyz[0])
        ys.append(lm_xyz[1])

cx = sum(xs)/len(xs) if xs else 0
cy = sum(ys)/len(ys) if ys else 0
padding = 3000
area = (int(cx-padding), int(cy-padding), int(cx+padding), int(cy+padding))

m = ml.get_map('yanis').open(scale=1.0, add_padding=True)

import numpy as np

# If a target landmark is provided: triangulate it via intersect_rays and
# color each ray by its perpendicular distance from the result (green=good,
# red=bad — same scheme as bundle adjust).
ray_data = []  # list of (cn, target_xy, color, width)
if lm_name:
    rays = []
    valid_cams = []
    for cn in cam_names:
        try:
            cam = ml.get_camera(cn)
            if lm_name not in md.pixels.get(cn, {{}}): continue
            d = cam.get_landmark_direction(lm_name)
            if d is None: continue
            rays.append((tuple(cam.xyz), tuple(d)))
            valid_cams.append(cn)
        except Exception:
            pass

    if len(rays) >= 2:
        try:
            pt, distances = ml.intersect_rays(rays)
            # Determine color from distance: green<0.5m, yellow<2m, red>5m
            def err_color(dist_m):
                if dist_m < 0.5: return (0, 220, 80)       # green
                if dist_m < 2.0: return (200, 220, 60)     # yellow-green
                if dist_m < 5.0: return (255, 165, 0)      # orange
                return (230, 60, 60)                       # red
            for cn, dist in zip(valid_cams, distances):
                cam = ml.get_camera(cn)
                d = cam.get_landmark_direction(lm_name)
                target_xy = ml.get_point(cam.xyz, d, 30000)[:2]
                ray_data.append((cn, target_xy, err_color(float(dist)), 4))
        except Exception as e:
            print(f'intersect_rays failed: {{e}}')

# If no lm_name (or triangulation failed): fallback to old behavior
# (all rays from all cams, but with much lower alpha to keep readable)
if not ray_data:
    import colorsys
    def landmark_color(idx, total):
        h = (idx * 0.618033988749895) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.85, 1.0)
        return (int(r*255), int(g*255), int(b*255))
    all_lms = set()
    for cn in cam_names:
        all_lms.update(md.pixels.get(cn, {{}}).keys())
    lm_to_color = {{ln: landmark_color(i, len(all_lms)) for i, ln in enumerate(sorted(all_lms))}}
    for cn in cam_names:
        try:
            cam = ml.get_camera(cn)
            cam_pixels = md.pixels.get(cn, {{}})
            for ln in cam_pixels:
                try:
                    d = cam.get_landmark_direction(ln)
                    if d is None: continue
                    target_xy = ml.get_point(cam.xyz, d, 30000)[:2]
                    color = lm_to_color.get(ln, (200, 200, 200))
                    width = 4 if (lm_name and ln == lm_name) else 2
                    ray_data.append((cn, target_xy, color, width))
                except: pass
        except Exception as e:
            print(f'Error rays {{cn}}: {{e}}')

# Draw the rays
for cn, target_xy, color, width in ray_data:
    try:
        cam = ml.get_camera(cn)
        m.draw_line((cam.xy, target_xy), color, width)
    except Exception:
        pass

# Camera frustum outer bounds in BLACK — better contrast in the multi-cam
# Ray Map context where several frustums converge near the landmark.
# Length = distance from cam to target landmark (so each cam's frustum fits
# the relevant scope without crossing the whole map).
FRUSTUM_BLUE = (0, 0, 0)  # name kept for compatibility, value is now black
for cn in cam_names:
    try:
        cam = ml.get_camera(cn)
        if lm_name:
            target_lm_xyz = md.landmarks.get(lm_name)
            if target_lm_xyz:
                dx = target_lm_xyz[0] - cam.xyz[0]
                dy = target_lm_xyz[1] - cam.xyz[1]
                ray_len = (dx*dx + dy*dy) ** 0.5
            else:
                ray_len = 250
        else:
            ray_len = 250
        for x in (0, cam.w):
            edge_dir = cam.get_pixel_direction((x, cam.h / 2))
            target_xy = ml.get_point(cam.xyz, edge_dir, ray_len)[:2]
            m.draw_line((cam.xy, target_xy), FRUSTUM_BLUE, 2)
        m.draw_circle(cam.xy, 8, (255, 255, 255), cam.color, 2, cam.name[0])
    except Exception as e:
        print(f'Error frustum {{cn}}: {{e}}')

if lm_name and md.landmarks.get(lm_name):
    m.draw_landmark(lm_name)

m.save('/tmp/ray_map.png', area)
"""
            try:
                import subprocess
                result = subprocess.run(['python3', '-c', script],
                    capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    self.send_json({'error': result.stderr[:200]}, 500)
                    return
                with open('/tmp/ray_map.png', 'rb') as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                self.send_json({'image': img_b64})
            except Exception as e:
                self.send_json({'error': str(e)}, 500)

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
    server = HTTPServer(('localhost', port), Handler)
    print(f"\n🗺  gtamaplib Calibration Tool")
    print(f"   http://localhost:{port}")
    print(f"   Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
