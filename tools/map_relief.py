#!/usr/bin/env python3
"""map_relief.py — le relief lu sur la CARTE, calibre par nos ancres. [MAP-RELIEF-V1]

Le declic (Alexandre, 2026-07-30): "regarde la map, c'est 0 parfait mais ca
va te permettre de comprendre comment ca marche".

Ce que la carte communautaire contient et que nous n'exploitions pas: les
massifs y sont dessines en PALIERS DE VERT emboites — une carte
hypsometrique. Chaque palier est une tranche d'altitude, et son contour est
le plan au sol EXACT du massif a cette altitude: sa forme, son orientation,
son etendue, ses deux sommets quand il y en a deux.

C'est exactement ce qui manquait a toutes nos tentatives precedentes:

  * la silhouette d'une frame donne la forme VUE, pas le plan au sol —
    la profondeur y est une hypothese (plan, rideau) et c'est elle qui
    cassait (Mount Waffles: crete orientee sur l'alignement de 3 ancres
    au lieu de suivre la vraie arete)
  * la crete declaree de rlx donne un plan au sol, mais a des distances
    devinees a l'oeil depuis une seule camera — mesuree contre nos
    triangulations, elle passe pour Gellhorn Hills (28 m rms) et casse
    pour Mount Waffles (322 m rms meme apres ajustement d'echelle)

La carte, elle, est DENSE et en XY pur. Ce qu'elle n'a pas, c'est
l'altitude: ses paliers ne sont pas cotes. C'est nous qui l'apportons —
nos landmarks triangules tombent dans les paliers et les cotent.

Repartition mesuree sur nos 15 ancres de relief:

    palier 0 (plaine)  z ~  81      palier 3   z ~ 112
    palier 1           z ~  81      palier 4   z ~ 196
    palier 2           z ~  97      palier 5   z ~ 207

Monotone. La carte donne la FORME, nous donnons l'ECHELLE VERTICALE.

ATTENTION (rappel d'Alexandre, deja inscrit dans map_crosscheck): la carte
est une observation communautaire au meilleur de nos connaissances, pas une
verite officielle. Elle est donc une BASE — dense et coherente — et jamais
un juge. Le juge reste nos ancres.

Usage:
  PYTHONPATH=. python3 tools/map_relief.py --calibrate
  PYTHONPATH=. python3 tools/map_relief.py --massif 'Mount Waffles' [--apply]
"""
import argparse
import collections
import json
import math
import os
import sys
import tempfile

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
from PIL import Image

TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,13', '5')
TILE = 256
MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
COLOR = '#4ade80'

# l'echelle hypsometrique de la carte, du plus clair (plaine) au plus fonce
PALETTE = [(186, 204, 120), (174, 198, 102), (156, 180, 90),
           (150, 168, 84), (132, 156, 72), (120, 144, 66)]
TOL2 = 900          # distance^2 max a une couleur de la palette (JPEG oblige)
KEY = ('mount', 'hill', 'ridge', 'pass')
SKIP = ('bridge', 'sign', 'billboard', 'road', 'st ', 'tower', 'station')


