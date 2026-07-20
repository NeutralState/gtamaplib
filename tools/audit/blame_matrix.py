#!/usr/bin/env python3
"""blame_matrix.py — l'arbitre mesh-vs-cam. [BLAME-MATRIX-V2, READ-ONLY]

V1 (matin du 07-19): decomposition jointe des residus par CELLULE (cam x
building) en effet cam + translation monde 2D. Trois faiblesses mesurees le
jour meme: (a) dz des buildings gele -> une erreur de hauteur fuyait en
dpitch sur toutes les cams (le +0.05 deg systematique du premier run);
(b) la rotation d'un building est INVISIBLE au niveau cellule (elle s'annule
dans la mediane des coins); (c) le consensus moyenne les dissidents — le
'Portofino 2.9m' etait en verite un split proche/loin (tension de frame
Keys), pas un mesh a bouger.

V2 — ce qui change:
  1. equations par OBSERVATION (chaque clic de coin), plus par cellule.
  2. buildings a 4 params: dE dN dU dtheta (rotation autour du centroide).
  3. INCERTITUDES formelles: Cov = sigma0^2 (A'WA + R)^-1 apres robuste —
     chaque verdict est un ratio signal/sigma, plus un seuil arbitraire.
  4. DETECTEUR DE DISSIDENCE par building: proposition 2D par cam (SVD
     tronquee — la composante long-rayon d'une cam seule est aveugle),
     chi2 d'homogeneite; si heterogene -> split par distance (la signature
     des tensions de frame zonales), PAS de proposition de deplacement.
  5. les BORDS comme 2e famille: sur les frames-juges nettes, le biais 2D
     du mesh (moindres carres offsets/normales, info matrice anisotrope —
     les aretes verticales ne contraignent que l'horizontal) entre dans le
     meme systeme. La ou les clics sont minces, les bords tranchent.
  6. contexte hors-mesh ASSAINI: mediane trimmed (les LMs en conflit de
     frame connus ne comptent plus comme 'mauvaise cam').
  7. sortie actionnable: la commande a rouler par verdict.

READ-ONLY: l'outil accuse, les corrections passent par fit_mesh /
edge_solve / refits et leurs gardes.

Usage:
  PYTHONPATH=. python3 tools/audit/blame_matrix.py [--buildings "..."]
      [--no-edges] [--min-obs 1]
"""
import argparse
import json
import math
import os
import statistics
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(THIS))
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, REPO)

import numpy as np
import common

RIDGE = 0.5           # arcmin d'a-priori 'rien ne bouge'
CAM_UNIT = 0.1        # inconnues cam en 0.1 deg
TH_UNIT = 0.5         # inconnues dtheta en 0.5 deg
HUBER_K = 3.0
EDGE_SIGMA_PX = 3.0   # bruit d'un echantillon de bord
EDGE_N_CAP = 200      # plafond d'echantillons effectifs par cellule bord
JUDGE_EDGE_CAMS = ['Port Vice City (A)', 'Port Vice City (B)',
                   'Vice City 03 (Basketball)', 'Shitzu Squalo 01 (Bay)']


def load_data(buildings, min_obs):
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    cams_json = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))

    members = {}
    for b in buildings:
        m = {n: np.array(e['xyz'], float) for n, e in lms.items()
             if n.startswith(b + ' (') and isinstance(e, dict) and e.get('xyz')}
        if len(m) >= 2:
            members[b] = m
    corner_lms = {n for m in members.values() for n in m}

    obs = []       # (cam, building, lm, pix, xyz)
    ctx_other = {} # cam -> [arcmin residuals hors-mesh]
    cam_cache = {}
    for cam_name, marks in px.items():
        if cam_name not in cams_json:
            continue
        try:
            cam = common.get_cam(cam_name)
            assert cam is not None
        except Exception:
            continue
        cam_cache[cam_name] = cam
        for lm, pix in marks.items():
            if pix is None or common.is_excluded_marking(cam_name, lm):
                continue
            e = lms.get(lm)
            if not isinstance(e, dict) or not e.get('xyz'):
                continue
            hit = next((b for b in members if lm in members[b]), None)
            if hit is None:
                if lm not in corner_lms:
                    a, _, _ = common.residual_dual(cam, list(pix), e['xyz'])
                    if a is not None:
                        ctx_other.setdefault(cam_name, []).append(a)
                continue
            p = cam.get_pixel(e['xyz'])
            if p is None:
                continue
            obs.append((cam_name, hit, lm, np.array(pix, float),
                        np.array(e['xyz'], float)))
    # filtre min_obs par cellule
    from collections import Counter
    cellcount = Counter((c, b) for c, b, _, _, _ in obs)
    obs = [o for o in obs if cellcount[(o[0], o[1])] >= min_obs]
    return members, obs, ctx_other, cam_cache, cams_json


