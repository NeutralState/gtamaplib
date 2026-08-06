#!/usr/bin/env python3
"""hill_fit.py — les fits de collines consolides en UNE commande. [HILL-FIT-V1]

Nes en scripts inline pendant la campagne TRACE-MESH (Easy Hill, BB Hill,
Gellhorn), reecrits une dizaine de fois — Alexandre: "on met dans l'outil
aussi?". Oui. Deux modes:

  ellipse   dome elliptique 6 parametres (centre, demi-axes, orientation,
            hauteur), Nelder-Mead multi-depart, cout = moyenne des medianes
            rasterisees des vues. La forme "colline simple" par defaut —
            c'est elle qui a gagne sur Easy Hill (2cba959).

  zfit      la forme au sol ne bouge PAS (epine + demi-largeurs existantes
            du mesh vise, lues d'un fichier de spine JSON) et seuls les z
            des points de controle sont ajustes par moindres carres
            linearises — la methode qui a fitte Gellhorn (edf4d4f).
            Points epingles possibles (sommets mesures).

LES REGLES APPRISES, appliquees d'office:
  - juge RASTERISE par colonne (b2aedd8): jamais de points epars;
  - garde-fou de recouvrement: moins de --min-cols colonnes = cout enorme,
    un fit qui fuit hors des traces ne peut pas gagner;
  - les traces viennent du TRACER (pixels exacts), etiquette par massif —
    jamais de digitalisation d'ecran;
  - les vues LEAK d'abord; toute vue a pose contestee est un temoin de
    forme, pas une ancre de position.

Usage:
  PYTHONPATH=. python3 tools/hill_fit.py --mode ellipse --name 'Easy Hill' \
      --views 'Diner (SE) (B)' 'Diner (SE) (A)' 'Ambrosia 04 (Fires)' \
      --init -5914 3969 200 140 0 56 [--label 'Easy Hill'] [--apply]
  PYTHONPATH=. python3 tools/hill_fit.py --mode zfit --name 'Gellhorn Hills (croquis)' \
      --spine tools/data/gellhorn_spine.json --label 'Gellhorn Bluff' \
      --views 'Ambrosia 04 (Fires)' 'Port Vice City (A)' [--pin 5 92 --pin 7 88] [--apply]
"""
import argparse
import json
import math
import os
import sys
import tempfile

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np

MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
BASE = 20.0


def profiles(views, label):
    import common
    from silhouette_hull import traced, poly_top
    TR = traced()
    out = {}
    for cn in views:
        c = common.get_cam(cn)
        e = (TR.get(cn) or {}).get(label)
        if not e:
            print(f'  (pas de trace {label!r} dans {cn!r} — vue ignoree)')
            continue
        out[cn] = poly_top(e.get('strokes') or e.get('points'), int(c.w))
    if not out:
        raise SystemExit('aucune vue avec trace')
    return out


def raster_judge(edges, prof_by_view):
    """mediane |dv| par vue, enveloppe rasterisee par colonne le long des ARETES."""
    import common
    out = {}
    for cn, prof in prof_by_view.items():
        c = common.get_cam(cn)
        cols = {}
        for a, b in edges:
            qa = c.get_pixel([float(x) for x in a])
            qb = c.get_pixel([float(x) for x in b])
            if qa is None or qb is None:
                continue
            n = max(2, int(abs(qb[0] - qa[0]) / 2) + 1)
            for t in np.linspace(0.0, 1.0, n):
                p = [a[i] + t * (b[i] - a[i]) for i in range(3)]
                q = c.get_pixel(p)
                if q is None:
                    continue
                u = int(round(q[0]))
                if 0 <= u < len(prof):
                    cols[u] = min(cols.get(u, 1e9), q[1])
        dv = [abs(v - prof[u]) for u, v in cols.items() if not math.isnan(prof[u])]
        out[cn] = (float(np.median(dv)), len(dv)) if len(dv) >= 6 else None
    return out


def ellipse_edges(cx, cy, a, b, th, H, nring=6, nrad=16):
    ct, st = math.cos(th), math.sin(th)
    E = []
    add = lambda x, y: E.append([list(map(float, x)), list(map(float, y))])
    def ring(r, n=40):
        z = BASE + H * (1 - r * r)
        return [(cx + (a * r * np.cos(t)) * ct - (b * r * np.sin(t)) * st,
                 cy + (a * r * np.cos(t)) * st + (b * r * np.sin(t)) * ct, z)
                for t in np.linspace(0, 2 * np.pi, n)]
    for r in np.linspace(1.0 / nring, 1.0, nring):
        q = ring(r)
        for x, y in zip(q[:-1], q[1:]):
            add(x, y)
    top = (cx, cy, BASE + H)
    for t in np.linspace(0, 2 * np.pi, nrad, endpoint=False):
        prev = top
        for r in np.linspace(1.0 / nring, 1.0, nring):
            z = BASE + H * (1 - r * r)
            q = (cx + (a * r * np.cos(t)) * ct - (b * r * np.sin(t)) * st,
                 cy + (a * r * np.cos(t)) * st + (b * r * np.sin(t)) * ct, z)
            add(prev, q)
            prev = q
    return E


