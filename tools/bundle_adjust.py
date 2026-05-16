#!/usr/bin/env python3
"""
bundle_adjust.py — Two-pass bundle adjustment.

Pass 1: linear loss (no Huber) — pulls cams/landmarks aggressively toward
        their best positions, including being influenced by outliers. Risky
        if outliers are catastrophic, but we've cleaned the worst already.

Pass 2: huber loss — polish convergence by downweighting remaining outliers.

The hypothesis: bundle_adjust_v2 converges in 2 iterations because Huber
already absorbs the gradient of the worst outliers from iteration 0. By
running linear first, we let the solver actually move toward the optimum
before applying robustness.

Output JSON format compatible with bundle_adjust_apply.py.

Run from gtamaplib-main/:
    python3 tools/bundle_adjust.py
"""

import json
import os
import re
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

# ── Identify leak cameras (auto-detect via source field) ──────────────────────
#
# LEAK   : source matches YYYY-MM-DD (extracted from game engine — locked)
# TRAILER: source starts with "Trailer" (community-calibrated — optimizable)
# other  : community-calibrated — optimizable

LEAK_RE = re.compile(r'\d{4}-\d{2}-\d{2}')

def is_leak(cn):
    src = md.cameras.get(cn, {}).get('source', '') or ''
    return bool(LEAK_RE.match(src))

def is_trailer(cn):
    src = md.cameras.get(cn, {}).get('source', '') or ''
    return src.startswith('Trailer')

LEAK_CAMS = {n for n in md.cameras if is_leak(n)}
print(f"Detected {len(LEAK_CAMS)} LEAK cams (locked), "
      f"{sum(1 for n in md.cameras if is_trailer(n))} TRAILER cams (optimizable)")

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

# ── BA-MIN-OBS-V1 ──
# Filter out cams with <3 observations (under-constrained, would drift).
# Count observations per cam.
_obs_count = {}
for _cn, _ln, _, _ in observations:
    _obs_count[_cn] = _obs_count.get(_cn, 0) + 1
MIN_OBS = 3
_under_constrained = {c for c in used_cams if _obs_count.get(c, 0) < MIN_OBS}
if _under_constrained:
    print(f"  Excluded {len(_under_constrained)} cams with <{MIN_OBS} obs:")
    for _c in sorted(_under_constrained):
        print(f"    {_obs_count.get(_c, 0)} obs  {_c}")
    used_cams = used_cams - _under_constrained
    # Also drop their observations
    observations = [o for o in observations if o[0] not in _under_constrained]
    # Rebuild used_lms in case some LMs only appeared in dropped cams
    used_lms = {o[1] for o in observations if o[1] in candidate_lms}

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

# ── [RIGID-BODY-V1] Rigid body setup ──────────────────────────────────────────
# Some LMs form rigid 3D structures (e.g. Four Seasons Hotel Miami).
# Instead of optimizing each LM xyz independently (3 DOF each), we treat
# the whole structure as 6 DOFs (3 translation + 3 rotation around centroid).
# See tools/RIGID_BODY_DESIGN.md for the full design.
# Hardcoded Four Seasons LM xyz from rlx vendor model (avoids namespace collision)
_FS_LM_MAP = {
    "Four Seasons Hotel Miami (BE)":     (-814.289000, -1306.504000, 263.568000),
    "Four Seasons Hotel Miami (BW)":     (-859.904021, -1289.449056, 263.568000),
    "Four Seasons Hotel Miami (E)":      (-817.997000, -1316.422000, 258.306000),
    "Four Seasons Hotel Miami (NE)":     (-802.124000, -1273.968000, 258.306000),
    "Four Seasons Hotel Miami (NW)":     (-847.739000, -1256.913000, 258.306000),
    "Four Seasons Hotel Miami (SE)":     (-817.997000, -1316.422000, 253.608000),
    "Four Seasons Hotel Miami (SW)":     (-863.612000, -1299.367000, 253.608000),
    "Four Seasons Hotel Miami (W)":      (-817.997000, -1316.422000, 258.306000),
    "Four Seasons Hotel Miami (40NE)":   (-800.000000, -1273.000000, 189.137000),
    "Four Seasons Hotel Miami (40NW)":   (-848.707000, -1254.789000, 189.137000),
    "Four Seasons Hotel Miami (40W)":    (-858.163000, -1280.079000, 189.137000),
    "Four Seasons Hotel Miami (40E)":    (-809.456000, -1298.290000, 189.137000),
    "Four Seasons Hotel Miami (32NE)":   (-800.000000, -1273.000000, 156.901500),
    "Four Seasons Hotel Miami (56NE)":   (-802.124000, -1273.968000, 253.608000),
    "Four Seasons Hotel Miami (HB28SE)": (-816.865000, -1313.394000, 140.784000),
    "Four Seasons Hotel Miami (HB8SE)":  (-815.574000, -1309.942000, 60.196000),
    "Four Seasons Hotel Miami (HB58SE)": (-814.289000, -1306.504000, 263.568000),
    "Four Seasons Hotel Miami (HB58NE)": (-813.449000, -1304.257000, 262.428000),
}
_fs_lms_present = {n: np.array(xyz) for n, xyz in _FS_LM_MAP.items() if n in md.landmarks}
if _fs_lms_present:
    _centroid_fs = np.mean(list(_fs_lms_present.values()), axis=0)
    _local_coords_fs = {n: xyz - _centroid_fs for n, xyz in _fs_lms_present.items()}
    _rigid_bodies = {
        "four_seasons": {
            "centroid": _centroid_fs,
            "lm_local_coords": _local_coords_fs,
        }
    }
    _lm_to_rigid_body = {n: "four_seasons" for n in _fs_lms_present}
    print(f"  [RIGID-BODY-V1] Registered 'four_seasons' with {len(_fs_lms_present)} LMs, "
          f"centroid=({_centroid_fs[0]:.1f},{_centroid_fs[1]:.1f},{_centroid_fs[2]:.1f})")
