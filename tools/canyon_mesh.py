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
from PIL import Image
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
    ap.add_argument('--slope-up', type=float, default=20.0,
                    help='pente max du terrain derriere le rim (deg)')
    ap.add_argument('--bench-slope', type=float, default=12.0,
                    help='pente du flanc doux du ridge droit (deg, descend vers la route)')
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

    # ── COTE GAUCHE d'abord (doctrine Alexandre): derriere le rim, le
    #    terrain S'ELOIGNE en montant doucement (--slope-up, defaut 20 deg)
    #    — surface balayee: generatrices depuis le rim, direction opposee a
    #    la route, etendues jusqu'a l'enveloppe hachuree dans l'IMAGE ────
    e_t = []
    up = math.radians(args.slope_up)

    # luminance de la frame: la surface visible s'arrete ou commence le
    # CIEL / fond clair (on ne depasse pas les arbres) et au rebord exact
    frame_L = np.asarray(Image.open(os.path.join(
        REPO, 'frames', f'{CAM}.png')).convert('L'), np.float32)
    fh, fw = frame_L.shape
    def lum(px, py):
        x0, x1 = max(0, int(px) - 3), min(fw, int(px) + 4)
        y0, y1 = max(0, int(py) - 3), min(fh, int(py) + 4)
        return float(frame_L[y0:y1, x0:x1].mean())
    SKY = 178.0

    def sweep(rim, env, stop_at_env, u_max, dens=2):
        """Generatrices a --slope-up depuis le rim, a l'oppose de la route.
        Terminaison: rebord EXACT du cadre (bissection) ou ligne des arbres
        (la projection atteint une zone claire = ciel/fond) ou enveloppe."""
        env_y = (lambda x: float(np.interp(x, env['x'], env['y']))) if env else None
        def point(R, nh, u):
            return np.array([R[0] + u * nh[0] * math.cos(up),
                             R[1] + u * nh[1] * math.cos(up),
                             R[2] + u * math.sin(up)])
        def ok(R, nh, u):
            pr = cam.get_pixel([float(v) for v in point(R, nh, u)])
            if pr is None or pr[0] < 1 or pr[0] > cam.w - 1 or pr[1] < 1:
                return False
            if lum(pr[0], pr[1]) > SKY:
                return False               # on ne depasse pas les arbres
            if stop_at_env and env_y is not None and env['x'][0] <= pr[0] <= env['x'][-1] \
                    and pr[1] <= env_y(pr[0]):
                return False
            return True
        gp = []
        for i in range(0, len(rim), dens):
            R = rim[i]
            j = int(np.argmin(np.linalg.norm(road_xy - R[:2], axis=1)))
            nh = R[:2] - road_xy[j]
            nh /= (np.linalg.norm(nh) + 1e-9)
            u_ok = None
            for u in np.arange(6, u_max, 6):
                if ok(R, nh, u):
                    u_ok = u
                else:
                    if u_ok is None:
                        break
                    lo, hi = u_ok, u
                    for _ in range(12):    # bissection: touche le rebord
                        mid = 0.5 * (lo + hi)
                        if ok(R, nh, mid):
                            lo = mid
                        else:
                            hi = mid
                    u_ok = lo
                    break
            if u_ok is not None and u_ok > 8:
                gp.append((R, point(R, nh, u_ok)))
        return gp

    def emit(gp):
        for R, Q in gp:
            e_t.append([list(map(float, R)), list(map(float, Q))])
        for k in range(len(gp) - 1):
            e_t.append([list(map(float, gp[k][1])), list(map(float, gp[k + 1][1]))])
        for f in (0.33, 0.66):
            for k in range(len(gp) - 1):
                a = gp[k][0] + f * (gp[k][1] - gp[k][0])
                b = gp[k + 1][0] + f * (gp[k + 1][1] - gp[k + 1][0])
                e_t.append([list(map(float, a)), list(map(float, b))])

    if 'rim_left' in walls:
        # section principale: jusqu'au BORD de la photo
        gp = sweep(walls['rim_left'], lines.get('terrain_left'), False, 900)
        emit(gp)
        ext = [float(np.linalg.norm(Q[:2] - R[:2])) for R, Q in gp]
        print(f'pente gauche (au bord du cadre): {len(gp)} generatrices, '
              f'extension mediane {np.median(ext):.0f} m (max {max(ext):.0f})')
    if 'rim_left_top' in walls:
        # bout le plus eloigne: la section du fond pres du pont
        gp = sweep(walls['rim_left_top'], lines.get('terrain_mid'), True, 320)
        emit(gp)
        if gp:
            ext = [float(np.linalg.norm(Q[:2] - R[:2])) for R, Q in gp]
            print(f'pente gauche FOND (rim_left_top): {len(gp)} generatrices, '
                  f'extension mediane {np.median(ext):.0f} m')
    # ── COTE DROIT (meme modele que le gauche valide): haut du ridge a
    #    --slope-up derriere le rim; et la section 'moins abrupte' = flanc
    #    qui DESCEND vers la route a --bench-slope, stoppe par la luminance
    #    (le sable clair du bord de route) ────────────────────────────────
    if 'rim_right' in walls:
        gp = sweep(walls['rim_right'], lines.get('terrain_right_top'), False, 900)
        emit(gp)
        if gp:
            ext = [float(np.linalg.norm(Q[:2] - R[:2])) for R, Q in gp]
            print(f'pente droite HAUT: {len(gp)} generatrices, extension mediane '
                  f'{np.median(ext):.0f} m (max {max(ext):.0f})')
        # bench: generatrices vers la ROUTE, inclinees vers le bas
        bs = math.radians(args.bench_slope)
        rim = walls['rim_right']
        gp2 = []
        for i2 in range(0, len(rim), 2):
            R = rim[i2]
            # flanc COTE CAMERA (les hachures 'moins abrupte' d'Alexandre
            # sont sur le versant qui nous fait face, pas sur la face canyon)
            nh = o[:2] - R[:2]
            nh /= (np.linalg.norm(nh) + 1e-9)
            u_ok = None
            def okb(u):
                Q = np.array([R[0] + u * nh[0] * math.cos(bs),
                              R[1] + u * nh[1] * math.cos(bs),
                              R[2] - u * math.sin(bs)])
                pr = cam.get_pixel([float(v) for v in Q])
                if pr is None or pr[0] < 1 or pr[0] > cam.w - 1 or pr[1] > cam.h - 2:
                    return None
                if pr[1] > 1780:
                    return None                    # borne basse de la zone hachuree bench
                if lum(pr[0], pr[1]) > SKY:
                    return None
                if float(np.min(np.linalg.norm(road_xy - Q[:2], axis=1))) < args.width:
                    return None                    # jamais sur la chaussee
                return Q
            lastQ = None
            for u in np.arange(6, 420, 6):
                Q = okb(u)
                if Q is not None:
                    u_ok, lastQ = u, Q
                elif u_ok is not None:
                    lo, hi = u_ok, u
                    for _ in range(10):
                        mid = 0.5 * (lo + hi)
                        Qm = okb(mid)
                        if Qm is not None:
                            lo, lastQ = mid, Qm
                        else:
                            hi = mid
                    break
            if lastQ is not None and u_ok and u_ok > 8:
                gp2.append((R, lastQ))
        emit(gp2)
        if gp2:
            ext = [float(np.linalg.norm(Q[:2] - R[:2])) for R, Q in gp2]
            print(f'bench droite ({args.bench_slope:.0f} deg vers la route): '
                  f'{len(gp2)} generatrices, extension mediane {np.median(ext):.0f} m')
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
