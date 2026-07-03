#!/usr/bin/env python3
"""fit_minimal.py — self-consistency bootstrap for under-determined cams.

For a cam with only 2-3 triangulated markings, a full 7-param calibration is
impossible (refine_cam_full requires >=4 LMs) — but there is NO excuse for the
projections not matching the markings we DO have. With xyz LOCKED at its
current value, 2 markings give 4 equations for yaw/pitch/hfov (3 unknowns):
an (over)determined fit exists and should be ~exact.

What this buys you (the bootstrap loop):
  1. fit_minimal -> projections match the markings (loss stops screaming)
  2. Assist ghosts now land close to reality -> marking a 3rd/4th LM is easy
  3. >=4 LMs -> refine_cam_full for a real, verifiable calibration

The result is SELF-CONSISTENT, not VERIFIED: with n<=3 obs there is no
redundancy to detect a wrong marking or a wrong xyz. Tiers/bundle stay
protected (n_obs gates, --cleanup junk filter, guarded apply).

Position workflow: if you believe xyz is off (e.g. Landing Gear), nudge the
sliders in the UI, Save, then re-run fit_minimal — it becomes an instant
"orient to match" after any manual position move.

Usage:
    python3 tools/fit_minimal.py "Green Sports Car"              # dry-run
    python3 tools/fit_minimal.py "Green Sports Car" --apply
    python3 tools/fit_minimal.py "Landing Gear (B)" --solve-roll # 4th DOF
    python3 tools/fit_minimal.py --list                          # candidates
"""
import argparse
import json
import math
import os
import sys

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOL_DIR)
sys.path.insert(0, ROOT)
sys.path.insert(0, TOOL_DIR)

import gtamaplib as ml
import gtamapdata as md
from common import is_excluded_marking

CAMERAS_JSON = os.path.join(ROOT, 'gtamapdata', 'cameras.json')
ROLL_PRIOR_WEIGHT = 50.0  # same calibration as refine_cam_ypr (Diner N)


def gather_obs(cam_name):
    """Markings of this cam whose LM has a triangulated xyz."""
    obs = []
    for lm, px in md.pixels.get(cam_name, {}).items():
        if px is None or is_excluded_marking(cam_name, lm):
            continue
        xyz = md.landmarks.get(lm)
        if xyz is None:
            continue
        obs.append((lm, px, xyz))
    return obs


def residuals_arcmin(cam, obs):
    out = []
    for lm, px, xyz in obs:
        p = cam.get_pixel(xyz)
        if p is None:
            out.append((float('inf'), lm))
            continue
        dx = (p[0] - px[0]) * cam.hfov / cam.w * 60
        dy = (p[1] - px[1]) * cam.vfov / cam.h * 60
        out.append((math.hypot(dx, dy), lm))
    return out


def fov_slot(cam_data):
    """[VFOV-V1] Some cams are vfov-primary: fov = (None, vfov). Return
    (index, value) of the active slot."""
    fv = cam_data.get('fov')
    if isinstance(fv, (list, tuple)):
        if fv[0] is not None:
            return 0, float(fv[0])
        return 1, float(fv[1])
    return 0, float(fv)


def make_cam(cam_name, ypr, fov_val):
    """Camera object with overridden ypr/fov (xyz stays as stored)."""
    saved = dict(md.cameras[cam_name])
    md.cameras[cam_name]['ypr'] = list(ypr)
    idx, _ = fov_slot(saved)
    new_fov = [None, None]
    if isinstance(saved.get('fov'), (list, tuple)) and len(saved['fov']) > 1:
        new_fov = list(saved['fov'])
    new_fov[idx] = fov_val
    md.cameras[cam_name]['fov'] = new_fov
    try:
        ml.get_camera.cache_clear()
    except Exception:
        pass
    cam = ml.get_camera(cam_name)
    md.cameras[cam_name] = saved
    try:
        ml.get_camera.cache_clear()
    except Exception:
        pass
    return cam


def fit(cam_name, obs, solve_roll, roll_sigma=2.0):
    from scipy.optimize import minimize
    c0 = md.cameras[cam_name]
    y0, p0, r0 = list(c0['ypr'])
    _, f0 = fov_slot(c0)  # [VFOV-V1]

    def loss(v):
        if solve_roll:
            yaw, pitch, roll, hfov = v
        else:
            yaw, pitch, hfov = v
            roll = r0
        if not (5.0 < hfov < 140.0):
            return 1e9
        cam = make_cam(cam_name, [yaw, pitch, roll], hfov)
        res = residuals_arcmin(cam, obs)
        vals = [r for r, _ in res]
        if any(math.isinf(v_) for v_ in vals):
            return 1e9
        rms = math.sqrt(sum(v_ * v_ for v_ in vals) / len(vals))
        if solve_roll:
            rms += ROLL_PRIOR_WEIGHT * (roll / roll_sigma) ** 2
        return rms

    x0 = [y0, p0, r0, f0] if solve_roll else [y0, p0, f0]

    # [MULTISTART-V1] if the current pose projects a marking behind the cam
    # (inf residual) or is wildly off, Nelder-Mead sits on a flat 1e9 plateau
    # and never escapes. Coarse yaw x pitch grid to find a finite basin first.
    if loss(x0) >= 1e9:
        best_seed, best_val = None, 1e9
        for yaw_g in range(0, 360, 15):
            for pitch_g in (-30.0, -10.0, 0.0, 10.0):
                seed = ([float(yaw_g), pitch_g, r0, f0] if solve_roll
                        else [float(yaw_g), pitch_g, f0])
                v = loss(seed)
                if v < best_val:
                    best_val, best_seed = v, seed
        if best_seed is not None and best_val < 1e9:
            print(f'  [multi-start] plateau at current pose; best seed '
                  f'yaw={best_seed[0]:.0f} pitch={best_seed[1]:.0f} '
                  f"({best_val:.1f}')")
            x0 = best_seed
        else:
            print('  [multi-start] no finite basin found on the coarse grid — '
                  'the xyz is likely far off or a LM xyz is wrong.')

    best = minimize(loss, x0, method='Nelder-Mead',
                    options={'xatol': 1e-5, 'fatol': 1e-8,
                             'maxiter': 8000, 'adaptive': True})
    v = list(best.x)
    if solve_roll:
        ypr, hfov = [v[0], v[1], v[2]], v[3]
    else:
        ypr, hfov = [v[0], v[1], r0], v[2]
    cam = make_cam(cam_name, ypr, hfov)
    return ypr, hfov, residuals_arcmin(cam, obs)


