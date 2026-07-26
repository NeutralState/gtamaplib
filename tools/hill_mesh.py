#!/usr/bin/env python3
"""hill_mesh.py — Ambrosia Hill en 3D, depuis sa silhouette. [HILL-3D-V1]

Meme idee que les eventails de rlx (silhouette de Bikers extrudee a
plusieurs profondeurs), mais en mieux sur trois points:

  1. SILHOUETTE VRAIE: extraite de la frame au subpixel (gradient de
     luminance dans un corridor autour des clics BW/TW/TE/BE), robuste aux
     occluders (billboard, palmiers, poteaux = gradients durs rejetes;
     l'arete colline/ciel est DOUCE a cause de la brume). ~600 points au
     lieu de 4.
  2. PROFONDEURS PHYSIQUES, pas arbitraires: la degenerescence mono-cam est
     z_crete = z_cam + d*tan(elev). On ne peut pas la lever, mais on peut
     la GRADUER avec les seules altitudes absolues de collines du monde:
     Mount Waffles 197 m, Mount Mountain 241 m (tous deux triangules).
     Argument massif: le clic BW (elev +5.10 deg) au bord gauche du cadre
     prolonge presque exactement le sommet de Mount Mountain (5.7 deg a
     2216 m, bearing 323 = 3.5 deg hors-cadre): la silhouette COULE dans
     le massif de Mount Mountain -> l'hypothese continue est d ~ 2.2 km.
  3. CHAQUE HYPOTHESE EST NOMMEE par ce qu'elle implique: Waffles-class
     (197 m), Mountain-class (241 m), massif continu (~350 m), et
     Kalaga-class a la distance ou rlx place la cam helico (5988 m ->
     ~900 m, du Chiliad). Un seul clic de cette crete depuis une 2e cam
     posee effondre d — le jour ou on l'a, ce fichier se re-genere.

Usage: PYTHONPATH=. python3 tools/hill_mesh.py [--depths 1157,2216,5988]
       [--apply] [--check]  (--check: reprojette la crete dans Bikers)
"""
import argparse
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
import common

CAM = 'Ambrosia 01 (Bikers)'
MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')

CLICKS = ['Ambrosia Hill (BW)', 'Ambrosia Hill (TW)',
          'Ambrosia Hill (TE)', 'Ambrosia Hill (BE)']
Z_BASE = 18.87                # plaine d'Ambrosia (datum Main St, GROUND-V1)
CORRIDOR = 90                 # demi-fenetre de recherche autour du prior (px)
HARD_EDGE = 26.0              # gradient au-dela = occluder (arete dure), rejet
MIN_EDGE = 1.2                # gradient en-deca = pas de bord trouvable
DEV_MAX = 28.0                # ecart max a la mediane locale (px)
COL_STEP = 4                  # une colonne sur 4

# (etiquette, profondeur m, couleur) — profondeurs par defaut, cf. --depths
HYPS = [
    ('Waffles-class 197m',  1157, '#fbbf24'),
    ('massif Mt Mountain',  2216, '#4ade80'),
    ('Kalaga-class (rlx)',  5988, '#a78bfa'),
]


