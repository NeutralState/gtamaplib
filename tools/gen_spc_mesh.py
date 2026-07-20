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

# [SPC-V3] le mat d'antenne (LM (A), triangule 07-20: 3 temoins 3-6') —
# regle verticale fine du toit a la pointe, visible de partout
ant = lms.get(B + ' (A)', {}).get('xyz')
if ant:
    edges.append([[ant[0], ant[1], z_roof], [ant[0], ant[1], ant[2]]])

# [SPC-V4] fenetres (carte des facades d'Alexandre, 07-20): meneaux verticaux
# sur les 2 faces vitrees NW->N et SE->S, colonne etroite sur les petites-
# fenetres NE->E et SW->W, de la ligne b (18.2, structure spc-b-level) au
# toit. Les 4 autres faces sont pleines — rien.
Z_B = 18.2
GLAZED = {(0, 1), (4, 5)}       # NW-N, SE-S
SMALL = {(2, 3), (6, 7)}        # NE-E, SW-W
for (i, j), fracs in [(f, [k / 6 for k in range(1, 6)]) for f in GLAZED] + \
                     [(f, [0.42, 0.58]) for f in SMALL]:
    a, b2 = roof[i], roof[j]
    for f in fracs:
        x = a[0] + f * (b2[0] - a[0]); y = a[1] + f * (b2[1] - a[1])
        edges.append([[x, y, Z_B], [x, y, z_roof]])

p = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
bp = json.load(open(p))
bp[B] = {'color': '#fb923c', 'world_edges': edges}
json.dump(bp, open(p + '.tmp', 'w'), indent=1, ensure_ascii=True)
os.replace(p + '.tmp', p)
print(f'{B} V2: {len(edges)} aretes — sol z={z_ground:.2f}, {N_FLOORS} etages x {FLOOR_H}m, toit z={z_roof:.2f}')
