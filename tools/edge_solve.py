#!/usr/bin/env python3
"""edge_solve.py — optimisation sub-pixel sur les bords d'image. [EDGE-FIT-V2]

Le cout: pour chaque arete projetee d'un mesh, echantillonner le long et
mesurer la distance perpendiculaire au pic de gradient (le vrai bord du
batiment). Soft-l1, vectorise numpy. Deux modes:

  --mode mesh  : fit le PLACEMENT du building (dx dy dth [+dz +scale]) en
                 sommant le cout sur plusieurs cams-juges nettes.
  --mode cam   : polit la POSE d'une cam (dyaw dpitch [droll]) contre les
                 meshes qu'elle voit — zero clic, la frame est la verite.

La frame de reference: seules les frames NETTES portent du signal (les
floues/nocturnes chassent les lumieres — mesure EDGE-FIT-V1). Le tool
rapporte le biais AVANT/APRES par cam x building; garde anti-regression.

Usage:
  # valider/fitter les twins sur 3 juges:
  PYTHONPATH=. python3 tools/edge_solve.py --mode mesh \
      --buildings "Vizcayne North Condominium,Vizcayne South Condominium" \
      --cams "Port Vice City (A),Port Vice City (B),Vice City 03 (Basketball)" [--apply]
  # polir la pose de Basketball contre ses 3 meshes:
  PYTHONPATH=. python3 tools/edge_solve.py --mode cam --cam "Vice City 03 (Basketball)" \
      --buildings "Stephen P. Clark Government Center,Vizcayne North Condominium,Vizcayne South Condominium" [--apply]
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

SEARCH = 10
STEP = 4
MIN_EDGE_PX = 15
MIN_PEAK = 12.0
PROMINENCE = 2.5


class FrameCtx:
    def __init__(self, cam_name):
        self.name = cam_name
        self.cam = common.get_cam(cam_name)
        img = np.asarray(Image.open(os.path.join(REPO, 'frames', f'{cam_name}.png')).convert('L'), dtype=float)
        gy, gx = np.gradient(img)
        self.gmag = np.hypot(gx, gy)
        self.H, self.W = img.shape

    def recam(self, cam_state):
        self.cam = common.get_cam(self.name, cam_state)


def sample_cost(ctx, edges_world, collect=False):
    """Cout soft-l1 des offsets perpendiculaires + (option) liste des offsets."""
    pts, nrms = [], []
    for a, b in edges_world:
        pa, pb = ctx.cam.get_pixel(a), ctx.cam.get_pixel(b)
        if pa is None or pb is None:
            continue
        pa = np.asarray(pa, float); pb = np.asarray(pb, float)
        L = float(np.hypot(*(pb - pa)))
        if L < MIN_EDGE_PX:
            continue
        t = (pb - pa) / L
        n = np.array([-t[1], t[0]])
        for s in np.arange(3, L - 3, STEP):
            pts.append(pa + t * s); nrms.append(n)
    if not pts:
        return 0.0, 0, []
    P = np.array(pts); N = np.array(nrms)
    ok = (P[:, 0] > SEARCH) & (P[:, 0] < ctx.W - SEARCH - 1) & (P[:, 1] > SEARCH) & (P[:, 1] < ctx.H - SEARCH - 1)
    P, N = P[ok], N[ok]
    if not len(P):
        return 0.0, 0, []
    offs_range = np.arange(-SEARCH, SEARCH + 1)
    # matrice (npts, 21) des gradients le long de la normale
    X = (P[:, 0:1] + N[:, 0:1] * offs_range[None, :]).astype(int)
    Y = (P[:, 1:2] + N[:, 1:2] * offs_range[None, :]).astype(int)
    G = ctx.gmag[Y, X]
    k = np.argmax(G, axis=1)
    peak = G[np.arange(len(G)), k]
    med = np.median(G, axis=1)
    valid = (peak >= MIN_PEAK) & (peak >= PROMINENCE * np.maximum(med, 1e-6))
    off = (k - SEARCH)[valid].astype(float)
    if not len(off):
        return 0.0, 0, []
    cost = float(np.sum(np.sqrt(1 + (off / 3.0) ** 2) - 1))
    return cost, len(off), (off if collect else [])


def transform_edges(edges, centroid, dx, dy, dz, dth, ds):
    c, s_ = math.cos(dth), math.sin(dth)
    out = []
    for a, b in edges:
        pts = []
        for p in (a, b):
            x = centroid[0] + ds * (c * (p[0] - centroid[0]) - s_ * (p[1] - centroid[1])) + dx
            y = centroid[1] + ds * (s_ * (p[0] - centroid[0]) + c * (p[1] - centroid[1])) + dy
            pts.append([x, y, centroid[2] + ds * (p[2] - centroid[2]) + dz])
        out.append(pts)
    return out


def descend(cost_fn, x0, steps, min_step=0.004, rounds=120):
    best = (cost_fn(x0), list(x0))
    step = list(steps)
    for _ in range(rounds):
        improved = False
        for i, s in enumerate(step):
            if s == 0.0:
                continue
            for sgn in (1, -1):
                cand = list(best[1]); cand[i] += sgn * s
                c = cost_fn(cand)
                if c < best[0] - 1e-9:
                    best = (c, cand); improved = True
        if not improved:
            step = [s / 2 for s in step]
            if max(step) < min_step:
                break
    return best[1]


def report(ctxs, meshes, label):
    print(f'── {label}:')
    for ctx in ctxs:
        for bname, edges in meshes.items():
            _, n, off = sample_cost(ctx, edges, collect=True)
            if n > 15:
                print(f'   {ctx.name[:28]:28} {bname.split()[0][:12]:12} {n:5} pts  biais {np.median(off):+.1f}px  |off| {np.median(np.abs(off)):.1f}px')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['mesh', 'cam'], required=True)
    ap.add_argument('--buildings', required=True)
    ap.add_argument('--cams', default=None, help='mode mesh: cams-juges (csv)')
    ap.add_argument('--cam', default=None, help='mode cam: la cam a polir')
    ap.add_argument('--dz', action='store_true')
    ap.add_argument('--scale', action='store_true')
    ap.add_argument('--roll', action='store_true', help='mode cam: roll libre aussi')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    bp = json.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')))
    buildings = [b.strip() for b in args.buildings.split(',')]
    meshes = {b: bp[b]['world_edges'] for b in buildings}

    if args.mode == 'mesh':
        cams = [c.strip() for c in args.cams.split(',')]
        ctxs = [FrameCtx(c) for c in cams]
        allpts = [p for e in meshes.values() for ab in e for p in ab]
        centroid = np.mean(np.array(allpts), axis=0)
        report(ctxs, meshes, 'AVANT')

        def cost(th):
            dx, dy, dz, dth, ds = th
            tot = 0.0
            for b, edges in meshes.items():
                te = transform_edges(edges, centroid, dx, dy, dz, dth, ds)
                for ctx in ctxs:
                    c, n, _ = sample_cost(ctx, te)
                    tot += c
            return tot

        steps = [1.0, 1.0, 0.5 if args.dz else 0.0, math.radians(0.2), 0.005 if args.scale else 0.0]
        th = descend(cost, [0.0, 0.0, 0.0, 0.0, 1.0], steps)
        dx, dy, dz, dth, ds = th
        print(f'\nTRANSFORM: dx={dx:+.2f} dy={dy:+.2f} dz={dz:+.2f} rot={math.degrees(dth):+.3f} deg scale={ds:.4f}')
        tmeshes = {b: transform_edges(e, centroid, *th) for b, e in meshes.items()}
        report(ctxs, tmeshes, 'APRES')
        if args.apply:
            # applique aux coins LMs (meme semantique que fit_mesh)
            lms_path = os.path.join(REPO, 'gtamapdata', 'landmarks.json')
            lms = json.load(open(lms_path))
            c, s_ = math.cos(dth), math.sin(dth)
            nmoved = 0
            for b in buildings:
                for n, e in lms.items():
                    if not n.startswith(b + ' (') or not isinstance(e, dict) or not e.get('xyz'):
                        continue
                    p = e['xyz']
                    x = centroid[0] + ds * (c * (p[0] - centroid[0]) - s_ * (p[1] - centroid[1])) + dx
                    y = centroid[1] + ds * (s_ * (p[0] - centroid[0]) + c * (p[1] - centroid[1])) + dy
                    z = centroid[2] + ds * (p[2] - centroid[2]) + dz
                    e['xyz'] = [round(float(x), 3), round(float(y), 3), round(float(z), 3)]
                    zc = e.get('z_constraint')
                    if zc and zc.get('type') == 'fixed' and (args.dz or args.scale):
                        zc['value'] = round(float(z), 3)
                    nmoved += 1
            tmp = lms_path + '.tmp'
            json.dump(lms, open(tmp, 'w'), indent=2, ensure_ascii=True)
            os.replace(tmp, lms_path)
            common.log_event('edge_solve', 'mesh_applied',
                             reason=f'{buildings}: edge-fit {len(ctxs)} cams, transform dx{dx:+.2f} dy{dy:+.2f} rot{math.degrees(dth):+.3f}')
            print(f'APPLIED: {nmoved} coins. Regenerer les meshes procedureaux!')
    else:
        C = args.cam
        ctx = FrameCtx(C)
        cams_json = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
        e0 = cams_json[C]
        report([ctx], meshes, 'AVANT')

        def cost(th):
            dyaw, dpitch, droll = th
            ctx.recam({'xyz': e0['xyz'], 'ypr': [e0['ypr'][0] + dyaw, e0['ypr'][1] + dpitch, e0['ypr'][2] + droll],
                       'fov': e0['fov']})
            tot = 0.0
            for b, edges in meshes.items():
                c, n, _ = sample_cost(ctx, edges)
                tot += c
            return tot

        steps = [0.05, 0.05, 0.05 if args.roll else 0.0]
        th = descend(cost, [0.0, 0.0, 0.0], steps, min_step=0.002)
        dyaw, dpitch, droll = th
        print(f'\nDELTA POSE: dyaw={dyaw:+.3f} dpitch={dpitch:+.3f} droll={droll:+.3f} deg')
        ctx.recam({'xyz': e0['xyz'], 'ypr': [e0['ypr'][0] + dyaw, e0['ypr'][1] + dpitch, e0['ypr'][2] + droll],
                   'fov': e0['fov']})
        report([ctx], meshes, 'APRES')
        if args.apply:
            e0['ypr'] = [round(e0['ypr'][0] + dyaw, 4), round(e0['ypr'][1] + dpitch, 4), round(e0['ypr'][2] + droll, 4)]
            tmp = os.path.join(REPO, 'gtamapdata', 'cameras.json.tmp')
            json.dump(cams_json, open(tmp, 'w'), indent=2, ensure_ascii=True)
            os.replace(tmp, os.path.join(REPO, 'gtamapdata', 'cameras.json'))
            common.log_event('edge_solve', 'cam_applied',
                             reason=f'{C}: pose polie sur les bords des meshes {buildings}, dypr=[{dyaw:+.3f},{dpitch:+.3f},{droll:+.3f}]')
            print('APPLIED: ypr poli.')


if __name__ == '__main__':
    main()
