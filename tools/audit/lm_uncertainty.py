#!/usr/bin/env python3
"""
lm_uncertainty.py - READ-ONLY (Chantier C1).

Incertitude 3D par LM via Monte-Carlo. Moteur: rayons reconstruits a la main
(cam.xyz + cam.get_pixel_direction(pixel)) pour pouvoir injecter le bruit pixel
ET le bruit de pose independamment, sans toucher l'etat global ml.

Pour chaque LM triangulable:
  1. robust_triangulate une fois (a vide) -> jeu 'kept' + xyz ref.
  2. N tirages: pixel += N(0,sigma_px); pose cam: ypr += N(0,sigma_ang),
     xyz += N(0,sigma_xyz) (sauf leak: xyz fige). Rayon perturbe, intersection LSQ.
  3. covariance empirique -> 3 demi-axes (sqrt valeurs propres), rayon = sqrt(trace),
     anisotropie = a1/a3. Trie par rayon (fragilite).

sigma_pose derive du tier cam. Le bruit de pose deplace l'ORIGINE et la DIRECTION
du rayon (on re-tire la direction depuis la pose perturbee via get_pixel_direction
sur la cam clonee... mais ml est global, donc on perturbe geometriquement: rotation
aleatoire de la direction par sigma_ang, translation de l'origine par sigma_xyz).

AUCUNE ECRITURE. stdout + JSON optionnel (--dump). Progress sur stderr.

Usage:
  python3 tools/audit/lm_uncertainty.py --n 200 --top 60 --dump
  python3 tools/audit/lm_uncertainty.py --only "Sebring"
  python3 tools/audit/lm_uncertainty.py --no-pose   (bruit pixel seul)
"""

import argparse
import json
import math
import os
import sys
import numpy as np
from scipy.optimize import minimize

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(THIS_DIR)
sys.path.insert(0, TOOLS_DIR)

import triangulate_lm as T
import gtamaplib as ml

GEN_DIR = os.path.join(TOOLS_DIR, 'generated')
DUMP_OUT = os.path.join(GEN_DIR, 'lm_uncertainty.json')

SIGMA_POSE = {
    'anchor':     (0.5, 0.05),
    'high':       (2.0, 0.20),
    'medium':     (5.0, 0.50),
    'low':        (15.0, 1.0),
    'unverified': (15.0, 1.0),
    None:         (15.0, 1.0),
}
SIGMA_PX_DEFAULT = 3.0


def is_leak(cn, cams):
    try:
        return T.is_leak_cam(cams.get(cn, {}))
    except Exception:
        return False


def perturb_direction(d, sigma_ang_deg, rng):
    """Tilt unit vector d by a small random rotation of std sigma_ang_deg."""
    if sigma_ang_deg <= 0:
        return d
    ang = math.radians(rng.normal(0, sigma_ang_deg))
    axis = rng.normal(size=3)
    axis -= np.dot(axis, d) * d
    na = np.linalg.norm(axis)
    if na < 1e-9:
        return d
    axis /= na
    dn = d * math.cos(ang) + np.cross(axis, d) * math.sin(ang)
    return dn / np.linalg.norm(dn)


def tri_rays(rays, init):
    def loss(p):
        t = 0.0
        for o, d in rays:
            v = p - o
            dist = np.linalg.norm(v)
            if dist < 1e-3:
                continue
            perp = v - np.dot(v, d) * d
            t += (np.linalg.norm(perp) / dist) ** 2
        return t
    r = minimize(loss, init, method='Nelder-Mead',
                 options={'xatol': 1e-2, 'fatol': 1e-10, 'maxiter': 4000, 'adaptive': True})
    return r.x


def _run_cloud(base, init, n, sigma_px, use_pose, rng):
    pts = []
    for _ in range(n):
        rays = []
        for cn, p0, o0, dir0, s_xyz, s_ang, leak, cam in base:
            pn = [p0[0] + rng.normal(0, sigma_px), p0[1] + rng.normal(0, sigma_px)]
            try:
                dirn = np.asarray(cam.get_pixel_direction(pn), float)
                dirn /= np.linalg.norm(dirn)
            except Exception:
                dirn = dir0.copy()
            o = o0.copy()
            if use_pose:
                dirn = perturb_direction(dirn, s_ang, rng)
                if not leak:
                    o = o0 + rng.normal(0, s_xyz, size=3)
            rays.append((o, dirn))
        try:
            p = tri_rays(rays, init)
            if np.all(np.isfinite(p)) and np.linalg.norm(np.asarray(p) - init) < 10000.0:
                pts.append(p)
        except Exception:
            pass
    return pts


