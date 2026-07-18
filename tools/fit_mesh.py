#!/usr/bin/env python3
"""fit_mesh.py — fit rigide d'un building sur TOUTES ses observations. [MESH-FIT-V1]

L'inverse du mesh-as-ruler: au lieu de calibrer une cam avec un mesh fige,
on optimise le placement du building (translation + rotation + echelle
optionnelle) pour minimiser la reprojection de TOUS les markings de TOUTES
les cams calibrees SIMULTANEMENT. La rigidite couple les coins: une cam qui
ne voit que le coin E contraint le coin W. Surdetermine massif (SPC: ~60
contraintes pour 4-5 params).

Ce que ca corrige: les positions de coins issues de triangulations paire-par-
paire (frames locales, circularites) se reconcilient en un placement global
unique qui honore chaque temoin a hauteur de sa coherence (soft-l1 robuste).

Usage:
  PYTHONPATH=. python3 tools/fit_mesh.py "Stephen P. Clark Government Center"
  PYTHONPATH=. python3 tools/fit_mesh.py "Vizcayne North Condominium" --scale --dz
  ... --apply    # ecrit les xyz transformes des coins (dry-run par defaut)

Apres --apply: regenerer le mesh procedural (gen_spc_mesh.py / gen_vizcayne_
mesh.py) et re-fitter les plans de structures.json si besoin.

Sorties: transform + residuels par observation (avant/apres) + bilan PAR CAM
(les cams en desaccord au fit final = diagnostic mesh-as-ruler integre).
"""
import argparse
import json
import math
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
import common


def collect(building):
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    members = {}
    for n, e in lms.items():
        if n.startswith(building + ' (') and isinstance(e, dict) and e.get('xyz'):
            members[n] = np.array(e['xyz'], float)
    obs = []
    for cam_name, marks in px.items():
        try:
            cam = common.get_cam(cam_name)
            assert cam is not None
        except Exception:
            continue
        for lm in marks:
            if lm not in members or marks[lm] is None:
                continue
            if common.is_excluded_marking(cam_name, lm):
                continue
            obs.append((cam_name, lm, np.array(marks[lm], float)))
    return members, obs


def transform_pts(members, centroid, dx, dy, dz, dth, ds):
    R = np.array([[math.cos(dth), -math.sin(dth)], [math.sin(dth), math.cos(dth)]])
    out = {}
    for n, p in members.items():
        xy = centroid[:2] + ds * (R @ (p[:2] - centroid[:2])) + np.array([dx, dy])
        z = centroid[2] + ds * (p[2] - centroid[2]) + dz
        out[n] = np.array([xy[0], xy[1], z])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('building')
    ap.add_argument('--scale', action='store_true', help='echelle uniforme libre')
    ap.add_argument('--dz', action='store_true', help='translation z libre (defaut: gele — respect des z_constraints)')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    members, obs = collect(args.building)
    if len(members) < 2 or len(obs) < 4:
        sys.exit(f'pas assez de donnees: {len(members)} coins xyz, {len(obs)} observations')
    centroid = np.mean(list(members.values()), axis=0)
    cams_used = sorted(set(c for c, _, _ in obs))
    print(f'{args.building}: {len(members)} coins, {len(obs)} observations, {len(cams_used)} cams')

    cam_cache = {c: common.get_cam(c) for c in cams_used}

    def cost(th):
        dx, dy, dz, dth, ds = th
        pts = transform_pts(members, centroid, dx, dy, dz, dth, ds)
        tot = 0.0
        for cam_name, lm, pix in obs:
            p = cam_cache[cam_name].get_pixel(pts[lm].tolist())
            if p is None:
                tot += 10; continue
            d2 = (p[0] - pix[0]) ** 2 + (p[1] - pix[1]) ** 2
            tot += math.sqrt(1 + d2 / 2500) - 1
        return tot

    def table(th, label):
        dx, dy, dz, dth, ds = th
        pts = transform_pts(members, centroid, dx, dy, dz, dth, ds)
        rows, by_cam = [], {}
        for cam_name, lm, pix in obs:
            cam = cam_cache[cam_name]
            a, g, d = common.residual_dual(cam, pix.tolist(), pts[lm].tolist())
            if a is None:
                continue
            rows.append((g, a, cam_name, lm))
            by_cam.setdefault(cam_name, []).append(g)
        import statistics
        med = statistics.median([r[0] for r in rows])
        print(f'\n── {label}: median {med:.3f}m sur {len(rows)} obs')
        for g, a, c, lm in sorted(rows, reverse=True)[:10]:
            print(f'   {a:7.2f}\' {g:7.3f}m  {c[:30]:30} {lm.replace(args.building, "..")}')
        print('   par cam:', '  '.join(f'{c.split("(")[0].strip()[:14]}={statistics.median(v):.2f}m'
                                       for c, v in sorted(by_cam.items(), key=lambda x: -statistics.median(x[1]))))
        return med

    zero = [0.0, 0.0, 0.0, 0.0, 1.0]
    med0 = table(zero, 'AVANT (placement actuel)')

    best = (cost(zero), *zero)
    step = [2.0, 2.0, 1.0 if args.dz else 0.0, math.radians(0.5), 0.01 if args.scale else 0.0]
    for it in range(120):
        improved = False
        for i, s in enumerate(step):
            if s == 0.0:
                continue
            for sgn in (1, -1):
                cand = list(best[1:]); cand[i] += sgn * s
                c = cost(cand)
                if c < best[0] - 1e-9:
                    best = (c, *cand); improved = True
        if not improved:
            step = [s / 2 for s in step]
            if max(step) < 1e-3 * max(1, min(s for s in [2.0] )) and max(step) < 0.004:
                break
    th = list(best[1:])
    dx, dy, dz, dth, ds = th
    print(f'\nTRANSFORM: dx={dx:+.2f} dy={dy:+.2f} dz={dz:+.2f} rot={math.degrees(dth):+.3f} deg scale={ds:.4f}')
    med1 = table(th, 'APRES (fit global)')

    if not args.apply:
        print('\nDRY-RUN. --apply pour ecrire les coins transformes.')
        return
    if med1 >= med0:
        sys.exit(f'\nREFUSE: median {med0:.3f} -> {med1:.3f} (pas d amelioration)')
    lms_path = os.path.join(REPO, 'gtamapdata', 'landmarks.json')
    lms = json.load(open(lms_path))
    pts = transform_pts(members, centroid, *th)
    for n, p in pts.items():
        lms[n]['xyz'] = [round(float(v), 3) for v in p]
        zc = lms[n].get('z_constraint')
        if zc and zc.get('type') == 'fixed' and (args.dz or args.scale):
            zc['value'] = round(float(p[2]), 3)  # la contrainte suit le corps rigide
    tmp = lms_path + '.tmp'
    json.dump(lms, open(tmp, 'w'), indent=2, ensure_ascii=True)
    os.replace(tmp, lms_path)
    common.log_event('mesh_fit', 'rigid_fit_applied',
                     reason=f'{args.building}: fit global {len(obs)} obs/{len(cams_used)} cams, '
                            f'median {med0:.2f}->{med1:.2f}m, transform dx{dx:+.2f} dy{dy:+.2f} '
                            f'rot{math.degrees(dth):+.3f} scale{ds:.4f}')
    print(f'\nAPPLIED: {len(pts)} coins ecrits. Regenerer le mesh procedural + refit structures si besoin.')


if __name__ == '__main__':
    main()
