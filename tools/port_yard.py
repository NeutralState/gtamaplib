#!/usr/bin/env python3
"""port_yard.py — parc a conteneurs du terminal de Port VC (couche VISUELLE). [PORT-YARD-V1 2026-10-05]

Port Vice City (A) montre le terminal rempli de piles de conteneurs; leur disposition exacte n'est pas mesurable -> la
DISPOSITION est ESTIMEE, la zone ne l'est pas: seulement les pixels « parc » de la V16 (gris 200) du terminal, a >= 6 m
des voies (gris fonce) et des batiments (176), a >= 45 m de l'eau (tablier des grues le long du quai).
Blocs de conteneurs de 40' alignes sur le quai le plus proche (axe du navire a quai = emprise V16 sur l'eau a cote des
grues): travees de 12.8 m, allee de 14 m toutes les 8 travees; rangees de 2.6 m, allee de 12 m toutes les 6 rangees;
1 a 5 niveaux, coherents par bloc. Couleurs: palette vue sur la frame (index dans le rendu).
Sortie (ignoree par git): tools/threejs/_port_yard.json {containers: [[x, y, z, ang, tiers, colorSeed], ...]}
Usage: python3 tools/port_yard.py
"""
import json, os, sys, math
import numpy as np
import cv2
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import horizon_resect as HR

TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,16', '5')
MESHES = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
MASS = os.path.join(THIS, 'threejs', '_v16_massing.json')
OUT = os.path.join(THIS, 'threejs', '_port_yard.json')
X0, X1, Y0, Y1 = 700, 1800, -1100, -100          # emprise du terminal (monde)


def raster():
    tx0, tx1 = int((X0 + 16384) // 256), int((X1 + 16384) // 256); ty0, ty1 = int((16384 - Y1) // 256), int((16384 - Y0) // 256)
    im = Image.new('RGB', ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            fp = os.path.join(TILES, '5,%d,%d.jpg' % (ty, tx))
            if os.path.exists(fp): im.paste(Image.open(fp), ((tx - tx0) * 256, (ty - ty0) * 256))
    ox, oy = int(X0 + 16384 - tx0 * 256), int(16384 - Y1 - ty0 * 256)
    return np.asarray(im.crop((ox, oy, ox + X1 - X0, oy + Y1 - Y0))).astype(int)   # 1 px = 1 m, ligne 0 = Y1


def main():
    A = raster(); H, W = A.shape[:2]
    near = lambda c, t: (np.abs(A - np.array(c)).max(2) <= t)
    yard = near((200, 200, 200), 7)
    water = (A[..., 2] > A[..., 0] + 40)
    block = near((80, 80, 80), 18) | near((176, 176, 176), 8) | (A.min(2) > 235)          # voies, batiments, marquages
    # le parc: les zones grises du terminal decoupees par les voies internes -> toutes celles > 5000 m2 dont le centre est
    # a < 450 m d'une grue (pas les ilots voisins)
    M0 = json.load(open(MESHES)); cr0 = [np.array(m['world_edges'], float).reshape(-1, 3)[:, :2].mean(0) for k, m in M0.items() if 'Container Crane' in k]
    n, lab, st, cen = cv2.connectedComponentsWithStats(yard.astype(np.uint8), 4)
    good = [k for k in range(1, n) if st[k, cv2.CC_STAT_AREA] > 5000 and min(np.hypot(c[0] - (cen[k][0] + X0), c[1] - (Y1 - cen[k][1])) for c in cr0) < 450]
    yard = np.isin(lab, good)
    dist_block = cv2.distanceTransform((~block).astype(np.uint8), cv2.DIST_L2, 5)
    dist_water = cv2.distanceTransform((~water).astype(np.uint8), cv2.DIST_L2, 5)
    ok = yard & (dist_block >= 6) & (dist_water >= 45)
    # axes des quais: navires a quai (emprises V16 sur l'eau pres des grues)
    M = json.load(open(MESHES)); cranes = []
    for nme, m in M.items():
        if 'Container Crane' in nme:
            P = np.array(m['world_edges'], float).reshape(-1, 3); cranes.append(P[:, :2].mean(0))
    ships = []
    for m in json.load(open(MASS)):
        O = np.array(m['o'], float); c = O.mean(0)
        if m['z'] > 0.5 or min(np.hypot(*(np.array(cranes) - c).T)) > 250: continue
        (cx, cy), (w, h), a = cv2.minAreaRect(O.astype(np.float32))
        if max(w, h) < 120: continue
        ang = math.radians(a if w >= h else a + 90); ships.append((c, ang))
    out = []; rnd = lambda k: (math.sin(k * 12.9898 + 7.7) * 43758.5453) % 1.0
    # une grille par quai: chaque cellule du parc prend l'axe du navire le plus proche
    for si, (c, ang) in enumerate(ships):
        ux, uy = math.cos(ang), math.sin(ang); vx, vy = -uy, ux
        for iu in range(-120, 121):
            for iv in range(-120, 121):
                bu, bv = iu // 9, iv // 7                              # blocs: 8 travees + allee, 6 rangees + allee
                if iu % 9 == 8 or iv % 7 == 6: continue
                u = iu * 12.8 + bu * 1.2; v = iv * 2.6 + bv * 9.4
                x = c[0] + u * ux + v * vx; y = c[1] + u * uy + v * vy
                d = [np.hypot(*(c2 - (x, y))) for c2, _ in ships]
                if int(np.argmin(d)) != si: continue                    # zone de ce quai
                ok_all = True
                for du in (-6.1, 0, 6.1):
                    for dv in (-1.2, 1.2):
                        px = x + du * ux + dv * vx - X0; py = Y1 - (y + du * uy + dv * vy)
                        i, j = int(px), int(py)
                        if not (0 <= i < W and 0 <= j < H and ok[j, i]): ok_all = False; break
                    if not ok_all: break
                if not ok_all: continue
                base = 1 + int(rnd(si * 1000 + bu * 37 + bv * 101) * 4.2)   # hauteur coherente par bloc
                tiers = max(1, min(5, base + (1 if rnd(iu * 7 + iv * 13 + si) > 0.8 else 0) - (1 if rnd(iu * 3 + iv * 5 + si) > 0.85 else 0)))
                z = max(0.0, float(HR.ground(np.array([x]), np.array([y]))[0]))
                out.append([round(x, 2), round(y, 2), round(z, 2), round(ang, 4), tiers, int(rnd(iu * 31 + iv * 17 + si * 7) * 1000)])
    json.dump({'containers': out, '_src': 'ESTIMATED layout on the V16 yard area (port_yard.py); yard filled as on Port Vice City (A)'}, open(OUT, 'w'), separators=(',', ':'))
    print('%d piles, %d conteneurs (%d quais) -> %s' % (len(out), sum(o[4] for o in out), len(ships), OUT))


if __name__ == '__main__':
    main()
