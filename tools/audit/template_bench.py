#!/usr/bin/env python3
# template_bench.py -- TEMPLATE-BENCH-V1 (2026-07-09). READ-ONLY.
#
# LE TRIBUNAL de la feature "template matching semi-auto" AVANT de la batir:
# pour chaque LM marque sur >=2 cams (avec frames locales + xyz), on prend le
# patch de la cam A autour de SON pixel, on le cherche dans la cam B autour de
# la projection du LM (multi-echelle, echelle initiale = ratio (f/d)_B/(f/d)_A,
# CLAHE pour normaliser les expositions), et on compare le pixel trouve au
# marking REEL de B = verite terrain. Verdict en nombres: hit-rate, erreur
# mediane, et surtout la relation score->erreur (quel seuil rend l'auto-suggest
# fiable). >70% sous 3px = la feature UI se construit; sinon elle meurt ici,
# 10 minutes de compute au lieu d'une soiree de debugging.
#
# Usage (necessite opencv: pip install opencv-python):
#   PYTHONPATH=. python3 tools/audit/template_bench.py [--n 150] [--seed 7]
import argparse
import json
import math
import os
import random
import sys

import numpy as np

try:
    import cv2
except ImportError:
    sys.exit("opencv manquant: pip install opencv-python")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from common import get_cam

FRAMES = os.path.join(ROOT, 'frames')
HALF = 48          # demi-patch en px source
WIN = 170          # demi-fenetre de recherche autour de la projection
SCALES = np.linspace(0.7, 1.4, 9)   # facteurs autour de l'echelle estimee

_clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
_cache = {}


def load_gray(cam):
    if cam in _cache:
        return _cache[cam]
    p = os.path.join(FRAMES, cam + '.png')
    if not os.path.exists(p):
        _cache[cam] = None
        return None
    img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    if img is not None:
        img = _clahe.apply(img)
    if len(_cache) > 24:
        _cache.clear()
    _cache[cam] = img
    return img


def f_px(meta):
    return (meta['size'][0] / 2.0) / math.tan(math.radians(meta['fov'][0] / 2.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=150, help='paires max a tester')
    ap.add_argument('--seed', type=int, default=7)
    args = ap.parse_args()

    lms = json.load(open('gtamapdata/landmarks.json'))
    px = json.load(open('gtamapdata/pixels.json'))
    cams_meta = json.load(open('gtamapdata/cameras.json'))

    obs_by_lm = {}
    for cn, marks in px.items():
        for ln, p in marks.items():
            obs_by_lm.setdefault(ln, []).append((cn, p))

    pairs = []
    for ln, obs in obs_by_lm.items():
        e = lms.get(ln) or {}
        if not e.get('xyz') or len(obs) < 2:
            continue
        for i in range(len(obs)):
            for j in range(len(obs)):
                if i != j:
                    pairs.append((ln, obs[i], obs[j], e['xyz']))
    random.Random(args.seed).shuffle(pairs)
    print(f'{len(pairs)} paires possibles, test de {min(args.n, len(pairs))}')

    results = []
    tested = skipped = 0
    for ln, (ca, pa), (cb, pb), xyz in pairs:
        if tested >= args.n:
            break
        A, B = load_gray(ca), load_gray(cb)
        if A is None or B is None:
            skipped += 1
            continue
        ma, mb = cams_meta[ca], cams_meta[cb]
        if not (ma.get('fov') and ma['fov'][0] and mb.get('fov') and mb['fov'][0]
                and ma.get('size') and mb.get('size')):
            skipped += 1
            continue
        cam_b = get_cam(cb)
        proj = cam_b.get_pixel(xyz)
        if proj is None:
            skipped += 1
            continue
        ax, ay = int(round(pa[0])), int(round(pa[1]))
        if not (HALF <= ax < A.shape[1] - HALF and HALF <= ay < A.shape[0] - HALF):
            skipped += 1
            continue
        patch = A[ay - HALF:ay + HALF, ax - HALF:ax + HALF]
        da = math.dist(xyz, ma['xyz'])
        db = math.dist(xyz, mb['xyz'])
        s_est = (f_px(mb) / db) / (f_px(ma) / da)
        gx, gy = int(round(proj[0])), int(round(proj[1]))
        best = None
        for sf in SCALES:
            s = s_est * sf
            if not 0.15 <= s <= 6.0:
                continue
            tp = cv2.resize(patch, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
            th, tw = tp.shape
            if th < 12 or tw < 12 or th > 2 * WIN or tw > 2 * WIN:
                continue
            x0, y0 = max(0, gx - WIN), max(0, gy - WIN)
            x1, y1 = min(B.shape[1], gx + WIN), min(B.shape[0], gy + WIN)
            win = B[y0:y1, x0:x1]
            if win.shape[0] <= th or win.shape[1] <= tw:
                continue
            res = cv2.matchTemplate(win, tp, cv2.TM_CCOEFF_NORMED)
            _, mx, _, ml = cv2.minMaxLoc(res)
            fx, fy = x0 + ml[0] + tw / 2.0, y0 + ml[1] + th / 2.0
            if best is None or mx > best[0]:
                best = (mx, fx, fy, s)
        if best is None:
            skipped += 1
            continue
        score, fx, fy, s_used = best
        err = math.hypot(fx - pb[0], fy - pb[1])
        results.append((err, score, ln, ca, cb, s_est))
        tested += 1
        if tested % 25 == 0:
            print(f'  ... {tested} testees')

    if not results:
        sys.exit('aucune paire testable (frames manquantes?)')
    errs = np.array([r[0] for r in results])
    scores = np.array([r[1] for r in results])
    print(f'\n══ TEMPLATE-BENCH-V1 — {len(results)} paires (skip {skipped}) ══')
    print(f'  erreur mediane: {np.median(errs):.1f}px | moyenne {errs.mean():.1f}px')
    for t in (3, 6, 12):
        print(f'  <= {t:2d}px : {100 * (errs <= t).mean():.0f}%')
    print('\n  relation score -> fiabilite (pour le seuil auto-suggest):')
    for smin in (0.5, 0.6, 0.7, 0.8):
        m = scores >= smin
        if m.sum() >= 5:
            print(f'  score>={smin}: {m.sum():3d} paires, {100 * (errs[m] <= 3).mean():.0f}% sous 3px, '
                  f'mediane {np.median(errs[m]):.1f}px')
    bad = sorted(results, reverse=True)[:5]
    print('\n  pires cas:')
    for err, sc, ln, ca, cb, s_est in bad:
        print(f'  {err:6.0f}px score {sc:.2f}  {ln}  {ca} -> {cb} (s_est {s_est:.2f})')
    print('\nVERDICT: si score>=0.7 donne >70% sous 3px, la feature UI se construit.')


if __name__ == '__main__':
    main()
