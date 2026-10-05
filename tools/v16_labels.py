#!/usr/bin/env python3
"""v16_labels.py — repere les libelles texte de la V16 (MT. KALAGA NATIONAL PARK, VICE CITY...). [LABELS-V1 2026-10-05]

Le SVG (export Figma) n'a ni <text> ni id: les lettres sont des chemins vectorises. On les retrouve sur le raster de la
V16 (rendu du meme SVG): composantes blanches de la taille d'une lettre (20-160 px de haut, pas plus larges que 1.8x leur
hauteur, assez pleines), regroupees en lignes de >= 3 lettres alignees (meme haut/bas a 25 % pres, ecart < 1.6 hauteur).
Les autoroutes blanches (longues, continues) ne passent pas le filtre. Sortie: rectangles des lignes de texte (agrandis
pour couvrir le halo), en coordonnees monde -> tools/threejs/_v16_labels.json (l'onglet 3D les efface de la carte drapee).
Usage: python3 tools/v16_labels.py
"""
import json, os, sys
import numpy as np
import cv2
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
RASTER = os.path.join(REPO, 'maps', 'yanis,16svg.png')
OUT = os.path.join(THIS, 'threejs', '_v16_labels.json')
X0 = 16991; Y0 = 11008
LEGEND_X = 6000                                  # planche de legende (x px < 6000): ignoree


def main():
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(RASTER); W, H = im.size
    letters = []
    STRIP, OV = 2000, 220
    for y in range(0, H, STRIP):
        a = np.asarray(im.crop((LEGEND_X, max(0, y - OV), W, min(H, y + STRIP + OV))).convert('RGB'))
        m = (a.min(2) > 232).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        for i in range(1, n):
            x, yy, w, h, ar = st[i]
            if not (20 <= h <= 160 and 3 <= w <= 1.8 * h and ar >= 0.12 * w * h): continue
            gy = max(0, y - OV) + yy
            if gy < y - 2 or gy >= y + STRIP: continue      # dedoublonnage des bandes
            letters.append((LEGEND_X + x, gy, w, h))
    letters.sort(key=lambda t: (round(t[1] / 8), t[0]))
    used = [False] * len(letters); rows = []
    for i, (x, y, w, h) in enumerate(letters):
        if used[i]: continue
        row = [i]; used[i] = True; rx1 = x + w
        for j in range(i + 1, min(len(letters), i + 4000)):
            if used[j]: continue
            x2, y2, w2, h2 = letters[j]
            if abs(y2 - y) > 0.25 * h or abs((y2 + h2) - (y + h)) > 0.25 * h: continue
            if x2 - rx1 > 1.6 * h or x2 < x: continue
            row.append(j); used[j] = True; rx1 = max(rx1, x2 + w2)
        if len(row) >= 3:
            xs = [letters[k][0] for k in row]; ys = [letters[k][1] for k in row]
            xe = [letters[k][0] + letters[k][2] for k in row]; ye = [letters[k][1] + letters[k][3] for k in row]
            hh = max(ye) - min(ys); pad = 0.45 * hh
            rows.append([min(xs) - pad, min(ys) - pad, max(xe) + pad, max(ye) + pad])
    # monde (x = px - 16991, y = 11008 - py)
    out = [[round(r[0] - X0, 1), round(Y0 - r[3], 1), round(r[2] - X0, 1), round(Y0 - r[1], 1)] for r in rows]
    json.dump(out, open(OUT, 'w'))
    print('%d lettres, %d lignes de texte -> %s' % (len(letters), len(out), OUT))
    big = sorted(out, key=lambda r: -(r[2] - r[0]))[:12]
    for r in big: print('  x %.0f..%.0f  y %.0f..%.0f' % (r[0], r[2], r[1], r[3]))


if __name__ == '__main__':
    main()
