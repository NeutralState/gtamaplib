#!/usr/bin/env python3
"""carve_missing.py — CANDIDATE FINDER for tall buildings missing from the 3D (2.5D space carving of the V16 lots). [CARVE-V2 2026-10-10]

RESULT: NOT a builder. Checked by eye, the "accepted" lots were phantoms or doubtful: the Bayside Ferris wheel and a jet-ski
rider classified as building by SegFormer, the Marine Stadium canopy, a leak frame's debug text, haze; Port Vice City A/B are
one viewpoint. The genuinely tall missing towers (lots 3101 118 m, 1957 96 m, 1954 86 m, 2719 85 m...) are seen from only 1-2
viewpoints, so their height is not measurable automatically. Use the list (docs/carve_missing.md) as a WHERE-TO-LOOK list for
clicks / identification, never as meshes. Third refutation of automatic sky-line heights (see the memory note).

Why: unmodelled towers steal the silhouette edges of their neighbours (Wells Fargo Center (S), The Palace, Met 1 vs the
Brickell camera): the global solver (MVS-V1) cannot go further until they exist. GTADB points are exhausted around them,
and an IRL->game warp is useless there (residuals 45-210 m: the game rearranges the city).
Refuted before: taking the sky line as a building's HEIGHT (silhouette-height scan, ~41/44 wrong) - a single view cannot tell
which lot the sky line belongs to, and the sky line is only an UPPER bound.
Method (2.5D visual hull over the V16 lots, existing meshes known):
  - candidate lots = V16 building footprints (150-60000 m2) not covered by an existing solid;
  - SKY rays (just above each column's sky boundary, padded by PAD px against pose errors) carve: every candidate lot they
    pass over gets h_max <= ray height there;
  - BUILDING rays (just below the boundary) must be stopped by something: if no existing solid explains them, the first
    candidate lot along the ray still allowed that high is a SUPPORT, with lower bound = ray height there.
  - only BUILDING pixels (ADE20K building/house/skyscraper) just below the sky line may require a support (CARVE-V2: wheels,
    people, planes, palms and HUD text made phantoms in V1);
  - a lot is a missing building if supported from >= MIN_CAMS distinct VIEWPOINTS (cameras < 50 m apart count once), its height (80th percentile of the supports) >= 30 m
    and within 20 % of its carved h_max.
Cameras: day frames with a pose-audit fit (|shift| <= 2.5 px, >= 4 judged meshes). SegFormer sky = ADE20K class 2.
Output: tools/generated/carve_missing.json + docs/carve_missing.md (candidate list). Nothing is ever written to the meshes.
Usage: PYTHONPATH=. python3 tools/carve_missing.py
"""
import json, os, sys, math
import numpy as np
import cv2

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import common
import mesh_solids as MS
import horizon_resect as HR

OUT = os.path.join(THIS, 'generated', 'carve_missing.json')
DOC = os.path.join(REPO, 'docs', 'carve_missing.md')
X0, X1, Y0, Y1, CELL = -1900.0, 2700.0, -2700.0, 3300.0, 2.0       # Vice City + Vice Beach
SKY, PAD, COLS, MIN_CAMS, TMAX = 2, 4.0, 640, 3, 7000.0
BUILDING = (1, 25, 48)        # ADE20K building, house, skyscraper: only these pixels may require a support (no wheels, people, planes, palms, HUD text)
VIEW_MERGE = 50.0             # cameras closer than this are ONE viewpoint (Port Vice City A/B)


def grid_xy(X, Y):
    i = ((X - X0) / CELL).astype(np.int64); j = ((Y1 - Y) / CELL).astype(np.int64)
    ok = (i >= 0) & (j >= 0) & (i < NX) & (j < NY)
    return i, j, ok


NX, NY = int((X1 - X0) / CELL), int((Y1 - Y0) / CELL)


def rasters():
    S = MS.build(); top = np.full((NY, NX), -1e3, np.float32)
    for so in S.values():
        for L in so['layers']:
            for p in L['polys']:
                q = np.c_[(np.array(p['outer'])[:, 0] - X0) / CELL, (Y1 - np.array(p['outer'])[:, 1]) / CELL].astype(np.int32)
                m = np.zeros((NY, NX), np.uint8); cv2.fillPoly(m, [q], 1); top[m > 0] = np.maximum(top[m > 0], L['z1'])
    F = json.load(open(os.path.join(REPO, 'gtamapdata', 'v16_footprints.json')))['polygons']
    lot = np.full((NY, NX), -1, np.int32); meta = {}
    for f in F:
        if not str(f.get('cat', '')).startswith('building') or not (150 <= f['area'] <= 60000): continue
        R = np.array(f['ring'], float)
        if R[:, 0].max() < X0 or R[:, 0].min() > X1 or R[:, 1].max() < Y0 or R[:, 1].min() > Y1: continue
        q = np.c_[(R[:, 0] - X0) / CELL, (Y1 - R[:, 1]) / CELL].astype(np.int32)
        m = np.zeros((NY, NX), np.uint8); cv2.fillPoly(m, [q], 1); cells = m > 0
        if cells.sum() == 0: continue
        if (top[cells] > -1e3).mean() > 0.3: continue                    # already (mostly) modelled
        lot[cells & (top <= -1e3)] = f['id']
        meta[f['id']] = {'area': f['area'], 'centroid': f['centroid'], 'ground': float(HR.ground(np.array([f['centroid'][0]]), np.array([f['centroid'][1]]))[0])}
    return top, lot, meta


def cameras():
    A = json.load(open(os.path.join(THIS, 'generated', 'pose_audit.json')))
    return [c for c, o in A.items() if o.get('fit') and abs(o['fit']['shift_px']) <= 2.5 and (o.get('n_judged') or 0) >= 4 and not o.get('night')]


