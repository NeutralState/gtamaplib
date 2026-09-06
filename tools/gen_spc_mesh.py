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

# [SPC-V6] SYMETRISATION du plan (Alexandre: "les coins sont pas symetriques
# comme le vrai building"). Le vrai SPC est un rectangle a chanfreins EGAUX;
# nos 8 coins triangules independamment donnaient un octogone bancal. On
# ajuste le gabarit ideal (centre, orientation, L, W, chanfrein — 6 params)
# aux 8 coins mesures en moindres carres et on construit sur le gabarit.
# Ecarts mesures -> symetrique: mediane 2.8 m, max 5.5 m (coin SW) — sous
# les ~3 px a 1 km, l'alignement dans les frames tient.
import math
import numpy as np
from scipy.optimize import least_squares
P2 = np.array([p[:2] for p in roof])
def _model(p):
    cx, cy, th, L, W, c, c2 = p   # [SPC-V7 2026-09-06] chanfreins inegaux (c en x, c2 en y): tooltips Alexandre 10.2 / 12.5 m
    ct, st = math.cos(th), math.sin(th)
    loc = [(-(L - c), W), ((L - c), W), (L, W - c2), (L, -(W - c2)),
           ((L - c), -W), (-(L - c), -W), (-L, -(W - c2)), (-L, W - c2)]
    return np.array([[cx + x * ct - y * st, cy + x * st + y * ct] for x, y in loc])
c0 = P2.mean(0)
best = None
for th0 in np.arange(0, math.pi / 2, 0.15):
    for rot in range(8):
        Pr = np.roll(P2, rot, axis=0)
        r = least_squares(lambda p, Pr=Pr: (_model(p) - Pr).ravel(),
                          [c0[0], c0[1], th0, 30, 14, 6, 6], method='lm')
        if best is None or r.cost < best[0]:
            best = (r.cost, r.x, rot)
_, psym, rot = best
M = np.roll(_model(psym), -rot, axis=0)      # remis dans l'ordre ORDER
roof = [[float(M[i][0]), float(M[i][1]), z_roof] for i in range(len(roof))]
z_ground = z_roof - N_FLOORS * FLOOR_H
n = len(roof)

def ring(z):
    return [[roof[i][0], roof[i][1], z] for i in range(n)]

edges = []
# verticales aux 8 coins
for i in range(n):
    edges.append([[roof[i][0], roof[i][1], z_ground], list(roof[i])])

# [SPC-V5] le vrai langage du batiment (photo IRL + carte des facades
# d'Alexandre): les fenetres sont des BANDEAUX HORIZONTAUX par etage sur les
# faces vitrees NW->N et SE->S (en retrait des coins — cadres de pierre),
# une bande etroite sur les faces petites-fenetres NE->E et SW->W, PIERRE
# NUE partout ailleurs: pas d'anneaux sur les faces pleines ni sous la
# ligne b (socle station). Anneaux complets seulement au sol, a la ligne b
# et au toit.
Z_B = 18.2
GLAZED = {(0, 1): (0.08, 0.92), (4, 5): (0.08, 0.92)}   # NW-N, SE-S
SMALL = {(2, 3): (0.42, 0.58), (6, 7): (0.42, 0.58)}    # NE-E, SW-W

def seg(i, j, f0, f1, z):
    a, b = roof[i], roof[j]
    return [[a[0] + f0 * (b[0] - a[0]), a[1] + f0 * (b[1] - a[1]), z],
            [a[0] + f1 * (b[0] - a[0]), a[1] + f1 * (b[1] - a[1]), z]]

for z in (z_ground, Z_B, z_roof):                        # anneaux complets
    r = ring(z)
    for i in range(n):
        edges.append([r[i], r[(i + 1) % n]])
levels = [z_ground + k * FLOOR_H for k in range(N_FLOORS + 1)]
for z in levels:                                         # bandeaux fenetres
    if z <= Z_B + 0.1 or z >= z_roof - 0.1:
        continue
    for (i, j), (f0, f1) in list(GLAZED.items()) + list(SMALL.items()):
        edges.append(seg(i, j, f0, f1, z))

# [SPC-V3] le mat d'antenne (LM (A), triangule 07-20: 3 temoins 3-6') —
# regle verticale fine du toit a la pointe, visible de partout
ant = lms.get(B + ' (A)', {}).get('xyz')
if ant:
    edges.append([[ant[0], ant[1], z_roof], [ant[0], ant[1], ant[2]]])

p = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
bp = json.load(open(p))
bp[B] = {'color': '#fb923c', 'world_edges': edges}
json.dump(bp, open(p + '.tmp', 'w'), indent=1, ensure_ascii=True)
os.replace(p + '.tmp', p)
print(f'{B} V2: {len(edges)} aretes — sol z={z_ground:.2f}, {N_FLOORS} etages x {FLOOR_H}m, toit z={z_roof:.2f}')
