#!/usr/bin/env python3
"""waning_sands_notmap.py — carte de ou Waning Sands N'EST PAS. [NOTMAP-V1]

Les 3 frames Waning Sands (Trailer 1) n'ont AUCUN landmark a xyz: la zone
flotte. Mais l'ABSENCE de contenu est une contrainte: la frame A couvre
hfov 58 deg avec un horizon bas et propre (sa seule skyline est petite et
lointaine, <~1.5 deg de proeminence). Donc en tout candidat (x, y) ou
AUCUNE fenetre azimutale de 58 deg n'echappe aux grosses tours connues
(proeminence > seuil), la frame A n'a pas pu etre prise -> EXCLU.
C'est l'argument 'sinon on verrait North Vice Beach', industrialise avec
les 220 landmarks z>60 deja triangules.

Couches:
  ROUGE  exclu dur: pas de fenetre calme de 58 deg (frame A seule)
  ORANGE exclu doux: pas de fenetre calme de 130 deg (A+B+C meme spot,
         yaws devines 270/330/345 -> ~130 deg de couverture combinee)
  sombre possible (geometriquement; marais/eau non filtres)

Seuil de proeminence: 2.0 deg au-dessus de l'horizon vu de z_cam=32
(la skyline OBSERVEE dans A culmine a ~1.5 deg — tout ce qui depasserait
2 deg contredirait la frame).
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
from PIL import Image, ImageDraw, ImageFont

Z_CAM = 32.0
PROM_DEG = 2.0          # proeminence au-dela de laquelle la frame l'aurait montree
HARD_WIN = 58.0         # hfov frame A
SOFT_WIN = 130.0        # couverture A+B+C si meme spot
XMIN, XMAX, YMIN, YMAX = -9000, 3000, -2500, 9000
CELL = 100

lms = json.load(open('gtamapdata/landmarks.json'))
talls = np.array([e['xyz'] for e in lms.values()
                  if isinstance(e, dict) and e.get('xyz') and e['xyz'][2] > 60])
print(f'{len(talls)} tours (z>60) utilisees')

xs = np.arange(XMIN, XMAX, CELL)
ys = np.arange(YMIN, YMAX, CELL)
hard = np.zeros((len(ys), len(xs)), bool)
soft = np.zeros((len(ys), len(xs)), bool)

for iy, cy in enumerate(ys):
    for ix, cx in enumerate(xs):
        dx = talls[:, 0] - cx
        dy = talls[:, 1] - cy
        dist = np.hypot(dx, dy)
        elev = np.degrees(np.arctan2(talls[:, 2] - Z_CAM, np.maximum(dist, 1.0)))
        prom = elev > PROM_DEG
        if not prom.any():
            continue
        az = np.degrees(np.arctan2(-dx[prom], dy[prom])) % 360.0
        az = np.sort(az)
        gaps = np.diff(az, append=az[0] + 360.0)
        widest = float(gaps.max())
        if widest < HARD_WIN:
            hard[iy, ix] = True
        if widest < SOFT_WIN:
            soft[iy, ix] = True

print(f'exclu dur (58): {hard.sum()} cellules | exclu doux (130): {soft.sum()}')

S = 0.14
W, H = int((XMAX - XMIN) * S), int((YMAX - YMIN) * S)
img = Image.new('RGB', (W, H), (9, 13, 20))
dr = ImageDraw.Draw(img)


def P(x, y):
    return ((x - XMIN) * S, (YMAX - y) * S)


ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
do = ImageDraw.Draw(ov)
for iy, cy in enumerate(ys):
    for ix, cx in enumerate(xs):
        if not soft[iy, ix]:
            continue
        x0, y0 = P(cx, cy + CELL)
        x1, y1 = P(cx + CELL, cy)
        col = (239, 68, 68, 150) if hard[iy, ix] else (249, 140, 55, 90)
        do.rectangle([x0, y0, x1, y1], fill=col)
img = Image.alpha_composite(img.convert('RGBA'), ov)
dr = ImageDraw.Draw(img)

for t in talls:
    x, y = P(t[0], t[1])
    if 0 <= x < W and 0 <= y < H:
        dr.ellipse([x - 2, y - 2, x + 2, y + 2], fill='#93c5fd')

gx, gy = P(-1000, 4000)
dr.line([gx - 8, gy - 8, gx + 8, gy + 8], fill='#facc15', width=3)
dr.line([gx - 8, gy + 8, gx + 8, gy - 8], fill='#facc15', width=3)

try:
    F = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s)
    FB = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s, index=1)
    f_h, f_s, f_xs = FB(30), F(20), F(17)
except Exception:
    f_h = f_s = f_xs = ImageFont.load_default()

dr.text((22, 16), 'WHERE WANING SANDS IS NOT', fill='#e2e8f0', font=f_h,
        stroke_width=4, stroke_fill=(9, 13, 20))
dr.text((22, 56), 'negative-skyline exclusion: frame A spans 58 deg with a clean low horizon (max ~1.5 deg skyline)',
        fill='#94a3b8', font=f_xs, stroke_width=3, stroke_fill=(9, 13, 20))
dr.text((22, 82), 'RED: no quiet 58 deg window exists (frame A impossible) - ORANGE: no quiet 130 deg (A+B+C same spot)',
        fill='#94a3b8', font=f_xs, stroke_width=3, stroke_fill=(9, 13, 20))
dr.text((22, 108), 'dots: the 220 solved towers (z>60) doing the excluding - yellow X: current placeholder guess',
        fill='#64748b', font=f_xs, stroke_width=3, stroke_fill=(9, 13, 20))

sx, sy = W - 260, H - 36
dr.line([sx, sy, sx + 1000 * S, sy], fill='#c3d2e6', width=3)
dr.text((sx + 30, sy - 26), '1 km', fill='#c3d2e6', font=f_xs)
nx, ny = W - 46, H - 120
dr.line([nx, ny, nx, ny - 40], fill='#c3d2e6', width=3)
dr.polygon([nx - 6, ny - 36, nx + 6, ny - 36, nx, ny - 55], fill='#c3d2e6')
dr.text((nx - 6, ny + 5), 'N', fill='#c3d2e6', font=f_xs)

out = os.path.join(REPO, 'tools', 'generated', 'waning_sands_notmap.png')
img.convert('RGB').save(out)
print('->', out)
