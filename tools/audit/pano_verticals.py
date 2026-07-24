#!/usr/bin/env python3
"""pano_verticals.py — le test de rlx: fils a plomb projetes dans le pano.

rlx (2026-07-24): 'if you can render the winning camera with verticals, i
would try that. because if it looks wrong, there's something wrong about
the result... i would bet that in that 54 image, the verticals are more
tilted than the brator chimney and the lampposts near the boxville.'

On projette des VERTICALES MONDE (x, y fixes, z variable) passant par des
landmarks triangules repartis dans la frame, par-dessus la frame Panorama,
pour deux poses: la gagnante du sweep ancre (~53.6) et le monde 48 de rlx
(resolu par la meme grille, meme cout, pose capturee). Si la pose est
juste, les structures verticales de l'image (cheminees, tours, mats)
doivent etre PARALLELES aux fils a plomb projetes.
"""
import importlib.util
import json
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(THIS))
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, REPO)
os.chdir(REPO)

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import common

spec = importlib.util.spec_from_file_location('aj', os.path.join(REPO, 'tools', 'ambrosia_joint.py'))
aj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aj)

PANO = 'Ambrosia 02 (Panorama)'
# verticales aux landmarks triangules, repartis dans la frame
PLUMBS = ['Wheelabrator South Broward (TE)', 'USSM Smokestack (7)',
          'Daytona Beach Water Tower', '1500 Sonora Ave (Silo) (L)',
          '1500 Sonora Ave (Tank)', 'US Sugar Mill (Factory)',
          'Flat Water Tower', 'Very Tall Water Tower', 'Titan America']


def solve_cell(pano_fov, dz, rounds=30):
    px, lms, cams = aj.load()
    zone, anchors, ext_rays = aj.collect(px, lms, cams, use_brator=True, no_kalaga=False)
    sv = aj.Solver(zone, anchors, ext_rays, lms, cams, init='ours', use_corpus=False)
    _, det0 = sv.cost(collect_detail=True)
    for lm in [l for l, (P, e) in det0.items() if e is not None and e > 90.0]:
        zone.pop(lm, None)
    sv = aj.Solver(zone, anchors, ext_rays, lms, cams, init='ours', use_corpus=False)
    sv.theta[PANO][6] = pano_fov
    sv.bounds[PANO][6] = (pano_fov - 0.05, pano_fov + 0.05)
    for c in aj.AMB:
        sv.theta[c][2] += dz
        z = sv.theta[c][2]
        sv.bounds[c][2] = (z - 0.75, z + 0.75)
    cost = sv.descend(rounds=rounds, verbose=False)
    # re-trianguler les LMs de plumb dans CE monde-la (coherence interne)
    _, det = sv.cost(collect_detail=True)
    pts = {lm: det[lm][0] for lm in PLUMBS if lm in det}
    th = sv.theta[PANO]
    state = {'xyz': th[:3], 'ypr': th[3:6], 'fov': [th[6], None]}
    return state, pts, cost


def render(state, pts, tag, cost, out_name):
    cam = common.get_cam(PANO, state)
    im = Image.open(f'frames/{PANO}.png').convert('RGB')
    dr = ImageDraw.Draw(im)
    for lm, P in pts.items():
        line = []
        z0 = min(0.0, P[2] - 10)
        for z in np.linspace(z0, P[2] + 15, 60):
            pr = cam.get_pixel([float(P[0]), float(P[1]), float(z)])
            if pr is not None and -50 <= pr[0] <= im.width + 50:
                line.append((pr[0], pr[1]))
        if len(line) > 1:
            dr.line(line, fill='#22d3ee', width=3)
            pr = cam.get_pixel([float(P[0]), float(P[1]), float(P[2])])
            if pr is not None:
                dr.ellipse([pr[0] - 6, pr[1] - 6, pr[0] + 6, pr[1] + 6],
                           outline='#facc15', width=3)
    try:
        F = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 44)
        Fs = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 30)
    except Exception:
        F = Fs = ImageFont.load_default()
    dr.text((30, 24), tag, fill='#fff', font=F, stroke_width=5, stroke_fill='#000')
    dr.text((30, 84), f'cyan = projected world verticals (plumb lines) - anchored joint cost {cost:.1f}',
            fill='#e2e8f0', font=Fs, stroke_width=4, stroke_fill='#000')
    out = os.path.join(REPO, 'tools', 'generated', 'ambrosia_bounty', out_name)
    im.save(out)
    print('->', out, f'({tag}, cost {cost:.1f})')


def main():
    # monde gagnant (fov 54, dz +4 — le fond de vallee robuste)
    st, pts, cost = solve_cell(54.0, 4.0)
    print(f'54-world: pose {["%.2f" % v for v in st["xyz"]]} ypr {["%.2f" % v for v in st["ypr"]]}')
    render(st, pts, 'PANO @ hfov 54.0 (anchored winner)', cost, 'pano_verticals_54.png')
    # monde rlx (fov 48, meilleur dz de sa ligne = +12)
    st, pts, cost = solve_cell(48.0, 12.0)
    print(f'48-world: pose {["%.2f" % v for v in st["xyz"]]} ypr {["%.2f" % v for v in st["ypr"]]}')
    render(st, pts, 'PANO @ hfov 48.0 (rlx candidate, best dz)', cost, 'pano_verticals_48.png')


if __name__ == '__main__':
    main()
