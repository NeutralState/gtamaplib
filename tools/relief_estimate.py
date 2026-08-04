#!/usr/bin/env python3
"""relief_estimate.py — la meilleure ESTIMATION possible, sans ancre. [RELIEF-EST-V1]

La demande (Alexandre, 2026-07-31): "le but est egalement d'utiliser les
frames quand on a pas de points triangules pour faire quand meme la
meilleure estimation possible avec le peu qu'on a".

La contrainte qui va avec, apprise a nos depens le meme jour: une estimation
qui va vivre dans landmarks.json redevient une "mesure" trois outils plus
loin. Les quatre ancres de Mount Ambrosia etaient toutes des estimations
deguisees, et c'est pour ca que rien ne se validait — on comparait un modele
a des points qui etaient eux-memes des modeles. Ici, donc: la sortie est un
MESH et une entree de registre, jamais un landmark.

CE QU'ON A REELLEMENT, pour un massif sans aucune ancre:

  1. la SILHOUETTE, mesuree dans une frame par une camera calibree. Elle
     donne une direction exacte par colonne — mais aucune profondeur.
  2. le RELIEF DE LA CARTE communautaire, dessine en paliers de vert
     emboites (carte hypsometrique). Il donne un plan au sol dense en XY —
     mais ses paliers ne sont pas cotes.

Ni l'un ni l'autre ne suffit. Ensemble ils se completent exactement: la
frame apporte la direction, la carte apporte la position au sol.

CE QUI REMPLACE LA PENTE SUPPOSEE. Un rayon de silhouette est TANGENT au
terrain: il rase la surface au point ou il cesse de voir le ciel. On marche
donc le long du rayon et on cherche le premier point ou son altitude passe
sous celle du terrain lu sur la carte. Aucune pente n'est postulee, aucune
distance n'est declaree — la profondeur SORT de la rencontre entre les deux
observations.

LA COTE DES PALIERS vient de nos ancres de relief RESTANTES, ailleurs sur la
carte (Waffles, Easy Hill, Interstate, Starlet...). La palette de la carte
est globale, donc une cote etablie sur des massifs mesures s'applique a un
massif qui ne l'est pas. C'est le seul endroit ou une mesure entre, et elle
n'entre pas par le massif qu'on estime — donc pas de circularite.

CE QUE CA VAUT: une estimation, et elle est etiquetee comme telle. La carte
est une observation communautaire, pas une verite; ses contours sont dessines
a la main. Le resultat est le meilleur compromis disponible, pas une mesure.

Usage:
  PYTHONPATH=. python3 tools/relief_estimate.py --massif 'Mount Ambrosia' \
      --cam 'Ambrosia 01 (Bikers)' [--apply]
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

TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,14', '5')
TILE = 256
MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
REG_PATH = os.path.join(THIS, 'data', 'terrains.json')
# echelle hypsometrique de la carte, du plus clair (plaine) au plus fonce
PALETTE = [(186, 204, 120), (174, 198, 102), (156, 180, 90),
           (150, 168, 84), (132, 156, 72), (120, 144, 66)]
TOL2 = 900
KEY = ('mount', 'hill', 'ridge', 'pass')
SKIP = ('bridge', 'sign', 'billboard', 'road', 'st ', 'tower', 'station')


def compose(xmin, xmax, ymin, ymax):
    lx, ty = xmin + 16384, 16384 - ymax
    rx, by = xmax + 16384, 16384 - ymin
    tx0, tx1 = int(lx // TILE), int(rx // TILE)
    ty0, ty1 = int(ty // TILE), int(by // TILE)
    comp = Image.new('RGB', ((tx1 - tx0 + 1) * TILE, (ty1 - ty0 + 1) * TILE), PALETTE[0])
    got = 0
    for a in range(ty0, ty1 + 1):
        for b in range(tx0, tx1 + 1):
            p = os.path.join(TILES, f'5,{a},{b}.jpg')
            if os.path.exists(p):
                comp.paste(Image.open(p).convert('RGB'),
                           ((b - tx0) * TILE, (a - ty0) * TILE))
                got += 1
    return comp.crop((int(lx - tx0 * TILE), int(ty - ty0 * TILE),
                      int(rx - tx0 * TILE), int(by - ty0 * TILE))), got


def level_map(img, min_area_px=120000):
    """Palier de relief par pixel. Median pour absorber le bruit JPEG, qui
    sinon decoupe un massif en dizaines d'ilots."""
    import cv2
    a = np.asarray(img, np.int16)
    d = np.stack([((a - np.array(p, np.int16)) ** 2).sum(axis=2) for p in PALETTE])
    lv = np.argmin(d, axis=0).astype(np.int16)
    lv[np.min(d, axis=0) > TOL2] = 0
    lv = cv2.medianBlur(lv.astype(np.uint8), 9).astype(np.int16)
    # LES TACHES DE VERT NE SONT PAS TOUTES DU RELIEF. La palette de la carte
    # encode aussi le couvert vegetal: 14 pct de la surface autour de Bikers
    # est en palier 2-3 sous forme de petites taches eparses. Des rayons de
    # silhouette s'y accrochaient a 300 m de la camera, alors que le vrai
    # massif est a 1800 m. On ne garde donc, pour chaque palier eleve, que
    # les regions CONNEXES assez vastes pour etre un massif.
    for l in range(2, len(PALETTE)):
        m = (lv >= l).astype(np.uint8)
        nlab, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
        for c in range(1, nlab):
            if stats[c, cv2.CC_STAT_AREA] < min_area_px:
                lv[lab == c] = min(lv[lab == c].min(), l - 1)
    return lv


