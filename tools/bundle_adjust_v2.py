#!/usr/bin/env python3
"""
bundle_adjust_v2.py — Global bundle adjustment with least_squares + sparse jacobian.

v2.1 fix: only includes variables that are actually constrained by at least
one observation (avoids zero-column jacobian + 'initial guess out of bounds'
error when scipy auto-scales).

Output JSON format identical to v1 — bundle_adjust_apply.py works as-is.

Run from gtamaplib-main/:
    python3 tools/bundle_adjust_v2.py
"""

import json
import os
import sys
import time

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

print("gtamaplib loaded ✓")

# ── Identify leak cameras (fixed — exact positions from game engine) ──────────

LEAK_CAMS = {
    'Tennis Stadium (4K)', 'Vice Beach (A)', 'Vice Beach (B)',
    'Metro (SE) (A) (4K)', 'Alley (W)', 'Park', 'Port',
    'Tennis Court (SE)', 'Tennis Court (NE)', 'Tennis Court (N)', 'Tennis Court (SW)',
    'AI World Editor Map (4K)',
    'Diner (W) (A)', 'Diner (W) (B)', 'Diner (N)', 'Diner (NW)', 'Diner (NE)',
    'Diner (E)', 'Diner (SE) (A)', 'Diner (SE) (B)', 'Diner (S)', 'Diner (SW)', 'Diner',
    'Gas Station (Lucia)', 'Gas Station (Jason)',
    'Loading Zone near Prison (SW)', 'Loading Zone near Prison (N)',
    'Ocean near Keys (N)', 'Ocean near Keys (E)', 'House with Boat (X)',
    'Highway (NE)', 'Sidewalk (Jason) (E)', 'Sidewalk (Jason) (S)',
    'Welcome Center (E)', 'Welcome Center (W)', 'Police Chase (A)', 'Police Chase (D)',
    'Airport (X)', 'Car Wash', 'Glitch (A)', 'Grassrivers Postcard (X)',
    'Handlebar (SE)', 'Handlebar (SW)', 'Hedge (B) (X)', 'Hotel (W)',
    'Intersection (W)', 'Penthouse (NE)', 'Penthouse (NW)',
    'Penthouse (SE)', 'Penthouse (SW)', 'Pool', 'Rooftop (SE)',
}

# ── Build candidate sets ──────────────────────────────────────────────────────
# These are the cameras and landmarks we *would* optimize if they have
# observations. Final sets are pruned below to only what's constrained.

candidate_cams = {
    n for n in md.pixels
    if n not in LEAK_CAMS and md.cameras.get(n, {}).get('xyz')
}

candidate_lms = {
    n for n, data in md.landmarks_meta.items()
    if md.landmarks.get(n) is not None
    and not all(s in LEAK_CAMS for s in data.get('source_cameras', []))
    and data.get('source_cameras')
}

# ── Build observation list ────────────────────────────────────────────────────
# Track which cams/lms are actually touched by at least one observation.

observations = []
used_cams = set()
used_lms  = set()
n_skipped_constant = 0
n_skipped_no_lm    = 0

for cam_name, cam_pixels in md.pixels.items():
    cam_is_candidate = cam_name in candidate_cams
    cam_is_leak      = cam_name in LEAK_CAMS
    if not cam_is_candidate and not cam_is_leak:
        continue

    for lm_name, pixel in cam_pixels.items():
        if md.landmarks.get(lm_name) is None:
            n_skipped_no_lm += 1
            continue

        lm_is_candidate = lm_name in candidate_lms

        if not cam_is_candidate and not lm_is_candidate:
            n_skipped_constant += 1
            continue

        observations.append((cam_name, lm_name, float(pixel[0]), float(pixel[1])))
        if cam_is_candidate: used_cams.add(cam_name)
        if lm_is_candidate:  used_lms.add(lm_name)

# Prune to constrained-only
opt_cam_names = sorted(used_cams)
opt_lm_names  = sorted(used_lms)
n_dropped_cams = len(candidate_cams - used_cams)
n_dropped_lms  = len(candidate_lms - used_lms)

print(f"Optimizable cameras  : {len(opt_cam_names)}  "
      f"(dropped {n_dropped_cams} unconstrained)")
print(f"Optimizable landmarks: {len(opt_lm_names)}  "
      f"(dropped {n_dropped_lms} unconstrained)")
print(f"Fixed landmarks      : {len(md.landmarks) - len(opt_lm_names)}")
print(f"Observations         : {len(observations)}  "
      f"({n_skipped_constant} constant skipped, {n_skipped_no_lm} missing-lm skipped)")

