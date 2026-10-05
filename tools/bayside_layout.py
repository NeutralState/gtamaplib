#!/usr/bin/env python3
"""bayside_layout.py — Bayfront Park / Bayside: amphitheatre, promenade couverte, marina (couche VISUELLE). [BAYSIDE-V1 2026-10-05]

Plan = la V16 (emprises du remplissage urbain + pontons de la marina lus sur les tuiles z5); aspect = frames du jeu
(Vice City 11 (Megamundo), vue de l'amphitheatre au sol): gradins bleus en eventail face a une scene ronde sous une grande
toiture en treillis blanc sur pieds obliques, promenade courbe sous une suite de voiles blanches, marina pleine de bateaux.
- scene: emprise V16 948 (carre ~20 m); gradins: 9 coins V16 (949-957) remplis de rangees radiales (0.9 m, +0.45 m/rang)
- promenade: bande courbe V16 958 -> ligne mediane (anneau autour de la scene) -> voiles tous les ~7 m
- marina: pixels gris clair des pontons dans l'eau (x -170..10, y 100..310) + bateaux amarres (espacement 9 m, ESTIME)
Sortie (ignoree par git): tools/threejs/_bayside.json
Usage: python3 tools/bayside_layout.py
"""
import json, os, sys, math
import numpy as np
import cv2
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import horizon_resect as HR

MASS = os.path.join(THIS, 'threejs', '_v16_massing.json')
TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,16', '5')
OUT = os.path.join(THIS, 'threejs', '_bayside.json')
ZONE = (-300, -190, -275, -165)                      # emprises de l'amphitheatre (x0, x1, y0, y1)


