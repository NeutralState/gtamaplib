#!/usr/bin/env python3
"""gen_spc_mesh.py — mesh procedural Stephen P. Clark Government Center.

Prisme octogonal V1 (2026-07-18): toit = 8 coins etablis par plan-toit
(5 triangules E/N/NE/NW/SE z=155.2-155.4 + 3 derives par symetrie centrale),
extrude jusqu'au sol. Anneau intermediaire au niveau mesure du vrai batiment
(la ziggourat IRL a des retraits — V2 quand on aura des coins de base).
Idempotent: reecrit l'entree du json procedural.
"""
import json, os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = 'Stephen P. Clark Government Center'
Z_GROUND = 8.0     # sol downtown approx (rues ~5-10)
ORDER = ['NW', 'N', 'NE', 'E', 'SE', 'S', 'SW', 'W']

lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
roof = [lms[f'{B} ({c})']['xyz'] for c in ORDER]
edges = []
n = len(roof)
for i in range(n):
    a, b = roof[i], roof[(i + 1) % n]
    edges.append([a, b])                                          # anneau toit
    edges.append([[a[0], a[1], Z_GROUND], [b[0], b[1], Z_GROUND]])  # anneau sol
    edges.append([a, [a[0], a[1], Z_GROUND]])                      # verticale

p = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
bp = json.load(open(p))
bp[B] = {'color': '#4ade80', 'world_edges': edges}
json.dump(bp, open(p, 'w'), indent=1, ensure_ascii=True)
print(f'{B}: {len(edges)} aretes (2 anneaux + 8 verticales) -> procedural json')
