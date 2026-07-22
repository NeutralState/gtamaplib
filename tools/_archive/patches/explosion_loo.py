#!/usr/bin/env python3
"""leave-one-out: colline+billboard (sans Rohde) vs colline+Rohde (sans
billboard) — laquelle des paires force une pose absurde?"""
import os, sys, json
REPO = '/Users/alexandreleblanc/Downloads/gtamaplib-main'
sys.path.insert(0, os.path.join(REPO, 'tools')); sys.path.insert(0, REPO)
os.chdir(REPO)
import numpy as np
from scipy.optimize import minimize
import common

CONS = [('Ambrosia 01 (Bikers)', 'Ambrosia Hill (TW)', (137, 252)),
        ('Ambrosia 01 (Bikers)', 'Ambrosia Hill (BW)', (310, 290)),
        ('Interchange', 'Tall Billboard near Interchange', (225, 55)),
        ('Metro (NE) (B)', 'Rohde Building (BSW)', (3306, 373))]
px = json.load(open('gtamapdata/pixels.json'))
RAYS = []
for cname, lm, epx in CONS:
    cam = common.get_cam(cname)
    o = np.asarray(cam.xyz, float)
    d = np.asarray(cam.get_pixel_direction(px[cname][lm]), float)
    RAYS.append((o, d / np.linalg.norm(d), lm, epx))

def residuals(th):
    cam = common.get_cam('Explosion', {'xyz': tuple(th[:3]), 'ypr': tuple(th[3:6]), 'fov': (th[6], None)})
    o_e = np.asarray(th[:3], float); out = []
    for i, (o, d, lm, epx) in enumerate(RAYS):
        P = o + th[7 + i] * d
        de = np.asarray(cam.get_pixel_direction(epx), float); de /= np.linalg.norm(de)
        v = P - o_e; nv = np.linalg.norm(v)
        if nv < 1: out.append(1e4); continue
        out.append(np.degrees(np.arccos(np.clip(de @ (v / nv), -1, 1))) * 60)
    return out

def cost(th, idx):
    r = residuals(th)
    c = sum(np.log1p((r[i] / 5.0) ** 2) for i in idx)
    if not (-3500 <= th[0] <= 500):  c += 50 + abs(th[0]) / 100
    if not (-1500 <= th[1] <= 1500): c += 50 + abs(th[1]) / 100
    if not (0 <= th[2] <= 200):      c += 50 + abs(th[2])
    if not (25 <= th[6] <= 70):      c += 50 + abs(th[6] - 45)
    if not (-8 <= th[4] <= 6):       c += (abs(th[4]) - 8) ** 2
    if abs(th[5]) > 3:               c += (abs(th[5]) - 3) ** 2
    Ptw = RAYS[0][0] + th[7] * RAYS[0][1]; Pbw = RAYS[1][0] + th[8] * RAYS[1][1]
    Pbb = RAYS[2][0] + th[9] * RAYS[2][1]; Pro = RAYS[3][0] + th[10] * RAYS[3][1]
    if 0 in idx:
        # vraie colline: sommet a 40m+ au-dessus de Bikers, pas une butte
        if th[7] < 250:              c += (250 - th[7]) / 10
        if not (45 <= Ptw[2] <= 400): c += 20 + abs(Ptw[2] - 150) / 10
        dxy = float(np.hypot(*(Ptw - Pbw)[:2]))
        if dxy > 400: c += (dxy - 400) / 50
        if Ptw[2] < Pbw[2] + 10: c += 20
    if 2 in idx and not (10 <= Pbb[2] <= 90): c += 20 + abs(Pbb[2] - 40) / 5
    if 3 in idx and not (-5 <= Pro[2] <= 45): c += 20 + abs(Pro[2]) / 5
    for i in range(4):
        if not (50 <= th[7 + i] <= 7000): c += 50 + abs(th[7 + i]) / 100
    return c

rng = np.random.default_rng(11)
for label, idx in [('COLLINE+BILLBOARD (sans Rohde)', (0, 1, 2)),
                   ('COLLINE+ROHDE (sans billboard)', (0, 1, 3)),
                   ('LES 4 (colline non-degeneree)', (0, 1, 2, 3))]:
    best = None
    for trial in range(250):
        th0 = np.array([rng.uniform(-3500, 500), rng.uniform(-1500, 1500), rng.uniform(2, 120),
                        rng.uniform(0, 360), rng.uniform(-5, 2), 0.0, rng.uniform(28, 65),
                        *rng.uniform(200, 6000, 4)])
        res = minimize(cost, th0, args=(idx,), method='Powell',
                       options={'maxiter': 3000, 'xtol': 1e-4, 'ftol': 1e-6})
        if best is None or res.fun < best.fun: best = res
    th = best.x; r = residuals(th)
    print(f'\n=== {label} ===  cost {best.fun:.3f}')
    print(f'xyz ({th[0]:8.1f}, {th[1]:8.1f}, {th[2]:6.1f}) ypr ({th[3]%360:6.2f}, {th[4]:5.2f}, {th[5]:4.2f}) hfov {th[6]:5.2f}')
    for i, (o, d, lm, epx) in enumerate(RAYS):
        P = o + th[7 + i] * d
        used = 'X' if i in idx else ' '
        print(f' [{used}] {lm:34s} res {r[i]:8.1f}\'  t={th[7+i]:6.0f}m -> ({P[0]:8.1f},{P[1]:8.1f},{P[2]:6.1f})')
