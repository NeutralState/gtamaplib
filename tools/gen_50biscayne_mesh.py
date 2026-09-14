#!/usr/bin/env python3
"""gen_50biscayne_mesh.py — mesh procedural 50 Biscayne Blvd (V2 detaillee). [B50-MESH-V2 2026-09-13]

IRL (Sieger Suarez / Rockwell, 2007): 55 etages, toit 169 m, style MiMo, balcons filants a angles arrondis,
podium (lobby 3 niveaux + « park suites » 4-9 autour du garage), couronne neon orange en vague.
En jeu (Vice City 11 Megamundo a 260 m, Sunrise, Port Vice City B): meme vocabulaire — dalles de balcon a chaque
etage aux angles arrondis, boite technique en retrait sur le toit, canopee ondulee doree qui deborde vers l'ouest.

Geometrie (monde):
  fut       rectangle x -472..-443, y -262..-202 (lame est du polygone V16 2334 elargie, valide dans 11 frames), angles r=4 m
  podium    polygone V16 2334 entier (fut + lame ouest 24 m) — hauteur ESTIMEE (9 niveaux, ~28 m), base cachee dans les frames
  toit      dalle a z 139.4 (NE 138.4 mesure; ratio Sunrise: boite 5.4 m, canopee 2.4 m sous la couronne 147.2 = landmark « 50 Biscayne Blvd »)
  boite     x -470..-445, y -251..-213, z 139.4 -> 144.8
  canopee   x -480..-443 (deborde 8 m a l'ouest, VC11), y -253..-210, z 144.8 -> 147.2, bord ondule (3 vagues par long cote)
  etages    anneaux tous les 3.0 m du haut du podium au toit (~37 niveaux visibles au-dessus du podium)

Usage: PYTHONPATH=. /usr/local/bin/python3 tools/gen_50biscayne_mesh.py [--apply] [--out draft.json] [--podium-z 28]
"""
import argparse, json, math, os, sys
import numpy as np
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS)
from horizon_resect import ground
B = '50 Biscayne Blvd'
X0, X1, Y0, Y1 = -472.0, -443.0, -262.0, -202.0
R_CORNER = 4.0; FLOOR = 3.0
Z_ROOF = 139.4; Z_BOX = 144.8; Z_CROWN = 147.2
BOX = (-470.0, -445.0, -251.0, -213.0)
CANOPY = (-480.0, -443.0, -253.0, -210.0)

def rounded_rect(x0, x1, y0, y1, r, n=5):
    pts = []
    for cx, cy, a0 in ((x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n); pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts

def loop(pts, z):
    return [[[float(p[0]), float(p[1]), float(z)], [float(q[0]), float(q[1]), float(z)]] for p, q in zip(pts, pts[1:] + pts[:1])]

def wavy_loop(x0, x1, y0, y1, zc, amp, waves_long=3, waves_short=1, n=48):
    # perimetre echantillonne avec une ondulation verticale (bord de la canopee doree)
    per = [(x0, y0, x1, y0, waves_short), (x1, y0, x1, y1, waves_long), (x1, y1, x0, y1, waves_short), (x0, y1, x0, y0, waves_long)]
    pts = []
    for ax, ay, bx, by, w in per:
        for k in range(n):
            t = k / n; pts.append((ax + (bx - ax) * t, ay + (by - ay) * t, zc + amp * math.sin(2 * math.pi * w * t)))
    return [[list(map(float, p)), list(map(float, q))] for p, q in zip(pts, pts[1:] + pts[:1])]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--apply', action='store_true'); ap.add_argument('--out'); ap.add_argument('--podium-z', type=float, default=28.0); a = ap.parse_args()
    F = {p['id']: p for p in json.load(open(os.path.join(REPO, 'gtamapdata', 'v16_footprints.json')))['polygons']}
    pod = [tuple(p) for p in F[2334]['ring']]
    zg = float(ground((X0 + X1) / 2, (Y0 + Y1) / 2)); zp = zg + a.podium_z
    E = []
    # podium (V16 entier)
    E += loop(pod, zg) + loop(pod, zp) + loop(pod, zg + 3.0 * 3)   # trait au niveau du lobby 3 etages
    for p in pod: E.append([[p[0], p[1], zg], [p[0], p[1], zp]])
    # fut: anneaux d'etage (dalles de balcon) + verticales aux tangentes des angles arrondis
    rr = rounded_rect(X0, X1, Y0, Y1, R_CORNER)
    z = zp
    while z < Z_ROOF - 0.5: E += loop(rr, z); z += FLOOR
    E += loop(rr, Z_ROOF)
    for (x, y) in [(X0 + R_CORNER, Y0), (X1 - R_CORNER, Y0), (X1, Y0 + R_CORNER), (X1, Y1 - R_CORNER),
                   (X1 - R_CORNER, Y1), (X0 + R_CORNER, Y1), (X0, Y1 - R_CORNER), (X0, Y0 + R_CORNER)]:
        E.append([[x, y, zp], [x, y, Z_ROOF]])
    # boite technique
    bx0, bx1, by0, by1 = BOX; box = [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)]
    E += loop(box, Z_ROOF) + loop(box, Z_BOX)
    for p in box: E.append([[p[0], p[1], Z_ROOF], [p[0], p[1], Z_BOX]])
    # canopee ondulee (dalle 2.4 m, bord superieur en vague, deborde a l'ouest)
    cx0, cx1, cy0, cy1 = CANOPY; can = [(cx0, cy0), (cx1, cy0), (cx1, cy1), (cx0, cy1)]
    E += loop(can, Z_BOX) + wavy_loop(cx0, cx1, cy0, cy1, Z_CROWN - 0.6, 0.6)
    for p in can: E.append([[p[0], p[1], Z_BOX], [p[0], p[1], Z_CROWN - 0.6]])
    # traverses de la canopee vers la boite (support visible sous le debord ouest)
    for yy in (cy0 + 8, (cy0 + cy1) / 2, cy1 - 8): E.append([[cx0, yy, Z_BOX], [bx0, yy, Z_BOX]])
    nfl = int((Z_ROOF - zp) / FLOOR)
    mesh = {'color': '#facc15', 'world_edges': E,
            'note': f'B50-MESH-V2 2026-09-13: fut {X1 - X0:.0f}x{Y1 - Y0:.0f} m angles r{R_CORNER:g} (lame est V16 2334 elargie, valide dans 11 frames), {nfl} dalles de balcon tous les {FLOOR:g} m de {zp:.1f} a {Z_ROOF:g}, boite technique -> {Z_BOX:g}, canopee doree ondulee -> {Z_CROWN:g} (landmark couronne) debordant 8 m a l\'ouest (VC11); podium = polygone V16 entier, hauteur ESTIMEE {a.podium_z:g} m (base jamais visible); IRL 55 etages / 169 m, MiMo, couronne neon orange',
            '_credit': 'empreinte: V16 (GTA VI Community Mapping Project); hauteurs: triangulation gtamaplib (couronne 4 cams 1.2 m, NE 2 cams); proportions toit: Sunrise over Vice City, Vice City 11'}
    print(f'{B}: sol {zg:.1f}, podium -> {zp:.1f}, {nfl} etages, {len(E)} aretes')
    if a.out: json.dump({B: mesh}, open(a.out, 'w'), ensure_ascii=True); print('->', a.out)
    if a.apply:
        mp = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json'); M = json.load(open(mp)); M[B] = mesh
        json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique ->', mp, len(M), 'meshs')

if __name__ == '__main__':
    main()
