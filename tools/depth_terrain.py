#!/usr/bin/env python3
"""depth_terrain.py — profondeur dense par reseau, calibree metrique. [DEPTH-V1]

Le saut d'outillage demande par Alexandre ('une meilleure modelisation avec
des meilleurs outils'): Depth Anything V2 (ONNX, local) donne une carte de
profondeur RELATIVE dense; nos landmarks triangules dans la frame la
calibrent en METRIQUE (fit disparite = a/z + b, moindres carres + rejet
d'outliers, validation leave-one-out imprimee).

Sortie: carte de profondeur colorisee + residus des ancres (PNG), et
optionnellement une surface 3D en grille sur une region (--region), ecrite
dans tools/generated/ (JAMAIS dans l'UI — regle: seuls nos modeles valides
y entrent).

Usage: PYTHONPATH=. python3 tools/depth_terrain.py --cam 'Ambrosia 01 (Bikers)'
       [--region x0,y0,x1,y1 --step 32 --mesh-out nom]
"""
import argparse
import json
import math
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
from PIL import Image
import common

MODEL = os.path.join(THIS, 'models', 'depth_anything_v2_vits.onnx')
NET_W = 700          # largeur d'inference (multiple de 14 apres resize)


def infer_disparity(img):
    import onnxruntime as ort
    w0, h0 = img.size
    w = NET_W - NET_W % 14
    h = int(round(h0 * w / w0 / 14)) * 14
    a = np.asarray(img.resize((w, h), Image.BICUBIC), np.float32) / 255.0
    a = (a - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    x = a.transpose(2, 0, 1)[None].astype(np.float32)
    s = ort.InferenceSession(MODEL, providers=['CPUExecutionProvider'])
    d = s.run(None, {'pixel_values': x})[0][0]
    return np.asarray(Image.fromarray(d).resize((w0, h0), Image.BILINEAR), np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cam', required=True)
    ap.add_argument('--region', default=None, help='x0,y0,x1,y1 pour la surface')
    ap.add_argument('--step', type=int, default=48)
    ap.add_argument('--mesh-out', default=None)
    ap.add_argument('--z-max', type=float, default=5000.0,
                    help='coupure ciel/fond: cellules plus loin exclues de la surface')
    ap.add_argument('--pseudo-road', action='store_true',
                    help='ajoute des pseudo-ancres sur la route du canyon '
                         '(profondeurs du profil DECLARE z0/z1 de canyon_mesh — '
                         'calibration partiellement assumee, pas 100 pct mesuree)')
    args = ap.parse_args()

    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    cam = common.get_cam(args.cam)
    o = np.asarray(cam.xyz, float)
    img = Image.open(os.path.join(REPO, 'frames', f'{args.cam}.png')).convert('RGB')
    disp = infer_disparity(img)
    print(f'disparite: {disp.shape}, range {disp.min():.2f}..{disp.max():.2f}')

    # ── ancres: marks de la frame avec xyz -> profondeur vraie ──────────
    anchors = []
    for lm, p in (px.get(args.cam) or {}).items():
        e = lms.get(lm)
        if not isinstance(e, dict) or not e.get('xyz'):
            continue
        P = np.asarray(e['xyz'], float)
        zdepth = float(np.linalg.norm(P - o))
        x, y = int(p[0]), int(p[1])
        if not (0 <= x < disp.shape[1] and 0 <= y < disp.shape[0]):
            continue
        d_net = float(np.median(disp[max(0, y - 3):y + 4, max(0, x - 3):x + 4]))
        anchors.append((lm, x, y, zdepth, d_net))
    print(f'{len(anchors)} ancres triangulees dans la frame')
    if args.pseudo_road:
        cl = json.load(open(os.path.join(REPO, 'tools', 'generated', 'canyon_lines.json')))
        rx, ry = cl['road_center']['x'], cl['road_center']['y']
        z0, z1 = 30.0, 55.0
        i_bot, i_top = int(np.argmax(ry)), int(np.argmin(ry))
        def dxy(i, zz):
            d = np.asarray(cam.get_pixel_direction((float(rx[i]), float(ry[i]))), float)
            d /= np.linalg.norm(d)
            t = (zz - o[2]) / d[2]
            return t
        t0, t1 = dxy(i_bot, z0), dxy(i_top, z1)
        for f in (0.0, 0.25, 0.5, 0.75, 1.0):
            i = int(i_bot + f * (i_top - i_bot))
            t = t0 + f * (t1 - t0)
            x, y = int(rx[i]), int(ry[i])
            d_net = float(np.median(disp[max(0, y - 3):y + 4, max(0, x - 3):x + 4]))
            anchors.append((f'[route declaree {f:.2f}]', x, y, float(t), d_net))
        print(f'+5 pseudo-ancres route (profil DECLARE z {z0}->{z1})')
    if len(anchors) < 3:
        print('pas assez d ancres pour calibrer'); return

    # fit disp = a * (1/z) + b, rejet iteratif des outliers
    keep = list(range(len(anchors)))
    for _ in range(4):
        A = np.array([[1.0 / anchors[i][3], 1.0] for i in keep])
        y_ = np.array([anchors[i][4] for i in keep])
        coef, *_ = np.linalg.lstsq(A, y_, rcond=None)
        a, b = float(coef[0]), float(coef[1])
        errs = []
        for i in keep:
            z_pred = a / max(1e-6, (anchors[i][4] - b))
            errs.append(abs(z_pred - anchors[i][3]) / anchors[i][3])
        med = float(np.median(errs))
        newkeep = [i for i, e2 in zip(keep, errs) if e2 < max(0.35, 3 * med)]
        if len(newkeep) == len(keep) or len(newkeep) < 3:
            break
        keep = newkeep
    print(f'calibration: disp = {a:.2f}/z + {b:.3f}  ({len(keep)}/{len(anchors)} ancres)')

    # validation leave-one-out
    print(f'{"ancre":36s} {"z vrai":>8s} {"z net":>8s} {"err":>7s}')
    rel = []
    for i in keep:
        others = [j for j in keep if j != i]
        A = np.array([[1.0 / anchors[j][3], 1.0] for j in others])
        y_ = np.array([anchors[j][4] for j in others])
        c2, *_ = np.linalg.lstsq(A, y_, rcond=None)
        z_pred = float(c2[0]) / max(1e-6, anchors[i][4] - float(c2[1]))
        e2 = (z_pred - anchors[i][3]) / anchors[i][3]
        rel.append(abs(e2))
        print(f'{anchors[i][0][:36]:36s} {anchors[i][3]:8.0f} {z_pred:8.0f} {100 * e2:+6.1f}%')
    print(f'LOO: erreur relative mediane {100 * np.median(rel):.1f}%')

    # ── visualisation ───────────────────────────────────────────────────
    z = a / np.clip(disp - b, a / 20000.0, None)
    z = np.clip(z, 0, 20000)
    from PIL import ImageDraw
    lo, hi = np.percentile(z, 2), np.percentile(z, 90)
    t = np.clip((z - lo) / (hi - lo + 1e-6), 0, 1)
    vis = np.stack([255 * (1 - t), 120 + 60 * t, 255 * t], axis=2).astype(np.uint8)
    sky = z > args.z_max
    base = np.asarray(img, np.uint8)
    vis[sky] = base[sky]                       # le ciel n'est pas teinte
    vim = Image.blend(img, Image.fromarray(vis), 0.55)
    dr = ImageDraw.Draw(vim)
    for i in keep:
        lm, x, y, zt, _ = anchors[i]
        dr.ellipse([x - 6, y - 6, x + 6, y + 6], outline=(255, 255, 0), width=3)
    od = os.path.join(REPO, 'tools', 'generated')
    vpath = os.path.join(od, f'depth_{args.cam.replace("/", "_")}.png')
    vim.save(vpath)
    print(f'-> {vpath}')

    # ── surface 3D optionnelle sur une region ───────────────────────────
    if args.region:
        x0, y0, x1, y1 = map(int, args.region.split(','))
        edges = []
        grid = {}
        gray = np.asarray(img.convert('L'), np.float32)
        for gy in range(y0, y1, args.step):
            for gx in range(x0, x1, args.step):
                zm = float(np.median(z[gy:gy + 7, gx:gx + 7]))
                if zm > args.z_max:
                    continue                     # ciel / fond trop lointain
                if float(gray[gy:gy + 7, gx:gx + 7].mean()) > 205 and zm > 1500:
                    continue                     # ciel clair residuel
                d = np.asarray(cam.get_pixel_direction((float(gx), float(gy))), float)
                d /= np.linalg.norm(d)
                grid[(gx, gy)] = o + zm * d
        for (gx, gy), P in grid.items():
            for nb in ((gx + args.step, gy), (gx, gy + args.step)):
                if nb in grid:
                    edges.append([list(map(float, P)), list(map(float, grid[nb]))])
        name = args.mesh_out or f'[depth] {args.cam}'
        out = {name: {'color': '#38bdf8', 'world_edges': edges}}
        mpath = os.path.join(od, 'depth_terrain_meshes.json')
        cur = json.load(open(mpath)) if os.path.exists(mpath) else {}
        cur.update(out)
        json.dump(cur, open(mpath, 'w'), indent=1)
        zs = [p[2] for p in grid.values()]
        print(f'surface: {len(grid)} pts, z {min(zs):.0f}-{max(zs):.0f} -> {mpath} '
              f'(PAS dans l UI)')


if __name__ == '__main__':
    main()