else:
    _rigid_bodies = {}
    _lm_to_rigid_body = {}
    print(f"  [RIGID-BODY-V1] No FourSeasons LMs in optimizable set; rigid body skipped")

# Remove rigid LMs from lm_idx and opt_lm_names; computed via rigid body params instead
_rigid_lm_names = set(_lm_to_rigid_body.keys())
_free_lm_names = [n for n in opt_lm_names if n not in _rigid_lm_names]
lm_idx = {n: i for i, n in enumerate(_free_lm_names)}
opt_lm_names = _free_lm_names

N_RIGID_BODIES = len(_rigid_bodies)
RIGID_BLOCK = N_RIGID_BODIES * 6
# [RIGID-BODY-V1-EDIT2]: rebind N_LM to reflect the rigid-LM-excluded opt_lm_names
N_LM = len(opt_lm_names)
LM_BLOCK = N_LM * 3
# ── End [RIGID-BODY-V1] setup ─────────────────────────────────────────────────

# ── [RIGID-BODY-V1-EDIT2] helpers ──────────────────────────────────────────────
def _rotation_matrix_xyz(rx, ry, rz):
    """Euler XYZ rotation matrix (Rz @ Ry @ Rx) for world axes."""
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def _transform_rigid_to_world(local_xyz, centroid, params6):
    """Apply rigid transform to a local coord. params6 = (tx, ty, tz, rx, ry, rz)."""
    tx, ty, tz, rx, ry, rz = params6
    R = _rotation_matrix_xyz(rx, ry, rz)
    return R @ local_xyz + centroid + np.array([tx, ty, tz])



# ── BUNDLE-ADJUST-ROLL-V1 ──
# V1-ROLL: each cam now has 7 optimized params (was 6): xyz + yaw + pitch + roll + hfov
N_CAM     = len(opt_cam_names)
N_LM      = len(opt_lm_names)
CAM_BLOCK = N_CAM * 7
N_VARS    = CAM_BLOCK + LM_BLOCK + RIGID_BLOCK  # [RIGID-BODY-V1-EDIT2]
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

# z constraints (item 1 / rlx roadmap) :
# {lm_name: {"type": "fixed", "value": <float>}}
# When a landmark has z_constraint, the solver lets x and y move freely but
# forces z to the fixed value at every residual evaluation.
_z_constraints = {
    n: meta['z_constraint']
    for n, meta in md.landmarks_meta.items()
    if meta.get('z_constraint')
}
n_z_fixed_in_opt = sum(1 for n in opt_lm_names if n in _z_constraints)
if _z_constraints:
    print(f"z constraints: {len(_z_constraints)} landmarks total, "
          f"{n_z_fixed_in_opt} in optimization set (z forced during solve)")

# ── Initial parameter vector ──────────────────────────────────────────────────