def compose(xmin, xmax, ymin, ymax):
    """Mosaique des tuiles couvrant la fenetre monde. Retourne (image, echelle
    px/m, origine monde du coin haut-gauche)."""
    lx, ty = xmin + 16384, 16384 - ymax
    rx, by = xmax + 16384, 16384 - ymin
    tx0, tx1 = int(lx // TILE), int(rx // TILE)
    ty0, ty1 = int(ty // TILE), int(by // TILE)
    comp = Image.new('RGB', ((tx1 - tx0 + 1) * TILE, (ty1 - ty0 + 1) * TILE),
                     PALETTE[0])
    got = 0
    for a in range(ty0, ty1 + 1):
        for b in range(tx0, tx1 + 1):
            p = os.path.join(TILES, f'5,{a},{b}.jpg')
            if os.path.exists(p):
                comp.paste(Image.open(p).convert('RGB'),
                           ((b - tx0) * TILE, (a - ty0) * TILE))
                got += 1
    comp = comp.crop((int(lx - tx0 * TILE), int(ty - ty0 * TILE),
                      int(rx - tx0 * TILE), int(by - ty0 * TILE)))
    return comp, got


def levels(img):
    """Carte des paliers: pour chaque pixel, l'indice de palette le plus
    proche, -1 si la couleur n'est pas du relief (route, ville, eau, texte)."""
    a = np.asarray(img, np.int16)
    d = np.stack([((a - np.array(p, np.int16)) ** 2).sum(axis=2) for p in PALETTE])
    lv = np.argmin(d, axis=0).astype(np.int16)
    lv[np.min(d, axis=0) > TOL2] = -1
    # DEBRUITAGE: les tuiles sont du JPEG, le ringing autour des traits et
    # des etiquettes seme des pixels isoles d'un palier voisin. Sans ca un
    # massif se decoupe en 130 ilots au lieu d'un seul.
    import cv2
    filled = np.where(lv < 0, 0, lv).astype(np.uint8)
    filled = cv2.medianBlur(filled, 9)
    return filled.astype(np.int16)


def sample_levels(pts):
    """Palier de la carte sous une liste de points monde. Le relief est sous
    les etiquettes et les traits: on prend le palier le plus FONCE d'une
    petite fenetre plutot que le pixel exact."""
    out, cache = [], {}
    for x, y in pts:
        px, py = x + 16384, 16384 - y
        tx, tyy = int(px // TILE), int(py // TILE)
        k = (tyy, tx)
        if k not in cache:
            p = os.path.join(TILES, f'5,{tyy},{tx}.jpg')
            cache[k] = (np.asarray(Image.open(p).convert('RGB'), np.int16)
                        if os.path.exists(p) else None)
        im = cache[k]
        if im is None:
            out.append(None)
            continue
        i, j = int(py - tyy * TILE), int(px - tx * TILE)
        patch = im[max(0, i - 2):i + 3, max(0, j - 2):j + 3].reshape(-1, 3)
        best = []
        for c in patch:
            dd = [int(((c - np.array(p)) ** 2).sum()) for p in PALETTE]
            m = int(np.argmin(dd))
            if dd[m] < TOL2:
                best.append(m)
        out.append(max(best) if best else None)
    return out


def anchors():
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    return [(k, np.asarray(v['xyz'], float)) for k, v in lms.items()
            if isinstance(v, dict) and v.get('xyz')
            and any(s in k.lower() for s in KEY)
            and not any(s in k.lower() for s in SKIP)]


def calibrate(verbose=True):
    """z de chaque palier, mesure sur nos ancres puis rendu MONOTONE.

    Un palier plus fonce est plus haut par construction de la carte: c'est
    une contrainte, pas une observation. On l'impose donc (regression
    isotone au pas simple) au lieu de laisser le bruit de 15 points la
    violer. Les paliers sans ancre sont interpoles."""
    anc = anchors()
    lv = sample_levels([(p[0], p[1]) for _, p in anc])
    by = collections.defaultdict(list)
    for (k, p), l in zip(anc, lv):
        if l is not None:
            by[l].append(float(p[2]))
    z = [None] * len(PALETTE)
    for l, zs in by.items():
        z[l] = float(np.median(zs))
    # interpolation des paliers vides, puis monotonie
    known = [l for l in range(len(PALETTE)) if z[l] is not None]
    if not known:
        raise SystemExit('aucune ancre de relief: calibration impossible')
    for l in range(len(PALETTE)):
        if z[l] is None:
            z[l] = float(np.interp(l, known, [z[k] for k in known]))
    for l in range(1, len(PALETTE)):
        z[l] = max(z[l], z[l - 1] + 1.0)
    if verbose:
        print('calibration des paliers (nos ancres cotent la carte):')
        for l in range(len(PALETTE)):
            n = len(by.get(l, []))
            print(f'  palier {l} {str(PALETTE[l]):18s} z = {z[l]:6.1f} m   '
                  f'({n} ancre(s))' + ('' if n else '   [interpole]'))
    return z, by


def rings(lv, level, scale, xmin, ymax, min_area_m2=20000.0):
    """Contours fermes du domaine 'palier >= level', en coordonnees monde."""
    import cv2
    m = (lv >= level).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cs:
        if cv2.contourArea(c) / (scale * scale) < min_area_m2:
            continue
        c = cv2.approxPolyDP(c, 4.0, True).reshape(-1, 2)
        if len(c) < 4:
            continue
        w = np.stack([xmin + c[:, 0] / scale, ymax - c[:, 1] / scale], axis=1)
        out.append(w)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--calibrate', action='store_true',
                    help='affiche seulement la cote des paliers')
    ap.add_argument('--massif', help="nom d'un massif (fenetre auto sur ses ancres)")
    ap.add_argument('--bbox', help='xmin,xmax,ymin,ymax en metres monde')
    ap.add_argument('--pad', type=float, default=900.0)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    z, by = calibrate()
    if args.calibrate:
        return

    if args.bbox:
        xmin, xmax, ymin, ymax = [float(v) for v in args.bbox.split(',')]
        name = args.massif or 'Relief'
    elif args.massif:
        A = np.array([p for k, p in anchors()
                      if args.massif.lower() in k.lower()])
        if not len(A):
            raise SystemExit(f'aucune ancre pour "{args.massif}"')
        xmin, xmax = A[:, 0].min() - args.pad, A[:, 0].max() + args.pad
        ymin, ymax = A[:, 1].min() - args.pad, A[:, 1].max() + args.pad
        name = args.massif
        print(f'\n{args.massif}: {len(A)} ancres, fenetre '
              f'{xmax - xmin:.0f} x {ymax - ymin:.0f} m')
    else:
        raise SystemExit('donner --massif ou --bbox (ou --calibrate)')

    img, got = compose(xmin, xmax, ymin, ymax)
    scale = img.size[0] / (xmax - xmin)
    lv = levels(img)
    print(f'carte: {got} tuiles, {img.size[0]}x{img.size[1]} px '
          f'({scale:.2f} px/m)')

    edges, per_level = [], []
    prev = None
    for l in range(1, len(PALETTE)):
        rs = rings(lv, l, scale, xmin, ymax)
        if not rs:
            continue
        npts = sum(len(r) for r in rs)
        per_level.append((l, len(rs), npts))
        for r in rs:
            for i in range(len(r)):
                a, b = r[i], r[(i + 1) % len(r)]
                edges.append([[float(a[0]), float(a[1]), z[l]],
                              [float(b[0]), float(b[1]), z[l]]])
            # paroi verticale vers le palier precedent: c'est ce qui fait
            # lire le mesh comme un terrain et pas comme des courbes plates
            if prev is not None:
                for p in r[::max(1, len(r) // 24)]:
                    edges.append([[float(p[0]), float(p[1]), z[l - 1]],
                                  [float(p[0]), float(p[1]), z[l]]])
        prev = rs
    if not edges:
        raise SystemExit('aucun palier de relief dans cette fenetre')

    print(f'\n{"palier":8s} {"iles":>5s} {"sommets":>8s}   z')
    for l, nr, npts in per_level:
        print(f'  {l:<6d} {nr:5d} {npts:8d}   {z[l]:6.1f} m')
    print(f'\n{len(edges)} aretes')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    mesh[name] = {'color': COLOR, 'world_edges': edges}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'\nAPPLIED: {name} ({len(edges)} aretes)')


if __name__ == '__main__':
    main()