cam_idx = {n: i for i, n in enumerate(opt_cam_names)}
lm_idx  = {n: i for i, n in enumerate(opt_lm_names)}

N_CAM     = len(opt_cam_names)
N_LM      = len(opt_lm_names)
CAM_BLOCK = N_CAM * 6
N_VARS    = CAM_BLOCK + N_LM * 3
n_obs       = len(observations)
n_residuals = n_obs * 2
print(f"Variables : {N_VARS}")
print(f"Residuals : {n_residuals}")

# ── Cache camera objects + leak/fixed params ──────────────────────────────────

_cam_cache = {n: ml.get_camera(n)
              for n in (set(md.pixels.keys()) & (used_cams | LEAK_CAMS))}

_leak_params = {}
for cam_name in LEAK_CAMS:
    if cam_name not in md.cameras:
        continue
    d = md.cameras[cam_name]
    xyz = d.get('xyz') or (0, 0, 0)
    ypr = d.get('ypr') or (0, 0, 0)
    fov = d.get('fov') or (60, None)
    size = d.get('size') or (1920, 1080)
    hfov = fov[0]
    if hfov is None:
        hfov = ml.get_hfov(fov[1], size) if fov[1] is not None else 60.0
    _leak_params[cam_name] = (tuple(xyz), tuple(ypr), float(hfov))

_fixed_lm_xyz = {n: tuple(md.landmarks[n])
                 for n in md.landmarks
                 if n not in lm_idx and md.landmarks.get(n) is not None}

# ── Initial parameter vector ──────────────────────────────────────────────────

cam_params_init = np.zeros((N_CAM, 6))
n_derived_hfov = 0
for i, cam_name in enumerate(opt_cam_names):
    cam = md.cameras[cam_name]
    xyz = cam.get('xyz') or [0, 0, 0]
    ypr = cam.get('ypr') or [0, 0, 0]
    fov = cam.get('fov') or [60, None]
    size = cam.get('size') or [1920, 1080]

    hfov = fov[0]
    if hfov is None:
        # Derive hfov from vfov + aspect ratio
        if fov[1] is None:
            print(f"  ⚠ {cam_name}: both hfov and vfov are None — using 60° default")
            hfov = 60.0
        else:
            hfov = ml.get_hfov(fov[1], size)
            n_derived_hfov += 1

    cam_params_init[i] = [xyz[0], xyz[1], xyz[2], ypr[0], ypr[1], hfov]

if n_derived_hfov:
    print(f"  ℹ Derived hfov from vfov for {n_derived_hfov} camera(s)")

lm_params_init = np.zeros((N_LM, 3))
for i, lm_name in enumerate(opt_lm_names):
    xyz = md.landmarks[lm_name]
    lm_params_init[i] = [xyz[0], xyz[1], xyz[2]]

x0 = np.concatenate([cam_params_init.ravel(), lm_params_init.ravel()])

# ── Residual function ─────────────────────────────────────────────────────────

_failed_obs_logged = set()

def pixel_residuals(x):
    cam_params = x[:CAM_BLOCK].reshape(N_CAM, 6)
    lm_params  = x[CAM_BLOCK:].reshape(N_LM, 3)

    out = np.zeros(n_residuals, dtype=np.float64)

    for k, (cam_name, lm_name, px_marked, py_marked) in enumerate(observations):
        if cam_name in cam_idx:
            cp = cam_params[cam_idx[cam_name]]
            xyz = (float(cp[0]), float(cp[1]), float(cp[2]))
            ypr = (float(cp[3]), float(cp[4]), 0.0)
            hfov = float(cp[5])
        else:
            xyz, ypr, hfov = _leak_params[cam_name]

        if lm_name in lm_idx:
            lp = lm_params[lm_idx[lm_name]]
            lm_xyz = (float(lp[0]), float(lp[1]), float(lp[2]))
        else:
            lm_xyz = _fixed_lm_xyz[lm_name]

        cam = _cam_cache[cam_name]
        try:
            cam.set_xyz(xyz)
            cam.set_ypr(ypr)
            cam.set_fov((hfov, None))
            proj = cam.get_pixel(lm_xyz)
            if proj is None:
                if k not in _failed_obs_logged:
                    _failed_obs_logged.add(k)
                continue
            out[2*k]   = (float(proj[0]) - px_marked) * hfov / cam.w * 60.0
            out[2*k+1] = (float(proj[1]) - py_marked) * cam.vfov / cam.h * 60.0
        except Exception:
            if k not in _failed_obs_logged:
                _failed_obs_logged.add(k)
            continue

    return out

