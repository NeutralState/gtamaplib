#!/usr/bin/env python3
"""structures.py — contraintes structurelles declaratives. [STRUCT-V1, 2026-07-18]

Le monde du jeu est rigide: pins a hauteur constante, lettres coplanaires,
toits plans, aretes verticales. Chaque victoire de la semaine du 07-14
(pins 15-65' -> 0.2m, panneau VICE, toit SPC, Metro +2.5 deg) venait d'un
prior de structure code a la main. Ce module les rend declaratifs:
gtamapdata/structures.json est LA source, le triangulateur snappe, le CI garde.

Types:
  fixed_z       {z, tol_m, members|members_pattern}      enforce possible
  plane         {point, normal, tol_m, members...}       fit gele a la declaration
  vertical_edge {edges: {lm: parent_corner_lm}, tol_m}   xy herite du parent
  mesh_prism    metadata (generateur de mesh; la geometrie est portee par
                les autres types)

`enforce: true`  -> snap(lm, xyz) projette sur la contrainte (verite connue).
`enforce: false` -> check-only: la mesure reste independante, le CI surveille
                    la violation (surface de validation, pas de snap).

API:
  load()                        -> dict structures
  members_of(name, s, lms)      -> [lm names]
  snap(lm_name, xyz, lms)       -> (xyz', [structures appliquees])
  check_all(lms)                -> [(structure, lm, ecart_m, tol_m)] violations
"""
import json
import os
import re

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_REPO, 'gtamapdata', 'structures.json')
_CACHE = None


def load(refresh=False):
    global _CACHE
    if _CACHE is None or refresh:
        try:
            _CACHE = {k: v for k, v in json.load(open(_PATH)).items()
                      if not k.startswith('_')}
        except FileNotFoundError:
            _CACHE = {}
    return _CACHE


def members_of(name, s, landmarks):
    if 'members' in s:
        return [m for m in s['members'] if m in landmarks]
    pat = s.get('members_pattern')
    if pat:
        rx = re.compile(pat)
        return [n for n in landmarks if rx.match(n)]
    if s.get('type') == 'vertical_edge':
        return [m for m in (s.get('edges') or {}) if m in landmarks]
    return []


def _xyz(landmarks, n):
    e = landmarks.get(n)
    if isinstance(e, dict):
        return e.get('xyz')
    return e  # md.landmarks style: xyz direct


def _plane_dist(xyz, s):
    p0, nrm = s['point'], s['normal']
    return sum((xyz[i] - p0[i]) * nrm[i] for i in range(3))


def snap(lm_name, xyz, landmarks):
    """Projette xyz sur toutes les contraintes ENFORCEES qui matchent lm_name.
    Retourne (xyz_corrige, [noms de structures appliquees])."""
    out = list(xyz)
    applied = []
    for name, s in load().items():
        if not s.get('enforce'):
            continue
        t = s.get('type')
        if t == 'fixed_z':
            if lm_name in members_of(name, s, {lm_name: True}):
                out[2] = float(s['z'])
                applied.append(name)
        elif t == 'plane':
            if lm_name in members_of(name, s, {lm_name: True}):
                d = _plane_dist(out, s)
                for i in range(3):
                    out[i] -= d * s['normal'][i]
                applied.append(name)
        elif t == 'vertical_edge':
            parent = (s.get('edges') or {}).get(lm_name)
            if parent:
                pxyz = _xyz(landmarks, parent)
                if pxyz:
                    out[0], out[1] = pxyz[0], pxyz[1]
                    applied.append(name)
    return out, applied


def check_all(landmarks):
    """Violations [(structure, lm, ecart_m, tol_m)] — enforce ET check-only."""
    fails = []
    for name, s in load().items():
        t = s.get('type')
        tol = float(s.get('tol_m', 1.0))
        if t == 'mesh_prism':
            continue
        for m in members_of(name, s, landmarks):
            xyz = _xyz(landmarks, m)
            if not xyz:
                continue
            if t == 'fixed_z':
                d = abs(xyz[2] - float(s['z']))
            elif t == 'plane':
                d = abs(_plane_dist(xyz, s))
            elif t == 'vertical_edge':
                pxyz = _xyz(landmarks, (s.get('edges') or {}).get(m, ''))
                if not pxyz:
                    continue
                d = ((xyz[0] - pxyz[0]) ** 2 + (xyz[1] - pxyz[1]) ** 2) ** 0.5
            else:
                continue
            if d > tol:
                fails.append((name, m, round(d, 3), tol))
    return fails


