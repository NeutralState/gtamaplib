#!/usr/bin/env python3
"""gen_portofino.py — Portofino Tower (South Pointe) en plan en Y. [PORTOFINO-V2 2026-10-01]

Plan en Y (trois ailes a bouts arrondis + noyau rond), comme la vue pre-alpha (forme seulement: sa position, 25 m au SE,
n'est pas fiable) et l'IRL. Position/orientation/longueurs AJUSTEES sur:
  - les 3 sommets de pavillons triangules (LMs Portofino Tower (NW)/(NE)/(S), 2-4 cams chacun) = centres des couronnes,
  - la silhouette dans Dominion Hotel (pose 10 clics <= 3 px): largeur du fut a z 100 (x 53..297) et au-dessus de
    l'epaulement a z 133 (x 80..263); residus 4-8 px.
Hauteurs lues dans Dominion Hotel (3.6 px/m): epaulement 126 m, toit 140 m, pavillons 129 -> 146 m + pyramide jusqu'aux LMs.
Usage: PYTHONPATH=. python3 tools/gen_portofino.py [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np, cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
D = lambda f: os.path.join(ROOT, 'gtamapdata', f)
CX, CY, TH, LW, HW, RC, DL, LC = 1752.95, -190.83, -11.5, 30.3, 10.95, 15.0, 6.18, 16.27
Z_SHOULDER, Z_ROOF, Z_CROWN0, Z_EAVE, A_CROWN = 126.0, 140.0, 129.0, 146.0, 12.0


def yplan(Lw, hw=HW, Rc=RC, round_ends=True):
    K = 5.0; S = 350; m = np.zeros((S * 2, S * 2), np.uint8); T = lambda x, y: (int(S + x * K), int(S - y * K))
    cv2.circle(m, T(0, 0), int(Rc * K), 255, -1)
    for a in (180, 60, -60):
        t = np.radians(a + TH); u = np.array([np.cos(t), np.sin(t)]); n = np.array([-u[1], u[0]])
        e = Lw - (hw if round_ends else 0)
        P = [n * hw, u * e + n * hw, u * e - n * hw, -n * hw]; cv2.fillPoly(m, [np.array([T(*p) for p in P], np.int32)], 255)
        if round_ends: cv2.circle(m, T(*(u * e)), int(hw * K), 255, -1)
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); c = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 0.35 * K, True).reshape(-1, 2)
    return [[CX + (px - S) / K, CY - (py - S) / K] for px, py in c]


def build():
    import v16_resect as RR
    L = json.load(open(D('landmarks.json'))); g = RR.ground(CX, CY); E = []
    def seg(a, b): E.append([[round(float(v), 2) for v in a], [round(float(v), 2) for v in b]])
    def ring(r, z):
        for i in range(len(r)): seg([*r[i], z], [*r[(i + 1) % len(r)], z])
    def prism(r, z0, z1, floor=3.3, vstep=1):
        zs = [z0] + list(np.arange(z0 + floor, z1, floor)) + [z1]
        for z in zs: ring(r, z)
        for p in r[::vstep]: seg([*p, z0], [*p, z1])
    full = yplan(LW); prism(full, g, Z_SHOULDER, vstep=max(1, len(full) // 30))
    up = yplan(LW - DL); prism(up, Z_SHOULDER, Z_ROOF, vstep=max(1, len(up) // 24)); ring(up, Z_ROOF + 1.2)
    for p in up[::max(1, len(up) // 24)]: seg([*p, Z_ROOF], [*p, Z_ROOF + 1.2])
    for a, k in zip((180, 60, -60), ('NW', 'NE', 'S')):            # pavillons a pyramide (couronnes) sur les 3 ailes
        t = np.radians(a + TH); u = np.array([np.cos(t), np.sin(t)]); n = np.array([-u[1], u[0]])
        c = np.array([CX, CY]) + u * LC; h = A_CROWN / 2
        sq = [c + u * h + n * h, c + u * h - n * h, c - u * h - n * h, c - u * h + n * h]
        prism(sq, Z_CROWN0, Z_EAVE, floor=3.4); ring([c + (q - c) * 1.12 for q in sq], Z_EAVE)
        apex = [*c, float(L['Portofino Tower (%s)' % k]['xyz'][2])]
        for q in sq: seg([*(c + (q - c) * 1.12), Z_EAVE], apex)
    note = ('PORTOFINO-V2 2026-10-01 (Alexandre: garder la position, rendre plus fidele): plan en Y (3 ailes arrondies + noyau) '
            'ajuste sur les 3 sommets de pavillons triangules et la silhouette de Dominion Hotel (residus 4-8 px); epaulement '
            '%.0f m, toit %.0f m, pavillons %.0f-%.0f m + pyramides aux LMs (lus dans Dominion Hotel). Forme du Y: vue pre-alpha '
            '(position de cette vue NON utilisee).' % (Z_SHOULDER, Z_ROOF, Z_CROWN0, Z_EAVE))
    return {'Portofino Tower': {'color': '#a78bfa', 'world_edges': E, 'note': note, '_credit': 'Alexandre Leblanc (landmarks) + Claude Opus 5.5'}}


if __name__ == '__main__':
    out = build(); print(len(out['Portofino Tower']['world_edges']), 'aretes')
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = D('building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_portofino_1001')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
