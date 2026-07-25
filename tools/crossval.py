#!/usr/bin/env python3
"""crossval.py — la carte se trompe de combien, VRAIMENT. [XVAL-V1]

Le projet publie des incertitudes venues de trois conventions differentes
qui se contredisent d'un facteur 50 (barres conditionnelles du solve joint,
modes joints de la hessienne, diagonale du BA global). Aucune n'a jamais
ete confrontee au reel.

Ce test-ci ne modelise rien, il mesure: pour chaque landmark vu par >=3
cameras, on RETIRE une camera, on triangule le point avec les autres
seulement, puis on reprojette dans la camera retiree et on compare au clic
qu'elle n'a pas vu. C'est de la prediction hors-echantillon: aucun moyen
de tricher, l'observation testee n'a pas participe a la construction.

Sortie: la distribution des erreurs de prediction (arcmin ET metres),
par zone, par tier de camera, plus le palmares des pires predictions —
qui est directement une liste de choses a re-verifier.

Usage: PYTHONPATH=. python3 tools/crossval.py [--min-views 3] [--json out]
"""
import argparse
import collections
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
from common import ray_ls_point


def pct(vals, p):
    return float(np.percentile(vals, p)) if len(vals) else float('nan')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min-views', type=int, default=3)
    ap.add_argument('--json', default=os.path.join(REPO, 'tools', 'generated', 'crossval.json'))
    ap.add_argument('--top', type=int, default=25)
    args = ap.parse_args()

    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    cams_j = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    try:
        tiers = json.load(open(os.path.join(REPO, 'tools', 'generated', 'confidence_tiers.json')))
        tj = tiers.get('cameras', {})
    except Exception:
        tj = {}

    def tier(c):
        t = tj.get(c)
        return (t.get('tier') if isinstance(t, dict) else t) or 'unknown'

    # cams utilisables: pose complete
    ok_cam = {c for c, e in cams_j.items()
              if e.get('xyz') and e.get('ypr') and e.get('fov') and e['fov'][0]}

    # observateurs par landmark
    obs_of = collections.defaultdict(list)
    for c, marks in px.items():
        if c not in ok_cam:
            continue
        for lm, p in marks.items():
            if p is None or common.is_excluded_marking(c, lm):
                continue
            obs_of[lm].append((c, p))

    tested = [lm for lm, o in obs_of.items() if len(o) >= args.min_views]
    print(f'{len(tested)} landmarks vus par >= {args.min_views} cameras -> '
          f'{sum(len(obs_of[l]) for l in tested)} predictions hors-echantillon\n')

    rows = []
    for lm in tested:
        obs = obs_of[lm]
        # rayons de chaque observateur
        rays = {}
        for c, p in obs:
            try:
                cam = common.get_cam(c)
                d = np.asarray(cam.get_pixel_direction(p), float)
            except Exception:
                continue
            if d is None:
                continue
            rays[c] = (np.asarray(cam.xyz, float), d / np.linalg.norm(d))
        if len(rays) < args.min_views:
            continue
        for held, (o_h, d_h) in rays.items():
            others = [v for c, v in rays.items() if c != held]
            if len(others) < 2:
                continue
            try:
                P = np.asarray(ray_ls_point(others), float)
            except Exception:
                continue
            if not np.all(np.isfinite(P)) or max(abs(v) for v in P) > 1e6:
                continue
            cam = common.get_cam(held)
            pr = cam.get_pixel([float(v) for v in P])
            p_obs = dict(obs)[held]
            dist = float(np.hypot(*(P[:2] - o_h[:2])))
            if pr is None:
                continue
            dx = (pr[0] - p_obs[0]) * cam.hfov / cam.w * 60.0
            dy = (pr[1] - p_obs[1]) * cam.vfov / cam.h * 60.0
            err_arcmin = math.hypot(dx, dy)
            err_m = math.radians(err_arcmin / 60.0) * dist
            zone = (lms.get(lm) or {}).get('zone') if isinstance(lms.get(lm), dict) else None
            rows.append({'lm': lm, 'held': held, 'arcmin': err_arcmin, 'm': err_m,
                         'dist': dist, 'zone': zone or '?', 'tier': tier(held),
                         'n_views': len(rays)})

    if not rows:
        print('aucune prediction possible.')
        return
    a = np.array([r['arcmin'] for r in rows])
    mm = np.array([r['m'] for r in rows])
    print('=' * 78)
    print('CE QUE LA CARTE PREDIT SUR CE QU ELLE N A PAS VU')
    print('=' * 78)
    print(f'  {len(rows)} predictions hors-echantillon')
    print(f'  erreur angulaire : mediane {np.median(a):6.1f}\'   80e pct {pct(a,80):7.1f}\'   '
          f'95e pct {pct(a,95):8.1f}\'')
    print(f'  erreur metrique  : mediane {np.median(mm):6.1f} m  80e pct {pct(mm,80):7.1f} m  '
          f'95e pct {pct(mm,95):8.1f} m')
    print(f'  sous 5\'  : {100*np.mean(a < 5):.0f}%      sous 10 m : {100*np.mean(mm < 10):.0f}%')

    print('\npar zone:')
    byz = collections.defaultdict(list)
    for r in rows:
        byz[r['zone']].append(r)
    print(f'  {"zone":24s} {"n":>5s} {"med arcmin":>11s} {"med m":>8s} {"80e m":>8s}')
    for z, rs in sorted(byz.items(), key=lambda kv: -len(kv[1])):
        aa = [r['arcmin'] for r in rs]; mmz = [r['m'] for r in rs]
        print(f'  {z:24s} {len(rs):5d} {np.median(aa):10.1f}\' {np.median(mmz):8.1f} {pct(mmz,80):8.1f}')

    print('\npar tier de la camera retiree:')
    byt = collections.defaultdict(list)
    for r in rows:
        byt[r['tier']].append(r)
    for t, rs in sorted(byt.items(), key=lambda kv: -len(kv[1])):
        aa = [r['arcmin'] for r in rs]
        print(f'  {t:14s} {len(rs):5d} predictions, mediane {np.median(aa):7.1f}\'')

    print(f'\nles {args.top} pires predictions (a re-verifier en priorite):')
    print(f'  {"arcmin":>8s} {"metres":>8s} {"dist":>7s}  landmark / camera retiree')
    for r in sorted(rows, key=lambda r: -r['arcmin'])[:args.top]:
        print(f'  {r["arcmin"]:8.1f} {r["m"]:8.1f} {r["dist"]:7.0f}  {r["lm"][:38]:38s} <- {r["held"]}')

    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    json.dump({'n': len(rows),
               'median_arcmin': float(np.median(a)), 'p80_arcmin': pct(a, 80),
               'median_m': float(np.median(mm)), 'p80_m': pct(mm, 80),
               'rows': rows}, open(args.json, 'w'), indent=1)
    print(f'\n-> {args.json}')


if __name__ == '__main__':
    main()
