#!/usr/bin/env python3
"""ground_points.py — features mono-cam AU SOL, par rayon x plan. [GROUND-V1]

Meme levier que lake_shoreline.py, generalise: un point de route, de rive
ou de parking n'est pas triangulable a une seule cam, mais il vit sur un
plan horizontal connu -> l'intersection du rayon de clic avec ce plan le
place. On declare le plan une fois, l'outil fait le reste.

Plans declares (monde H, bounty clos 2026-07-25):
  * Ambrosia Main St / Main St, z 18.87
    Origine: la cam Bikers (S2/56) roule SUR cette rue; sa pose H donne
    z 20.265, moins la hauteur cam au-dessus du bitume mesuree a ~1.4 m
    (ligne d'horizon a pitch ~0 coupant la tete des motards assis).
    Recoupe rlx: "silo maybe even higher than ambrosia main st (even
    though not much)" — silo_z 19.655 vs 18.87.
  * Red Boxville (base), z 15.16
    Origine: rlx, "silo is 4.5 above boxville" -> 19.655 - 4.5.

L'incertitude est propagee: dxy/dz = 1/tan(depression), ecrite en error_m.
Dry-run par defaut.
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

CAM = 'Ambrosia 02 (Panorama)'
Z_SIGMA = 1.0

PLANES = [
    # (prefixes des landmarks, z du plan, etiquette de provenance)
    (('Ambrosia Main St (', 'Main St ('), 18.87,
     'rue: cam Bikers z 20.265 - 1.4 m (hauteur cam mesuree par la ligne d horizon)'),
    (('Red Boxville (B', 'Red Boxville (F', 'Red Boxville (R'), 15.16,
     'sol du boxville: silo_z 19.655 - 4.5 (delta rlx)'),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    cam = common.get_cam(CAM)
    o = np.asarray(cam.xyz, float)
    rows = []
    for prefixes, zp, why in PLANES:
        for lm, p in sorted((px.get(CAM) or {}).items()):
            if p is None or not lm.startswith(prefixes):
                continue
            d = np.asarray(cam.get_pixel_direction(p), float)
            d /= np.linalg.norm(d)
            if d[2] >= -1e-4:
                print(f'  {lm}: rayon au-dessus de l horizon, SKIP')
                continue
            t = (zp - o[2]) / d[2]
            P = o + t * d
            dist = float(np.hypot(*(P - o)[:2]))
            depr = math.degrees(math.asin(-d[2]))
            sens = 1.0 / math.tan(math.radians(depr))
            err = round(math.hypot(sens * Z_SIGMA, 0.5), 1)
            old = lms.get(lm)
            oldz = old['xyz'][2] if isinstance(old, dict) and old.get('xyz') else None
            rows.append((lm, P, dist, sens, err, zp, why, oldz))

    print(f'cam {CAM} z={o[2]:.2f}\n')
    print(f'{"landmark":30s} {"z plan":>7s} {"x":>9s} {"y":>9s} {"dist":>6s} {"err":>5s}  {"ancien z":>9s}')
    for lm, P, dist, sens, err, zp, why, oldz in rows:
        old_s = f'{oldz:9.1f}' if oldz is not None else '        -'
        print(f'{lm:30s} {zp:7.2f} {P[0]:9.1f} {P[1]:9.1f} {dist:6.0f} {err:5.1f} {old_s}')

    if not args.apply:
        print(f'\n{len(rows)} points. DRY-RUN (--apply pour ecrire).')
        return
    for lm, P, dist, sens, err, zp, why, oldz in rows:
        e = lms.get(lm) if isinstance(lms.get(lm), dict) else {}
        e.update({
            'xyz': [round(float(P[0]), 2), round(float(P[1]), 2), zp],
            'source_cameras': [CAM],
            'error_m': err,
            'zone': 'ambrosia',
            'method': f'rayon x plan z={zp} (GROUND-V1, monde H); {why}; '
                      f'sensibilite {sens:.1f} m/m de datum',
        })
        lms[lm] = e
    path = os.path.join(REPO, 'gtamapdata', 'landmarks.json')
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(lms, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)
    print(f'\nAPPLIED: {len(rows)} points au sol.')


if __name__ == '__main__':
    main()
