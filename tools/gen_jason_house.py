#!/usr/bin/env python3
"""gen_jason_house.py — maison de Jason (Keys) sur pilotis. [JASON-HOUSE-V1 2026-10-04, demande rlx]

La V16 ne dessine que des fragments ici: le plan vient des ~60 landmarks triangules (House (Keys), Jason's Safehouse Vehicles (X),
House with Boat (X)): pieds de piles a 1.9 m, plancher sur pilotis a 6.0 m (tetes de piles), corps principal x -2356.4..-2346.3,
y -5536..-5522 (coins de toit SW/SE/NE a 9.6-9.8 m), faitage N-S a 11.1 m (Roof (S)), veranda sud couverte a 7.4 m (VSE/VSW),
veranda haute nord a 7.3 m (Upper Veranda TNE), terrasse nord jusqu'a y -5512.6 (North Veranda TNE, 6.2 m), escalier avant
(est, Front Stairs MTNE/MTSE 5.8 m) et escalier arriere (ouest, Rear Stairs BW). Coin NW du corps: rectangle (non observe).
Usage: PYTHONPATH=. python3 tools/gen_jason_house.py [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z_G, Z_F, Z_EAVE, Z_RIDGE = 1.9, 6.0, 9.6, 11.1
BX0, BX1, BY0, BY1 = -2356.4, -2346.3, -5536.0, -5522.0          # corps principal
DX0, DX1, DY0, DY1 = -2357.7, -2345.5, -5538.9, -5512.6          # plancher sur pilotis (verandas comprises)
r2 = lambda v: [round(float(a), 2) for a in v]


def build():
    E = []; L = lambda a, b: E.append([r2(a), r2(b)])
    def rect(x0, x1, y0, y1, z):
        P = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        for i in range(4): L([*P[i], z], [*P[(i + 1) % 4], z])
    # pilotis (grille lue sur les piles 5-11) + plancher
    for x in (-2357.5, -2351.5, -2345.6):
        for y in (-5538.5, -5529.2, -5522.0, -5513.0):
            L([x, y, Z_G], [x, y, Z_F])
    rect(DX0, DX1, DY0, DY1, Z_F); rect(DX0, DX1, DY0, DY1, Z_F - 0.4)
    # corps principal: murs + pignons + toit a 2 pans (faitage N-S)
    rect(BX0, BX1, BY0, BY1, Z_EAVE)
    for x, y in ((BX0, BY0), (BX1, BY0), (BX1, BY1), (BX0, BY1)): L([x, y, Z_F], [x, y, Z_EAVE])
    xm = (BX0 + BX1) / 2
    L([xm, BY0, Z_RIDGE], [xm, BY1, Z_RIDGE])
    for y in (BY0, BY1):
        L([BX0, y, Z_EAVE], [xm, y, Z_RIDGE]); L([BX1, y, Z_EAVE], [xm, y, Z_RIDGE])
    for y in np.linspace(BY0, BY1, 5)[1:-1]:
        L([BX0 - 0.6, y, Z_EAVE - 0.2], [xm, y, Z_RIDGE]); L([BX1 + 0.6, y, Z_EAVE - 0.2], [xm, y, Z_RIDGE])
    # veranda sud couverte (toit 7.4, poteaux)
    rect(DX0, DX1, DY0, BY0, 7.4)
    for x in (DX0, -2351.5, DX1): L([x, DY0, Z_F], [x, DY0, 7.4])
    # veranda haute nord (7.3) + terrasse nord avec garde-corps
    rect(BX0, BX1, BY1, -5519.6, 7.3)
    for x in (BX0, BX1): L([x, -5519.6, Z_F], [x, -5519.6, 7.3])
    rect(DX0, DX1, -5519.6, DY1, Z_F + 1.0)
    for x, y in ((DX0, DY1), (DX1, DY1)): L([x, y, Z_F], [x, y, Z_F + 1.0])
    # escaliers: avant (est) et arriere (ouest)
    for w in (-5534.5, -5533.4):
        L([-2345.5, w, 5.8], [-2342.0, w, Z_G])
    L([-2357.7, -5522.4, Z_F], [-2359.6, -5522.4, 2.9]); L([-2357.7, -5523.4, Z_F], [-2359.6, -5523.4, 2.9])
    return {"Jason's House (Keys)": {'color': '#fde68a', 'world_edges': E, '_credit': 'Alexandre Leblanc (landmarks) + Claude Opus 5.5',
            'note': "JASON-HOUSE-V1 2026-10-04 (demande rlx): plan et hauteurs = ~60 landmarks triangules (pilotis 1.9->6.0, toit 9.6/11.1, "
                    "verandas 7.4/7.3, terrasse nord, escaliers); coin NW du corps non observe (rectangle). Voir tools/gen_jason_house.py"}}


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print(k, len(v['world_edges']))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = os.path.join(ROOT, 'gtamapdata', 'building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_jasonhouse_1004')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
