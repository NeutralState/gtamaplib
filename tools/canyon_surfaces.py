#!/usr/bin/env python3
"""canyon_surfaces.py — chaque surface ANALYSEE, pas devinee. [CANYON-SURF-V1]

Ce que les v1-v8 faisaient: choisir une direction et une pente, puis
verifier que ca retombe sur la photo — tautologique en vue unique.

Ce que fait celui-ci: il MESURE la forme de chaque surface dans l'image.

  1. PROFONDEUR DENSE — Depth Anything V2 (local) sur la frame.
  2. CALIBRATION METRIQUE — pas 4 ancres eparses: les ~667 points de la
     ligne de sol d'Alexandre, dont la profondeur est exacte (rayon x
     plancher du canyon). Fit disp = a/z + b + validation leave-one-out.
  3. REGIONS — bornees par SES lignes (sol / crete / enveloppe haute):
     'face' = entre le pied et la crete, 'plateau' = au-dessus de la crete.
  4. ANALYSE PAR SURFACE — pour chaque region on echantillonne la carte de
     profondeur, on retro-projette en 3D et on fitte un PLAN robuste
     (moindres carres + rejet iteratif). On imprime sa pente reelle, son
     azimut et son rms: la geometrie devient une MESURE, verifiable.
  5. MESH — grille de la surface fittee, clippee a la region.

Usage: PYTHONPATH=. python3 tools/canyon_surfaces.py [--apply] [--step 24]
"""
import argparse
import importlib.util
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

spec = importlib.util.spec_from_file_location('dt', os.path.join(THIS, 'depth_terrain.py'))
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)

CAM = 'Mount Kalaga National Park 04 (Mountain Pass) (X)'
MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
COLORS = {'face': '#fb923c', 'plateau': '#4ade80',
          'face_droite': '#f87171', 'plateau_droit': '#22d3ee'}


def line_y(l):
    x = np.asarray(l['x'], float)
    y = np.asarray(l['y'], float)
    i = np.argsort(x)
    return x[i], y[i]


