#!/usr/bin/env python3
"""dual_metric_bench.py — READ-ONLY A/B bench for DUAL-METRIC-V3.

The triangulator's outlier rejection (robust_triangulate) is expressed in
PURE ARCMIN. Arcmin explodes at short range (a 1px error on a 20m witness =
~190') and stays small at long range even for big ground errors (a 3px error
on a 10km witness = ~3' but 8m off). So the arcmin outlier rule over-penalizes
NEAR witnesses and under-penalizes FAR ones.

This tool replays every multi-source triangulation TWICE — with the current
arcmin rule and with the DUAL (metre-authoritative) rule — and reports, per
LM, how the kept-source set, the converged point, and the all-observer metric
residual differ. Read-only; touches no files on disk.

Usage:
    ./.venv/bin/python tools/audit/dual_metric_bench.py               # A/B summary
    ./.venv/bin/python tools/audit/dual_metric_bench.py --floor-m 8   # sweep the metre floor
    ./.venv/bin/python tools/audit/dual_metric_bench.py --json OUT.json
    ./.venv/bin/python tools/audit/dual_metric_bench.py --limit 50
"""
import argparse
import json
import math
import os
import statistics
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(THIS_DIR)
REPO_DIR = os.path.dirname(TOOLS_DIR)
sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, REPO_DIR)

import triangulate_lm as tl