cam_params_init = np.zeros((N_CAM, 7))  # V1-ROLL: 7 params (was 6)
n_derived_hfov = 0
for i, cam_name in enumerate(opt_cam_names):
    cam = md.cameras[cam_name]
    xyz = cam.get('xyz') or [0, 0, 0]
    ypr = list(cam.get('ypr') or [0, 0, 0])
    # V1-ROLL: ensure ypr has 3 components (older entries may have just 2)
    while len(ypr) < 3:
        ypr.append(0.0)
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

    # V1-ROLL: roll (ypr[2]) inserted between pitch and hfov
    cam_params_init[i] = [xyz[0], xyz[1], xyz[2], ypr[0], ypr[1], ypr[2], hfov]

if n_derived_hfov:
    print(f"  ℹ Derived hfov from vfov for {n_derived_hfov} camera(s)")

lm_params_init = np.zeros((N_LM, 3))
for i, lm_name in enumerate(opt_lm_names):
    xyz = md.landmarks[lm_name]
    lm_params_init[i] = [xyz[0], xyz[1], xyz[2]]

# [RIGID-BODY-V1-EDIT2]: add rigid body params (init at zero = identity transform)
rigid_params_init = np.zeros(RIGID_BLOCK)
x0 = np.concatenate([cam_params_init.ravel(), lm_params_init.ravel(), rigid_params_init])

# ── Residual function ─────────────────────────────────────────────────────────

_failed_obs_logged = set()

def pixel_residuals(x):
    # V1-ROLL: 7 params per cam (was 6) — roll at cp[5], hfov at cp[6]
    cam_params = x[:CAM_BLOCK].reshape(N_CAM, 7)
    lm_params  = x[CAM_BLOCK:CAM_BLOCK + LM_BLOCK].reshape(N_LM, 3)  # [RIGID-BODY-V1-EDIT2]

    out = np.zeros(n_residuals, dtype=np.float64)

    for k, (cam_name, lm_name, px_marked, py_marked) in enumerate(observations):
        if cam_name in cam_idx:
            cp = cam_params[cam_idx[cam_name]]
            xyz = (float(cp[0]), float(cp[1]), float(cp[2]))
            ypr = (float(cp[3]), float(cp[4]), float(cp[5]))
            hfov = float(cp[6])
        else:
            xyz, ypr, hfov = _leak_params[cam_name]

        if lm_name in lm_idx:
            lp = lm_params[lm_idx[lm_name]]
            z_val = float(lp[2])
            zc = _z_constraints.get(lm_name)
            if zc and zc.get('type') == 'fixed':
                z_val = float(zc['value'])
            lm_xyz = (float(lp[0]), float(lp[1]), z_val)
        elif lm_name in _lm_to_rigid_body:
            # [RIGID-BODY-V1-EDIT2]: compute LM xyz from rigid body 6 DOFs
            body_id = _lm_to_rigid_body[lm_name]
            body_keys = list(_rigid_bodies.keys())
            body_idx = body_keys.index(body_id)
            rigid_offset = CAM_BLOCK + LM_BLOCK + body_idx * 6
            body_params = x[rigid_offset:rigid_offset + 6]
            body = _rigid_bodies[body_id]
            local = body['lm_local_coords'][lm_name]
            world = _transform_rigid_to_world(local, body['centroid'], body_params)
            lm_xyz = (float(world[0]), float(world[1]), float(world[2]))
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
            # V1-ROLL: 7 cols per cam (was 6) — every cam param affects every obs of it
            for col in range(7*c, 7*c + 7):
                J_sparsity[r, col] = 1

    if lm_name in lm_idx:
        l = lm_idx[lm_name]
        for r in rows:
            for col in range(CAM_BLOCK + 3*l, CAM_BLOCK + 3*l + 3):
                J_sparsity[r, col] = 1
    elif lm_name in _lm_to_rigid_body:
        # [RIGID-BODY-V1-EDIT2]: rigid LM depends on 6 body DOFs
        body_keys = list(_rigid_bodies.keys())
        body_idx = body_keys.index(_lm_to_rigid_body[lm_name])
        rigid_offset = CAM_BLOCK + LM_BLOCK + body_idx * 6
        for r in rows:
            for col in range(rigid_offset, rigid_offset + 6):
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
        cam_i = i // 7  # V1-ROLL: 7 params per cam (was 6)
        param = ['x','y','z','yaw','pitch','roll','hfov'][i % 7]
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

