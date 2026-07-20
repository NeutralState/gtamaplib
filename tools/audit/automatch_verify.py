#!/usr/bin/env python3
"""automatch_verify.py — juge de reciprocite + planche-contact. [READ-ONLY]

Deux passes automatch independantes (A->B et B->A) n'ont aucune raison de
s'accorder sur un point 3D... sauf si le point est reel. On garde les paires
de candidats des deux sens a <RECIP_TOL m l'un de l'autre (match reciproque),
on deduplique par clustering glouton (rayon CLUSTER_M), et on rend une
planche-contact crop-A | crop-B par survivant — le verdict a l'oeil.

Usage:
  PYTHONPATH=. python3 tools/audit/automatch_verify.py \
      tools/generated/automatch_sift_ab.json tools/generated/automatch_sift_ba.json
"""
import json
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(THIS))
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, REPO)

import numpy as np
from PIL import Image, ImageDraw, ImageFont

RECIP_TOL = 2.0   # m entre les solves des deux sens
CLUSTER_M = 3.0   # dedup
CROP = 48         # demi-cote du crop
PER_ROW = 6


def main():
    fwd = json.load(open(sys.argv[1]))
    rev = json.load(open(sys.argv[2]))
    assert fwd['src'] == rev['dst'] and fwd['dst'] == rev['src'], 'paires incoherentes'
    A, B = fwd['src'], fwd['dst']
    ca = fwd['candidates']; cb = rev['candidates']
    print(f'{A} -> {B}: {len(ca)} cands | retour: {len(cb)}')
    if not ca or not cb:
        sys.exit('rien a verifier')
    Pa = np.array([c['xyz'] for c in ca]); Pb = np.array([c['xyz'] for c in cb])

    # reciprocite: plus proche voisin croise < RECIP_TOL
    from scipy.spatial import cKDTree
    tb = cKDTree(Pb)
    d, j = tb.query(Pa)
    pairs = [(ca[i], cb[int(j[i])], float(d[i])) for i in range(len(ca)) if d[i] < RECIP_TOL]
    print(f'reciproques (<{RECIP_TOL}m): {len(pairs)} / {len(ca)}')

    # dedup glouton par distance 3D (garde le plus petit ecart reciproque)
    pairs.sort(key=lambda p: p[2])
    kept = []
    for cf, cr, dd in pairs:
        p = np.asarray(cf['xyz'])
        if all(np.linalg.norm(p - np.asarray(k[0]['xyz'])) > CLUSTER_M for k in kept):
            kept.append((cf, cr, dd))
    print(f'apres dedup ({CLUSTER_M}m): {len(kept)} points')

    zs = sorted(k[0]['xyz'][2] for k in kept)
    if kept:
        print(f'z: min {zs[0]:.0f} median {zs[len(zs)//2]:.0f} max {zs[-1]:.0f} | '
              f'ecart reciproque median {np.median([k[2] for k in kept]):.2f}m')

    # planche-contact
    imA = Image.open(os.path.join(REPO, 'frames', f'{A}.png')).convert('RGB')
    imB = Image.open(os.path.join(REPO, 'frames', f'{B}.png')).convert('RGB')
    n = len(kept)
    rows = (n + PER_ROW - 1) // PER_ROW
    cell_w, cell_h = 2 * (2 * CROP) + 12, 2 * CROP + 26
    sheet = Image.new('RGB', (PER_ROW * cell_w, max(1, rows * cell_h)), (18, 18, 24))
    dr = ImageDraw.Draw(sheet)

    def crop(im, x, y):
        x, y = int(round(x)), int(round(y))
        c = im.crop((x - CROP, y - CROP, x + CROP, y + CROP))
        d2 = ImageDraw.Draw(c)
        d2.line([(CROP - 8, CROP), (CROP + 8, CROP)], fill=(255, 230, 40), width=2)
        d2.line([(CROP, CROP - 8), (CROP, CROP + 8)], fill=(255, 230, 40), width=2)
        return c

    for idx, (cf, cr, dd) in enumerate(kept):
        r, c = divmod(idx, PER_ROW)
        x0, y0 = c * cell_w, r * cell_h
        sheet.paste(crop(imA, *cf['src_px']), (x0, y0))
        sheet.paste(crop(imB, *cf['dst_px']), (x0 + 2 * CROP + 8, y0))
        dr.text((x0 + 2, y0 + 2 * CROP + 3),
                f'#{idx} d{cf["depth_m"]:.0f}m z{cf["xyz"][2]:.0f} recip {dd:.2f}m',
                fill=(200, 200, 210))
    out = os.path.join(REPO, 'tools', 'generated', 'automatch_contact_sheet.png')
    sheet.save(out)
    outj = os.path.join(REPO, 'tools', 'generated', 'automatch_gold.json')
    tmp = outj + '.tmp'
    json.dump(dict(src=A, dst=B, recip_tol_m=RECIP_TOL, cluster_m=CLUSTER_M,
                   gold=[dict(xyz=k[0]['xyz'], src_px=k[0]['src_px'], dst_px=k[0]['dst_px'],
                              depth_m=k[0]['depth_m'], recip_m=round(k[2], 3)) for k in kept]),
              open(tmp, 'w'), indent=1)
    os.replace(tmp, outj)
    print(f'-> {out}\n-> {outj}')


if __name__ == '__main__':
    main()
