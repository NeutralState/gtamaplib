#!/usr/bin/env python3
"""mvs_solve.py — global multi-view solver: cameras + mesh footprints/heights together. [MVS-V1 2026-10-09]

Why: every fix so far was local (one camera against a few meshes, one mesh against a few cameras) and the pieces can
disagree (Brickell vs Met 1, 2026-10-09: no camera pose fitted both towers). This solves everything at once.
Unknowns (deltas from the current state, with priors):
  - every non-SOLVED, non-HUD-locked camera (leak debug poses are exact and frozen): dx dy dz (m), dyaw dpitch droll (deg), dfov (deg, active fov slot). Player-locked cameras
    (a 'player' position, e.g. the 2022 debug HUD) keep their position (sigma 0.5 m). SOLVED cameras are FIXED.
  - every mesh seen in >= 2 edge observations: plan translation tx ty (m) and height scale sh (top = ground + (1+sh) h).
    Priors: measured meshes (notes MEASURED/MESURE/LM/triangul) sigma 3 m / 0.03, V16-IRL-estimated ones 6 m / 0.12;
    a triangulated landmark on the roof pins the plan (sigma 0.3 m, ROOF-ANCHOR: a direct measurement of the
    building position; edges alone dragged Wells Fargo Center (S) 34 m against sigma 2 m).
Observations:
  - pose-audit edges (tools/generated/pose_audit.json: left/right/top silhouette residual d = frame - model, px at
    1280 wide, median over rows; kept when mad <= 3 and n >= 6, day frames only), sigma = 1 + mad px. A parameter
    change moves the model edge by the change of the projected extreme of the mesh (min x / max x / min y).
  - landmark markings (pixels.json) of the free cameras against the triangulated landmarks (fixed), sigma 1.5 px at
    1280: they anchor the network.
Robust least squares (soft L1, f_scale 3 sigma), steps scaled by the prior sigmas, finite-difference Jacobian blocks;
landmark residuals as (du, dv).
Output: tools/generated/mvs_solution.json, docs/mvs_report.md. Nothing is written to the data unless --apply (guarded,
see apply()).
Usage: PYTHONPATH=. python3 tools/mvs_solve.py [--apply]
"""
import json, os, sys, copy, math, re, time
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import common
import gtamapdata as md
import mesh_solids as MS
import mesh_pose_audit as A
from leak_cam_audit import is_triangulation_trusted   # HUD-locked leak cameras: exact poses, frozen (invariants LEAK)

OUT = os.path.join(THIS, 'generated', 'mvs_solution.json')
DOC = os.path.join(REPO, 'docs', 'mvs_report.md')
WORK = A.WORK
CS = np.array([15.0, 15.0, 6.0, 1.0, 1.0, 0.5, 1.5])          # camera prior sigmas: x y z yaw pitch roll fov
CS_PLAYER = np.array([0.5, 0.5, 0.5, 1.0, 1.0, 0.5, 1.5])
CD = np.array([0.05, 0.05, 0.05, 0.005, 0.005, 0.005, 0.005])  # finite-difference steps
MD = np.array([0.05, 0.05, 0.001])
MIN_DEPTH, MIN_LM_DIST, BROKEN_SIGMA = 10.0, 25.0, 25.0
SIG_LM = 1.5
MEASURED = re.compile(r'MEASURED|MESURE|\bLMs?\b|triangul|measured', re.I)


def fov_slot(c):
    fv = c.get('fov')
    if isinstance(fv, (list, tuple)):
        return (0, float(fv[0])) if fv[0] is not None else (1, float(fv[1]))
    return 0, float(fv)


def state(c0, p):
    st = {'xyz': [c0['xyz'][k] + p[k] for k in range(3)], 'ypr': [c0['ypr'][k] + p[3 + k] for k in range(3)]}
    i, f = fov_slot(c0); fv = list(c0['fov']) if isinstance(c0['fov'], (list, tuple)) else [c0['fov'], None]
    fv[i] = f + p[6]; st['fov'] = fv
    return st


def basis(name, st):
    cm = common.get_cam(name, st); B = A.basis(cm)
    return B


def proj(B, X):
    o, f, r, u, fpx, W, H = B; s = WORK / W
    D = X - o; z = D @ f
    ok = z > 1.0
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.c_[(W / 2 + fpx * (D @ r) / z) * s, (H / 2 - fpx * (D @ u) / z) * s], ok


