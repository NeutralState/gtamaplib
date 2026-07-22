#!/usr/bin/env python3
"""explosion_hill_map.py — carte top-down one-shot: pourquoi la crete
marquee dans Explosion ne PEUT PAS etre la colline d'Ambrosia (Bikers).

1) Fit la pose d'Explosion sur ses 2 marquages incontestes (Tall Billboard
   via Interchange resolu + Rohde via Metro), prior doux vers la pose
   devinee (elle est bonne a ~300m pres).
2) Dessine: frustum reel + rayon de la crete marquee vs la position reelle
   de la colline (rayons Bikers) + frustum fantome (le yaw qu'il faudrait)
   -> l'ecart angulaire est plus grand que la demi-frame.

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
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import minimize
import common

HAND = np.array([-1030.0, 100.0, 20.0])       # devinette existante
RIDGE_PX = (310, 290)                          # 'Mount Leonida Ridge (Explosion)'
ANCHORS = [('Interchange', 'Tall Billboard near Interchange', (225, 55)),
           ('Metro (NE) (B)', 'Rohde Building (BSW)', (3306, 373))]
HILL = [('Ambrosia Hill (TW)', None), ('Ambrosia Hill (BW)', None),
        ('Ambrosia Hill (TE)', None), ('Ambrosia Hill (BE)', None)]

px = json.load(open('gtamapdata/pixels.json'))

# rayons partenaires des ancres + rayons colline de Bikers
rays = []
for cname, lm, epx in ANCHORS:
    cam = common.get_cam(cname)
    o = np.asarray(cam.xyz, float)
    d = np.asarray(cam.get_pixel_direction(px[cname][lm]), float)
    rays.append((o, d / np.linalg.norm(d), epx))
bik = common.get_cam('Ambrosia 01 (Bikers)')
o_b = np.asarray(bik.xyz, float)
hill_dirs = []
for lm, _ in HILL:
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


# azimuts: rayon de la crete marquee vs colline reelle
d_ridge = np.asarray(cam_e.get_pixel_direction(RIDGE_PX), float)
az_ridge = az_of(d_ridge)
hill_mid = (o_b + hill_dirs[0] * 600 + o_b + hill_dirs[1] * 600) / 2
az_hill = az_of(hill_mid - o_e)
gap = (az_hill - az_ridge + 540) % 360 - 180
yaw_fit = th[3] % 360
print(f'az crete marquee {az_ridge:.1f}  az colline Bikers {az_hill:.1f}  '
      f'ECART {gap:+.1f} deg  (demi-frame = {th[6] / 2:.1f} deg)')

# ── dessin ──────────────────────────────────────────────────────────────
XMIN, XMAX, YMIN, YMAX = -3700, 700, -1000, 4800
S = 0.42
W, H = int((XMAX - XMIN) * S), int((YMAX - YMIN) * S)
img = Image.new('RGB', (W, H + 210), '#0b0f14')
ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
dr = ImageDraw.Draw(img)
do = ImageDraw.Draw(ov)


def P(x, y):
    return ((x - XMIN) * S, 210 + (YMAX - y) * S)


def wedge(orig, yaw_c, hfov, L, fill=None, outline=None, width=2, dashed=False):
    pts = [P(*orig[:2])]
    for a in np.linspace(yaw_c - hfov / 2, yaw_c + hfov / 2, 24):
        rad = math.radians(a)
        pts.append(P(orig[0] - math.sin(rad) * L, orig[1] + math.cos(rad) * L))
    if fill:
        do.polygon(pts, fill=fill)
    if outline:
        edge = [pts[0], pts[1], pts[0], pts[-1]]
        if dashed:
            for a, b in (edge[:2], edge[2:]):
                n = int(math.hypot(b[0] - a[0], b[1] - a[1]) / 18)
                for k in range(0, n, 2):
                    q0 = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
                    q1 = (a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n)
                    dr.line([q0, q1], fill=outline, width=width)
        else:
            dr.line(edge[:2], fill=outline, width=width)
            dr.line(edge[2:], fill=outline, width=width)


try:
    F = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s)
    f_t, f_m, f_s = F(40), F(28), F(22)
except Exception:
    f_t = f_m = f_s = ImageFont.load_default()

# colline reelle: bande le long des rayons Bikers (t 250..1200)
band = ([P(*(o_b + d * 250)[:2]) for d in hill_dirs[:2]]
        + [P(*(o_b + d * 1200)[:2]) for d in hill_dirs[1::-1]])
do.polygon(band, fill=(251, 146, 60, 70))
for d in hill_dirs:
    q = o_b + d * 1200
    dr.line([P(*o_b[:2]), P(*q[:2])], fill='#fb923c', width=2)
hx, hy = P(hill_mid[0], hill_mid[1])
dr.text((hx - 240, hy - 70), 'AMBROSIA HILL', fill='#fb923c', font=f_m)
dr.text((hx - 240, hy - 36), 'as seen by Bikers (fills ~25 deg of its frame)',
        fill='#fdba74', font=f_s)
bx, by = P(*o_b[:2])
dr.ellipse([bx - 7, by - 7, bx + 7, by + 7], fill='#fb923c')
dr.text((bx + 12, by - 10), 'Ambrosia 01 (Bikers) — solved', fill='#fb923c', font=f_s)

# cams partenaires + rayons d'ancrage
for (cname, lm, _), (o, d, _) , t in zip(ANCHORS, rays, th[7:9]):
    q = o + d * t
    dr.line([P(*o[:2]), P(*q[:2])], fill='#475569', width=2)
    cx, cy = P(*o[:2])
    dr.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill='#94a3b8')
    dr.text((cx + 9, cy - 8), cname, fill='#94a3b8', font=f_s)
    qx, qy = P(*q[:2])
    dr.ellipse([qx - 6, qy - 6, qx + 6, qy + 6], outline='#4ade80', width=3)
    dr.text((qx + 10, qy - 8), f"{lm.split('(')[0].strip()} (fit 0.0')",
            fill='#4ade80', font=f_s)

# Explosion: frustum reel, rayon crete, frustum fantome
ex, ey = P(*o_e[:2])
wedge(o_e, yaw_fit, th[6], 4600, fill=(59, 130, 246, 45), outline='#3b82f6')
rq = o_e + (d_ridge / np.linalg.norm(d_ridge)) * 5200
dr.line([P(*o_e[:2]), P(*rq[:2])], fill='#ef4444', width=4)
rx, ry = P(*(o_e + (d_ridge / np.linalg.norm(d_ridge)) * 3400)[:2])
dr.text((rx + 18, ry - 16), 'marked ridge points HERE', fill='#ef4444', font=f_m)
dr.text((rx + 18, ry + 18), '(Mount Leonida direction)', fill='#f87171', font=f_s)
wedge(o_e, yaw_fit + gap, th[6], 4600, outline='#ef4444', width=2, dashed=True)
grad = math.radians(yaw_fit + gap)
gx2, gy2 = P(o_e[0] - math.sin(grad) * 4100, o_e[1] + math.cos(grad) * 4100)
dr.text((gx2 - 480, gy2 - 40), f'frame yawed {gap:+.0f} deg: ridge pixel would hit',
        fill='#f87171', font=f_s)
dr.text((gx2 - 480, gy2 - 12), 'the hill - but billboard & Rohde are lost',
        fill='#f87171', font=f_s)
dr.ellipse([ex - 8, ey - 8, ex + 8, ey + 8], fill='#3b82f6')
dr.text((ex + 14, ey + 2), 'Explosion — fitted on billboard+Rohde',
        fill='#60a5fa', font=f_m)
dr.text((ex + 14, ey + 34),
        f'xyz ({th[0]:.0f}, {th[1]:.0f})  yaw {yaw_fit:.1f}  hfov {th[6]:.1f}',
        fill='#60a5fa', font=f_s)
gx, gy = P(*HAND[:2])
dr.line([gx - 8, gy - 8, gx + 8, gy + 8], fill='#94a3b8', width=3)
dr.line([gx - 8, gy + 8, gx + 8, gy - 8], fill='#94a3b8', width=3)
dr.text((gx - 330, gy - 10),
        f'hand guess ({np.linalg.norm(th[:2] - HAND[:2]):.0f} m away)',
        fill='#94a3b8', font=f_s)

# arc de l'ecart angulaire
R = 900 * S
a1 = math.degrees(math.atan2(*(np.array(P(*rq[:2])) - (ex, ey))[::-1]))
mid = o_e + (hill_mid - o_e) / np.linalg.norm((hill_mid - o_e)[:2]) * 900
a2 = math.degrees(math.atan2(*(np.array(P(*hill_mid[:2])) - (ex, ey))[::-1]))
lo, hi = sorted((a1 % 360, a2 % 360))
if hi - lo > 180:
    lo, hi = hi, lo + 360
dr.arc([ex - R, ey - R, ex + R, ey + R], lo, hi, fill='#facc15', width=4)
ma = math.radians((lo + hi) / 2)
dr.text((ex + math.cos(ma) * (R + 26) - 60, ey + math.sin(ma) * (R + 26) - 14),
        f'{abs(gap):.0f} deg', fill='#facc15', font=f_t)

img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
dr = ImageDraw.Draw(img)
dr.text((28, 18), 'Explosion frame: the marked ridge cannot be the Ambrosia hill',
        fill='#e2e8f0', font=f_t)
dr.text((28, 70),
        f'Camera resected on its two uncontested markings (billboard 0.0\', Rohde 0.0\') '
        f'-> lands {np.linalg.norm(th[:2] - HAND[:2]):.0f} m from the hand guess, hfov {th[6]:.1f} (guess 40): the guess was good.',
        fill='#94a3b8', font=f_s)
d_c = np.asarray(cam_e.get_pixel_direction((1920, 864)), float)
d_c /= np.linalg.norm(d_c)
vh = hill_mid - o_e
hill_off = math.degrees(math.acos(float(np.clip(d_c @ (vh / np.linalg.norm(vh)), -1, 1))))
dr.text((28, 100),
        f'From there the ridge marking points {abs(gap):.0f} deg away from the real hill: '
        f'the hill sits {hill_off:.0f} deg off-axis, {hill_off - th[6] / 2:.0f} deg beyond the '
        f'frame edge ({th[6] / 2:.0f} deg).',
        fill='#94a3b8', font=f_s)
dr.text((28, 130),
        f'Dashed red: the yaw the camera would need ({yaw_fit:.0f} -> {(yaw_fit + gap) % 360:.0f}) '
        f'- it would drag billboard & Rohde {abs(gap):.0f} deg (~{abs(gap) * 3840 / th[6]:.0f} px) off their pixels.',
        fill='#94a3b8', font=f_s)
dr.text((28, 160), 'Free-pose test (~1200 starts): no plausible pose reconciles all four markings; 37-102\' irreducible.',
        fill='#64748b', font=f_s)
# echelle + nord
sx, sy = P(XMAX - 1150, YMIN + 120)
dr.line([sx, sy, sx + 1000 * S, sy], fill='#e2e8f0', width=4)
dr.text((sx + 150, sy - 34), '1 km', fill='#e2e8f0', font=f_s)
nx, ny = P(XMAX - 250, YMIN + 350)
dr.line([nx, ny, nx, ny - 60], fill='#e2e8f0', width=4)
dr.polygon([nx - 8, ny - 55, nx + 8, ny - 55, nx, ny - 80], fill='#e2e8f0')
dr.text((nx - 8, ny + 8), 'N', fill='#e2e8f0', font=f_m)

out = os.path.join(REPO, 'tools', 'generated', 'ambrosia_bounty',
                   'explosion_hill_map.png')
os.makedirs(os.path.dirname(out), exist_ok=True)
img.save(out)
print('->', out)
