#!/usr/bin/env python3
"""
triangulate_lm.py — Triangulate a single landmark using priority-based source selection.

Priority order for which cameras to use:
  1. Leak + Leak (xyz/fov ground truth from console)
  2. Leak + Trusted non-leak (tier anchor/high)
  3. Trusted + Trusted (no leak available)
  4. Leak + Other (fallback)
  5. Other (last resort)

The selected pair/group is used to triangulate. Cameras outside the chosen
priority tier are ignored even if they have markings.

The LM xyz is updated based on the triangulation. Cameras DO NOT move.

Default mode is dry-run (shows what would change without modifying files).
Use --apply to actually update landmarks.json.

Usage:
    python3 tools/triangulate_lm.py "1000 Venetian Way (SW)"           # dry-run
    python3 tools/triangulate_lm.py "1000 Venetian Way (SW)" --apply   # write
"""

import argparse
import json
import math
import os
import re
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(THIS_DIR)
DATA_DIR = os.path.join(REPO_DIR, 'gtamapdata')
GEN_DIR = os.path.join(THIS_DIR, 'generated')

CAMERAS_JSON = os.path.join(DATA_DIR, 'cameras.json')
PIXELS_JSON = os.path.join(DATA_DIR, 'pixels.json')
EXCLUDED_JSON = os.path.join(DATA_DIR, 'excluded_markings.json')

# [EXCLUDED-MARKINGS-V1]
def _load_excluded_markings():
    data = {}
    try:
        with open(EXCLUDED_JSON) as f:
            raw = json.load(f)
        for cam, lms in raw.items():
            if not cam.startswith("_") and isinstance(lms, list):
                data[cam] = set(lms)
    except FileNotFoundError:
        pass
    return data
LANDMARKS_JSON = os.path.join(DATA_DIR, 'landmarks.json')
TIERS_JSON = os.path.join(GEN_DIR, 'confidence_tiers.json')

sys.path.insert(0, REPO_DIR)
import gtamaplib as ml


def load_all():
    """Load cameras, pixels, landmarks, tiers."""
    with open(CAMERAS_JSON) as f:
        cameras = json.load(f)
    with open(PIXELS_JSON) as f:
        pixels = json.load(f)
    with open(LANDMARKS_JSON) as f:
        landmarks = json.load(f)
    tiers_data = {'cameras': {}, 'landmarks': {}}
    if os.path.exists(TIERS_JSON):
        with open(TIERS_JSON) as f:
            tiers_data = json.load(f)
    cam_tiers = {}
    for n, d in tiers_data.get('cameras', {}).items():
        cam_tiers[n] = d.get('tier') if isinstance(d, dict) else d
    return cameras, pixels, landmarks, cam_tiers


def is_leak_cam(cam_data):
    """A cam is 'leak' if its source matches a date pattern YYYY-MM-DD."""
    if not isinstance(cam_data, dict):
        return False
    src = cam_data.get('source', '') or ''
    return bool(re.match(r'\d{4}-\d{2}-\d{2}', src))


def classify_cam(cam_name, cameras, cam_tiers):
    """Return 'leak', 'trusted_non_leak', 'other', or 'excluded'.

    Selection is driven purely by calibration confidence (tier).
    constraint_class is kept in the data for provenance but does NOT affect
    source selection: nearly all non-leak cams are trailer/screenshot
    captures we calibrate ourselves, so what matters is how well a cam was
    calibrated (its tier), not its origin class. Only 'low' tier cams are
    excluded as triangulation sources; cams with no tier fall through to
    'other' (usable only as a last resort, never as an anchor).
    """
    c = cameras.get(cam_name, {})
    tier = cam_tiers.get(cam_name)
    # Leak cams have HUD-locked position (and usually fov) = ground truth.
    # Only D (no ground truth) and X (invalid) are excluded; A/B/C/Cm all
    # have at least a locked position, so their rays originate from a known
    # point and are valid triangulation sources regardless of tier.
    if is_leak_cam(c):
        cls = (c.get('constraint_class') or '')
        if cls.startswith('D') or cls.startswith('X'):
            return 'excluded'
        if cls.startswith('A'):
            return 'leak_a'
        return 'leak_pos'
    if tier == 'low':
        return 'excluded'
    if tier in ('anchor', 'high'):
        return 'trusted_non_leak'
    return 'other'


