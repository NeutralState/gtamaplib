#!/usr/bin/env python3
"""rlx_refine.py — sa POSITION, nos silhouettes pour l'ajuster. [RLX-REFINE-V1]

La consigne (Alexandre, 2026-07-31): "prend les modeles de rlx pour la
position et apres maybe avec tout ce qu'on a fait on peut leur donner plus de
detail... peut-etre juste pas ambrosia mountain for now vu j'aime quand meme
notre truc".

Le partage des roles est le bon, et c'est ce que la journee a etabli:
  * rlx a POSITIONNE chaque massif. Ses distances sont declarees a l'oeil
    depuis une camera, donc approximatives — mesurees contre nos
    triangulations elles s'ecartent de 6.9 pct en median — mais elles
    existent, et nous n'avons rien d'equivalent: aucune ancre valide sur
    ces massifs.
  * nous avons des SILHOUETTES tracees a la main sur 3 a 5 vues par massif,
    exactes et sans ambiguite de designation.

Ce que la silhouette contraint, c'est la SILHOUETTE: un point du massif ne
peut pas se projeter au-dessus du trait, sinon la camera y verrait du ciel.
Et l'erreur de rlx est RADIALE depuis sa camera, puisqu'elle porte sur une
distance devinee. Un seul parametre suffit donc: le facteur radial k autour
de SA camera.

On cherche le plus PETIT k sans violation, et le sens compte. Eloigner un
massif le fait DESCENDRE dans l'image: son angle apparent diminue. Donc
n'importe quel k assez grand supprime toutes les violations, et "le plus
grand k valide" n'existe pas — ma premiere version cherchait ca et les trois
massifs sortaient colles au plafond de recherche, a x1.60.

La silhouette borne donc par le BAS: elle interdit d'etre trop pres. Le plus
petit k valide est la position ou la crete TOUCHE la silhouette par en
dessous, c'est-a-dire la plus proche que nos traces autorisent.

CE QUI RESTE DE LUI: la forme, l'orientation, le trace au sol. CE QU'ON
CORRIGE: l'echelle radiale, et rien d'autre.

Mount Ambrosia est exclu par defaut — notre modele y est prefere.

Usage:
  PYTHONPATH=. python3 tools/rlx_refine.py [--only 'Mount Waffles'] [--apply]
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
RLX_PATH = os.path.join(THIS, 'data', 'rlx_mountains_meshes.json')
SKIP = ('Mount Ambrosia',)          # notre modele est prefere


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only')
    ap.add_argument('--include-ambrosia', action='store_true')
    ap.add_argument('--tol', type=float, default=1.0,
                    help='pourcentage de sommets tolere au-dessus des traces')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    import common
    from silhouette_hull import traced, cam_profile
    from silhouette_volume import is_skyline
    from import_rlx_mountains import MOUNTAINS
    src = {n: c for n, c, _, _, _ in MOUNTAINS}
    R = json.load(open(RLX_PATH))
    TR = traced()

    # profils tracés valides, une seule fois
    prof = {}
    for cn in TR:
        try:
            c = common.get_cam(cn)
        except Exception:
            continue
        pr = cam_profile(TR, cn, int(c.w))
        if np.isnan(pr).all():
            continue
        ok, gap = is_skyline(cn, pr)
        if ok:
            prof[cn] = (c, pr)
    print(f'{len(prof)} vues tracees utilisables comme limite de ciel\n')

    def violations(V, massif):
        """Sommets qui passent au-dessus d'un trait, et de combien."""
        out = []
        for cn, (c, pr) in prof.items():
            if massif not in (TR.get(cn) or {}):
                continue          # cette vue ne trace pas ce massif
            for P in V:
                q = c.get_pixel([float(v) for v in P])
                if q is None:
                    continue
                u = int(round(q[0]))
                if not (0 <= u < len(pr)) or math.isnan(pr[u]):
                    continue
                if q[1] < pr[u] - 2.0:
                    out.append((cn, float(pr[u] - q[1])))
        return out

    out = {}
    for key, ent in sorted(R.items()):
        name = key.replace('[rlx] ', '')
        if args.only and args.only.lower() not in name.lower():
            continue
        if name in SKIP and not args.include_ambrosia:
            print(f'{name}: EXCLU (notre modele est prefere)')
            continue
        cn = src.get(name)
        if cn is None:
            print(f'{name}: camera source inconnue, ignore')
            continue
        views = [c for c in prof if name in (TR.get(c) or {})]
        if not views:
            print(f'{name}: aucune de nos vues tracees ne le couvre, ignore')
            continue
        cam = common.get_cam(cn)
        o = np.asarray(cam.xyz, float)
        V0 = np.array([p for a, b in ent['world_edges'] for p in (a, b)], float)
        n0 = len(violations(V0, name))
        best = None
        for k in np.arange(0.30, 3.01, 0.01):
            V = V0.copy()
            V[:, :2] = o[:2] + k * (V0[:, :2] - o[:2])
            nv = len(violations(V, name))
            if nv <= args.tol / 100.0 * len(V0):
                best = (float(k), nv)   # le PLUS PETIT k qui passe
                break
        d0 = float(np.median(np.linalg.norm(V0[:, :2] - o[:2], axis=1)))
        print(f'{name}   ({len(views)} de nos vues: '
              f'{", ".join(v[:22] for v in views)})')
        print(f'   sa position: {d0:.0f} m de {cn[:30]}, '
              f'{n0} sommets sur {len(V0)} au-dessus de nos traces')
        if best is None:
            print('   AUCUN facteur ne le rend compatible — sa forme meme '
                  'contredit nos silhouettes, on ne touche a rien\n')
            continue
        k, nv = best
        print(f'   -> plus proche position compatible: facteur x{k:.2f} '
              f'({d0 * k:.0f} m), {nv} sommets restants au-dessus')
        if abs(k - 1.0) < 0.02:
            print('   (sa position tient deja: correction sous 2 pct)')
        V = V0.copy()
        V[:, :2] = o[:2] + k * (V0[:, :2] - o[:2])
        edges = [[list(map(float, V[2 * i])), list(map(float, V[2 * i + 1]))]
                 for i in range(len(ent['world_edges']))]
        out[f'{name} (rlx recale)'] = {'color': '#a78bfa', 'world_edges': edges}
        print()

    if not out:
        print('rien a ecrire.')
        return
    if not args.apply:
        print(f'DRY-RUN — {len(out)} massifs prets ({", ".join(out)}).')
        return
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    mesh.update(out)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'APPLIED: {len(out)} massifs — {", ".join(out)}')


if __name__ == '__main__':
    main()
