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


def rlx_curtain(only, A, max_rms=80.0):
    """La crete de rlx comme BASE de profondeur, RECALEE sur nos ancres.

    Ce que son mesh apporte et qu'un plan ne peut pas: le TRACE AU SOL de la
    crete — courbe, pas droit. Ce qu'il n'apporte pas: l'echelle. Ses
    distances sont declarees a l'oeil depuis UNE camera (chiffres ronds:
    4400, 4450, 4300...), donc son erreur est RADIALE depuis ce point. On
    ajuste donc une similitude a 3 parametres — facteur radial k autour de
    SA camera + translation — sur nos ancres triangulees.

    Mesure de confiance: le rms final. Si nos ancres ne se posent pas sur sa
    polyligne apres recalage, sa crete n'est pas la meme chose que la notre
    (points d'identites differentes) et on REFUSE sa base au lieu de la
    subir — c'est le cas de Mount Waffles, ou nos "Waffles Ridge (C)" et
    "(TW)" sont a z 81 quand le sommet est a z 197.
    """
    rp = os.path.join(THIS, 'data', 'rlx_mountains_meshes.json')
    if not os.path.exists(rp):
        return None
    R = json.load(open(rp))
    key = next((k for k in R if k.replace('[rlx] ', '') == only), None)
    if key is None:
        print(f'  base rlx: aucun mesh pour "{only}"')
        return None
    ent = R[key]
    C = np.array(ent.get('crest') or [], float)
    if len(C) < 2:
        return None
    O = np.array(ent.get('camera_xy') or C[:, :2].mean(axis=0), float)

    def place(par):
        k, tx, ty = par
        P = C.copy()
        P[:, :2] = O + k * (C[:, :2] - O) + np.array([tx, ty])
        return P

    def cost(par):
        P = place(par)
        return sum(min(seg_dist(p, P[i, :2], P[i + 1, :2])
                       for i in range(len(P) - 1)) ** 2 for p in A[:, :2])

    par = np.array([1.0, 0.0, 0.0])
    step = np.array([0.10, 200.0, 200.0])
    while step[1] > 0.5:
        best, moved = cost(par), False
        for i in range(3):
            for sg in (1, -1):
                q = par.copy()
                q[i] += sg * step[i]
                if q[0] < 0.5 or q[0] > 2.0:
                    continue
                v = cost(q)
                if v < best - 1e-6:
                    best, par, moved = v, q, True
        if not moved:
            step = step * 0.5
    rms = math.sqrt(cost(par) / len(A))
    r0 = math.sqrt(cost(np.array([1.0, 0.0, 0.0])) / len(A))
    verdict = 'ACCEPTEE' if rms <= max_rms else 'REFUSEE'
    print(f'  base rlx "{key}" ({len(C)} pts, cam {ent.get("camera")}): '
          f'echelle x{par[0]:.3f}, translation {math.hypot(par[1], par[2]):.0f} m '
          f'-> rms sur nos {len(A)} ancres {r0:.0f} -> {rms:.0f} m  [{verdict}]')
    if rms > max_rms:
        print('    (ses points de crete ne sont pas les notres — on retombe '
              'sur nos seules ancres)')
        return None
    return place(par)


def seg_dist(p, a, b):
    ab = b - a
    L = float(ab @ ab)
    u = 0.0 if L < 1e-9 else max(0.0, min(1.0, float((p - a) @ ab) / L))
    return float(np.linalg.norm(p - (a + u * ab)))


def curtain_hit(o, d, poly):
    """Intersection du rayon avec le RIDEAU vertical porte par la polyligne.
    Les segments d'extremite sont prolonges a l'infini (la crete continue
    au-dela de ce que rlx a modelise)."""
    best = None
    for i in range(len(poly) - 1):
        a, b = poly[i, :2], poly[i + 1, :2]
        e = b - a
        den = d[0] * (-e[1]) + d[1] * e[0]
        if abs(den) < 1e-9:
            continue
        w = a - o[:2]
        t = (w[0] * (-e[1]) + w[1] * e[0]) / den
        u = (d[0] * w[1] - d[1] * w[0]) / den
        lo = -6.0 if i == 0 else 0.0
        hi = 7.0 if i == len(poly) - 2 else 1.0
        if t > 1.0 and lo <= u <= hi and (best is None or t < best):
            best = t
    return None if best is None else o + best * d


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
    curtain = rlx_curtain(args.only, A) if args.base_rlx else None
    if curtain is not None:
        n, kind, rms = None, 'RIDEAU rlx recale sur nos ancres', float('nan')
    elif n is None:
        # PLAN VERTICAL: la normale est horizontale, perpendiculaire a la
        # direction de la crete (SVD sur nos seules ancres).
        u_, s_, vt2 = np.linalg.svd(A[:, :2] - ctr[:2])
        ax = vt2[0]
        n = np.array([-ax[1], ax[0], 0.0])
        n /= np.linalg.norm(n)
        rms = float(np.sqrt(np.mean(((A - ctr) @ n) ** 2)))
        kind = 'plan VERTICAL (hypothese crete)'
    nd = '' if n is None else (f', normale ({n[0]:+.2f},{n[1]:+.2f},{n[2]:+.2f}), '
                               f'rms {rms:.1f} m')
    print(f'silhouette {args.silhouette}: {len(anc)} ancres "{fam}", {kind}{nd}')
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
    # OCCLUDERS: un poteau, un panneau ou un arbre devant la crete fait
    # decrocher UNE poignee de colonnes de plusieurs dizaines de pixels,
    # alors qu'une crete reelle varie doucement. On rejette donc les
    # colonnes qui s'ecartent trop d'une mediane glissante LARGE et on
    # interpole a travers — un lissage seul ne fait qu'etaler l'encoche.
    for _ in range(3):
        base = np.array([np.median(ys2[max(0, i - 12):i + 13])
                         for i in range(len(ys2))])
        r = ys2 - base
        bad = np.abs(r) > max(6.0, 2.5 * float(np.median(np.abs(r)) + 1e-6))
        if not bad.any() or bad.all():
            break
        idx = np.arange(len(ys2))
        ys2 = np.interp(idx, idx[~bad], ys2[~bad])
    n_bad = 0 if 'bad' not in dir() else int(bad.sum())
    ys2 = np.array([np.median(ys2[max(0, i - 3):i + 4]) for i in range(len(ys2))])
    print(f'  silhouette: {len(ys2)} colonnes, {n_bad} rejetees (occluders)')
    P = []
    for (x, _), y in zip(crest, ys2):
        d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
        d /= np.linalg.norm(d)
        if curtain is not None:
            q = curtain_hit(o, d, curtain)
            if q is not None:
                P.append(q)
            continue
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
    ap.add_argument('--base-rlx', action='store_true',
                    help="prend l'ORIENTATION de crete du mesh de rlx comme base "
                         "(tools/data/rlx_mountains_meshes.json) — sa geometrie sert "
                         "de point de depart, la POSITION reste la notre (ancres "
                         "triangulees) et la FORME reste la notre (silhouette)")
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
