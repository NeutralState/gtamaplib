#!/usr/bin/env python3
"""silhouette_volume.py — le VOLUME taille par les silhouettes tracees. [SILVOL-V1]

Suite directe de SILHULL, qui ne bornait qu'un rayon a la fois. Ici on taille
un champ de hauteur complet: pour chaque cellule du sol, l'altitude maximale
compatible avec TOUTES les silhouettes tracees a la main.

LE PRINCIPE, en une phrase: si un point du monde se projette AU-DESSUS de la
ligne de silhouette d'une camera, cette camera y voit du ciel — donc il n'y a
pas de terrain a cet endroit. Pour une cellule (x, y) donnee et une camera, il
existe donc une altitude maximale: celle a partir de laquelle le point sort
au-dessus de la ligne. Elle se trouve par dichotomie, la projection etant
monotone en z. Le champ final est le MINIMUM sur toutes les cameras.

POURQUOI CA MARCHE MAINTENANT ET PAS AVANT. La meme idee, appliquee aux
masques de ciel AUTOMATIQUES (SKYCARVE), donnait des cones: le masque
attrapait des facades, des poteaux, du HUD, et la moitie des cameras ne
disait rien d'exploitable. Les traces d'Alexandre sont exactes et couvrent
plusieurs azimuts — 227 degres d'eventail sur Mount Ambrosia. Au-dela d'une
soixantaine de degres, le hull cesse d'etre un cone et devient un volume.

CE QUE C'EST, ET CE QUE CE N'EST PAS. C'est l'ENVELOPPE SUPERIEURE du relief:
le terrain est a cette altitude ou plus bas, jamais plus haut. La ou plusieurs
azimuts se croisent, l'enveloppe colle a la vraie surface; la ou une seule
camera regarde, elle reste lache et le dit (l'outil compte, par cellule,
combien de cameras l'ont effectivement contrainte).

Aucune pente n'est supposee, aucune distance declaree, aucune carte
consultee. Uniquement les traces et les poses.

Usage:
  PYTHONPATH=. python3 tools/silhouette_volume.py --bbox -4800,-1800,4400,7800 \
      --cell 30 --name 'Mount Ambrosia (volume)' [--apply]
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

MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')


def is_skyline(cam_name, prof):
    """Le trait est-il vraiment la LIMITE DU CIEL de cette camera ?

    La contrainte "au-dessus du trait = ciel" n'est valable que si le trait
    est la crete la plus HAUTE de sa colonne. Si l'utilisateur a trace une
    crete intermediaire, avec du relief au-dessus, tailler dessus retirerait
    du terrain qui existe.

    Test: la luminance mediane juste au-dessus contre juste en dessous. Le
    ciel, meme brumeux et blanc, est plus clair que du terrain. Un premier
    test base sur la dominance BLEUE se trompait lourdement — le ciel
    d'Ambrosia 01 est blanc laiteux et il etait classe "terrain".
    """
    from PIL import Image
    p = os.path.join(REPO, 'frames', f'{cam_name}.png')
    if not os.path.exists(p):
        return False, 0.0
    L = np.asarray(Image.open(p).convert('L'), np.float32)
    up, dn = [], []
    for u in np.where(~np.isnan(prof))[0]:
        v = int(prof[u])
        if v - 20 >= 0 and v + 20 < L.shape[0]:
            up.append(L[v - 20:v - 8, u].mean())
            dn.append(L[v + 8:v + 20, u].mean())
    if len(up) < 20:
        return False, 0.0
    gap = float(np.median(up) - np.median(dn))
    return gap > 12.0, gap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bbox', required=True, help='xmin,xmax,ymin,ymax')
    ap.add_argument('--cell', type=float, default=30.0)
    ap.add_argument('--ceiling', type=float, default=800.0)
    ap.add_argument('--floor', type=float, default=0.0)
    ap.add_argument('--min-cams', type=int, default=2,
                    help='cameras devant contraindre une cellule pour qu elle '
                         'soit gardee — une seule vue ne referme rien')
    ap.add_argument('--name', default='Relief (volume silhouettes)')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    import common
    from silhouette_hull import traced, cam_profile
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    TR = traced()
    if not TR:
        raise SystemExit('aucun trace: tools/data/silhouettes.json est absent')

    xmin, xmax, ymin, ymax = [float(v) for v in args.bbox.split(',')]
    nx = int((xmax - xmin) / args.cell)
    ny = int((ymax - ymin) / args.cell)
    X, Y = np.meshgrid(xmin + (np.arange(nx) + 0.5) * args.cell,
                       ymin + (np.arange(ny) + 0.5) * args.cell)
    H = np.full(X.shape, args.ceiling)
    votes = np.zeros(X.shape, np.int16)
    print(f'grille {nx} x {ny} de {args.cell:.0f} m '
          f'({(xmax - xmin) / 1000:.1f} x {(ymax - ymin) / 1000:.1f} km)\n')
    print(f'{"camera":42s} {"cellules vues":>13s} {"taillees":>9s}')

    for cn in sorted(TR):
        if cn not in cams:
            continue
        cam = common.get_cam(cn)
        prof = cam_profile(TR, cn, int(cam.w))
        if np.isnan(prof).all():
            continue
        ok, gap = is_skyline(cn, prof)
        if not ok:
            print(f'{cn[:42]:42s} {"":13s} {"":9s}  ECARTEE: le trait n est pas '
                  f'la limite du ciel (ecart {gap:+.0f})')
            continue

        def above_sky(P):
            """Le point est-il au-dessus de la ligne tracee (donc dans le
            ciel) ? None si cette camera ne dit rien de cette direction."""
            q = cam.get_pixel([float(v) for v in P])
            if q is None:
                return None
            u = int(round(q[0]))
            if not (0 <= u < len(prof)) or math.isnan(prof[u]):
                return None
            return q[1] < prof[u]

        seen = cut = 0
        for i in range(ny):
            for j in range(nx):
                x, y = X[i, j], Y[i, j]
                lo, hi = args.floor, args.ceiling
                a = above_sky((x, y, lo))
                if a is None:
                    continue
                seen += 1
                if a:
                    # meme au sol le point est dans le ciel: la cellule est
                    # entierement exclue par cette camera
                    if H[i, j] > args.floor:
                        H[i, j] = args.floor
                        cut += 1
                    votes[i, j] += 1
                    continue
                b = above_sky((x, y, hi))
                if b is None or not b:
                    continue          # meme au plafond rien ne l'exclut
                for _ in range(18):
                    mid = 0.5 * (lo + hi)
                    m = above_sky((x, y, mid))
                    if m is None:
                        break
                    if m:
                        hi = mid
                    else:
                        lo = mid
                votes[i, j] += 1
                if lo < H[i, j] - 0.5:
                    H[i, j] = lo
                    cut += 1
        print(f'{cn[:42]:42s} {seen:13d} {cut:9d}')

    keep = (votes >= args.min_cams) & (H < args.ceiling - 1)
    print(f'\ncellules contraintes par >= {args.min_cams} cameras: '
          f'{int(keep.sum())} / {H.size} ({100.0 * keep.mean():.1f} pct)')
    if not keep.any():
        raise SystemExit('aucune cellule contrainte par assez de cameras')
    Z = H[keep]
    print(f'enveloppe sur ces cellules: z {Z.min():.0f} a {Z.max():.0f} m '
          f'(mediane {np.median(Z):.0f})')
    print(f'cellules vues par 1 seule camera: {int(((votes == 1)).sum())} '
          f'— ecartees, une vue ne referme rien')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    edges = []
    for i in range(ny - 1):
        for j in range(nx - 1):
            if not (keep[i, j] and keep[i, j + 1] and keep[i + 1, j]):
                continue
            a = [float(X[i, j]), float(Y[i, j]), float(H[i, j])]
            edges.append([a, [float(X[i, j + 1]), float(Y[i, j + 1]),
                              float(H[i, j + 1])]])
            edges.append([a, [float(X[i + 1, j]), float(Y[i + 1, j]),
                              float(H[i + 1, j])]])
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    mesh[args.name] = {'color': '#4ade80', 'world_edges': edges}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'\nAPPLIED: "{args.name}" ({len(edges)} aretes)')


if __name__ == '__main__':
    main()
