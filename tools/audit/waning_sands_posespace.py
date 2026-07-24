#!/usr/bin/env python3
"""waning_sands_posespace.py — TOUTES les poses possibles de Waning Sands (A).

Ce qu'on sait de la cam (frame A, Trailer 1 [1815]): hfov ~58, z ~32,
pitch ~-4.3 — et le CONTENU: un horizon bas au-dessus de l'eau, aucune
grosse tour (la skyline visible culmine a ~1.5 deg). Inconnues: x, y, yaw.

Pour chaque position candidate (grille 100m autour de la ville dessinee
sur la map communautaire), on calcule l'ENSEMBLE des yaw admissibles:
  yaw ok si la fenetre [yaw-29, yaw+29] :
   1. ne contient aucun landmark solveĂŠ z>60 a proeminence >2 deg
      (sinon on verrait Vice City / une tour dans la frame)
   2. contient >=24 deg contigus de vue-sur-eau (eau des tiles, 150-1400m)
Rendu: eventail cyan = plage(s) de yaw admissible(s) a cette position.
Pas d'eventail = position impossible pour la frame A.
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

TILES_DIR = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,13')


def render_basemap(cx, cy, half_m, out_px):
    TS = 256
    ZX = ZY = 16384
    RANGES = {0: [[0, 0], [2, 2]], 1: [[0, 1], [4, 5]], 2: [[0, 2], [9, 11]],
              3: [[0, 4], [19, 23]], 4: [[0, 8], [38, 47]],
              5: [[0, 17], [77, 95]], 6: [[0, 34], [155, 190]]}
    z = 0
    while z < 6 and (2.0 * half_m) / (32.0 / (2 ** z)) < out_px:
        z += 1
    mppx = 32.0 / (2 ** z)
    cpx = (ZX + cx) / mppx
    cpy = (ZY - cy) / mppx
    hw = half_m / mppx
    left, top = cpx - hw, cpy - hw
    tx_min, tx_max = int(left // TS), int((cpx + hw - 1) // TS)
    ty_min, ty_max = int(top // TS), int((cpy + hw - 1) // TS)
    [[bx0, by0], [bx1, by1]] = RANGES[z]
    comp = Image.new('RGB', ((tx_max - tx_min + 1) * TS, (ty_max - ty_min + 1) * TS), (10, 10, 12))
    for ty in range(ty_min, ty_max + 1):
        for tx in range(tx_min, tx_max + 1):
            if bx0 <= tx <= bx1 and by0 <= ty <= by1:
                tp = os.path.join(TILES_DIR, str(z), f'{z},{ty},{tx}.jpg')
                if os.path.exists(tp):
                    try:
                        comp.paste(Image.open(tp).convert('RGB'),
                                   ((tx - tx_min) * TS, (ty - ty_min) * TS))
                    except Exception:
                        pass
    cx0 = int(round(left - tx_min * TS))
    cy0 = int(round(top - ty_min * TS))
    side = int(round(2 * hw))
    return comp.crop((cx0, cy0, cx0 + side, cy0 + side)).resize((out_px, out_px), Image.BILINEAR)


Z_CAM = 32.0
PROM_DEG = 2.0
HFOV = 58.0
XMIN, XMAX, YMIN, YMAX = -2200, 1400, 2600, 5400
CELL = 100
AZ_STEP = 3
N_AZ = 360 // AZ_STEP
WIN = int(HFOV // AZ_STEP)
NEED_WATER = int(24 // AZ_STEP)

lms = json.load(open('gtamapdata/landmarks.json'))
talls = np.array([e['xyz'] for e in lms.values()
                  if isinstance(e, dict) and e.get('xyz') and e['xyz'][2] > 60])

# masque d'eau (6 m/px) sur une region elargie (les rayons sortent du cadre)
MPP = 6.0
PAD = 1600
cxw0, cyw0 = (XMIN + XMAX) / 2.0, (YMIN + YMAX) / 2.0
half0 = max(XMAX - XMIN, YMAX - YMIN) / 2.0 + PAD
wpx = int(2 * half0 / MPP)
wmap = np.asarray(render_basemap(cxw0, cyw0, half0, wpx), dtype=np.int16)
rC, gC, bC = wmap[:, :, 0], wmap[:, :, 1], wmap[:, :, 2]
WATER = (bC > rC + 18) & (bC > 80)
print(f'eau: {WATER.mean()*100:.0f}% de la region etendue')

DS = np.linspace(150, 1400, 14)


def water_ok(cx, cy, az_deg):
    rad = math.radians(az_deg)
    px_ = cx - np.sin(rad) * DS
    py_ = cy + np.cos(rad) * DS
    ix_ = ((px_ - (cxw0 - half0)) / MPP).astype(int)
    iy_ = (((cyw0 + half0) - py_) / MPP).astype(int)
    ok = (ix_ >= 0) & (ix_ < WATER.shape[1]) & (iy_ >= 0) & (iy_ < WATER.shape[0])
    if not ok.any():
        return False
    return float(WATER[iy_[ok], ix_[ok]].mean()) > 0.5


# rendu
S = 0.5
W, H = int((XMAX - XMIN) * S), int((YMAX - YMIN) * S)
side_px = int(2 * (max(XMAX - XMIN, YMAX - YMIN) / 2.0) * S)
base = render_basemap((XMIN + XMAX) / 2, (YMIN + YMAX) / 2,
                      max(XMAX - XMIN, YMAX - YMIN) / 2.0, side_px)
ox = int((max(XMAX - XMIN, YMAX - YMIN) / 2.0 - ((XMIN + XMAX) / 2 - XMIN)) * S)
oy = int((max(XMAX - XMIN, YMAX - YMIN) / 2.0 - (YMAX - (YMIN + YMAX) / 2)) * S)
img = base.crop((ox, oy, ox + W, oy + H)).convert('RGB')
img = Image.eval(img, lambda v: int(v * 0.72))
ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
do = ImageDraw.Draw(ov)


def P(x, y):
    return ((x - XMIN) * S, (YMAX - y) * S)


n_pos = 0
for cy in range(YMIN + CELL // 2, YMAX, CELL):
    for cx in range(XMIN + CELL // 2, XMAX, CELL):
        dx = talls[:, 0] - cx
        dy = talls[:, 1] - cy
        dist = np.hypot(dx, dy)
        elev = np.degrees(np.arctan2(talls[:, 2] - Z_CAM, np.maximum(dist, 1.0)))
        prom = elev > PROM_DEG
        blocked = np.zeros(N_AZ, bool)
        if prom.any():
            for a in (np.degrees(np.arctan2(-dx[prom], dy[prom])) % 360.0):
                i0 = int(a // AZ_STEP)
                blocked[(i0 - 1) % N_AZ] = blocked[i0 % N_AZ] = blocked[(i0 + 1) % N_AZ] = True
        wat = np.array([water_ok(cx, cy, i * AZ_STEP) for i in range(N_AZ)])
        feas = np.zeros(N_AZ, bool)          # yaw admissible (centre de fenetre)
        for c in range(N_AZ):
            idx = np.arange(c - WIN // 2, c + WIN // 2 + 1) % N_AZ
            if blocked[idx].any():
                continue
            run = best = 0
            for j in idx:
                run = run + 1 if wat[j] else 0
                best = max(best, run)
            if best >= NEED_WATER:
                feas[c] = True
        if not feas.any():
            continue
        n_pos += 1
        # eventails: intervalles contigus de yaw admissibles
        x0, y0 = P(cx, cy)
        Rf = 46
        f2 = np.r_[feas, feas]
        s = 0
        while s < N_AZ:
            if f2[s]:
                e = s
                while f2[e + 1] and e - s < N_AZ:
                    e += 1
                a0 = s * AZ_STEP
                a1 = (e + 1) * AZ_STEP
                # PIL: angles horaires depuis 3h; monde: az CCW depuis N (90=W)
                start = (a1 * -1) + 270 - 180  # conversion az->angle image
                end = (a0 * -1) + 270 - 180
                start2 = 270 - a1 - 90
                end2 = 270 - a0 - 90
                do.pieslice([x0 - Rf, y0 - Rf, x0 + Rf, y0 + Rf],
                            start=(-a1 - 90) % 360, end=(-a0 - 90) % 360,
                            fill=(34, 211, 238, 60), outline=(34, 211, 238, 140))
                s = e + 1
            else:
                s += 1
        do.ellipse([x0 - 2.5, y0 - 2.5, x0 + 2.5, y0 + 2.5], fill=(232, 121, 249, 220))

print(f'{n_pos} positions avec au moins un yaw admissible')
img = Image.alpha_composite(img.convert('RGBA'), ov)
dr = ImageDraw.Draw(img)

gx, gy = P(-1000, 4000)
dr.line([gx - 9, gy - 9, gx + 9, gy + 9], fill='#facc15', width=3)
dr.line([gx - 9, gy + 9, gx + 9, gy - 9], fill='#facc15', width=3)

try:
    F = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s)
    FB = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s, index=1)
    f_h, f_xs = FB(34), F(19)
except Exception:
    f_h = f_xs = ImageFont.load_default()
dr.text((22, 16), 'WANING SANDS (A) - ALL FEASIBLE POSES', fill='#e2e8f0', font=f_h,
        stroke_width=4, stroke_fill=(9, 13, 20))
dr.text((22, 60), 'cyan fan = yaw directions where a 58deg frame holds: no solved tower >2deg in view (no Vice City),',
        fill='#c3d2e6', font=f_xs, stroke_width=3, stroke_fill=(9, 13, 20))
dr.text((22, 86), 'and 24+ deg of open water 150-1400m ahead. no fan = frame A impossible there. yellow X = old placeholder',
        fill='#c3d2e6', font=f_xs, stroke_width=3, stroke_fill=(9, 13, 20))

out = os.path.join(REPO, 'tools', 'generated', 'waning_sands_posespace.png')
img.convert('RGB').save(out)
print('->', out)
