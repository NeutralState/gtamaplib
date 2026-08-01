#!/usr/bin/env python3
"""silhouette_hull.py — profondeur bornee par les SILHOUETTES seules. [SILHULL-V1]

La consigne (Alexandre, 2026-07-31): "je veux juste qu'on se base sur les
silhouettes et sur les calibrations de nos cams". Rien d'autre — pas la carte
communautaire (perimee dans cette zone, elle est justement en cours de
refonte), pas les distances declarees de rlx, pas les ancres du massif (elles
n'existent pas: l'audit epipolaire a montre qu'aucune des quatre n'etait une
triangulation valide).

CE QUE CETTE CONSIGNE PERMET, et que je n'avais pas exploite. Avec une seule
silhouette on n'a qu'un cone de rayons: aucune profondeur. Mais une DEUXIEME
silhouette, meme sans aucun point commun identifiable, contraint quand meme —
par ce qu'elle montre de CIEL.

Le raisonnement tient en une phrase: un point de la crete avance le long de
son rayon en MONTANT; projete dans une autre camera, s'il tombe dans le CIEL,
il est impossible — cette camera verrait du terrain a cet endroit. Chaque
autre silhouette pose donc une BORNE SUPERIEURE sur la profondeur, et la plus
serree gagne.

C'est le hull visuel (shape-from-silhouette) ramene au seul rayon de crete.
Deux proprietes qui comptent ici:

  * AUCUNE CORRESPONDANCE n'est demandee. On ne cherche pas le meme point
    dans deux images — ce qui est heureux, puisque c'est precisement ce qui
    a echoue partout ailleurs sur ce massif.
  * LES OCCLUDERS SONT CONSERVATEURS. Un poteau ou un panneau devant la
    crete d'une camera temoin fait DESCENDRE sa ligne de ciel, donc relache
    sa borne. On sous-contraint, jamais l'inverse.

CE QUE CA DONNE: un intervalle [proche, borne] par colonne, pas un point. La
borne est la surface du hull visuel — la profondeur MAXIMALE compatible avec
tout ce qu'on voit. Le massif est a cette distance ou plus pres, jamais plus
loin. C'est une borne mesuree, pas un parametre declare, et c'est la premiere
chose de la journee sur ce massif qui ne repose que sur nos propres donnees.

Usage:
  PYTHONPATH=. python3 tools/silhouette_hull.py --cam 'Ambrosia 01 (Bikers)' \
      --massif 'Mount Ambrosia' [--apply]
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

MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')


def posed(e):
    return bool(e.get('xyz') and e.get('ypr') and any(e['ypr'])
                and e.get('fov') and (e['fov'][0] or e['fov'][1]))


def sky_line(cam_name):
    """Ligne de ciel par COLONNE d'image: la bande de ciel connexe au bord
    superieur. Retourne un tableau de longueur W (nan la ou le haut de la
    colonne n'est pas du ciel, donc la ou la camera ne dit rien)."""
    p = os.path.join(REPO, 'frames', f'{cam_name}.png')
    if not os.path.exists(p):
        return None
    a = np.asarray(Image.open(p).convert('RGB'), np.int16)
    # Uniquement la DOMINANCE BLEUE. Le critere "tres clair" attrapait des
    # facades, des routes surexposees et des ecrans de HUD: avec un ET sur
    # 161 temoins, un seul faux ciel suffisait a tout rejeter.
    sky = (a[:, :, 2] - a[:, :, 0]) > 8
    H, W = sky.shape
    out = np.full(W, np.nan)
    for x in range(W):
        col = sky[:, x]
        if not col[0]:
            continue
        run = int(np.argmin(col)) if (~col).any() else H
        if 2 <= run - 1 < H - 3:
            out[x] = float(run - 1)
    return out


def in_sky(cam, prof, P):
    """Le point P tombe-t-il dans le CIEL de cette camera ? None si elle ne
    dit rien (hors champ, ou colonne sans ligne de ciel lisible)."""
    q = cam.get_pixel([float(v) for v in P])
    if q is None:
        return None
    x = int(round(q[0]))
    if not (0 <= x < len(prof)) or math.isnan(prof[x]):
        return None
    if not (0 <= q[1] < cam.h):
        return None
    # au-dessus de la ligne de ciel (y plus petit) = dans le ciel
    return q[1] < prof[x] - 2.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cam', required=True, help='vue dont on prend la crete')
    ap.add_argument('--massif', required=True)
    ap.add_argument('--near', type=float, default=200.0)
    ap.add_argument('--far', type=float, default=9000.0)
    ap.add_argument('--witnesses', help='liste explicite separee par ";"')
    ap.add_argument('--min-votes', type=int, default=2,
                    help='nombre de temoins qui doivent voir du CIEL pour '
                         'ecarter une profondeur')
    ap.add_argument('--max-base', type=float, default=8000.0,
                    help='distance max entre la vue et un temoin')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    import common
    from hill_mesh import extract_skyline
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    cam = common.get_cam(args.cam)
    o = np.asarray(cam.xyz, float)

    marks = px[args.cam]
    P = [(k, marks[k]) for k in marks
         if k.startswith(args.massif) and marks[k] is not None]
    if len(P) < 2:
        raise SystemExit(f'{args.cam}: moins de 2 clics "{args.massif}"')
    P.sort(key=lambda r: r[1][0])
    xs = [p[0] for _, p in P]
    ys = [p[1] for _, p in P]

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
    print(f'crete {args.cam}: {int(known.sum())} colonnes mesurees '
          f'({len(anchors)} corrections a la main)')

    wl = ([w.strip() for w in args.witnesses.split(';')] if args.witnesses
          else [c for c, e in cams.items()
                if c != args.cam and posed(e)
                and os.path.exists(os.path.join(REPO, 'frames', f'{c}.png'))])
    # PRE-FILTRE DES TEMOINS: garder ceux qui sont assez proches ET qui
    # voient effectivement la zone (au moins un point du cone de crete tombe
    # dans leur image). Une camera a 12 km qui regarde ailleurs n'apporte
    # rien et ne peut que faire du bruit.
    d0 = np.asarray(cam.get_pixel_direction((float(cols[len(cols) // 2]),
                                             float(sky[len(sky) // 2]))), float)
    d0 /= np.linalg.norm(d0)
    probes = [o + t * d0 for t in (500.0, 1500.0, 3000.0, 5000.0)]
    wit = []
    for w in wl:
        if np.linalg.norm(np.asarray(cams[w]['xyz'], float) - o) > args.max_base:
            continue
        prof = sky_line(w)
        if prof is None or np.isnan(prof).all():
            continue
        c2 = common.get_cam(w)
        if not any(c2.get_pixel([float(v) for v in P_]) is not None for P_ in probes):
            continue
        wit.append((w, c2, prof))
    print(f'{len(wit)} temoins avec une ligne de ciel lisible\n')

    res, binder = [], {}
    for x, y, k in zip(cols, sky, known):
        if not k:
            continue
        d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
        n = np.linalg.norm(d)
        if n < 1e-9:
            continue
        d /= n
        # recherche dichotomique de la plus grande profondeur pour laquelle
        # AUCUN temoin ne place le point dans son ciel
        def ok(t):
            # VOTE, pas veto. Un seul masque de ciel douteux ne doit pas
            # decider: on n'ecarte une profondeur que si PLUSIEURS temoins
            # independants y voient du ciel.
            Q = o + t * d
            says = [w for w, c2, prof in wit if in_sky(c2, prof, Q)]
            if len(says) >= args.min_votes:
                return False, says[0]
            return True, None
        lo, hi = args.near, args.far
        good, who = ok(lo)
        if not good:
            continue
        okhi, whohi = ok(hi)
        if okhi:
            res.append((float(x), float(y), hi, None))
            continue
        who = whohi
        for _ in range(24):
            mid = 0.5 * (lo + hi)
            g, w2 = ok(mid)
            if g:
                lo = mid
            else:
                hi, who = mid, w2
        res.append((float(x), float(y), lo, who))
        binder[who] = binder.get(who, 0) + 1

    if not res:
        raise SystemExit('aucune colonne bornee')
    T = np.array([r[2] for r in res])
    B = np.array([r[2] for r in res if r[3] is not None])
    nb = sum(1 for r in res if r[3] is None)
    print(f'{len(res)} colonnes bornees — profondeur MAXIMALE compatible avec '
          f'toutes les silhouettes:')
    print(f'   mediane {np.median(T):.0f} m, etendue {T.min():.0f}-{T.max():.0f} m')
    print(f'   {nb} colonnes non bornees (aucun temoin ne les contredit meme a '
          f'{args.far:.0f} m)')
    if len(B):
        print(f'   sur les {len(B)} colonnes REELLEMENT bornees: '
              f'{B.min():.0f} / {np.percentile(B, 25):.0f} / {np.median(B):.0f} / '
              f'{np.percentile(B, 75):.0f} / {B.max():.0f} m '
              f'(min / q1 / mediane / q3 / max)')
    if binder:
        print('\n   qui borne, et combien de colonnes:')
        for w, n in sorted(binder.items(), key=lambda r: -r[1]):
            print(f'      {n:4d}  {w}')
    print('\n  C est une BORNE, pas une distance: le massif est a cette '
          'profondeur ou plus pres,\n  jamais plus loin. Elle ne vient que de '
          'nos silhouettes et de nos poses.')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    pts = []
    for x, y, t, _ in res:
        d = np.asarray(cam.get_pixel_direction((x, y)), float)
        d /= np.linalg.norm(d)
        pts.append(o + t * d)
    pts = np.array(pts)
    edges = [[list(map(float, pts[i])), list(map(float, pts[i + 1]))]
             for i in range(len(pts) - 1)
             if np.linalg.norm(pts[i + 1] - pts[i]) < 400.0]
    name = f'{args.massif} (borne silhouettes)'
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    mesh[name] = {'color': '#38bdf8', 'world_edges': edges}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'\nAPPLIED: "{name}" ({len(edges)} segments)')


if __name__ == '__main__':
    main()