def tile_crop(x0, x1, y0, y1):
    tx0, tx1 = int((x0 + 16384) // 256), int((x1 + 16384) // 256); ty0, ty1 = int((16384 - y1) // 256), int((16384 - y0) // 256)
    im = Image.new('RGB', ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            fp = os.path.join(TILES, '5,%d,%d.jpg' % (ty, tx))
            if os.path.exists(fp): im.paste(Image.open(fp), ((tx - tx0) * 256, (ty - ty0) * 256))
    ox, oy = int(x0 + 16384 - tx0 * 256), int(16384 - y1 - ty0 * 256)
    return np.asarray(im.crop((ox, oy, ox + x1 - x0, oy + y1 - y0))).astype(int)


def inpoly(x, y, O):
    c = False; n = len(O)
    for i in range(n):
        x1, y1 = O[i]; x2, y2 = O[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def main():
    M = json.load(open(MASS)); zone = []
    for i, m in enumerate(M):
        O = np.array(m['o'], float); c = O.mean(0)
        if ZONE[0] < c[0] < ZONE[1] and ZONE[2] < c[1] < ZONE[3]: zone.append((i, O, m['z']))
    area = lambda O: abs(np.sum(O[:, 0] * np.roll(O[:, 1], 1) - np.roll(O[:, 0], 1) * O[:, 1])) / 2
    arc = max(zone, key=lambda t: len(t[1]))                                  # bande courbe (le plus de sommets)
    rest = [t for t in zone if t[0] != arc[0]]
    stage = max(rest, key=lambda t: area(t[1]))                               # la plus grande emprise compacte
    wedges = [t for t in rest if t[0] != stage[0]]
    sc = stage[1].mean(0); zg = float(min(t[2] for t in zone))
    # gradins [BAYSIDE-V3, compare a la frame Vice City 11 (Megamundo)]: fer a cheval COMPACT = les coins V16 (deux couronnes
    # = deux niveaux separes par une allee circulaire), PAS jusqu'a la promenade (une pelouse les separe dans le jeu);
    # trous angulaires entre coins combles, allee a la frontiere des deux couronnes
    allw = np.concatenate([O for _, O, _ in wedges]); rw = np.hypot(*(allw - sc).T)
    thw = np.arctan2(allw[:, 1] - sc[1], allw[:, 0] - sc[0]); thm = math.atan2(np.mean(np.sin(thw)), np.mean(np.cos(thw)))
    dw = np.angle(np.exp(1j * (thw - thm))); tlo, thi = dw.min(), dw.max()
    r0, r1 = float(rw.min()), float(rw.max())
    inner_out = [float(np.hypot(*(O - sc).T).max()) for _, O, _ in wedges]; ring_split = float(np.median(inner_out))
    aisle = (ring_split - 0.9, ring_split + 0.9) if r0 + 4 < ring_split < r1 - 4 else (1e9, 1e9)
    seats = []
    k = 0; r = r0 + 0.45
    while r < r1:
        if not (aisle[0] <= r <= aisle[1]):
            step = 0.95 / r
            for t in np.arange(tlo, thi, step):
                a = thm + t
                seats.append([round(sc[0] + r * math.cos(a), 2), round(sc[1] + r * math.sin(a), 2), round(a, 4), k])
        r += 0.9; k += 1
    bowl = {'c': [round(float(sc[0]), 2), round(float(sc[1]), 2)], 'th0': round(float(thm + tlo), 4), 'th1': round(float(thm + thi), 4),
            'r0': round(r0, 2), 'r1': round(r1, 2), 'rows': k}
    # promenade: ligne mediane de la bande = anneau (rayon moyen) borne par les angles de la bande
    A = arc[1]
    # cercle ajuste sur la bande (moindres carres) — la promenade n'est pas forcement centree sur la scene
    Am = np.array([[2 * x, 2 * y, 1.0] for x, y in A]); bm = np.array([x * x + y * y for x, y in A])
    cxa, cya, cc = np.linalg.lstsq(Am, bm, rcond=None)[0]; ac = np.array([cxa, cya])
    ra = np.hypot(*(A - ac).T); th = np.arctan2(A[:, 1] - ac[1], A[:, 0] - ac[0])
    thc = math.atan2(*(np.mean(np.c_[np.sin(th), np.cos(th)], 0)))
    dth = np.angle(np.exp(1j * (th - thc)))
    rm, half = float(np.median(ra)), float(np.ptp(ra)) / 2
    sails = []
    t = dth.min() + 0.02
    while t < dth.max() - 0.02:
        a = thc + t; x, y = ac[0] + rm * math.cos(a), ac[1] + rm * math.sin(a)
        if inpoly(x, y, A) or True: sails.append([round(x, 2), round(y, 2), round(a, 4)])
        t += 7.0 / rm
    # marina: pontons (gris clair dans l'eau) + bateaux amarres
    X0, X1, Y0, Y1 = -260, 10, 60, 310
    T = tile_crop(X0, X1, Y0, Y1)
    water = (T[..., 2] > T[..., 0] + 40)
    light = (T.min(2) > 180) & (T.max(2) < 214) & (T.max(2) - T.min(2) < 28)     # pontons: traits gris ~200 (quai 217, lettres des libelles 252)
    wd = cv2.dilate(water.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    pier = light & wd
    # garder les structures fines (pontons): ouverture morphologique qui enleve les grosses plaques (quais)
    big = cv2.morphologyEx(pier.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)   # lettres des libelles (traits epais)
    big = cv2.dilate(big.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    pier &= ~big
    ys, xs = np.nonzero(pier)
    piers = [[X0 + int(x) + 0.5, Y1 - int(y) - 0.5] for x, y in zip(xs, ys)]
    dist = cv2.distanceTransform((~pier).astype(np.uint8), cv2.DIST_L2, 5)
    cand = np.argwhere(water & (dist >= 4.5) & (dist <= 7.0))
    rng = np.random.default_rng(7); rng.shuffle(cand)
    boats = []
    for j, i in cand:
        x, y = X0 + i + 0.5, Y1 - j - 0.5
        if any(math.hypot(x - b[0], y - b[1]) < 9.0 for b in boats): continue
        # direction: perpendiculaire au ponton le plus proche (amarrage en epi)
        w = pier[max(0, j - 10):j + 11, max(0, i - 10):i + 11]; py, px = np.nonzero(w)
        if len(px) < 4: continue
        P = np.c_[px, py].astype(float); P -= P.mean(0); ev = np.linalg.eigh(P.T @ P)[1][:, -1]   # axe du ponton (pixels)
        ang = math.atan2(ev[0], ev[1])                                        # perpendiculaire, repere monde (y inverse)
        L = 9 + 11 * rng.random()
        boats.append([round(x, 2), round(y, 2), round(ang, 3), round(L, 1)])
        if len(boats) > 160: break
    out = {'stage': {'o': stage[1].round(2).tolist(), 'z': zg}, 'seats': seats, 'seat_z': zg, 'bowl': bowl,
           'arc': {'o': A.round(2).tolist(), 'sails': sails, 'width': round(2 * half, 1)},
           'piers': piers, 'boats': boats, 'replace': [t[0] for t in zone],
           '_src': 'plan V16 (emprises 948-958 + pontons), aspect = frames (Megamundo, amphitheatre au sol); bateaux ESTIMES'}
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print('scene %s, %d places/cellules en %d rangs, %d voiles (r %.0f m), %d px de pontons, %d bateaux -> %s' % (
        sc.round(1), len(seats), k, len(sails), rm, len(piers), len(boats), OUT))


if __name__ == '__main__':
    main()
