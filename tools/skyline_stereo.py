#!/usr/bin/env python3
"""skyline_stereo.py — la profondeur de la crete MESUREE par un temoin. [SKYSTEREO-V1]

Ce que ca remplace. Le mesh d'Mount Ambrosia actuellement dans l'UI garde la
silhouette validee a la main par Alexandre, mais sa PROFONDEUR est une
hypothese: un volume a pente 30 degres pose derriere le trace. La silhouette
est mesuree, le relief derriere ne l'est pas.

L'idee. Un point de crete n'est pas une texture a apparier — c'est un point
qui appartient a la LIGNE DE CIEL DES DEUX CAMERAS a la fois. Donc:

    rayon du pixel de crete dans la vue A
      x  cone des rayons de la ligne de ciel de la vue B
      =  le point 3D

C'est une intersection geometrique. Aucune correlation d'image, donc ni
l'heure, ni la meteo, ni la resolution, ni l'exposition n'entrent en jeu —
c'est exactement ce qui a fait echouer le plane sweep (17 a 43 pct d'erreur
malgre une homographie exacte a 0.00 px).

Et contrairement au sky carving, ca ne donne pas une enveloppe conique: pour
chaque colonne on obtient UN point, a une profondeur determinee.

LA LIMITE, qu'il faut connaitre avant de lire les chiffres. Une silhouette
depend du point de vue: le point de la surface qui se detache sur le ciel
depuis A n'est pas exactement celui qui s'en detache depuis B — il GLISSE
sur la surface (c'est le probleme des "points frontiere" en shape-from-
silhouette). L'erreur est petite pour une arete franche vue de biais, et
grande pour un dome lisse. Elle croit avec la parallaxe: c'est le compromis
inverse de la triangulation, ou plus de parallaxe vaut mieux. L'outil mesure
donc son propre resultat contre nos ancres au lieu de le supposer bon.

Usage:
  PYTHONPATH=. python3 tools/skyline_stereo.py --witness 'Hedge (B) (X)'
  PYTHONPATH=. python3 tools/skyline_stereo.py --witness 'Explosion' --apply
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
CAM = 'Ambrosia 01 (Bikers)'
CLICKS = ['Mount Ambrosia (B)', 'Mount Ambrosia (D)',
          'Mount Ambrosia (E)', 'Mount Ambrosia (G)']


def skyline_A(x0=130):
    """La silhouette d'Ambrosia depuis Bikers — celle qu'Alexandre a validee.
    On reprend telle quelle la machinerie de hill_mesh: traqueur DP, bande du
    billboard exclue, et ses corrections au pixel pres."""
    import common
    from hill_mesh import extract_skyline
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    marks = px[CAM]
    gray = np.asarray(Image.open(os.path.join(REPO, 'frames', f'{CAM}.png'))
                      .convert('L'), np.float32)
    P = [marks[c] for c in CLICKS]
    xs = [p[0] for p in P]
    ys = [p[1] for p in P]

    def prior_y(x):
        return float(np.interp(x, xs, ys))

    exclude = []
    bw = marks.get('Billboard with Diversity Motif (TW)')
    be = marks.get('Billboard with Diversity Motif (TE)')
    if bw and be:
        exclude.append((bw[0] - 40, be[0] + 70))
    cp = os.path.join(THIS, 'data', 'hill_outline_corrections.json')
    anchors = json.load(open(cp)).get(CAM, []) if os.path.exists(cp) else []
    cols, sky, meas, manual = extract_skyline(gray, prior_y, x0,
                                              gray.shape[1] - 4,
                                              exclude=exclude, anchors=anchors)
    known = meas | manual
    mi = np.where(known)[0]
    lo, hi = max(0, mi[0] - 40), min(len(cols), mi[-1] + 41)
    return (cols[lo:hi], sky[lo:hi], meas[lo:hi], manual[lo:hi],
            len(anchors), exclude)


def witness_window(cam_name, pad=120.0):
    """Fenetre en x ou le massif se trouve dans la frame du temoin, deduite
    de SES PROPRES clics sur Ambrosia. Sans elle, on apparie la crete contre
    la ligne de ciel entiere du temoin — batiments, arbres, autres collines —
    et le minimum tombe sur n'importe quel croisement fortuit: c'est ce qui
    donnait une crete a 8900 m et 1127 m d'altitude."""
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    xs = [p[0] for lm, p in (px.get(cam_name) or {}).items()
          if p is not None
          and any(s in lm.lower() for s in ('ambrosia hill', 'mount ambrosia'))]
    if not xs:
        return None
    return (min(xs) - pad, max(xs) + pad)


