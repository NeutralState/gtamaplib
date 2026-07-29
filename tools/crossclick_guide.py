#!/usr/bin/env python3
"""crossclick_guide.py — guides epipolaires pour clics croises. [XCLICK-V1]

Etape 1 du pilote 'modeliser parfaitement': densifier les ANCRES (points
triangules 2+ cams), la seule vraie source de precision. Pour chaque mark
de la cam source, on projette son RAYON dans la frame cible: la ligne
coloree = l'endroit ou le meme point physique doit se trouver. Alexandre
clique dessus (meme nom de landmark) -> triangulation immediate.

Usage: PYTHONPATH=. python3 tools/crossclick_guide.py \\
         --src 'Ambrosia 01 (Bikers)' --dst 'Mount Kalaga ... (X)' \\
         --marks 'Mount Ambrosia (' --dmin 1500 --dmax 3600
Sortie: tools/generated/xclick_<dst>.png
"""
import argparse
import json
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import common

PALETTE = [(248, 113, 113), (251, 191, 36), (74, 222, 128), (56, 189, 248),
           (167, 139, 250), (244, 114, 182), (251, 146, 60), (94, 234, 212)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--dst', required=True)
    ap.add_argument('--marks', required=True, help='prefixe des marks source')
    ap.add_argument('--dmin', type=float, default=1500.0)
    ap.add_argument('--dmax', type=float, default=3600.0)
    args = ap.parse_args()

    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    cs = common.get_cam(args.src)          # gotcha #5: directions AVANT l'autre cam
    o_s = np.asarray(cs.xyz, float)
    rays = []
    for lm, p in sorted(px[args.src].items()):
        if not any(lm.startswith(m) for m in args.marks.split(',')):
            continue
        d = np.asarray(cs.get_pixel_direction(p), float)
        rays.append((lm, d / np.linalg.norm(d)))
    print(f'{len(rays)} marks source "{args.marks}*"')

    cd = common.get_cam(args.dst)
    im = Image.open(os.path.join(REPO, 'frames', f'{args.dst}.png')).convert('RGB')
    dr = ImageDraw.Draw(im)
    F = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 30)
    drawn = 0
    for k, (lm, d) in enumerate(rays):
        col = PALETTE[k % len(PALETTE)]
        pts = []
        for t in np.linspace(args.dmin, args.dmax, 60):
            pr = cd.get_pixel([float(v) for v in (o_s + t * d)])
            if pr is None or not (0 <= pr[0] < cd.w and 0 <= pr[1] < cd.h):
                continue
            pts.append((float(pr[0]), float(pr[1]), float(t)))
        if len(pts) < 2:
            print(f'  {lm}: hors champ de la cible')
            continue
        for i in range(len(pts) - 1):
            dr.line([pts[i][:2], pts[i + 1][:2]], fill=col, width=4)
        # graduations de profondeur
        for frac in (0, 0.5, 1.0):
            i = int(frac * (len(pts) - 1))
            x, y, t = pts[i]
            dr.ellipse([x - 5, y - 5, x + 5, y + 5], fill=col)
            if frac == 0:
                dr.text((x + 8, y - 34), f'{lm}  '
                        f'{pts[0][2]:.0f}-{pts[-1][2]:.0f}m',
                        fill=col, font=F, stroke_width=3, stroke_fill=(0, 0, 0))
        drawn += 1
    dr.text((24, 16), f'GUIDES EPIPOLAIRES — clics de {args.src} projetes ici: '
            f'cliquer le meme point physique SUR sa ligne (meme nom de landmark)',
            fill=(240, 244, 250), font=F, stroke_width=4, stroke_fill=(0, 0, 0))
    tag = args.marks.split(',')[0].strip().replace(' ', '').replace('(', '')
    out = os.path.join(REPO, 'tools', 'generated',
                       f'xclick_{tag}_dans_{args.dst.replace("/", "_")}.png')
    im.save(out)
    print(f'{drawn} guides -> {out}')


if __name__ == '__main__':
    main()
