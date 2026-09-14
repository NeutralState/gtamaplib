#!/usr/bin/env python3
"""gen_marina_blue_mesh.py — mesh procedural Marina Blue (tour nord « spinnaker »). [MB-MESH-V1 2026-09-13]

Pourquoi un generateur dedie: la V16 ne dessine que l'ilot entier (podium 88x77 m, polygone 2577) et l'extrusion
generique (gen_footprint_mesh.py) donnait une boite 3x trop large (Alexandre: « le marina blue est 0 comme ca »).
IRL (Arquitectonica): « the North Tower bows out like a blue spinnaker » — face sud droite, face nord bombee.
Nos 4 coins de toit (SW 4 cams, NE 6 cams, NW 2 cams, SE tooltip) dessinent exactement cette voile:
corde SW->SE = 63 m, bombement nord 13-20 m (NE, NW). Plan = corde droite SW->SE + courbe Catmull-Rom SW->NW->NE->SE.
Fut extrude du sol (heightmap) au toit (mediane des 4 coins), anneaux tous les 5 m (rythme des balcons), couronne au toit.
Non modelise: la tour sud plus basse (LNE, z 127) et le podium vitre.

Usage: PYTHONPATH=. /usr/local/bin/python3 tools/gen_marina_blue_mesh.py [--apply] [--out draft.json] [--ring 5]
"""
import argparse, json, os, sys
import numpy as np
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS)
from horizon_resect import ground
B = 'Marina Blue'

def catmull_rom(P, n_per=8):
    P = np.asarray(P, float); out = []
    Q = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        for t in np.linspace(0, 1, n_per, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1]); return np.array(out)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--apply', action='store_true'); ap.add_argument('--out'); ap.add_argument('--ring', type=float, default=5.0)
    ap.add_argument('--se', type=float, nargs=2, default=None, help='coin SE impose (x y): le tooltip SE d\'Alexandre est « environ »; Skyline (vue en bout depuis le NE) montre la tour ~10 m plus large cote SE')
    a = ap.parse_args()
    L = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    c = {k: np.array(L[f'{B} ({k})']['xyz'], float) for k in ('SW', 'NW', 'NE', 'SE')}
    if a.se: c['SE'] = np.array([a.se[0], a.se[1], c['SE'][2]])
    z_roof = float(np.median([c[k][2] for k in c])); z_ground = float(ground(*((c['SW'][:2] + c['SE'][:2]) / 2)))
    north = catmull_rom([c['SW'][:2], c['NW'][:2], c['NE'][:2], c['SE'][:2]])       # face nord bombee (SW -> SE)
    ring = np.vstack([north, [c['SE'][:2]], [c['SW'][:2]]])                           # + corde sud SE -> SW (fermeture)
    # dedoublonner
    keep = [0] + [i for i in range(1, len(ring)) if np.linalg.norm(ring[i] - ring[i - 1]) > 0.3]; ring = ring[keep]
    if np.linalg.norm(ring[-1] - ring[0]) < 0.3: ring = ring[:-1]
    def loop(z): return [[[float(p[0]), float(p[1]), z], [float(q[0]), float(q[1]), z]] for p, q in zip(ring, np.roll(ring, -1, axis=0))]
    edges = loop(z_ground) + loop(z_roof) + loop(z_roof - 4.0)   # couronne = double anneau au sommet
    for k in ('SW', 'NW', 'NE', 'SE'):
        edges.append([[float(c[k][0]), float(c[k][1]), z_ground], [float(c[k][0]), float(c[k][1]), z_roof]])
    z = z_ground + a.ring
    while z < z_roof - 5: edges += loop(z); z += a.ring
    # [MB-MESH-V2] tour 2 (plus basse, 52 etages IRL): lobe nord-est de l'ilot V16 (polygone 2577, face courbe
    # (-466.7,453.3)->(-441.1,425.6)), adossee a la face nord de la tour 1; coin NW = LNE (3 cams, z 126.6).
    # Identifiee par projection: Jason Duval 05 (tour basse a gauche du fut, sommet a LNE) et Port Vice City (B)
    # (tour basse a droite, couronne bleue a LNE). La lame nord-ouest du bloc etait l'autre hypothese: refutee
    # (elle chevauchait la tour 1 dans Jason Duval 05).
    lne = np.array(L[f'{B} (LNE)']['xyz'], float); z2 = float(lne[2])
    ring2 = np.array([[lne[0], lne[1]], [-458.5, 450.4], [-452.3, 444.9], [-446.6, 436.9], [-441.1, 425.6], [-446.9, 421.5],
                      [c['NE'][0], c['NE'][1]], [lne[0], 419.0]])
    def loop2(z): return [[[float(p[0]), float(p[1]), z], [float(q[0]), float(q[1]), z]] for p, q in zip(ring2, np.roll(ring2, -1, axis=0))]
    edges += loop2(z_ground) + loop2(z2) + loop2(z2 - 3.0)
    for p in ring2: edges.append([[float(p[0]), float(p[1]), z_ground], [float(p[0]), float(p[1]), z2]])
    z = z_ground + a.ring
    while z < z2 - 4: edges += loop2(z); z += a.ring
    chord = float(np.linalg.norm(c['SE'][:2] - c['SW'][:2]))
    mesh = {'color': '#38bdf8', 'world_edges': edges,
            'note': f'MB-MESH-V1 2026-09-13: fut « spinnaker » sur les 4 coins de toit (corde SW-SE {chord:.1f} m, face nord Catmull-Rom SW-NW-NE-SE), sol {z_ground:.1f} (heightmap), toit {z_roof:.1f} (mediane 4 coins), anneaux {a.ring:g} m, couronne 4 m; tour 2 (lobe NE de l\'ilot V16, coin NW = LNE, toit {z2:.1f}) incluse [MB-MESH-V2]; podium non modelise; la V16 ne dessine que l\'ilot (polygone 2577)',
            '_credit': 'coins: triangulation gtamaplib (SW 4 cams, NE 6 cams, NW 2 cams, SE tooltip V16 Alexandre' + (f', SE deplace a ({a.se[0]}, {a.se[1]}) = bord est de l\'ilot V16, d\'apres la silhouette Skyline' if a.se else '') + ')'}
    print(f'{B}: corde {chord:.1f} m, sol {z_ground:.1f}, toit {z_roof:.1f}, {len(ring)} sommets, {len(edges)} aretes')
    if a.out: json.dump({B: mesh}, open(a.out, 'w'), ensure_ascii=True); print('->', a.out)
    if a.apply:
        mp = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json'); M = json.load(open(mp)); M[B] = mesh
        json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique ->', mp, len(M), 'meshs')

if __name__ == '__main__':
    main()
