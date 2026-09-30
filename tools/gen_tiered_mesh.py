#!/usr/bin/env python3
"""gen_tiered_mesh.py — meshes a gradins depuis les VOLUMES V16 (tools/v16_tiers.py). [TIERED-MESH-V1 2026-09-30]

Pour chaque batiment de SPEC: polygone V16 -> regions (traits interieurs) -> hauteur par region (groupes nommes).
Geometrie: fut = contour exterieur (union) du sol jusqu'au plus bas des toits de gradins (anneaux d'etages tous les
~12 m), puis chaque region: anneau de toit a sa hauteur + aretes verticales depuis le haut du fut (parapet 1.2 m).
Elements de toit optionnels: 'drum' = region(s) couronne extrudee(s) de +h.
Usage: PYTHONPATH=. python3 tools/gen_tiered_mesh.py [nom ...] [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np
import cv2

THIS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(THIS); sys.path.insert(0, THIS)
D = lambda f: os.path.join(ROOT, 'gtamapdata', f)
import v16_tiers as VT

# Jade Ocean: V16 3584 = lame centrale (7,10,13,14,9,12,15) + ailes (3,8,11,16) + gradins aux deux bouts. Sommet 203 m
# (LMs Jade Ocean / (SW), 202.7-202.9). Les vues de nuit (Biplane Night) montrent un seul fut a bouts arrondis dont le
# sommet est chanfreine aux extremites (couronne de LED rouges): gradins ESTIMES a -6 m (anneau interieur) et -12 m
# (anneau exterieur); la couronne ronde de la V16 (regions 9,10,12,13,14 = cercle) en tambour de +4 m (ESTIME).
SPEC = {
    'Jade Ocean Condos': {'poly': 3584, 'color': '#34d399', 'groups': [
        ([3, 7, 8, 11, 15, 16, 9, 10, 12, 13, 14], 202.9), ([1, 4, 6, 2, 17, 19, 20, 21], 196.9), ([0, 5, 18, 22], 190.9)],
        'drum': ([9, 10, 12, 13, 14], 4.0),
        'src': 'sommet LM 202.9 (2 LMs); gradins -6/-12 m et tambour +4 m ESTIMES d apres le chanfrein de la couronne vu dans Biplane Night. '
               'Largeur du fut verifiee dans Beach et Biplane Night (93 vs 90 px, 132 vs 130 px); DISCORDANCE: les deux vues placent la tour '
               '13 m a l ouest / 4 m au sud du polygone V16 (residu 2 px) -> garde sur la V16, a arbitrer'},
}


def union_ring(regs):
    A = np.vstack([np.array(r['ring']) for r in regs]); x0, y0 = A.min(0) - 2; x1, y1 = A.max(0) + 2; K = 5.0
    m = np.zeros((int((y1 - y0) * K) + 1, int((x1 - x0) * K) + 1), np.uint8)
    for r in regs: cv2.fillPoly(m, [np.array([[(x - x0) * K, (y1 - y) * K] for x, y in r['ring']], np.int32)], 255)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); c = max(cs, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, 0.4 * K, True).reshape(-1, 2)
    return [[x0 + px / K, y1 - py / K] for px, py in c]


def build(names=None):
    import v16_resect as RR
    out = {}
    for name, S in SPEC.items():
        if names and name not in names: continue
        R = {r['id']: r for r in VT.regions(S['poly'])}; E = []
        def seg(a, b): E.append([[round(float(v), 2) for v in a], [round(float(v), 2) for v in b]])
        def ring(pts, z):
            for i in range(len(pts)): seg([*pts[i], z], [*pts[(i + 1) % len(pts)], z])
        H = {}
        for ids, z in S['groups']:
            for i in ids: H[i] = z
        used = [R[i] for i in H if i in R]
        g = RR.ground(*np.mean([r['centroid'] for r in used], 0)); zmin = min(H.values())
        U = union_ring(used)
        for z in [g] + list(np.arange(g + 12, zmin - 1, 12.0)) + [zmin]: ring(U, z)
        for p in U: seg([*p, g], [*p, zmin])
        for i, z in H.items():
            if i not in R: continue
            rr = R[i]['ring']; ring(rr, z); ring(rr, z + 1.2)
            if z > zmin:
                for p in rr: seg([*p, zmin], [*p, z + 1.2])
        if S.get('drum'):
            ids, dh = S['drum']; ztop = max(H[i] for i in ids)
            Ud = union_ring([R[i] for i in ids]); ring(Ud, ztop + dh)
            for p in Ud: seg([*p, ztop], [*p, ztop + dh])
        out[name] = {'color': S['color'], 'world_edges': E, '_credit': 'Alexandre Leblanc (V16 + landmarks) + Claude Opus 5.5',
                     'note': 'TIERED-MESH-V1 2026-09-30: volumes = traits interieurs du polygone V16 %d (%d regions, tools/v16_tiers.py); %s.'
                             % (S['poly'], len(R), S['src'])}
    return out


if __name__ == '__main__':
    names = [a for a in sys.argv[1:] if not a.startswith('--') and not a.endswith('.json')]
    out = build(names or None)
    for k, v in out.items(): print(k, len(v['world_edges']))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = D('building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_tiered_0930')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