def new_violations(landmarks):
    """Violations NOUVELLES ou aggravees (+0.5m) vs la baseline gelee dans
    structures.json['_baseline_violations']. C'est ce que le CI bloque."""
    try:
        base = json.load(open(_PATH)).get('_baseline_violations', {}).get('items', {})
    except Exception:
        base = {}
    out = []
    for name, m, d, tol in check_all(landmarks):
        key = f'{name}::{m}'
        if key not in base or d > base[key] + 0.5:
            out.append((name, m, d, tol, base.get(key)))
    return out


# ── CYLINDER-V1 (2026-07-22, question rlx bounty #23) ───────────────────
# Les clics d'arete L/R d'un objet rond sont des points de silhouette
# DEPENDANTS DU POINT DE VUE: ils ne se point-matchent pas entre frames
# (tank (R): tangentes etalees sur 35m; silo: largeur point-match 15.6 vs
# 14.2 reelle). Le bon modele: cylindre vertical (centre xy + rayon), chaque
# clic d'arete = rayon TANGENT au cercle en plan.
#   type: "cylinder"  {tangents: {lm: "L"|"R"}, axis: {x,y,radius} (fit
#   gele comme plane), tol_m}
# Contrainte de RAYONS (il faut cams+pixels) -> check via check_cylinders(),
# pas snap(); enforce non supporte en V1 (check-only, doctrine STRUCT-V1).


def _tangent_rays(s, pixels):
    """[(cam, lm, o2d, d2d)] pour chaque clic tangent du cylindre."""
    import numpy as np
    import sys
    sys.path.insert(0, os.path.join(_REPO, 'tools'))
    import common
    out = []
    for lm in (s.get('tangents') or {}):
        for cn, marks in pixels.items():
            p = marks.get(lm)
            if p is None:
                continue
            try:
                cam = common.get_cam(cn)
            except Exception:
                continue
            o = np.asarray(cam.xyz, float)[:2]
            d = np.asarray(cam.get_pixel_direction(p), float)[:2]
            n = float(np.hypot(*d))
            if n > 1e-9:
                out.append((cn, lm, o, d / n))
    return out


def _ray_dist(cx, cy, o, d):
    v0, v1 = cx - o[0], cy - o[1]
    return abs(v0 * d[1] - v1 * d[0])


def fit_cylinder(s, pixels):
    """Fit (cx, cy, r) par moindres carres de tangence sur les rayons L/R.
    Retourne {'x','y','radius','rms_m','n_rays'} ou None (<3 rayons)."""
    import numpy as np
    from scipy.optimize import minimize
    rays = _tangent_rays(s, pixels)
    if len(rays) < 3:
        return None
    # init: moyenne des intersections 2 a 2 des lignes
    pts = []
    for i in range(len(rays)):
        for j in range(i + 1, len(rays)):
            (_, _, o1, d1), (_, _, o2, d2) = rays[i], rays[j]
            det = d1[0] * (-d2[1]) - d1[1] * (-d2[0])
            if abs(det) < 1e-9:
                continue
            t = ((o2[0] - o1[0]) * (-d2[1]) - (o2[1] - o1[1]) * (-d2[0])) / det
            pts.append(o1 + t * d1)
    c0 = np.mean(pts, axis=0) if pts else np.mean([o for _, _, o, _ in rays], axis=0)

    def cost(th):
        return sum((_ray_dist(th[0], th[1], o, d) - th[2]) ** 2
                   for _, _, o, d in rays)

    best = None
    for r0 in (2.0, 4.0, 7.0, 12.0):
        res = minimize(cost, [c0[0], c0[1], r0], method='Nelder-Mead',
                       options={'xatol': 1e-5, 'fatol': 1e-10, 'maxiter': 40000})
        if res.x[2] > 0 and (best is None or res.fun < best.fun):
            best = res
    if best is None:
        return None
    cx, cy, r = best.x
    rms = (best.fun / len(rays)) ** 0.5
    return {'x': round(float(cx), 2), 'y': round(float(cy), 2),
            'radius': round(float(r), 3), 'rms_m': round(float(rms), 3),
            'n_rays': len(rays)}


