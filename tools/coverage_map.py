#!/usr/bin/env python3
"""coverage_map.py — what the posed cameras really see, and how precisely. [COVERAGE-V2 2026-10-19]

Alexandre: "une carte de couverture: ce qui est vu, et avec quelle precision" (for him and the other mappers: where the
evidence is solid, where it is thin, where to look next). Replaces the naive Map-view "Coverage" layer (1.5 km wedges,
no occlusion) with a ray-cast one:
  - surface = game heightmap (gtamapdata/heightmap, via horizon_resect.ground) + building volumes (tools/mesh_solids.py)
    rasterized at 4 m; sea level 0; buildings without a mesh are NOT in the surface (they do not occlude);
  - every posed camera (xyz + ypr + hfov, z < 1500 m) casts a 160 x 90 grid of rays through its image; each ray stops at
    the first surface hit (<= 4 km); neighbouring hits form quads, rasterized on a 10 m world grid;
  - precision of a seen cell (1 sigma, metres, ESTIMATED model): position sigma (+) range x angular sigma (+) the pixel
    footprint, the along-ray part divided by sin(grazing angle). Pose sigmas come from tools/generated/covariances.json
    when the camera has one, else from its confidence tier (DEFAULT_SIGMA below).
Output (served by the /threejs/ static route, no server restart; ignored by git):
  tools/threejs/_coverage.png      R = number of cameras seeing the cell (cap 255), G = precision code
                                   (sigma = 0.25 * 1.045**G m, G = 0: not seen), B = 0
  tools/threejs/_coverage_cam.png  R, G = index (hi, lo) of the camera with the best precision (65535 = none)
  tools/threejs/_coverage.json     grid, camera list, model parameters, summary
Usage: PYTHONPATH=. python3 tools/coverage_map.py [--rays 160x90] [--only "Cam name"]
"""
import json, math, os, sys, time, warnings
import numpy as np, cv2
warnings.filterwarnings("ignore", "Mean of empty slice")
from scipy.spatial.transform import Rotation as Rot

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
from horizon_resect import ground
import mesh_solids

GRID = dict(x0=-9600.0, y0=-8800.0, x1=3200.0, y1=12400.0, r=10.0)      # same extent as the Map-view layer
SURF_R, TMAX = 4.0, 4000.0
DEFAULT_SIGMA = {   # tier -> (position sigma m, angle sigma deg): medians of covariances.json per tier, rounded up
    'anchor': (1.0, 0.03), 'high': (3.5, 0.05), 'medium': (12.0, 0.5), 'low': (15.0, 0.6), 'unverified': (30.0, 1.5), None: (30.0, 1.5)}
G_BASE, G_STEP = 0.25, 1.045
SEA_Z, SIG_MAX = 0.3, 300.0          # hits on the sea surface are dropped; cells worse than 300 m (1 sigma) count as not seen


def surface():
    gx = np.arange(GRID['x0'], GRID['x1'], SURF_R) + SURF_R / 2; gy = np.arange(GRID['y1'], GRID['y0'], -SURF_R) - SURF_R / 2
    X, Y = np.meshgrid(gx, gy); S = np.maximum(ground(X, Y), 0.0).astype(np.float32)
    polys = []
    for so in mesh_solids.cached().values():
        for L in so['layers']:
            for p in L['polys']: polys.append((L['z1'], p['outer']))
    polys.sort(key=lambda a: a[0])
    B = np.zeros_like(S)
    for z1, outer in polys:
        q = np.array([[(x - GRID['x0']) / SURF_R, (GRID['y1'] - y) / SURF_R] for x, y in outer], np.float32)
        cv2.fillPoly(B, [np.round(q * 4).astype(np.int32)], float(z1), lineType=cv2.LINE_8, shift=2)
    return np.maximum(S, B), X.shape


def lookup(S, P):
    i = ((GRID['y1'] - P[:, 1]) / SURF_R).astype(int); j = ((P[:, 0] - GRID['x0']) / SURF_R).astype(int)
    ok = (i >= 0) & (j >= 0) & (i < S.shape[0]) & (j < S.shape[1])
    z = np.full(len(P), -1e9, np.float32); z[ok] = S[i[ok], j[ok]]; return z