def fit_ellipse(prof_by_view, init, min_cols, drift):
    import common
    from scipy.optimize import minimize
    x0 = np.asarray(init, float)
    def pts_of(p, nr=8, na=32):
        cx, cy, a, b, th, H = p
        ct, st = math.cos(th), math.sin(th)
        out = []
        for r in np.linspace(0, 1, nr):
            z = BASE + H * (1 - r * r)
            for t in np.linspace(0, 2 * np.pi, na, endpoint=False):
                ex, ey = a * r * np.cos(t), b * r * np.sin(t)
                out.append((cx + ex * ct - ey * st, cy + ex * st + ey * ct, z))
        return out
    def cost(p):
        cx, cy, a, b, th, H = p
        if not (50 <= a <= 500 and 50 <= b <= 500 and 15 <= H <= 130):
            return 1e6
        if np.hypot(cx - x0[0], cy - x0[1]) > drift:
            return 1e6
        tot = 0.0
        P = pts_of(p)
        for cn, prof in prof_by_view.items():
            c = common.get_cam(cn)
            cols = {}
            for q3 in P:
                q = c.get_pixel([float(x) for x in q3])
                if q is None:
                    continue
                u = int(round(q[0]))
                if 0 <= u < len(prof):
                    cols[u] = min(cols.get(u, 1e9), q[1])
            dv = [abs(v - prof[u]) for u, v in cols.items()
                  if not math.isnan(prof[u])]
            if len(dv) < min_cols:
                return 1e5          # fuir hors des traces ne gagne JAMAIS
            tot += float(np.median(dv))
        return tot / len(prof_by_view)
    best = None
    for th0 in np.arange(0, np.pi, 0.6):
        p0 = x0.copy(); p0[4] = th0
        r = minimize(cost, p0, method='Nelder-Mead',
                     options={'maxiter': 250, 'xatol': 2, 'fatol': 0.05})
        if best is None or r.fun < best.fun:
            best = r
    return best


