#!/usr/bin/env python3
"""massing_colors.py — couleur REELLE des batiments du remplissage urbain (emprises V16), lue sur les frames. [MASSING-COLOR-V1 2026-10-05]

Meme mesure que facade_colors.py (projection peinte du plus loin au plus proche, pixels « bati » de SegFormer, balance
monde gris + exposition), appliquee aux emprises extrudees de tools/v16_massing.py; les volumes modelises (mesh_solids)
participent a l'ordre de peinture -> une tour modelisee devant masque correctement l'emprise derriere. Seuil: >= 150 px
par cam (petits batiments) et >= 2 cams. Les HAUTEURS du remplissage restent ESTIMEES: seule la couleur est mesuree.
Sortie (couche visuelle, ignoree par git): tools/threejs/_v16_massing_colors.json {"x,y" (centroide arrondi au m): {rgb, n_cams}}
Usage: python3 tools/massing_colors.py
"""
import json, os, sys
import numpy as np
THIS = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, THIS); sys.path.insert(0, os.path.dirname(THIS))
import mesh_solids as MS
import facade_colors as FC

MASS = os.path.join(THIS, 'threejs', '_v16_massing.json')
OUT = os.path.join(THIS, 'threejs', '_v16_massing_colors.json')


def key(o):
    c = np.mean(np.array(o, float), axis=0); return '%d,%d' % (round(c[0]), round(c[1]))


def main():
    S = MS.build(); M = json.load(open(MASS)); names = {}
    for i, m in enumerate(M):
        n = 'V16 building #%d' % (i + 1); names[n] = key(m['o'])
        S[n] = {'zmin': m['z'], 'zmax': m['z'] + m['h'], 'layers': [{'z0': m['z'], 'z1': m['z'] + m['h'], 'polys': [{'outer': m['o'], 'holes': []}]}]}
    out = FC.run(S=S, min_px=150)
    res = {names[n]: {'rgb': v['rgb'], 'n_cams': v['n_cams']} for n, v in out.items() if n in names and v['n_cams'] >= 2}
    json.dump(res, open(OUT, 'w'), separators=(',', ':'))
    print('%d emprises colorees (>= 2 cams) sur %d -> %s' % (len(res), len(M), OUT))


if __name__ == '__main__':
    main()