def cast(S, xyz, ypr, hfov, size, nu, nv):
    W, H = size; Rm = Rot.from_euler('ZXY', ypr, degrees=True).as_matrix(); th = math.tan(math.radians(hfov) / 2); tv = th * H / W
    u, v = np.meshgrid((np.arange(nu) + 0.5) / nu, (np.arange(nv) + 0.5) / nv)
    D = np.stack([(u * 2 - 1) * th, np.ones_like(u), (1 - v * 2) * tv], -1).reshape(-1, 3) @ Rm.T
    D /= np.linalg.norm(D, axis=1)[:, None]
    o = np.asarray(xyz, float); n = len(D); T = np.full(n, np.nan); alive = np.arange(n); t, tp = 0.5, 0.0
    tprev = np.zeros(n)
    while t < TMAX and len(alive):
        P = o + D[alive] * t; hit = P[:, 2] <= lookup(S, P)
        if hit.any():
            idx = alive[hit]; a, b = tprev[idx], np.full(len(idx), t)
            for _ in range(7):
                m = (a + b) / 2; Q = o + D[idx] * m[:, None]; bl = Q[:, 2] <= lookup(S, Q); b = np.where(bl, m, b); a = np.where(bl, a, m)
            T[idx] = b; alive = alive[~hit]
        tprev[alive] = t; t = t * 1.012 + 0.4
    return D.reshape(nv, nu, 3), T.reshape(nv, nu)