def list_candidates():
    print('Under-determined cams (2-3 triangulated obs, calibrated xyz):')
    rows = []
    for cn, cd in md.cameras.items():
        if not cd.get('xyz'):
            continue
        obs = gather_obs(cn)
        if 2 <= len(obs) <= 3:
            cam = ml.get_camera(cn)
            res = residuals_arcmin(cam, obs)
            worst = max(r for r, _ in res)
            rows.append((worst, len(obs), cn))
    rows.sort(reverse=True)
    for worst, n, cn in rows:
        flag = ' <- fit would help' if worst > 5 else ''
        print(f"  {worst:9.1f}'  n={n}  {cn}{flag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cam_name', nargs='?')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--solve-roll', action='store_true',
                    help='also free roll (soft prior at 0, needs >=2 obs; '
                         'default keeps current roll)')
    ap.add_argument('--list', action='store_true',
                    help='list under-determined candidate cams')
    args = ap.parse_args()

    if args.list or not args.cam_name:
        list_candidates()
        return 0

    cn = args.cam_name
    if cn not in md.cameras:
        print(f'unknown cam: {cn}'); return 1
    if not md.cameras[cn].get('xyz'):
        print(f'{cn} has no xyz — place it first (UI sliders / map reasoning)')
        return 1
    obs = gather_obs(cn)
    if len(obs) < 2:
        print(f'{cn}: only {len(obs)} triangulated marking(s) — need >= 2. '
              f'Use Assist mode to find a landmark to mark.')
        return 1

    # Golden rule: if this cam sources any LM, changing its ypr invalidates
    # those children — flag them for retriangulation after --apply.
    children = [n for n, d in md.landmarks_meta.items()
                if cn in (d.get('source_cameras') or [])]
    if children:
        print(f'NOTE: this cam is a SOURCE of {len(children)} LM(s): {children}')
        print('      after --apply, dry-run triangulate_lm on each and review.')

    cam = ml.get_camera(cn)
    before = residuals_arcmin(cam, obs)
    print(f'=== {cn} ===  (xyz LOCKED, fitting yaw/pitch/hfov'
          + ('/roll' if args.solve_roll else '') + f' on {len(obs)} obs)')
    print('Before:')
    for r, lm in sorted(before, reverse=True):
        print(f"  {r:9.2f}'  {lm}")

    ypr, hfov, after = fit(cn, obs, args.solve_roll)
    print('After:')
    for r, lm in sorted(after, reverse=True):
        print(f"  {r:9.2f}'  {lm}")
    c0 = md.cameras[cn]
    print(f"ypr:  {[round(float(v), 4) for v in c0['ypr']]} -> {[round(float(v), 4) for v in ypr]}")
    _idx, f0 = fov_slot(c0)  # [VFOV-V1]
    print(f"{'vfov' if _idx else 'hfov'}: {round(float(f0), 4)} -> {round(float(hfov), 4)}")

    worst = max(r for r, _ in after)
    if worst > 5.0:
        print(f"\nWARNING: worst residual {worst:.1f}' > 5' — with xyz locked the "
              f'fit cannot close. Either the xyz is off (nudge it in the UI, '
              f'Save, re-run) or a marking/LM is wrong.')
    if len(obs) <= 3:
        print(f'NOTE: n={len(obs)} obs -> SELF-CONSISTENT only, not verified. '
              f'Turn on Assist: ghosts are now accurate, mark 1-2 more LMs, '
              f'then run refine_cam_full for a real calibration.')

    if not args.apply:
        print('\nDRY-RUN. Use --apply to write.')
        return 0
    with open(CAMERAS_JSON) as f:
        cameras = json.load(f)
    cameras[cn]['ypr'] = [round(float(v), 6) for v in ypr]
    _idx, _ = fov_slot(md.cameras[cn])  # [VFOV-V1] write back to the active slot
    if isinstance(cameras[cn].get('fov'), list):
        cameras[cn]['fov'][_idx] = round(float(hfov), 6)
    else:
        _f = [None, None]; _f[_idx] = round(float(hfov), 6)
        cameras[cn]['fov'] = _f
    with open(CAMERAS_JSON, 'w') as f:
        json.dump(cameras, f, indent=2)
    print('APPLIED: cameras.json updated. (Re-run compute_confidence_tiers.py)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
