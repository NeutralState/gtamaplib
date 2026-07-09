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
# [NEXT-CLICK-V2] --pose --cam X: le DUAL — gain sur la POSE de la cam.
# Prior honnete reconstruit des observations existantes (Jacobien numerique),
# pas des covariances flattees par les barrieres (lecon JD05). La diversite
# ANGULAIRE bat la proximite (vecu Rooftop: un pont des Keys a 9.4km vaut
# 20.8m de gain — direction orthogonale au cluster downtown).
#
# Usage:
#   PYTHONPATH=. python3 tools/audit/next_clicks.py [--top 15] [--zone Z]
#   PYTHONPATH=. python3 tools/audit/next_clicks.py --pose --cam "NomCam"
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

from common import get_cam, cam_sigma_pos, is_excluded_marking, lm_sigma_m

SIGMA_ANG_RAD = math.radians(3.0 / 60.0)   # bruit d'observation ~3 arcmin
D_MAX = 12000.0
RANK = {'anchor': 0, 'high': 1, 'medium': 2}


def pose_mode(cam_name, top, min_gain):
    # ── NEXT-CLICK-V2 [2026-07-09]: GAIN DE POSE — le dual du V1 ────────────
    # Pour consolider une cam faible: chaque clic candidat (LM solide visible)
    # ajoute Lambda_pose += J^T J / sigma_eff^2, ou J = d(pixel)/d(pose 7p)
    # numerique et sigma_eff^2 = sigma_clic_px^2 + (sigma_LM projete en px)^2
    # — cliquer un LM mou enseigne peu. Greedy sur sigma_pos de la cam.
    import numpy as _np
    lms = json.load(open('gtamapdata/landmarks.json'))
    px = json.load(open('gtamapdata/pixels.json'))
    meta = json.load(open('gtamapdata/cameras.json'))[cam_name]
    # Prior HONNETE [lecon JD05/barrieres]: les sigmas de covariances.json
    # incluent les priors du BA (flattes). Ici Lambda_old = ce que les
    # observations EXISTANTES de la cam contraignent vraiment (meme Jacobien
    # numerique sur ses markings de LM solides) + prior faible. La geometrie
    # parle, pas les barrieres.
    sig7 = _np.array([50., 50., 50., 3., 3., 3., 3.], float)
    Lam = _np.diag(1.0 / sig7 ** 2)
    w, h = meta['size']
    f_px = (w / 2.0) / math.tan(math.radians(meta['fov'][0] / 2.0))
    SIG_CLICK_PX = 2.0
    EPS = [0.5, 0.5, 0.5, 0.02, 0.02, 0.02, 0.02]  # m, m, m, deg x4

    def proj(state, xyz):
        cam = get_cam(cam_name, cam_state=state)
        return cam.get_pixel(xyz)

    base_state = {'xyz': list(meta['xyz']), 'ypr': list(meta['ypr']),
                  'fov': [meta['fov'][0], None]}

    def jac_for(xyz_lm):
        p0 = proj(base_state, xyz_lm)
        if p0 is None or not (0 <= p0[0] <= w and 0 <= p0[1] <= h):
            return None, None
        J = _np.zeros((2, 7))
        for i in range(7):
            st2 = {'xyz': list(base_state['xyz']), 'ypr': list(base_state['ypr']),
                   'fov': [base_state['fov'][0], None]}
            if i < 3:
                st2['xyz'][i] += EPS[i]
            elif i < 6:
                st2['ypr'][i - 3] += EPS[i]
            else:
                st2['fov'][0] += EPS[i]
            p1 = proj(st2, xyz_lm)
            if p1 is None:
                return None, None
            J[0, i] = (p1[0] - p0[0]) / EPS[i]
            J[1, i] = (p1[1] - p0[1]) / EPS[i]
        return J, p0

    n_exist = 0
    for ln in px.get(cam_name, {}):
        e = lms.get(ln)
        if not e or not e.get('xyz') or is_excluded_marking(cam_name, ln):
            continue
        s_lm = lm_sigma_m(ln)
        if s_lm is None:
            s_lm = 5.0
        d = math.dist(e['xyz'], meta['xyz'])
        if d < 1.0:
            continue
        J, p0 = jac_for(e['xyz'])
        if J is None:
            continue
        sig_lm_px = (s_lm / d) * f_px
        Lam += (J.T @ J) / (SIG_CLICK_PX ** 2 + sig_lm_px ** 2)
        n_exist += 1
    cands = []
    for ln, e in lms.items():
        if not e or not e.get('xyz') or ln in px.get(cam_name, {}):
            continue
        if is_excluded_marking(cam_name, ln):
            continue
        s_lm = lm_sigma_m(ln)
        if s_lm is None:
            s_lm = 5.0
        d = math.dist(e['xyz'], meta['xyz'])
        if d < 1.0 or d > D_MAX:
            continue
        J, p0 = jac_for(e['xyz'])
        if J is None:
            continue
        sig_lm_px = (s_lm / d) * f_px
        w_eff = 1.0 / (SIG_CLICK_PX ** 2 + sig_lm_px ** 2)
        cands.append((ln, p0, d, s_lm, J, w_eff))

    def spos(L):
        try:
            S = _np.linalg.inv(L)
            return float(math.sqrt(max(S[0, 0] + S[1, 1] + S[2, 2], 0.0)))
        except Exception:
            return float('inf')

    print(f'NEXT-CLICK-V2 (gain de POSE) — {cam_name}')
    print(f'  sigma_pos GEOMETRIQUE (obs existantes: {n_exist}): {spos(Lam):.1f}m | {len(cands)} clics candidats\n')
    chosen = 0
    while cands and chosen < top:
        s0 = spos(Lam)
        best = None
        for i, (ln, p0, d, s_lm, J, w_eff) in enumerate(cands):
            L2 = Lam + (J.T @ J) * w_eff
            g = s0 - spos(L2)
            if best is None or g > best[0]:
                best = (g, i, L2)
        g, i, L2 = best
        if g < min_gain:
            break
        ln, p0, d, s_lm, J, w_eff = cands.pop(i)
        Lam = L2
        chosen += 1
        print(f'  #{chosen} gain {g:6.1f}m  sigma_pos -> {spos(Lam):5.1f}m   '
              f'{ln} (s_lm {s_lm:.1f}m)')
        print(f'      -> @({p0[0]:.0f},{p0[1]:.0f}), {d:.0f}m')
    print(f'\n  sigma_pos final si tout clique: {spos(Lam):.1f}m')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=15)
    ap.add_argument('--cam', default=None, help='limiter aux clics sur cette cam')
    ap.add_argument('--zone', default=None)
    ap.add_argument('--min-gain', type=float, default=0.5, help='gain minimal (m)')
    ap.add_argument('--pose', action='store_true',
                    help='NEXT-CLICK-V2: gain de POSE de --cam (consolidation)')
    args = ap.parse_args()
    if args.pose:
        if not args.cam:
            sys.exit('--pose exige --cam')
        pose_mode(args.cam, args.top, args.min_gain)
        return

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