def world_jacobian(cam, xyz):
    """G (2x3): px par metre E/N/U au point xyz. None si hors-champ."""
    p0 = cam.get_pixel(list(xyz))
    if p0 is None:
        return None, None
    G = np.zeros((2, 3))
    for i, d in enumerate(np.eye(3)):
        p1 = cam.get_pixel((np.asarray(xyz) + d).tolist())
        if p1 is None:
            return None, None
        G[:, i] = [p1[0] - p0[0], p1[1] - p0[1]]
    return G, np.asarray(p0, float)


def cam_jacobian(cam_name, entry, xyz):
    """K (2x2): px par CAM_UNIT deg de yaw/pitch, au point xyz."""
    cam0 = common.get_cam(cam_name)
    p0 = cam0.get_pixel(list(xyz))
    if p0 is None:
        return None
    K = np.zeros((2, 2))
    for i in range(2):
        ypr = list(entry['ypr']); ypr[i] += CAM_UNIT
        c2 = common.get_cam(cam_name, {'xyz': entry['xyz'], 'ypr': ypr, 'fov': entry['fov']})
        p1 = c2.get_pixel(list(xyz))
        if p1 is None:
            return None
        K[:, i] = [p1[0] - p0[0], p1[1] - p0[1]]
    return K


def build_system(members, obs, cam_cache, cams_json, use_edges):
    blds = sorted({b for _, b, _, _, _ in obs})
    cams = sorted({c for c, _, _, _, _ in obs})
    centroids = {b: np.mean(list(members[b].values()), axis=0) for b in blds}
    ci = {c: i for i, c in enumerate(cams)}
    bi = {b: i for i, b in enumerate(blds)}
    ncol = 2 * len(cams) + 4 * len(blds)

    rows_A, rows_r, meta = [], [], []
    zhat = np.array([0.0, 0.0, 1.0])
    for c, b, lm, pix, xyz in obs:
        cam = cam_cache[c]
        K = cam_jacobian(c, cams_json[c], xyz)
        G, p0 = world_jacobian(cam, xyz)
        if K is None or G is None:
            continue
        apx = 6.0 / max(float(np.linalg.norm(K[:, 0])), 1e-6)  # arcmin/px
        arm = np.cross(zhat, xyz - centroids[b])                # dtheta lever
        col_th = G @ arm * math.radians(TH_UNIT)
        A2 = np.zeros((2, ncol))
        A2[:, 2 * ci[c]:2 * ci[c] + 2] = K
        j0 = 2 * len(cams) + 4 * bi[b]
        A2[:, j0:j0 + 3] = G
        A2[:, j0 + 3] = col_th
        r2 = pix - p0
        rows_A.append(A2 * apx); rows_r.append(r2 * apx)
        meta.append(dict(cam=c, bld=b, lm=lm, family='click', apx=apx,
                         G=G, K=K, r=r2, dist=float(np.linalg.norm(xyz - np.asarray(cam.xyz)))))

    n_edge_cells = 0
    if use_edges:
        try:
            from edgefit_core import FrameCtx, sample as edge_sample, build_hulls
            bp = json.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')))
            for c in JUDGE_EDGE_CAMS:
                if c not in ci:
                    continue
                if not os.path.exists(os.path.join(REPO, 'frames', f'{c}.png')):
                    continue
                ctx = FrameCtx(c)
                meshes = {b: bp[b]['world_edges'] for b in blds if b in bp}
                hulls = build_hulls(ctx, meshes)
                for b, edges in meshes.items():
                    res = edge_sample(ctx, edges, self_name=b, hulls=hulls)
                    off, nrm = res['offsets'], res['normals']
                    if res['n_sil'] < 50 or not len(nrm):
                        continue
                    M = nrm.T @ nrm
                    v = nrm.T @ off
                    try:
                        t2 = np.linalg.solve(M, v)   # biais 2D px (truth - proj)
                    except np.linalg.LinAlgError:
                        continue
                    scale = min(1.0, EDGE_N_CAP / res['n_sil'])
                    L = np.linalg.cholesky(M * scale / EDGE_SIGMA_PX ** 2)
                    cen = centroids[b]
                    K = cam_jacobian(c, cams_json[c], cen)
                    G, _ = world_jacobian(cam_cache[c], cen)
                    if K is None or G is None:
                        continue
                    arm = np.cross(zhat, np.zeros(3))  # rotation ~ invisible au centroide
                    A2 = np.zeros((2, ncol))
                    A2[:, 2 * ci[c]:2 * ci[c] + 2] = K
                    j0 = 2 * len(cams) + 4 * bi[b]
                    A2[:, j0:j0 + 3] = G
                    apx = 6.0 / max(float(np.linalg.norm(K[:, 0])), 1e-6)
                    # equations en unites 'sigma de bord', deja normalisees par L
                    rows_A.append(L.T @ A2); rows_r.append(L.T @ t2)
                    meta.append(dict(cam=c, bld=b, lm='[edges]', family='edge', apx=apx,
                                     G=G, K=K, r=t2,
                                     dist=float(np.linalg.norm(cen - np.asarray(cam_cache[c].xyz))),
                                     n_sil=res['n_sil']))
                    n_edge_cells += 1
        except Exception as ex:
            print(f'(bords desactives: {ex})')
    return cams, blds, centroids, ci, bi, ncol, rows_A, rows_r, meta, n_edge_cells


