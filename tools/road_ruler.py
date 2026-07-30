#!/usr/bin/env python3
"""road_ruler.py — la route comme REGLE photogrammetrique. [ROAD-RULER-V1]

Constat qui declenche l'outil: tout le canyon 3D repose sur deux nombres
INVENTES (z de la route en bas de cadre et sous le pont). Les reseaux de
profondeur ne peuvent pas les corriger (ils saturent au-dela de 700 m).

Mais la scene contient sa propre regle: une route a une LARGEUR CONSTANTE.
Donc, sans aucun reseau et sans 2e vue:

    largeur_pixels(s) * profondeur(s) = focale * largeur_reelle = CONSTANTE

La largeur mesuree en pixels le long de la route donne donc la profondeur
RELATIVE exacte de chaque point de la chaussee. Une seule inconnue reste:
la largeur reelle (un scalaire), et elle fixe toute l'echelle du canyon.

Methode: pour chaque point de la ligne de route tracee par Alexandre, on
balaye PERPENDICULAIREMENT dans l'image et on detecte les deux bords de
l'asphalte (l'asphalte est sombre et peu sature, les accotements sont
clairs/ocres). Largeur -> profondeur relative -> profil z de la chaussee.

Sortie: profil mesure z(d) de la route, pente reelle, et le tableau
d'echelle (z0/z1 impliques pour differentes largeurs de chaussee).

Usage: PYTHONPATH=. python3 tools/road_ruler.py [--width 9.0] [--debug]
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
from PIL import Image, ImageDraw
import common

CAM = 'Mount Kalaga National Park 04 (Mountain Pass) (X)'
HALF = 160          # demi-fenetre de balayage (px)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--width', type=float, default=9.0,
                    help='largeur reelle de la chaussee (m) — la SEULE inconnue')
    ap.add_argument('--step', type=int, default=6, help='un point sur N')
    ap.add_argument('--debug', action='store_true')
    args = ap.parse_args()

    lines = json.load(open(os.path.join(REPO, 'tools', 'generated', 'canyon_lines.json')))
    cam = common.get_cam(CAM)
    o = np.asarray(cam.xyz, float)
    img = Image.open(os.path.join(REPO, 'frames', f'{CAM}.png')).convert('RGB')
    a = np.asarray(img, np.float32)
    L = a.mean(axis=2)
    SAT = a.max(axis=2) - a.min(axis=2)          # asphalte = peu sature
    H, W = L.shape

    rx = np.asarray(lines['road_center']['x'], float)
    ry = np.asarray(lines['road_center']['y'], float)

    def road_px(v):
        return float(np.clip(v, 0, None))

    samples = []
    for i in range(2, len(rx) - 2, args.step):
        x0, y0 = rx[i], ry[i]
        tx, ty = rx[i + 2] - rx[i - 2], ry[i + 2] - ry[i - 2]
        n = math.hypot(tx, ty)
        if n < 1e-6:
            continue
        px_, py_ = -ty / n, tx / n               # perpendiculaire image
        # profil le long de la perpendiculaire
        prof, sats, pos = [], [], []
        for s in np.arange(-HALF, HALF, 1.0):
            xx, yy = x0 + s * px_, y0 + s * py_
            if not (1 <= xx < W - 1 and 1 <= yy < H - 1):
                continue
            prof.append(L[int(yy), int(xx)])
            sats.append(SAT[int(yy), int(xx)])
            pos.append(s)
        if len(prof) < 60:
            continue
        prof = np.array(prof); sats = np.array(sats); pos = np.array(pos)
        c = np.argmin(np.abs(pos))
        base_l, base_s = prof[c], sats[c]
        # bord = ou la luminance ET la saturation quittent le regime asphalte
        def edge(direction):
            thr_l = base_l + 26.0
            thr_s = base_s + 16.0
            k = c
            while 0 < k < len(pos) - 1:
                k += direction
                if k <= 0 or k >= len(pos) - 1:
                    return None
                if prof[k] > thr_l and sats[k] > thr_s:
                    return pos[k]
            return None
        el, er = edge(-1), edge(+1)
        if el is None or er is None:
            continue
        w_px = abs(er - el)
        if not (8 < w_px < 2 * HALF):
            continue
        d = np.asarray(cam.get_pixel_direction((float(x0), float(y0))), float)
        samples.append((float(x0), float(y0), w_px, d / np.linalg.norm(d), el, er))

    if len(samples) < 8:
        print(f'seulement {len(samples)} mesures de largeur — echec.')
        return
    wpx = np.array([s[2] for s in samples])
    print(f'{len(samples)} largeurs mesurees: {wpx.min():.0f} - {wpx.max():.0f} px '
          f'(mediane {np.median(wpx):.0f})')

    # focale en pixels
    f_px = cam.w / (2 * math.tan(math.radians(cam.hfov) / 2))
    print(f'focale {f_px:.0f} px, hfov {cam.hfov:.2f} deg')

    # profondeur = f * W_reelle / largeur_px  (perpendiculairement a l'axe)
    vhat = np.asarray(cam.get_pixel_direction((cam.w / 2, cam.h / 2)), float)
    vhat /= np.linalg.norm(vhat)
    P = []
    for x0, y0, w_px, r, el, er in samples:
        z_axis = f_px * args.width / w_px        # profondeur le long de l'axe
        t = z_axis / float(np.dot(r, vhat))
        P.append(o + t * r)
    P = np.array(P)
    d_xy = np.hypot(P[:, 0] - o[0], P[:, 1] - o[1])
    order = np.argsort(d_xy)
    P, d_xy = P[order], d_xy[order]
    A_, B_ = np.polyfit(d_xy, P[:, 2], 1)[::-1]
    resid = P[:, 2] - (A_ + B_ * d_xy)
    print(f'\nPROFIL MESURE de la chaussee (largeur reelle supposee {args.width} m):')
    print(f'  distance {d_xy.min():.0f} -> {d_xy.max():.0f} m')
    print(f'  z {P[:, 2].min():.1f} -> {P[:, 2].max():.1f} m')
    print(f'  droite: z = {A_:.1f} + {B_:.4f} * d_xy   (pente {100 * B_:.1f}%), '
          f'rms {np.sqrt(np.mean(resid ** 2)):.1f} m')
    print(f'  -> z bas de cadre {A_ + B_ * d_xy.min():.1f} m, '
          f'z sous le pont {A_ + B_ * d_xy.max():.1f} m '
          f'(le modele actuel DECLARE 30 et 55)')

    print(f'\nSENSIBILITE a la seule inconnue (largeur de chaussee):')
    print(f'  {"largeur":>8s} {"z bas":>7s} {"z pont":>7s} {"pente":>7s} {"d max":>7s}')
    for Wr in (7.0, 8.0, 9.0, 10.0, 12.0, 14.0):
        k = Wr / args.width
        z = A_ * k + B_ * k * d_xy               # tout echelle lineairement
        print(f'  {Wr:8.1f} {z.min():7.1f} {z.max():7.1f} {100 * B_:6.1f}% '
              f'{d_xy.max() * k:7.0f}')

    if args.debug:
        dr = ImageDraw.Draw(img)
        for x0, y0, w_px, r, el, er in samples:
            i = samples.index((x0, y0, w_px, r, el, er))
            tx, ty = 0, 0
            dr.ellipse([x0 - 3, y0 - 3, x0 + 3, y0 + 3], fill=(56, 189, 248))
        for x0, y0, w_px, r, el, er in samples:
            idx = None
        out = os.path.join(REPO, 'tools', 'generated', 'road_ruler_debug.png')
        img.save(out)
        print(f'\n-> {out}')


if __name__ == '__main__':
    main()
