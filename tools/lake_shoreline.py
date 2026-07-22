#!/usr/bin/env python3
"""lake_shoreline.py — LAKE-V1 (2026-07-22): le contour du lac Leonida par
rayon x plan d'eau.

Panorama (resolue +-0.2m au solve joint) marque 26 points de rive 'Lake
Leonida (A)..(Z)' — mono-cam, jamais triangulables. Mais l'eau est un plan
z=constante parfait: chaque rayon de clic intersecte z=Z_WATER -> point
monde. C'est le meme levier que la ligne b (ray x geometrie connue).

Datum Z_WATER = 5.0 +-0.5, encadre par:
  - rive au Red Boxville ~5.3 (rlx, avec notre pose pano)
  - rue au pied du silo ~4.6 (cam Bikers z 6.0 - 1.4 mesure horizon-tetes)
L'incertitude est propagee par point: dxy/dz = 1/tan(depression) — les
points lointains glissent le long du rayon si le datum bouge (honnete,
ecrit dans error_m).

Dry-run par defaut; --apply ecrit les LMs (zone ambrosia, note methode).
--z pour re-deriver avec un autre datum le jour ou il se raffine.
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
os.chdir(REPO)

import numpy as np
import common

CAM = 'Ambrosia 02 (Panorama)'
Z_WATER_DEFAULT = 5.0
Z_SIGMA = 0.5
LETTERS = [chr(ord('A') + i) for i in range(26)]
# doublons pixel-exact au bord de frame (clics dupliques)
DUPES = {'Lake Leonida (Z)': 'Lake Leonida (X)',
         'Lake Leonida (Y)': 'Lake Leonida (W)'}


def atomic(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--z', type=float, default=Z_WATER_DEFAULT)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    px = json.load(open('gtamapdata/pixels.json'))
    lms = json.load(open('gtamapdata/landmarks.json'))
    cam = common.get_cam(CAM)
    o = np.asarray(cam.xyz, float)
    zw = args.z

    rows = []
    for L in LETTERS:
        name = f'Lake Leonida ({L})'
        p = px[CAM].get(name)
        if p is None:
            continue
        d = np.asarray(cam.get_pixel_direction(p), float)
        d /= np.linalg.norm(d)
        if d[2] >= -1e-4:
            print(f'  {name}: rayon au-dessus de l horizon, SKIP')
            continue
        t = (zw - o[2]) / d[2]
        P = o + t * d
        dist = float(np.hypot(*(P - o)[:2]))
        depr = math.degrees(math.asin(-d[2]))
        sens = 1.0 / math.tan(math.radians(depr))     # m de xy par m de datum
        err = round(math.hypot(sens * Z_SIGMA, 0.3), 1)
        dup = DUPES.get(name)
        edge = p[0] <= 20 or p[0] >= 3820
        rows.append((name, P, dist, depr, sens, err, dup, edge))

    print(f'datum eau z={zw} (+-{Z_SIGMA})  cam {CAM} z={o[2]:.1f}')
    print(f'{"point":22s} {"x":>9s} {"y":>9s} {"dist":>6s} {"depr":>5s} '
          f'{"sens":>5s} {"err_m":>5s}')
    for name, P, dist, depr, sens, err, dup, edge in rows:
        tag = ' (dup de ' + dup.split('(')[1] if dup else ('  [bord frame]' if edge else '')
        print(f'{name:22s} {P[0]:9.1f} {P[1]:9.1f} {dist:6.0f} {depr:5.2f} '
              f'{sens:5.1f} {err:5.1f}{tag}')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return

    n = 0
    for name, P, dist, depr, sens, err, dup, edge in rows:
        e = lms.get(name) or {}
        e.update({
            'xyz': [round(float(P[0]), 2), round(float(P[1]), 2), zw],
            'source_cameras': [CAM],
            'error_m': err,
            'zone': 'ambrosia',
            'method': f'ray x plan d eau z={zw} (LAKE-V1); sens {sens:.1f} m/m de datum',
        })
        if dup:
            e['note'] = f'clic pixel-exact identique a {dup} (bord de frame)'
        lms[name] = e
        n += 1
    atomic('gtamapdata/landmarks.json', lms)
    print(f'\nAPPLIED: {n} points de rive ecrits (z={zw}).')


if __name__ == '__main__':
    main()