# ── Sparse jacobian sparsity pattern ──────────────────────────────────────────

print("\nBuilding sparse jacobian pattern...")
J_sparsity = lil_matrix((n_residuals, N_VARS), dtype=np.int8)

for k, (cam_name, lm_name, _, _) in enumerate(observations):
    rows = (2*k, 2*k + 1)

    if cam_name in cam_idx:
        c = cam_idx[cam_name]
        for r in rows:
            for col in range(6*c, 6*c + 6):
                J_sparsity[r, col] = 1

    if lm_name in lm_idx:
        l = lm_idx[lm_name]
        for r in rows:
            for col in range(CAM_BLOCK + 3*l, CAM_BLOCK + 3*l + 3):
                J_sparsity[r, col] = 1

J_sparsity = J_sparsity.tocsr()
density = J_sparsity.nnz / (n_residuals * N_VARS) * 100
print(f"Jacobian: {n_residuals} x {N_VARS}, {J_sparsity.nnz} non-zeros "
      f"({density:.4f}% dense)")

# ── Sanity check: every column should have at least one non-zero ──────────────

col_nnz = np.diff(J_sparsity.tocsc().indptr)
zero_cols = np.where(col_nnz == 0)[0]
if len(zero_cols) > 0:
    print(f"⚠ {len(zero_cols)} unconstrained variable columns — pruning bug")
    sys.exit(1)
else:
    print("✓ All variables are constrained")

# ── Initial loss ──────────────────────────────────────────────────────────────

print("\nComputing initial residuals...")
t0 = time.time()
r0 = pixel_residuals(x0)
print(f"  ({time.time()-t0:.1f}s for one residual eval)")
if _failed_obs_logged:
    print(f"  ⚠ {len(_failed_obs_logged)} observations failed projection (treated as 0)")
initial_loss = float(np.sqrt(np.mean(r0**2)))
print(f"Initial RMS loss: {initial_loss:.4f} arcmin")

_failed_obs_logged.clear()

# ── Diagnostic on x0 ──────────────────────────────────────────────────────────

print(f"\nx0 stats: shape={x0.shape}, dtype={x0.dtype}")
print(f"  min={x0.min():.4e}, max={x0.max():.4e}")
print(f"  any NaN: {np.any(np.isnan(x0))}")
print(f"  any Inf: {np.any(np.isinf(x0))}")

def _describe_idx(i):
    if i < CAM_BLOCK:
        cam_i = i // 6
        param = ['x','y','z','yaw','pitch','hfov'][i % 6]
        return f"cam '{opt_cam_names[cam_i]}'.{param}"
    else:
        lm_i = (i - CAM_BLOCK) // 3
        coord = ['x','y','z'][(i - CAM_BLOCK) % 3]
        return f"lm '{opt_lm_names[lm_i]}'.{coord}"

bad_idx = np.where(~np.isfinite(x0))[0]
if len(bad_idx) > 0:
    print(f"  ⚠ {len(bad_idx)} non-finite values in x0:")
    for i in bad_idx[:30]:
        print(f"      [{i}] {_describe_idx(i)} = {x0[i]}")
    if len(bad_idx) > 30:
        print(f"      ... and {len(bad_idx)-30} more")
    print("\nFix the corrupted entries in cameras.json or landmarks.json and re-run.")
    sys.exit(1)
else:
    print("  ✓ All values finite")

# ── Run bundle adjustment ─────────────────────────────────────────────────────

print(f"\nRunning bundle adjustment ({N_VARS} variables, {n_residuals} residuals)...")
print("Method: trust region reflective (TRF) with sparse jacobian\n")

t_start = time.time()
result = least_squares(
    pixel_residuals, x0,
    jac_sparsity=J_sparsity,
    method='trf',
    verbose=2,
    x_scale='jac',
    loss='huber',      # robust loss — prevents single outliers from dominating
    f_scale=10.0,      # arcmin threshold above which huber kicks in (1px ~= 2')
    ftol=1e-8,
    xtol=1e-8,
    gtol=1e-8,
    max_nfev=500,      # full run — TRF will converge before hitting this
)
elapsed = time.time() - t_start

print(f"\nOptimization done in {elapsed/60:.1f} min")
print(f"  status: {result.status}  ({result.message})")
print(f"  nfev: {result.nfev}, njev: {result.njev}")

final_loss = float(np.sqrt(np.mean(result.fun**2)))
improvement = (initial_loss - final_loss) / initial_loss * 100
print(f"\nFinal RMS loss: {final_loss:.4f} arcmin")
print(f"Improvement: {improvement:.1f}%")

