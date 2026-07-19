#!/usr/bin/env python3
"""edgefit_core.py — noyau d'echantillonnage silhouette. [EDGE-FIT-V3]

V3 FINAL (2026-07-19): echantillonnage DENSE (toutes aretes) + raffinement
SUB-PIXEL du pic (parabole 3 points) + masque d'occlusion inter-buildings.
Le biais = mediane fractionnaire, resolution ~0.3-0.7px (IC bootstrap) =
25-70cm aux distances des juges.

FILTRES TESTES ET REFUTES (A/B 2026-07-19, garder pour l'histoire):
- silhouette-only (hull + mono-modal): en skyline dense le bord batiment/ciel
  est rare -> 40-340 pts bruites, biais erratiques. REFUTE.
- orientation-gating (gradient aligne normale): le bruit ±6px n'est PAS de la
  texture croisee mais la grille PARALLELE de la facade (pas ~6px) -> aucun
  gain. REFUTE.
La masse + la mediane sub-pixel battent le filtrage. L'occlusion inter-
buildings (z-buffer de hulls) reste utile et active.

API:
  ctx = FrameCtx(cam_name)                    # image + gradients precalcules
  ctx.recam(cam_state)                        # pose candidate (mode cam)
  res = sample(ctx, edges, other_hulls=None)  # -> dict(offsets, n_raw, n_sil)
  hulls = build_hulls(ctx, meshes)            # occluders pour sample()
"""
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_THIS)
sys.path.insert(0, _THIS)
sys.path.insert(0, _REPO)

import numpy as np
from PIL import Image
import common

SEARCH = 10
STEP = 3
MIN_EDGE_PX = 15
MIN_PEAK = 12.0
PROMINENCE = 2.5
HULL_TOL_PX = 4.0       # distance max au bord du hull pour etre 'silhouette'
SECOND_PEAK_MAX = 0.55  # 2e pic < 55% du 1er = mono-modal


class FrameCtx:
    def __init__(self, cam_name):
        self.name = cam_name
        self.cam = common.get_cam(cam_name)
        img = np.asarray(Image.open(os.path.join(_REPO, 'frames', f'{cam_name}.png')).convert('L'), dtype=float)
        gy, gx = np.gradient(img)
        self.gmag = np.hypot(gx, gy)
        self.H, self.W = img.shape

    def recam(self, cam_state):
        self.cam = common.get_cam(self.name, cam_state)


def _project_pts(ctx, edges):
    out = []
    for a, b in edges:
        pa, pb = ctx.cam.get_pixel(a), ctx.cam.get_pixel(b)
        if pa is not None and pb is not None:
            out.append((np.asarray(pa, float), np.asarray(pb, float)))
    return out


def _hull_eqs(points):
    """Equations du hull convexe 2D (A@p + b <= 0 dedans). None si degenere."""
    try:
        from scipy.spatial import ConvexHull
        h = ConvexHull(points)
        return h.equations  # (n, 3): a1, a2, b
    except Exception:
        return None


def build_hulls(ctx, meshes):
    """{building: (equations_hull, profondeur_centroide)} pour l'occlusion."""
    hulls = {}
    for b, edges in meshes.items():
        proj = _project_pts(ctx, edges)
        if len(proj) < 4:
            continue
        pts = np.array([p for ab in proj for p in ab])
        eqs = _hull_eqs(pts)
        if eqs is None:
            continue
        world = np.array([p for a_, b_ in edges for p in (a_, b_)])
        depth = float(np.linalg.norm(world.mean(axis=0) - np.asarray(ctx.cam.xyz)))
        hulls[b] = (eqs, depth)
    return hulls


def _signed_dist_hull(eqs, pts):
    """Distance signee max aux demi-plans (<=0 dedans). (n_pts,)"""
    return (pts @ eqs[:, :2].T + eqs[:, 2][None, :]).max(axis=1)


def sample(ctx, edges, self_name=None, hulls=None, silhouette=False, collect=True):
    """Echantillonne les aretes projetees. Retourne dict avec offsets valides."""
    proj = _project_pts(ctx, edges)
    pts, nrms = [], []
    for pa, pb in proj:
        L = float(np.hypot(*(pb - pa)))
        if L < MIN_EDGE_PX:
            continue
        t = (pb - pa) / L
        n = np.array([-t[1], t[0]])
        for s in np.arange(3, L - 3, STEP):
            pts.append(pa + t * s)
            nrms.append(n)
    if not pts:
        return dict(offsets=np.array([]), n_raw=0, n_sil=0)
    P = np.array(pts); N = np.array(nrms)
    ok = (P[:, 0] > SEARCH) & (P[:, 0] < ctx.W - SEARCH - 1) & \
         (P[:, 1] > SEARCH) & (P[:, 1] < ctx.H - SEARCH - 1)
    P, N = P[ok], N[ok]
    n_raw = len(P)
    if not n_raw:
        return dict(offsets=np.array([]), n_raw=0, n_sil=0)

    if silhouette:
        # (refute pour la skyline dense — conserve pour cas isoles)
        all_pts = np.array([p for ab in proj for p in ab])
        eqs = _hull_eqs(all_pts)
        if eqs is not None:
            d = _signed_dist_hull(eqs, P)
            keep = np.abs(d) < HULL_TOL_PX
            P, N = P[keep], N[keep]
    if True:
        # occlusion inter-buildings: toujours active si hulls fournis
        if hulls and len(P):
            self_depth = hulls.get(self_name, (None, None))[1] if self_name in (hulls or {}) else None
            for b2, (eqs2, depth2) in hulls.items():
                if b2 == self_name or not len(P):
                    continue
                if self_depth is not None and depth2 >= self_depth:
                    continue
                inside = _signed_dist_hull(eqs2, P) < -1.0
                P, N = P[~inside], N[~inside]
    if not len(P):
        return dict(offsets=np.array([]), n_raw=n_raw, n_sil=0)

    offs_range = np.arange(-SEARCH, SEARCH + 1)
    X = (P[:, 0:1] + N[:, 0:1] * offs_range[None, :]).astype(int)
    Y = (P[:, 1:2] + N[:, 1:2] * offs_range[None, :]).astype(int)
    G = ctx.gmag[Y, X]
    k = np.argmax(G, axis=1)
    idx = np.arange(len(G))
    peak = G[idx, k]
    med = np.median(G, axis=1)
    valid = (peak >= MIN_PEAK) & (peak >= PROMINENCE * np.maximum(med, 1e-6)) \
            & (k > 0) & (k < 2 * SEARCH)
    # raffinement SUB-PIXEL: parabole 3 points autour du pic
    km = np.clip(k - 1, 0, 2 * SEARCH); kp = np.clip(k + 1, 0, 2 * SEARCH)
    y0, y1, y2 = G[idx, km], G[idx, k], G[idx, kp]
    denom = y0 - 2 * y1 + y2
    with np.errstate(divide='ignore', invalid='ignore'):
        frac = np.where(np.abs(denom) > 1e-6, 0.5 * (y0 - y2) / denom, 0.0)
    frac = np.clip(np.nan_to_num(frac), -1, 1)
    off = (k - SEARCH + frac)[valid].astype(float)
    return dict(offsets=off if collect else np.array([]),
                n_raw=n_raw, n_sil=int(valid.sum()),
                cost=float(np.sum(np.sqrt(1 + (off / 3.0) ** 2) - 1)))
