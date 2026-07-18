#!/usr/bin/env python3
"""gen_vizcayne_mesh.py — meshes des twins Vizcayne depuis le modele Sketchfab.

Credit (CC-BY-4.0): "The Vizcayne, Miami" par aitortilla01
https://sketchfab.com/3d-models/the-vizcayne-miami-2f326604f2c34a09b3dcf3d6f8e3fd4b

Le jeu = verite (echelles calees sur nos coins triangules, exageration
verticale GTA s_z resolue par le z des toits), le modele = topologie
(corps chanfreine a encoches, couronne cruciforme). Les twins du jeu sont
perpendiculaires comme les vrais. Modele attendu dans
~/Downloads/the_vizcayne_miami/ (scene.bin). Relancer apres raffinement
des coins.
"""
import json, math, os, sys
import numpy as np
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.expanduser('~/Downloads/the_vizcayne_miami')

buf = open(f'{D}/scene.bin', 'rb').read()
P = np.frombuffer(buf, dtype='<f4', count=15714*3, offset=608664).reshape(-1, 3)
I = np.frombuffer(buf, dtype='<u4', count=26454, offset=0).reshape(-1, 3)
T = P[I]

def slice_segs3(z):
    out = []
    for tri in T:
        zs = tri[:, 2]
        if zs.min() > z or zs.max() < z: continue
        pts = [tri[a] + (z - tri[a,2]) / (tri[b,2] - tri[a,2]) * (tri[b] - tri[a])
               for a, b in [(0,1),(1,2),(2,0)] if (tri[a,2]-z)*(tri[b,2]-z) < 0]
        if len(pts) == 2: out.append((pts[0], pts[1]))
    return out

lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
def gxy(name):
    return np.array(lms[name]['xyz'][:2])

FITS = [dict(ctr=np.array([-21.1, 33.3]),
             mA=np.array([-38.32, 44.45]), mB=np.array([-3.12, 44.45]),
             gA=gxy('Vizcayne South Condominium (NW)'), gB=gxy('Vizcayne South Condominium (NE)'),
             name='Vizcayne South Condominium'),
        dict(ctr=np.array([33.2, -21.0]),
             mA=np.array([44.40, -3.07]), mB=np.array([44.40, -38.27]),
             gA=gxy('Vizcayne North Condominium (NE)'), gB=gxy('Vizcayne North Condominium (SE)'),
             name='Vizcayne North Condominium')]
Z_ROOF_MODEL, Z_GROUND = 149.5, 5.0
zc = [lms[f'Vizcayne North Condominium ({c})']['xyz'][2] for c in ['NE','NW','SE']]
Z_CORNERS_GAME = sum(zc) / len(zc)
s_z = (Z_CORNERS_GAME - Z_GROUND) / Z_ROOF_MODEL

bp_path = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
bp = json.load(open(bp_path))
CREDIT = ('base: "The Vizcayne, Miami" par aitortilla01 (sketchfab CC-BY-4.0) — topologie modele, '
          f'echelles calees sur nos coins (s_z={s_z:.2f} exageration verticale GTA) [gen_vizcayne_mesh.py]')
for f in FITS:
    vm, vg = f['mB'] - f['mA'], f['gB'] - f['gA']
    s = float(np.linalg.norm(vg) / np.linalg.norm(vm))
    rot = math.atan2(vg[1], vg[0]) - math.atan2(vm[1], vm[0])
    R = np.array([[math.cos(rot), -math.sin(rot)], [math.sin(rot), math.cos(rot)]])
    t = f['gA'] - s * (R @ f['mA'])
    def tf(p3, R=R, s=s, t=t):
        pm = np.array([float(p3[0]), float(p3[1])]) / 100.0
        g = s * (R @ pm) + t
        return [round(float(g[0]), 2), round(float(g[1]), 2),
                round(float(Z_GROUND + s_z * float(p3[2]) / 100.0), 2)]
    ctr_cm = f['ctr'] * 100
    edges = []
    for zl in [16, 40, 70, 100, 130, 148.5, 151.5]:
        for a, b in slice_segs3(zl * 100):
            pa2 = np.array([float(a[0]), float(a[1])])
            if np.linalg.norm(pa2 - ctr_cm) > 4000: continue
            if np.linalg.norm(pa2 - np.array([float(b[0]), float(b[1])])) < 80: continue
            edges.append([tf(a), tf(b)])
    seen = set()
    for tri in T:
        for a, b in [(0,1),(1,2),(2,0)]:
            pa, pb = tri[a], tri[b]
            if abs(float(pa[2]) - float(pb[2])) < 800: continue
            if np.linalg.norm(pa[:2] - ctr_cm) > 4000: continue
            if pa[2] < 1500 and pb[2] < 1500: continue
            key = tuple(round(float(v)) for v in list(pa) + list(pb))
            if key in seen or key[3:] + key[:3] in seen: continue
            seen.add(key)
            edges.append([tf(pa), tf(pb)])
    bp[f['name']] = {'color': '#60a5fa', 'source': CREDIT, 'world_edges': edges}
    print(f"{f['name']}: {len(edges)} aretes, s_xy={s:.3f}, rot={math.degrees(rot):.2f} deg")
# ecriture ATOMIQUE (lecon: un crash mi-dump corrompt le fichier)
tmp = bp_path + '.tmp'
json.dump(bp, open(tmp, 'w'), indent=1, ensure_ascii=True)
os.replace(tmp, bp_path)
bm_path = os.path.join(REPO, 'gtamapdata', 'building_meshes.json')
bm = json.load(open(bm_path))
for f in FITS:
    bm.setdefault(f['name'], {'color': '#60a5fa', 'source': CREDIT})
json.dump(bm, open(bm_path + '.tmp', 'w'), indent=2, ensure_ascii=True)
os.replace(bm_path + '.tmp', bm_path)
print(f'ecrits (s_z={s_z:.3f})')
