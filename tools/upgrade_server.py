#!/usr/bin/env python3
"""
upgrade_server.py — Upgrade the calib tool's server.py with the methods
we developed today:
  - /api/optimize: switch from Nelder-Mead/MSE to scipy.least_squares (TRF)
                   with huber loss. Robust to outlier landmarks.
  - /api/update_landmarks: switch from ray-ray to multi-cam least-squares
                            triangulation. Detects co-located source cams
                            and refuses to update in that case (avoids
                            the Easy Hill scenario).

Run from gtamaplib-main/:
    python3 tools/upgrade_server.py        # dry run, shows diff
    python3 tools/upgrade_server.py --apply
"""

import argparse
import os
import shutil
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_PATH = os.path.join(GTAMAP_DIR, "tools", "server.py")
BACKUP_PATH = SERVER_PATH + ".bak"

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

if not os.path.exists(SERVER_PATH):
    print(f"ERROR: {SERVER_PATH} not found"); sys.exit(1)

with open(SERVER_PATH) as f:
    src = f.read()

# ─────────────────────────────────────────────────────────────────────────────
# REPLACEMENT 1: optimize_camera function
# ─────────────────────────────────────────────────────────────────────────────

OLD_OPTIMIZE = '''def optimize_camera(cam_name, xyz, ypr, hfov):
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
    }, None'''

NEW_OPTIMIZE = '''def optimize_camera(cam_name, xyz, ypr, hfov):
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
    }, None'''

# ─────────────────────────────────────────────────────────────────────────────
# REPLACEMENT 2: update_landmarks endpoint logic
# ─────────────────────────────────────────────────────────────────────────────

OLD_UPDATE = '''        elif path == '/api/update_landmarks':
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
            self.send_json({'updated': len(updated), 'errors': len(errors), 'names': updated})'''

NEW_UPDATE = '''        elif path == '/api/update_landmarks':
            cam_name = unquote(qs.get('cam', [''])[0])
            xyz = [float(qs['x'][0]), float(qs['y'][0]), float(qs['z'][0])]
            ypr = [float(qs['yaw'][0]), float(qs['pitch'][0]), 0.0]
            hfov_val = float(qs['hfov'][0])

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
            })'''

# ─────────────────────────────────────────────────────────────────────────────
# Apply replacements
# ─────────────────────────────────────────────────────────────────────────────

new_src = src

# Check that old strings are present
if OLD_OPTIMIZE not in new_src:
    print("✗ Could not find OLD_OPTIMIZE block in server.py")
    print("  The server.py may have already been upgraded, or its content has changed.")
    sys.exit(1)
if OLD_UPDATE not in new_src:
    print("✗ Could not find OLD_UPDATE block in server.py")
    sys.exit(1)

new_src = new_src.replace(OLD_OPTIMIZE, NEW_OPTIMIZE)
new_src = new_src.replace(OLD_UPDATE, NEW_UPDATE)

print(f"Plan:")
print(f"  - Replace optimize_camera with TRF + huber loss version")
print(f"  - Replace /api/update_landmarks with multi-cam triangulation")
print(f"  - Add co-location check (refuse to triangulate when cams within 50m)")
print(f"  - Backup current server.py to {BACKUP_PATH}")
print(f"")
old_lines = src.count('\\n')
new_lines = new_src.count('\\n')
print(f"  Lines: {old_lines} -> {new_lines} ({new_lines - old_lines:+d})")

if not args.apply:
    print(f"\\n(dry run — re-run with --apply to write changes)")
    sys.exit(0)

# Backup
shutil.copy(SERVER_PATH, BACKUP_PATH)
print(f"\\n✓ Backup: {BACKUP_PATH}")

with open(SERVER_PATH, 'w') as f:
    f.write(new_src)
print(f"✓ Updated: {SERVER_PATH}")

print(f"\\nRestart the server to take effect:")
print(f"  lsof -ti :8765 | xargs kill -9")
print(f"  python3 tools/server.py")
print(f"\\nIf something breaks, revert with:")
print(f"  cp {BACKUP_PATH} {SERVER_PATH}")
