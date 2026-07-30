#!/usr/bin/env python3
"""canyon_mesh.py — la paroi du canyon, modele SIMPLE et honnete. [CANYON-3D-V8]

Lecon des versions 1-7 (jetees): en vue unique, tout ce qu'on construit le
long des rayons retombe sur la photo par CONSTRUCTION — la verification en
projection etait tautologique, et la 3D reelle etait un tas de rubans
replies. Ici on ne garde que ce qui a une profondeur CONTRAINTE:

  1. PLANCHER  z = A + B * d_xy, cale sur le profil de route declare
     (--z0 au bas du cadre, --z1 sous le pont). Seule hypothese restante.
  2. PIED      la ligne de sol tracee par Alexandre (ground_left) coupee
     avec ce plancher: intersection rayon x plan, bien conditionnee,
     profondeur exacte par point.
  3. HAUT      hauteur au-dessus du pied, LISSEE fortement le long de la
     paroi (fenetre --smooth). La ligne de crete de l'image ne sert qu'a
     donner l'echelle de hauteur — on ne la matche PAS point par point
     (c'est ce matching qui laissait la profondeur zigzaguer et repliait
     le mur).

Rien d'autre n'est emis: pas de nappes de plateau, pas de cote droit tant
qu'il n'a pas sa ligne de sol. Auto-controle imprime: profondeur, hauteur,
et repliement (le pied doit avancer de facon monotone).

Usage: PYTHONPATH=. python3 tools/canyon_mesh.py [--apply]
       [--z0 30 --z1 55 --face 65 --smooth 25]
"""
import argparse
import json
import math
import os
import sys
import tempfile

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
import common

CAM = 'Mount Kalaga National Park 04 (Mountain Pass) (X)'
MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
MESH_NAME = 'Canyon Wall (Kalaga Pass)'
COLOR = '#fb923c'


