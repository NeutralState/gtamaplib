#!/usr/bin/env python3
"""sky_pose_test.py — solveur de pose par la frontiere CIEL de la segmentation (zero clic). [SKY-POSE 2026-09-30]

Cout: les contours de la silhouette des meshes visibles (union des enveloppes par tranche de
hauteur, meshes caches par la vegetation exclus) doivent tomber sur la frontiere ciel / non-ciel
de la segmentation SegFormer (classe 2 = sky). Contrairement aux bords d'image, cette frontiere
n'a pas de texture parasite (champs, feuillage, nuages, fils).
Symetrique: on penalise aussi le ciel predit comme bati (mesh la ou la segmentation voit du ciel).
Test: pose validee -> perturbation -> grille + Nelder-Mead -> ecart a la pose validee.
"""
import json, os, sys
THIS = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, THIS); sys.path.insert(0, os.path.dirname(THIS))
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.optimize import minimize
from scipy.spatial import ConvexHull
import common
import mesh_fit as MF
from edgefit_core import _project_pts

SKY = 2
WORK = 960          # largeur de travail (px)
CAP = 12.0


class SkyCtx:
    def __init__(self, cam):
        self.name = cam
        cls = np.load(os.path.join(THIS, 'generated', 'seg_veg', cam.replace('/', '_') + '_cls.npy'))
        H0, W0 = cls.shape; self.s = WORK / W0
        self.W, self.H = WORK, int(round(H0 * self.s))
        c = np.asarray(Image.fromarray(cls).resize((self.W, self.H), Image.NEAREST))
        self.sky = c == SKY
        edge = self.sky ^ ndimage.binary_erosion(self.sky)
        self.dist = ndimage.distance_transform_edt(~edge)
        self.veg = np.isin(c, [4, 17, 9, 72, 66])


def mesh_union(ctx, cam_state, M, cam):
    fc = MF._Ctx.__new__(MF._Ctx); fc.name = cam; fc.cam = common.get_cam(cam, cam_state)
    fc.W, fc.H = int(ctx.W / ctx.s), int(ctx.H / ctx.s)
    vis = MF._visible(fc, M)
    U = Image.new('L', (ctx.W, ctx.H), 0); dr = ImageDraw.Draw(U)
    for name, e in vis.items():
        E = np.asarray(e, float); z = E[..., 2]; zmin, zmax = z.min(), z.max(); nb = max(1, min(12, int((zmax - zmin) / 6)))
        polys = []
        for b in range(nb):
            lo = zmin + (zmax - zmin) * b / nb; hi = zmin + (zmax - zmin) * (b + 1) / nb
            sel = [ab for ab in e if max(ab[0][2], ab[1][2]) >= lo - 1e-6 and min(ab[0][2], ab[1][2]) <= hi + 1e-6]
            pr = _project_pts(fc, sel)
            if len(pr) < 2: continue
            A = np.array([p for ab in pr for p in ab]) * ctx.s
            try: polys.append(A[ConvexHull(A).vertices])
            except Exception: pass
        if not polys: continue
        # mesh cache par la vegetation -> exclu
        m = Image.new('L', (ctx.W, ctx.H), 0); d2 = ImageDraw.Draw(m)
        for p in polys: d2.polygon([tuple(map(float, q)) for q in p], fill=1)
        mk = np.asarray(m, bool)
        if mk.sum() < 6: continue
        ys = np.nonzero(mk.any(1))[0]; top = mk.copy(); top[int((ys[0] + ys[-1]) / 2):] = False
        if top.sum() and ctx.veg[top].mean() > 0.75: continue
        for p in polys: dr.polygon([tuple(map(float, q)) for q in p], fill=1)
    return np.asarray(U, bool)


def cost(ctx, U):
    if U.sum() < 20: return 99.0
    bnd = U & ~ndimage.binary_erosion(U)
    ys, xs = np.nonzero(bnd)
    ok = ~ctx.veg[ys, xs]                                    # bords du mesh sur vegetation: pas de signal
    near_sky = ndimage.binary_dilation(ctx.sky, iterations=3)[ys, xs]
    ys, xs = ys[ok & near_sky], xs[ok & near_sky]           # seuls les bords du mesh au contact du ciel comptent
    if len(ys) < 20: return 99.0
    c1 = float(np.mean(np.minimum(ctx.dist[ys, xs], CAP)))
    c2 = float((U & ctx.sky).sum()) / max(1.0, U.sum())       # mesh dessine dans le ciel
    return c1 + 8.0 * c2


def run(cam, pert, M):
    c = json.load(open(MF.CAMS))[cam]; ctx = SkyCtx(cam)
    def f(th):
        st = {'xyz': c['xyz'], 'ypr': [c['ypr'][0] + th[0], c['ypr'][1] + th[1], c['ypr'][2] + th[2]], 'fov': [c['fov'][0] + th[3], c['fov'][1]]}
        return cost(ctx, mesh_union(ctx, st, M, cam))
    start = np.array(pert, float); best = (f(start), start)
    for dy in np.linspace(-0.8, 0.8, 9):
        for dp in np.linspace(-0.8, 0.8, 9):
            t = start + [dy, dp, 0, 0]; v = f(t)
            if v < best[0]: best = (v, t)
    r = minimize(f, best[1], method='Nelder-Mead', options={'xatol': 0.004, 'fatol': 0.001, 'maxiter': 250,
                 'initial_simplex': best[1] + np.array([[0, 0, 0, 0], [0.12, 0, 0, 0], [0, 0.12, 0, 0], [0, 0, 0.3, 0], [0, 0, 0, 0.4]])})
    return f(np.zeros(4)), f(start), r.fun, r.x


if __name__ == '__main__':
    M = json.load(open(MF.MESHES)); rng = np.random.default_rng(1)
    for cam in [a for a in sys.argv[1:] if not a.startswith('--')]:
        pert = [0.5 * rng.choice([-1, 1]), 0.4 * rng.choice([-1, 1]), 0.3 * rng.choice([-1, 1]), 0.8 * rng.choice([-1, 1])]
        c0, cs, cf, x = run(cam, pert, M)
        print('%-34s depart %s | cout vraie %.2f depart %.2f final %.2f | ecart final yaw %+.3f pitch %+.3f roll %+.3f fov %+.2f'
              % (cam[:34], [float(p) for p in pert], c0, cs, cf, *x), flush=True)
