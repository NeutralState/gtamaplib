#!/usr/bin/env python3
"""explosion_resection.py — la pose d'Explosion peut-elle rendre ses 4
marquages coherents avec les rayons des cams de confiance?

Hypothese testee: 'Ambrosia Hill (TW)/(BW)' d'Explosion = la colline du
cluster (rayons Bikers). Pose d'Explosion 100% libre (elle est posee a la
main). Chaque LM vit a profondeur t le long du rayon partenaire.
11 inconnues (x,y,z,yaw,pitch,roll,hfov + 4 t), 8 equations.
"""
import os
import sys

REPO = '/Users/alexandreleblanc/Downloads/gtamaplib-main'
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, REPO)
os.chdir(REPO)

import numpy as np
from scipy.optimize import minimize
import common

# rayons partenaires: (cam, lm_partenaire, pixel_explosion)
CONS = [
    ('Ambrosia 01 (Bikers)', 'Ambrosia Hill (TW)', (137, 252)),
    ('Ambrosia 01 (Bikers)', 'Ambrosia Hill (BW)', (310, 290)),
    ('Interchange', 'Tall Billboard near Interchange', (225, 55)),
    ('Metro (NE) (B)', 'Rohde Building (BSW)', (3306, 373)),
]
SIZE = (3840, 1728)

import gtamaplib as ml  # noqa: F401  (via common)
import json
px = json.load(open('gtamapdata/pixels.json'))

RAYS = []
for cname, lm, epx in CONS:
    cam = common.get_cam(cname)
    p = px[cname][lm]
    o = np.asarray(cam.xyz, float)
    d = np.asarray(cam.get_pixel_direction(p), float)
    d = d / np.linalg.norm(d)
    RAYS.append((o, d, lm, epx))
    print(f'rayon {cname:25s} {lm:32s} origine {np.round(o,1)} dir {np.round(d,3)}')


def make_state(th):
    return {'xyz': (th[0], th[1], th[2]), 'ypr': (th[3], th[4], th[5]),
            'fov': (th[6], None)}


def residuals(th):
    """angulaire (arcmin) entre le rayon-pixel d'Explosion et le point a
    profondeur t sur le rayon partenaire."""
    cam = common.get_cam('Explosion', make_state(th))
    out = []
    o_e = np.asarray(th[:3], float)
    for i, (o, d, lm, epx) in enumerate(RAYS):
        t = th[7 + i]
        P = o + t * d
        de = np.asarray(cam.get_pixel_direction(epx), float)
        de /= np.linalg.norm(de)
        v = P - o_e
        nv = np.linalg.norm(v)
        if nv < 1:
            out.append(1e4)
            continue
        c = float(np.clip(np.dot(de, v / nv), -1, 1))
        out.append(np.degrees(np.arccos(c)) * 60)
    return out


def cost(th, with_hill=True):
    r = residuals(th)
    idx = range(4) if with_hill else range(2, 4)
    c = sum(np.log1p((r[i] / 5.0) ** 2) for i in idx)
    # pose plausible: zone metro Vice City, fov trailer, cam basse
    if not (-3500 <= th[0] <= 500):
        c += 50 + abs(th[0]) / 100
    if not (-1500 <= th[1] <= 1500):
        c += 50 + abs(th[1]) / 100
    if not (0 <= th[2] <= 200):
        c += 50 + abs(th[2])
    if not (25 <= th[6] <= 70):
        c += 50 + abs(th[6] - 45)
    if not (-8 <= th[4] <= 6):
        c += (abs(th[4]) - 8) ** 2
    if abs(th[5]) > 3:
        c += (abs(th[5]) - 3) ** 2
    # points monde plausibles
    Ptw = RAYS[0][0] + th[7] * RAYS[0][1]
    Pbw = RAYS[1][0] + th[8] * RAYS[1][1]
    Pbb = RAYS[2][0] + th[9] * RAYS[2][1]
    Pro = RAYS[3][0] + th[10] * RAYS[3][1]
    if with_hill:
        if not (20 <= Ptw[2] <= 400):        # sommet de colline
            c += 20 + abs(Ptw[2] - 150) / 10
        dxy = float(np.hypot(*(Ptw - Pbw)[:2]))
        if dxy > 400:                         # meme flanc ouest
            c += (dxy - 400) / 50
        if Ptw[2] < Pbw[2]:                   # top au-dessus de bottom
            c += 20
    if not (10 <= Pbb[2] <= 90):              # haut de billboard
        c += 20 + abs(Pbb[2] - 40) / 5
    if not (-5 <= Pro[2] <= 45):              # coin bas de building
        c += 20 + abs(Pro[2]) / 5
    for i in range(4):
        t = th[7 + i]
        if not (50 <= t <= 7000):
            c += 50 + abs(t) / 100
    return c