def smooth(a, w):
    """Moyenne glissante, bords tenus."""
    if len(a) < 3 or w < 3:
        return np.asarray(a, float)
    k = np.ones(w) / w
    s = np.convolve(np.asarray(a, float), k, mode='same')
    h = w // 2
    s[:h] = np.mean(a[:h + 1])
    s[-h:] = np.mean(a[-(h + 1):])
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--z0', type=float, default=30.0, help='z route, bas du cadre')
    ap.add_argument('--z1', type=float, default=55.0, help='z route, sous le pont')
    ap.add_argument('--face', type=float, default=65.0, help='elevation de la face (deg)')
    ap.add_argument('--smooth', type=int, default=25, help='lissage de la hauteur')
    ap.add_argument('--ribs', type=int, default=8, help='une nervure sur N')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    lines = json.load(open(os.path.join(REPO, 'tools', 'generated', 'canyon_lines.json')))
    cam = common.get_cam(CAM)
    o = np.asarray(cam.xyz, float)

    def ray(x, y):
        d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
        return d / np.linalg.norm(d)

    # ── 1. plancher: z = A + B * d_xy (profil de route declare) ─────────
    rx, ry = lines['road_center']['x'], lines['road_center']['y']
    i_bot, i_top = int(np.argmax(ry)), int(np.argmin(ry))
    r0, r1 = ray(rx[i_bot], ry[i_bot]), ray(rx[i_top], ry[i_top])
    d0 = (args.z0 - o[2]) / r0[2] * float(np.hypot(r0[0], r0[1]))
    d1 = (args.z1 - o[2]) / r1[2] * float(np.hypot(r1[0], r1[1]))
    B = (args.z1 - args.z0) / (d1 - d0)
    A = args.z0 - B * d0
    road = []
    for x, y in zip(rx, ry):
        r = ray(x, y)
        t = (A - o[2]) / (r[2] - B * float(np.hypot(r[0], r[1])))
        if t > 0:
            road.append(o + t * r)
    road_xy = np.array(road)[:, :2]
    print(f'plancher: z = {A:.1f} + {B:.4f} * d_xy  (route {args.z0} -> {args.z1} m, '
          f'pente {100 * B:.1f}%)')

    # ── 2. pied: la ligne de sol d'Alexandre x le plancher ──────────────
    gl = lines.get('ground_left')
    if not gl:
        print('pas de ground_left: rien a construire.')
        return
    feet = []
    for gx, gy in zip(gl['x'], gl['y']):
        r = ray(gx, gy)
        t = (A - o[2]) / (r[2] - B * float(np.hypot(r[0], r[1])))
        if t > 0:
            feet.append(o + t * r)
    feet = np.array(feet)
    dfeet = np.hypot(feet[:, 0] - o[0], feet[:, 1] - o[1])
    print(f'pied: {len(feet)} points, profondeur {dfeet.min():.0f} -> {dfeet.max():.0f} m')

    # ── 3. haut: hauteur LISSEE au-dessus du pied ───────────────────────
    # la ligne de crete donne l'ECHELLE de hauteur (pas un matching point
    # par point): pour chaque pied on mesure la montee qui atteindrait la
    # crete dans l'image, puis on lisse fortement.
    rim2d = []
    for nm in ('rim_left', 'rim_left_pinnacle', 'rim_left_top'):
        if nm in lines:
            rim2d += list(zip(lines[nm]['x'], lines[nm]['y']))
    top_by_col = {}
    for xx, yy in rim2d:                       # enveloppe superieure
        k = int(round(xx / 8.0))
        if k not in top_by_col or yy < top_by_col[k][1]:
            top_by_col[k] = (xx, yy)
    env = sorted(top_by_col.values())
    ex = np.array([p[0] for p in env])
    ey = np.array([p[1] for p in env])

    FACE = math.radians(args.face)
    # direction horizontale de la face: a l'oppose de la route, lissee
    nh = feet[:, :2] - road_xy[np.argmin(
        np.linalg.norm(road_xy[None, :, :] - feet[:, None, :2], axis=2), axis=1)]
    nh /= (np.linalg.norm(nh, axis=1)[:, None] + 1e-9)
    nh = np.stack([smooth(nh[:, 0], args.smooth), smooth(nh[:, 1], args.smooth)], axis=1)
    nh /= (np.linalg.norm(nh, axis=1)[:, None] + 1e-9)

    raw_u = np.zeros(len(feet))
    for i, F in enumerate(feet):
        u_hit = np.nan
        for u in np.arange(4, 260, 4):
            Q = np.array([F[0] + u * nh[i, 0] * math.cos(FACE),
                          F[1] + u * nh[i, 1] * math.cos(FACE),
                          F[2] + u * math.sin(FACE)])
            pr = cam.get_pixel([float(v) for v in Q])
            if pr is None:
                break
            if ex[0] <= pr[0] <= ex[-1] and pr[1] <= float(np.interp(pr[0], ex, ey)):
                u_hit = u
                break
        raw_u[i] = u_hit
    ok = ~np.isnan(raw_u)
    if ok.sum() < 5:
        print('pas assez de mesures de hauteur.')
        return
    u = np.interp(np.arange(len(feet)), np.where(ok)[0], raw_u[ok])
    u = smooth(u, args.smooth)                 # LISSAGE FORT: pas de zigzag
    tops = np.stack([feet[:, 0] + u * nh[:, 0] * math.cos(FACE),
                     feet[:, 1] + u * nh[:, 1] * math.cos(FACE),
                     feet[:, 2] + u * math.sin(FACE)], axis=1)
    print(f'haut: montee {u.min():.0f} -> {u.max():.0f} m le long de la face, '
          f'z {tops[:, 2].min():.0f} -> {tops[:, 2].max():.0f} m '
          f'({int(ok.sum())}/{len(feet)} mesures, reste interpole)')

    # ── auto-controle: repliement du pied et du haut ────────────────────
    for nom, P in (('pied', feet), ('haut', tops)):
        seg = np.diff(P[:, :2], axis=0)
        n = np.linalg.norm(seg, axis=1)
        good = n > 1e-6
        cs = np.sum(seg[good][:-1] * seg[good][1:], axis=1) / (
            n[good][:-1] * n[good][1:] + 1e-9)
        back = int((cs < 0).sum())
        print(f'  {nom}: {back} retournements sur {len(cs)} segments '
              f'({100 * back / max(1, len(cs)):.1f}%)')

    # ── mesh: pied + haut + nervures ────────────────────────────────────
    edges = []
    for i in range(len(feet) - 1):
        edges.append([list(map(float, feet[i])), list(map(float, feet[i + 1]))])
        edges.append([list(map(float, tops[i])), list(map(float, tops[i + 1]))])
    for i in range(0, len(feet), args.ribs):
        edges.append([list(map(float, feet[i])), list(map(float, tops[i]))])
    out = {MESH_NAME: {'color': COLOR, 'world_edges': edges}}
    print(f'{MESH_NAME}: {len(edges)} aretes')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    for k in [k for k in mesh if '(Kalaga Pass)' in k]:
        mesh.pop(k)
    mesh.update(out)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'APPLIED: {MESH_NAME}')


if __name__ == '__main__':
    main()
