#!/usr/bin/env python3
# next_clicks.py -- ACTIVE LEARNING [NEXT-CLICK-V1, 2026-07-09]. READ-ONLY.
#
# Pour chaque clic candidat (cam calibree C marquerait le LM solve L), on
# quantifie le gain d'information AVANT de le faire:
#   - un nouveau rayon contraint le plan perpendiculaire a sa direction,
#     avec sigma_ray ~= d * sigma_ang + sigma_pose(C)
#   - Lambda_new = Lambda_old + P / sigma_ray^2   (P = I - r r^T)
#   - gain = sigma_m(avant) - sigma_m(apres)
# Selection GREEDY sequentielle: chaque ligne = le meilleur clic MARGINAL en
# supposant les precedents faits (sinon le top-N = N fois le meme LM sature).
# Approximation LOCALE (diagonales de COVARIANCE-V1, correlations ignorees):
# echelle indicative, CLASSEMENT fiable — meme doctrine que sigma_report.
# Le tool ne sait pas si le feature est VISIBLE/identifiable dans le frame:
# skip humain legitime, passe au suivant. Le grind a l'aveugle est mort.
#
# Usage:
#   PYTHONPATH=. python3 tools/audit/next_clicks.py [--top 15]
#   PYTHONPATH=. python3 tools/audit/next_clicks.py --cam "Motorboats (B)"
#   PYTHONPATH=. python3 tools/audit/next_clicks.py --zone vice_city
import argparse
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from common import get_cam, cam_sigma_pos, is_excluded_marking

SIGMA_ANG_RAD = math.radians(3.0 / 60.0)   # bruit d'observation ~3 arcmin
D_MAX = 12000.0
RANK = {'anchor': 0, 'high': 1, 'medium': 2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=15)
    ap.add_argument('--cam', default=None, help='limiter aux clics sur cette cam')
    ap.add_argument('--zone', default=None)
    ap.add_argument('--min-gain', type=float, default=0.5, help='gain minimal (m)')
    args = ap.parse_args()

    lms = json.load(open('gtamapdata/landmarks.json'))
    px = json.load(open('gtamapdata/pixels.json'))
    cams_meta = json.load(open('gtamapdata/cameras.json'))
    cov = json.load(open('tools/generated/covariances.json'))['lms']
    tiers = json.load(open('tools/generated/confidence_tiers.json'))
    tc = tiers.get('cameras', tiers.get('cams', {}))

    elig = []
    for cn, meta in cams_meta.items():
        if args.cam and cn != args.cam:
            continue
        tier = (tc.get(cn) or {}).get('tier')
        sp = cam_sigma_pos(cn)
        if tier not in RANK and sp != 0.0:
            continue
        cam = get_cam(cn)
        if cam is None:
            continue
        elig.append((cn, meta, cam, sp if sp is not None else 10.0, tier or 'HUD'))

    rows = []
    for ln, ce in cov.items():
        e = lms.get(ln) or {}
        xyz = e.get('xyz')
        if not xyz:
            continue
        if args.zone and e.get('zone') != args.zone:
            continue
        sig = np.clip(np.asarray(ce['sigma_xyz_m'], float), 1e-3, None)
        s_old = float(np.linalg.norm(sig))
        if s_old < args.min_gain:
            continue
        L_old = np.diag(1.0 / sig ** 2)
        X = np.asarray(xyz, float)
        for cn, meta, cam, sp, tier in elig:
            if ln in px.get(cn, {}) or is_excluded_marking(cn, ln):
                continue
            p = cam.get_pixel(xyz)
            w, h = meta.get('size', [0, 0])
            if p is None or not (0 <= p[0] <= w and 0 <= p[1] <= h):
                continue
            O = np.asarray(meta['xyz'], float)
            r = X - O
            d = float(np.linalg.norm(r))
            if d > D_MAX or d < 1.0:
                continue
            r /= d
            s_ray = d * SIGMA_ANG_RAD + sp
            P = np.eye(3) - np.outer(r, r)
            L_new = L_old + P / (s_ray ** 2)
            s_new = float(math.sqrt(max(np.trace(np.linalg.inv(L_new)), 0.0)))
            gain = s_old - s_new
            if gain >= args.min_gain:
                rows.append((gain, s_old, s_new, ln, cn, tier, p, d, P, s_ray))

    lam = {}
    for gain, s_old, s_new, ln, cn, tier, p, d, P, s_ray in rows:
        if ln not in lam:
            sig = np.clip(np.asarray(cov[ln]['sigma_xyz_m'], float), 1e-3, None)
            lam[ln] = np.diag(1.0 / sig ** 2)
    pool = list(rows)
    chosen = []
    while pool and len(chosen) < args.top:
        best_i, best = None, None
        for i, (g0, s_old, s_new, ln, cn, tier, p, d, P, s_ray) in enumerate(pool):
            L = lam[ln]
            s_o = float(math.sqrt(max(np.trace(np.linalg.inv(L)), 0.0)))
            L2 = L + P / (s_ray ** 2)
            s_n = float(math.sqrt(max(np.trace(np.linalg.inv(L2)), 0.0)))
            g = s_o - s_n
            if best is None or g > best[0]:
                best_i, best = i, (g, s_o, s_n, ln, cn, tier, p, d, L2)
        g, s_o, s_n, ln, cn, tier, p, d, L2 = best
        if g < args.min_gain:
            break
        lam[ln] = L2
        chosen.append((g, s_o, s_n, ln, cn, tier, p, d))
        pool.pop(best_i)
    print(f'NEXT-CLICKS (greedy) — {len(chosen)} clics / {len(rows)} candidats '
          f'(gain marginal >= {args.min_gain}m)\n')
    tot = 0.0
    for k, (g, s_o, s_n, ln, cn, tier, p, d) in enumerate(chosen, 1):
        tot += g
        print(f'  #{k:2d} gain {g:6.1f}m  sig {s_o:6.1f}->{s_n:5.1f}m  {ln}')
        print(f'       -> marquer sur {cn} [{tier}] @ ({p[0]:.0f},{p[1]:.0f}), {d:.0f}m')
    print(f'\n  gain total du batch: {tot:.1f}m de sigma')


if __name__ == '__main__':
    main()
