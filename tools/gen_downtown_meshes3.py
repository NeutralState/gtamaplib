#!/usr/bin/env python3
"""Lot Downtown n. 3 (2026-09-22): polygones V16 SANS landmark de toit, hauteur LUE (+-15 m) en projetant l'empreinte
a plusieurs altitudes dans Port Vice City (A) (est) et Sunrise (ouest), lectures croisees (scratchpad hgt_*.jpg).
A affiner des qu'un coin de toit est triangule ou Alt-clique. Noms = position (pas d'identification IRL sure).
"""
import json, sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_downtown_meshes import ring, ground, extrude, entry

ITEMS = [  # (nom, polygone, hauteur lue, couleur, lecture)
    ('Tower 2253 (SE 3rd Ave)', 2253, 190.0, '#94a3b8', 'Port VC A: tour eclairee sous le prisme, toit ~205; Sunrise: silhouette ~180'),
    ('Tower 2262 (LED)', 2262, 200.0, '#94a3b8', 'Port VC A: la tour a facade LED sous le prisme, toit ~200; Sunrise ~180 (2254 devant)'),
    ('Tower 2254 (W of Met 1)', 2254, 185.0, '#94a3b8', 'Sunrise (devant): silhouette ~185; Port VC A masque par 2262'),
    ('Tower 2436 (W of Vizcayne)', 2436, 155.0, '#94a3b8', 'Sunrise (devant): toit ~150; Vice City 10 ~170; Port VC A masque par Vizcayne'),
]


def build():
    out = {}
    for name, pid, h, color, note in ITEMS:
        p = ring(pid); z0 = ground(p)
        out.update(entry(name, extrude(p, z0, h, ring_step=max(4.0, (h - z0) / 12)), color,
                         'Empreinte V16 %d extrudee; hauteur %.0f m LUE (+-15 m) par projection a plusieurs altitudes: %s; sol %.1f; nom provisoire (pas de landmark)' % (pid, h, note, z0)))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out'); ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(); meshes = build()
    for k, v in meshes.items(): print('%-32s %5d aretes' % (k, len(v['world_edges'])))
    if a.out: json.dump(meshes, open(a.out, 'w'), indent=1, ensure_ascii=True); print('brouillon ->', a.out)
    if a.apply:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'gtamapdata', 'building_meshes_procedural.json')
        M = json.load(open(path)); M.update(meshes); json.dump(M, open(path, 'w'), indent=1, ensure_ascii=True); print('applique ->', path)