def check_cylinders(pixels):
    """Violations de tangence vs l'axe GELE: [(structure, cam, lm, ecart_m,
    tol_m)]. Meme esprit que check_all mais sur les rayons."""
    fails = []
    for name, s in load().items():
        if s.get('type') != 'cylinder' or not s.get('axis'):
            continue
        ax, tol = s['axis'], float(s.get('tol_m', 0.5))
        for cn, lm, o, d in _tangent_rays(s, pixels):
            e = abs(_ray_dist(ax['x'], ax['y'], o, d) - ax['radius'])
            if e > tol:
                fails.append((name, cn, lm, round(e, 3), tol))
    return fails



if __name__ == '__main__':
    import argparse
    import sys
    ap = argparse.ArgumentParser(description='STRUCT: check CI (defaut) / fit-check cylindres')
    ap.add_argument('--fit', metavar='NAME', help='fit tangence du cylindre NAME')
    ap.add_argument('--write', action='store_true', help='gele le fit dans structures.json')
    ap.add_argument('--check-cylinders', action='store_true',
                    help='check tangence de tous les cylindres')
    args = ap.parse_args()

    if args.fit or args.check_cylinders:
        pixels = json.load(open(os.path.join(_REPO, 'gtamapdata', 'pixels.json')))
        if args.fit:
            s = load().get(args.fit)
            if not s or s.get('type') != 'cylinder':
                raise SystemExit(f'structure cylindre inconnue: {args.fit}')
            fit = fit_cylinder(s, pixels)
            if not fit:
                raise SystemExit('pas assez de rayons tangents (<3)')
            print(f'{args.fit}: centre ({fit["x"]}, {fit["y"]})  rayon {fit["radius"]}m '
                  f'-> largeur {2 * fit["radius"]:.2f}m  rms {fit["rms_m"]}m  ({fit["n_rays"]} rayons)')
            if args.write:
                import tempfile
                full = json.load(open(_PATH))
                full[args.fit]['axis'] = {k: fit[k] for k in ('x', 'y', 'radius')}
                full[args.fit]['fit_meta'] = {'rms_m': fit['rms_m'], 'n_rays': fit['n_rays'],
                                              'date': '2026-07-22'}
                fd, tmp = tempfile.mkstemp(dir=os.path.dirname(_PATH), suffix='.tmp')
                with os.fdopen(fd, 'w') as f:
                    json.dump(full, f, indent=1, ensure_ascii=False)
                os.replace(tmp, _PATH)
                load(refresh=True)
                print('axe gele dans structures.json')
        if args.check_cylinders:
            v = check_cylinders(pixels)
            if not v:
                print('tangence OK sur tous les cylindres')
            for name, cn, lm, e, tol in v:
                print(f'VIOLATION {name}: {cn} / {lm}  ecart {e}m (tol {tol})')
            sys.exit(1 if v else 0)
        sys.exit(0)

    # defaut: check CI (comportement historique, invariants/CI comptent dessus)
    lms = json.load(open(os.path.join(_REPO, 'gtamapdata', 'landmarks.json')))
    allv = check_all(lms)
    newv = new_violations(lms)
    for name, m, d, tol in allv:
        tag = 'NOUVELLE ' if any(x[1] == m and x[0] == name for x in newv) else 'baseline '
        print(f'{tag}VIOLATION {name}: {m} ecart {d}m > tol {tol}m')
    print(f'{len(load())} structures, {len(allv)} violation(s) dont {len(newv)} nouvelles')
    sys.exit(1 if newv else 0)