def skyline_B(cam_name, step=2, window=None):
    """Ligne de ciel du temoin: bande de ciel CONNEXE au haut de l'image.
    Pas de traqueur DP ici — on ne cherche pas a suivre un massif precis,
    seulement la frontiere ciel/terrain, et la contiguite au bord superieur
    suffit a ne pas confondre une facade claire avec du ciel."""
    p = os.path.join(REPO, 'frames', f'{cam_name}.png')
    if not os.path.exists(p):
        raise SystemExit(f'frame absente: {p}')
    a = np.asarray(Image.open(p).convert('RGB'), np.int16)
    sky = ((a[:, :, 2] - a[:, :, 0]) > 6) | (a.mean(axis=2) > 205)
    H, W = sky.shape
    out = []
    for x in range(0, W, step):
        col = sky[:, x]
        if not col[0]:
            continue
        run = int(np.argmin(col)) if (~col).any() else len(col)
        y = run - 1
        if 2 <= y < H - 3:
            if window is None or (window[0] <= x <= window[1]):
                out.append((float(x), float(y)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--witness', required=True,
                    help='camera temoin (Hedge (B) (X), Explosion, '
                         'Empty Lot near Metro Station...)')
    ap.add_argument('--wrange', help='fenetre x du massif chez le temoin '
                                     '(defaut: deduite de ses propres clics)')
    ap.add_argument('--max-gap', type=float, default=60.0,
                    help='ecart maximal admis entre les deux rayons (m)')
    ap.add_argument('--min-par', type=float, default=3.0,
                    help='parallaxe minimale entre les deux rayons (deg)')
    ap.add_argument('--near', type=float, default=300.0)
    ap.add_argument('--far', type=float, default=9000.0)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    import common
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    A = common.get_cam(CAM)
    B = common.get_cam(args.witness)
    o1 = np.asarray(A.xyz, float)
    o2 = np.asarray(B.xyz, float)
    print(f'vue A  {CAM}   xyz {[round(v) for v in o1]}')
    print(f'temoin {args.witness}   xyz {[round(v) for v in o2]}   '
          f'base {np.linalg.norm(o1 - o2):.0f} m')

    cols, sky, meas, manual, nanch, exclude = skyline_A()
    print(f'silhouette A: {len(cols)} colonnes, {int(meas.sum())} mesurees + '
          f'{int(manual.sum())} corrigees a la main ({nanch} strokes)')
    win = ([float(v) for v in args.wrange.split(',')] if args.wrange
           else witness_window(args.witness))
    if win is None:
        print('  (le temoin n a aucun clic sur Ambrosia: ligne de ciel entiere '
              '— attention aux appariements fortuits)')
    else:
        print(f'  fenetre du massif chez le temoin: x {win[0]:.0f}-{win[1]:.0f}')
    pts_b = skyline_B(args.witness, window=win)
    print(f'ligne de ciel du temoin (dans la fenetre): {len(pts_b)} points')
    if len(pts_b) < 20:
        raise SystemExit('temoin sans ligne de ciel exploitable')

    def dirs(cam, pts):
        D = []
        for (x, y) in pts:
            d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
            D.append(d / max(1e-9, np.linalg.norm(d)))
        return np.array(D)

    keep_a = (meas | manual)
    pa = [(float(x), float(y)) for x, y, k in zip(cols, sky, keep_a) if k]
    D1 = dirs(A, pa)
    D2 = dirs(B, pts_b)

    # POINT LE PLUS PROCHE entre deux droites gauches, vectorise. Les deux
    # origines sont fixes (les centres optiques), donc tout se ramene a des
    # produits scalaires entre directions.
    w0 = o1 - o2
    bmat = D1 @ D2.T                       # nA x nB
    dvec = D1 @ w0                         # nA
    evec = D2 @ w0                         # nB
    den = 1.0 - bmat ** 2
    den = np.where(np.abs(den) < 1e-9, np.nan, den)
    t1 = (bmat * evec[None, :] - dvec[:, None]) / den
    t2 = (evec[None, :] - bmat * dvec[:, None]) / den
    P1 = o1[None, None, :] + t1[:, :, None] * D1[:, None, :]
    P2 = o2[None, None, :] + t2[:, :, None] * D2[None, :, :]
    gap = np.linalg.norm(P1 - P2, axis=2)
    par = np.degrees(np.arccos(np.clip(np.abs(bmat), -1, 1)))
    bad = (t1 <= args.near) | (t1 >= args.far) | (t2 <= 0) | (par < args.min_par)
    gap = np.where(bad | np.isnan(gap), np.inf, gap)

    j = np.argmin(gap, axis=1)
    i = np.arange(len(D1))
    g = gap[i, j]
    ok = np.isfinite(g) & (g <= args.max_gap)
    Q = 0.5 * (P1[i, j] + P2[i, j])
    print(f'\n{int(ok.sum())} / {len(D1)} colonnes appariees '
          f'(ecart entre rayons <= {args.max_gap:.0f} m, '
          f'parallaxe >= {args.min_par:.0f} deg)')
    if not ok.any():
        raise SystemExit('aucun appariement — le temoin ne voit pas cette crete')
    QQ = Q[ok]
    dd = np.linalg.norm(QQ[:, :2] - o1[:2], axis=1)
    print(f'crete reconstruite: distance {dd.min():.0f}-{dd.max():.0f} m '
          f'(mediane {np.median(dd):.0f}), z {QQ[:, 2].min():.0f} a '
          f'{QQ[:, 2].max():.0f} m, ecart median entre rayons '
          f'{np.median(g[ok]):.1f} m')

    # VALIDATION: nos ancres n'ont pas servi. On compare la profondeur
    # reconstruite AU PIXEL de chaque ancre du massif, pas au point le plus
    # proche du nuage — c'est la lecon du plane sweep.
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    xs_ok = np.array([p[0] for p, k in zip(pa, ok) if k])
    print('\nvalidation sur nos ancres (non utilisees pour reconstruire):')
    errs = []
    for lm, p in (px.get(CAM) or {}).items():
        e = lms.get(lm)
        if not (isinstance(e, dict) and e.get('xyz')):
            continue
        if not any(s in lm.lower() for s in ('ambrosia hill', 'mount ambrosia')):
            continue
        k = int(np.argmin(np.abs(xs_ok - p[0])))
        if abs(xs_ok[k] - p[0]) > 30:
            print(f'   {lm[:30]:30s} (aucune colonne reconstruite a ce pixel)')
            continue
        vraie = float(np.linalg.norm(np.asarray(e['xyz'], float)[:2] - o1[:2]))
        got = float(dd[k])
        errs.append(abs(got - vraie) / max(1.0, vraie))
        print(f'   {lm[:30]:30s} vraie {vraie:6.0f} m   stereo {got:6.0f} m   '
              f'{got - vraie:+6.0f} m ({100 * abs(got - vraie) / max(1, vraie):.1f} pct)'
              f'   [err ancre {e.get("error_m")} m]')
    if errs:
        print(f'\n   ecart median {100 * float(np.median(errs)):.1f} pct '
              f'sur {len(errs)} ancres')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire la crete).')
        return
    edges = [[list(map(float, QQ[k])), list(map(float, QQ[k + 1]))]
             for k in range(len(QQ) - 1)
             if np.linalg.norm(QQ[k + 1] - QQ[k]) < 250.0]
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    mesh['Mount Ambrosia (crete mesuree)'] = {'color': '#38bdf8',
                                             'world_edges': edges}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'\nAPPLIED: crete mesuree ({len(edges)} segments)')


if __name__ == '__main__':
    main()
