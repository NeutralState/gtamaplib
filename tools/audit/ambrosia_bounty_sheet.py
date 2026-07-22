#!/usr/bin/env python3
"""ambrosia_bounty_sheet.py — les 4 vues du bounty #23, preuve visuelle.

Pour chaque cam Ambrosia: la frame + les LMs de zone reprojetes (croix) +
etiquettes des objets-cles du fil (Lollipop, smokestacks, silo, factory).
-> tools/generated/ambrosia_bounty/*.png — postables dans le fil Discord.
"""
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

AMB = ['Ambrosia 01 (Bikers)', 'Ambrosia 02 (Panorama)',
       'Ambrosia 04 (Fires)', 'Ambrosia Postcard (X)']
KEY = {'Daytona Beach Water Tower': 'LOLLIPOP', 'US Sugar Mill (Factory)': 'FACTORY',
       '1500 Sonora Ave (Silo) (L)': 'SILO', '1500 Sonora Ave (Tank)': 'TANK',
       'Wheelabrator South Broward (TE)': 'BRATOR', 'USSM Smokestack (7)': 'STACK7'}


def main():
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    outdir = os.path.join(REPO, 'tools', 'generated', 'ambrosia_bounty')
    os.makedirs(outdir, exist_ok=True)
    for C in AMB:
        fp = os.path.join(REPO, 'frames', f'{C}.png')
        if not os.path.exists(fp):
            continue
        cam = common.get_cam(C)
        img = Image.open(fp).convert('RGB')
        dr = ImageDraw.Draw(img)
        n = 0
        for lm, p in (px.get(C) or {}).items():
            if p is None or common.is_excluded_marking(C, lm):
                continue
            e = lms.get(lm)
            if not isinstance(e, dict) or not e.get('xyz'):
                continue
            pr = cam.get_pixel(e['xyz'])
            if pr is None:
                continue
            x, y = pr
            # clic = croix jaune, reprojection = croix cyan
            dr.line([(p[0] - 9, p[1]), (p[0] + 9, p[1])], fill='#facc15', width=2)
            dr.line([(p[0], p[1] - 9), (p[0], p[1] + 9)], fill='#facc15', width=2)
            dr.line([(x - 7, y - 7), (x + 7, y + 7)], fill='#22d3ee', width=2)
            dr.line([(x - 7, y + 7), (x + 7, y - 7)], fill='#22d3ee', width=2)
            if lm in KEY:
                dr.text((x + 10, y - 18), KEY[lm], fill='#4ade80')
            n += 1
        out = os.path.join(outdir, C.replace(' ', '_').replace('/', '_') + '.png')
        img.save(out)
        print(f'{C}: {n} LMs -> {out}')


if __name__ == '__main__':
    main()
