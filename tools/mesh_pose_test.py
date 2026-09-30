#!/usr/bin/env python3
"""mesh_pose_test.py — le solveur de pose par silhouettes de meshes retrouve-t-il une pose
validee apres perturbation ? (zero clic) [MESH-POSE-TEST 2026-09-30]

Pour chaque cam: pose validee P0 -> perturbation (dyaw, dpitch, droll, dfov) -> optimisation
de l'orientation + fov sur le cout de silhouette (distance moyenne des contours des meshes
visibles, non occultes, hors vegetation, aux bords de l'image) -> ecart final a P0.
Recherche grossiere (grille) puis Nelder-Mead, pour sortir des minima locaux.
"""
import json, os, sys
THIS = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, THIS); sys.path.insert(0, os.path.dirname(THIS))
import numpy as np
from scipy.optimize import minimize
import mesh_fit as MF


def silhouettes(cam, st, M):
    ctx = MF._Ctx(cam, st); vis = MF._visible(ctx, M); occ = MF._band_masks(ctx, vis); Ps = []
    for k, e in vis.items():
        P = MF._samples(ctx, e, k, occ)
        if len(P) < 15: continue
        if ctx.veg is not None:
            yi = np.clip(P[:, 1].astype(int), 0, ctx.H - 1); xi = np.clip(P[:, 0].astype(int), 0, ctx.W - 1)
            if ctx.veg[yi, xi].mean() > MF.FOLIAGE_MAX: continue
        Ps.append(P)
    return ctx, Ps


def cost(cam, c, th, M, ctx0):
    st = {'xyz': c['xyz'], 'ypr': [c['ypr'][0] + th[0], c['ypr'][1] + th[1], c['ypr'][2] + th[2]], 'fov': [c['fov'][0] + th[3], c['fov'][1]]}
    ctx0.cam = MF.common.get_cam(cam, st)
    vis = MF._visible(ctx0, M); occ = MF._band_masks(ctx0, vis); tot = 0.0; n = 0
    for k, e in vis.items():
        P = MF._samples(ctx0, e, k, occ)
        if len(P) < 15: continue
        if ctx0.veg is not None:
            yi = np.clip(P[:, 1].astype(int), 0, ctx0.H - 1); xi = np.clip(P[:, 0].astype(int), 0, ctx0.W - 1)
            if ctx0.veg[yi, xi].mean() > MF.FOLIAGE_MAX: continue
        tot += MF._cost(ctx0, P) * len(P); n += len(P)
    return tot / n if n else 99.0


def run(cam, pert, M):
    c = json.load(open(MF.CAMS))[cam]; ctx0 = MF._Ctx(cam)
    f = lambda th: cost(cam, c, th, M, ctx0)
    start = np.array(pert, float)
    # grille grossiere autour du depart (+-0.6 deg yaw/pitch)
    best = (f(start), start)
    for dy in np.linspace(-0.6, 0.6, 7):
        for dp in np.linspace(-0.6, 0.6, 7):
            t = start + [dy, dp, 0, 0]; v = f(t)
            if v < best[0]: best = (v, t)
    r = minimize(f, best[1], method='Nelder-Mead', options={'xatol': 0.005, 'fatol': 0.002, 'maxiter': 300,
                 'initial_simplex': best[1] + np.array([[0, 0, 0, 0], [0.15, 0, 0, 0], [0, 0.15, 0, 0], [0, 0, 0.3, 0], [0, 0, 0, 0.4]])})
    return f(np.zeros(4)), f(start), r.fun, r.x


if __name__ == '__main__':
    M = json.load(open(MF.MESHES))
    cams = [a for a in sys.argv[1:] if not a.startswith('--')]
    rng = np.random.default_rng(1)
    for cam in cams:
        pert = [0.5 * rng.choice([-1, 1]), 0.4 * rng.choice([-1, 1]), 0.3 * rng.choice([-1, 1]), 0.8 * rng.choice([-1, 1])]
        c0, cs, cf, x = run(cam, pert, M)
        print('%-34s depart %s | cout vraie %.2f, depart %.2f, final %.2f | ecart final yaw %+.3f pitch %+.3f roll %+.3f fov %+.2f'
              % (cam[:34], pert, c0, cs, cf, *x), flush=True)
