#!/usr/bin/env python3
"""v16_infill.py — densification ESTIMEE des ilots urbains vides de la V16 (couche VISUELLE de l'onglet 3D). [INFILL-V1 2026-10-05]

Le jeu a des ilots pleins (Vice Beach, Downtown, Little Haiti...); la V16 n'y dessine souvent que l'ilot (gris 217) sans
les batiments. Cette couche remplit ces ilots d'un bati PLAUSIBLE, clairement ESTIME (rien n'est ecrit dans les meshes,
chip a part dans le rendu): ilots = composantes gris 217 de la V16 (z4, 2 m/px) hors emprises V16 (176), hors volumes
modelises et remplissage existant (dilates 4 m); trottoir 3 m; bati en front de rue sur 22 m de profondeur max (coeurs
d'ilots libres), parcelles de 14 a 32 m le long de l'axe principal de l'ilot, petits retraits aleatoires.
Exclu: l'ile du port (terminal). Hauteurs par quartier: coeur Downtown/Brickell 18-60 m, Vice Beach 8-22 m, ailleurs 4.5-12 m.
Sortie (ignoree par git): tools/threejs/_v16_infill.json (meme format que _v16_massing.json)
Usage: python3 tools/v16_infill.py
"""
import json, os, sys, math
import numpy as np
import cv2
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import horizon_resect as HR

TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,16', '4')
SOL = os.path.join(THIS, 'threejs', '_mesh_solids.json')
MASS = os.path.join(THIS, 'threejs', '_v16_massing.json')
OUT = os.path.join(THIS, 'threejs', '_v16_infill.json')
X0, X1, Y0, Y1 = -4200, 3400, -3200, 5400
MPX = 2.0


