#!/usr/bin/env python3
"""canyon_mesh.py — le canyon de Mountain Pass en 3D. [CANYON-3D-V1]

Doctrine colline: les DONNEES sont les lignes 2D validees d'Alexandre
(canyon_lines.json, traces pixel-exact) + la pose resolue de la cam
(RESECTION-V1); les HYPOTHESES sont des parametres declares:

  --z0     z de la route au bas du cadre (defaut 30)
  --z1     z de la route sous le pont    (defaut 55 — la route monte vers
           le col en s'eloignant)
  --clear  clairance route -> tablier    (defaut 6.5)
  --width  demi-largeur du canyon au sol (defaut 14: bord de route)

Geometrie:
  * ROUTE: chaque pixel de road_center est un rayon; profil z lineaire en
    distance horizontale cale sur (z0 au 1er rayon du bas, z1 au rayon
    sous le pont) -> intersection fermee par rayon.
  * PONT: tablier horizontal a z1+clear; extremites = rayons du deck x ce
    plan; piles verticales jusqu'a la route.
  * PAROIS: hypothese murs VERTICAUX — chaque point de rim est le point de
    son rayon qui minimise la distance horizontale a la ligne de bord de
    route (offset +-width). Nervures bord->rim.

Sanity imprimees: portee du pont, hauteurs de parois, pente de la route.
Usage: PYTHONPATH=. python3 tools/canyon_mesh.py [--apply] [params]
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


def rays_of(cam, xs, ys):
    out = []
    for x, y in zip(xs, ys):
        d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
        out.append(d / np.linalg.norm(d))
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--z0', type=float, default=30.0)
    ap.add_argument('--z1', type=float, default=55.0)
    ap.add_argument('--clear', type=float, default=6.5)
    ap.add_argument('--width', type=float, default=14.0)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    lines = json.load(open(os.path.join(REPO, 'tools', 'generated', 'canyon_lines.json')))
    cam = common.get_cam(CAM)
    o = np.asarray(cam.xyz, float)

    # ── route: profil z lineaire en distance horizontale ────────────────
    rx, ry = lines['road_center']['x'], lines['road_center']['y']
    rr = rays_of(cam, rx, ry)
    # rayon du bas du cadre = plus grand y ; rayon sous le pont = plus petit y
    i_bot = int(np.argmax(ry))
    i_top = int(np.argmin(ry))
    def dxy_at_z(ray, z):
        t = (z - o[2]) / ray[2]
        return t * float(np.hypot(ray[0], ray[1])), t
    d0, _ = dxy_at_z(rr[i_bot], args.z0)
    d1, _ = dxy_at_z(rr[i_top], args.z1)
    B = (args.z1 - args.z0) / (d1 - d0)
    A = args.z0 - B * d0
    road = []
    for ray in rr:
        hx = float(np.hypot(ray[0], ray[1]))
        t = (A - o[2]) / (ray[2] - B * hx)
        if t <= 0:
            continue
        road.append(o + t * ray)
    road = np.array(road)
    order = np.argsort(-np.array(ry)[:len(road)])   # du bas (proche) au pont
    grade = 100 * B
    print(f'route: {len(road)} pts, d {d0:.0f} -> {d1:.0f} m, z {args.z0} -> {args.z1}, '
          f'pente {grade:.1f}%')

    # ── pont: tablier a la PROFONDEUR de la route (la clairance est une
    #    SORTIE, pas une hypothese — c'est un pont de gorge) ─────────────
    bx, by = lines['bridge_deck']['x'], lines['bridge_deck']['y']
    br = rays_of(cam, bx, by)
    road_under = road[int(np.argmin(np.hypot(*(road[:, :2] - o[:2]).T) * 0 + np.array(ry)[:len(road)]))]
    vhat = np.asarray(cam.get_pixel_direction((cam.w / 2, cam.h / 2)), float)
    vhat /= np.linalg.norm(vhat)
    depth_under = float(np.dot(road_under - o, vhat))
    deck = []
    for ray in br:
        t = depth_under / float(np.dot(ray, vhat))
        deck.append(o + t * ray)
    deck = np.array(deck)
    span = float(np.linalg.norm(deck[-1] - deck[0]))
    z_deck = float(np.median(deck[:, 2]))
    print(f'pont: profondeur {depth_under:.0f} m, tablier z {z_deck:.1f} '
          f'(clairance {z_deck - args.z1:.0f} m au-dessus de la route), portee {span:.0f} m')

    # ── parois: murs verticaux au-dessus du bord de route ───────────────
    road_xy = road[:, :2]
    t_road = np.gradient(road_xy, axis=0)
    t_road /= (np.linalg.norm(t_road, axis=1)[:, None] + 1e-9)
    n_road = np.stack([-t_road[:, 1], t_road[:, 0]], axis=1)

    walls = {}
    rim_names = ['rim_right', 'rim_left', 'rim_left_pinnacle', 'rim_left_top']
    # terrain_near_right exclu: versant du PREMIER PLAN (la colline de la
    # cam), aucune route sous lui dans l'image -> l'echafaudage par colonne
    # le placerait sous terre. Il attendra son propre ancrage.
    terr_names = [k for k in lines if (k.startswith('terrain_') or k == 'ridge_back')
                  and k != 'terrain_near_right']
    for name in rim_names + terr_names:
        if name not in lines:
            continue
        wx, wy = lines[name]['x'], lines[name]['y']
        wr = rays_of(cam, wx, wy)
        # correspondance par COLONNE d'image: le haut du mur est au-dessus
        # du point de route qui passe sous lui dans la frame
        rx_arr = np.array(rx, float)
        road_depth = np.dot(road - o[None, :], vhat)
        pts = []
        for (x, ray) in zip(wx, wr):
            j = int(np.argmin(np.abs(rx_arr[:len(road)] - float(x))))
            t = float(road_depth[j]) / float(np.dot(ray, vhat))
            if t <= 0:
                continue
            pts.append(o + t * ray)
        walls[name] = np.array(pts)
        rel = walls[name][:, 2] - A - B * np.hypot(*(walls[name][:, :2] - o[:2]).T)
        print(f'{name:18s}: {len(pts)} pts, z {walls[name][:,2].min():.0f}-'
              f'{walls[name][:,2].max():.0f}, hauteur/route mediane {np.median(rel):.0f} m')

    # ── meshs (route et pont RETIRES a la demande d'Alexandre — la route
    #    reste l'echafaudage de profondeur interne) ─────────────────────
    out = {}
    def poly_edges(pts, step=1):
        return [[list(map(float, pts[i])), list(map(float, pts[i + step]))]
                for i in range(0, len(pts) - step, step)]

    e_w = []
    for name in rim_names:
        if name not in walls:
            continue
        pts = walls[name]
        e_w += poly_edges(pts)
        for i in range(0, len(pts), 6):             # nervures vers la route
            base = A + B * float(np.hypot(*(pts[i, :2] - o[:2])))
            e_w.append([list(map(float, pts[i])), [float(pts[i][0]), float(pts[i][1]), float(base)]])
    out['Canyon Walls (Kalaga Pass)'] = {'color': '#fb923c', 'world_edges': e_w}

    # terrain au-dessus des rims (enveloppes des hachures) + ridge_back:
    # polylines 3D + nervures vers le rim le plus proche
    # association explicite terrain -> rim (le 'plus proche' traversait le
    # canyon); ridge_back et la bench restent des polylines libres
    ASSOC = {'terrain_left': 'rim_left', 'terrain_mid': 'rim_left_top',
             'terrain_right_top': 'rim_right'}
    e_t = []
    for name in terr_names:
        if name not in walls:
            continue
        pts = walls[name]
        e_t += poly_edges(pts)
        rim_n = ASSOC.get(name)
        if rim_n and rim_n in walls:
            rim = walls[rim_n]
            for i in range(0, len(pts), 4):
                j = int(np.argmin(np.linalg.norm(rim - pts[i], axis=1)))
                if np.linalg.norm(rim[j] - pts[i]) < 130:
                    e_t.append([list(map(float, pts[i])), list(map(float, rim[j]))])
    out['Canyon Terrain (Kalaga Pass)'] = {'color': '#4ade80', 'world_edges': e_t}

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
    print(f'\nAPPLIED: {list(out)}')


if __name__ == '__main__':
    main()
