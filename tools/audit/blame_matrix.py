#!/usr/bin/env python3
"""blame_matrix.py — l'arbitre mesh-vs-cam. [BLAME-MATRIX-V1, READ-ONLY]

La question d'Alexandre (2026-07-19): un outil qui compare toutes les poses
et dit comment le mesh devrait changer — MAIS qui trie entre 'le mesh est
faux' et 'la cam est mal calibree'. Les deux fautes ont des signatures
distinctes, et on les separe par decomposition jointe:

  r_ij (residu median pixel de la cam i sur le building j)
       ~= K_ij @ (dyaw_i, dpitch_i)   # effet CAM: tout bouge pareil en IMAGE
        + J_ij @ (dE_j, dN_j)         # effet MESH: les cams s'accordent en MONDE
        + reste                       # markings douteux / non-rigide

K (px par degre de ypr) et J (px par metre est/nord) sont calcules par
differences finies sur le VRAI modele cam (common.get_cam — jamais de
projecteur maison, lecon Peacock B). Moindres carres ridge + une passe de
reponderation robuste. Unites d'equation: arcmin (cams zoomees non favorisees).

Identifiabilite (l'honnetete de l'outil):
- un building juge par <3 cams ou <60 deg d'etalement d'azimut = consensus
  fragile (une erreur cam peut se deguiser en translation monde);
- une cam qui ne voit qu'UN building = signature non separable;
- le contexte 'clics hors-mesh' par cam departage: une cam bien ancree
  ailleurs mais 'coupable' ici -> soupcon renvoye vers le mesh/frame locale.

READ-ONLY: l'outil accuse, il ne corrige pas. Les corrections passent par
les outils dedies (edge_solve --mode cam, fit_mesh/edge_solve --mode mesh)
apres verdict humain.

Usage:
  PYTHONPATH=. python3 tools/audit/blame_matrix.py
  PYTHONPATH=. python3 tools/audit/blame_matrix.py --buildings "Vizcayne North Condominium,..."
  ... --min-obs 2    # ignorer les cellules a 1 observation
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

RIDGE = 0.5          # arcmin d'a-priori 'rien ne bouge' (les deux familles)
CAM_UNIT = 0.1       # les inconnues cam sont en unites de 0.1 deg (~O(1))
HUBER_K = 3.0        # cellules > 3x mediane des restes -> downweight


def load_cells(buildings, min_obs):
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    cams_json = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))

    members = {}   # building -> {lm: xyz}
    for b in buildings:
        m = {n: np.array(e['xyz'], float) for n, e in lms.items()
             if n.startswith(b + ' (') and isinstance(e, dict) and e.get('xyz')}
        if len(m) >= 2:
            members[b] = m
    corner_lms = {n for m in members.values() for n in m}

    cells = {}     # (cam, building) -> list[(du, dv)]
    ctx_other = {} # cam -> residus arcmin sur les LMs HORS buildings (ancrage independant)
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
            cells.setdefault((cam_name, hit), []).append((pix[0] - p[0], pix[1] - p[1]))

    cells = {k: v for k, v in cells.items() if len(v) >= min_obs}
    return members, cells, ctx_other, cam_cache, cams_json


def jacobians(cam_name, cam, entry, centroid):
    """K (px / 0.1 deg yaw,pitch) et J (px / m est,nord), differences finies."""
    p0 = cam.get_pixel(centroid.tolist())
    if p0 is None:
        return None, None, None
    K = np.zeros((2, 2))
    for i in range(2):
        ypr = list(entry['ypr']); ypr[i] += CAM_UNIT
        c2 = common.get_cam(cam_name, {'xyz': entry['xyz'], 'ypr': ypr, 'fov': entry['fov']})
        p1 = c2.get_pixel(centroid.tolist())
        if p1 is None:
            return None, None, None
        K[:, i] = [p1[0] - p0[0], p1[1] - p0[1]]
    J = np.zeros((2, 2))
    for i, d in enumerate((np.array([1.0, 0, 0]), np.array([0, 1.0, 0]))):
        p1 = cam.get_pixel((centroid + d).tolist())
        if p1 is None:
            return None, None, None
        J[:, i] = [p1[0] - p0[0], p1[1] - p0[1]]
    # echelle angulaire locale: |reponse a 0.1 deg de yaw| px = 6 arcmin
    apx = 6.0 / max(float(np.linalg.norm(K[:, 0])), 1e-6)
    return K, J, apx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--buildings', default=None, help='csv (defaut: tous les meshes proceduraux)')
    ap.add_argument('--min-obs', type=int, default=1)
    args = ap.parse_args()

    if args.buildings:
        buildings = [b.strip() for b in args.buildings.split(',')]
    else:
        bp = json.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')))
        buildings = sorted(bp.keys())

    members, cells, ctx_other, cam_cache, cams_json = load_cells(buildings, args.min_obs)
    blds = sorted({b for _, b in cells})
    cams = sorted({c for c, _ in cells})
    if not cells:
        sys.exit('aucune cellule (cam x building) avec assez d observations')
    centroids = {b: np.mean(list(members[b].values()), axis=0) for b in blds}

    # ── assemble le systeme: 2 equations arcmin par cellule
    ci = {c: i for i, c in enumerate(cams)}
    bi = {b: i for i, b in enumerate(blds)}
    ncol = 2 * len(cams) + 2 * len(blds)
    rows_A, rows_r, meta = [], [], []
    for (c, b), res in sorted(cells.items()):
        cam = cam_cache[c]
        K, J, apx = jacobians(c, cam, cams_json[c], centroids[b])
        if K is None:
            continue
        du = statistics.median(r[0] for r in res)
        dv = statistics.median(r[1] for r in res)
        w = math.sqrt(min(len(res), 9))
        A2 = np.zeros((2, ncol))
        A2[:, 2 * ci[c]:2 * ci[c] + 2] = K
        A2[:, 2 * len(cams) + 2 * bi[b]:2 * len(cams) + 2 * bi[b] + 2] = J
        rows_A.append(A2 * apx * w)
        rows_r.append(np.array([du, dv]) * apx * w)
        meta.append((c, b, len(res), du, dv, apx, K, J))
    A = np.vstack(rows_A)
    r = np.concatenate(rows_r)

    def solve(wts):
        W = np.repeat(wts, 2)
        Aw, rw = A * W[:, None], r * W
        return np.linalg.solve(Aw.T @ Aw + RIDGE ** 2 * np.eye(ncol), Aw.T @ rw)

    wts = np.ones(len(meta))
    x = solve(wts)
    # une passe robuste: downweight les cellules au reste aberrant
    resid = (A @ x - r).reshape(-1, 2)
    cell_err = np.linalg.norm(resid, axis=1)
    med = max(float(np.median(cell_err)), 1e-6)
    wts = np.minimum(1.0, HUBER_K * med / np.maximum(cell_err, 1e-9))
    x = solve(wts)
    resid = (A @ x - r).reshape(-1, 2)

    # ── la matrice
    print(f'BLAME-MATRIX-V1: {len(cams)} cams x {len(blds)} buildings, {len(meta)} cellules')
    hdr = ' ' * 30 + ''.join(f'{b.split()[0][:10]:>12}' for b in blds)
    print(hdr)
    for c in cams:
        row = f'{c[:29]:30}'
        for b in blds:
            m = next((mm for mm in meta if mm[0] == c and mm[1] == b), None)
            if m is None:
                row += f'{"·":>12}'
            else:
                ang = math.hypot(m[3], m[4]) * m[5]
                row += f'{ang:8.1f}\'x{m[2]:<3}'
        print(row)

    # ── verdicts BUILDING (consensus monde)
    print('\n── VERDICTS MESH (deplacement monde propose par le consensus):')
    for b in blds:
        t = x[2 * len(cams) + 2 * bi[b]:2 * len(cams) + 2 * bi[b] + 2]
        wit = [m for m in meta if m[1] == b]
        azs = []
        for m in wit:
            d = centroids[b] - np.asarray(cam_cache[m[0]].xyz)
            azs.append(math.degrees(math.atan2(-d[0], d[1])) % 360)
        spread = 0.0
        if len(azs) > 1:
            s = sorted(azs)
            gaps = [(s[(i + 1) % len(s)] - s[i]) % 360 for i in range(len(s))]
            spread = 360.0 - max(gaps)
        mag = float(np.linalg.norm(t))
        flag = ''
        if len(wit) < 3 or spread < 60:
            flag = '  [FRAGILE: peu de temoins/azimuts — une erreur cam peut se deguiser]'
        verdict = 'stable' if mag < 0.7 else ('a bouger?' if mag < 2.5 else 'SUSPECT')
        print(f'   {b[:38]:38} dE={t[0]:+6.2f}m dN={t[1]:+6.2f}m |t|={mag:5.2f}m '
              f'({len(wit)} cams, azimuts {spread:.0f} deg) {verdict}{flag}')

    # ── verdicts CAM (signature ypr uniforme)
    print('\n── VERDICTS CAM (correction ypr proposee par la signature image):')
    out = []
    for c in cams:
        dyaw, dpitch = x[2 * ci[c]] * CAM_UNIT, x[2 * ci[c] + 1] * CAM_UNIT
        nb = len([m for m in meta if m[0] == c])
        amin = math.hypot(dyaw, dpitch) * 60
        other = statistics.median(ctx_other[c]) if ctx_other.get(c) else None
        out.append((amin, c, dyaw, dpitch, nb, other))
    for amin, c, dyaw, dpitch, nb, other in sorted(out, reverse=True):
        flags = []
        if nb < 2:
            flags.append('1 building: non separable du mesh')
        if other is not None and amin > 2.0 and other < 1.5:
            flags.append(f'MAIS bien ancree ailleurs ({other:.1f}\' hors-mesh) -> soupcon renvoye au mesh/frame')
        ctx = f'hors-mesh {other:.1f}\'' if other is not None else 'hors-mesh: aucun'
        verdict = 'ok' if amin < 1.5 else ('a polir?' if amin < 4 else 'SUSPECT')
        print(f'   {c[:34]:34} dyaw={dyaw:+.3f} dpitch={dpitch:+.3f} ({amin:4.1f}\') '
              f'{nb} blds, {ctx}  {verdict}' + ('  [' + '; '.join(flags) + ']' if flags else ''))

    # ── restes inexpliques (ni cam ni mesh: markings / non-rigide)
    print('\n── RESTES INEXPLIQUES (top cellules — markings douteux ou non-rigidite):')
    order = np.argsort(-np.linalg.norm(resid, axis=1))
    for i in order[:8]:
        c, b, n, du, dv, apx, _, _ = meta[i]
        e = float(np.linalg.norm(resid[i]))
        if e < 1.0:
            break
        w = '' if wts[i] >= 0.999 else f'  (downweight x{wts[i]:.2f})'
        print(f'   {c[:28]:28} x {b.split()[0][:12]:12} reste {e:4.1f}\'  ({n} obs){w}')


if __name__ == '__main__':
    main()