def fit_plane(P, iters=5):
    """Plan robuste z = c0*x + c1*y + c2, rejet iteratif a 2 sigma."""
    keep = np.ones(len(P), bool)
    c = None
    for _ in range(iters):
        A = np.column_stack([P[keep, 0], P[keep, 1], np.ones(keep.sum())])
        c, *_ = np.linalg.lstsq(A, P[keep, 2], rcond=None)
        r = P[:, 2] - (c[0] * P[:, 0] + c[1] * P[:, 1] + c[2])
        s = np.std(r[keep])
        nk = np.abs(r) < 2.0 * s
        if nk.sum() < 20 or nk.sum() == keep.sum():
            keep = nk if nk.sum() >= 20 else keep
            break
        keep = nk
    r = P[keep, 2] - (c[0] * P[keep, 0] + c[1] * P[keep, 1] + c[2])
    slope = math.degrees(math.atan(math.hypot(c[0], c[1])))
    az = math.degrees(math.atan2(-c[0], -c[1])) % 360      # direction de montee
    return c, float(np.sqrt(np.mean(r ** 2))), slope, az, keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--z0', type=float, default=30.0)
    ap.add_argument('--z1', type=float, default=55.0)
    ap.add_argument('--step', type=int, default=24)
    ap.add_argument('--local', action='store_true',
                    help='surface LOCALE (profondeur lissee back-projetee) au lieu '
                         'd un plan global par region — garde le relief mesure')
    ap.add_argument('--smooth-px', type=int, default=61,
                    help='lissage de la carte de profondeur (px), mode --local')
    ap.add_argument('--model', default='small', choices=['small', 'large'],
                    help='taille du reseau de profondeur (large = ViT-L, 1.3 Go)')
    ap.add_argument('--net-w', type=int, default=700,
                    help='largeur d inference du reseau (plus grand = plus fin)')
    ap.add_argument('--normals', action='store_true',
                    help='controle independant: orientation de chaque surface '
                         'mesuree par les NORMALES de Metric3D V2 (sans echelle)')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    lines = json.load(open(os.path.join(REPO, 'tools', 'generated', 'canyon_lines.json')))
    cam = common.get_cam(CAM)
    o = np.asarray(cam.xyz, float)
    img = Image.open(os.path.join(REPO, 'frames', f'{CAM}.png')).convert('RGB')

    def ray(x, y):
        d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
        return d / np.linalg.norm(d)

    # ── plancher + pieds ancres (les ancres de calibration) ─────────────
    rx, ry = lines['road_center']['x'], lines['road_center']['y']
    i_bot, i_top = int(np.argmax(ry)), int(np.argmin(ry))
    r0, r1 = ray(rx[i_bot], ry[i_bot]), ray(rx[i_top], ry[i_top])
    d0 = (args.z0 - o[2]) / r0[2] * float(np.hypot(r0[0], r0[1]))
    d1 = (args.z1 - o[2]) / r1[2] * float(np.hypot(r1[0], r1[1]))
    B = (args.z1 - args.z0) / (d1 - d0)
    A = args.z0 - B * d0

    gl = lines['ground_left']
    anchors = []                                # (px, py, profondeur vraie)
    for gx, gy in zip(gl['x'], gl['y']):
        r = ray(gx, gy)
        t = (A - o[2]) / (r[2] - B * float(np.hypot(r[0], r[1])))
        if t > 0:
            anchors.append((float(gx), float(gy), float(t)))
    print(f'{len(anchors)} ancres de calibration (ligne de sol x plancher), '
          f'profondeur {min(a[2] for a in anchors):.0f}-{max(a[2] for a in anchors):.0f} m')

    # ── profondeur dense + calibration metrique ─────────────────────────
    dt.MODEL = dt.MODELS[args.model]
    dt.NET_W = args.net_w
    print(f'reseau: {args.model} @ {args.net_w} px')
    disp = dt.infer_disparity(img)
    dv = np.array([float(np.median(disp[max(0, int(y) - 3):int(y) + 4,
                                        max(0, int(x) - 3):int(x) + 4]))
                   for x, y, _ in anchors])
    zv = np.array([a[2] for a in anchors])
    keep = np.ones(len(zv), bool)
    for _ in range(4):
        M = np.column_stack([1.0 / zv[keep], np.ones(keep.sum())])
        c, *_ = np.linalg.lstsq(M, dv[keep], rcond=None)
        zp = c[0] / np.clip(dv - c[1], 1e-6, None)
        err = np.abs(zp - zv) / zv
        nk = err < max(0.25, 3 * np.median(err[keep]))
        if nk.sum() < 30 or nk.sum() == keep.sum():
            break
        keep = nk
    a_, b_ = float(c[0]), float(c[1])
    zp = a_ / np.clip(dv - b_, 1e-6, None)
    rel = np.abs(zp - zv)[keep] / zv[keep]
    print(f'calibration: disp = {a_:.1f}/z + {b_:.3f}  ({int(keep.sum())}/{len(zv)} ancres), '
          f'erreur relative mediane {100 * np.median(rel):.1f}%')
    Z = a_ / np.clip(disp - b_, a_ / 20000.0, None)
    if args.local:
        # lissage separable de la carte de profondeur: le bruit du reseau
        # (~4 pct = 16 m a 400 m) est filtre, le RELIEF reste
        w = max(3, args.smooth_px | 1)
        k = np.ones(w) / w
        Zs = np.apply_along_axis(lambda v: np.convolve(v, k, mode='same'), 1, Z)
        Zs = np.apply_along_axis(lambda v: np.convolve(v, k, mode='same'), 0, Zs)
        b2 = w // 2
        Zs[:b2] = Z[:b2]; Zs[-b2:] = Z[-b2:]
        Zs[:, :b2] = Z[:, :b2]; Zs[:, -b2:] = Z[:, -b2:]
        Z = Zs
        print(f'mode LOCAL: carte de profondeur lissee sur {w} px')

    # ── regions bornees par SES lignes ──────────────────────────────────
    gx_, gy_ = line_y(gl)
    rim = []
    for nm in ('rim_left', 'rim_left_pinnacle', 'rim_left_top'):
        if nm in lines:
            rim += list(zip(lines[nm]['x'], lines[nm]['y']))
    tb = {}
    for xx, yy in rim:
        k = int(round(xx / 8.0))
        if k not in tb or yy < tb[k][1]:
            tb[k] = (xx, yy)
    rr = sorted(tb.values())
    rx_ = np.array([p[0] for p in rr]); ry_ = np.array([p[1] for p in rr])
    env = lines.get('terrain_left')
    ex_, ey_ = line_y(env) if env else (None, None)

    X0 = int(max(gx_.min(), rx_.min()))
    X1 = int(min(gx_.max(), rx_.max()))
    print(f'bande commune sol/crete: x {X0} -> {X1}')

    regions = {'face': [], 'plateau': []}
    for px_ in range(X0, X1, args.step):
        y_g = float(np.interp(px_, gx_, gy_))
        y_r = float(np.interp(px_, rx_, ry_))
        y_e = float(np.interp(px_, ex_, ey_)) if env is not None else y_r - 200
        for py_ in range(int(y_r) + 6, int(y_g) - 6, args.step):
            regions['face'].append((px_, py_))
        for py_ in range(int(y_e) + 6, int(y_r) - 6, args.step):
            regions['plateau'].append((px_, py_))

    # ── COTE DROIT: memes bornes, ses lignes de droite ──────────────────
    # face droite  = rim_right -> terrain_right_bench (la section 'moins
    #                abrupte' qu'il a hachuree = le pied de la paroi)
    # plateau droit= terrain_right_top -> rim_right
    if 'rim_right' in lines:
        rrx, rry = line_y(lines['rim_right'])
        bench = lines.get('terrain_right_bench')
        rtop = lines.get('terrain_right_top')
        bx_, by_ = line_y(bench) if bench else (None, None)
        tx_, ty_ = line_y(rtop) if rtop else (None, None)
        RX0 = int(rrx.min())
        RX1 = int(rrx.max())
        if bench is not None:
            RX0 = max(RX0, int(bx_.min())); RX1 = min(RX1, int(bx_.max()))
        regions['face_droite'] = []
        regions['plateau_droit'] = []
        for px_ in range(RX0, RX1, args.step):
            y_r = float(np.interp(px_, rrx, rry))
            if bench is not None:
                y_b = float(np.interp(px_, bx_, by_))
                for py_ in range(int(y_r) + 6, int(y_b) - 6, args.step):
                    regions['face_droite'].append((px_, py_))
            if rtop is not None and tx_.min() <= px_ <= tx_.max():
                y_t = float(np.interp(px_, tx_, ty_))
                for py_ in range(int(y_t) + 6, int(y_r) - 6, args.step):
                    regions['plateau_droit'].append((px_, py_))
        print(f'cote droit: bande x {RX0} -> {RX1}')

    # ── controle independant par NORMALES (Metric3D V2) ─────────────────
    NRM = None
    if args.normals:
        import onnxruntime as ort
        mp = os.path.join(THIS, 'models', 'metric3d_vitl.onnx')
        if not os.path.exists(mp):
            print('normales: modele Metric3D absent, saute')
        else:
            w_ = args.net_w - args.net_w % 14
            h_ = int(round(img.size[1] * w_ / img.size[0] / 14)) * 14
            aa = np.asarray(img.resize((w_, h_), Image.BICUBIC), np.float32)
            aa = (aa / 255.0 - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
            sess = ort.InferenceSession(mp, providers=['CPUExecutionProvider'])
            _, nor, cf = sess.run(None, {'pixel_values':
                                         aa.transpose(2, 0, 1)[None].astype(np.float32)})
            NRM = (nor[0], cf[0])
            print(f'normales Metric3D: {nor[0].shape[1]}x{nor[0].shape[2]}')

    def measure_normal(pxs):
        nor, cf = NRM
        _, Hn, Wn = nor.shape
        sx, sy = img.size[0] / Wn, img.size[1] / Hn
        c0 = np.asarray(cam.get_pixel_direction((cam.w / 2, cam.h / 2)), float)
        c0 /= np.linalg.norm(c0)
        rgt = (np.asarray(cam.get_pixel_direction((cam.w / 2 + 400, cam.h / 2)), float)
               - np.asarray(cam.get_pixel_direction((cam.w / 2 - 400, cam.h / 2)), float))
        rgt /= np.linalg.norm(rgt)
        dwn = (np.asarray(cam.get_pixel_direction((cam.w / 2, cam.h / 2 + 400)), float)
               - np.asarray(cam.get_pixel_direction((cam.w / 2, cam.h / 2 - 400)), float))
        dwn /= np.linalg.norm(dwn)
        N, C = [], []
        for x, y in pxs:
            xi, yi = int(x / sx), int(y / sy)
            if not (0 <= xi < Wn and 0 <= yi < Hn):
                continue
            n_ = nor[:, yi, xi]
            nw = n_[0] * rgt + n_[1] * dwn + n_[2] * c0
            nw /= (np.linalg.norm(nw) + 1e-9)
            if nw[2] < 0:
                nw = -nw
            N.append(nw); C.append(cf[yi, xi])
        if len(N) < 20:
            return None
        N = np.array(N); C = np.array(C)
        m = (N * (C / C.sum())[:, None]).sum(axis=0)
        m /= np.linalg.norm(m)
        slope = math.degrees(math.acos(min(1.0, abs(m[2]))))
        az = math.degrees(math.atan2(m[0], m[1])) % 360     # montee
        disp_ = math.degrees(float(np.mean(np.arccos(np.clip(N @ m, -1, 1)))))
        return slope, az, disp_

    out = {}
    for name, pxs in regions.items():
        if len(pxs) < 40:
            print(f'{name}: trop peu de pixels ({len(pxs)}), saute')
            continue
        P = []
        for x, y in pxs:
            zm = float(np.median(Z[y:y + 5, x:x + 5]))
            if not (50 < zm < 3000):
                continue
            P.append(o + zm * ray(x, y))
        P = np.array(P)
        c, rms, slope, az, kp = fit_plane(P)
        az_up = (az + 180.0) % 360           # convention: azimut de MONTEE
        print(f'{name:8s}: {len(P)} points, PLAN(profondeur)  pente {slope:5.1f} deg  '
              f'montee {az_up:5.0f}  rms {rms:5.1f} m  ({int(kp.sum())} inliers)')
        if NRM is not None:
            mn = measure_normal(pxs)
            if mn:
                print(f'          NORMALES(Metric3D)  pente {mn[0]:5.1f} deg  '
                      f'montee {mn[1]:5.0f}  dispersion {mn[2]:4.1f} deg '
                      f'-> ecart de pente {abs(mn[0] - slope):4.1f} deg')
        # mesh: la surface fittee, echantillonnee sur les memes pixels
        grid = {}
        for x, y in pxs:
            r = ray(x, y)
            if args.local:
                zm = float(np.median(Z[y:y + 5, x:x + 5]))
                if not (50 < zm < 3000):
                    continue
                grid[(x, y)] = o + zm * r      # surface MESUREE, pas le plan
                continue
            den = r[2] - c[0] * r[0] - c[1] * r[1]
            if abs(den) < 1e-9:
                continue
            t = (c[0] * o[0] + c[1] * o[1] + c[2] - o[2]) / den
            if t <= 0:
                continue
            grid[(x, y)] = o + t * r
        edges = []
        for (x, y), Pt in grid.items():
            for nb in ((x + args.step, y), (x, y + args.step)):
                if nb in grid:
                    edges.append([list(map(float, Pt)), list(map(float, grid[nb]))])
        if edges:
            out[f'Canyon {name.replace("_", " ").title()} (Kalaga Pass)'] = {
                'color': COLORS[name], 'world_edges': edges}
            zs = [p[2] for p in grid.values()]
            print(f'          -> {len(edges)} aretes, z {min(zs):.0f}-{max(zs):.0f} m')

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
