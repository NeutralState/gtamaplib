#!/usr/bin/env python3
"""rlx_pose_gate.py — READ-ONLY gate for upstream (rlx) pose imports.

CHANTIER-1 (2026-07-14). Proven pattern (House (Keys), Safehouse Vehicles,
House with Boat): a rlx pose is importable iff it is INTERNALLY COHERENT
through OUR projection lib — rlx markings x rlx landmark xyz x rlx pose,
median residual < 2 arcmin. A pose that only "works" inside rlx's own solve
does not pass; a pose backed by consistent observations does.

Also reports the CROSS residual (our markings x our LM xyz x rlx pose) —
diagnostic only: high cross + high internal on OUR pose too = arbitration
case (Skyline 71m / Squalo 45m pattern), do NOT import either way.

Prereq: git fetch upstream && git show upstream/main:gtamapdata.py
        > /tmp/rlx_data.py, then extract to /tmp/rlx_dump.json (the module
        downloads assets at import — only ever exec it with cwd=/tmp):
            cd /tmp && python3 /tmp/extract_rlx.py

Usage:
    ./.venv/bin/python tools/audit/rlx_pose_gate.py "Grassrivers Postcard (X)"
    ./.venv/bin/python tools/audit/rlx_pose_gate.py --all      # every shared cam with delta > 5m
"""
import argparse
import json
import math
import os
import statistics
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(THIS_DIR)
REPO_DIR = os.path.dirname(TOOLS_DIR)
sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, REPO_DIR)

import common

RLX_DUMP = '/tmp/rlx_dump.json'
GATE_ARCMIN = 2.0


def gate_cam(name, rlx, verbose=True):
    """Returns dict verdict or None if not gateable."""
    rc = rlx['cameras'].get(name)
    if not rc or not rc.get('xyz') or not rc.get('ypr') or not rc.get('fov'):
        return {'cam': name, 'verdict': 'NO_RLX_POSE'}
    if name not in common.md.cameras:
        return {'cam': name, 'verdict': 'NOT_IN_OURS'}
    ours = common.md.cameras[name]
    if list(common.md.cameras[name].get('size') or []) != list(rc.get('size') or []):
        return {'cam': name, 'verdict': 'SIZE_MISMATCH',
                'ours': ours.get('size'), 'rlx': rc.get('size')}
    hfov, vfov = rc['fov'][0], (rc['fov'][1] if len(rc['fov']) > 1 else None)
    if hfov is None:
        return {'cam': name, 'verdict': 'NO_FOV'}
    if vfov is None:
        w, h = rc['size']
        vfov = math.degrees(2 * math.atan(math.tan(math.radians(hfov) / 2) * h / w))
    cam_state = {'xyz': rc['xyz'], 'ypr': rc['ypr'], 'fov': [hfov, vfov]}
    try:
        cam = common.get_cam(name, cam_state)
    except Exception as e:
        return {'cam': name, 'verdict': f'GET_CAM_FAIL: {e}'}

    delta = None
    if ours.get('xyz'):
        delta = math.dist(ours['xyz'], rc['xyz'])

    # INTERNAL gate: rlx markings x rlx LM xyz x rlx pose, through OUR lib.
    internal = []
    for lm, mk in (rlx['pixels'].get(name) or {}).items():
        xyz = rlx['landmarks'].get(lm)
        if not xyz:
            continue
        ang, gap, dist = common.residual_dual(cam, mk, xyz)
        if ang is not None:
            internal.append((ang, gap, lm))
    # CROSS: our markings x our LM xyz x rlx pose (diagnostic only).
    cross = []
    for lm, mk in (common.md.pixels.get(name) or {}).items():
        if mk is None or common.is_excluded_marking(name, lm):
            continue
        xyz = common.md.landmarks.get(lm)
        if not xyz:
            continue
        ang, gap, dist = common.residual_dual(cam, mk, xyz)
        if ang is not None:
            cross.append((ang, gap, lm))

    med_i = statistics.median(a for a, _, _ in internal) if internal else None
    med_c = statistics.median(a for a, _, _ in cross) if cross else None
    verdict = 'NO_OBS' if not internal else ('PASS' if med_i < GATE_ARCMIN else 'FAIL')
    out = {'cam': name, 'verdict': verdict, 'delta_m': delta,
           'internal_median_arcmin': med_i, 'internal_n': len(internal),
           'cross_median_arcmin': med_c, 'cross_n': len(cross)}
    if verbose:
        d = 'n/a' if delta is None else f"{delta:.1f}m"
        mi = 'n/a' if med_i is None else f"{med_i:.2f}'"
        mc = 'n/a' if med_c is None else f"{mc_fmt(med_c)}"
        print(f"=== {name} ===")
        print(f"  delta ours->rlx: {d}   rlx pose: xyz={rc['xyz']} ypr={rc['ypr']} fov={rc['fov']}")
        print(f"  INTERNAL (rlx mk x rlx LM x rlx pose): median {mi} on {len(internal)} obs -> {verdict}")
        if internal:
            for a, g, lm in sorted(internal, reverse=True)[:8]:
                gs = 'n/a' if g is None else f"{g:6.2f}m"
                print(f"     {a:7.2f}'  {gs}  {lm}")
            if len(internal) > 8:
                print(f"     ... +{len(internal)-8} more")
        print(f"  CROSS (our mk x our LM x rlx pose): median {mc} on {len(cross)} obs (diagnostic)")
        print()
    return out


def mc_fmt(v):
    return f"{v:.2f}'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cam', nargs='?', help="Cam name to gate.")
    ap.add_argument('--all', action='store_true',
                    help="Gate every cam present in both datasets with pose delta > 5m.")
    args = ap.parse_args()

    if not os.path.exists(RLX_DUMP):
        sys.exit(f"ERROR: {RLX_DUMP} missing — see module docstring for the extract step.")
    rlx = json.load(open(RLX_DUMP))

    if args.cam:
        gate_cam(args.cam, rlx)
        return

    if not args.all:
        sys.exit("Pass a cam name or --all.")

    rows = []
    for name, rc in sorted(rlx['cameras'].items()):
        if name not in common.md.cameras or not rc.get('xyz'):
            continue
        ours = common.md.cameras[name].get('xyz')
        if not ours:
            continue
        delta = math.dist(ours, rc['xyz'])
        if delta <= 5.0:
            continue
        rows.append(gate_cam(name, rlx, verbose=False))
    order = {'PASS': 0, 'FAIL': 1}
    rows.sort(key=lambda r: (order.get(r['verdict'], 2),
                             -(r.get('delta_m') or 0)))
    print(f"{'verdict':8} {'delta_m':>8} {'internal':>10} {'n':>4} {'cross':>8} {'n':>4}  cam")
    for r in rows:
        d = 'n/a' if r.get('delta_m') is None else f"{r['delta_m']:8.1f}"
        mi = '   n/a' if r.get('internal_median_arcmin') is None else f"{r['internal_median_arcmin']:9.2f}'"
        mc = '  n/a' if r.get('cross_median_arcmin') is None else f"{r['cross_median_arcmin']:7.2f}'"
        print(f"{r['verdict']:8} {d} {mi} {r.get('internal_n', 0):4} {mc} {r.get('cross_n', 0):4}  {r['cam']}")


if __name__ == '__main__':
    sys.exit(main())