def extract_skyline(gray, prior_y, x0, x1, exclude=()):
    """Bord ciel/colline par colonne: max du gradient vertical descendant
    (ciel clair au-dessus, colline sombre dessous), dans le corridor.
    Rejette les aretes DURES (occluders), les deviations locales et les
    bandes x exclues (occluders connus, ex: billboard clique)."""
    h, w = gray.shape
    sm = np.zeros_like(gray)
    # lissage vertical leger (le bord brume est large)
    sm[2:-2] = (gray[:-4] + gray[1:-3] + gray[2:-2] + gray[3:-1] + gray[4:]) / 5.0
    cols, raw = [], []
    for x in range(x0, x1, COL_STEP):
        if any(a <= x <= b for a, b in exclude):
            continue
        yc = prior_y(x)
        a = max(3, int(yc - CORRIDOR))
        b = min(h - 3, int(yc + CORRIDOR))
        col = sm[a:b, x]
        g = col[:-3] - col[3:]            # >0 quand ca s'assombrit vers le bas
        if not len(g):
            continue
        i = int(np.argmax(g))
        if g[i] < MIN_EDGE or g[i] > HARD_EDGE:
            continue                       # invisible ou occluder
        cols.append(x)
        raw.append(a + i + 1.5)
    cols = np.array(cols, float)
    raw = np.array(raw, float)
    # rejet des deviations vs mediane glissante, puis lissage
    keep = np.ones(len(cols), bool)
    for k in range(len(cols)):
        lo, hi = max(0, k - 8), min(len(cols), k + 9)
        if abs(raw[k] - np.median(raw[lo:hi])) > DEV_MAX:
            keep[k] = False
    cols, ys = cols[keep], raw[keep]
    smooth = np.array([np.median(ys[max(0, k - 4):k + 5]) for k in range(len(ys))])
    return cols, smooth


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--depths', default=None,
                    help='profondeurs m, separees par des virgules')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    marks = px[CAM]
    cam = common.get_cam(CAM)
    o = np.asarray(cam.xyz, float)
    im = Image.open(os.path.join(REPO, 'frames', f'{CAM}.png')).convert('L')
    gray = np.asarray(im, np.float32)

    # prior: polyline BW -> TW -> TE -> BE
    P = [marks[c] for c in CLICKS]
    xs = [p[0] for p in P]
    ys = [p[1] for p in P]
    prior_y = lambda x: float(np.interp(x, xs, ys))
    # occluders connus: le billboard Diversity couvre le corridor TW-TE
    exclude = []
    bb_w = marks.get('Billboard with Diversity Motif (TW)')
    bb_e = marks.get('Billboard with Diversity Motif (TE)')
    if bb_w and bb_e:
        exclude.append((bb_w[0] - 40, bb_e[0] + 70))     # +70: poteau du panneau
    cols, sky = extract_skyline(gray, prior_y, int(xs[0]), int(xs[-1]),
                                exclude=exclude)
    # les 4 clics humains sont des points de confiance: on les insere
    cols = np.concatenate([cols, [float(x) for x in xs]])
    sky = np.concatenate([sky, [float(y) for y in ys]])
    order = np.argsort(cols)
    cols, sky = cols[order], sky[order]
    print(f'silhouette: {len(cols)} points entre x={xs[0]} et x={xs[-1]} '
          f'(extraction + 4 clics; bande billboard exclue {exclude})')

    # rayons + geometrie de la degenerescence
    rays = []
    for x, y in zip(cols, sky):
        d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
        rays.append(d / np.linalg.norm(d))
    rays = np.array(rays)
    elev = np.degrees(np.arcsin(rays[:, 2]))
    bear = np.degrees(np.arctan2(rays[:, 0], rays[:, 1])) % 360
    print(f'bearings {bear.min():.1f} -> {bear.max():.1f}, '
          f'elevation crete max {elev.max():.2f} deg')
    print(f'degenerescence mono-cam: z_crete = {o[2]:.1f} + d * tan(elev) '
          f'= {o[2]:.1f} + {math.tan(math.radians(elev.max())):.4f} * d\n')

    hyps = HYPS
    if args.depths:
        hyps = [(f'd={v}m', float(v), c) for v, (_, _, c) in
                zip(args.depths.split(','), HYPS + HYPS)]

    # table des hypotheses
    print(f'{"hypothese":24s} {"d (m)":>7s} {"z crete (m)":>12s}  lecture')
    for lab, d, _ in hyps:
        zc = o[2] + d * math.tan(math.radians(float(elev.max())))
        note = ('~ Mount Waffles (197, triangule)' if abs(zc - 197) < 40 else
                '~ Mount Mountain (241, triangule)' if abs(zc - 241) < 40 else
                'continuite du massif Mt Mountain' if 300 < zc < 420 else
                'Chiliad-class, massif Kalaga' if zc > 700 else '')
        print(f'{lab:24s} {d:7.0f} {zc:12.1f}  {note}')

    out = {}
    for lab, d, col in hyps:
        # plan vertical perpendiculaire au bearing moyen, a distance d
        b0 = math.radians(float(np.median(bear)))
        n = np.array([math.sin(b0), math.cos(b0)])          # normale horizontale
        pts = []
        for r in rays:
            t = d / (r[0] * n[0] + r[1] * n[1])
            if t <= 0:
                continue
            pts.append(o + t * r)
        pts = np.array(pts)
        edges = []
        for i in range(len(pts) - 1):                        # crete
            edges.append([list(pts[i]), list(pts[i + 1])])
        for i in range(0, len(pts), 6):                      # nervures
            edges.append([list(pts[i]), [pts[i][0], pts[i][1], Z_BASE]])
        base = [[p[0], p[1], Z_BASE] for p in pts]
        for i in range(0, len(base) - 6, 6):                 # ligne de base
            edges.append([base[i], base[i + 6]])
        name = f'Ambrosia Hill [{lab}]'
        out[name] = {'color': col, 'world_edges': edges}
        print(f'  {name}: {len(edges)} aretes, crete z '
              f'{pts[:, 2].min():.0f}-{pts[:, 2].max():.0f} m')

    if args.check:
        # la crete re-projetee doit epouser la silhouette extraite (par
        # construction) — verifie l'aller-retour projection
        worst = 0.0
        lab, d, _ = hyps[0]
        b0 = math.radians(float(np.median(bear)))
        n = np.array([math.sin(b0), math.cos(b0)])
        for (x, y, r) in zip(cols, sky, rays):
            t = d / (r[0] * n[0] + r[1] * n[1])
            pr = cam.get_pixel([float(v) for v in (o + t * r)])
            if pr is not None:
                worst = max(worst, math.hypot(pr[0] - x, pr[1] - y))
        print(f'\ncheck aller-retour ({lab}): pire ecart {worst:.2f} px')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire dans building_meshes_procedural.json).')
        return
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    stale = [k for k in mesh if k.startswith('Ambrosia Hill [')]
    for k in stale:
        mesh.pop(k)                       # re-generation: on remplace les notres
    mesh.update(out)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=False)
    os.replace(tmp, MESH_PATH)
    print(f'\nAPPLIED: {list(out)} ({len(stale)} anciens remplaces)')


if __name__ == '__main__':
    main()
