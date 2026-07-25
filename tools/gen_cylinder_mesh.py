#!/usr/bin/env python3
"""gen_cylinder_mesh.py — meshs des structures cylindriques. [CYL-MESH-V1]

Consomme les structures de type "cylinder" de gtamapdata/structures.json
(axe xy + rayon issus du fit de tangence: les clics d'arete L/R sont des
TANGENTES, jamais des points a matcher — cf. CYLINDER-V1) et en fait des
meshs: anneaux horizontaux + generatrices verticales.

Le silo 1500 Sonora: axe et rayon du fit (rms 0.2m), rebord haut = z moyen
des points (L)/(R) re-triangules, sol = silo_z de la solution H de rlx
(19.655) — nos deux mesures du rebord concordent a 14 cm (64.09 vs 63.95).

Refuse de generer un mesh quand le fit de tangence ne ferme pas (le tank
Sonora: rms 3.1m — c'est une ferme de reservoirs quasi-identiques et les
trois frames marquent des objets differents).

Usage: PYTHONPATH=. python3 tools/gen_cylinder_mesh.py [--apply]
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

MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
RMS_MAX = 0.6          # au-dela, le cylindre n'est pas un cylindre: on refuse
N_SIDES = 24           # segments par anneau
COLOR = '#fb923c'


def cylinder_edges(cx, cy, r, z0, z1, rings, n=N_SIDES):
    """Anneaux horizontaux + generatrices verticales."""
    edges = []
    ang = [2 * math.pi * i / n for i in range(n)]
    pts = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in ang]
    for z in rings:
        for i in range(n):
            j = (i + 1) % n
            edges.append([[pts[i][0], pts[i][1], z], [pts[j][0], pts[j][1], z]])
    for i in range(0, n, 2):          # une generatrice sur deux
        edges.append([[pts[i][0], pts[i][1], z0], [pts[i][0], pts[i][1], z1]])
    return edges


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    structs = json.load(open(os.path.join(REPO, 'gtamapdata', 'structures.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    out = {}

    for name, s in structs.items():
        if not isinstance(s, dict) or s.get('type') != 'cylinder':
            continue
        ax = s.get('axis')
        meta = s.get('fit_meta') or {}
        rms = meta.get('rms_m')
        if not ax:
            print(f'{name}: pas d axe fitte, saute')
            continue
        if rms is not None and rms > RMS_MAX:
            print(f'{name}: fit de tangence rms {rms} m > {RMS_MAX} -> PAS de mesh '
                  f'(ce n est pas un cylindre unique)')
            continue
        # rebord haut: moyenne des z des points tangents re-triangules
        zs = [lms[lm]['xyz'][2] for lm in (s.get('tangents') or {})
              if isinstance(lms.get(lm), dict) and lms[lm].get('xyz')]
        if not zs:
            print(f'{name}: pas de z pour le rebord, saute')
            continue
        z_top = sum(zs) / len(zs)
        z_base = s.get('z_ground')
        if z_base is None:
            print(f'{name}: pas de z_ground declare, saute')
            continue
        h = z_top - z_base
        rings = [z_base + h * f for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
        edges = cylinder_edges(ax['x'], ax['y'], ax['radius'], z_base, z_top, rings)
        label = s.get('mesh_name') or name
        out[label] = {'color': COLOR, 'world_edges': [[list(a), list(b)] for a, b in edges]}
        print(f'{name}: cylindre r={ax["radius"]:.2f} ({2*ax["radius"]:.2f} m de large), '
              f'z {z_base:.2f} -> {z_top:.2f} (h {h:.2f} m), {len(edges)} aretes, rms {rms} m')

    if not out:
        print('\nrien a ecrire.')
        return
    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire dans building_meshes_procedural.json).')
        return
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    mesh.update(out)                   # merge, JAMAIS ecraser le fichier
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=False)
    os.replace(tmp, MESH_PATH)
    print(f'\nAPPLIED: {list(out)} -> {MESH_PATH} ({len(mesh)} meshs au total)')


if __name__ == '__main__':
    main()