def sample_levels(pts):
    out, cache = [], {}
    for x, y in pts:
        px_, py_ = x + 16384, 16384 - y
        tx, tyy = int(px_ // TILE), int(py_ // TILE)
        if (tyy, tx) not in cache:
            p = os.path.join(TILES, f'5,{tyy},{tx}.jpg')
            cache[(tyy, tx)] = (np.asarray(Image.open(p).convert('RGB'), np.int16)
                                if os.path.exists(p) else None)
        im = cache[(tyy, tx)]
        if im is None:
            out.append(None)
            continue
        i, j = int(py_ - tyy * TILE), int(px_ - tx * TILE)
        patch = im[max(0, i - 2):i + 3, max(0, j - 2):j + 3].reshape(-1, 3)
        best = []
        for c in patch:
            dd = [int(((c - np.array(p)) ** 2).sum()) for p in PALETTE]
            k = int(np.argmin(dd))
            if dd[k] < TOL2:
                best.append(k)
        out.append(max(best) if best else None)
    return out


def calibrate(exclude_massif):
    """Cote des paliers, mesuree sur nos ancres de relief RESTANTES — en
    excluant celles du massif qu'on estime, pour qu'aucune circularite ne
    s'installe. Monotonie imposee: un palier plus fonce est plus haut par
    construction de la carte, ce n'est pas une observation a discuter."""
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))

    def is_relief(k):
        return (any(s in k.lower() for s in KEY)
                and not any(s in k.lower() for s in SKIP))

    anc = [(k, np.asarray(v['xyz'], float)) for k, v in lms.items()
           if isinstance(v, dict) and v.get('xyz') and is_relief(k)
           and exclude_massif.lower() not in k.lower()]
    # LA PLAINE NE SE COTE PAS AVEC DES POINTS DE MONTAGNE. Premiere version:
    # le palier 0 heritait de "Mount Waffles (TW)", un point de massif qui
    # tombe dans la plaine a z 80.7 — la plaine se retrouvait a 80 m, le
    # rayon partait sous le sol des le premier pas et la crete sortait a
    # 120 m de la camera. Le sol se cote avec des objets de sol: on prend
    # donc, pour chaque palier, les landmarks NON-relief qui y tombent, et
    # on ne garde les points de massif que pour les paliers eleves ou il n'y
    # a rien d'autre.
    ground = [(k, np.asarray(v['xyz'], float)) for k, v in lms.items()
              if isinstance(v, dict) and v.get('xyz') and not is_relief(k)]
    if len(ground) > 400:
        ground = ground[::max(1, len(ground) // 400)]
    lv = sample_levels([(p[0], p[1]) for _, p in anc])
    lvg = sample_levels([(p[0], p[1]) for _, p in ground])
    by = collections.defaultdict(list)
    byg = collections.defaultdict(list)
    for (k, p), l in zip(anc, lv):
        if l is not None:
            by[l].append(float(p[2]))
    for (k, p), l in zip(ground, lvg):
        if l is not None:
            byg[l].append(float(p[2]))
    # QUI COTE QUOI. Les deux premiers paliers sont de la plaine: ce sont les
    # objets de sol qui les cotent, et a un bas percentile puisqu'un batiment
    # est marque a son toit. Les paliers eleves sont du relief: seules les
    # ancres de massif y ont un sens. Melanger les deux mettait le palier 5 a
    # 197.7 m sur la foi de 24 "objets de sol" qui etaient en realite des
    # sommets de tours, et la crete sortait plate.
    z = [None] * len(PALETTE)
    for l in range(len(PALETTE)):
        if l <= 1 and len(byg.get(l, [])) >= 5:
            z[l] = float(np.percentile(byg[l], 25))
        elif by.get(l):
            z[l] = float(np.median(by[l]))
        elif len(byg.get(l, [])) >= 5:
            z[l] = float(np.percentile(byg[l], 25))
    known = [l for l in range(len(PALETTE)) if z[l] is not None]
    if len(known) < 2:
        raise SystemExit('pas assez d ancres de relief hors du massif pour coter la carte')
    for l in range(len(PALETTE)):
        if z[l] is None:
            z[l] = float(np.interp(l, known, [z[k] for k in known]))
    for l in range(1, len(PALETTE)):
        z[l] = max(z[l], z[l - 1] + 1.0)
    print(f'cote des paliers — {len(ground)} objets de sol, {len(anc)} ancres de '
          f'relief HORS "{exclude_massif}":')
    for l in range(len(PALETTE)):
        ng, nr = len(byg.get(l, [])), len(by.get(l, []))
        src = (f'{ng} objets de sol' if (l <= 1 and ng >= 5) else
               (f'{nr} ancre(s) de relief' if nr else
                (f'{ng} objets de sol' if ng >= 5 else 'interpole')))
        print(f'   palier {l}  z = {z[l]:6.1f} m   ({src})')
    return z


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--massif', required=True)
    ap.add_argument('--cam', required=True)
    ap.add_argument('--bbox', help='xmin,xmax,ymin,ymax (defaut: autour de la cam)')
    ap.add_argument('--reach', type=float, default=6000.0,
                    help='distance max exploree le long des rayons')
    ap.add_argument('--step', type=float, default=15.0)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    import common
    from hill_mesh import extract_skyline
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    cam = common.get_cam(args.cam)
    o = np.asarray(cam.xyz, float)

    z_of = calibrate(args.massif)

    if args.bbox:
        xmin, xmax, ymin, ymax = [float(v) for v in args.bbox.split(',')]
    else:
        xmin, xmax = o[0] - args.reach, o[0] + args.reach
        ymin, ymax = o[1] - args.reach, o[1] + args.reach
    img, got = compose(xmin, xmax, ymin, ymax)
    sc0 = img.size[0] / (xmax - xmin)
    lv = level_map(img, min_area_px=int(120000 * sc0 * sc0))
    sc = img.size[0] / (xmax - xmin)
    print(f'\ncarte: {got} tuiles, {img.size[0]}x{img.size[1]} px ({sc:.2f} px/m)')

    def terrain_z(X, Y):
        j = ((X - xmin) * sc).astype(np.int32)
        i = ((ymax - Y) * sc).astype(np.int32)
        ok = (i >= 0) & (i < lv.shape[0]) & (j >= 0) & (j < lv.shape[1])
        out = np.full(X.shape, z_of[0])
        out[ok] = np.array(z_of)[lv[i[ok], j[ok]]]
        return out

    marks = px[args.cam]
    P = [marks[c] for c in marks
         if c.startswith(args.massif) and marks[c] is not None]
    if len(P) < 2:
        raise SystemExit(f'{args.cam} n a pas assez de clics "{args.massif}"')
    xs = sorted(p[0] for p in P)
    ys = [p[1] for p in sorted(P, key=lambda q: q[0])]

    def prior_y(x):
        return float(np.interp(x, xs, ys))

    gray = np.asarray(Image.open(os.path.join(REPO, 'frames', f'{args.cam}.png'))
                      .convert('L'), np.float32)
    cp = os.path.join(THIS, 'data', 'hill_outline_corrections.json')
    anchors = json.load(open(cp)).get(args.cam, []) if os.path.exists(cp) else []
    exclude = []
    bw = marks.get('Billboard with Diversity Motif (TW)')
    be = marks.get('Billboard with Diversity Motif (TE)')
    if bw and be:
        exclude.append((bw[0] - 40, be[0] + 70))
    cols, sky, meas, manual = extract_skyline(gray, prior_y, 130, gray.shape[1] - 4,
                                              exclude=exclude, anchors=anchors)
    known = meas | manual
    mi = np.where(known)[0]
    cols, sky, known = (cols[mi[0]:mi[-1] + 1], sky[mi[0]:mi[-1] + 1],
                        known[mi[0]:mi[-1] + 1])
    print(f'silhouette {args.cam}: {int(known.sum())} colonnes mesurees '
          f'({len(anchors)} corrections a la main)')

    # TANGENCE. Le rayon de silhouette rase le terrain: on avance jusqu'au
    # premier point ou son altitude passe SOUS celle lue sur la carte.
    ts = np.arange(120.0, args.reach, args.step)
    out, miss = [], 0
    for x, y, k in zip(cols, sky, known):
        if not k:
            continue
        d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
        n = np.linalg.norm(d)
        if n < 1e-9:
            continue
        d /= n
        X, Y = o[0] + ts * d[0], o[1] + ts * d[1]
        Zr = o[2] + ts * d[2]
        Zt = terrain_z(X, Y)
        hit = np.where(Zr <= Zt)[0]
        if not len(hit):
            miss += 1
            continue
        h = int(hit[0])
        out.append((float(X[h]), float(Y[h]), float(Zt[h]), float(ts[h])))
    if not out:
        raise SystemExit('aucun rayon ne rencontre le relief de la carte — '
                         'verifier --bbox ou la cote des paliers')
    A = np.array(out)
    print(f'\ncrete estimee: {len(A)} points, distance {A[:, 3].min():.0f}-'
          f'{A[:, 3].max():.0f} m (mediane {np.median(A[:, 3]):.0f}), '
          f'z {A[:, 2].min():.0f} a {A[:, 2].max():.0f} m')
    if miss:
        print(f'  {miss} colonnes sans rencontre (rayon au-dessus de tout '
              f'le relief de la fenetre)')
    print('\n  ESTIMATION, pas une mesure: direction mesuree (camera calibree), '
          'position au sol\n  lue sur la carte communautaire, altitude des '
          'paliers cotee sur des ancres\n  d autres massifs. Aucune ancre de '
          f'"{args.massif}" n intervient — il n en existe aucune.')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    edges = [[[A[i, 0], A[i, 1], A[i, 2]], [A[i + 1, 0], A[i + 1, 1], A[i + 1, 2]]]
             for i in range(len(A) - 1)
             if abs(A[i + 1, 3] - A[i, 3]) < 400.0]
    name = f'{args.massif} (estimation)'
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    mesh[name] = {'color': '#fbbf24', 'world_edges': edges}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    reg = json.load(open(REG_PATH))
    reg.setdefault(args.massif, {}).update({
        'estimation': {
            'tool': 'relief_estimate.py [RELIEF-EST-V1]',
            'camera': args.cam,
            'points': len(A),
            'distance_m': [round(float(A[:, 3].min())), round(float(A[:, 3].max()))],
            'z_m': [round(float(A[:, 2].min())), round(float(A[:, 2].max()))],
            'sources': ['silhouette mesuree (camera calibree + corrections main)',
                        'plan au sol: paliers de la carte communautaire',
                        'altitude des paliers: ancres de relief d AUTRES massifs'],
            'nature': 'ESTIMATION — ne jamais reinjecter dans landmarks.json',
        }})
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(REG_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(reg, f, indent=1, ensure_ascii=True)
    os.replace(tmp, REG_PATH)
    print(f'\nAPPLIED: "{name}" ({len(edges)} segments) + registre terrains.json')


if __name__ == '__main__':
    main()