print(f"\nRunning two-pass bundle adjustment ({N_VARS} variables, {n_residuals} residuals)...")
print("Method: trust region reflective (TRF) with sparse jacobian")

t_start = time.time()

# ── Pass 1: linear loss — aggressive movement, no robustness ──────────────────
print("\n" + "═" * 78)
print("PASS 1 — linear loss (aggressive convergence, outliers pull full strength)")
print("═" * 78 + "\n")

result1 = least_squares(
    pixel_residuals, x0,
    jac_sparsity=J_sparsity,
    method='trf',
    verbose=2,
    x_scale='jac',
    loss='linear',     # no robustness — let outliers tug
    ftol=1e-7,
    xtol=1e-7,
    gtol=1e-7,
    max_nfev=200,
)

pass1_loss = float(np.sqrt(np.mean(result1.fun**2)))
print(f"\nPass 1 done. RMS: {initial_loss:.4f}' → {pass1_loss:.4f}' "
      f"({(initial_loss-pass1_loss)/initial_loss*100:.1f}% improvement)")
print(f"  nfev: {result1.nfev}, status: {result1.status}")

# ── Pass 2: huber loss — polish, downweight remaining outliers ────────────────
print("\n" + "═" * 78)
print("PASS 2 — huber loss (polish, robust against remaining outliers)")
print("═" * 78 + "\n")

result = least_squares(
    pixel_residuals, result1.x,   # start from pass 1 result
    jac_sparsity=J_sparsity,
    method='trf',
    verbose=2,
    x_scale='jac',
    loss='huber',
    f_scale=10.0,
    ftol=1e-8,
    xtol=1e-8,
    gtol=1e-8,
    max_nfev=500,
)

elapsed = time.time() - t_start

print(f"\n" + "═" * 78)
print(f"Total optimization done in {elapsed/60:.1f} min")
print(f"  Pass 1 (linear): {result1.nfev} nfev, status {result1.status}")
print(f"  Pass 2 (huber) : {result.nfev} nfev, status {result.status}  ({result.message})")

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

# V1-ROLL: 7 params per cam (was 6)
cam_params_final = result.x[:CAM_BLOCK].reshape(N_CAM, 7)
lm_params_final  = result.x[CAM_BLOCK:CAM_BLOCK + LM_BLOCK].reshape(N_LM, 3)  # [RIGID-BODY-V1-EDIT3]

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
        # V1-ROLL: roll is now optimized (cp[5]), hfov moved to cp[6]
        'ypr': [round(float(cp[3]), 4), round(float(cp[4]), 4), round(float(cp[5]), 4)],
        'hfov': round(float(cp[6]), 4),
    }

for i, lm_name in enumerate(opt_lm_names):
    lp = lm_params_final[i]
    # Snap z to fixed value if constrained (single source of truth)
    z_final = float(lp[2])
    zc = _z_constraints.get(lm_name)
    if zc and zc.get('type') == 'fixed':
        z_final = float(zc['value'])
    output['landmarks'][lm_name] = [round(float(lp[0]), 4),
                                    round(float(lp[1]), 4),
                                    round(z_final, 4)]

# [RIGID-BODY-V1-EDIT4]: write rigid body LMs to output
rigid_params_final = result.x[CAM_BLOCK + LM_BLOCK:]
for body_idx, (body_id, body) in enumerate(_rigid_bodies.items()):
    body_params = rigid_params_final[body_idx*6:body_idx*6 + 6]
    tx, ty, tz, rx, ry, rz = body_params
    print(f"  [RIGID-BODY-V1] {body_id} final pose: "
          f"t=({tx:.3f},{ty:.3f},{tz:.3f})m rot=({np.degrees(rx):.2f},{np.degrees(ry):.2f},{np.degrees(rz):.2f})deg")
    for lm_name, local_xyz in body['lm_local_coords'].items():
        world_xyz = _transform_rigid_to_world(local_xyz, body['centroid'], body_params)
        output['landmarks'][lm_name] = [round(float(world_xyz[0]), 4),
                                        round(float(world_xyz[1]), 4),
                                        round(float(world_xyz[2]), 4)]

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bundle_adjust_result.json')
with open(out_path, 'w') as f:
    json.dump(output, f, indent=2)

print(f"\nResults saved to: {out_path}")
print(f"  {len(output['cameras'])} cameras optimized")
print(f"  {len(output['landmarks'])} landmarks optimized")
print("\nTo apply results, run: python3 tools/bundle_adjust_apply.py")
