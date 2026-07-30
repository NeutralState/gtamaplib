#!/usr/bin/env python3
"""mountain_mesh.py — tous les massifs, bâtis sur leurs points MESURES. [MTN-MESH-V1]

Generalisation du chantier Ambrosia Hill / Canyon a l'ensemble du relief.

Constat qui dicte la methode: la plupart des massifs ne sont vus que par des
frames de leak en 1080p, ou la crete est un fond brumeux occlus par des
batiments, des arbres et des poteaux — une extraction de silhouette y serait
du bruit deguise en mesure. En revanche beaucoup ont deja des points
TRIANGULES (2 cams ou plus, gates du profil 'mountain'). Ces points sont la
donnee: on batit sur eux, pas sur une devinette.

Modele par massif:
  * CRETE  = les landmarks positionnes du massif, ordonnes le long de leur
             axe principal (ACP), relies en polyligne
  * VOLUME = chaque point de crete descend a --slope deg jusqu'a --base,
             des deux cotes perpendiculairement a la crete
  * ECHELLE: aucune. Tout vient des triangulations existantes.

Sortie: un mesh par massif + un tableau de ce qui est modelisable et de ce
qui manque (combien de points, quelle etendue, quelle hauteur).

Usage: PYTHONPATH=. python3 tools/mountain_mesh.py [--apply] [--slope 30]
       [--only 'Mount Waffles']
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

MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
KEY = ('mount', 'hill', 'ridge', 'pass', 'massif')
SKIP = ('bridge', 'sign', 'billboard', 'arrow', 'road', 'tree')
COLOR = '#4ade80'


def massif_of(name):
    """Nom du massif d'un landmark ('Mount Waffles (TW)' -> 'Mount Waffles').
    Les suffixes de crete sont des lettres/chiffres entre parentheses."""
    low = name.lower()
    if not any(k in low for k in KEY) or any(s in low for s in SKIP):
        return None
    base = name.split(' (')[0]
    # 'Waffles Ridge' et 'Mount Waffles' sont deux epaules du meme massif,
    # mais on les garde distincts: leurs points ne sont pas interchangeables
    return base


def densify(args):
    """Crete dense: silhouette DP dans la frame, profondeur = intersection
    du rayon avec le PLAN ajuste sur les points triangules du massif."""
    import common
    from PIL import Image
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    cam = common.get_cam(args.silhouette)
    o = np.asarray(cam.xyz, float)
    marks = px[args.silhouette]
    fam = args.family or args.only
    anc = [(p, np.asarray(lms[lm]['xyz'], float)) for lm, p in marks.items()
           if fam.lower() in lm.lower() and massif_of(lm) and
           isinstance(lms.get(lm), dict) and lms[lm].get('xyz')]
    if len(anc) < 2:
        print(f'silhouette: {len(anc)} ancre(s) dans {args.silhouette} pour '
              f'"{fam}" — il en faut 2')
        return None
    A = np.array([q for _, q in anc])
    ctr = A.mean(axis=0)
    if len(anc) >= 3:
        _, sv_, vt = np.linalg.svd(A - ctr)
        n = vt[2]
        rms = float(np.sqrt(np.mean(((A - ctr) @ n) ** 2)))
        kind = 'plan ajuste (SVD)'
        # un plan quasi horizontal ne peut pas porter une crete: on
        # bascule sur le plan vertical
        if abs(n[2]) > 0.8:
            n = None
    else:
        n = None
    if n is None:
        # PLAN VERTICAL passant par les ancres: la normale est horizontale,
        # perpendiculaire a la direction de la crete. Hypothese honnete pour
        # une crete vue de loin, et elle ne demande que 2 points.
        u_, s_, vt2 = np.linalg.svd(A[:, :2] - ctr[:2])
        ax = vt2[0]
        n = np.array([-ax[1], ax[0], 0.0])
        n /= np.linalg.norm(n)
        rms = float(np.sqrt(np.mean(((A - ctr) @ n) ** 2)))
        kind = 'plan VERTICAL (hypothese crete)'
    print(f'silhouette {args.silhouette}: {len(anc)} ancres "{fam}", {kind}, '
          f'normale ({n[0]:+.2f},{n[1]:+.2f},{n[2]:+.2f}), rms {rms:.1f} m')
    if args.xrange:
        x0, x1 = [int(v) for v in args.xrange.split(',')]
    else:
        xs = [p[0] for p, _ in anc]
        x0, x1 = int(min(xs)) - 40, int(max(xs)) + 40
    ys = [p[1] for p, _ in anc]
    prior = float(np.median(ys))
    im = Image.open(os.path.join(REPO, 'frames', f'{args.silhouette}.png')).convert('RGB')
    a_ = np.asarray(im, np.float32)
    L = a_.mean(axis=2)
    blue = a_[:, :, 2] - a_[:, :, 0]          # ciel = bleu domine
    H, W = L.shape
    x0, x1 = max(2, x0), min(W - 2, x1)
    band = 150
    crest = []
    for x in range(x0, x1, 3):
        lo = max(2, int(prior - band)); hi = min(H - 3, int(prior + band))
        col_b = blue[lo:hi, x]
        # bord ciel->terrain: dernier pixel bleu en descendant
        idx = np.where(col_b > 6.0)[0]
        if len(idx) < 5:
            continue
        y = lo + int(idx.max())
        crest.append((x, y))
    if len(crest) < 20:
        print('silhouette: pas assez de colonnes'); return None
    ys2 = np.array([c[1] for c in crest], float)
    ys2 = np.array([np.median(ys2[max(0, i - 3):i + 4]) for i in range(len(ys2))])
    P = []
    for (x, _), y in zip(crest, ys2):
        d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
        d /= np.linalg.norm(d)
        den = float(np.dot(d, n))
        if abs(den) < 1e-6:
            continue
        t = float(np.dot(ctr - o, n)) / den
        if t > 0:
            P.append(o + t * d)
    P = np.array(P)
    # le pied du massif ne descend pas sous ses ancres: les colonnes de bord
    # de la silhouette sortent de la zone ancree et plongent sous l'horizon
    zmin = float(A[:, 2].min()) - 20.0
    keep = P[:, 2] > zmin
    if keep.sum() >= 20:
        P = P[keep]
    dd = np.hypot(P[:, 0] - o[0], P[:, 1] - o[1])
    print(f'  -> crete densifiee: {len(P)} points, distance {dd.min():.0f}-{dd.max():.0f} m, '
          f'z {P[:, 2].min():.0f}-{P[:, 2].max():.0f} m')
    return P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slope', type=float, default=30.0,
                    help='pente des flancs (deg) — SEULE hypothese du modele')
    ap.add_argument('--base', type=float, default=None,
                    help='z du pied (defaut: z min des points - 5 m)')
    ap.add_argument('--min-pts', type=int, default=2)
    ap.add_argument('--only')
    ap.add_argument('--silhouette', metavar='CAM',
                    help='densifie la crete du massif par sa SILHOUETTE dans '
                         'cette frame; la profondeur vient du plan ajuste sur '
                         'ses points triangules (aucune echelle inventee)')
    ap.add_argument('--xrange', help='x0,x1 dans la frame (defaut: emprise des marks)')
    ap.add_argument('--family', help='prefixe des ancres (defaut: le massif); '
                                     "ex 'Waffles' regroupe Mount Waffles ET Waffles Ridge")
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    groups = collections.defaultdict(list)
    for lm, e in lms.items():
        if not (isinstance(e, dict) and e.get('xyz')):
            continue
        b = massif_of(lm)
        if b:
            groups[b].append((lm, np.asarray(e['xyz'], float),
                              float(e.get('error_m') or 0)))

    out = {}
    ok, thin = [], []
    sil = None
    if args.silhouette:
        sil = densify(args)
    for base, pts in sorted(groups.items()):
        if args.only and base != args.only:
            continue
        if len(pts) < args.min_pts:
            thin.append((base, len(pts)))
            continue
        P = np.array([p for _, p, _ in pts])
        if sil is not None and args.only == base:
            P = sil
        # ordre le long de l'axe principal de la crete (ACP horizontale)
        c = P[:, :2].mean(axis=0)
        u, s, vt = np.linalg.svd(P[:, :2] - c)
        axis = vt[0]
        t = (P[:, :2] - c) @ axis
        order = np.argsort(t)
        P = P[order]
        names = ([pts[i][0] for i in order] if len(pts) == len(order)
                 else [f'silhouette x{len(order)}'])
        span = float(t.max() - t.min())
        anchor_z = min((p[2] for _, p, _ in pts), default=P[:, 2].min())
        base_z = (args.base if args.base is not None
                  else float(min(anchor_z, P[:, 2].min()) - 5.0))
        h = float(P[:, 2].max() - base_z)
        run = 1.0 / math.tan(math.radians(args.slope))
        # normale horizontale a la crete
        nrm = np.array([-axis[1], axis[0]])
        edges = []
        for i in range(len(P) - 1):
            edges.append([list(map(float, P[i])), list(map(float, P[i + 1]))])
        for i in range(len(P)):
            hh = max(0.0, P[i][2] - base_z)
            for sgn in (+1.0, -1.0):
                q = P[i][:2] + sgn * nrm * hh * run
                edges.append([list(map(float, P[i])),
                              [float(q[0]), float(q[1]), base_z]])
        # ligne de pied des deux cotes
        for sgn in (+1.0, -1.0):
            foot = [[float(P[i][0] + sgn * nrm[0] * max(0.0, P[i][2] - base_z) * run),
                     float(P[i][1] + sgn * nrm[1] * max(0.0, P[i][2] - base_z) * run),
                     base_z] for i in range(len(P))]
            for i in range(len(foot) - 1):
                edges.append([foot[i], foot[i + 1]])
        out[base] = {'color': COLOR, 'world_edges': edges}
        ok.append((base, len(P), span, base_z, float(P[:, 2].max()), h, names))

    print(f'{"massif":26s} {"pts":>4s} {"etendue":>9s} {"z pied":>8s} {"z crete":>9s} {"hauteur":>8s}')
    for base, n, span, bz, tz, h, names in sorted(ok, key=lambda r: -r[1]):
        print(f'{base[:26]:26s} {n:4d} {span:8.0f}m {bz:7.0f}m {tz:8.0f}m {h:7.0f}m')
        print(f'{"":26s}      {", ".join(x.split("(")[-1].rstrip(")") if "(" in x else "centre" for x in names)}')
    if thin:
        print(f'\n{len(thin)} massifs a moins de {args.min_pts} points positionnes '
              f'(non modelisables en l etat):')
        print('   ' + ', '.join(f'{b} ({n})' for b, n in sorted(thin))[:400])

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    for k in list(mesh):
        if k in out:
            mesh.pop(k)
    mesh.update(out)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'\nAPPLIED: {len(out)} massifs -> {list(out)}')


if __name__ == '__main__':
    main()