def _radius(pts, n):
    if len(pts) < max(5, n // 4):
        return None, None, None
    P = np.array(pts)
    cov = np.cov((P - P.mean(axis=0)).T)
    evals = np.clip(np.sort(np.linalg.eigvalsh(cov))[::-1], 0, None)
    semi = np.sqrt(evals)
    aniso = float(semi[0]/semi[2]) if semi[2] > 1e-6 else float('inf')
    return float(np.sqrt(np.trace(cov))), [float(x) for x in semi], aniso


def mc_lm(lm_name, cams, pix, lms, tiers, n, sigma_px, use_pose, rng):
    d = lms.get(lm_name)
    if not isinstance(d, dict) or d.get('xyz') is None:
        return None
    # [EXCL-AWARE-V1] honorer excluded_markings.json (meme trou que le
    # bundle avait: une source dont le marking est exclu ne doit pas
    # participer a l'incertitude du LM)
    from common import is_excluded_marking as _iem
    srcs = [c for c in (d.get('source_cameras') or [])
            if c in cams and not _iem(c, lm_name)]
    if len(srcs) < 2:
        return None
    init = np.asarray(d['xyz'], float)
    try:
        xyz0, maxres0, kept, _ = T.robust_triangulate(srcs, lm_name, pix, cams, list(init), verbose=False)
    except Exception:
        return None
    if not kept or len(kept) < 2:
        return None

    base = []
    for cn in kept:
        p = pix.get(cn, {}).get(lm_name)
        if p is None:
            continue
        cam = ml.get_camera(cn)
        dir0 = np.asarray(cam.get_pixel_direction(p), float)
        dir0 /= np.linalg.norm(dir0)
        o0 = np.asarray(cam.xyz, float)
        tier = tiers.get(cn)
        leak = is_leak(cn, cams)
        if leak:
            s_xyz, s_ang = 0.0, 0.02
        else:
            s_xyz, s_ang = SIGMA_POSE.get(tier, SIGMA_POSE[None])
        base.append((cn, np.asarray(p, float), o0, dir0, s_xyz, s_ang, leak, cam))

    if len(base) < 2:
        return None

    pts_pose = _run_cloud(base, init, n, sigma_px, True, rng)
    pts_pix  = _run_cloud(base, init, n, sigma_px, False, rng)
    r_pose, semi, aniso = _radius(pts_pose, n)
    r_pix, _, _ = _radius(pts_pix, n)
    if r_pose is None:
        return {'lm': lm_name, 'status': 'few_results', 'n_ok': len(pts_pose), 'kept': kept}
    ratio = (r_pose / r_pix) if (r_pix and r_pix > 1e-6) else float('inf')
    return {
        'lm': lm_name, 'status': 'ok', 'n_ok': len(pts_pose), 'n_sources': len(kept),
        'kept': kept, 'tier': tiers.get(lm_name),
        'radius_m': r_pose, 'radius_pix_m': r_pix, 'ratio_pose_pix': ratio,
        'semi_axes_m': semi, 'anisotropy': aniso,
        'max_res_arcmin': float(maxres0),
        'error_m': d.get('error_m'),
        'all_sources_leak': all(b[6] for b in base),
    }


def main():
    ap = argparse.ArgumentParser(description="READ-ONLY: incertitude 3D par LM (Monte-Carlo).")
    ap.add_argument('--n', type=int, default=200)
    ap.add_argument('--sigma-px', type=float, default=SIGMA_PX_DEFAULT)
    ap.add_argument('--top', type=int, default=50)
    ap.add_argument('--only', type=str, default=None)
    ap.add_argument('--no-pose', action='store_true', help="bruit pixel seul (pas de bruit pose)")
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--dump', action='store_true')
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    cams, pix, lms, tiers = T.load_all()

    targets = [lm for lm, d in lms.items()
               if isinstance(d, dict) and d.get('xyz') is not None
               and len([c for c in (d.get('source_cameras') or []) if c in cams]) >= 2]
    if args.only:
        targets = [lm for lm in targets if args.only.lower() in lm.lower()]
    print(f"# {len(targets)} LM, N={args.n}, sigma_px={args.sigma_px}, "
          f"pose_noise={'OFF' if args.no_pose else 'ON'}", file=sys.stderr)

    results = []
    for i, lm in enumerate(targets):
        if i % 50 == 0:
            print(f"#  {i}/{len(targets)}...", file=sys.stderr)
        r = mc_lm(lm, cams, pix, lms, tiers, args.n, args.sigma_px, not args.no_pose, rng)
        if r:
            results.append(r)

    ok = [r for r in results if r.get('status') == 'ok']
    ok.sort(key=lambda r: r['radius_m'], reverse=True)
    print(f"\n# {len(ok)} LM avec covariance ; {len(results)-len(ok)} few_results")
    print(f"\n{'rank':>4} {'r_pose':>8} {'r_pix':>7} {'ratio':>6} {'nsrc':>4} {'allleak':>7}  LM")
    for rank, r in enumerate(ok[:args.top], 1):
        print(f"{rank:>4} {r['radius_m']:8.1f} {r['radius_pix_m']:7.1f} {r['ratio_pose_pix']:6.1f} "
              f"{r['n_sources']:>4} {str(r['all_sources_leak']):>7}  {r['lm']}")
    if ok:
        rads = np.array([r['radius_m'] for r in ok])
        print(f"\n# radius_m: median={np.median(rads):.2f} p90={np.percentile(rads,90):.2f} max={rads.max():.2f}")

    if args.dump:
        os.makedirs(GEN_DIR, exist_ok=True)
        with open(DUMP_OUT, 'w') as f:
            json.dump({'meta': {'n': args.n, 'sigma_px': args.sigma_px,
                                'pose_noise': not args.no_pose}, 'results': results}, f, indent=2)
        print(f"# dumpe: {DUMP_OUT}", file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
