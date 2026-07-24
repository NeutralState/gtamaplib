#!/usr/bin/env python3
"""ambrosia_sweep.py — la grille de rlx x le cout joint ancre. [AMB-SWEEP-V1]

Le debat du fil (2026-07-24): rlx balaie (pano fov x street z) avec un cout
SANS ancre absolue -> vallee plate, il ne peut pas trancher 48-vs-53 ni le
datum 5-vs-15. Notre solve joint est ancre mais n'explore pas (descente
bornee). Cet outil fait les deux: pour chaque cellule (pano_hfov, dz
collectif du monde entier), on PIN ces deux hypotheses et on laisse le
solve joint borne optimiser tout le reste (26 params libres) — le cout
final est comparable de cellule en cellule, ET il contient les ancres
absolues (FAA MIA / MIA N / SSB, auditees non-circulaires).

Lecture: le minimum de la table = le monde que TOUTES les donnees
(415 obs + rayons externes + ancres) preferent. Si la vallee est plate en
dz -> le datum est vraiment mou et rlx a raison de douter; si elle monte
franchement -> les ancres tranchent.

Usage:  PYTHONPATH=. python3 tools/ambrosia_sweep.py [--rounds 18]
        [--fov 47:55:1] [--dz 0:12:2] [--out tools/generated/ambrosia_sweep]
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

PANO = 'Ambrosia 02 (Panorama)'


def parse_range(s):
    a, b, st = (float(x) for x in s.split(':'))
    out = []
    v = a
    while v <= b + 1e-9:
        out.append(round(v, 3))
        v += st
    return out


def cell_solve(px, lms, cams, quarantined, pano_fov, dz, rounds):
    zone, anchors, ext_rays = aj.collect(px, lms, cams, use_brator=True, no_kalaga=False)
    for lm in quarantined:
        zone.pop(lm, None)
    sv = aj.Solver(zone, anchors, ext_rays, lms, cams, init='ours', use_corpus=False)
    # hypothese 1: pano hfov PINNE
    i_f = 6
    sv.theta[PANO][i_f] = pano_fov
    sv.bounds[PANO][i_f] = (pano_fov - 0.05, pano_fov + 0.05)
    # hypothese 2: dz COLLECTIF pinne (tout le monde monte ensemble;
    # les ancres absolues, elles, ne bougent pas -> ce sont elles qui payent)
    for c in aj.AMB:
        sv.theta[c][2] += dz
        z = sv.theta[c][2]
        sv.bounds[c][2] = (z - 0.75, z + 0.75)
    sv.descend(rounds=rounds, verbose=False)
    return sv.cost()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rounds', type=int, default=18)
    ap.add_argument('--fov', default='47:55:1')
    ap.add_argument('--dz', default='0:12:2')
    ap.add_argument('--out', default=os.path.join(REPO, 'tools', 'generated', 'ambrosia_sweep'))
    args = ap.parse_args()
    fovs = parse_range(args.fov)
    dzs = parse_range(args.dz)
    os.makedirs(args.out, exist_ok=True)

    px, lms, cams = aj.load()
    # quarantaine calculee UNE fois a l'etat courant (memes exclusions pour
    # toutes les cellules -> couts comparables)
    zone, anchors, ext_rays = aj.collect(px, lms, cams, use_brator=True, no_kalaga=False)
    sv0 = aj.Solver(zone, anchors, ext_rays, lms, cams, init='ours', use_corpus=False)
    _, det0 = sv0.cost(collect_detail=True)
    quarantined = [lm for lm, (P, e) in det0.items() if e is not None and e > 90.0]
    print(f'quarantaine fixe ({len(quarantined)}): {quarantined}')
    print(f'ancres: {list(anchors)}')
    print(f'grille: pano fov {fovs} x dz {dzs}, {args.rounds} rounds/cellule\n')

    table = np.full((len(fovs), len(dzs)), np.nan)
    for i, f in enumerate(fovs):
        row = []
        for j, dz in enumerate(dzs):
            c = cell_solve(px, lms, cams, quarantined, f, dz, args.rounds)
            table[i, j] = c
            row.append(f'{c:8.2f}')
        print(f'p {f:5.1f}  ' + ' '.join(row), flush=True)

    # sortie table texte style rlx
    lines = ['pano fov \\ dz collectif (m) — cout joint ancre final',
             '         ' + ' '.join(f'{dz:8.0f}' for dz in dzs)]
    for i, f in enumerate(fovs):
        lines.append(f'p {f:5.1f}  ' + ' '.join(f'{table[i, j]:8.2f}' for j in range(len(dzs))))
    best = np.unravel_index(np.nanargmin(table), table.shape)
    lines.append(f'\nminimum: pano fov {fovs[best[0]]}, dz +{dzs[best[1]]:.0f}m, cout {table[best]:.2f}')
    txt = '\n'.join(lines)
    open(os.path.join(args.out, 'sweep.txt'), 'w').write(txt + '\n')
    print('\n' + txt)
    json.dump({'fovs': fovs, 'dzs': dzs, 'table': table.tolist()},
              open(os.path.join(args.out, 'sweep.json'), 'w'), indent=1)
    print(f"\n-> {args.out}/sweep.txt")


if __name__ == '__main__':
    main()
