#!/usr/bin/env python3
"""import_rlx_mountains.py — la couche [rlx] de comparaison. [RLX-MTN-V1]

Porte les 6 montagnes wireframe de rlx (upstream 5016dd2, classe Mountain)
en meshs '[rlx] ...' dans notre UI, pour comparer son monde au notre.
SA construction, SES chiffres: crete = points sur rayons a des distances
DECLAREES a la main (chiffres ronds); pentes avant/arriere -30 deg vers
z=base (20); flancs -60 deg (ou -30). On ne les melange pas a nos meshs —
c'est une couche de reference, pas une adoption.

Usage: PYTHONPATH=. python3 tools/import_rlx_mountains.py [--apply]
"""
import argparse
import json
import math
import os
import sys
import tempfile

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
import common

MESH_PATH = os.path.join(REPO, 'tools', 'data', 'rlx_mountains_meshes.json')  # PAS l'UI (Alexandre: garder pour comparer, ne pas montrer)
BASE = 20.0
COLOR = '#94a3b8'

# (nom, cam, [(px, py, distance_m)...], slope, side_slope)
# distances = les chiffres DECLARES de rlx (5016dd2)
MOUNTAINS = [
    ('Mount Ambrosia', 'Ambrosia 01 (Bikers)',
     [(23.5, 533, 3200), (325, 560, 3000), (794.5, 345, 2800), (1219, 201, 2600),
      (1913, 267, 2500), (2345, 415.5, 2400), (2865, 580, 2400), (3099, 580, 2500)],
     30, 60),
    ('Mount Ambrosia (X)', 'Hedge (B) (X)',
     [(364.5, 511.5, 8200), (431, 501, 8000), (475, 495, 7800)], 30, 60),
    ('Mount Leonida', 'Mount Kalaga National Park 02 (Helicopter) (X)',
     [(1292, 2160, 200), (1901, 1643, 300), (3840, 855, 400)], 30, 60),
    ('Mount Mountain', 'Diner (N)',
     [(1478.5, 66.5, 1900), (1543, 52.5, 2000), (1603, 69, 2100)], 30, 30),
    ('Mount Waffles', 'Diner (N)',
     [(654, 90, 1150), (814, 102, 1200), (938, 67, 1300), (1075, 15, 1450),
      (1136, 8.5, 1500), (1194, 16, 1450), (1443, 57.5, 1450)], 30, 60),
    ('Waffles Ridge', 'Gas Station (Lucia)',
     [(1214, 489, 2900), (1255, 486, 2900), (1320, 485, 2900)], 30, 30),
]


def build(name, cam_name, pts, slope, side_slope):
    cam = common.get_cam(cam_name)
    o = np.asarray(cam.xyz, float)
    tops = []
    for x, y, dist in pts:
        d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
        d /= np.linalg.norm(d)
        t = dist / float(np.hypot(d[0], d[1]))
        tops.append(o + t * d)
    edges = []
    sl = math.tan(math.radians(slope))
    for i, T in enumerate(tops):
        if i:
            edges.append([list(tops[i - 1]), list(T)])
        # pente avant (vers la cam) et arriere (a l'oppose), -30 deg -> z=BASE
        for sgn in (+1.0, -1.0):
            v = (o[:2] - T[:2]) * sgn
            v /= (np.linalg.norm(v) + 1e-9)
            run = max(0.0, (T[2] - BASE)) / sl
            F = [float(T[0] + v[0] * run), float(T[1] + v[1] * run), BASE]
            edges.append([list(T), F])
    # flancs
    ss = math.tan(math.radians(side_slope))
    for T, other in ((tops[0], tops[1]), (tops[-1], tops[-2])):
        v = (T[:2] - other[:2])
        v /= (np.linalg.norm(v) + 1e-9)
        run = max(0.0, (T[2] - BASE)) / ss
        F = [float(T[0] + v[0] * run), float(T[1] + v[1] * run), BASE]
        edges.append([list(T), F])
    zs = [t[2] for t in tops]
    print(f'[rlx] {name:20s}: {len(tops)} pts de crete, z {min(zs):.0f}-{max(zs):.0f}')
    return {'color': COLOR, 'world_edges': [[list(map(float, a)), list(map(float, b))]
                                            for a, b in edges]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    out = {}
    for name, cam_name, pts, slope, side in MOUNTAINS:
        try:
            out[f'[rlx] {name}'] = build(name, cam_name, pts, slope, side)
        except Exception as ex:
            print(f'[rlx] {name}: ECHEC ({ex})')
    if not args.apply:
        print('DRY-RUN (--apply pour ecrire).')
        return
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    for k in [k for k in mesh if k.startswith('[rlx] ')]:
        mesh.pop(k)
    mesh.update(out)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'APPLIED: {len(out)} montagnes [rlx]')


if __name__ == '__main__':
    main()
