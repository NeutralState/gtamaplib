#!/usr/bin/env python3
"""v16_massing.py — remplissage urbain 3D: toutes les emprises de batiments de la V16 extrudees. [MASSING-V1 2026-10-05]

Couche VISUELLE de l'onglet 3D (pas un produit mesh: hauteurs ESTIMEES, rien n'est ecrit dans
building_meshes_procedural.json). Emprises = gtamapdata/v16_footprints.json, categories building* (4 couleurs V16);
les emprises deja couvertes par un mesh modelise (volumes de tools/mesh_solids.py) sont ignorees.
Hauteur estimee (hash deterministe par emprise): selon la surface et le quartier
  - coeur Downtown/Brickell: 400-3000 m2 -> 18-70 m, > 3000 m2 -> 12-30 m
  - Vice Beach: 300-3000 m2 -> 10-34 m
  - ailleurs: < 150 m2 maisons 4.5-7 m, 150-700 m2 6-12 m, 700-3000 m2 8-18 m, > 3000 m2 entrepots/centres 7-13 m
Sol = heightmap (v16_resect.ground). Sortie servie sans redemarrage: tools/threejs/_v16_massing.json (ignore par git).
Usage: python3 tools/v16_massing.py
"""
import json, os, sys, math
import numpy as np
import cv2

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import v16_resect as RR

FOOT = os.path.join(REPO, 'gtamapdata', 'v16_footprints.json')
SOLIDS = os.path.join(THIS, 'threejs', '_mesh_solids.json')
OUT = os.path.join(THIS, 'threejs', '_v16_massing.json')


def hsh(i, k):
    x = math.sin(i * 12.9898 + k * 78.233) * 43758.5453
    return x - math.floor(x)


def inpoly(x, y, O):
    c = False; n = len(O)
    for i in range(n):
        x1, y1 = O[i]; x2, y2 = O[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def main():
    F = json.load(open(FOOT))['polygons']; S = json.load(open(SOLIDS))
    solid_polys = [p['outer'] for so in S.values() for L in so['layers'][:1] for p in L['polys']]
    sbb = [(min(q[0] for q in O), min(q[1] for q in O), max(q[0] for q in O), max(q[1] for q in O)) for O in solid_polys]
    out = []
    for i, p in enumerate(F):
        if not str(p.get('cat', '')).startswith('building'): continue
        R = np.array(p['ring'], float)
        if len(R) < 3 or p['area'] < 12 or p['area'] > 60000: continue
        R = cv2.approxPolyDP(R.astype(np.float32).reshape(-1, 1, 2), 0.6, True).reshape(-1, 2)
        if len(R) < 3: continue
        cx, cy = R.mean(0)
        skip = False
        for O, b in zip(solid_polys, sbb):                      # deja modelise
            if b[0] - 2 <= cx <= b[2] + 2 and b[1] - 2 <= cy <= b[3] + 2 and inpoly(cx, cy, O): skip = True; break
        if skip: continue
        a, r1, r2 = p['area'], hsh(i, 1), hsh(i, 2)
        core = -1250 < cx < 350 and -1350 < cy < 1250
        beach = 1250 < cx < 2700 and -200 < cy < 4300
        if core and a > 400: h = (18 + 52 * r1 ** 1.6) if a < 3000 else 12 + 18 * r1
        elif beach and a > 300 and a < 3000: h = 10 + 24 * r1 ** 1.4
        elif a < 150: h = 4.5 + 2.5 * r1
        elif a < 700: h = 6 + 6 * r1
        elif a < 3000: h = 8 + 10 * r1
        else: h = 7 + 6 * r1
        try: z = max(0.0, float(RR.ground(cx, cy)))
        except Exception: z = 0.0
        out.append({'o': [[round(float(x), 1), round(float(y), 1)] for x, y in R], 'z': round(z, 2), 'h': round(h, 1), 'k': int(r2 * 1000)})
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print('%d emprises extrudees -> %s (%.0f ko)' % (len(out), OUT, os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
