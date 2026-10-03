#!/usr/bin/env python3
"""gen_garage_2693.py — parking a etages a cote du stade (V16 2693, marqueur S2/05). [GARAGE-2693-V1 2026-10-03]

Plan RE-MESURE dans Street (Lucia) (N) (seule vue utilisable; Lucia (S) ne le voit pas, biplan v2370 trop flou): bouts ouest/est
x -1421 / -1335 (rayons u 518 / 1000 coupes par la facade sud), facade sud y ~1082 (espacement des bandes d'etages compatible
with 1075-1082; = trace V16), profondeur N-S non mesurable -> V16 2693. Ancien: polygone V16 coupe a l'ouest a x = -1421 (Alexandre: « le parking est pas aussi gros »): dans Street (Lucia) (N) la facade
sud a bandes va de la cage d'escalier grise (x -1421..-1412) au coin est (x -1335, V16 -1333); a l'ouest c'est un autre batiment bas.
Hauteur LUE dans Street (Lucia) (N): haut de la facade sol + 20.3 m (v 509) (rayons coupes par le plan de la facade y 1082), cage grise +2.2 m.
6 niveaux. Profondeur N-S: V16 (une seule vue).
Usage: PYTHONPATH=. python3 tools/gen_garage_2693.py [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import v16_resect as RR

H_ROOF, H_CORE, N_LEV = 20.3, 2.5, 6
X_WEST = -1421.0      # bout ouest LU (cage d'escalier grise, Street (Lucia) (N), u 518); a l'ouest: autre batiment bas (non modelise)
X_EAST = -1335.0      # bout est LU (Street (Lucia) (N), u 1000)
r2 = lambda v: [round(float(a), 2) for a in v]


def build():
    F = {p['id']: p for p in json.load(open(os.path.join(ROOT, 'gtamapdata', 'v16_footprints.json')))['polygons']}
    import cv2
    R0 = np.array(F[2693]['ring']); K = 5.0; x0, y0 = R0.min(0) - 2; x1, y1 = R0.max(0) + 2
    m = np.zeros((int((y1 - y0) * K) + 1, int((x1 - x0) * K) + 1), np.uint8)
    cv2.fillPoly(m, [np.array([[(x - x0) * K, (y1 - y) * K] for x, y in R0], np.int32)], 1); m[:, :int((X_WEST - x0) * K)] = 0; m[:, int((X_EAST - x0) * K):] = 0
    c = cv2.approxPolyDP(max(cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea), 0.4 * K, True).reshape(-1, 2)
    R = np.array([[x0 + px / K, y1 - py / K] for px, py in c]); g = RR.ground(*R.mean(0)); zt = g + H_ROOF
    E = []; L = lambda a, b: E.append([r2(a), r2(b)])
    ring = lambda P, z: [L([*P[i], z], [*P[(i + 1) % len(P)], z]) for i in range(len(P))]
    for k in range(N_LEV + 1): ring(R, g + k * H_ROOF / N_LEV)                 # dalles
    ring(R, zt + 1.1)                                                            # garde-corps du toit
    for p in R: L([*p, g], [*p, zt + 1.1])
    # poteaux de facade le long des grands cotes (rythme ~8.5 m)
    for i in range(len(R)):
        a, b = R[i], R[(i + 1) % len(R)]; n = int(np.hypot(*(b - a)) // 8.5)
        for t in np.linspace(0, 1, n + 1)[1:-1]: L([*(a + (b - a) * t), g], [*(a + (b - a) * t), zt])
    CORES = [np.array([[-1421.0, 1081.0], [-1412.5, 1081.0], [-1412.5, 1090.0], [-1421.0, 1090.0]]),   # cage grise ouest (LUE)
             R0[[2, 3, 4, 5]]]                                                                           # saillie sud-est V16
    for C, hc in ((CORES[0], H_ROOF + 2.2), (CORES[1], H_ROOF + H_CORE)):
        zc = g + hc
        ring(C, zc)
        for p in C: L([*p, zt], [*p, zc])
        continue
    return {'Parking Garage (V16 2693)': {'color': '#cbd5e1', 'world_edges': E, '_credit': 'Alexandre Leblanc (V16) + Claude Opus 5.5',
            'note': 'GARAGE-2693-V1 2026-10-03: plan V16 2693 (marqueur S2/05 a cote); coupe a l ouest a x -1421 et toit sol + 20.3 m LUS dans Street '
                    '(Lucia) (N) (facade sud a bandes de couleur), 6 niveaux; cage grise ouest +2.2 m LUE; profondeur N-S = V16. Voir tools/gen_garage_2693.py'}}


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print(k, len(v['world_edges']))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = os.path.join(ROOT, 'gtamapdata', 'building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_garage2693_1003')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
