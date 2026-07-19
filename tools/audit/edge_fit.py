#!/usr/bin/env python3
"""edge_fit.py — READ-ONLY. [EDGE-FIT-V1, 2026-07-18]

LA reponse a 'comment tu sais si ca fit?': pour chaque arete projetee d'un
mesh, echantillonne le long et mesure la distance PERPENDICULAIRE au pic de
gradient de l'image (= le vrai bord du batiment). Des milliers de points par
frame au lieu des quelques coins cliques.

Lecture: offset median SIGNE = biais de placement (en px; ~metres = px *
dist / focale). |offset| median = nettete de l'accord. Fonctionne sur les
frames NETTES (jour); les frames floues/nocturnes chassent les lumieres
(mesure prototype JD05: pics sur les lampes, pas les bords).

Usage:
  PYTHONPATH=. python3 tools/audit/edge_fit.py "Vice City 03 (Basketball)" \
      "Vizcayne North Condominium" ["Stephen P. Clark Government Center" ...]
  -> stats + visualisation tools/generated/edge_fit/<cam>.png (vert=mesh,
     rouge=bords detectes)

Limites V1 (documentees): pas de masque d'occlusion (les bords du premier
plan contaminent), pas de distinction silhouette/facade interne. V2 =
brancher ce cout dans fit_mesh/solve de pose pour du fit sub-pixel sans clic.
"""
import argparse
import json
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(THIS))
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, REPO)

import numpy as np
from PIL import Image, ImageDraw
import common

SEARCH = 10
STEP = 3
MIN_EDGE_PX = 15
MIN_PEAK = 12.0
PROMINENCE = 2.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cam')
    ap.add_argument('buildings', nargs='+')
    args = ap.parse_args()
    C = args.cam
    # [V3] stats sub-pixel + IC bootstrap via edgefit_core
    import json as _j
    _bp = _j.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')))
    _ctx = FrameCtx(C)
    _meshes = {b: _bp[b]['world_edges'] for b in args.buildings if b in _bp}
    _hulls = build_hulls(_ctx, _meshes)
    for _b, _e in _meshes.items():
        _r = core_sample(_ctx, _e, self_name=_b, hulls=_hulls)
        _o = _r['offsets']
        if len(_o) > 30:
            _boots = [float(np.median(np.random.choice(_o, len(_o)))) for _ in range(200)]
            lo, hi = np.percentile(_boots, [2.5, 97.5])
            print(f'[V3] {_b}: {len(_o)} pts | biais {np.median(_o):+.2f}px IC95 [{lo:+.2f}, {hi:+.2f}] | |off| {np.median(np.abs(_o)):.1f}px')
    cam = common.get_cam(C)
    frame = os.path.join(REPO, 'frames', f'{C}.png')
    img = np.asarray(Image.open(frame).convert('L'), dtype=float)
    H, W = img.shape
    gy, gx = np.gradient(img)
    gmag = np.hypot(gx, gy)
    bp = json.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')))
    im2 = Image.open(frame).convert('RGB')
    dr = ImageDraw.Draw(im2)
    allp = []
    for b in args.buildings:
        offs = []
        for a, bb in bp[b].get('world_edges', []):
            pa, pb = cam.get_pixel(a), cam.get_pixel(bb)
            if pa is None or pb is None:
                continue
            dr.line([tuple(pa), tuple(pb)], fill=(74, 222, 128), width=1)
            allp += [pa, pb]
            pa, pb = np.array(pa), np.array(pb)
            L = np.linalg.norm(pb - pa)
            if L < MIN_EDGE_PX:
                continue
            t = (pb - pa) / L
            n = np.array([-t[1], t[0]])
            for s in np.arange(3, L - 3, STEP):
                p = pa + t * s
                if not (SEARCH < p[0] < W - SEARCH - 1 and SEARCH < p[1] < H - SEARCH - 1):
                    continue
                prof = np.array([gmag[int((p + n * o)[1]), int((p + n * o)[0])]
                                 for o in range(-SEARCH, SEARCH + 1)])
                k = int(np.argmax(prof))
                if prof[k] < MIN_PEAK or prof[k] < PROMINENCE * np.median(prof):
                    continue
                offs.append(k - SEARCH)
                q = p + n * (k - SEARCH)
                dr.ellipse([q[0] - 1.5, q[1] - 1.5, q[0] + 1.5, q[1] + 1.5], fill=(248, 113, 113))
        offs = np.array(offs)
        if len(offs) > 15:
            print(f'{b}: {len(offs)} pts | offset median {np.median(offs):+.1f}px '
                  f'(biais placement) | |offset| median {np.median(np.abs(offs)):.1f}px')
        else:
            print(f'{b}: {len(offs)} pts — pas assez de bords nets (frame floue/occluse?)')
    outdir = os.path.join(REPO, 'tools', 'generated', 'edge_fit')
    os.makedirs(outdir, exist_ok=True)
    if allp:
        xs = [p[0] for p in allp]; ys = [p[1] for p in allp]
        box = (max(0, int(min(xs)) - 60), max(0, int(min(ys)) - 50),
               min(im2.width, int(max(xs)) + 60), min(im2.height, int(max(ys)) + 60))
        crop = im2.crop(box)
        if crop.width > 1100:
            crop = crop.resize((1100, int(crop.height * 1100 / crop.width)))
        safe = C.replace(' ', '_').replace('(', '').replace(')', '')
        crop.save(os.path.join(outdir, f'{safe}.png'))
        print(f'-> visualisation: tools/generated/edge_fit/{safe}.png')


if __name__ == '__main__':
    main()
