#!/usr/bin/env python3
"""map_crosscheck.py — la MAP comme temoin geometrique. [MAP-XCHECK-V1]

Idee (sortie de boite, 2026-07-29): la carte communautaire connait le TRACE
XY des routes. Une route vue en perspective doit S'ELOIGNER dans l'image.
Donc, pour une pose de camera donnee, on peut caster les rayons des pixels
de route et regarder OU ils rencontrent le trace de la carte: si la
distance reste constante d'un bout a l'autre de l'image, la pose est
fausse (la route serait un mur perpendiculaire a la vue).

C'est un test de pose qui ne coute AUCUN clic et n'utilise aucun reseau.

ATTENTION (rappel d'Alexandre): la carte communautaire est une OBSERVATION
au meilleur de nos connaissances, pas une verite officielle. Le test est
donc un temoin, pas un juge — mais un rapport de distances de 1.05 (mur)
contre 3.84 (route qui fuit) tranche sans ambiguite.

Resultat du premier passage (Mount Kalaga 04):
  notre resection RESECTION-V1 : 248-260 m, rapport 1.05  -> IMPOSSIBLE
  pose rlx (upstream)          : 128-492 m, rapport 3.84  -> coherente

Usage: PYTHONPATH=. python3 tools/map_crosscheck.py --cam '<nom>' --line road_center
"""
import argparse
import json
import math
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
from PIL import Image
import common

TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,14', '5')
TILE = 256


def road_mask_world(xmin, xmax, ymin, ymax):
    """Pixels de route (rouge brique) de la carte, en coordonnees monde."""
    lx, ty = xmin + 16384, 16384 - ymax
    rx, by = xmax + 16384, 16384 - ymin
    tx0, tx1 = int(lx // TILE), int(rx // TILE)
    ty0, ty1 = int(ty // TILE), int(by // TILE)
    comp = Image.new('RGB', ((tx1 - tx0 + 1) * TILE, (ty1 - ty0 + 1) * TILE), (16, 20, 28))
    for tyy in range(ty0, ty1 + 1):
        for txx in range(tx0, tx1 + 1):
            p = os.path.join(TILES, f'5,{tyy},{txx}.jpg')
            if os.path.exists(p):
                comp.paste(Image.open(p).convert('RGB'),
                           ((txx - tx0) * TILE, (tyy - ty0) * TILE))
    comp = comp.crop((int(lx - tx0 * TILE), int(ty - ty0 * TILE),
                      int(rx - tx0 * TILE), int(by - ty0 * TILE)))
    a = np.asarray(comp, np.int16)
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    m = (R > 120) & (R < 210) & (G > 50) & (G < 120) & (B > 50) & (B < 120) & (R - G > 40)
    ys, xs = np.where(m)
    return np.stack([xs + xmin, ymax - ys], axis=1).astype(float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cam', required=True)
    ap.add_argument('--line', default='road_center',
                    help='ligne 2D de la route (canyon_lines.json)')
    ap.add_argument('--lines-json',
                    default=os.path.join(REPO, 'tools', 'generated', 'canyon_lines.json'))
    ap.add_argument('--span', type=float, default=1600.0, help='demi-emprise carte (m)')
    args = ap.parse_args()

    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    lines = json.load(open(args.lines_json))
    rx = lines[args.line]['x']
    ry = lines[args.line]['y']

    base = cams[args.cam]
    o0 = np.asarray(base['xyz'], float)
    RM = road_mask_world(o0[0] - args.span, o0[0] + args.span,
                         o0[1] - args.span, o0[1] + args.span)
    print(f'{len(RM)} pixels de route dans la carte autour de la cam')
    CELL = 6.0
    X0, Y0 = RM[:, 0].min(), RM[:, 1].min()
    occ = set(zip(((RM[:, 0] - X0) // CELL).astype(int).tolist(),
                  ((RM[:, 1] - Y0) // CELL).astype(int).tolist()))

    def test(state, label):
        cam = common.get_cam(args.cam, state)
        o = np.asarray(state['xyz'], float)
        ds = []
        for i in range(0, len(rx), max(1, len(rx) // 40)):
            d = np.asarray(cam.get_pixel_direction((float(rx[i]), float(ry[i]))), float)
            d /= np.linalg.norm(d)
            hx = float(np.hypot(d[0], d[1]))
            if hx < 1e-6:
                continue
            for t in np.arange(60, 2500, 4):
                x, y = o[0] + t * d[0] / hx, o[1] + t * d[1] / hx
                if (int((x - X0) // CELL), int((y - Y0) // CELL)) in occ:
                    ds.append((float(ry[i]), t))
                    break
        if len(ds) < 6:
            print(f'{label:22s}: la route de la carte n est pas dans le champ')
            return None
        ds.sort(key=lambda r: -r[0])
        dd = np.array([t for _, t in ds])
        ratio = dd.max() / dd.min()
        rho = float(np.corrcoef(np.arange(len(dd)), dd)[0, 1])
        verdict = ('IMPOSSIBLE (mur perpendiculaire)' if ratio < 1.5 else
                   'coherente (la route s eloigne)')
        print(f'{label:22s}: {len(dd)} colonnes, distance {dd.min():.0f}-{dd.max():.0f} m, '
              f'rapport {ratio:.2f}, correlation {rho:+.2f}  -> {verdict}')
        return ratio

    test({'xyz': base['xyz'], 'ypr': base['ypr'], 'fov': base['fov']}, 'pose actuelle')
    note = base.get('note', '')
    if 'RESECTION' in note:
        test({'xyz': [-4750.0, 6000.0, 120.0], 'ypr': [156.447, -13.566, 0.0],
              'fov': [60.0, None]}, 'pose rlx (reference)')


if __name__ == '__main__':
    main()