def raster():
    s = 1.0 / MPX                                   # px par metre (z4)
    tx0, tx1 = int((X0 + 16384) * s // 256), int((X1 + 16384) * s // 256)
    ty0, ty1 = int((16384 - Y1) * s // 256), int((16384 - Y0) * s // 256)
    im = Image.new('RGB', ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            fp = os.path.join(TILES, '4,%d,%d.jpg' % (ty, tx))
            if os.path.exists(fp): im.paste(Image.open(fp), ((tx - tx0) * 256, (ty - ty0) * 256))
    ox, oy = int((X0 + 16384) * s - tx0 * 256), int((16384 - Y1) * s - ty0 * 256)
    W, H = int((X1 - X0) * s), int((Y1 - Y0) * s)
    return np.asarray(im.crop((ox, oy, ox + W, oy + H))).astype(np.int16)


def w2p(x, y): return ((x - X0) / MPX, (Y1 - y) / MPX)
def p2w(i, j): return (X0 + i * MPX, Y1 - j * MPX)


def main():
    A = raster(); H, W = A.shape[:2]
    near = lambda c, t: (np.abs(A - np.array(c)).max(2) <= t)
    urban = near((217, 217, 217), 6)
    taken = np.zeros((H, W), np.uint8)
    polys = []
    for so in json.load(open(SOL)).values():
        for L in so['layers'][:1]:
            for p in L['polys']: polys.append(p['outer'])
    for m in json.load(open(MASS)): polys.append(m['o'])
    for O in polys:
        P = np.array([w2p(x, y) for x, y in O], np.float32)
        if len(P) >= 3: cv2.fillPoly(taken, [np.round(P).astype(np.int32)], 1)
    taken = cv2.dilate(taken, np.ones((5, 5), np.uint8)) | near((176, 176, 176), 8).astype(np.uint8)
    free = urban & (taken == 0)
    n, lab, st, _ = cv2.connectedComponentsWithStats(free.astype(np.uint8), 4)
    rnd = lambda k: (math.sin(k * 12.9898 + 4.4) * 43758.5453) % 1.0
    out = []
    for k in range(1, n):
        area = st[k, cv2.CC_STAT_AREA] * MPX * MPX
        if area < 900: continue
        x, y, w, h = st[k, :4]
        sub = (lab[y:y + h, x:x + w] == k).astype(np.uint8)
        dist = cv2.distanceTransform(np.pad(sub, 1), cv2.DIST_L2, 5)[1:-1, 1:-1] * MPX   # m depuis le bord de l'ilot
        band = (dist >= 3.0) & (dist <= 25.0)                                            # trottoir 3 m, front bati <= 22 m
        if band.sum() * MPX * MPX < 300: continue
        ys, xs = np.nonzero(sub)
        pts = np.c_[xs, ys].astype(np.float32)
        (cx, cy), (rw, rh), ang = cv2.minAreaRect(pts)
        th = math.radians(ang); ux, uy = math.cos(th), math.sin(th); vx, vy = -uy, ux
        # quartier (monde)
        wx, wy = p2w(x + w / 2, y + h / 2)
        core = -1250 < wx < 350 and -1350 < wy < 1250
        beach = 1250 < wx < 2700 and -200 < wy < 4300
        # grille de parcelles dans le repere de l'ilot
        U = (xs - cx) * ux + (ys - cy) * uy; V = (xs - cx) * vx + (ys - cy) * vy
        u0, u1, v0, v1 = U.min(), U.max(), V.min(), V.max()
        lot = (16 + 14 * rnd(k)) / MPX                                                  # parcelles 16-30 m
        bandm = (band & (sub > 0)).astype(np.uint8)
        for iu in range(int(math.floor(u0 / lot)), int(math.ceil(u1 / lot)) + 1):
            for iv in range(int(math.floor(v0 / lot)), int(math.ceil(v1 / lot)) + 1):
                a0, a1, b0, b1 = iu * lot, (iu + 1) * lot, iv * lot, (iv + 1) * lot
                Q = np.array([(cx + a * ux + b * vx, cy + a * uy + b * vy) for a, b in ((a0, b0), (a1, b0), (a1, b1), (a0, b1))])
                qa = np.round(Q).astype(np.int32)
                bx0, by0 = max(0, qa[:, 0].min()), max(0, qa[:, 1].min()); bx1, by1 = min(w, qa[:, 0].max() + 1), min(h, qa[:, 1].max() + 1)
                if bx1 - bx0 < 3 or by1 - by0 < 3: continue
                win_ = bandm[by0:by1, bx0:bx1]
                if win_.sum() * MPX * MPX < 110: continue
                m = np.zeros_like(win_); cv2.fillPoly(m, [qa - [bx0, by0]], 1)
                m &= win_
                m = cv2.erode(m, np.ones((2, 2), np.uint8))                              # ~1 m entre voisins
                if m.sum() * MPX * MPX < 110: continue
                cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cs = [c + [bx0, by0] for c in cs]
                for cn in cs:
                    if cv2.contourArea(cn) * MPX * MPX < 110: continue
                    cn = cv2.approxPolyDP(cn, 0.8, True).reshape(-1, 2)
                    if len(cn) < 3: continue
                    r1 = rnd(iu * 7.7 + iv * 1.3 + k)
                    if core: hgt = 18 + 42 * r1 ** 1.7
                    elif beach: hgt = 8 + 14 * r1 ** 1.3
                    else: hgt = 4.5 + 7.5 * r1
                    wq = [p2w(x + a, y + b) for a, b in cn]
                    gx, gy = np.mean([q[0] for q in wq]), np.mean([q[1] for q in wq])
                    if 600 < gx < 1850 and -1150 < gy < -80: continue                   # ile du port (terminal industriel, parc a conteneurs)
                    z = max(0.0, float(HR.ground(np.array([gx]), np.array([gy]))[0]))
                    out.append({'o': [[round(a, 1), round(b, 1)] for a, b in wq], 'z': round(z, 2), 'h': round(hgt, 1), 'k': int(rnd(k * 3 + iu + iv * 7) * 1000)})
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print('%d batiments ESTIMES dans %d ilots -> %s (%.0f ko)' % (len(out), n - 1, OUT, os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
