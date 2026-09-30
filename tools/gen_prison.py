#!/usr/bin/env python3
"""gen_prison.py — mesh de la prison (Hamlet / Grassrivers). [PRISON-V1 2026-09-30]

Plan = polygones V16 (batiments 940-963, tours 964-981). Hauteurs LUES dans Prison (Aerial) (Biplane) apres recalage
de sa pose sur les 6 tours (sommet = landmark Prison Tower (n), pied = sol heightmap sous le polygone V16 de la tour,
+ chateau d'eau Homestead): rms 5 px; echelles verticales tous les 2 m aux coins avant de chaque batiment.
Tours: fut (V16 38 m2) jusqu'a sommet LM - 5 m, cabine plus large (V16 46 m2 x 1.25) jusqu'au sommet LM, toit conique.
Cloture double sur l'hexagone des tours (4.5 m, interieure par les tours, exterieure a +7 m).
Usage: PYTHONPATH=. python3 tools/gen_prison.py [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
D = lambda f: os.path.join(ROOT, 'gtamapdata', f)
# hauteur de l'egout (m au-dessus du sol) lue dans l'aerien; +ridge = toit a deux pans (tuiles rouges)
H = {941: (8, 3), 942: (6, 3), 943: (8, 3), 944: (7, 3), 945: (6, 2.5), 946: (8, 3.5), 947: (8, 3), 952: (18, 0),
     954: (8, 3.5), 955: (6, 2.5), 956: (6, 2.5), 958: (12, 4), 959: (13, 0), 960: (6, 2.5), 961: (6, 2.5)}
SMALL = [940, 948, 949, 950, 951, 953, 957, 962, 963]          # petits batiments: 4 m (non mesures, trop petits)
TOWERS = {1: (973, 974, 975), 2: (970, 971, 972), 3: (967, 968, 969), 4: (964, 965, 966), 5: (979, 980, 981), 6: (976, 977, 978)}


def build():
    import v16_resect as RR
    F = {f['id']: f for f in json.load(open(D('v16_footprints.json')))['polygons']}
    L = json.load(open(D('landmarks.json')))
    E = []
    def seg(a, b): E.append([[round(float(a[0]), 2), round(float(a[1]), 2), round(float(a[2]), 2)], [round(float(b[0]), 2), round(float(b[1]), 2), round(float(b[2]), 2)]])
    def ring(pts, z):
        for i in range(len(pts)): seg([*pts[i], z], [*pts[(i + 1) % len(pts)], z])
    def prism(pts, z0, z1):
        ring(pts, z0); ring(pts, z1)
        for p in pts: seg([*p, z0], [*p, z1])
    out = {}
    B = []
    for pid, (eave, ridge) in list(H.items()) + [(p, (4, 0)) for p in SMALL]:
        r = np.array(F[pid]['ring'], float); g = RR.ground(*r.mean(0)); prism(r, g, g + eave)
        if ridge:                                            # faitage le long du grand axe
            c = r.mean(0); u = np.linalg.svd(r - c)[2][0]; s = (r - c) @ u
            a, b = c + u * s.min(), c + u * s.max(); seg([*a, g + eave + ridge], [*b, g + eave + ridge])
            for p in r:                                      # pans: coins -> faitage le plus proche
                t = np.clip((p - c) @ u, s.min(), s.max()); q = c + u * t
                seg([*p, g + eave], [*q, g + eave + ridge])
    out['Prison (Buildings)'] = E; E = []
    cents = {}
    for t, (p42, p46, p38) in TOWERS.items():
        c = np.array(F[p42]['centroid']); cents[t] = c; g = RR.ground(*c); zt = float(L['Prison Tower (%d)' % t]['xyz'][2])
        r0 = np.sqrt(F[p38]['area'] / np.pi); r1 = np.sqrt(F[p46]['area'] / np.pi) * 1.25
        circ = lambda r, n=14: [c + r * np.array([np.cos(a), np.sin(a)]) for a in np.linspace(0, 2 * np.pi, n, endpoint=False)]
        prism(circ(r0), g, zt - 5.0)
        for z in np.arange(g + 5, zt - 5, 5.0): ring(circ(r0), z)
        prism(circ(r1), zt - 5.0, zt - 1.5)                  # cabine vitree
        ring(circ(r1 + 0.6), zt - 1.5)
        for p in circ(r1 + 0.6, 8): seg([*p, zt - 1.5], [*c, zt + 0.8])      # toit conique
    out['Prison Towers'] = E; E = []
    order = [1, 2, 3, 4, 5, 6]
    P = np.array([cents[t] for t in order]); ctr = P.mean(0)
    for off in (0.0, 7.0):
        Q = [p + (p - ctr) / np.linalg.norm(p - ctr) * off for p in P]
        for i in range(6):
            a, b = Q[i], Q[(i + 1) % 6]; n = max(2, int(np.linalg.norm(b - a) / 8))
            for k in range(n + 1):
                p = a + (b - a) * k / n; g = RR.ground(*p); seg([*p, g], [*p, g + 4.5])
            ga, gb = RR.ground(*a), RR.ground(*b)
            for dz in (0.3, 4.5): seg([*a, ga + dz], [*b, gb + dz])
    out['Prison Fence'] = E
    note = ('PRISON-V1 2026-09-30 (demande Alexandre): plan V16 (batiments 940-963, tours 964-981); hauteurs lues dans Prison (Aerial) '
            '(Biplane) recale sur les 6 tours (rms 5 px): blocs cellulaires 6-8 m a l egout + toit a deux pans, bloc blanc central 18 m, '
            'entrepot blanc nord 13 m, bloc est 12 m; petits batiments 4 m (ESTIME). Tours: sommets = landmarks Prison Tower (1-6). '
            'Cloture double 4.5 m (ESTIME) sur l hexagone des tours.')
    cols = {'Prison (Buildings)': '#fca5a5', 'Prison Towers': '#e5e7eb', 'Prison Fence': '#a3a3a3'}
    return {k: {'color': cols[k], 'world_edges': v, 'note': note, '_credit': 'Alexandre Leblanc (V16 + landmarks) + Claude Opus 5.5'} for k, v in out.items()}


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print(k, len(v['world_edges']), 'aretes')
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = D('building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_prison_0930')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
