#!/usr/bin/env python3
"""leak_visibility_sheet.py — READ-ONLY. [CAMPAIGN-TRIAGE-V1, 2026-07-19]

Le triage de VISIBILITE de la campagne leaks: l'ordre de bataille comptait
les LMs dans le frustum, mais les frames leak sont souvent des interieurs/
rues occludees (Farm = une grange!, Alley = un mur + HUD dev, Hangar = un
habitacle). Ce tool rend chaque leak sous-marquee avec ses cibles projetees
(rouge=1obs jaune=2 vert=3+) -> planche-contact HTML. 5 secondes d'oeil par
frame pour garder les vraies fenetres sur le monde.

Usage:
  PYTHONPATH=. python3 tools/audit/leak_visibility_sheet.py [--max-marked 5]
  -> tools/generated/leak_triage/sheet.html
"""
import argparse
import json
import os
import re
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(THIS))
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, REPO)

from PIL import Image, ImageDraw
import common


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-marked', type=int, default=5)
    args = ap.parse_args()
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    obs_count = {}
    for cn, m in px.items():
        for l in m:
            obs_count[l] = obs_count.get(l, 0) + 1
    outdir = os.path.join(REPO, 'tools', 'generated', 'leak_triage')
    os.makedirs(outdir, exist_ok=True)
    cards = []
    for C, e in sorted(cams.items()):
        src = e.get('source') or ''
        is_leak = re.match(r'\d{4}-\d{2}-\d{2}', src) or re.match(r'^L\d', e.get('id') or '')
        if not is_leak:
            continue
        if len(px.get(C, {})) > args.max_marked:
            continue
        frame = os.path.join(REPO, 'frames', f'{C}.png')
        if not os.path.exists(frame):
            continue
        try:
            cam = common.get_cam(C)
            assert cam is not None
        except Exception:
            continue
        im = Image.open(frame).convert('RGB')
        dr = ImageDraw.Draw(im)
        n1 = n2 = n3 = 0
        for lm, le in lms.items():
            if not isinstance(le, dict) or not le.get('xyz'):
                continue
            p = cam.get_pixel(le['xyz'])
            if p is None or not (0 <= p[0] < cam.w and 0 <= p[1] < cam.h):
                continue
            oc = obs_count.get(lm, 0)
            if oc <= 1: col, _ = (248, 113, 113), None; n1 += 1
            elif oc == 2: col = (251, 191, 36); n2 += 1
            else: col = (74, 222, 128); n3 += 1
            dr.ellipse([p[0]-5, p[1]-5, p[0]+5, p[1]+5], outline=col, width=2)
        w = 900
        im2 = im.resize((w, int(im.height * w / im.width)))
        safe = C.replace(' ', '_').replace('(', '').replace(')', '').replace("'", '')
        im2.save(os.path.join(outdir, f'{safe}.jpg'), quality=72)
        cards.append((C, safe, len(px.get(C, {})), n1, n2, n3))
    cards.sort(key=lambda c: -(c[3] * 3 + c[4] * 2 + c[5]))
    html = ['<html><body style="background:#111;color:#ddd;font-family:monospace">',
            f'<h2>Triage visibilite campagne leaks — {len(cards)} cams (rouge=1obs jaune=2 vert=3+)</h2>',
            '<p>Garder les frames avec de VRAIES vues (skyline, vista); rejeter interieurs/murs/HUD-dev.</p>']
    for C, safe, nm, n1, n2, n3 in cards:
        html.append(f'<div style="margin:14px 0"><b>{C}</b> — {nm} markings, cibles frustum: '
                    f'<span style="color:#f87171">{n1}</span>/<span style="color:#fbbf24">{n2}</span>/'
                    f'<span style="color:#4ade80">{n3}</span><br><img src="{safe}.jpg" style="max-width:920px"></div>')
    html.append('</body></html>')
    open(os.path.join(outdir, 'sheet.html'), 'w').write('\n'.join(html))
    print(f'{len(cards)} cams -> {outdir}/sheet.html')


if __name__ == '__main__':
    main()