best = None
rng = np.random.default_rng(7)
# multi-start large: position downtown/large, yaw plein cercle
for trial in range(400):
    x = rng.uniform(-3500, 500)
    y = rng.uniform(-1500, 1500)
    z = rng.uniform(2, 120)
    yaw = rng.uniform(0, 360)
    fov = rng.uniform(28, 65)
    th0 = np.array([x, y, z, yaw, rng.uniform(-5, 2), 0.0, fov,
                    *rng.uniform(200, 6000, 4)])
    res = minimize(cost, th0, method='Powell',
                   options={'maxiter': 4000, 'xtol': 1e-4, 'ftol': 1e-6})
    if best is None or res.fun < best.fun:
        best = res
        r = residuals(res.x)
        print(f'trial {trial:3d} cost {res.fun:8.3f}  res(arcmin) '
              + ' '.join(f'{e:7.1f}' for e in r))

th = best.x
r = residuals(th)
print('\n=== MEILLEURE POSE LIBRE ===')
print(f'xyz  ({th[0]:9.1f}, {th[1]:9.1f}, {th[2]:7.1f})')
print(f'ypr  ({th[3] % 360:7.2f}, {th[4]:6.2f}, {th[5]:5.2f})  hfov {th[6]:5.2f}')
for i, (o, d, lm, epx) in enumerate(RAYS):
    t = th[7 + i]
    P = o + t * d
    print(f'{lm:34s} res {r[i]:7.1f}\'  t={t:7.0f}m  -> ({P[0]:8.1f}, {P[1]:8.1f}, {P[2]:6.1f})')

# structure: TW/BW meme colline -> alignes xy, TW plus haut
Ptw = RAYS[0][0] + th[7] * RAYS[0][1]
Pbw = RAYS[1][0] + th[8] * RAYS[1][1]
dxy = float(np.hypot(*(Ptw - Pbw)[:2]))
print(f'\ncheck structure colline: |xy(TW)-xy(BW)| = {dxy:.0f}m, '
      f'z TW {Ptw[2]:.0f} vs BW {Pbw[2]:.0f}')
d_hill = float(np.linalg.norm(Ptw - np.asarray(th[:3])))
print(f'distance cam->TW: {d_hill:.0f}m')

print('\n=== CONTROLE sans la colline (billboard+Rohde seuls) ===')
best2 = None
for trial in range(150):
    x = rng.uniform(-3500, 500); y = rng.uniform(-1500, 1500)
    th0 = np.array([x, y, rng.uniform(2, 120), rng.uniform(0, 360),
                    rng.uniform(-5, 2), 0.0, rng.uniform(28, 65),
                    *rng.uniform(200, 6000, 4)])
    res = minimize(lambda t: cost(t, with_hill=False), th0, method='Powell',
                   options={'maxiter': 3000, 'xtol': 1e-4, 'ftol': 1e-6})
    if best2 is None or res.fun < best2.fun:
        best2 = res
th2 = best2.x
r2 = residuals(th2)
print(f'xyz ({th2[0]:8.1f}, {th2[1]:8.1f}, {th2[2]:6.1f}) ypr ({th2[3]%360:6.2f}, {th2[4]:5.2f}, {th2[5]:4.2f}) hfov {th2[6]:5.2f}')
for i, (o, d, lm, epx) in enumerate(RAYS):
    P = o + th2[7+i]*d
    tag = ' (CONTRAINTE)' if i >= 2 else ' (libre — ou pointent les rayons colline?)'
    print(f'{lm:34s} res {r2[i]:8.1f}\'  t={th2[7+i]:6.0f}m z={P[2]:6.1f}{tag}')
