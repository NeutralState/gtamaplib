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
    'Jade Ocean Condos': {'poly': 3584, 'color': '#34d399', 'shift': (-13.0, -3.6), 'groups': [
        ([3, 7, 8, 11, 15, 16, 9, 10, 12, 13, 14], 202.9), ([1, 4, 6, 2, 17, 19, 20, 21], 196.9), ([0, 5, 18, 22], 190.9)],
        'drum': ([9, 10, 12, 13, 14], 4.0),
        'src': 'sommet LM 202.9 (2 LMs); gradins -6/-12 m et tambour +4 m ESTIMES d apres le chanfrein de la couronne vu dans Biplane Night. '
               'Largeur du fut verifiee dans Beach et Biplane Night (93 vs 90 px, 132 vs 130 px); DISCORDANCE: les deux vues placent la tour '
               '13 m a l ouest / 4 m au sud du polygone V16 (residu 2 px) -> garde sur la V16, a arbitrer'},
    # 1500 Ocean Dr (V16 3335): tour courbe a bout arrondi (region 4) sur podium a facade a persiennes (region 1),
    # lame rose a bow-windows octogonaux (region 2), immeuble ouest (0) + tourelle hexagonale (3). Comme l'IRL.
    '1500 Ocean Dr': {'poly': 3335, 'color': '#f9a8d4', 'shift': (-25.0, 0.0), 'groups': [([4], 63.8), ([2], 62.3), ([1], 21.0), ([0], 34.0), ([3], 36.0)],
        'src': 'tour 63.8 (LM) et lame rose 62.3 (3 LMs S/SE/NW/SW); podium 21 m LU dans Vice Beach (B) (echelles aux coins); '
               'immeuble ouest 34 m LU (toit a gradins blanc derriere la lame, Vice Beach (B)), tourelle hexagonale 36 m ESTIMEE. Note: Vice Beach (B) montre tout le complexe ~10-15 m au NO de la V16 (pose de la cam non verifiee, la tour Jade Ocean est decalee dans une autre direction -> pas un decalage V16)'},
    # --- Vice Beach, plus hautes tours (2026-09-30, demande Alexandre). Hauteur de la region qui contient le LM = LM;
    # les autres volumes ESTIMES (proportions IRL); les traits V16 donnent la forme (arrondis, ailes, gradins).
    # CORRIGE (Alexandre): la tour = le carre a verriere pyramidale (X de la V16) + ses ailes; le grand polygone = le podium bas
    'Blue Diamond': {'poly': 3575, 'color': '#60a5fa', 'shift': (-39.8, -18.8), 'groups': [([2, 3, 5, 7], 126.0), ([0], 40.0), ([1], 40.0), ([6], 40.0), ([4], 14.0)], 'core_scale': ([2, 3, 5, 7], 1.35),
        'pyramid': ([2, 3, 5, 7], 14.0), 'src': 'tour = carre a X de la V16 elargi x1.35 (largeur lue dans Venetian Islands: 63 px), toit 126 m + pyramide 14 m LUS dans Venetian Islands (le LM 146 = pointe lumineuse, 6 m au-dessus de la pyramide lue); tour ~30 px a l est de la V16 dans cette vue (garde sur la V16), ailes basses 40 m ESTIMEES (Venetian Islands: fut etroit), verriere pyramidale +14 m (vue dans Biplane Night (Video) Last); podium (region 4) 14 m ESTIME'},
    'Green Diamond': {'poly': 3576, 'color': '#4ade80', 'shift': (-22.5, -23.4), 'groups': [([2, 3, 4, 6], 126.0), ([0], 40.0), ([1], 40.0), ([5], 40.0), ([7], 14.0)], 'core_scale': ([2, 3, 4, 6], 1.35),
        'pyramid': ([2, 3, 4, 6], 14.0), 'src': 'tour = carre a X de la V16 elargi x1.35 (largeur lue dans Venetian Islands: 60 px), toit 126 m + pyramide 14 m LUS dans Venetian Islands (LM 145 = pointe); tour ~30 px a l est de la V16 dans cette vue (garde sur la V16), ailes basses 40 m ESTIMEES (Venetian Islands: fut etroit), verriere pyramidale +14 m (vue dans Biplane Night (Video) Last); podium (region 7) 14 m ESTIME'},
    'Icon at South Beach': {'poly': 3251, 'color': '#f472b6', 'groups': [([0], 142.0), ([1], 147.0), ([2], 110.0)],
        'src': 'tour (region 0) = LM 142; couronne (region 1) +5 m et aile courbe (region 2) 110 m ESTIMES'},
    'Murano Grande': {'poly': 3233, 'color': '#fb923c', 'groups': [([1], 139.0), ([2], 133.0), ([4], 127.0), ([3], 12.0), ([0], 30.0)],
        'src': 'tour courbe en 3 segments V16 (1,2,4): 139 (LM) puis gradins 133/127 ESTIMES; podium 12 et bloc 0 30 m ESTIMES'},
    'Tresor Tower': {'poly': 3573, 'color': '#c084fc', 'shift': (-25.2, -6.2), 'groups': [([3, 1], 120.0), ([2], 100.0), ([0], 12.0)],
        'src': 'fut rond + lame (regions 3,1) = LM 120; aile est 100 m et podium 12 m ESTIMES'},
    'Flamingo South Beach': {'poly': 3400, 'color': '#fda4af', 'groups': [([2], 111.0), ([0], 51.0), ([1], 52.0), ([3], 62.0)],
        'src': 'hauteurs par region = LMs contenus (T* 111, NENE/NERNE 51-55, NWNE 52, SDS/SRSW 59-64): toutes MESUREES'},
    'The Waverly South Beach': {'poly': 3302, 'color': '#fde68a', 'groups': [([0], 113.0), ([1], 107.0)],
        'src': 'lame sud = LM (SE) 113; lame nord 107 = LM (NW) (35 m hors empreinte: attribution ESTIMEE)'},
    'The Ritz-Carlton Bal Harbour': {'poly': 3588, 'color': '#e5e7eb', 'groups': [([0, 1, 3], 104.0), ([2], 108.0), ([4, 5], 30.0)],
        'src': 'lame courbe (regions 0,1,3) = LM 104; edicule 108 et ailes basses courbes 30 m ESTIMES'},
    'Apogee Condominium': {'poly': 3228, 'color': '#a5b4fc', 'groups': [([0], 93.0), ([1], 15.0)],
        'src': 'tour (region 0) = LM 93; podium (region 1) 15 m ESTIME'},
    'Akoya Condominium': {'poly': 3586, 'color': '#99f6e4', 'groups': [([0], 145.0)],
        'src': 'plan cruciforme V16 = LM 145'},
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
        if S.get('shift'):   # [VB-SETBACK 2026-10-01] V16 Vice Beach = parcelle (terrasse/piscine cote plage): tour recalee sur les images
            sh = np.array(S['shift']); R = {i: dict(r, ring=[list(np.array(p) + sh) for p in r['ring']], centroid=list(np.array(r['centroid']) + sh)) for i, r in R.items()}
        if S.get('core_scale'):
            ids, sc = S['core_scale']; cc = np.mean(np.vstack([np.array(R[i]['ring']) for i in ids]), 0)
            for i in ids: R[i] = dict(R[i], ring=[list(cc + (np.array(p) - cc) * sc) for p in R[i]['ring']])
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
        if S.get('pyramid'):
            ids, ah = S['pyramid']; zb = max(H[i] for i in ids); Up = union_ring([R[i] for i in ids]); ap = np.mean(Up, 0)
            for p in Up: seg([*p, zb], [*ap, zb + ah])
        if S.get('drum'):
            ids, dh = S['drum']; ztop = max(H[i] for i in ids)
            Ud = union_ring([R[i] for i in ids]); ring(Ud, ztop + dh)
            for p in Ud: seg([*p, ztop], [*p, ztop + dh])
        out[name] = {'color': S['color'], 'world_edges': E, '_credit': 'Alexandre Leblanc (V16 + landmarks) + Claude Opus 5.5',
                     'note': 'TIERED-MESH-V1 2026-09-30: volumes = traits interieurs du polygone V16 %d (%d regions, tools/v16_tiers.py); %s.%s'
                             % (S['poly'], len(R), S['src'], (' DECALE de (%.1f, %.1f) m par rapport a la V16 (VB-SETBACK, valide Alexandre 2026-10-01: la V16 de Vice Beach dessine la parcelle, la tour est en retrait; decalage lu dans les images)' % tuple(S['shift'])) if S.get('shift') else '')}
    return out


if __name__ == '__main__':
    names = [a for a in sys.argv[1:] if not a.startswith('--') and not a.endswith('.json')]
    out = build(names or None)
    for k, v in out.items(): print(k, len(v['world_edges']))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = D('building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_tiered_0930')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
