#!/usr/bin/env python3
"""lake_shoreline_map.py — carte du contour du lac Leonida (LAKE-V1).

Polyline A->Z des points de rive (ray x plan d'eau z=5), moustaches
d'incertitude LE LONG DU RAYON (c'est la que le datum fait glisser les
points), cams du solve, contexte (silo, factory, Main St datum suspect).
-> tools/generated/ambrosia_bounty/lake_shoreline_map.png
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
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import common

lms = json.load(open('gtamapdata/landmarks.json'))
cams = json.load(open('gtamapdata/cameras.json'))

LETTERS = [chr(ord('A') + i) for i in range(26)]
shore = []
for L in LETTERS:
    e = lms.get(f'Lake Leonida ({L})')
    if e and e.get('xyz') and 'dup' not in (e.get('note') or ''):
        shore.append((L, np.asarray(e['xyz']), e.get('error_m', 0)))

pano = np.asarray(cams['Ambrosia 02 (Panorama)']['xyz'])

XMIN, XMAX = -3100, -2000
YMIN, YMAX = 3700, 5600
S = 1.5
W, H = int((XMAX - XMIN) * S), int((YMAX - YMIN) * S)
BG = (9, 13, 20)
img = Image.new('RGB', (W, H), BG)
dr = ImageDraw.Draw(img)


def P(x, y):
    return ((x - XMIN) * S, (YMAX - y) * S)


try:
    F = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s)
    FB = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s, index=1)
    f_h, f_m, f_s, f_xs = FB(34), F(26), F(22), F(18)
except Exception:
    f_h = f_m = f_s = f_xs = ImageFont.load_default()

for gx in range(XMIN, XMAX + 1, 250):
    dr.line([P(gx, YMIN), P(gx, YMAX)], fill=(24, 32, 44), width=1)
for gy in range(YMIN, YMAX + 1, 250):
    dr.line([P(XMIN, gy), P(XMAX, gy)], fill=(24, 32, 44), width=1)

ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
do = ImageDraw.Draw(ov)
glow = Image.new('RGBA', img.size, (0, 0, 0, 0))
dg = ImageDraw.Draw(glow)

# eau: bande cote est de la polyline (le lac est entre la rive et l'est)
pts = [P(p[0], p[1]) for _, p, _ in shore]
water = pts + [P(shore[-1][1][0] + 320, shore[-1][1][1] - 60),
               P(shore[0][1][0] + 460, shore[0][1][1] + 60)]
do.polygon(water, fill=(45, 110, 190, 42))

# moustaches d'incertitude le long du rayon cam->point
for L, p, err in shore:
    v = p[:2] - pano[:2]
    v = v / np.linalg.norm(v)
    a = P(*(p[:2] - v * err))
    b = P(*(p[:2] + v * err))
    dr.line([a, b], fill='#26506e', width=3)

# polyline de rive
dg.line(pts, fill=(90, 190, 255, 210), width=7)
glow = glow.filter(ImageFilter.GaussianBlur(6))
img = Image.alpha_composite(img.convert('RGBA'), ov)
img = Image.alpha_composite(img, glow)
dr = ImageDraw.Draw(img)
dr.line(pts, fill='#7dd3fc', width=3)
for L, p, err in shore:
    x, y = P(p[0], p[1])
    dr.ellipse([x - 4, y - 4, x + 4, y + 4], fill='#bae6fd')
    if L in ('A', 'E', 'J', 'O', 'S', 'V'):
        dr.text((x + 8, y - 26), L, fill='#7dd3fc', font=f_s)

# cams
for cn, col in [('Ambrosia 02 (Panorama)', '#fb923c'), ('Ambrosia 01 (Bikers)', '#fbbf24'),
                ('Ambrosia Postcard (X)', '#a78bfa')]:
    c = cams[cn]['xyz']
    if not (XMIN < c[0] < XMAX and YMIN < c[1] < YMAX):
        continue
    x, y = P(c[0], c[1])
    dr.ellipse([x - 7, y - 7, x + 7, y + 7], fill=col)
    dr.text((x + 12, y - 12), cn.replace('Ambrosia ', ''), fill=col, font=f_s,
            stroke_width=3, stroke_fill=BG)

# contexte
CTX = [('1500 Sonora Ave (Silo) (B)', 'silo'), ('US Sugar Mill (Factory)', 'factory')]
for lm, lab in CTX:
    e = lms.get(lm)
    if not e or not e.get('xyz'):
        continue
    x, y = P(e['xyz'][0], e['xyz'][1])
    if not (0 < x < W and 0 < y < H):
        continue
    dr.rectangle([x - 5, y - 5, x + 5, y + 5], outline='#94a3b8', width=2)
    dr.text((x + 10, y - 10), lab, fill='#94a3b8', font=f_xs)
# Main St datum suspect (z~10, vieux)
for L in 'ABCD':
    e = lms.get(f'Ambrosia Main St ({L})')
    if e and e.get('xyz'):
        x, y = P(e['xyz'][0], e['xyz'][1])
        dr.line([x - 5, y - 5, x + 5, y + 5], fill='#64748b', width=2)
        dr.line([x - 5, y + 5, x + 5, y - 5], fill='#64748b', width=2)
dr.text(P(-2990, 3920)[0:2], 'Main St (old z=10 datum, to re-derive)',
        fill='#64748b', font=f_xs)

dr.text((28, 20), 'LAKE LEONIDA — west shoreline from S2/57 panorama', fill='#e2e8f0',
        font=f_h, stroke_width=4, stroke_fill=BG)
dr.text((28, 64), 'ray x water plane z=14.486 (rlx final datum, bounty H) - whiskers = +-0.5 m datum slide along the ray',
        fill='#94a3b8', font=f_xs, stroke_width=3, stroke_fill=BG)

sx, sy = W - 420, H - 46
dr.line([sx, sy, sx + 250 * S, sy], fill='#c3d2e6', width=4)
dr.line([sx, sy - 8, sx, sy + 8], fill='#c3d2e6', width=3)
dr.line([sx + 250 * S, sy - 8, sx + 250 * S, sy + 8], fill='#c3d2e6', width=3)
dr.text((sx + 125 * S - 34, sy - 38), '250 m', fill='#c3d2e6', font=f_s)
nx, ny = W - 60, H - 140
dr.line([nx, ny, nx, ny - 50], fill='#c3d2e6', width=4)
dr.polygon([nx - 8, ny - 45, nx + 8, ny - 45, nx, ny - 70], fill='#c3d2e6')
dr.text((nx - 8, ny + 6), 'N', fill='#c3d2e6', font=f_m)

out = os.path.join(REPO, 'tools', 'generated', 'ambrosia_bounty', 'lake_shoreline_map.png')
img.convert('RGB').save(out)
print('->', out)
