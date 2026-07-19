#!/usr/bin/env python3
"""gen_vizcayne_mesh.py — meshes V6 des twins Vizcayne (topologie reelle).

Credit (CC-BY-4.0): "The Vizcayne, Miami" par aitortilla01
https://sketchfab.com/3d-models/the-vizcayne-miami-2f326604f2c34a09b3dcf3d6f8e3fd4b

Topologie extraite du modele (tools/data/vizcayne_loops.json: boucles de
contour par slicing triangle-plan — corps 32 sommets avec encoches, retrait
a 122m, croix de couronne 24 sommets), echelles/angles cales sur NOS coins
triangules (le jeu = verite). 90 deg exact entre les twins. Relancer apres
tout mouvement des coins (fit_mesh, edge_ba...).
"""
import json, math, os
import numpy as np
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

loops = json.load(open(os.path.join(REPO, 'tools', 'data', 'vizcayne_loops.json')))
lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
gNW = np.array(lms['Vizcayne South Condominium (NW)']['xyz'][:2])
gNE = np.array(lms['Vizcayne South Condominium (NE)']['xyz'][:2])
gnNE = np.array(lms['Vizcayne North Condominium (NE)']['xyz'][:2])
gnSE = np.array(lms['Vizcayne North Condominium (SE)']['xyz'][:2])
zc = [lms[f'Vizcayne North Condominium ({c})']['xyz'][2] for c in ['NE','NW','SE']]
Z_TOP = sum(zc) / len(zc)
ZG = 5.0
L_MODEL = 44.9
SZ = (Z_TOP - ZG) / 152.5

thS = math.atan2((gNE-gNW)[1], (gNE-gNW)[0])
thN = math.atan2((gnSE-gnNE)[1], (gnSE-gnNE)[0]) + math.pi/2
th = math.atan2((math.sin(thS)+math.sin(thN))/2, (math.cos(thS)+math.cos(thN))/2)
s = float((np.linalg.norm(gNE-gNW) + np.linalg.norm(gnSE-gnNE)) / (2 * L_MODEL))

def rotm(u):
    return np.array([[math.cos(u), -math.sin(u)], [math.sin(u), math.cos(u)]])

W_MODEL = 24.8
vS = np.array([-math.sin(th), math.cos(th)])
midS = (gNW + gNE) / 2
ctrS = midS - vS * (W_MODEL*s/2) if vS[1] > 0 else midS + vS * (W_MODEL*s/2)
uN = rotm(th - math.pi/2) @ np.array([1.0, 0.0])
vN = np.array([-uN[1], uN[0]])
midN = (gnNE + gnSE) / 2
ctrN = midN - vN * (W_MODEL*s/2) if vN[0] > 0 else midN + vN * (W_MODEL*s/2)

# tours du modele: V (ctr 33.6,-20.7) = North jeu; H (ctr -20.8,33.6) = South
FITS = [('Vizcayne North Condominium', np.array([33.6, -20.7]), ctrN, th - math.pi/2),
        ('Vizcayne South Condominium', np.array([-20.8, 33.6]), ctrS, th)]
# rotation modele->jeu par tour: la tour H du modele est E-O; on l'amene a
# l'angle du jeu. Pour V (N-S modele), meme delta d'angle global.
CREDIT = (f'V6 topologie reelle (boucles 32/17/24 sommets, retrait 122m, croix 144m->sommet), '
          f'90 deg exact, echelle {s:.3f}, s_z {SZ:.3f}; base: "The Vizcayne, Miami" par aitortilla01 '
          '(sketchfab CC-BY-4.0) [gen_vizcayne_mesh.py V6]')

def loop_at(zkey, ctr_m):
    cands = [k for k in loops[zkey] if np.linalg.norm(np.array(k['ctr']) - ctr_m) < 15]
    return max(cands, key=lambda k: len(k['poly']))['poly'] if cands else None

bp_path = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
bp = json.load(open(bp_path))
for name, ctr_m, ctr_g, ang in FITS:
    # delta de rotation: axe long modele (x pour H, y pour V) vers l'angle jeu
    base_ang = 0.0 if ctr_m[1] > 0 else math.pi/2   # H: axe x; V: axe y (90)
    rot = ang - base_ang if ctr_m[1] > 0 else (ang + math.pi/2 - base_ang)
    # simplification: on tourne les boucles autour du centre modele de `rot`
    # H: rot = th; V: rot = th (meme rotation globale du bloc)
    rot = th if ctr_m[1] > 0 else th
    R = rotm(rot)
    def tf(p, z_m):
        g = s * (R @ (np.array(p) - ctr_m)) + ctr_g
        return [round(float(g[0]), 2), round(float(g[1]), 2), round(ZG + SZ * z_m, 2)]
    body = loop_at('3000', ctr_m); upper = loop_at('12200', ctr_m); crown = loop_at('14400', ctr_m)
    z_b1, z_u1, z_top = 122.0, 144.0, (Z_TOP - ZG) / SZ
    edges = []
    def ring(poly, z_m):
        r = [tf(p, z_m) for p in poly]
        return [[a, b] for a, b in zip(r, r[1:] + [r[0]])]
    def verts(poly, z0, z1):
        return [[tf(p, z0), tf(p, z1)] for p in poly]
    for z in [0, 30, 60, 90, z_b1]:
        edges += ring(body, z)
    edges += verts(body, 0, z_b1)
    if upper:
        edges += ring(upper, z_b1) + ring(upper, z_u1) + verts(upper, z_b1, z_u1)
    if crown:
        edges += ring(crown, z_u1) + ring(crown, z_top) + verts(crown, z_u1, z_top)
    bp[name] = {'color': '#4ade80', 'source': CREDIT, 'world_edges': edges}
    print(f'{name}: {len(edges)} aretes')
tmp = bp_path + '.tmp'
json.dump(bp, open(tmp, 'w'), indent=1, ensure_ascii=True)
os.replace(tmp, bp_path)
print(f'V6 ecrits (echelle {s:.3f}, rot {math.degrees(th):.2f})')
