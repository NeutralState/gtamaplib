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


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.join(_REPO, 'tools'))
    lms = json.load(open(os.path.join(_REPO, 'gtamapdata', 'landmarks.json')))
    allv = check_all(lms)
    newv = new_violations(lms)
    for name, m, d, tol in allv:
        tag = 'NOUVELLE ' if any(x[1] == m and x[0] == name for x in newv) else 'baseline '
        print(f'{tag}VIOLATION {name}: {m} ecart {d}m > tol {tol}m')
    print(f'{len(load())} structures, {len(allv)} violation(s) dont {len(newv)} nouvelles')
    sys.exit(1 if newv else 0)