def main():
    nu, nv = map(int, (sys.argv[sys.argv.index('--rays') + 1] if '--rays' in sys.argv else '160x90').split('x'))
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    C = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    TI = json.load(open(os.path.join(THIS, 'generated', 'confidence_tiers.json')))['cameras']
    CV = json.load(open(os.path.join(THIS, 'generated', 'covariances.json')))['cams']
    t0 = time.time(); S, _ = surface(); print('surface %s in %.0f s' % (S.shape, time.time() - t0))
    gw, gh = int((GRID['x1'] - GRID['x0']) / GRID['r']), int((GRID['y1'] - GRID['y0']) / GRID['r'])
    count = np.zeros((gh, gw), np.uint16); best = np.full((gh, gw), np.inf, np.float32); bcam = np.full((gh, gw), 65535, np.uint16)
    names, used = [], []
    for name, c in C.items():
        if only and name != only: continue
        fov = (c.get('fov') or [None])[0]
        if not c.get('xyz') or not c.get('ypr') or not fov or c['xyz'][2] > 1500: continue
        tier = (TI.get(name) or {}).get('tier')
        if name in CV: sp, sa = CV[name]['sigma_pos_m'], max(CV[name]['sigma_ypr_deg'][:2]); src = 'covariance'
        else: (sp, sa), src = DEFAULT_SIGMA.get(tier, DEFAULT_SIGMA[None]), 'tier default'
        D, T = cast(S, c['xyz'], c['ypr'], fov, c.get('size') or [1920, 1080], nu, nv)
        P = np.asarray(c['xyz'])[None, None, :] + D * T[..., None]
        W = (c.get('size') or [1920, 1080])[0]
        foot = T * 2 * math.tan(math.radians(fov) / 2) / W                       # metres per image pixel at the hit
        ang = T * math.radians(sa)
        sing = np.clip(-D[..., 2], 0.05, 1.0)                                   # grazing angle on a level surface
        sig = np.sqrt(sp ** 2 + ang ** 2 + foot ** 2 + ((ang ** 2 + foot ** 2) / sing ** 2)).astype(np.float32)
        sea = np.isfinite(T) & (P[..., 2] <= SEA_Z)                            # open water: nothing to map there
        T = np.where(sea | (sig > SIG_MAX), np.nan, T)
        # quads of 4 neighbouring hits (no depth jump) -> grid cells
        ok = np.isfinite(T)
        q = ok[:-1, :-1] & ok[1:, :-1] & ok[1:, 1:] & ok[:-1, 1:]
        Tq = np.stack([T[:-1, :-1], T[1:, :-1], T[1:, 1:], T[:-1, 1:]], -1)
        q &= (np.nanmax(Tq, -1) / np.maximum(np.nanmin(Tq, -1), 1e-3)) < 1.6
        if not q.any(): continue
        G = np.stack([(P[..., 0] - GRID['x0']) / GRID['r'], (GRID['y1'] - P[..., 1]) / GRID['r']], -1)
        quads = np.stack([G[:-1, :-1], G[1:, :-1], G[1:, 1:], G[:-1, 1:]], -2)[q]           # (n, 4, 2)
        sq = np.nanmean(np.stack([sig[:-1, :-1], sig[1:, :-1], sig[1:, 1:], sig[:-1, 1:]], -1), -1)[q]
        lo = np.floor(quads.reshape(-1, 2).min(0)).astype(int) - 1; hi = np.ceil(quads.reshape(-1, 2).max(0)).astype(int) + 2
        lo = np.maximum(lo, 0); hi = np.minimum(hi, [gw, gh])
        if (hi <= lo).any(): continue
        sub = np.full((hi[1] - lo[1], hi[0] - lo[0]), np.inf, np.float32)
        codes = np.clip(np.round(np.log(np.maximum(sq, G_BASE) / G_BASE) / math.log(G_STEP)), 1, 255)
        for g in np.unique(codes)[::-1]:                                       # worst first: the best precision ends on top
            sel = quads[codes == g] - lo
            m = np.zeros(sub.shape, np.uint8); cv2.fillPoly(m, list(np.round(sel * 4).astype(np.int32)), 1, cv2.LINE_8, shift=2)
            for pt in np.round(sel.reshape(-1, 2)).astype(int):                  # thin quads: keep their corners
                if 0 <= pt[1] < m.shape[0] and 0 <= pt[0] < m.shape[1]: m[pt[1], pt[0]] = 1
            sub[m > 0] = np.minimum(sub[m > 0], G_BASE * G_STEP ** g)
        seen = np.isfinite(sub); ys, xs = np.where(seen); ys = ys + lo[1]; xs = xs + lo[0]
        k = len(names); names.append(name); count[ys, xs] += 1
        better = sub[seen] < best[ys, xs]; best[ys[better], xs[better]] = sub[seen][better]; bcam[ys[better], xs[better]] = k
        used.append(dict(name=name, id=c.get('id'), tier=tier, sigma_pos_m=round(sp, 2), sigma_ang_deg=round(sa, 3), sigma_src=src,
                         cells=int(seen.sum()), area_km2=round(seen.sum() * GRID['r'] ** 2 / 1e6, 3)))
        if len(names) % 25 == 0: print('%d cams, %.0f s' % (len(names), time.time() - t0))
    gcode = np.where(np.isfinite(best), np.clip(np.round(np.log(np.maximum(best, G_BASE) / G_BASE) / math.log(G_STEP)), 1, 255), 0).astype(np.uint8)
    img = np.dstack([np.zeros_like(gcode), gcode, np.minimum(count, 255).astype(np.uint8)])      # BGR for cv2: R=count, G=code
    out = os.path.join(THIS, 'threejs')
    cv2.imwrite(os.path.join(out, '_coverage.png'), img)
    cv2.imwrite(os.path.join(out, '_coverage_cam.png'), np.dstack([np.zeros_like(gcode), (bcam & 255).astype(np.uint8), (bcam >> 8).astype(np.uint8)]))
    seen = count > 0; land = ground(*np.meshgrid(np.arange(GRID['x0'], GRID['x1'], GRID['r']) + 5, np.arange(GRID['y1'], GRID['y0'], -GRID['r']) - 5)) > 0.5
    summ = dict(cameras=len(names), seen_km2=round(seen.sum() * 1e-4, 2), land_km2=round(land.sum() * 1e-4, 2), land_seen_km2=round((seen & land).sum() * 1e-4, 2),
                land_seen_under_5m_km2=round((seen & land & (best <= 5)).sum() * 1e-4, 2), land_seen_under_20m_km2=round((seen & land & (best <= 20)).sum() * 1e-4, 2))
    json.dump(dict(_doc=__doc__.split('\n')[0], grid=GRID, png='_coverage.png', cam_png='_coverage_cam.png', sigma_code=dict(base=G_BASE, step=G_STEP),
                   rays=[nu, nv], tmax_m=TMAX, sea_z=SEA_Z, sigma_max_m=SIG_MAX, default_sigma={str(k): v for k, v in DEFAULT_SIGMA.items()}, summary=summ, cameras=used,
                   generated=time.strftime('%Y-%m-%d %H:%M')), open(os.path.join(out, '_coverage.json'), 'w'), indent=0)
    print('done in %.0f s' % (time.time() - t0)); print(json.dumps(summ))


if __name__ == '__main__':
    main()
