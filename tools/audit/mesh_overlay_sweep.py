#!/usr/bin/env python3
"""mesh_overlay_sweep.py — READ-ONLY. [MESH-SWEEP-V1, 2026-07-18]

Rend le wireframe d'un building procedural dans TOUTES les cams qui le voient
(frustum + frame presente), en crops -> contact sheet HTML. Deux usages:

1. VALIDER un mesh: l'oeil compare wireframe vs batiment dans chaque cam saine.
2. DIAGNOSTIQUER une cam: sur un mesh valide, le desalignement = erreur de
   pose de la cam — des dizaines de correspondances gratuites sans marking
   (idee du 2026-07-18, nee de la revue SPC ou 32/40 cams etaient occludees
   mais Convertible/Peacock voyaient le mesh en entier).

Usage:
  PYTHONPATH=. python3 tools/audit/mesh_overlay_sweep.py "Stephen P. Clark Government Center"
  PYTHONPATH=. python3 tools/audit/mesh_overlay_sweep.py --all      # tous les buildings
  -> tools/generated/mesh_sweep/<building>/*.png + sheet.html
"""
import argparse
import json
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(THIS))
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, REPO)

from PIL import Image, ImageDraw
import common

MIN_APPARENT_PX = 60
MARGIN = 120


def sweep(building, edges, color, outdir):
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    os.makedirs(outdir, exist_ok=True)
    cards = []
    for C in sorted(cams):
        frame = os.path.join(REPO, 'frames', f'{C}.png')
        if not os.path.exists(frame):
            continue
        try:
            cam = common.get_cam(C)
            assert cam is not None
        except Exception:
            continue
        pts = []
        for a, b in edges:
            for p3 in (a, b):
                p = cam.get_pixel(p3)
                if p is not None:
                    pts.append(p)
        if not pts:
            continue
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        if max(xs) < 0 or min(xs) > cam.w or max(ys) < 0 or min(ys) > cam.h:
            continue
        if (max(ys) - min(ys)) < MIN_APPARENT_PX:
            continue
        im = Image.open(frame).convert('RGB')
        dr = ImageDraw.Draw(im)
        rgb = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        for a, b in edges:
            pa, pb = cam.get_pixel(a), cam.get_pixel(b)
            if pa is None or pb is None:
                continue
            dr.line([tuple(pa), tuple(pb)], fill=rgb, width=2)
        box = (max(0, int(min(xs)) - MARGIN), max(0, int(min(ys)) - MARGIN),
               min(im.width, int(max(xs)) + MARGIN), min(im.height, int(max(ys)) + MARGIN))
        if box[2] - box[0] < 50 or box[3] - box[1] < 50:
            continue
        crop = im.crop(box)
        if crop.width > 800:
            crop = crop.resize((800, int(crop.height * 800 / crop.width)))
        safe = C.replace(' ', '_').replace('(', '').replace(')', '').replace("'", '')
        fn = f'{safe}.png'
        crop.save(os.path.join(outdir, fn))
        cards.append((C, fn, max(ys) - min(ys)))
    cards.sort(key=lambda x: -x[2])
    html = ['<html><body style="background:#111;color:#ddd;font-family:monospace">',
            f'<h2>{building} — {len(cards)} cams</h2>']
    for C, fn, h in cards:
        html.append(f'<div style="display:inline-block;margin:8px;vertical-align:top">'
                    f'<div>{C} ({h:.0f}px)</div><img src="{fn}" style="max-width:420px"></div>')
    html.append('</body></html>')
    open(os.path.join(outdir, 'sheet.html'), 'w').write('\n'.join(html))
    print(f'{building}: {len(cards)} cams -> {outdir}/sheet.html')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('building', nargs='?')
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()
    bp = json.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')))
    targets = [k for k in bp if not k.startswith('_')] if args.all else [args.building]
    if not targets or targets == [None]:
        sys.exit('building requis (ou --all)')
    for b in targets:
        m = bp.get(b)
        if not m or not m.get('world_edges'):
            print(f'{b}: pas de world_edges — skip'); continue
        out = os.path.join(REPO, 'tools', 'generated', 'mesh_sweep', b.replace(' ', '_'))
        sweep(b, m['world_edges'], m.get('color', '#4ade80'), out)


if __name__ == '__main__':
    main()