def mesh_pts(so):
    P = [[q[0], q[1], L[z]] for L in so['layers'] for p in L['polys'] for q in p['outer'] for z in ('z0', 'z1')]
    return np.array(P, float), float(so['zmin'])


def moved(P, g, q):
    X = P.copy(); X[:, 0] += q[0]; X[:, 1] += q[1]; X[:, 2] = g + (X[:, 2] - g) * (1 + q[2]); return X


def extreme(B, X, t):
    uv, ok = proj(B, X)
    if ok.sum() < 2: return np.nan
    uv = uv[ok]
    return uv[:, 0].min() if t == 'L' else (uv[:, 0].max() if t == 'R' else uv[:, 1].min())


def load():
    C = json.load(open(A.CAMS)); AUD = json.load(open(A.OUTJ)); M = json.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')))
    S = MS.build(); solids = {n: mesh_pts(so) for n, so in S.items() if so['layers']}
    edges = []
    for cam, o in AUD.items():
        if cam not in C or o.get('night'): continue
        for n, m in o['meshes'].items():
            if n not in solids or m.get('verdict') == 'occluded': continue
            for t in ('L', 'R', 'T'):
                e = m['edges'].get(t)
                if e and e['mad'] <= 3 and e['n'] >= 6: edges.append((cam, n, t, float(e['d']), 1.0 + float(e['mad'])))
    lms = []
    for cam, obs in md.pixels.items():
        if cam not in C: continue
        for lm, px in (obs or {}).items():
            if px is None or common.is_excluded_marking(cam, lm) or md.landmarks.get(lm) is None: continue
            lms.append((cam, lm, np.array(md.landmarks[lm], float), np.array(px[:2], float)))
    return C, M, solids, edges, lms