def all_obs_dual(lm, xyz, observers, pixels):
    """(max_arcmin, median_m, max_m) over every observer at candidate xyz."""
    rays = tl._build_rays(observers, lm, pixels)
    if not rays:
        return None, None, None
    dres = tl._residuals_dual(xyz, rays)
    arcs = [a for a, _ in dres.values()]
    gaps = [g for _, g in dres.values()]
    gaps_s = sorted(gaps)
    return (max(arcs), gaps_s[len(gaps_s) // 2], max(gaps))


def run_one(lm, pool, classified, cur_xyz, pixels, cameras, dual, floor_m,
            weighted=False):
    init = cur_xyz if cur_xyz else [0.0, 0.0, 0.0]
    xyz, max_res, kept, dropped = tl.robust_triangulate(
        pool, lm, pixels, cameras, init, verbose=False,
        observers_classified_global=classified, dual=dual,
        outlier_floor_m=floor_m, weighted=weighted)
    return xyz, kept, dropped


def leak_judge(lm, xyz, classified, pixels):
    """Metric residuals against class-A (full-HUD pose) observers ONLY —
    the closest thing to ground-truth rays. Returns (max_m, n) or (None, 0)."""
    leak_obs = [c for c, cl in classified.items() if cl == 'leak_a']
    if not leak_obs:
        return None, 0
    rays = tl._build_rays(leak_obs, lm, pixels)
    if not rays:
        return None, 0
    d = tl._residuals_dual(xyz, rays)
    return max(g for _, g in d.values()), len(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default=None)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--floor-m', type=float, default=12.0,
                    help="Metric outlier floor for the dual rule (metres).")
    ap.add_argument('--ab', choices=['dual', 'weighted'], default='dual',
                    help="What to A/B: 'dual' = arcmin-rule vs dual-rule (both "
                         "equal-weight); 'weighted' = production (dual, equal-"
                         "weight) vs SIGMA-TRI-V1 (dual, sigma-weighted).")
    args = ap.parse_args()

    cameras, pixels, landmarks, cam_tiers = tl.load_all()
    excluded = tl._load_excluded_markings()

    obs_of = {}
    for cam_name, lm_map in pixels.items():
        for lm_name in lm_map:
            if lm_name in excluded.get(cam_name, ()):
                continue
            obs_of.setdefault(lm_name, []).append(cam_name)
    targets = sorted(lm for lm, obs in obs_of.items()
                     if len(obs) >= 2 and isinstance(landmarks.get(lm), dict)
                     and landmarks[lm].get('xyz'))
    if args.limit:
        targets = targets[:args.limit]

    dump = {}
    changed = []          # LMs whose kept set differs
    max_m_before, max_m_after = [], []
    n_ok = 0

    for lm in targets:
        observers = obs_of[lm]
        classified = {c: tl.classify_cam(c, cameras, cam_tiers) for c in observers}
        pool, _r = tl.select_sources(classified)
        if len(pool) < 2:
            continue
        cur_xyz = landmarks[lm].get('xyz')
        try:
            if args.ab == 'dual':
                xa, ka, da = run_one(lm, pool, classified, cur_xyz, pixels, cameras, False, args.floor_m)
                xb, kb, db = run_one(lm, pool, classified, cur_xyz, pixels, cameras, True, args.floor_m)
            else:  # weighted: production (dual, equal-weight) vs sigma-weighted
                xa, ka, da = run_one(lm, pool, classified, cur_xyz, pixels, cameras, True, args.floor_m)
                xb, kb, db = run_one(lm, pool, classified, cur_xyz, pixels, cameras, True, args.floor_m, weighted=True)
        except Exception as e:
            dump[lm] = {'error': str(e)}
            continue
        if xa is None or xb is None:
            continue
        n_ok += 1

        # Z-JUDGE: for fixed-z LMs the true z is KNOWN. |z_solved - z_true|
        # measured BEFORE the snap is an objective, external accuracy judge
        # (the all-observer judge is biased toward the equal-weight solver,
        # which approximately optimizes it).
        z_err_a = z_err_b = None
        zc = (landmarks[lm].get('z_constraint') or None)
        if zc and zc.get('type') == 'fixed':
            z = float(zc['value'])
            z_err_a = abs(xa[2] - z); z_err_b = abs(xb[2] - z)
            xa = [xa[0], xa[1], z]; xb = [xb[0], xb[1], z]

        ra = all_obs_dual(lm, xa, observers, pixels)
        rb = all_obs_dual(lm, xb, observers, pixels)
        if ra[2] is not None:
            max_m_before.append(ra[2])
        if rb[2] is not None:
            max_m_after.append(rb[2])
        la, na = leak_judge(lm, xa, classified, pixels)
        lb, _ = leak_judge(lm, xb, classified, pixels)
        move = math.dist(xa, xb) if xa and xb else 0.0
        rec = {
            'kept_current': ka, 'kept_dual': kb,
            'dropped_by_dual': sorted(set(ka) - set(kb)),
            'readmitted_by_dual': sorted(set(kb) - set(ka)),
            'move_m': round(move, 3),
            'allobs_current': {'max_arcmin': round(ra[0], 2), 'median_m': round(ra[1], 3), 'max_m': round(ra[2], 3)},
            'allobs_dual': {'max_arcmin': round(rb[0], 2), 'median_m': round(rb[1], 3), 'max_m': round(rb[2], 3)},
            'leak_max_m_current': None if la is None else round(la, 3),
            'leak_max_m_new': None if lb is None else round(lb, 3),
            'leak_n': na,
            'z_err_current': None if z_err_a is None else round(z_err_a, 3),
            'z_err_new': None if z_err_b is None else round(z_err_b, 3),
        }
        dump[lm] = rec
        if set(ka) != set(kb) or move > 0.25:
            changed.append((lm, rec))

    # ---- summary ----
    label_a, label_b = (('arcmin', 'dual') if args.ab == 'dual'
                        else ('equal-w', 'sigma-w'))
    print(f"=== A/B bench [{args.ab}] (metric floor {args.floor_m}m) ===")
    print(f"Multi-source LMs triangulated by both: {n_ok}")
    print(f"LMs that change (kept set differs or point moves >0.25m): {len(changed)}")
    if max_m_before and max_m_after:
        print(f"All-observer MAX metric residual (metres), across LMs:")
        print(f"    median  {label_a} {statistics.median(max_m_before):6.3f}  ->  {label_b} {statistics.median(max_m_after):6.3f}")
        print(f"    mean    {label_a} {statistics.mean(max_m_before):6.3f}  ->  {label_b} {statistics.mean(max_m_after):6.3f}")
    # Leak judge: residuals vs class-A (full HUD) observers only.
    lj = [(rec['leak_max_m_current'], rec['leak_max_m_new'])
          for _, rec in dump.items()
          if isinstance(rec, dict) and rec.get('leak_max_m_current') is not None]
    if lj:
        print(f"LEAK-JUDGE (max_m vs class-A observers only, {len(lj)} LMs):")
        print(f"    median  {label_a} {statistics.median(x[0] for x in lj):6.3f}  ->  {label_b} {statistics.median(x[1] for x in lj):6.3f}")
        print(f"    mean    {label_a} {statistics.mean(x[0] for x in lj):6.3f}  ->  {label_b} {statistics.mean(x[1] for x in lj):6.3f}")
    zj = [(rec['z_err_current'], rec['z_err_new'])
          for _, rec in dump.items()
          if isinstance(rec, dict) and rec.get('z_err_current') is not None]
    if zj:
        wins = sum(1 for a, b in zj if b < a - 0.02)
        losses = sum(1 for a, b in zj if b > a + 0.02)
        print(f"Z-JUDGE (|z_solved - z_true| on fixed-z LMs, EXTERNAL ground truth, {len(zj)} LMs):")
        print(f"    median  {label_a} {statistics.median(x[0] for x in zj):6.3f}  ->  {label_b} {statistics.median(x[1] for x in zj):6.3f}")
        print(f"    mean    {label_a} {statistics.mean(x[0] for x in zj):6.3f}  ->  {label_b} {statistics.mean(x[1] for x in zj):6.3f}")
        print(f"    per-LM: {wins} closer, {losses} farther, {len(zj)-wins-losses} ~tied (0.02m dead band)")
    print()

    improved = degraded = 0
    for lm, rec in changed:
        b = rec['allobs_current']['max_m']; a = rec['allobs_dual']['max_m']
        if a < b - 0.05:
            improved += 1
        elif a > b + 0.05:
            degraded += 1
    print(f"Of the {len(changed)} changed LMs (all-observer max_m): "
          f"{improved} improve, {degraded} degrade, {len(changed)-improved-degraded} ~flat")
    print()
    print(f"--- CHANGED LMs (sorted by all-observer max_m improvement, top 40) ---")
    changed.sort(key=lambda x: (x[1]['allobs_dual']['max_m'] - x[1]['allobs_current']['max_m']))
    print(f"    {'maxm_A':>9} {'maxm_B':>9} {'leak_A':>7} {'leak_B':>7} {'move_m':>7}  LM  (dropped / readmitted)")
    for lm, rec in changed[:40]:
        b = rec['allobs_current']['max_m']; a = rec['allobs_dual']['max_m']
        ljc = rec.get('leak_max_m_current'); ljn = rec.get('leak_max_m_new')
        ljc_s = '   n/a' if ljc is None else f"{ljc:7.2f}"
        ljn_s = '   n/a' if ljn is None else f"{ljn:7.2f}"
        drp = ('drop ' + ','.join(rec['dropped_by_dual'])) if rec['dropped_by_dual'] else ''
        rdm = ('  readmit ' + ','.join(rec['readmitted_by_dual'])) if rec['readmitted_by_dual'] else ''
        print(f"    {b:9.3f} {a:9.3f} {ljc_s} {ljn_s} {rec['move_m']:7.2f}  {lm}  [{drp}{rdm}]")
    if len(changed) > 40:
        print(f"    ... and {len(changed) - 40} more (see --json)")

    if args.json:
        with open(args.json, 'w') as f:
            json.dump(dump, f, indent=2, sort_keys=True)
        print(f"\nJSON dump -> {args.json}")


if __name__ == '__main__':
    sys.exit(main())
