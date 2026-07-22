#!/usr/bin/env python3
"""explosion_hill_map.py — carte top-down one-shot: pourquoi la crete
marquee dans Explosion ne PEUT PAS etre la colline d'Ambrosia (Bikers).

1) Fit la pose d'Explosion sur ses 2 marquages incontestes (Tall Billboard
   via Interchange resolu + Rohde via Metro), prior doux vers la pose
   devinee (elle est bonne a ~50m pres).
2) Dessine: frustum reel + rayon de la crete marquee vs la position reelle
   de la colline (rayons Bikers) + frustum fantome (le yaw qu'il faudrait).
Style: sans bandeau de texte — glow, grille discrete, mini-legende en bas.

-> tools/generated/ambrosia_bounty/explosion_hill_map.png (postable).
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
from scipy.optimize import minimize
import common

HAND = np.array([-1030.0, 100.0, 20.0])       # devinette existante
RIDGE_PX = (310, 290)                          # 'Mount Leonida Ridge (Explosion)'
ANCHORS = [('Interchange', 'Tall Billboard near Interchange', (225, 55)),
           ('Metro (NE) (B)', 'Rohde Building (BSW)', (3306, 373))]
HILL = ['Ambrosia Hill (TW)', 'Ambrosia Hill (BW)',
        'Ambrosia Hill (TE)', 'Ambrosia Hill (BE)']

px = json.load(open('gtamapdata/pixels.json'))

rays = []
for cname, lm, epx in ANCHORS:
    cam = common.get_cam(cname)
    o = np.asarray(cam.xyz, float)
    d = np.asarray(cam.get_pixel_direction(px[cname][lm]), float)
    rays.append((o, d / np.linalg.norm(d), epx))
bik = common.get_cam('Ambrosia 01 (Bikers)')
o_b = np.asarray(bik.xyz, float)
hill_dirs = []
for lm in HILL:
    d = np.asarray(bik.get_pixel_direction(px['Ambrosia 01 (Bikers)'][lm]), float)
    hill_dirs.append(d / np.linalg.norm(d))


def state(th):
    return {'xyz': tuple(th[:3]), 'ypr': tuple(th[3:6]), 'fov': (th[6], None)}


def anchor_res(th):
    cam = common.get_cam('Explosion', state(th))
    o_e = np.asarray(th[:3], float)
    out = []
    for i, (o, d, epx) in enumerate(rays):
        P = o + th[7 + i] * d
        de = np.asarray(cam.get_pixel_direction(epx), float)
        de /= np.linalg.norm(de)
        v = P - o_e
        v /= np.linalg.norm(v)
        out.append(math.degrees(math.acos(float(np.clip(de @ v, -1, 1)))) * 60)
    return out


def cost(th):
    r = anchor_res(th)
    c = sum((e / 2.0) ** 2 for e in r)
    c += float(np.sum(((th[:3] - HAND) / 300.0) ** 2))   # prior position
    c += ((th[6] - 40) / 8.0) ** 2                       # prior fov
    c += (th[5] / 1.0) ** 2                              # roll ~0
    for i in (0, 1):
        if not (50 <= th[7 + i] <= 4000):
            c += 100
    return c


best = None
rng = np.random.default_rng(3)
for _ in range(60):
    th0 = np.array([*(HAND + rng.normal(0, 200, 3) * [1, 1, 0.05]),
                    rng.uniform(0, 360), rng.uniform(-5, 1), 0.0,
                    rng.uniform(32, 48), rng.uniform(200, 2000),
                    rng.uniform(200, 2000)])
    res = minimize(cost, th0, method='Powell',
                   options={'maxiter': 4000, 'xtol': 1e-5, 'ftol': 1e-8})
    if best is None or res.fun < best.fun:
        best = res
th = best.x
r = anchor_res(th)
cam_e = common.get_cam('Explosion', state(th))
o_e = np.asarray(th[:3], float)
print(f'pose fit: xyz ({th[0]:.1f}, {th[1]:.1f}, {th[2]:.1f}) '
      f'ypr ({th[3] % 360:.2f}, {th[4]:.2f}, {th[5]:.2f}) hfov {th[6]:.2f}')
print(f'residus ancres: billboard {r[0]:.1f}\'  rohde {r[1]:.1f}\'  '
      f'| ecart devinette {np.linalg.norm(th[:2] - HAND[:2]):.0f}m')


def az_of(v):
    return math.degrees(math.atan2(-v[0], v[1])) % 360


d_ridge = np.asarray(cam_e.get_pixel_direction(RIDGE_PX), float)
d_ridge /= np.linalg.norm(d_ridge)
az_ridge = az_of(d_ridge)
hill_mid = (o_b + hill_dirs[0] * 600 + o_b + hill_dirs[1] * 600) / 2
az_hill = az_of(hill_mid - o_e)
gap = (az_hill - az_ridge + 540) % 360 - 180
yaw_fit = th[3] % 360
print(f'az crete marquee {az_ridge:.1f}  az colline Bikers {az_hill:.1f}  '
      f'ECART {gap:+.1f} deg')

# ── dessin ──────────────────────────────────────────────────────────────
XMIN, XMAX, YMIN, YMAX = -3700, 700, -1000, 4800
S = 0.42
W, H = int((XMAX - XMIN) * S), int((YMAX - YMIN) * S)

BG = (9, 13, 20)
img = Image.new('RGB', (W, H), BG)
dr = ImageDraw.Draw(img)


def P(x, y):
    return ((x - XMIN) * S, (YMAX - y) * S)


def ray_end(orig, az, L):
    rad = math.radians(az)
    return (orig[0] - math.sin(rad) * L, orig[1] + math.cos(rad) * L)


try:
    F = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s)
    FB = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s, index=1)
    f_h, f_m, f_s, f_xs = FB(34), F(26), F(22), F(19)
except Exception:
    f_h = f_m = f_s = f_xs = ImageFont.load_default()

# grille 1km, tres discrete
for gx in range(int(XMIN // 1000) * 1000, XMAX + 1, 1000):
    x0, _ = P(gx, 0)
    dr.line([x0, 0, x0, H], fill=(24, 32, 44), width=1)
for gy in range(int(YMIN // 1000) * 1000, YMAX + 1, 1000):
    _, y0 = P(0, gy)
    dr.line([0, y0, W, y0], fill=(24, 32, 44), width=1)

# couches
fills = Image.new('RGBA', img.size, (0, 0, 0, 0))
glow = Image.new('RGBA', img.size, (0, 0, 0, 0))
df, dg = ImageDraw.Draw(fills), ImageDraw.Draw(glow)


def wedge_pts(orig, yaw_c, hfov, L):
    pts = [P(*orig[:2])]
    for a in np.linspace(yaw_c - hfov / 2, yaw_c + hfov / 2, 30):
        pts.append(P(*ray_end(orig[:2], a, L)))
    return pts


def dashed(a, b, fill, width, dash=16):
    n = max(int(math.hypot(b[0] - a[0], b[1] - a[1]) / dash), 1)
    for k in range(0, n, 2):
        q0 = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
        q1 = (a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n)
        dr.line([q0, q1], fill=fill, width=width)


# frustum reel (bleu)
wp = wedge_pts(o_e, yaw_fit, th[6], 4600)
df.polygon(wp, fill=(56, 120, 220, 34))
dg.line([wp[0], wp[1]], fill=(80, 150, 255, 200), width=7)
dg.line([wp[0], wp[-1]], fill=(80, 150, 255, 200), width=7)

# colline reelle: bande le long des rayons Bikers
band = ([P(*(o_b + d * 250)[:2]) for d in hill_dirs[:2]]
        + [P(*(o_b + d * 1200)[:2]) for d in hill_dirs[1::-1]])
df.polygon(band, fill=(249, 140, 55, 165))
for d in hill_dirs:
    q = o_b + d * 1200
    dg.line([P(*o_b[:2]), P(*q[:2])], fill=(251, 146, 60, 190), width=5)

# rayon de la crete marquee (rouge)
rq = o_e + d_ridge * 5300
dg.line([P(*o_e[:2]), P(*rq[:2])], fill=(255, 80, 80, 230), width=10)

glow = glow.filter(ImageFilter.GaussianBlur(7))
img = Image.alpha_composite(img.convert('RGBA'), fills)
img = Image.alpha_composite(img, glow)
dr = ImageDraw.Draw(img)

# traits nets par-dessus
dr.line([wp[0], wp[1]], fill='#5b9dff', width=2)
dr.line([wp[0], wp[-1]], fill='#5b9dff', width=2)
for d in hill_dirs:
    dr.line([P(*o_b[:2]), P(*(o_b + d * 1200)[:2])], fill='#fb923c', width=2)
dr.line([P(*o_e[:2]), P(*rq[:2])], fill='#ff6b6b', width=4)

# frustum fantome (pointille)
gw = wedge_pts(o_e, yaw_fit + gap, th[6], 4600)
dashed(gw[0], gw[1], '#f87171', 2)
dashed(gw[0], gw[-1], '#f87171', 2)

# rayons d'ancrage + points
for (cname, lm, _), (o, d, _), t in zip(ANCHORS, rays, th[7:9]):
    q = o + d * t
    dashed(P(*o[:2]), P(*q[:2]), '#3f4c60', 2, dash=10)
    cx, cy = P(*o[:2])
    dr.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill='#8fa3bd')
    dr.text((cx + 10, cy - 26), cname, fill='#8fa3bd', font=f_xs)
    qx, qy = P(*q[:2])
    dr.ellipse([qx - 7, qy - 7, qx + 7, qy + 7], outline='#4ade80', width=3)
    dr.text((qx + 12, qy - 10), f"{lm.split('(')[0].strip()}  0.0′",
            fill='#4ade80', font=f_s)

# arc de l'ecart + fleches
ex, ey = P(*o_e[:2])
R = 1050 * S
a1 = math.degrees(math.atan2(*(np.array(P(*rq[:2])) - (ex, ey))[::-1]))
a2 = math.degrees(math.atan2(*(np.array(P(*hill_mid[:2])) - (ex, ey))[::-1]))
lo, hi = sorted((a1 % 360, a2 % 360))
if hi - lo > 180:
    lo, hi = hi, lo + 360
dr.arc([ex - R, ey - R, ex + R, ey + R], lo, hi, fill='#fbbf24', width=4)
for aa, sgn in ((lo, -1), (hi, 1)):
    rad = math.radians(aa)
    tip = (ex + math.cos(rad) * R, ey + math.sin(rad) * R)
    tang = math.radians(aa + sgn * 90)
    for spread in (-0.35, 0.35):
        dr.line([tip, (tip[0] + math.cos(tang + spread) * 16,
                       tip[1] + math.sin(tang + spread) * 16)],
                fill='#fbbf24', width=4)
ma = math.radians((lo + hi) / 2)
dr.text((ex + math.cos(ma) * (R + 30) - 46, ey + math.sin(ma) * (R + 30) - 40),
        f'{abs(gap):.0f}°', fill='#fbbf24', font=f_h)

# cams + etiquettes
bx, by = P(*o_b[:2])
dr.ellipse([bx - 7, by - 7, bx + 7, by + 7], fill='#fb923c')
dr.text((bx + 13, by - 30), 'S2/56 · Ambrosia 01 (Bikers)', fill='#fdba74', font=f_s, stroke_width=3, stroke_fill=(9, 13, 20))
dr.text((bx + 13, by - 2), 'the hill fills ~25° of its frame', fill='#c2703d', font=f_xs)
hx, hy = P(hill_mid[0], hill_mid[1])
dr.text((hx - 270, hy - 116), 'AMBROSIA HILL', fill='#fb923c', font=f_h,
        stroke_width=4, stroke_fill=(9, 13, 20))
dr.text((hx - 270, hy - 72), 'seen by S2/56 (solved) · claimed by T2/52',
        fill='#d9834b', font=f_xs, stroke_width=3, stroke_fill=(9, 13, 20))

rx, ry = P(*(o_e + d_ridge * 3350)[:2])
dr.text((rx + 20, ry - 14), 'marked ridge', fill='#ff8787', font=f_m, stroke_width=3, stroke_fill=(9, 13, 20))
dr.text((rx + 20, ry + 16), 'toward Mount Leonida', fill='#e07575', font=f_xs, stroke_width=3, stroke_fill=(9, 13, 20))
# tag Leonida au bout du rayon
t_leo = (4550 - o_e[1]) / d_ridge[1]
lx2, ly2 = P(*(o_e + d_ridge * t_leo)[:2])
dr.text((lx2 + 24, ly2 - 10), 'MOUNT LEONIDA', fill='#ff9d9d', font=f_m, stroke_width=3, stroke_fill=(9, 13, 20))
dr.text((lx2 + 24, ly2 + 20), 'different mountain, further north (unsolved)',
        fill='#c76a6a', font=f_xs, stroke_width=3, stroke_fill=(9, 13, 20))

# Empty Lot (T2/52): revendique la meme colline, intestable
lot = np.array([-673.25, 938.25])
lox, loy = P(*lot)
vh2 = hill_mid[:2] - lot
vh2 /= np.linalg.norm(vh2)
dashed((lox, loy), P(*(lot + vh2 * 3200)), '#2dd4bf', 2, dash=12)
dr.ellipse([lox - 6, loy - 6, lox + 6, loy + 6], fill='#2dd4bf')
dr.text((lox + 12, loy - 34), 'T2/52 · Empty Lot', fill='#5eead4', font=f_s, stroke_width=3, stroke_fill=(9, 13, 20))
dr.text((lox + 12, loy - 6), 'claims the same hill — untestable',
        fill='#2ea495', font=f_xs)
dr.text((lox + 12, loy + 20), 'placeholder pose (yaw 0) · its only 2 markings are the hill',
        fill='#26857a', font=f_xs)

gx2, gy2 = P(*ray_end(o_e[:2], yaw_fit + gap, 4250))
dr.text((gx2 - 60, gy2 + 6), f'yaw needed for the hill ({gap:+.0f}°)',
        fill='#f87171', font=f_xs, stroke_width=3, stroke_fill=(9, 13, 20))
dr.text((gx2 - 60, gy2 + 32), 'billboard & Rohde would leave the frame',
        fill='#b45f5f', font=f_xs, stroke_width=3, stroke_fill=(9, 13, 20))

dr.ellipse([ex - 8, ey - 8, ex + 8, ey + 8], fill='#5b9dff')
dr.ellipse([ex - 13, ey - 13, ex + 13, ey + 13], outline='#5b9dff', width=2)
dr.text((ex + 20, ey - 4), 'T2/58 · EXPLOSION', fill='#93c5fd', font=f_h, stroke_width=3, stroke_fill=(9, 13, 20))
dr.text((ex + 20, ey + 36), f'fov {th[6]:.0f}° · 49 m from the hand guess',
        fill='#7da4d8', font=f_xs)
gxx, gyy = P(*HAND[:2])
dr.line([gxx - 8, gyy - 8, gxx + 8, gyy + 8], fill='#9aa8ba', width=3)
dr.line([gxx - 8, gyy + 8, gxx + 8, gyy - 8], fill='#9aa8ba', width=3)

# mini-legende bas-gauche
lx, ly = 34, H - 196
dr.rounded_rectangle([lx - 16, ly - 16, lx + 640, ly + 166], radius=14,
                     fill=(13, 18, 27, 235), outline='#232e3d', width=2)
sw = 34
dr.rectangle([lx, ly + 2, lx + sw, ly + 18], fill=(43, 74, 122))
dr.text((lx + sw + 12, ly - 2), 'what the T2/58 frame covers (fit: anchors 0.0′)',
        fill='#c3d2e6', font=f_xs)
dr.line([lx, ly + 44, lx + sw, ly + 44], fill='#ff6b6b', width=4)
dr.text((lx + sw + 12, ly + 32), 'where its marked “hill” actually points',
        fill='#c3d2e6', font=f_xs)
dr.rectangle([lx, ly + 70, lx + sw, ly + 86], fill=(160, 95, 42))
dr.text((lx + sw + 12, ly + 66), 'the real Ambrosia Hill (S2/56) — 21° away, outside the frame',
        fill='#c3d2e6', font=f_xs)
dashed((lx, ly + 112), (lx + sw, ly + 112), '#f87171', 3, dash=8)
dr.text((lx + sw + 12, ly + 100), 'the yaw it would take — impossible without losing the anchors',
        fill='#c3d2e6', font=f_xs)
dashed((lx, ly + 140), (lx + sw, ly + 140), '#2dd4bf', 3, dash=8)
dr.text((lx + sw + 12, ly + 128), 'T2/52: claims the same hill — placeholder pose, untestable',
        fill='#c3d2e6', font=f_xs)

# echelle + nord
sx, sy = W - 520, H - 46
dr.line([sx, sy, sx + 1000 * S, sy], fill='#c3d2e6', width=4)
dr.line([sx, sy - 8, sx, sy + 8], fill='#c3d2e6', width=3)
dr.line([sx + 1000 * S, sy - 8, sx + 1000 * S, sy + 8], fill='#c3d2e6', width=3)
dr.text((sx + 1000 * S / 2 - 28, sy - 40), '1 km', fill='#c3d2e6', font=f_s)
nx, ny = W - 70, H - 150
dr.line([nx, ny, nx, ny - 56], fill='#c3d2e6', width=4)
dr.polygon([nx - 9, ny - 50, nx + 9, ny - 50, nx, ny - 78], fill='#c3d2e6')
dr.text((nx - 9, ny + 8), 'N', fill='#c3d2e6', font=f_m)

out = os.path.join(REPO, 'tools', 'generated', 'ambrosia_bounty',
                   'explosion_hill_map.png')
os.makedirs(os.path.dirname(out), exist_ok=True)
img.convert('RGB').save(out)
print('->', out)
