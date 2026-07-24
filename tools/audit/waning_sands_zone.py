#!/usr/bin/env python3
"""waning_sands_zone.py — LA zone possible pour Waning Sands (A). [WS-ZONE-V1]

Une position (x, y) est DANS la zone si, avec les params connus de la cam
(hfov 58, z ~32, pitch -4.3), il existe au moins un yaw tel que:
  1. la fenetre de 58 deg ne contient aucun landmark solve z>60 a
     proeminence >2 deg (la frame ne montre aucune grosse tour — pas de VC);
  2. la meme fenetre contient >=24 deg contigus de vue-sur-eau ouverte a
     150-1400m (la frame regarde au-dessus d'une baie);
  3. la cellule est sur TERRE (masque eau des tiles);
  4. aucune cam de confiance (tiers anchor/high/medium) ne regarde cette
     cellule a <3km (sinon Waning Sands serait dans une frame connue).
Rendu: une seule region verte translucide sur la map communautaire.
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
CELL = 80
AZ_STEP = 3
N_AZ = 360 // AZ_STEP
WIN = int(HFOV // AZ_STEP)
NEED_WATER = int(24 // AZ_STEP)
SEE_RANGE = 3000.0

lms = json.load(open('gtamapdata/landmarks.json'))
talls = np.array([e['xyz'] for e in lms.values()
                  if isinstance(e, dict) and e.get('xyz') and e['xyz'][2] > 60])

MPP = 6.0
PAD = 1600
cxw0, cyw0 = (XMIN + XMAX) / 2.0, (YMIN + YMAX) / 2.0
half0 = max(XMAX - XMIN, YMAX - YMIN) / 2.0 + PAD
wpx = int(2 * half0 / MPP)
wmap = np.asarray(render_basemap(cxw0, cyw0, half0, wpx), dtype=np.int16)
WATER = (wmap[:, :, 2] > wmap[:, :, 0] + 18) & (wmap[:, :, 2] > 80)

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


def on_land(cx, cy):
    ix_ = int((cx - (cxw0 - half0)) / MPP)
    iy_ = int(((cyw0 + half0) - cy) / MPP)
    if not (0 <= ix_ < WATER.shape[1] and 0 <= iy_ < WATER.shape[0]):
        return False
    r = int(40 / MPP)
    patch = WATER[max(0, iy_ - r):iy_ + r + 1, max(0, ix_ - r):ix_ + r + 1]
    return patch.size > 0 and patch.mean() < 0.3


# cams de confiance (couche invisibilite mutuelle)
tiers = json.load(open(os.path.join(REPO, 'tools', 'generated', 'confidence_tiers.json')))
tj = tiers.get('cameras', {})
cams_j = json.load(open('gtamapdata/cameras.json'))
trusted = []
for cn, ce in cams_j.items():
    if 'Waning Sands' in cn or 'AI World' in cn:
        continue
    t = tj.get(cn)
    t = t.get('tier') if isinstance(t, dict) else t
    if t in ('anchor', 'high', 'medium') and ce.get('xyz') and ce.get('ypr') and ce.get('fov') and ce['fov'][0]:
        trusted.append((ce['xyz'][0], ce['xyz'][1], ce['ypr'][0], ce['fov'][0]))


def seen_by_solved(cx, cy):
    for tx, ty, tyaw, thf in trusted:
        dx, dy = cx - tx, cy - ty
        d = math.hypot(dx, dy)
        if not (60.0 < d < SEE_RANGE):
            continue
        az = math.degrees(math.atan2(-dx, dy)) % 360.0
        if abs((az - tyaw + 180.0) % 360.0 - 180.0) < thf / 2.0 - 2.0:
            return True
    return False


xs = np.arange(XMIN, XMAX, CELL)
ys = np.arange(YMIN, YMAX, CELL)
feas = np.zeros((len(ys), len(xs)), bool)
for iy, cy0 in enumerate(ys):
    for ix, cx0 in enumerate(xs):
        cx, cy = cx0 + CELL / 2, cy0 + CELL / 2
        if not on_land(cx, cy) or seen_by_solved(cx, cy):
            continue
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
        wat = None
        q2 = np.r_[~blocked, ~blocked[:WIN]]
        run = 0
        found = False
        for s in range(N_AZ + WIN):
            run = run + 1 if q2[s] else 0
            if run >= WIN:
                if wat is None:
                    wat = np.array([water_ok(cx, cy, i * AZ_STEP) for i in range(N_AZ)])
                w2 = np.r_[wat, wat[:WIN]]
                seg = w2[s - WIN + 1:s + 1]
                rr = 0
                for v in seg:
                    rr = rr + 1 if v else 0
                    if rr >= NEED_WATER:
                        found = True
                        break
                if found:
                    break
        feas[iy, ix] = found

print(f'zone possible: {feas.sum()} cellules de {CELL}m ({feas.sum() * CELL * CELL / 1e6:.2f} km2)')

# rendu: map claire + region verte
S = 0.5
W, H = int((XMAX - XMIN) * S), int((YMAX - YMIN) * S)
side_px = int(2 * (max(XMAX - XMIN, YMAX - YMIN) / 2.0) * S)
base = render_basemap((XMIN + XMAX) / 2, (YMIN + YMAX) / 2,
                      max(XMAX - XMIN, YMAX - YMIN) / 2.0, side_px)
ox = int((max(XMAX - XMIN, YMAX - YMIN) / 2.0 - ((XMIN + XMAX) / 2 - XMIN)) * S)
oy = int((max(XMAX - XMIN, YMAX - YMIN) / 2.0 - (YMAX - (YMIN + YMAX) / 2)) * S)
img = base.crop((ox, oy, ox + W, oy + H)).convert('RGB')
img = Image.eval(img, lambda v: int(v * 0.85))
ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
do = ImageDraw.Draw(ov)


def P(x, y):
    return ((x - XMIN) * S, (YMAX - y) * S)


for iy, cy0 in enumerate(ys):
    for ix, cx0 in enumerate(xs):
        if not feas[iy, ix]:
            continue
        x0, y0 = P(cx0, cy0 + CELL)
        x1, y1 = P(cx0 + CELL, cy0)
        do.rectangle([x0, y0, x1, y1], fill=(34, 197, 94, 105))
# contour
for iy in range(len(ys)):
    for ix in range(len(xs)):
        if not feas[iy, ix]:
            continue
        cx0, cy0 = xs[ix], ys[iy]
        for dy_, dx_, seg in ((1, 0, 'top'), (-1, 0, 'bot'), (0, 1, 'right'), (0, -1, 'left')):
            jy, jx = iy + dy_, ix + dx_
            edge = not (0 <= jy < len(ys) and 0 <= jx < len(xs) and feas[jy, jx])
            if not edge:
                continue
            x0, y0 = P(cx0, cy0 + CELL)
            x1, y1 = P(cx0 + CELL, cy0)
            if seg == 'top':
                do.line([x0, y0, x1, y0], fill=(22, 163, 74, 255), width=3)
            elif seg == 'bot':
                do.line([x0, y1, x1, y1], fill=(22, 163, 74, 255), width=3)
            elif seg == 'right':
                do.line([x1, y0, x1, y1], fill=(22, 163, 74, 255), width=3)
            else:
                do.line([x0, y0, x0, y1], fill=(22, 163, 74, 255), width=3)

img = Image.alpha_composite(img.convert('RGBA'), ov)
dr = ImageDraw.Draw(img)
try:
    FB = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s, index=1)
    F = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s)
    f_h, f_xs = FB(34), F(19)
except Exception:
    f_h = f_xs = ImageFont.load_default()
dr.text((22, 16), 'WANING SANDS (A) - POSSIBLE ZONE', fill='#0f172a', font=f_h,
        stroke_width=4, stroke_fill='#e2e8f0')
dr.text((22, 60), 'green = every constraint fits: 58deg window with no known tower, open water ahead,',
        fill='#0f172a', font=f_xs, stroke_width=3, stroke_fill='#e2e8f0')
dr.text((22, 86), 'on land, and not inside any solved camera view (<3km)',
        fill='#0f172a', font=f_xs, stroke_width=3, stroke_fill='#e2e8f0')

out = os.path.join(REPO, 'tools', 'generated', 'waning_sands_zone.png')
img.convert('RGB').save(out)
print('->', out)
