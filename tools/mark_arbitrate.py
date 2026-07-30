#!/usr/bin/env python3
"""mark_arbitrate.py — arbitrer nos clics contre ceux de rlx. [MARK-ARB-V1]

Meme doctrine que l'arbitrage des poses (PGH-ARBITRAGE): on n'ecrase jamais
sur l'autorite, on tranche par TEMOIN INDEPENDANT.

Pour chaque mark deplace (le meme landmark cliqué a un endroit different
chez nous et chez rlx), on re-triangule le landmark avec la cam en litige
+ ses AUTRES observateurs, une fois avec notre pixel, une fois avec le sien,
et on mesure le residu perpendiculaire des rayons. Le pixel qui donne
l'intersection la plus serree gagne.

Cas ecartes:
  * landmark vu par < 2 autres cams  -> pas de temoin, on garde le notre
  * gain sous le seuil (--min-gain)  -> egalite, on garde le notre
  * la cam en litige n'est pas posee -> intriangulable

Sortie: le verdict mark par mark, puis --apply pour n'importer QUE les
gagnants de rlx.

Usage: PYTHONPATH=. python3 tools/mark_arbitrate.py [--apply] [--min-gain 1.2]
"""
import argparse
import collections
import json
import math
import os
import re
import subprocess
import sys
import tempfile

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
import common
from common import ray_ls_point

PAT = re.compile(r'\s*\(\(([-\d.]+), ([-\d.]+)\), "([^"]+)"\),?')
CAMPAT = re.compile(r'\s*"\[[^\]]+\] ([^"]+)": \[')


def upstream_marks(ref='upstream/main'):
    src = subprocess.run(['git', 'show', f'{ref}:gtamapdata.py'], cwd=REPO,
                         capture_output=True, text=True).stdout
    cam, out = None, collections.defaultdict(dict)
    for line in src.split('\n'):
        m = CAMPAT.match(line)
        if m:
            cam = m.group(1)
            continue
        m = PAT.match(line)
        if m and cam:
            out[cam][m.group(3)] = [float(m.group(1)), float(m.group(2))]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--min-gain', type=float, default=1.2,
                    help='facteur d amelioration minimal pour adopter le pixel de rlx')
    ap.add_argument('--min-move', type=float, default=3.0, help='deplacement min (px)')
    args = ap.parse_args()

    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    ups = upstream_marks()

    def posed(c):
        e = cams.get(c, {})
        return bool(e.get('xyz') and e.get('ypr') and any(e['ypr'])
                    and e.get('fov') and (e['fov'][0] or e['fov'][1]))

    # observateurs par landmark (pour trouver les temoins)
    obs = collections.defaultdict(list)
    for c, marks in px.items():
        if not posed(c):
            continue
        for lm, p in marks.items():
            if p is not None and not common.is_excluded_marking(c, lm):
                obs[lm].append(c)

    def perp(cam_list, pixels):
        rays = []
        for cn, p in zip(cam_list, pixels):
            cam = common.get_cam(cn)          # gotcha #5
            d = np.asarray(cam.get_pixel_direction(p), float)
            rays.append((np.asarray(cam.xyz, float), d / np.linalg.norm(d)))
        if len(rays) < 2:
            return None
        P = np.asarray(ray_ls_point(rays), float)
        if not np.all(np.isfinite(P)):
            return None
        return float(np.median([np.linalg.norm((P - o) - np.dot(P - o, d) * d)
                                for o, d in rays]))

    wins_rlx, wins_us, no_witness, ties = [], [], [], []
    for c, marks in ups.items():
        if c not in px or not posed(c):
            continue
        for lm, pr in marks.items():
            po = px[c].get(lm)
            if po is None:
                continue
            if abs(po[0] - pr[0]) < args.min_move and abs(po[1] - pr[1]) < args.min_move:
                continue
            others = [o for o in obs.get(lm, []) if o != c]
            if len(others) < 1:
                no_witness.append((c, lm))
                continue
            cam_list = [c] + others
            e_us = perp(cam_list, [po] + [px[o][lm] for o in others])
            e_rlx = perp(cam_list, [pr] + [px[o][lm] for o in others])
            if e_us is None or e_rlx is None:
                no_witness.append((c, lm))
                continue
            move = math.hypot(po[0] - pr[0], po[1] - pr[1])
            rec = (c, lm, po, pr, e_us, e_rlx, move, len(others))
            if e_rlx * args.min_gain < e_us:
                wins_rlx.append(rec)
            elif e_us * args.min_gain < e_rlx:
                wins_us.append(rec)
            else:
                ties.append(rec)

    print(f'{len(wins_rlx)} gagnes par rlx, {len(wins_us)} par nous, '
          f'{len(ties)} egalites, {len(no_witness)} sans temoin\n')
    print(f'{"cam":26s} {"landmark":30s} {"move":>6s} {"nous":>8s} {"rlx":>8s} {"n":>3s}')
    for c, lm, po, pr, eu, er, mv, n in sorted(wins_rlx, key=lambda r: r[4] - r[5],
                                               reverse=True)[:20]:
        print(f'  {c[:24]:24s} {lm[:30]:30s} {mv:5.0f}px {eu:7.1f}m {er:7.1f}m {n:3d}')
    if wins_us:
        print('\n  --- ou NOTRE clic gagne (non touche) ---')
        for c, lm, po, pr, eu, er, mv, n in sorted(wins_us, key=lambda r: r[5] - r[4],
                                                   reverse=True)[:8]:
            print(f'  {c[:24]:24s} {lm[:30]:30s} {mv:5.0f}px {eu:7.1f}m {er:7.1f}m {n:3d}')

    if not args.apply:
        print('\nDRY-RUN (--apply pour importer UNIQUEMENT les gagnants de rlx).')
        return
    for c, lm, po, pr, eu, er, mv, n in wins_rlx:
        px[c][lm] = pr
    p = os.path.join(REPO, 'gtamapdata', 'pixels.json')
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(px, f, indent=1, ensure_ascii=True)
    os.replace(tmp, p)
    print(f'\nAPPLIED: {len(wins_rlx)} clics de rlx adoptes (les autres restent les notres).')


if __name__ == '__main__':
    main()