def column_rays(cam):
    p = os.path.join(THIS, 'generated', 'seg_veg', cam.replace('/', '_') + '_cls.npy')
    if not os.path.exists(p): return None
    cls = np.load(p, mmap_mode='r'); c = common.get_cam(cam); W, H = c.size
    sy, sx = cls.shape[0] / H, cls.shape[1] / W; out = []
    for xf in np.linspace(0.5, W - 0.5, COLS):
        col = np.asarray(cls[:, int(xf * sx)]); nz = np.where(col != SKY)[0]
        if len(nz) == 0 or nz[0] < 3: continue                          # no sky / sky boundary at the very top
        ys = nz[0] / sy
        below = col[min(len(col) - 1, nz[0] + max(2, int(PAD * sy))):min(len(col), nz[0] + max(6, int(3 * PAD * sy)))]
        is_bld = len(below) > 0 and np.isin(below, BUILDING).mean() >= 0.6
        d_sky = np.array(c.get_pixel_direction(np.array([xf, ys - PAD], float)), float).ravel()
        d_bld = np.array(c.get_pixel_direction(np.array([xf, ys + PAD], float)), float).ravel()
        out.append((d_sky / np.linalg.norm(d_sky), d_bld / np.linalg.norm(d_bld) if is_bld else None))
    return np.array(c.xyz, float), out


TS = np.unique(np.r_[np.arange(15, 1000, 2.0), np.arange(1000, TMAX, 4.0)])


def march(o, d):
    P = o[None, :] + TS[:, None] * d[None, :]
    i, j, ok = grid_xy(P[:, 0], P[:, 1]); return P, i, j, ok


def main():
    top, lot, meta = rasters(); cams = cameras()
    print('candidate lots %d, cameras %d' % (len(meta), len(cams)), flush=True)
    hmax = {k: 1e9 for k in meta}; rays = {}
    for cam in cams:                                                     # pass 1: sky rays carve
        r = column_rays(cam)
        if not r: continue
        o, cols = r; rays[cam] = (o, cols)
        for d_sky, _ in cols:
            P, i, j, ok = march(o, d_sky)
            ids = np.where(ok, lot[np.clip(j, 0, NY - 1), np.clip(i, 0, NX - 1)], -1)
            for k in np.unique(ids[ids >= 0]):
                z = P[ids == k, 2].min() - meta[k]['ground']
                if z < hmax[k]: hmax[k] = z
    sup = {k: [] for k in meta}
    for cam, (o, cols) in rays.items():                                  # pass 2: building rays need a support
        for _, d_bld in cols:
            if d_bld is None: continue
            P, i, j, ok = march(o, d_bld)
            g = HR.ground(P[:, 0], P[:, 1])
            if (P[:, 2] <= g).any(): P, i, j, ok = P[:np.argmax(P[:, 2] <= g)], i[:np.argmax(P[:, 2] <= g)], j[:np.argmax(P[:, 2] <= g)], ok[:np.argmax(P[:, 2] <= g)]
            ti = np.where(ok, top[np.clip(j, 0, NY - 1), np.clip(i, 0, NX - 1)], -1e3)
            ids = np.where(ok, lot[np.clip(j, 0, NY - 1), np.clip(i, 0, NX - 1)], -1)
            for s in range(len(P)):
                if ti[s] >= P[s, 2]: break                                # an existing solid explains it
                k = ids[s]
                if k >= 0:
                    need = P[s, 2] - meta[k]['ground']
                    if need >= 25 and hmax[k] >= need - 3: sup[k].append((cam, float(need))); break
    rows = []
    for k, v in sup.items():
        if not v: continue
        cams_k = sorted({c for c, _ in v}); need = np.array([n for _, n in v])
        views = []                                                     # distinct viewpoints (Port Vice City A/B = one)
        for c_ in cams_k:
            o_ = rays[c_][0]
            if not any(np.linalg.norm(o_ - rays[w][0]) < VIEW_MERGE for w in views): views.append(c_)
        h = float(np.percentile(need, 80)); hm = hmax[k] if hmax[k] < 1e8 else None
        ok = len(views) >= MIN_CAMS and h >= 30 and (hm is None or hm <= 1.2 * h)
        rows.append({'lot': int(k), 'h': round(h, 1), 'h_max': None if hm is None else round(hm, 1), 'cams': cams_k, 'views': len(views), 'n_rays': len(v), 'accept': bool(ok),
                     'area': round(meta[k]['area']), 'centroid': [round(x, 1) for x in meta[k]['centroid']], 'ground': round(meta[k]['ground'], 1)})
    rows.sort(key=lambda r: (not r['accept'], -r['h']))
    json.dump(rows, open(OUT, 'w'), indent=1)
    L = ['# Missing tall buildings (CARVE-V1)', '', '2.5D visual hull of the unmodelled V16 lots from the sky lines of %d day cameras (existing meshes known). '
         'Accepted = supported in >= %d cameras, height >= 30 m, within 20 %% of the carved maximum. Nothing applied.' % (len(rays), MIN_CAMS), '',
         '| V16 lot | centre | area m2 | height (m) | carved max | cameras | views | rays | accepted |', '|---|---|---|---|---|---|---|---|---|']
    for r in rows[:150]:
        L.append('| %d | %s | %d | %.0f | %s | %d | %d | %d | %s |' % (r['lot'], r['centroid'], r['area'], r['h'], r['h_max'], len(r['cams']), r['views'], r['n_rays'], 'yes' if r['accept'] else ''))
    open(DOC, 'w').write('\n'.join(L) + '\n')
    print('lots with support %d, accepted %d -> %s' % (len(rows), sum(r['accept'] for r in rows), OUT))


if __name__ == '__main__':
    main()