def robust_solve(rows_A, rows_r, ncol):
    A = np.vstack(rows_A); r = np.concatenate(rows_r)
    n_eq_groups = len(rows_A)
    wts = np.ones(n_eq_groups)

    def solve(w):
        W = np.repeat(w, 2)
        Aw, rw = A * W[:, None], r * W
        H = Aw.T @ Aw + RIDGE ** 2 * np.eye(ncol)
        return np.linalg.solve(H, Aw.T @ rw), H

    x, H = solve(wts)
    for _ in range(2):
        resid = (A @ x - r).reshape(-1, 2)
        err = np.linalg.norm(resid, axis=1)
        med = max(float(np.median(err)), 1e-6)
        wts = np.minimum(1.0, HUBER_K * med / np.maximum(err, 1e-9))
        x, H = solve(wts)
    resid = (A @ x - r).reshape(-1, 2)
    W = np.repeat(wts, 2)
    dof = max(1, int(2 * n_eq_groups - ncol))
    sigma0 = math.sqrt(float(np.sum((W * (A @ x - r)) ** 2)) / dof)
    cov = sigma0 ** 2 * np.linalg.inv(H)
    return x, cov, resid, wts, sigma0


def per_cam_proposals(meta, x, ci, bi, ncams, bld):
    """Proposition 2D (E,N) par cam pour un building, residus apres effet cam.
    SVD tronquee: une cam seule est aveugle le long de son rayon."""
    props = {}
    for c in sorted({m['cam'] for m in meta if m['bld'] == bld and m['family'] == 'click'}):
        rows = [m for m in meta if m['bld'] == bld and m['cam'] == c and m['family'] == 'click']
        if not rows:
            continue
        Gs = np.vstack([m['G'][:, :2] * m['apx'] for m in rows])
        rs = np.concatenate([(m['r'] - m['K'] @ x[2 * ci[c]:2 * ci[c] + 2]) * m['apx'] for m in rows])
        U, S, Vt = np.linalg.svd(Gs, full_matrices=False)
        keep = S > 0.25 * S[0]
        t = Vt[keep].T @ ((U[:, keep].T @ rs) / S[keep])
        # info dans le sous-espace garde
        Info = Vt[keep].T @ np.diag(S[keep] ** 2) @ Vt[keep]
        props[c] = (t, Info, np.mean([m['dist'] for m in rows]), len(rows))
    return props


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--buildings', default=None)
    ap.add_argument('--min-obs', type=int, default=1)
    ap.add_argument('--no-edges', action='store_true')
    args = ap.parse_args()

    if args.buildings:
        buildings = [b.strip() for b in args.buildings.split(',')]
    else:
        bp = json.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')))
        buildings = sorted(bp.keys())

    members, obs, ctx_other, cam_cache, cams_json = load_data(buildings, args.min_obs)
    if not obs:
        sys.exit('aucune observation')
    cams, blds, centroids, ci, bi, ncol, rows_A, rows_r, meta, n_edge = \
        build_system(members, obs, cam_cache, cams_json, not args.no_edges)
    x, cov, resid, wts, sigma0 = robust_solve(rows_A, rows_r, ncol)
    sig = np.sqrt(np.maximum(np.diag(cov), 0))

    n_click = sum(1 for m in meta if m['family'] == 'click')
    print(f'BLAME-MATRIX-V2: {len(cams)} cams x {len(blds)} buildings — '
          f'{n_click} obs clic + {n_edge} cellules bord, sigma0 {sigma0:.2f}\'')

    # ── VERDICTS MESH
    print('\n── VERDICTS MESH (dE dN dU dtheta ± sigma; dissidence testee):')
    for b in blds:
        j0 = 2 * len(cams) + 4 * bi[b]
        dE, dN, dU = x[j0], x[j0 + 1], x[j0 + 2]
        dTH = x[j0 + 3] * TH_UNIT
        sE, sN, sU = sig[j0], sig[j0 + 1], sig[j0 + 2]
        sTH = sig[j0 + 3] * TH_UNIT
        mag = math.hypot(dE, dN)
        smag = math.hypot(sE, sN) + 1e-9
        wit = sorted({m['cam'] for m in meta if m['bld'] == b})
        azs = []
        for c in wit:
            d = centroids[b] - np.asarray(cam_cache[c].xyz)
            azs.append(math.degrees(math.atan2(-d[0], d[1])) % 360)
        spread = 0.0
        if len(azs) > 1:
            s = sorted(azs)
            gaps = [(s[(i + 1) % len(s)] - s[i]) % 360 for i in range(len(s))]
            spread = 360.0 - max(gaps)

        # dissidence: chi2 d'homogeneite des propositions par cam
        props = per_cam_proposals(meta, x, ci, bi, len(cams), b)
        splitmsg = ''
        if len(props) >= 4:
            ts = list(props.values())
            Wsum = sum(p[1] for p in ts)
            tbar = np.linalg.solve(Wsum + 1e-9 * np.eye(2), sum(p[1] @ p[0] for p in ts))
            chi2 = sum(float((p[0] - tbar) @ p[1] @ (p[0] - tbar)) for p in ts) / max(sigma0 ** 2, 1e-9)
            dofc = 2 * (len(ts) - 1)
            # split proche/loin evalue en METRES (doctrine dual-metric: les
            # dissidents lointains pesent peu en arcmin mais leur desaccord
            # metrique est la signature des tensions de frame zonales)
            dists = sorted((p[2], c) for c, p in props.items())
            medd = dists[len(dists) // 2][0]
            near = [c for c, p in props.items() if p[2] <= medd]
            far = [c for c, p in props.items() if p[2] > medd]
            def gmean(group):
                w = np.array([math.sqrt(props[c][3]) for c in group])
                pts = np.array([props[c][0] for c in group])
                return (pts * w[:, None]).sum(axis=0) / w.sum()
            tn, tf = gmean(near), gmean(far)
            gap = float(np.linalg.norm(tn - tf))
            if chi2 > 3.0 * dofc or gap > 2.5:
                splitmsg = (f'\n        DISSIDENCE (chi2 {chi2:.0f}/dof {dofc}, gap {gap:.1f}m): '
                            f'proches ({len(near)} cams, <{medd:.0f}m) disent [{tn[0]:+.1f},{tn[1]:+.1f}]m, '
                            f'lointaines ({len(far)}) [{tf[0]:+.1f},{tf[1]:+.1f}]m '
                            f'= tension de FRAME zonale, pas un mesh a bouger')
        nsig = mag / smag
        if splitmsg:
            verdict = 'ARBITRAGE'
        elif nsig < 2.5 or mag < 0.5:
            verdict = 'stable'
        else:
            verdict = f'A BOUGER ({nsig:.1f} sigma) -> fit_mesh "{b}" [--dz]'
        flag = ' [FRAGILE azimuts]' if (len(wit) < 3 or spread < 60) else ''
        print(f'   {b[:36]:36} dE{dE:+6.2f}±{sE:.2f} dN{dN:+6.2f}±{sN:.2f} '
              f'dU{dU:+5.2f}±{sU:.2f} dth{dTH:+6.3f}±{sTH:.3f}deg '
              f'({len(wit)} cams/{spread:.0f}deg) {verdict}{flag}{splitmsg}')

    # ── VERDICTS CAM
    print('\n── VERDICTS CAM (dyaw dpitch ± sigma; contexte hors-mesh trimmed):')
    out = []
    for c in cams:
        dyaw = x[2 * ci[c]] * CAM_UNIT; dpitch = x[2 * ci[c] + 1] * CAM_UNIT
        syaw = sig[2 * ci[c]] * CAM_UNIT; spitch = sig[2 * ci[c] + 1] * CAM_UNIT
        amin = math.hypot(dyaw, dpitch) * 60
        samin = math.hypot(syaw, spitch) * 60 + 1e-9
        nb = len({m['bld'] for m in meta if m['cam'] == c})
        oth = sorted(ctx_other.get(c, []))
        if len(oth) >= 4:
            k = max(1, len(oth) // 5)
            trimmed = statistics.median(oth[:-k])   # coupe les 20% pires (conflits de frame)
        elif oth:
            trimmed = statistics.median(oth)
        else:
            trimmed = None
        out.append((amin / samin, amin, samin, c, dyaw, dpitch, nb, trimmed))
    for nsig, amin, samin, c, dyaw, dpitch, nb, trimmed in sorted(out, reverse=True):
        flags = []
        if nb < 2:
            flags.append('1 bld: non separable')
        if trimmed is not None and nsig > 3 and trimmed < 1.5:
            flags.append(f'bien ancree ailleurs ({trimmed:.1f}\') -> soupcon mesh/frame')
        if nsig < 2.5 or amin < 1.5:
            verdict = 'ok'
        elif any('ancree' in f for f in flags):
            verdict = 'a investiguer'
        else:
            verdict = f'A POLIR -> edge_solve --mode cam --cam "{c}"' if c in JUDGE_EDGE_CAMS \
                else 'A POLIR (refit ypr sur appuis vetted)'
        ctxs = f'hors-mesh {trimmed:.1f}\'' if trimmed is not None else 'hors-mesh: n/a'
        print(f'   {c[:32]:32} dyaw{dyaw:+.3f}±{samin/60/1.414:.3f} dpitch{dpitch:+.3f} '
              f'({amin:4.1f}\'={nsig:4.1f}sig) {nb} blds, {ctxs}  {verdict}'
              + ('  [' + '; '.join(flags) + ']' if flags else ''))

    # ── RESTES
    print('\n── RESTES INEXPLIQUES (obs, apres effets cam+mesh — markings/non-rigide):')
    errs = np.linalg.norm(resid, axis=1)
    order = np.argsort(-errs)
    shown = 0
    for i in order:
        if shown >= 10 or errs[i] < 2.0:
            break
        m = meta[i]
        unit = "'" if m['family'] == 'click' else 'sig_e'
        print(f'   {m["cam"][:26]:26} {m["lm"].replace(m["bld"], "..")[:34]:34} '
              f'reste {errs[i]:5.1f}{unit}  (w {wts[i]:.2f})')
        shown += 1


if __name__ == '__main__':
    main()
