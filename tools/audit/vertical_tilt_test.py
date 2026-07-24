#!/usr/bin/env python3
"""vertical_tilt_test.py — le test de rlx, quantifie. [VERT-TILT-V1]

rlx (2026-07-24): 'i would bet that in that 54 image, the verticals are more
tilted than the brator chimney and the lampposts near the boxville.'

Test SANS triangulation (ne depend que de la pose):
  - pour un pixel p sur une structure verticale reelle de la frame, on
    de-projette p, on prend un point a distance D, et on projette la
    VERTICALE MONDE passant par ce point -> inclinaison PREDITE en p.
    (l'inclinaison predite ne depend quasiment pas de D: c'est la direction
    du point de fuite vertical vue de p.)
  - on MESURE l'inclinaison reelle des aretes de la structure autour de p
    par tenseur de structure (gradients Sobel, aretes quasi-verticales).
  - |predite - mesuree| = l'erreur que rlx veut voir. On compare les poses.

Usage: PYTHONPATH=. python3 tools/audit/vertical_tilt_test.py
"""
import json
import math
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(THIS))
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, REPO)
os.chdir(REPO)

import numpy as np
from PIL import Image
import common

PANO = 'Ambrosia 02 (Panorama)'

# poses issues du sweep ancre (solve joint complet, cellule pinnee)
WORLDS = {
    'hfov 54 (anchored winner)': {'xyz': [-2465.72, 5111.18, 83.29],
                                  'ypr': [160.15, -4.15, -0.14], 'fov': [54.0, None]},
    'hfov 48 (rlx candidate)':   {'xyz': [-2449.72, 5101.18, 91.29],
                                  'ypr': [160.15, -3.85, 0.41], 'fov': [48.0, None]},
    'applied solution (53.64)':  None,   # etat disque
}

# structures verticales fines et nettes de la frame (clics existants),
# avec l'offset vers le bas ou vit le FUT (pas le sommet/reservoir)
TARGETS = [
    ('Wheelabrator South Broward (TE)', 70, 'brator chimney'),
    ('USSM Smokestack (7)', 60, 'smokestack 7'),
    ('USSM Smokestack (4)', 60, 'smokestack 4'),
    ('Daytona Beach Water Tower', 55, 'lollipop legs'),
    ('Flat Water Tower', 40, 'flat water tower'),
    ('Very Tall Water Tower', 60, 'very tall water tower'),
    ('Titan America', 50, 'titan america'),
    ('1500 Sonora Ave (Silo) (L)', 60, 'silo left edge'),
]

GRAY = None


def measured_tilt(gray, px, py, half_w=26, half_h=70, max_dev=25.0):
    """Inclinaison moyenne (deg, + = penche vers la droite en montant) des
    aretes quasi-verticales dans la fenetre, ponderee par |grad|."""
    x0, x1 = int(px - half_w), int(px + half_w)
    y0, y1 = int(py - half_h), int(py + half_h)
    h, w = gray.shape
    if x0 < 1 or y0 < 1 or x1 >= w - 1 or y1 >= h - 1:
        return None, 0.0
    win = gray[y0:y1, x0:x1]
    gx = np.zeros_like(win)
    gy = np.zeros_like(win)
    gx[:, 1:-1] = win[:, 2:] - win[:, :-2]
    gy[1:-1, :] = win[2:, :] - win[:-2, :]
    mag = np.hypot(gx, gy)
    # arete = perpendiculaire au gradient: e = (-gy, gx)
    ex, ey = -gy, gx
    # angle depuis la verticale image (y vers le bas): tilt = atan2(ex, -ey)
    tilt = np.degrees(np.arctan2(ex, -ey))
    tilt = (tilt + 90) % 180 - 90        # ramene dans [-90, 90)
    m = (mag > np.percentile(mag, 88)) & (np.abs(tilt) < max_dev)
    if m.sum() < 30:
        return None, 0.0
    wgt = mag[m]
    a = np.radians(tilt[m] * 2.0)         # moyenne circulaire (axe, pas vecteur)
    mean = math.degrees(math.atan2(np.average(np.sin(a), weights=wgt),
                                   np.average(np.cos(a), weights=wgt))) / 2.0
    return mean, float(wgt.sum())


def predicted_tilt(cam, px, py, D=1200.0):
    """Inclinaison de la verticale monde passant par le point vu en (px, py)
    a distance D. Independante de D a <0.05 deg pres."""
    o = np.asarray(cam.xyz, float)
    d = np.asarray(cam.get_pixel_direction((px, py)), float)
    d /= np.linalg.norm(d)
    P = o + D * d
    a = cam.get_pixel([float(P[0]), float(P[1]), float(P[2])])
    b = cam.get_pixel([float(P[0]), float(P[1]), float(P[2] + 40.0)])
    if a is None or b is None:
        return None
    dx, dy = b[0] - a[0], b[1] - a[1]
    return math.degrees(math.atan2(dx, -dy))


def main():
    px_all = json.load(open('gtamapdata/pixels.json'))
    pano_px = px_all[PANO]
    im = Image.open(f'frames/{PANO}.png').convert('L')
    gray = np.asarray(im, dtype=np.float32)

    rows = []
    for lm, off, label in TARGETS:
        p = pano_px.get(lm)
        if p is None:
            continue
        mt, wsum = measured_tilt(gray, p[0], p[1] + off)
        if mt is None:
            print(f'  (skip {label}: pas assez d aretes verticales)')
            continue
        rows.append((label, p[0], p[1] + off, mt, wsum))

    print(f'{len(rows)} structures verticales mesurees dans la frame\n')
    header = f'{"structure":26s} {"px":>6s} {"mesure":>8s}'
    for name in WORLDS:
        header += f' | {name[:22]:>22s}'
    print(header)

    # GOTCHA gtamaplib: ml.get_camera() rend la MEME instance -> on ne peut
    # pas pre-construire plusieurs cams; on re-applique l'etat a chaque usage
    totals = {name: [] for name in WORLDS}
    for label, x, y, mt, wsum in rows:
        line = f'{label:26s} {x:6.0f} {mt:+7.2f}°'
        for name, st in WORLDS.items():
            cam = common.get_cam(PANO, st) if st else common.get_cam(PANO)
            pt = predicted_tilt(cam, x, y)
            if pt is None:
                line += f' | {"n/a":>22s}'
                continue
            err = abs(pt - mt)
            totals[name].append(err)
            line += f' | pred {pt:+6.2f}° err {err:5.2f}°'
        print(line)

    print('\nERREUR MOYENNE |predite - mesuree| (plus bas = pose plus juste):')
    for name in WORLDS:
        v = totals[name]
        if v:
            print(f'  {name:28s} {np.mean(v):5.2f}°   (median {np.median(v):5.2f}°, n={len(v)})')


if __name__ == '__main__':
    main()
