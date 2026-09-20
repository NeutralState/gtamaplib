#!/usr/bin/env python3
"""Podiums / socles des tours existantes, extrudes depuis les polygones V16 (2026-09-20).

  * Vizcayne (Podium): V16 2435 (l'ilot entier, 5251 m2, arcades eclairees en rose dans Shitzu Squalo 01):
    hauteur 25 m ESTIMEE (etages 2-7 IRL = Everglades Plaza; les arcades roses de Shitzu Squalo 01 sont la causeway au premier plan, pas le podium).
  * Four Seasons (Podium): V16 1939 (6471 m2, terrasse piscine IRL "2 acres" au 7e etage) + 1955 (aile ouest):
    hauteur 32 m lue dans Tennis Stadium (4K) (bande claire de la terrasse aux palmiers a +31..+35 m avec les anneaux-guides).
  * Stephen P. Clark (Podium): V16 2413 (4534 m2, socle nord) 14 m ESTIME, 3857 (station Metrorail, 3058 m2)
    18 m ESTIME (station aerienne), rampe helicoidale = octogones 2407 (ext.) / 2410 (noyau) 12 m ESTIME;
    aucune cam nette sur ce socle (Metro (NE) (B) et Intersection (SE) a ~850 m, flou).

Usage: gen_podiums.py [--out brouillon.json] [--apply]
"""
import json, sys, os, argparse
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'gtamapdata')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import horizon_resect as HR

POLYS = json.load(open(os.path.join(ROOT, 'v16_footprints.json')))['polygons']


def ring(i):
    return np.array(POLYS[i]['ring'], float)


def ground(poly):
    zs = [HR.ground(x, y) for x, y in poly]
    zs = [z for z in zs if z is not None and np.isfinite(z)]
    return float(np.median(zs)) if zs else 2.0


def loop_edges(poly, z):
    P = [[float(x), float(y), float(z)] for x, y in poly]
    return [[P[k], P[(k + 1) % len(P)]] for k in range(len(P))]


def vertical_edges(poly, z0, z1, every=1):
    return [[[float(x), float(y), float(z0)], [float(x), float(y), float(z1)]] for x, y in poly[::every]]


def extrude(poly, z0, z1, ring_step=None, every=1):
    E = loop_edges(poly, z0) + loop_edges(poly, z1) + vertical_edges(poly, z0, z1, every)
    if ring_step:
        for z in np.arange(z0 + ring_step, z1 - 0.01, ring_step):
            E += loop_edges(poly, z)
    return E


def helix(poly, z0, z1, turns):
    """Ligne helicoidale le long d'un anneau (rampe)."""
    P = np.array(poly, float); n = len(P); E = []
    steps = int(turns * n)
    for k in range(steps):
        a = P[k % n]; b = P[(k + 1) % n]
        za = z0 + (z1 - z0) * k / steps; zb = z0 + (z1 - z0) * (k + 1) / steps
        E.append([[float(a[0]), float(a[1]), za], [float(b[0]), float(b[1]), zb]])
    return E


def build():
    out = {}
    # Vizcayne
    p = ring(2435); z0 = ground(p)
    E = extrude(p, z0, z0 + 25.0, ring_step=4.2)
    out['Vizcayne (Podium)'] = {'color': '#4ade80', 'world_edges': E,
        'note': 'Podium = ilot V16 2435 (Everglades Plaza + parking, etages 2-7 IRL); hauteur 25 m ESTIMEE (aucune cam nette: dans Shitzu Squalo 01 les arcades roses devant sont la causeway); anneaux tous les 4.2 m; sol %.1f' % z0,
        '_credit': 'gen_podiums.py 2026-09-20'}
    # Four Seasons
    p = ring(1939); z0 = ground(p)
    E = extrude(p, z0, z0 + 32.0, ring_step=4.6)
    q = ring(1955); E += extrude(q, ground(q), ground(q) + 32.0, ring_step=4.6)
    out['Four Seasons (Podium)'] = {'color': '#60a5fa', 'world_edges': E,
        'note': 'Socle = V16 1939 (terrasse piscine, 7e etage IRL) + 1955 (aile ouest); hauteur 32 m lue dans Tennis Stadium (4K) (terrasse aux palmiers a +31..+35 m avec les anneaux-guides, 7e etage IRL); sol %.1f' % z0,
        '_credit': 'gen_podiums.py 2026-09-20'}
    # Stephen P. Clark
    p = ring(2413); z0 = ground(p)
    E = extrude(p, z0, z0 + 14.0, ring_step=4.7)
    s = ring(3857); zs = ground(s)
    E += extrude(s, zs, zs + 18.0, ring_step=6.0)
    o = ring(2407); zo = ground(o); c = ring(2410)
    E += extrude(o, zo, zo + 12.0, ring_step=3.0) + extrude(c, zo, zo + 12.0) + helix(o, zo, zo + 12.0, 2)
    out['Stephen P. Clark (Podium)'] = {'color': '#fb923c', 'world_edges': E,
        'note': 'Socle nord = V16 2413, 14 m ESTIME; station Metrorail = V16 3857, 18 m ESTIME (station aerienne dans le batiment IRL); rampe helicoidale = octogones V16 2407/2410, 12 m ESTIME (2 tours); aucune cam nette a < 700 m: a affiner quand une frame le montrera',
        '_credit': 'gen_podiums.py 2026-09-20'}
    for v in out.values():
        v['world_edges'] = [[[round(c, 2) for c in pt] for pt in e] for e in v['world_edges']]
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out'); ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(); meshes = build()
    for k, v in meshes.items():
        print('%-28s %5d aretes' % (k, len(v['world_edges'])))
    if a.out:
        json.dump(meshes, open(a.out, 'w'), indent=1, ensure_ascii=True); print('brouillon ->', a.out)
    if a.apply:
        path = os.path.join(ROOT, 'building_meshes_procedural.json')
        M = json.load(open(path)); M.update(meshes)
        json.dump(M, open(path, 'w'), indent=1, ensure_ascii=True); print('applique ->', path)
