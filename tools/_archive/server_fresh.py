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
    try:
        from scipy.optimize import minimize
        import numpy as np
    except ImportError:
        return None, "scipy not installed — run: pip3 install scipy"

    cam_pixels = md.pixels.get(cam_name, {})

    # Independent landmarks only
    constraints = [
        (md.landmarks.get(lm), list(mp))
        for lm, mp in cam_pixels.items()
        if md.landmarks.get(lm) is not None
        and cam_name not in md.landmarks_meta.get(lm, {}).get('source_cameras', [])
    ]

    n_indep = len(constraints)
    if n_indep < 3:
        return None, f"Not enough independent landmarks ({n_indep} — need at least 3)"

    # Loss before
    cam_before = get_cam(cam_name, xyz, ypr, hfov)
    loss_before = math.sqrt(sum(pixel_error(cam_before, lm, mp)**2 for lm, mp in constraints) / n_indep)

    x0 = np.array([xyz[0], xyz[1], xyz[2], ypr[0], ypr[1], hfov])

    def objective(p):
        try:
            cam = get_cam(cam_name, list(p[:3]), [p[3], p[4], 0.0], float(p[5]))
            return sum(pixel_error(cam, lm, mp)**2 for lm, mp in constraints) / len(constraints)
        except: return 1e9

    result = minimize(objective, x0, method='Nelder-Mead',
        options={'xatol':1e-5, 'fatol':1e-7, 'maxiter':5000, 'adaptive':True})

    loss_after = round(math.sqrt(abs(float(result.fun))), 4)
    improvement = round((loss_before - loss_after) / loss_before * 100, 1) if loss_before > 0 else 0

    return {
        'xyz': [round(float(v), 4) for v in result.x[:3]],
        'ypr': [round(float(result.x[3]), 4), round(float(result.x[4]), 4), 0.0],
        'hfov': round(float(result.x[5]), 4),
        'loss_before': round(loss_before, 4),
        'loss': loss_after,
        'improvement_pct': improvement,
        'n_constraints': n_indep,
        'success': bool(result.success),
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
                })
            self.send_json(result)

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
            cam_name = unquote(qs.get('cam', [''])[0])
            xyz = [float(qs['x'][0]), float(qs['y'][0]), float(qs['z'][0])]
            ypr = [float(qs['yaw'][0]), float(qs['pitch'][0]), 0.0]
            hfov_val = float(qs['hfov'][0])

            cam = get_cam(cam_name, xyz, ypr, hfov_val)
            cam_pixels = md.pixels.get(cam_name, {})
            updated = []
            errors = []

            for lm_name, marked_pixel in cam_pixels.items():
                src = md.landmarks_meta.get(lm_name, {}).get('source_cameras', [])
                if cam_name not in src:
                    continue  # skip independent landmarks

                other_cams = [s for s in src if s != cam_name]

                if not other_cams:
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
                else:
                    # Multi-source — triangulate with first other cam
                    other_cam_name = other_cams[0]
                    if lm_name not in md.pixels.get(other_cam_name, {}):
                        continue
                    try:
                        other_cam = ml.get_camera(other_cam_name)
                        ray_a = (cam.xyz, cam.get_landmark_direction(lm_name))
                        ray_b = (other_cam.xyz, other_cam.get_landmark_direction(lm_name))
                        result = ml.intersect_ray_and_ray(ray_a, ray_b)
                        if result is not None:
                            pt, _, _, d, _ = result
                            md.update_landmark(lm_name, list(pt),
                                source_cameras=src,
                                error_m=round(float(d), 3),
                                zone=md.landmarks_meta.get(lm_name, {}).get('zone'))
                            updated.append(lm_name)
                    except Exception as e:
                        errors.append(f"{lm_name}: {e}")

            print(f"Updated {len(updated)} landmarks for {cam_name}")
            if errors:
                print(f"  Errors: {errors[:3]}")
            self.send_json({'updated': len(updated), 'errors': len(errors), 'names': updated})

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
                    if e['err'] > max(avg * 3, 10):
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

            # Save to landmarks
            meta = md.landmarks_meta.get(lm_name, {})
            md.update_landmark(lm_name, best['xyz'],
                source_cameras=source_cams,
                error_m=best['error_m'],
                zone=meta.get('zone', 'unknown'))
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

color_list = [(255,68,68),(68,170,255),(255,170,0),(170,68,255),(68,255,170)]
for idx2, cn in enumerate(cam_names):
    try:
        cam = ml.get_camera(cn)
        color = color_list[idx2 % len(color_list)]
        m.draw_camera(cam, d=30000)
        cam_pixels = md.pixels.get(cn, {{}})
        drawn = 0
        for ln in cam_pixels:
            if drawn >= 8: break
            try:
                d = cam.get_landmark_direction(ln)
                if d is None: continue
                target_xy = ml.get_point(cam.xyz, d, 30000)[:2]
                m.draw_line((cam.xy, target_xy), color, 2)
                drawn += 1
            except: pass
        if lm_name and lm_name in cam_pixels:
            try:
                d = cam.get_landmark_direction(lm_name)
                if d is not None:
                    target_xy = ml.get_point(cam.xyz, d, 30000)[:2]
                    m.draw_line((cam.xy, target_xy), (255,255,255), 5)
            except: pass
    except Exception as e:
        print(f'Error {{cn}}: {{e}}')

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
