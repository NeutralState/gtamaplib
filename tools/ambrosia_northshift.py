#!/usr/bin/env python3
"""ambrosia_northshift.py — 'is Ambrosia further north?' [AMB-NORTH-V1]

rlx tient depuis des mois que la zone est plus au nord. Sa postcard du
2026-07-24 (fov 48) sort a y=4202 quand la notre est a y=3814: 390 m.
Comme sa postcard n'a aucune ancre lointaine, sa position est portee par
la construction du silo depuis le pano — donc c'est TOUTE la zone qui
est decalee au nord chez lui.

Test: on translate les 4 cams (et donc, par re-triangulation, tout le
monde de la zone) de dy, on epingle ce decalage (+-5 m par cam, le reste
libre), on resout le joint borne, et on regarde le cout ANCRE final.
Les ancres (FAA MIA, MIA N Terminal, SSB N/S) ne bougent pas: si la zone
n'est pas a sa place, ce sont elles qui payent.

Usage: PYTHONPATH=. python3 tools/ambrosia_northshift.py [--rounds 25]
"""
import argparse
import importlib.util
import json
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np

spec = importlib.util.spec_from_file_location('aj', os.path.join(THIS, 'ambrosia_joint.py'))
aj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aj)

SLACK = 5.0     # liberte residuelle par cam autour de la position decalee


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rounds', type=int, default=25)
    ap.add_argument('--dys', default='-200,-100,0,100,200,300,390,500')
    args = ap.parse_args()
    dys = [float(v) for v in args.dys.split(',')]

    px, lms, cams = aj.load()
    zone, anchors, ext = aj.collect(px, lms, cams, use_brator=True, no_kalaga=False)
    sv0 = aj.Solver(zone, anchors, ext, lms, cams, init='ours')
    _, d0 = sv0.cost(collect_detail=True)
    for lm in [l for l, (P, e) in d0.items() if e is not None and e > 90.0]:
        zone.pop(lm, None)
    print(f'ancres: {list(anchors)}')
    print(f'decalage nord de TOUTE la zone (4 cams + monde re-triangule), '
          f'ancres fixes, {args.rounds} rounds/cellule\n')
    print(f'{"dy (m)":>8s}  {"cout ancre":>11s}   {"vs dy=0":>9s}')

    out = {}
    base = None
    for dy in dys:
        sv = aj.Solver(zone, anchors, ext, lms, cams, init='ours')
        for c in aj.AMB:
            sv.theta[c][1] += dy
            y = sv.theta[c][1]
            sv.bounds[c][1] = (y - SLACK, y + SLACK)
        cost = sv.descend(rounds=args.rounds, verbose=False)
        out[dy] = cost
        if dy == 0:
            base = cost
        print(f'{dy:8.0f}  {cost:11.2f}   {"" if base is None else f"{cost-base:+9.2f}"}',
              flush=True)

    if base is not None:
        print('\nrelecture:')
        for dy, c in sorted(out.items()):
            bar = '#' * max(0, int((c - base) / 5))
            print(f'  {dy:+6.0f} m  {c:8.2f}  {bar}')
    dst = os.path.join(REPO, 'tools', 'generated', 'ambrosia_sweep')
    os.makedirs(dst, exist_ok=True)
    json.dump(out, open(os.path.join(dst, 'northshift.json'), 'w'), indent=1)
    print(f'\n-> {dst}/northshift.json')


if __name__ == '__main__':
    main()