# ── Outlier analysis ──────────────────────────────────────────────────────────
# After convergence, identify the observations with the largest remaining
# residuals. These are the pixels you should review in the calibration tool —
# either the pixel was mistakenly marked, or there's a real geometric problem
# (e.g. occluded landmark, wrong identification).

print("\n" + "─" * 78)
print("OUTLIER ANALYSIS — top 20 worst observations after optimization")
print("─" * 78)

# Per-observation error (arcmin): sqrt(dx² + dy²) from the 2 residuals
res_per_obs = np.sqrt(result.fun[0::2]**2 + result.fun[1::2]**2)

# Sort descending
worst_idx = np.argsort(res_per_obs)[::-1]

# Save full ranking for later review
outlier_report = []
for k in worst_idx:
    cam_name, lm_name, px, py = observations[k]
    outlier_report.append({
        'rank': len(outlier_report) + 1,
        'cam': cam_name,
        'landmark': lm_name,
        'marked_pixel': [round(px, 1), round(py, 1)],
        'error_arcmin': round(float(res_per_obs[k]), 2),
        'cam_optimized': cam_name in cam_idx,
        'lm_optimized': lm_name in lm_idx,
    })

# Print top 20 to stdout
print(f"{'#':>3}  {'error':>8}  {'cam':<35} {'landmark':<35}")
print("─" * 78)
for entry in outlier_report[:20]:
    flag = ''
    if not entry['cam_optimized']: flag += '  [LEAK CAM]'
    if not entry['lm_optimized']:  flag += '  [FIXED LM]'
    print(f"{entry['rank']:>3}  {entry['error_arcmin']:>6.1f}'   "
          f"{entry['cam'][:35]:<35} {entry['landmark'][:35]:<35}{flag}")

# Distribution stats
p50 = float(np.percentile(res_per_obs, 50))
p90 = float(np.percentile(res_per_obs, 90))
p99 = float(np.percentile(res_per_obs, 99))
print()
print(f"Per-observation error distribution (arcmin):")
print(f"  p50 = {p50:6.2f}    p90 = {p90:6.2f}    p99 = {p99:6.2f}    max = {res_per_obs.max():.2f}")
print(f"  obs > 50 arcmin: {int((res_per_obs > 50).sum())}")
print(f"  obs > 20 arcmin: {int((res_per_obs > 20).sum())}")
print(f"  obs > 10 arcmin: {int((res_per_obs > 10).sum())}")
print(f"  obs <  5 arcmin: {int((res_per_obs <  5).sum())} / {len(res_per_obs)}")

# ── Save results (v1-compatible format) ───────────────────────────────────────

cam_params_final = result.x[:CAM_BLOCK].reshape(N_CAM, 6)
lm_params_final  = result.x[CAM_BLOCK:].reshape(N_LM, 3)

output = {
    'initial_loss': round(initial_loss, 4),
    'final_loss': round(final_loss, 4),
    'improvement_pct': round(improvement, 1),
    'cameras': {},
    'landmarks': {},
    'outliers': outlier_report[:50],  # top 50 for review
    'distribution_arcmin': {
        'p50': round(p50, 2),
        'p90': round(p90, 2),
        'p99': round(p99, 2),
        'max': round(float(res_per_obs.max()), 2),
        'count_over_50': int((res_per_obs > 50).sum()),
        'count_over_20': int((res_per_obs > 20).sum()),
        'count_over_10': int((res_per_obs > 10).sum()),
        'count_under_5': int((res_per_obs <  5).sum()),
        'total': len(res_per_obs),
    },
}

for i, cam_name in enumerate(opt_cam_names):
    cp = cam_params_final[i]
    output['cameras'][cam_name] = {
        'xyz': [round(float(v), 4) for v in cp[:3]],
        'ypr': [round(float(cp[3]), 4), round(float(cp[4]), 4), 0.0],
        'hfov': round(float(cp[5]), 4),
    }

for i, lm_name in enumerate(opt_lm_names):
    lp = lm_params_final[i]
    output['landmarks'][lm_name] = [round(float(v), 4) for v in lp]

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bundle_adjust_result.json')
with open(out_path, 'w') as f:
    json.dump(output, f, indent=2)

print(f"\nResults saved to: {out_path}")
print(f"  {len(output['cameras'])} cameras optimized")
print(f"  {len(output['landmarks'])} landmarks optimized")
print("\nTo apply results, run: python3 tools/bundle_adjust_apply.py")
