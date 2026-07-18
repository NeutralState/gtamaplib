#!/usr/bin/env python3
"""gen_spc_mesh.py — mesh procedural Stephen P. Clark Government Center (V2).

Donnees IRL (Wikipedia/Stubbins 1985): 510 ft = 155m, 28 etages a 5.5m/etage
(ratio le plus haut des gratte-ciels). Notre toit mesure: z=155.35 (plan-toit,
5 coins triangules + 3 symetrie centrale). Le jeu est a l'echelle 1:1 ->
sol derive: 155.35 - 28*5.5 = 1.35 (downtown au niveau de la mer, coherent).

V2: prisme octogonal + anneaux d'etage tous les 5.5m (texture-rythme du vrai)
+ anneau toit. Relancer apres tout raffinement de coin.
"""
import json, os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = 'Stephen P. Clark Government Center'
N_FLOORS = 28
FLOOR_H = 5.5
ORDER = ['NW', 'N', 'NE', 'E', 'SE', 'S', 'SW', 'W']

lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
roof = [lms[f'{B} ({c})']['xyz'] for c in ORDER]
z_roof = sum(p[2] for p in roof) / len(roof)
z_ground = z_roof - N_FLOORS * FLOOR_H
n = len(roof)

def ring(z):
    return [[roof[i][0], roof[i][1], z] for i in range(n)]

edges = []
# verticales aux 8 coins
for i in range(n):
    edges.append([[roof[i][0], roof[i][1], z_ground], list(roof[i])])
# anneaux: sol, chaque etage, toit
levels = [z_ground + k * FLOOR_H for k in range(N_FLOORS + 1)]
for z in levels:
    r = ring(z)
    for i in range(n):
        edges.append([r[i], r[(i + 1) % n]])

p = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
bp = json.load(open(p))
bp[B] = {'color': '#4ade80', 'world_edges': edges}
json.dump(bp, open(p, 'w'), indent=1, ensure_ascii=True)
print(f'{B} V2: {len(edges)} aretes — sol z={z_ground:.2f}, {N_FLOORS} etages x {FLOOR_H}m, toit z={z_roof:.2f}')