def footprint_edges(spine, contour_step=12.0, samp=22.0):
    """spine: [(x, y, hwL, hwR, z)] — crete + pieds + pentes + niveaux."""
    C = np.asarray(spine, float)
    t = np.r_[0, np.cumsum(np.linalg.norm(np.diff(C[:, :2], axis=0), axis=1))]
    ts = np.unique(np.r_[np.arange(t[0], t[-1], samp), t])
    S = np.stack([np.interp(ts, t, C[:, i]) for i in range(5)], axis=1)
    T = np.gradient(S[:, :2], axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    N = np.stack([-T[:, 1], T[:, 0]], axis=1)
    crest = np.column_stack([S[:, :2], BASE + S[:, 4]])
    L = np.column_stack([S[:, :2] + N * S[:, 2:3], np.full(len(S), BASE)])
    R = np.column_stack([S[:, :2] - N * S[:, 3:4], np.full(len(S), BASE)])
    E = []
    add = lambda a, b: E.append([list(map(float, a)), list(map(float, b))])
    for Xs in (crest, L, R):
        for a, b in zip(Xs[:-1], Xs[1:]):
            add(a, b)
    for i in range(0, len(S), 2):
        add(crest[i], L[i]); add(crest[i], R[i])
    for zc in np.arange(contour_step, S[:, 4].max(), contour_step):
        for side in (L, R):
            ring = [crest[i] + (zc / S[i, 4]) * (side[i] - crest[i])
                    if S[i, 4] > zc else None for i in range(len(S))]
            for a, b in zip(ring[:-1], ring[1:]):
                if a is not None and b is not None:
                    add(a, b)
    return E


def fit_z(spines, prof_by_view, pins, iters=3, keep=0.35, smooth=0.8):
    """z des points de controle par moindres carres linearises; la forme au
    sol des spines ([(x,y,hwL,hwR,z)] par segment) est INTOUCHEE."""
    import common
    allpts = [list(p) for sp in spines for p in sp]
    nseg = [len(sp) for sp in spines]
    z = np.array([p[4] for p in allpts], float)
    def samples(z):
        out = []
        off = 0
        for sp, n in zip(spines, nseg):
            C = np.array([[p[0], p[1]] for p in sp], float)
            t = np.r_[0, np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))]
            for s0 in np.arange(0, t[-1], 25.0):
                j = min(max(np.searchsorted(t, s0, side='right') - 1, 0), len(t) - 2)
                f = (s0 - t[j]) / max(t[j + 1] - t[j], 1e-9)
                x = C[j, 0] + f * (C[j + 1, 0] - C[j, 0])
                y = C[j, 1] + f * (C[j + 1, 1] - C[j, 1])
                zz = z[off + j] + f * (z[off + j + 1] - z[off + j])
                w = np.zeros(len(z)); w[off + j] = 1 - f; w[off + j + 1] = f
                out.append((x, y, zz, w))
            off += n
        return out
    def eval_views(z):
        S = samples(z); res = {}
        for cn, prof in prof_by_view.items():
            c = common.get_cam(cn)
            cols = {}
            for i, (x, y, zz, w) in enumerate(S):
                q = c.get_pixel([x, y, BASE + zz])
                if q is None:
                    continue
                u = int(round(q[0]))
                if 0 <= u < len(prof) and not math.isnan(prof[u]):
                    if u not in cols or q[1] < cols[u][0]:
                        cols[u] = (q[1], i)
            res[cn] = cols
        return S, res
    for _ in range(iters):
        S, res = eval_views(z)
        rows, rhs = [], []
        for cn, cols in res.items():
            c = common.get_cam(cn)
            prof = prof_by_view[cn]
            for u, (v0, i) in cols.items():
                x, y, zz, w = S[i]
                q2 = c.get_pixel([x, y, BASE + zz + 4.0])
                if q2 is None:
                    continue
                sens = (q2[1] - v0) / 4.0
                if abs(sens) < 1e-4:
                    continue
                rows.append(sens * w); rhs.append(prof[u] - v0)
        n = len(z)
        seg_bounds = set(np.cumsum(nseg)[:-1]) | set(np.cumsum(nseg) - 1)
        for j in range(n):
            r = np.zeros(n); r[j] = keep; rows.append(r); rhs.append(0.0)
        for j in range(1, n - 1):
            if j in seg_bounds:
                continue
            r = np.zeros(n); r[j - 1] = 0.5; r[j] = -1.0; r[j + 1] = 0.5
            rows.append(r * smooth); rhs.append(0.0)
        for j, zt in pins:
            r = np.zeros(n); r[j] = 6.0; rows.append(r); rhs.append(6.0 * (zt - z[j]))
        dz, *_ = np.linalg.lstsq(np.vstack(rows), np.asarray(rhs), rcond=None)
        z = np.clip(z + dz, 3, 130)
    out = []
    off = 0
    for sp, n in zip(spines, nseg):
        out.append([(p[0], p[1], p[2], p[3], float(z[off + k]))
                    for k, p in enumerate(sp)])
        off += n
    return out, z


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', required=True, choices=['ellipse', 'zfit'])
    ap.add_argument('--name', required=True, help='nom du mesh dans l UI')
    ap.add_argument('--label', default=None,
                    help='etiquette de trace dans le tracer (defaut: --name)')
    ap.add_argument('--views', nargs='+', required=True)
    ap.add_argument('--init', nargs=6, type=float,
                    help='ellipse: cx cy a b theta H')
    ap.add_argument('--spine', help='zfit: JSON [[ [x,y,hwL,hwR,z], ... ], ...]')
    ap.add_argument('--pin', nargs=2, type=float, action='append', default=[],
                    help='zfit: index_ctrl z_mesure (repetable)')
    ap.add_argument('--drift', type=float, default=260.0,
                    help='ellipse: derive max du centre en m')
    ap.add_argument('--min-cols', type=int, default=25)
    ap.add_argument('--color', default=None)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    prof = profiles(args.views, args.label or args.name)
    mesh = json.load(open(MESH_PATH))
    old = mesh.get(args.name, {}).get('world_edges')

    if args.mode == 'ellipse':
        if not args.init:
            raise SystemExit('--init cx cy a b theta H requis en mode ellipse')
        best = fit_ellipse(prof, args.init, args.min_cols, args.drift)
        cx, cy, a, b, th, H = best.x
        print(f'ellipse: centre ({cx:.0f},{cy:.0f}), {a:.0f} x {b:.0f} m, '
              f'orientation {math.degrees(th) % 180:.0f} deg, H {H:.0f} m, '
              f'cout {best.fun:.1f} px')
        edges = ellipse_edges(cx, cy, a, b, th, H)
    else:
        if not args.spine:
            raise SystemExit('--spine requis en mode zfit')
        spines = json.load(open(args.spine))
        pins = [(int(i), z) for i, z in args.pin]
        fitted, z = fit_z(spines, prof, pins)
        print('z ctrl:', ', '.join(f'{v:.0f}' for v in z))
        edges = []
        for sp in fitted:
            edges += footprint_edges(sp)

    print(f'\n{"vue":30s} {"avant":>9s} {"apres":>9s}')
    jn = raster_judge(edges, prof)
    jo = raster_judge(old, prof) if old else {}
    for cn in prof:
        o = jo.get(cn); n = jn.get(cn)
        so = f'{o[0]:7.1f}px' if o else '      —'
        sn = f'{n[0]:7.1f}px' if n else '      —'
        print(f'{cn[:30]:30s} {so:>9s} {sn:>9s}')
    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    color = args.color or mesh.get(args.name, {}).get('color', '#fbbf24')
    mesh[args.name] = {'color': color, 'world_edges': edges}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'APPLIED: "{args.name}" ({len(edges)} aretes)')


if __name__ == '__main__':
    main()
