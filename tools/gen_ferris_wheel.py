#!/usr/bin/env python3
"""gen_ferris_wheel.py — mesh de la Skyviews Miami Observation Wheel (Bayside). [WHEEL-V1 2026-09-30]

Plan = polygone V16 2432 (socle allonge ~75 x 14 m): le plan de la roue suit son grand axe, moyeu au centre du socle.
Hauteurs = landmarks: sommet (Skyviews Miami Observation Wheel, z 70.3, 4 cams) et moyeu (Center E/W, z 36-38)
-> rayon = sommet - moyeu. Structure type Skyviews/London Eye reduite: deux jantes (+-1.6 m), rayons, 42 nacelles,
axe, pieds en A de part et d'autre, socle V16 extrude.
Usage: PYTHONPATH=. python3 tools/gen_ferris_wheel.py [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda f: os.path.join(ROOT, 'gtamapdata', f)
NAME = 'Skyviews Miami Observation Wheel'
# ajustement tools (scratchpad wfit.py) sur Shoreline [Gameinformer], Vice City 08 (Ferris Wheel), Port Vice City (A),
# Vice City 11 (Megamundo): residus <= 11 px (1920); azimut 61.1 deg vs 64.0 pour le socle V16, moyeu 7 m au NE du centre du socle
FIT = [31.3, 132.5, 36.0, 32.9, 1.0664]


def build():
    F = {f['id']: f for f in json.load(open(D('v16_footprints.json')))['polygons']}
    L = json.load(open(D('landmarks.json')))
    R_ = np.array(F[2432]['ring'], float); c = R_.mean(0)
    u = np.linalg.svd(R_ - c)[2][0]; u /= np.linalg.norm(u); n = np.array([-u[1], u[0]])      # u = plan de la roue, n = axe
    top = np.array(L[NAME]['xyz']); hub_z = (L[NAME + ' Center (E)']['xyz'][2] + L[NAME + ' Center (W)']['xyz'][2]) / 2
    R = float(top[2] - hub_z); E = []
    if FIT:     # [WHEEL-V2] moyeu, rayon et azimut du plan ajustes sur le contour de la jante (g/d/haut/bas) + moyeu dans 4 cams
        c = np.array(FIT[:2]); hub_z = FIT[2]; R = FIT[3]; u = np.array([np.cos(FIT[4]), np.sin(FIT[4])]); n = np.array([-u[1], u[0]])
    P = lambda t, w, z: [round(float((c + u * t + n * w)[0]), 2), round(float((c + u * t + n * w)[1]), 2), round(float(z), 2)]
    L_ = lambda a, b: E.append([a, b])
    ang = np.linspace(0, 2 * np.pi, 49)
    for w in (-1.6, 1.6):                                             # jantes (double anneau) + entretoises
        for r in (R, R - 1.8):
            for a0, a1 in zip(ang[:-1], ang[1:]): L_(P(r * np.cos(a0), w, hub_z + r * np.sin(a0)), P(r * np.cos(a1), w, hub_z + r * np.sin(a1)))
    for a in ang[:-1:2]:
        L_(P(R * np.cos(a), -1.6, hub_z + R * np.sin(a)), P(R * np.cos(a), 1.6, hub_z + R * np.sin(a)))
    for a in np.linspace(0, 2 * np.pi, 32, endpoint=False):           # rayons (cables) depuis les deux bouts du moyeu
        for w in (-3.5, 3.5): L_(P(0, w, hub_z), P((R - 1.8) * np.cos(a), np.sign(w) * 1.6, hub_z + (R - 1.8) * np.sin(a)))
    L_(P(0, -4.5, hub_z), P(0, 4.5, hub_z))                           # axe
    for a in np.linspace(0, 2 * np.pi, 42, endpoint=False):           # nacelles (capsules exterieures 3 x 2.4 x 2.6 m)
        cx, cz = (R - 2.4) * np.cos(a), hub_z + (R - 2.4) * np.sin(a)   # nacelles a l'interieur de la jante lumineuse (vu dans Vice City 08)
        cs = [(cx - 1.5, -1.2), (cx + 1.5, -1.2), (cx + 1.5, 1.2), (cx - 1.5, 1.2)]
        for z in (cz - 1.3, cz + 1.3):
            for i in range(4): L_(P(cs[i][0], cs[i][1], z), P(cs[(i + 1) % 4][0], cs[(i + 1) % 4][1], z))
        for t, w in cs: L_(P(t, w, cz - 1.3), P(t, w, cz + 1.3))
    zg = 1.5
    for w in (-4.5, 4.5):                                             # pieds en A (de chaque cote du plan, ecartes en pied)
        for t in (-0.42 * R, 0.42 * R):
            L_(P(0, w, hub_z), P(t, w * 2.2, zg))
        L_(P(-0.42 * R, w * 2.2, zg), P(0.42 * R, w * 2.2, zg))
        L_(P(-0.21 * R, w * 1.6, (hub_z + zg) / 2), P(0.21 * R, w * 1.6, (hub_z + zg) / 2))
    ring = [[float(p[0]), float(p[1])] for p in R_]                  # socle V16 extrude (gare d'embarquement, 4 m)
    for z in (zg - 1.5, zg + 2.5):
        for i in range(len(ring)): L_([*map(lambda v: round(v, 2), ring[i]), z], [*map(lambda v: round(v, 2), ring[(i + 1) % len(ring)]), z])
    for p in ring: L_([round(p[0], 2), round(p[1], 2), zg - 1.5], [round(p[0], 2), round(p[1], 2), zg + 2.5])
    note = ('WHEEL-V2 2026-09-30 (demande Alexandre): socle = polygone V16 2432; moyeu (%.1f, %.1f, %.1f), rayon de jante %.1f m, '
            'azimut du plan %.1f deg AJUSTES sur le contour de la jante + moyeu dans 4 cams (Shoreline, Vice City 08, Port VC A, '
            'Megamundo; residus <= 11 px); coherent avec le socle V16 (64 deg) et le sommet LM (z %.1f). 2 jantes, 32 rayons, 42 nacelles, pieds en A.'
            % (c[0], c[1], hub_z, R, np.degrees(np.arctan2(u[1], u[0])) % 180, top[2]))
    return {NAME: {'color': '#f5f5f4', 'world_edges': E, 'note': note, '_credit': 'Alexandre Leblanc (landmarks) + Claude Opus 5.5'}}


if __name__ == '__main__':
    out = build(); print(NAME, len(out[NAME]['world_edges']), 'aretes |', out[NAME]['note'])
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = D('building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_wheel_0930')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