def select_sources(observers_classified):
    """Apply priority hierarchy. Returns (selected_cams, reason_str).

    observers_classified: dict {cam_name: classification}
    """
    leak_a = [n for n, c in observers_classified.items() if c == 'leak_a']
    leak_pos = [n for n, c in observers_classified.items() if c == 'leak_pos']
    trusted = [n for n, c in observers_classified.items() if c == 'trusted_non_leak']
    other = [n for n, c in observers_classified.items() if c == 'other']

    # Priority tiers, best first: A (full HUD) > trusted non-leak > C/B/Cm
    # (pos-locked, dir uncertain) > other. We INCLUDE all sources from every
    # tier that has any reliable cam, rather than stopping at 2 — this gives
    # the triangulation enough viewpoint diversity (parallax) and avoids the
    # degenerate case of two near-collinear cams (e.g. Port + Port (B) at
    # 0.03 deg) being picked alone and blowing the solution up to 1e15.
    pool = []
    reason_parts = []
    for label, group in [('leak_A', leak_a), ('trusted', trusted),
                         ('leak_pos', leak_pos)]:
        if group:
            pool += group
            reason_parts.append(f"{label}({len(group)})")
    # Only fall back to 'other' if the reliable pool is still too small.
    if len(pool) < 2 and other:
        pool += other
        reason_parts.append(f"other({len(other)})")
    if len(pool) >= 2:
        return pool, " + ".join(reason_parts)
    return [], "insufficient observers"


def triangulate(selected_cams, lm_name, pixels, cameras, init_xyz):
    """Multi-cam triangulation using the selected cams. Returns (xyz, max_residual_arcmin).

    Returns (None, error_str) on failure.
    """
    try:
        import numpy as np
        from scipy.optimize import minimize
    except ImportError:
        return None, "scipy/numpy not installed"

    rays = []
    for cn in selected_cams:
        if cn not in pixels.get(cn, {}) and lm_name not in pixels.get(cn, {}):
            continue
        try:
            cam = ml.get_camera(cn)
            d = cam.get_landmark_direction(lm_name)
            d = np.asarray(d, dtype=float)
            d = d / np.linalg.norm(d)
            rays.append((cn, np.asarray(cam.xyz, dtype=float), d))
        except Exception as e:
            return None, f"failed to build ray for {cn}: {e}"

    if len(rays) < 2:
        return None, f"not enough rays ({len(rays)})"

    # Parallax guard: reject degenerate near-collinear configurations
    # (e.g. Port + Port (B) at 0.03 deg) that send the LSQ solution to ~1e15.
    import itertools, math as _m
    max_par = 0.0
    for (_, _, d1), (_, _, d2) in itertools.combinations(rays, 2):
        cosang = float(np.clip(np.dot(d1, d2), -1.0, 1.0))
        max_par = max(max_par, _m.degrees(_m.acos(cosang)))
    if max_par < 3.0:
        return None, f"insufficient parallax (max {max_par:.2f} deg between all ray pairs)"

    def loss(p):
        p = np.asarray(p)
        total = 0.0
        for _, o, d in rays:
            v = p - o
            dist = np.linalg.norm(v)
            if dist < 1e-3:
                continue
            perp = v - np.dot(v, d) * d
            ang = np.linalg.norm(perp) / dist
            total += ang * ang
        return total

    result = minimize(loss, init_xyz, method='Nelder-Mead',
                      options={'xatol': 1e-3, 'fatol': 1e-12,
                               'maxiter': 10000, 'adaptive': True})
    p_new = result.x

    # Compute max residual in arcmin
    max_res = 0.0
    for _, o, d in rays:
        v = p_new - o
        dist = np.linalg.norm(v)
        if dist < 1e-3:
            continue
        perp = v - np.dot(v, d) * d
        ang_arcmin = math.degrees(np.linalg.norm(perp) / dist) * 60
        max_res = max(max_res, ang_arcmin)

    return p_new.tolist(), max_res


def _build_rays(cams, lm_name, pixels):
    """Build (name, origin, unit_dir) for each cam that can see lm_name."""
    import numpy as np
    rays = []
    for cn in cams:
        if lm_name not in pixels.get(cn, {}):
            continue
        try:
            cam = ml.get_camera(cn)
            d = np.asarray(cam.get_landmark_direction(lm_name), dtype=float)
            d = d / np.linalg.norm(d)
            rays.append((cn, np.asarray(cam.xyz, dtype=float), d))
        except Exception:
            continue
    return rays


def _residuals_arcmin(point, rays):
    """Per-cam reprojection residual in arcmin for a candidate point."""
    import numpy as np, math
    out = {}
    p = np.asarray(point, dtype=float)
    for cn, o, d in rays:
        v = p - o
        dist = np.linalg.norm(v)
        if dist < 1e-3:
            out[cn] = 0.0; continue
        perp = v - np.dot(v, d) * d
        out[cn] = math.degrees(np.linalg.norm(perp) / dist) * 60.0
    return out