def main():
    t0 = time.time()
    C, M, solids, edges, lms = load()
    ecount = {}
    for cam, n, *_ in edges: ecount.setdefault(n, set()).add(cam)
    cams = sorted({e[0] for e in edges} | {l[0] for l in lms})
    free_c = [c for c in cams if not C[c].get('pose_verified') and C[c].get('constraint_class') != 'X_excluded' and not is_triangulation_trusted(c)
              and (sum(e[0] == c for e in edges) >= 3 or sum(l[0] == c for l in lms) >= 3)]
    free_m = [n for n in solids if len([e for e in edges if e[1] == n]) >= 2]
    ci = {c: k for k, c in enumerate(free_c)}; mi = {n: k for k, n in enumerate(free_m)}
    nc, nm = len(free_c), len(free_m); NP = 7 * nc + 3 * nm
    lms = [l for l in lms if l[0] in ci]                               # fixed cameras: constant LM residuals, dropped
    print('free cameras %d, free meshes %d, edge obs %d, LM obs %d, params %d' % (nc, nm, len(edges), len(lms), NP), flush=True)
    csig = np.array([CS_PLAYER if C[c].get('player') else CS for c in free_c]) if nc else np.zeros((0, 7))
    from horizon_resect import ground as _gnd                         # MVS-GUARD: street-level (eye-height) cameras keep their height
    for c in free_c:
        h = C[c]['xyz'][2] - float(_gnd(*C[c]['xyz'][:2]))
        if 1.2 <= h <= 2.2: csig[ci[c], 2] = 0.3
    # sibling shots (< 5 m apart: same terrace / same spot, e.g. Speaking with Brian at Effluvia (1)-(3)) keep their place
    for c in free_c:
        if any(o != c and np.linalg.norm(np.array(C[o]['xyz'], float) - np.array(C[c]['xyz'], float)) < 5.0 for o in C): csig[ci[c], :3] = np.minimum(csig[ci[c], :3], 2.0)
    msig = np.array([[3.0, 3.0, 0.03] if MEASURED.search(M.get(n, {}).get('note', '')) else [6.0, 6.0, 0.12] for n in free_m]) if nm else np.zeros((0, 3))
    # ROOF-ANCHOR: a triangulated landmark on the mesh roof (inside the top footprint, within 3 m of the top) pins the plan
    # (Wells Fargo Center (S), 2026-10-09: the solver wanted +41 m onto a road while its roof landmark sat 16.6 m inside)
    # -> near-hard (sigma 0.3 m); the height scale stays free
    import cv2
    LMX = np.array([v for v in md.landmarks.values() if v is not None], float); anchored = set()
    for n in free_m:
        Pm, g = solids[n]; zt = Pm[:, 2].max(); top = Pm[np.isclose(Pm[:, 2], zt)][:, :2]
        if len(top) < 3: continue
        hull = cv2.convexHull(top.astype(np.float32)); near = LMX[np.abs(LMX[:, 2] - zt) < 3.0]
        if any(cv2.pointPolygonTest(hull, (float(x), float(y)), False) >= 0 for x, y, _ in near):
            msig[mi[n], :2] = 0.3; anchored.add(n)
    B0 = {c: basis(c, C[c]) for c in cams}
    def edge_ok(c, n, t):                                              # whole mesh in front (>= MIN_DEPTH) and its extreme in frame
        B = B0[c]; o, f = B[0], B[1]; X = solids[n][0]
        if ((X - o) @ f).min() < MIN_DEPTH: return np.nan
        e = extreme(B, X, t); Hs = B[6] * WORK / B[5]
        lim = WORK if t in 'LR' else Hs
        return e if 0 <= e <= lim else np.nan
    E0 = np.array([edge_ok(c, n, t) for c, n, t, d, s in edges])
    keep = np.isfinite(E0); edges = [e for e, k in zip(edges, keep) if k]; E0 = E0[keep]
    # landmarks: not too close to their camera (non-linear), and not from broken cameras (> BROKEN_SIGMA at start)
    lms = [l for l in lms if np.hypot(*(l[2][:2] - np.array(C[l[0]]['xyz'][:2]))) >= MIN_LM_DIST]
    def lm_sig(l):
        uv, ok = proj(B0[l[0]], l[2][None, :]); s = WORK / B0[l[0]][5]
        return float(np.hypot(*(uv[0] - l[3] * s))) / SIG_LM if ok[0] else 1e3
    per = {}
    for l in lms: per.setdefault(l[0], []).append(lm_sig(l))
    broken = sorted(c for c, v in per.items() if np.sqrt(np.mean(np.square(v))) > BROKEN_SIGMA)
    lms = [l for l in lms if l[0] not in broken]
    print('edges kept %d, LM kept %d, broken cameras (LMs dropped): %s' % (len(edges), len(lms), broken), flush=True)

    def unpack(x):
        P = x[:7 * nc].reshape(nc, 7) if nc else np.zeros((0, 7)); Q = x[7 * nc:].reshape(nm, 3) if nm else np.zeros((0, 3)); return P, Q

    def cam_B(c, P, cache):
        if c not in ci: return B0[c]
        if c not in cache: cache[c] = basis(c, state(C[c], P[ci[c]]))
        return cache[c]

    def r_edge(k, Bc, q):
        c, n, t, d, s = edges[k]; Pm, g = solids[n]
        X = moved(Pm, g, q) if q is not None else Pm
        return (d - (extreme(Bc, X, t) - E0[k])) / s

    def r_lm(k, Bc):                                                   # (du, dv) / sigma: the direction matters for the solver
        c, lm, X, px = lms[k]; uv, ok = proj(Bc, X[None, :])
        if not ok[0]: return np.array([50.0, 50.0])
        s = WORK / Bc[5]
        return (uv[0] - px * s) / SIG_LM

    def residuals(x):
        P, Q = unpack(x); cache = {}; R = []
        for k, (c, n, t, d, s) in enumerate(edges):
            v = r_edge(k, cam_B(c, P, cache), Q[mi[n]] if n in mi else None); R.append(v if np.isfinite(v) else 0.0)
        for k, (c, *_r) in enumerate(lms): R.extend(r_lm(k, cam_B(c, P, cache)))
        R.extend((P / csig).ravel()); R.extend((Q / msig).ravel())
        return np.array(R, float)

    rows_c = {c: [] for c in free_c}; rows_m = {n: [] for n in free_m}
    for k, (c, n, *_r) in enumerate(edges):
        if c in ci: rows_c[c].append(('e', k))
        if n in mi: rows_m[n].append(k)
    for k, (c, *_r) in enumerate(lms): rows_c[c].append(('l', k))
    ne, nl = len(edges), 2 * len(lms)

    def jac(x):
        P, Q = unpack(x); base = residuals(x); J = lil_matrix((len(base), NP))
        cache = {}
        for c in free_c:
            j0 = 7 * ci[c]
            for a in range(7):
                P2 = P.copy(); P2[ci[c], a] += CD[a]; Bc = basis(c, state(C[c], P2[ci[c]]))
                for kind, k in rows_c[c]:
                    if kind == 'e':
                        cc, n, *_r = edges[k]; v = r_edge(k, Bc, Q[mi[n]] if n in mi else None)
                        if np.isfinite(v): J[k, j0 + a] = (v - base[k]) / CD[a]
                    else:
                        dv = (r_lm(k, Bc) - base[ne + 2 * k:ne + 2 * k + 2]) / CD[a]
                        J[ne + 2 * k, j0 + a] = dv[0]; J[ne + 2 * k + 1, j0 + a] = dv[1]
                J[ne + nl + j0 + a, j0 + a] = 1.0 / csig[ci[c], a]
        for n in free_m:
            j0 = 7 * nc + 3 * mi[n]
            for a in range(3):
                q = Q[mi[n]].copy(); q[a] += MD[a]
                for k in rows_m[n]:
                    c = edges[k][0]; v = r_edge(k, cam_B(c, P, cache), q)
                    if np.isfinite(v): J[k, j0 + a] = (v - base[k]) / MD[a]
                J[ne + nl + j0 + a, j0 + a] = 1.0 / msig[mi[n], a]
        return J.tocsr()

    x0 = np.zeros(NP); r0 = residuals(x0)
    if '--checkjac' in sys.argv:
        J = jac(x0); rs = np.random.RandomState(0)
        for trial in range(3):
            v = rs.randn(NP) * np.r_[csig.ravel(), msig.ravel()] * 0.05
            fd = (residuals(x0 + v) - r0); lin = J @ v
            err = np.abs(fd - lin); k = np.argsort(-err)[:5]
            print('trial', trial, '|fd| %.3f |lin| %.3f |err| %.3f' % (np.linalg.norm(fd), np.linalg.norm(lin), np.linalg.norm(fd - lin)), 'worst rows', [(int(i), round(float(fd[i]), 2), round(float(lin[i]), 2)) for i in k])
        return
    xs = np.r_[csig.ravel(), msig.ravel()]                              # steps scaled by the prior sigmas (m and deg mixed)
    res = least_squares(residuals, x0, jac=jac, loss='soft_l1', f_scale=3.0, tr_solver='lsmr', x_scale=xs, max_nfev=120, xtol=1e-10, ftol=1e-6, verbose=1)
    x = res.x; r1 = residuals(x); P, Q = unpack(x)
    def stats(r):
        e, l = r[:ne], r[ne:ne + nl]
        return {'edge_rms_sigma': round(float(np.sqrt(np.mean(e ** 2))), 3), 'edge_med_abs': round(float(np.median(np.abs(e))), 3),
                'lm_rms_sigma': round(float(np.sqrt(np.mean(l ** 2))), 3) if nl else None}
    out = {'stats_before': stats(r0), 'stats_after': stats(r1), 'cams': {}, 'meshes': {}, 'n_edges': ne, 'n_lms': nl // 2, 'broken_cams': broken, 'secs': round(time.time() - t0)}
    for c in free_c:
        p = P[ci[c]]; k_e = [k for kind, k in rows_c[c] if kind == 'e']; k_l = [k for kind, k in rows_c[c] if kind == 'l']
        k_l2 = [j for k in k_l for j in (2 * k, 2 * k + 1)]
        out['cams'][c] = {'delta': [round(float(v), 3) for v in p], 'z_score': round(float(np.sqrt(np.mean((p / csig[ci[c]]) ** 2))), 2),
                          'edges': len(k_e), 'lms': len(k_l),
                          'edge_rms_before': round(float(np.sqrt(np.mean(r0[k_e] ** 2))), 2) if k_e else None, 'edge_rms_after': round(float(np.sqrt(np.mean(r1[k_e] ** 2))), 2) if k_e else None,
                          'lm_rms_before': round(float(np.sqrt(np.mean(r0[[ne + j for j in k_l2]] ** 2))), 2) if k_l else None, 'lm_rms_after': round(float(np.sqrt(np.mean(r1[[ne + j for j in k_l2]] ** 2))), 2) if k_l else None}
    for n in free_m:
        q = Q[mi[n]]; ks = rows_m[n]
        out['meshes'][n] = {'delta': [round(float(v), 3) for v in q], 'cams': sorted({edges[k][0] for k in ks}), 'edges': len(ks),
                            'edge_rms_before': round(float(np.sqrt(np.mean(r0[ks] ** 2))), 2), 'edge_rms_after': round(float(np.sqrt(np.mean(r1[ks] ** 2))), 2),
                            'prior': ('roof-anchored ' if n in anchored else '') + ('measured' if msig[mi[n], 2] < 0.05 else 'estimated')}
    json.dump(out, open(OUT, 'w'), indent=1)
    report(out)
    print(json.dumps({k: out[k] for k in ('stats_before', 'stats_after', 'n_edges', 'n_lms', 'secs')}))


def report(out):
    L = ['# Global multi-view solve (MVS-V1)', '',
         'Cameras (non-SOLVED) and mesh footprints/heights solved together against the pose-audit edges of all day frames and the landmark markings. '
         'Residuals in sigma units. Nothing applied unless guarded --apply.', '',
         '- before: %s' % out['stats_before'], '- after: %s' % out['stats_after'], '',
         '## Cameras (largest changes first)', '', '| Camera | dx dy dz (m) | dyaw dpitch droll dfov (deg) | edges | LMs | edge rms | LM rms |', '|---|---|---|---|---|---|---|']
    for c, v in sorted(out['cams'].items(), key=lambda kv: -kv[1]['z_score'])[:80]:
        d = v['delta']
        L.append('| %s | %+.1f %+.1f %+.1f | %+.2f %+.2f %+.2f %+.2f | %d | %d | %s -> %s | %s -> %s |' % (c, *d[:3], *d[3:], v['edges'], v['lms'], v['edge_rms_before'], v['edge_rms_after'], v['lm_rms_before'], v['lm_rms_after']))
    L += ['', '## Meshes (largest changes first)', '', '| Mesh | tx ty (m) | height scale | prior | cams | edge rms |', '|---|---|---|---|---|---|']
    for n, v in sorted(out['meshes'].items(), key=lambda kv: -(abs(kv[1]['delta'][0]) + abs(kv[1]['delta'][1]) + 100 * abs(kv[1]['delta'][2])))[:120]:
        d = v['delta']
        L.append('| %s | %+.1f %+.1f | %+.3f | %s | %d | %s -> %s |' % (n, d[0], d[1], d[2], v['prior'], len(v['cams']), v['edge_rms_before'], v['edge_rms_after']))
    open(DOC, 'w').write('\n'.join(L) + '\n')


# ROADS-GT (Alexandre 2026-10-09): roads are ground truth (the 2022 leak map; V16 roads match it) - a mesh plan may never be
# moved onto a road. Footprint = convex hull of the mesh's lowest vertices; overlap = share of its area within a V16 road
# stroke (road / hwy / small, at their width).
_ROADSEG = None
def _roads():
    global _ROADSEG
    if _ROADSEG is None:
        R = json.load(open(os.path.join(THIS, 'threejs', '_v16_roads.json'))); A_, B_, W_ = [], [], []
        for cl in ('road', 'hwy', 'small'):
            for s_ in R[cl]:
                Q = np.array(s_['p'], float)[:, :2]
                for a, b in zip(Q[:-1], Q[1:]): A_.append(a); B_.append(b); W_.append(s_['w'] / 2)
        _ROADSEG = (np.array(A_), np.array(B_), np.array(W_))
    return _ROADSEG


def footprint(E):
    import cv2
    E = np.asarray(E, float); z = E[:, :, 2]; low = E[np.isclose(z.min(1), z.min())][:, :, :2].reshape(-1, 2)
    return cv2.convexHull(low.astype(np.float32)).reshape(-1, 2) if len(low) >= 3 else None


def road_overlap(poly, step=2.0):
    import cv2
    if poly is None: return 0.0
    SA, SB, SW = _roads(); x0, y0 = poly.min(0); x1, y1 = poly.max(0)
    pts = np.array([(x, y) for x in np.arange(x0, x1, step) for y in np.arange(y0, y1, step)
                    if cv2.pointPolygonTest(poly.reshape(-1, 1, 2).astype(np.float32), (float(x), float(y)), False) >= 0])
    if len(pts) == 0: return 0.0
    c = poly.mean(0); near = np.where(np.minimum(np.hypot(*(SA - c).T), np.hypot(*(SB - c).T)) < np.hypot(*(poly.max(0) - poly.min(0))) + 60)[0]
    on = np.zeros(len(pts), bool)
    for i in near:
        a, b, w = SA[i], SB[i], SW[i]; ab = b - a; L2 = ab @ ab
        if L2 < 1e-6: continue
        t = np.clip(((pts - a) @ ab) / L2, 0, 1); on |= np.hypot(*(pts - (a + t[:, None] * ab)).T) < w
    return float(on.mean())


def apply():
    """guarded application of tools/generated/mvs_solution.json (backups first; SOLVED cameras are never in the solution).
    Cameras: canonical landmark RMS (common.cam_rms, arcmin) must not rise > 5 %, edges must improve, |dxy| <= 40 m,
    |dz| <= 20 m; without landmarks: >= 8 edges and >= 30 % edge gain. Skips negligible changes (z-score < 0.15).
    MVS-GUARD (2026-10-10): never below the ground; street-level cameras keep their eye height; sibling shots (< 5 m apart)
    stay together (and get a 2 m position prior in the solve); cumulative drift from _mvs_origin <= 20 m without
    landmarks (40 m if >= 20 edges improve >= 50 %) / 40 m with landmarks.
    Meshes: >= 3 cameras, >= 25 % edge gain, |t| <= 25 m, |sh| <= 0.15, and never onto a road (ROADS-GT: the road
    overlap of the footprint may not grow). Everything else -> review list in the report."""
    import shutil
    sol = json.load(open(OUT)); C = json.load(open(A.CAMS)); MP = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json'); M = json.load(open(MP))
    shutil.copy(A.CAMS, A.CAMS + '.bak_mvs_1009'); shutil.copy(MP, MP + '.bak_mvs_1009')
    acc_c, rej_c, acc_m, rej_m = [], [], [], []
    from horizon_resect import ground as _gnd
    # MVS-GUARD 2026-10-10: siblings = cameras shot within 5 m of each other (same scene) must stay within 5 m of each other;
    # origin = position before the first MVS move (stored as _mvs_origin): cumulative drift <= 20 m (no landmarks) / 40 m
    pos0 = {c: np.array(C[c]['xyz'], float) for c in C}
    sib = {c: [o for o in sol['cams'] if o != c and np.linalg.norm(pos0[o] - pos0[c]) < 5.0] for c in sol['cams']}
    newpos = {}
    for cam, v in sol['cams'].items():
        d = np.array(v['delta']); c0 = C[cam]
        if v['z_score'] < 0.15: continue
        st = state(c0, d); why = []
        h0 = c0['xyz'][2] - float(_gnd(*c0['xyz'][:2])); h1 = st['xyz'][2] - float(_gnd(*st['xyz'][:2]))
        if h1 < 0.5 and h1 < h0: why.append('would go below the ground (%.1f m above the heightmap)' % h1)
        if 1.2 <= h0 <= 2.2 and abs(h1 - h0) > 0.5: why.append('street-level camera would change its eye height %.1f -> %.1f m' % (h0, h1))
        org = np.array(c0.get('_mvs_origin') or c0['xyz'], float)
        strong = v['edges'] >= 20 and v['edge_rms_after'] is not None and v['edge_rms_after'] <= 0.5 * v['edge_rms_before']
        lim = 40.0 if (v['lms'] >= 3 or strong) else 20.0
        if np.linalg.norm(np.array(st['xyz']) - org) > lim: why.append('cumulative drift %.0f m from its pre-MVS position (> %.0f m)' % (np.linalg.norm(np.array(st['xyz']) - org), lim))
        for o in sib[cam]:
            po = np.array(state(C[o], np.array(sol['cams'][o]['delta']))['xyz']) if o in sol['cams'] else pos0[o]
            if abs(np.linalg.norm(np.array(st['xyz']) - po) - np.linalg.norm(pos0[cam] - pos0[o])) > 5.0: why.append('would separate from its sibling shot %s' % o)
        r0 = common.cam_rms(cam, cam_state={'xyz': c0['xyz'], 'ypr': c0['ypr'], 'fov': c0['fov']}); r1 = common.cam_rms(cam, cam_state=st)
        if np.hypot(d[0], d[1]) > 40 or abs(d[2]) > 20: why.append('move too large')
        if v['lms'] >= 3:
            if r0 is not None and r1 is not None and r1 > r0 * 1.05 + 0.05: why.append("LM RMS %.2f' -> %.2f'" % (r0, r1))
        elif not (v['edges'] >= 8 and v['edge_rms_after'] is not None and v['edge_rms_after'] <= 0.7 * v['edge_rms_before']): why.append('no landmarks and weak edge gain')
        if v['edges'] and v['edge_rms_after'] is not None and v['edge_rms_after'] > v['edge_rms_before']: why.append('edges worse')
        if why: rej_c.append((cam, d.tolist(), why)); continue
        C[cam].setdefault('_mvs_origin', [round(float(x), 3) for x in c0['xyz']])
        C[cam]['xyz'] = [round(float(x), 3) for x in st['xyz']]; C[cam]['ypr'] = [round(float(x), 3) for x in st['ypr']]
        C[cam]['fov'] = [None if f is None else round(float(f), 3) for f in st['fov']]
        C[cam]['note'] = (str(C[cam].get('note') or '') + (' | ' if C[cam].get('note') else '') +
                          "MVS-V1 2026-10-09: global multi-view solve, d(xyz) %+.1f %+.1f %+.1f m, d(ypr) %+.2f %+.2f %+.2f deg, dfov %+.2f; edges %s -> %s sigma, landmark RMS %s' -> %s'" %
                          (*d, v['edge_rms_before'], v['edge_rms_after'], None if r0 is None else round(r0, 2), None if r1 is None else round(r1, 2)))
        acc_c.append((cam, d.tolist(), r0, r1))
    for n, v in sol['meshes'].items():
        t = np.array(v['delta']); why = []
        if len(v['cams']) < 3: why.append('%d camera(s)' % len(v['cams']))
        if v['edge_rms_after'] > 0.75 * v['edge_rms_before']: why.append('edge gain < 25 %%: %s -> %s' % (v['edge_rms_before'], v['edge_rms_after']))
        if np.hypot(t[0], t[1]) > 25 or abs(t[2]) > 0.15: why.append('change too large')
        if np.hypot(t[0], t[1]) < 1.0 and abs(t[2]) < 0.01: continue
        if not why and np.hypot(t[0], t[1]) >= 1.0:                    # ROADS-GT: never onto a road
            E0 = np.array(M[n]['world_edges'], float); fp0 = footprint(E0)
            if fp0 is not None:
                o0, o1 = road_overlap(fp0), road_overlap(fp0 + t[:2])
                if o1 > o0 + 0.005: why.append('would cover a V16 road (%.0f%% -> %.0f%%; roads are ground truth)' % (o0 * 100, o1 * 100))
        if why: rej_m.append((n, t.tolist(), why)); continue
        E = np.array(M[n]['world_edges'], float); g = E[:, :, 2].min()
        E[:, :, 0] += t[0]; E[:, :, 1] += t[1]; E[:, :, 2] = g + (E[:, :, 2] - g) * (1 + t[2])
        M[n]['world_edges'] = np.round(E, 2).tolist()
        M[n]['note'] = M[n].get('note', '') + (' | MVS-V1 2026-10-09: global multi-view solve (%d cameras): plan shifted (%+.1f, %+.1f) m, height x%.3f; edges %s -> %s sigma.' %
                                                (len(v['cams']), t[0], t[1], 1 + t[2], v['edge_rms_before'], v['edge_rms_after']))
        acc_m.append((n, t.tolist(), len(v['cams'])))
    json.dump(C, open(A.CAMS, 'w'), indent=1, ensure_ascii=True); json.dump(M, open(MP, 'w'), indent=1, ensure_ascii=True)
    L = open(DOC).read().split('\n')
    L += ['', '## Applied (guarded)', '', 'Cameras applied: %d; meshes applied: %d.' % (len(acc_c), len(acc_m)), '',
          '### Cameras kept for review', ''] + ['- %s %s: %s' % (c, np.round(d, 2).tolist(), '; '.join(w)) for c, d, w in rej_c] + \
         ['', '### Meshes kept for review', ''] + ['- %s %s: %s' % (n, np.round(t, 3).tolist(), '; '.join(w)) for n, t, w in rej_m]
    open(DOC, 'w').write('\n'.join(L) + '\n')
    print('applied cameras %d (review %d), meshes %d (review %d)' % (len(acc_c), len(rej_c), len(acc_m), len(rej_m)))
    for a in acc_c: print('  cam', a[0], np.round(a[1], 2).tolist(), 'RMS', a[2], '->', a[3])
    for a in acc_m: print('  mesh', a[0], np.round(a[1], 3).tolist(), a[2], 'cams')


if __name__ == '__main__':
    if '--apply' in sys.argv: apply()
    else: main()
