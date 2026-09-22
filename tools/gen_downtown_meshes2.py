#!/usr/bin/env python3
"""Lot Downtown / Brickell n. 2 (2026-09-22): tous les polygones V16 sans mesh qui contiennent (ou frolent a < 20 m)
un landmark de toit. Regle: plan = V16 (polygone rempli, ou tour dessinee en TRAITS extraite de la SVG), hauteur = landmark.

  Met 1 Condominium: tour = enveloppe convexe des 3 traits V16 (1448+811+567 m2) dans l'ilot 2261; toit 195.3
  The Palace Condominium: tour = enveloppe des 2 traits V16 (647+626 m2) dans l'ilot 1923; toit 136.3
  Asia Brickell Key: fut = enveloppe des polygones 3102 + 3103 (592 + 352 m2), toit 226 (coins CC2/CC2B); podium = 3100 (10 m ESTIME)
  Ten Museum Park 2568/138.6 | 100 Biscayne Blvd (NE) 2297/92.1 | Bayshore Place 1938/64.1 | Meditteranea 2166/61.0
  Keystone Park 2165/60.3 | Seybold Pointe 2217/52.7

Usage: gen_downtown_meshes2.py [--out brouillon.json] [--apply] [--only "Nom" ...]
"""
import json, sys, os, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_downtown_meshes import ring, ground, lm, extrude, entry, POLYS, LMS
import cv2


def hull(pts):
    h = cv2.convexHull(np.array(pts, np.float32)).reshape(-1, 2)
    return h.astype(float)


MET1 = [[-596.7, -582.8], [-597.6, -582.7], [-590.1, -540.8], [-566.9, -529.8], [-533.3, -535.7], [-531.7, -538.0], [-528.5, -544.1],
        [-522.6, -544.8], [-519.2, -542.2], [-516.0, -542.5], [-513.7, -546.6], [-588.7, -586.1], [-591.2, -581.6], [-585.2, -577.1], [-582.9, -573.1]]
PALACE = [[-807.1, -1549.7], [-814.4, -1556.3], [-839.0, -1578.9], [-851.7, -1590.6], [-863.0, -1578.3], [-795.3, -1538.8], [-806.5, -1526.6], [-818.0, -1537.1], [-850.2, -1566.6]]

SIMPLE = [
    ('Ten Museum Park', 2568, 'Ten Museum Park (SW)', '#38bdf8', 'Empreinte V16 2568 extrudee; toit = coins SW/SE/NE 134-139 (138.6)'),
    ('100 Biscayne Blvd (NE)', 2297, '100 Biscayne Blvd (NE)', '#a7f3d0', 'Aile NE du complexe 100 Biscayne: empreinte V16 2297 extrudee; toit = coin (NE) 92.1'),
    ('Bayshore Place Condominium', 1938, 'Bayshore Place Condominium (TE)', '#fcd34d', 'Empreinte V16 1938 extrudee; toit = landmark (TE) 64.1 (a 11 m du bord)'),
    ('Meditteranea Condo', 2166, 'Meditteranea Condo', '#fda4af', 'Empreinte V16 2166 extrudee; toit = landmark 61.0'),
    ('Keystone Park Condo', 2165, 'Keystone Park Condo', '#fda4af', 'Empreinte V16 2165 extrudee; toit = landmark 60.3'),
    ('Seybold Pointe', 2217, 'Seybold Pointe (SE)', '#c4b5fd', 'Empreinte V16 2217 extrudee; toit = coin (SE) 52.7'),
]


def build():
    out = {}
    for name, pid, lmk, color, note in SIMPLE:
        p = ring(pid); z0 = ground(p); zr = float(lm(lmk)[2])
        out.update(entry(name, extrude(p, z0, zr, ring_step=max(4.0, (zr - z0) / 12)), color, note + '; sol %.1f' % z0))
    T = hull(MET1); z0 = ground(T)
    out.update(entry('Met 1 Condominium', extrude(T, z0, 195.3, ring_step=4.5), '#f9a8d4',
                     'Tour = enveloppe convexe des traits V16 (3 bandes, 1448+811+567 m2) dans l ilot 2261 (footprint V16 prime); toit = landmark 195.3; sol %.1f' % z0))
    T = hull(PALACE); z0 = ground(T)
    out.update(entry('The Palace Condominium', extrude(T, z0, 136.3, ring_step=4.5), '#fdba74',
                     'Tour = enveloppe des traits V16 (647+626 m2) dans l ilot 1923; toit = landmark 136.3; sol %.1f' % z0))
    T = hull(np.vstack([ring(3102), ring(3103)])); pod = ring(3100); z0 = ground(pod)
    E = extrude(T, z0, 226.0, ring_step=4.5) + extrude(pod, z0, z0 + 10.0, ring_step=5.0)
    out.update(entry('Asia Brickell Key', E, '#67e8f9',
                     'Fut = enveloppe des polygones V16 3102 + 3103 (592 + 352 m2), toit = coins CC2/CC2B 224-226; podium = ilot V16 3100 a 10 m ESTIME; sol %.1f' % z0))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out'); ap.add_argument('--apply', action='store_true'); ap.add_argument('--only', nargs='*')
    a = ap.parse_args(); meshes = build()
    if a.only: meshes = {k: v for k, v in meshes.items() if k in a.only}
    for k, v in meshes.items(): print('%-32s %5d aretes' % (k, len(v['world_edges'])))
    if a.out: json.dump(meshes, open(a.out, 'w'), indent=1, ensure_ascii=True); print('brouillon ->', a.out)
    if a.apply:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'gtamapdata', 'building_meshes_procedural.json')
        M = json.load(open(path)); M.update(meshes)
        json.dump(M, open(path, 'w'), indent=1, ensure_ascii=True); print('applique ->', path)