def robust_triangulate(candidate_cams, lm_name, pixels, cameras, init_xyz,
                       min_parallax=15.0, outlier_mult=2.0, outlier_floor=5.0,
                       verbose=True, observers_classified_global=None):
    """Choose a consensus subset of sources automatically.

    1. Drop cams that have NO pairing >= min_parallax with any other cam
       (a source with only collinear partners is useless / dangerous).
    2. Triangulate with survivors, compute per-cam reprojection residual.
    3. Reject the worst cam if its residual > outlier_mult * median AND
       > outlier_floor; retriangulate; repeat until stable or < 3 cams.
    Returns (xyz, max_res, kept, dropped_log).
    """
    import numpy as np, math, itertools

    rays = _build_rays(candidate_cams, lm_name, pixels)
    observers_classified_global = observers_classified_global or {}
    dropped = []
    if len(rays) < 2:
        return None, f"not enough rays ({len(rays)})", [], dropped

    # --- Step 1: parallax filter ---
    names = [r[0] for r in rays]
    best_par = {n: 0.0 for n in names}
    pair_par = {}
    for (n1, _, d1), (n2, _, d2) in itertools.combinations(rays, 2):
        ang = math.degrees(math.acos(float(np.clip(np.dot(d1, d2), -1.0, 1.0))))
        pair_par[(n1, n2)] = ang
        best_par[n1] = max(best_par[n1], ang)
        best_par[n2] = max(best_par[n2], ang)
    survivors = [r for r in rays if best_par[r[0]] >= min_parallax]
    for r in rays:
        if best_par[r[0]] < min_parallax:
            dropped.append((r[0], f"low parallax (best {best_par[r[0]]:.1f}deg < {min_parallax})"))
    if verbose:
        print("  Pairwise parallax (best per cam):")
        for n in names:
            mark = "" if best_par[n] >= min_parallax else "  DROP (collinear)"
            print(f"    {best_par[n]:6.1f}deg  {n}{mark}")
    if len(survivors) < 2:
        return None, f"only {len(survivors)} cam(s) survive parallax filter",                [r[0] for r in survivors], dropped

    # --- Step 1b: collinear-pair dedup ---
    # Two cams seeing the LM from nearly the same direction (mutual parallax
    # < dedup_thresh) add no independent info and form a degenerate pair
    # (e.g. Port + Port (B) at 0.03 deg). Keep only the better one, ranked
    # leak_a > trusted_non_leak > leak_pos > other.
    dedup_thresh = 5.0
    rank = {'leak_a': 0, 'trusted_non_leak': 1, 'leak_pos': 2, 'other': 3}
    def _worse(n1, n2):
        r1 = rank.get(observers_classified_global.get(n1, 'other'), 9)
        r2 = rank.get(observers_classified_global.get(n2, 'other'), 9)
        return n2 if r1 <= r2 else n1
    removed = set()
    snames = [r[0] for r in survivors]
    for i in range(len(snames)):
        for j in range(i + 1, len(snames)):
            n1, n2 = snames[i], snames[j]
            if n1 in removed or n2 in removed:
                continue
            par = pair_par.get((n1, n2), pair_par.get((n2, n1)))
            if par is not None and par < dedup_thresh:
                w = _worse(n1, n2)
                keep = n1 if w == n2 else n2
                removed.add(w)
                dropped.append((w, f"collinear with {keep} ({par:.2f}deg) - redundant viewpoint"))
                if verbose:
                    print(f"  dedup: drop {w} (collinear {par:.2f}deg with {keep})")
    survivors = [r for r in survivors if r[0] not in removed]
    if len(survivors) < 2:
        return None, f"only {len(survivors)} cam(s) after dedup", [r[0] for r in survivors], dropped

    # --- Step 2+3: triangulate, reject outliers iteratively ---
    cur = list(survivors)
    while True:
        names_cur = [r[0] for r in cur]
        xyz, max_res = triangulate(names_cur, lm_name, pixels, cameras, init_xyz)
        if xyz is None:
            return None, max_res, names_cur, dropped
        res = _residuals_arcmin(xyz, cur)
        vals = sorted(res.values())
        median = vals[len(vals) // 2]
        worst_cam = max(res, key=res.get)
        worst_res = res[worst_cam]
        if len(cur) > 3 and worst_res > outlier_mult * median and worst_res > outlier_floor:
            dropped.append((worst_cam, f"outlier residual {worst_res:.1f}' (>{outlier_mult}x median {median:.1f}')"))
            if verbose:
                print(f"  reject outlier: {worst_cam} ({worst_res:.1f}', median {median:.1f}')")
            cur = [r for r in cur if r[0] != worst_cam]
            continue
        # stable
        if verbose:
            print("  Final source residuals:")
            for cn in sorted(res, key=res.get):
                print(f"    {res[cn]:6.2f}'  {cn}")
        return xyz, max_res, names_cur, dropped


def main():
    parser = argparse.ArgumentParser(description="Triangulate a single LM with priority-based source selection.")
    parser.add_argument('lm_name', help="Name of the landmark to triangulate.")
    parser.add_argument('--apply', action='store_true',
                        help="Actually write the update. Default is dry-run.")
    args = parser.parse_args()

    cameras, pixels, landmarks, cam_tiers = load_all()

    lm = landmarks.get(args.lm_name)
    if lm is None:
        print(f"ERROR: LM '{args.lm_name}' not found in landmarks.json")
        return 1

    if not isinstance(lm, dict):
        print(f"ERROR: LM '{args.lm_name}' has unexpected format")
        return 1

    cur_xyz = lm.get('xyz')
    cur_err = lm.get('error_m')
    cur_sources = lm.get('source_cameras', [])

    print(f"=== {args.lm_name} ===")
    print(f"Current xyz: {cur_xyz}")
    print(f"Current error_m: {cur_err}")
    print(f"Current sources: {cur_sources}")
    print()

    # Find all cams with markings for this LM
    excluded = _load_excluded_markings()  # [EXCLUDED-MARKINGS-V1]
    observers = []
    for cam_name, lm_map in pixels.items():
        if args.lm_name in lm_map:
            if args.lm_name in excluded.get(cam_name, ()):  # [EXCLUDED-MARKINGS-V1]
                print(f"  [excluded] {cam_name} (skipped per excluded_markings.json)")
                continue
            observers.append(cam_name)

    if not observers:
        print(f"ERROR: No cam has a pixel marking for '{args.lm_name}'")
        print(f"LM not updated, reason: no observers")
        return 1

    # Classify each observer
    observers_classified = {}
    for cam_name in observers:
        cls = classify_cam(cam_name, cameras, cam_tiers)
        observers_classified[cam_name] = cls

    print(f"Observers ({len(observers)}):")
    for cam_name, cls in observers_classified.items():
        print(f"  [{cls:18}] {cam_name}")
    print()

    # Build candidate pool by class priority (excludes D/X and low-tier).
    candidate, reason = select_sources(observers_classified)
    print(f"Candidate pool ({len(candidate)}): {candidate}")
    print(f"Pool reason: {reason}")
    print()

    if len(candidate) < 2:
        print(f"LM not updated, reason: only {len(candidate)} cam(s) in pool (need >= 2)")
        return 1

    # Triangulate
    init = cur_xyz if cur_xyz else [0.0, 0.0, 0.0]
    # Robust consensus: parallax filter + iterative outlier rejection.
    print("Robust source selection:")
    new_xyz, max_res, kept, dropped = robust_triangulate(
        candidate, args.lm_name, pixels, cameras, init,
        observers_classified_global=observers_classified)
    print()
    if dropped:
        print("Dropped sources:")
        for cn, why in dropped:
            print(f"  - {cn}: {why}")
    print(f"Kept sources ({len(kept) if kept else 0}): {kept}")
    print()

    if new_xyz is None:
        print(f"LM not updated, reason: {max_res}")
        return 1

    # Compute diff
    if cur_xyz:
        delta = math.sqrt(sum((new_xyz[i] - cur_xyz[i]) ** 2 for i in range(3)))
    else:
        delta = None

    print(f"Triangulation result:")
    print(f"  New xyz: [{new_xyz[0]:.4f}, {new_xyz[1]:.4f}, {new_xyz[2]:.4f}]")
    print(f"  Max residual: {max_res:.3f} arcmin")
    if delta is not None:
        print(f"  Delta from current: {delta:.3f} m")
    print()

    if not args.apply:
        print("DRY-RUN: not writing. Use --apply to actually update.")
        return 0

    # Apply
    lm['xyz'] = new_xyz
    lm['error_m'] = round(float(max_res), 3)
    lm['source_cameras'] = kept
    landmarks[args.lm_name] = lm

    with open(LANDMARKS_JSON, 'w') as f:
        json.dump(landmarks, f, indent=2)

    print(f"APPLIED: landmarks.json updated.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
