#!/usr/bin/env python3
"""
bundle_adjust_weighted.py — Phase C of the T3 intake pipeline.

Tier-aware global bundle adjustment with movement barriers:

- Reads tools/generated/confidence_tiers.json (Phase A output) to weight each
  observation by min(cam_tier_weight, lm_tier_weight). Trustworthy obs dominate
  the optimization; wobbly obs barely contribute.

- Adds movement barrier residuals on each cam: quadratic penalty if xyz/ypr/fov
  drift more than the tier-specific budget. Anchor/high cams are locked tight
  (already well calibrated); medium/low/unverified have more room. Leak cams
  are fully locked (not optimized).

- LMs also locked in proportion to their tier (anchor LMs barely move).

- Two-pass: linear → huber, like bundle_adjust.py.

- Output JSON compatible with bundle_adjust_apply.py existant.

Tier weights (per refine_cam_full):
    anchor    = 15.0
    high      =  7.5
    medium    =  2.0
    low       =  0.5
    unverified=  0.1
    unknown   =  1.0  (fallback)

Combination rule: per observation, weight = min(cam_w, lm_w).

Movement budget per tier (xyz_m, ypr_deg, fov_deg):
    anchor    = ( 1.0,  0.2, 0.2)   # barely budge
    high      = ( 5.0,  0.5, 0.5)
    medium    = (20.0,  2.0, 1.0)
    low       = (50.0,  5.0, 2.0)
    unverified= (200., 15.0, 5.0)

The penalty is quadratic OUTSIDE the budget (soft hinge):
    pen(delta) = max(0, |delta| - budget) * stiffness

Run from gtamaplib-main/:
    python3 tools/bundle_adjust_weighted.py
"""

import argparse
import json
import math
import os
import re
import sys
import time

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
from scipy.spatial.transform import Rotation as Rot

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
TIERS_PATH = os.path.join(TOOLS_DIR, 'generated', 'confidence_tiers.json')
OUT_PATH   = os.path.join(TOOLS_DIR, 'bundle_adjust_result.json')

# ── Tier definitions ─────────────────────────────────────────────────────────

TIER_WEIGHTS = {
    'anchor':     15.0,
    'high':        7.5,
    'medium':      2.0,
    'low':         0.5,
    'unverified':  0.1,
    'unknown':     1.0,
}

# (xyz_budget_m, ypr_budget_deg, fov_budget_deg, stiffness)
# Stiffness chosen so a 2× over-budget movement contributes roughly the same
# weight as a 1-arcmin observation residual at unit weight.
TIER_MOVEMENT_BUDGET = {
    'anchor':     ( 1.0,  0.2, 0.2, 10.0),
    'high':       ( 5.0,  0.5, 0.5,  5.0),
    'medium':     (20.0,  2.0, 1.0,  2.0),
    'low':        (50.0,  5.0, 2.0,  1.0),
    'unverified': (200., 15.0, 5.0,  0.5),
    'unknown':    (20.0,  2.0, 1.0,  2.0),
}

# Same idea for LM movement (in meters only — LMs are points)
TIER_LM_BUDGET_M = {
    'anchor':       1.0,
    'high':         5.0,
    'medium':      20.0,
    'low':         50.0,
    'unverified': 200.0,
    'unknown':     20.0,
}
TIER_LM_STIFFNESS = {
    'anchor':     10.0,
    'high':        5.0,
    'medium':      2.0,
    'low':         1.0,
    'unverified':  0.5,
    'unknown':     2.0,
}


# ── Args ────────────────────────────────────────────────────────────────────

ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--max-iter', type=int, default=50,
                help='Max iterations per pass (default: 50)')
ap.add_argument('--no-huber', action='store_true',
                help='Skip pass 2 (huber). Pass 1 is always linear.')
ap.add_argument('--no-barriers', action='store_true',
                help='Disable movement barriers (debug only).')
ap.add_argument('--dry-run', action='store_true',
                help="Don't write bundle_adjust_result.json")
ap.add_argument('--cleanup', action='store_true',
                help="V3 cleanup: exclude junk cams (low/unverified + median>30') "
                     "weak LMs (low/unverified + <=1 good obs) and broken "
                     "triangulations (free LM, median>60'); freeze leak-anchored "
                     "and anchor-tier LMs (their rays become anchors)")
args = ap.parse_args()


# ── Load tiers ──────────────────────────────────────────────────────────────

if not os.path.exists(TIERS_PATH):
    print(f"ERROR: {TIERS_PATH} not found.")
    print("Run: python3 tools/compute_confidence_tiers.py")
    sys.exit(1)

with open(TIERS_PATH) as f:
    tiers = json.load(f)
# Cameras and landmarks have form {name: {tier: 'high', ...}}; extract just .tier
cam_tier = {n: (d.get('tier') if isinstance(d, dict) else d) for n, d in tiers['cameras'].items()}
lm_tier  = {n: (d.get('tier') if isinstance(d, dict) else d) for n, d in tiers['landmarks'].items()}

print(f"Loaded tiers: {len(cam_tier)} cams, {len(lm_tier)} LMs")


# ── Identify cams with HUD-locked xyz (excluded from optimization) ──────────
#
# V2 audit-driven. See bundle_adjust.py for the full rationale.

from leak_cam_audit import (
    is_triangulation_trusted,
    is_excluded,
    legacy_cam_names,
    get_class,
    class_b_roll_prior_sigma,
    ROLL_PRIOR_WEIGHT,
)

LOCKED_XYZ_CAMS = {n for n in md.cameras if is_triangulation_trusted(n, cameras=md.cameras)}
EXCLUDED_CAMS   = {n for n in md.cameras if is_excluded(n, cameras=md.cameras)}

_legacy = legacy_cam_names(md.cameras)
print(f"Detected {len(LOCKED_XYZ_CAMS)} cams with HUD-locked xyz (excluded from BA)")
if _legacy:
    print(f"  (Includes {len(_legacy)} legacy date-source cam(s) without audit entry)")
if EXCLUDED_CAMS:
    print(f"  Excluded (class X): {sorted(EXCLUDED_CAMS)}")


# ── Build candidate sets ────────────────────────────────────────────────────

# CLEANUP_V3_MARKER — junk-cam / weak-LM / broken-LM exclusion + frozen anchor LMs
JUNK_CAMS = set()
WEAK_LMS = set()
FROZEN_LMS = set()
if args.cleanup:
    _cmeta = tiers['cameras']
    _lmeta = tiers['landmarks']
    JUNK_CAMS = {n for n, d in _cmeta.items()
                 if d.get('tier') in ('low', 'unverified')
                 and (d.get('median_res_all') or 0) > 30.0
                 and n not in LOCKED_XYZ_CAMS}
    _good_obs = {}
    for _cam, _d in md.pixels.items():
        if _cam in JUNK_CAMS:
            continue
        if cam_tier.get(_cam) in ('anchor', 'high', 'medium') or _cam in LOCKED_XYZ_CAMS:
            for _lm in _d:
                _good_obs[_lm] = _good_obs.get(_lm, 0) + 1
    WEAK_LMS = {n for n, d in _lmeta.items()
                if d.get('tier') in ('low', 'unverified')
                and _good_obs.get(n, 0) <= 1}
    _frozen_pre = {n for n, d in _lmeta.items()
                   if md.landmarks.get(n) is not None
                   and (d.get('n_leak_sources', 0) >= 2 or d.get('tier') == 'anchor')}
    BROKEN_LMS = {n for n, d in _lmeta.items()
                  if md.landmarks.get(n) is not None
                  and n not in WEAK_LMS
                  and n not in _frozen_pre
                  and (d.get('median_res') or 0) > 60.0}
    if BROKEN_LMS:
        print(f"[cleanup] broken triangulations excluded (retriangulate these, not BA):")
        for _n in sorted(BROKEN_LMS):
            print(f"    {_n}  (median {_lmeta[_n].get('median_res')}')")
    WEAK_LMS |= BROKEN_LMS
    FROZEN_LMS = _frozen_pre
    print(f"[cleanup] junk cams excluded (param+obs): {len(JUNK_CAMS)}")
    print(f"[cleanup] weak LMs excluded (param+obs):  {len(WEAK_LMS)}")
    print(f"[cleanup] frozen LMs (xyz constant, rays kept): {len(FROZEN_LMS)}")

candidate_cams = {
    n for n in md.pixels
    if n not in LOCKED_XYZ_CAMS
    and n not in EXCLUDED_CAMS
    and n not in JUNK_CAMS
    and md.cameras.get(n, {}).get('xyz')
}

candidate_lms = {
    n for n, data in md.landmarks_meta.items()
    if md.landmarks.get(n) is not None
    and not all(s in LOCKED_XYZ_CAMS for s in (data.get('source_cameras') or []))
    and data.get('source_cameras')
    and n not in WEAK_LMS
    and n not in FROZEN_LMS
    # Reject LMs with aberrant xyz (e.g. failed triangulations at e15+ meters)
    and max(abs(x) for x in md.landmarks[n]) < 1e6
}

print(f"Candidate: {len(candidate_cams)} cams, {len(candidate_lms)} LMs")


# ── Build observation list ──────────────────────────────────────────────────

observations = []
used_cams = set()
used_lms = set()

for cam_name, lm_pixels in md.pixels.items():
    if cam_name not in md.cameras: continue
    if md.cameras[cam_name].get('xyz') is None: continue
    if cam_name in EXCLUDED_CAMS: continue
    if cam_name in JUNK_CAMS: continue
    cam_xyz_is_locked = cam_name in LOCKED_XYZ_CAMS
    cam_t = cam_tier.get(cam_name, 'unknown')
    cam_w = TIER_WEIGHTS.get(cam_t, 1.0)
    cam_xyz_arr = np.array(md.cameras[cam_name]['xyz'])
    for lm_name, pixel in lm_pixels.items():
        if lm_name in WEAK_LMS: continue
        if lm_name not in candidate_lms and lm_name not in md.landmarks: continue
        if md.landmarks.get(lm_name) is None: continue
        if cam_xyz_is_locked and lm_name not in candidate_lms: continue
        # Skip degenerate near-cam observations (constraint is too sensitive)
        lm_xyz_arr = np.array(md.landmarks[lm_name])
        dist = np.linalg.norm(lm_xyz_arr - cam_xyz_arr)
        if dist < 50.0:
            continue
        lm_t = lm_tier.get(lm_name, 'unknown')
        lm_w = TIER_WEIGHTS.get(lm_t, 1.0)
        if cam_xyz_is_locked:
            # leak ray dominates: HUD-locked pose is ground truth, so the obs
            # weight must not be capped by the LM's tier (min() let medium
            # cams contest leak rays on shared LMs -> Pool/Motel massacre).
            obs_w = TIER_WEIGHTS['anchor']
        else:
            obs_w = min(cam_w, lm_w)
        observations.append({
            'cam': cam_name,
            'lm': lm_name,
            'pixel': pixel,
            'weight': obs_w,
            'cam_tier': cam_t,
            'lm_tier': lm_t,
        })
        if not cam_xyz_is_locked:
            used_cams.add(cam_name)
        used_lms.add(lm_name)

# Only optimize cams/lms that have observations AND are candidates
_cam_cls = {n: get_class(n, cameras=md.cameras) for n in (used_cams & candidate_cams)}
opt_cams = sorted(used_cams & candidate_cams)
opt_lms = sorted(used_lms & candidate_lms)

print(f"Observations: {len(observations)}")
print(f"Optimizing: {len(opt_cams)} cams, {len(opt_lms)} LMs")

# Tier distribution
from collections import Counter
cam_tier_dist = Counter(cam_tier.get(c, 'unknown') for c in opt_cams)
lm_tier_dist = Counter(lm_tier.get(l, 'unknown') for l in opt_lms)
print(f"  Cam tiers: {dict(cam_tier_dist)}")
print(f"  LM  tiers: {dict(lm_tier_dist)}")


# ── Param vector layout ─────────────────────────────────────────────────────
# [cam0_x, cam0_y, cam0_z, cam0_yaw, cam0_pitch, cam0_roll, cam0_hfov,
#  cam1_x, ... 7 params per cam, then 3 params per LM (x,y,z)]

CAM_PARAMS = 7
LM_PARAMS = 3

cam_idx = {n: i for i, n in enumerate(opt_cams)}
lm_idx = {n: i for i, n in enumerate(opt_lms)}

n_cam_params = len(opt_cams) * CAM_PARAMS
n_lm_params = len(opt_lms) * LM_PARAMS
n_total = n_cam_params + n_lm_params

def pack_initial():
    p = np.zeros(n_total)
    for n in opt_cams:
        i = cam_idx[n] * CAM_PARAMS
        c = md.cameras[n]
        p[i:i+3] = c['xyz']
        p[i+3:i+6] = c['ypr']
        p[i+6] = CAM_HFOV_INIT[n]
    for n in opt_lms:
        i = n_cam_params + lm_idx[n] * LM_PARAMS
        p[i:i+3] = md.landmarks[n]
    return p

def get_cam_fov(name):
    """Get (hfov, vfov) in degrees, deriving whichever is None from the other + aspect."""
    c = md.cameras[name]
    fov = c.get('fov') or [None, None]
    hfov, vfov = fov[0], fov[1]
    w, h = c['size']
    aspect = w / h
    if hfov is None and vfov is not None:
        # Derive hfov from vfov
        hfov = math.degrees(2 * math.atan(math.tan(math.radians(vfov)/2) * aspect))
    elif vfov is None and hfov is not None:
        vfov = math.degrees(2 * math.atan(math.tan(math.radians(hfov)/2) / aspect))
    elif hfov is None and vfov is None:
        return None, None
    return hfov, vfov

CAM_HFOV_INIT = {n: get_cam_fov(n)[0] for n in md.cameras if get_cam_fov(n)[0] is not None}


def get_cam_params(p, name):
    """Return (xyz, ypr, hfov) for cam, either from p (if optimized) or md (if leak/fixed)."""
    if name in cam_idx:
        i = cam_idx[name] * CAM_PARAMS
        xyz = p[i:i+3]
        ypr = p[i+3:i+6]
        hfov = p[i+6]
    else:
        c = md.cameras[name]
        xyz = np.array(c['xyz'])
        ypr = np.array(c['ypr'])
        hfov = CAM_HFOV_INIT.get(name)
    return xyz, ypr, hfov

# LMs with a fixed z_constraint are pinned in the OPTIMIZER (not just at
# write time): md.update_landmark snaps z on write, so optimizing a free z
# means converging on geometry that will never reach the disk (2026-06-10).
LM_FIXED_Z = {
    n: float(m["z_constraint"]["value"])
    for n, m in md.landmarks_meta.items()
    if (m or {}).get("z_constraint") and m["z_constraint"].get("type") == "fixed"
}

def get_lm_xyz(p, name):
    if name in lm_idx:
        i = n_cam_params + lm_idx[name] * LM_PARAMS
        xyz = p[i:i+3]
        if name in LM_FIXED_Z:
            xyz = np.array([xyz[0], xyz[1], LM_FIXED_Z[name]])
        return xyz
    return np.array(md.landmarks[name])


# ── Initial params + cache of starting state for barriers ───────────────────

p0 = pack_initial()
cam_init = {n: (np.array(md.cameras[n]['xyz']),
                np.array(md.cameras[n]['ypr']),
                CAM_HFOV_INIT[n]) for n in opt_cams}
lm_init = {n: np.array(md.landmarks[n]) for n in opt_lms}


# ── Residual function ──────────────────────────────────────────────────────

def project_one(xyz_cam, ypr, hfov, vfov, w, h, lm_xyz):
    """Mimic gtamaplib's get_pixel, returns (px, py) or None if behind cam."""
    q = Rot.from_euler("ZXY", ypr, degrees=True)
    delta = lm_xyz - xyz_cam
    cam_dir = q.inv().apply(delta)
    if cam_dir[1] <= 0:
        return None
    tan_h = math.tan(math.radians(hfov)/2)
    tan_v = math.tan(math.radians(vfov)/2)
    ndc_x = cam_dir[0] / cam_dir[1] / tan_h
    ndc_y = cam_dir[2] / cam_dir[1] / tan_v
    px = (ndc_x + 1) * 0.5 * w - 0.5
    py = (1 - (ndc_y + 1) * 0.5) * h - 0.5
    return px, py

CAM_SIZES = {n: tuple(md.cameras[n]['size']) for n in md.cameras}

def compute_residuals(p):
    """Return flat residual vector: [obs residuals..., barrier residuals...]"""
    res = []
    # Observation residuals (pixel errors, weighted)
    for obs in observations:
        cam_name = obs['cam']
        lm_name = obs['lm']
        xyz, ypr, hfov = get_cam_params(p, cam_name)
        w, h = CAM_SIZES[cam_name]
        aspect = w / h
        vfov = math.degrees(2*math.atan(math.tan(math.radians(hfov)/2)/aspect))
        lm_xyz = get_lm_xyz(p, lm_name)
        proj = project_one(xyz, ypr, hfov, vfov, w, h, lm_xyz)
        if proj is None:
            # Behind cam — skip (contribute 0); the LM is geometrically infeasible
            # for this cam, so let other obs constrain it
            res.append(0.0)
            res.append(0.0)
        else:
            mx, my = obs['pixel']
            sw = math.sqrt(obs['weight'])
            res.append((proj[0] - mx) * sw)
            res.append((proj[1] - my) * sw)

    # Barrier residuals (one set per opt cam, one per opt LM)
    if not args.no_barriers:
        for n in opt_cams:
            xyz, ypr, hfov = get_cam_params(p, n)
            init_xyz, init_ypr, init_hfov = cam_init[n]
            tier = cam_tier.get(n, 'unknown')
            xyz_budget, ypr_budget, fov_budget, stiff = TIER_MOVEMENT_BUDGET.get(tier, TIER_MOVEMENT_BUDGET['unknown'])
            # xyz hinge (per axis)
            for d in (xyz - init_xyz):
                excess = max(0.0, abs(d) - xyz_budget)
                res.append(excess * stiff)
            # yaw/pitch hinge (toward init); roll uses a soft prior toward 0
            # instead (game cams have ~0 roll; a hinge-to-init would freeze any
            # inherited noise). Same residual count (3) -> sparsity unchanged.
            # Residual sqrt(W)*roll/sigma -> W*(roll/sigma)^2 in the LS loss,
            # same scale as refine_cam_ypr & refine_cam_full.
            _rsig = class_b_roll_prior_sigma() * (1.5 if _cam_cls.get(n) == 'D_no_ground_truth' else 1.0)
            for _axis, d in enumerate(ypr - init_ypr):
                if _axis == 2:
                    res.append(math.sqrt(ROLL_PRIOR_WEIGHT) * ypr[2] / _rsig)
                else:
                    dd = ((d + 180) % 360) - 180
                    excess = max(0.0, abs(dd) - ypr_budget)
                    res.append(excess * stiff)
            # hfov hinge
            excess = max(0.0, abs(hfov - init_hfov) - fov_budget)
            res.append(excess * stiff)

        for n in opt_lms:
            xyz = get_lm_xyz(p, n)
            init_xyz = lm_init[n]
            tier = lm_tier.get(n, 'unknown')
            budget = TIER_LM_BUDGET_M.get(tier, TIER_LM_BUDGET_M['unknown'])
            stiff = TIER_LM_STIFFNESS.get(tier, TIER_LM_STIFFNESS['unknown'])
            # Hinge on total euclidean distance from init
            d = np.linalg.norm(xyz - init_xyz)
            excess = max(0.0, d - budget)
            res.append(excess * stiff)

    return np.array(res)


# ── Run optimization ────────────────────────────────────────────────────────

def report_obs_rms(p, label):
    res = compute_residuals(p)
    # Recover just observation residuals (first 2*N_obs entries)
    n_obs = 2 * len(observations)
    obs_res = res[:n_obs]
    # Sum of squares / number of pixel-residual-pairs, square root for RMS
    # But these are weighted residuals — for human-readable RMS, divide by sqrt(weight)
    raw_px_err = []
    for i, obs in enumerate(observations):
        sw = math.sqrt(obs['weight']) if obs['weight'] > 0 else 1.0
        rx = obs_res[2*i] / sw
        ry = obs_res[2*i + 1] / sw
        raw_px_err.append(math.sqrt(rx*rx + ry*ry))
    raw_px_err = np.array(raw_px_err)
    rms = math.sqrt(np.mean(raw_px_err**2))
    p95 = np.percentile(raw_px_err, 95)
    print(f"  [{label}] pixel RMS: {rms:.2f}px   p95: {p95:.2f}px   max: {raw_px_err.max():.2f}px")
    return rms

print()
print(f"=== Initial state ===")
print(f"Param vector: {n_total} ({n_cam_params} cam + {n_lm_params} lm)")

# Compute residual count
N_OBS = 2 * len(observations)
if args.no_barriers:
    N_BAR = 0
else:
    # Per opt cam: 3 xyz + 3 ypr + 1 fov = 7 barrier residuals
    # Per opt LM: 1 distance barrier
    N_BAR = len(opt_cams) * 7 + len(opt_lms)
N_RES = N_OBS + N_BAR
print(f"Residuals: {N_OBS} obs + {N_BAR} barriers = {N_RES}")

# ── Build sparsity mask ─────────────────────────────────────────────────────
# Each obs residual depends on cam_params (7) + lm_params (3) of its cam/lm.
# Each cam barrier (7 residuals) depends only on its own 7 cam params.
# Each lm barrier (1 residual) depends only on its own 3 lm params.

print()
print("Building Jacobian sparsity pattern...")
t0 = time.time()
sparsity = lil_matrix((N_RES, n_total), dtype=np.uint8)

# Obs residuals: rows 0..N_OBS-1 (2 rows per obs)
for k, obs in enumerate(observations):
    cam_name = obs['cam']
    lm_name = obs['lm']
    row_x = 2 * k
    row_y = 2 * k + 1
    if cam_name in cam_idx:
        i = cam_idx[cam_name] * CAM_PARAMS
        sparsity[row_x, i:i+CAM_PARAMS] = 1
        sparsity[row_y, i:i+CAM_PARAMS] = 1
    if lm_name in lm_idx:
        j = n_cam_params + lm_idx[lm_name] * LM_PARAMS
        sparsity[row_x, j:j+LM_PARAMS] = 1
        sparsity[row_y, j:j+LM_PARAMS] = 1

if not args.no_barriers:
    # Cam barriers: 7 rows per opt cam, after N_OBS
    cam_bar_start = N_OBS
    for k, n in enumerate(opt_cams):
        i = cam_idx[n] * CAM_PARAMS
        for row_off in range(7):  # 3 xyz + 3 ypr + 1 fov
            sparsity[cam_bar_start + k*7 + row_off, i:i+CAM_PARAMS] = 1

    # LM barriers: 1 row per opt LM, after cam barriers
    lm_bar_start = N_OBS + len(opt_cams) * 7
    for k, n in enumerate(opt_lms):
        j = n_cam_params + lm_idx[n] * LM_PARAMS
        sparsity[lm_bar_start + k, j:j+LM_PARAMS] = 1

sparsity = sparsity.tocsr()
nnz = sparsity.nnz
density = nnz / (N_RES * n_total) * 100
print(f"  Sparsity: {nnz} non-zeros / {N_RES * n_total} = {density:.3f}% dense")
print(f"  Built in {time.time()-t0:.1f}s")

initial_rms = report_obs_rms(p0, 'init')

# Pass 1: linear
print()
print(f"=== Pass 1: linear loss (max_iter={args.max_iter}) ===")
t0 = time.time()
result1 = least_squares(
    compute_residuals, p0,
    method='trf',
    loss='linear',
    jac_sparsity=sparsity,
    max_nfev=args.max_iter * 3,
    verbose=2,
)
print(f"Pass 1 done in {time.time()-t0:.1f}s")
print(f"  Status: {result1.status}, cost: {result1.cost:.2f}, nfev: {result1.nfev}")
p1 = result1.x
mid_rms = report_obs_rms(p1, 'pass1')

# Pass 2: huber
if not args.no_huber:
    print()
    print(f"=== Pass 2: huber loss (max_iter={args.max_iter}) ===")
    t0 = time.time()
    result2 = least_squares(
        compute_residuals, p1,
        method='trf',
        loss='huber',
        f_scale=5.0,
        jac_sparsity=sparsity,
        max_nfev=args.max_iter * 3,
        verbose=2,
    )
    print(f"Pass 2 done in {time.time()-t0:.1f}s")
    print(f"  Status: {result2.status}, cost: {result2.cost:.2f}, nfev: {result2.nfev}")
    p_final = result2.x
    final_rms = report_obs_rms(p_final, 'pass2')
else:
    p_final = p1
    final_rms = mid_rms


# ── Movement summary ────────────────────────────────────────────────────────

print()
print(f"=== Movement summary ===")
cam_moves = []
for n in opt_cams:
    xyz_f, ypr_f, hfov_f = get_cam_params(p_final, n)
    xyz_i, ypr_i, hfov_i = cam_init[n]
    dxyz = float(np.linalg.norm(xyz_f - xyz_i))
    dypr = float(max(abs(((ypr_f - ypr_i + 180) % 360) - 180)))
    dfov = float(abs(hfov_f - hfov_i))
    tier = cam_tier.get(n, 'unknown')
    cam_moves.append((n, tier, dxyz, dypr, dfov))

print(f"  Largest cam movements:")
cam_moves.sort(key=lambda x: -x[2])
for n, t, dxyz, dypr, dfov in cam_moves[:10]:
    print(f"    [{t:10}] dxyz={dxyz:7.2f}m  dypr={dypr:6.3f}°  dfov={dfov:5.3f}°  {n}")

lm_moves = []
for n in opt_lms:
    xyz_f = get_lm_xyz(p_final, n)
    d = float(np.linalg.norm(xyz_f - lm_init[n]))
    tier = lm_tier.get(n, 'unknown')
    lm_moves.append((n, tier, d))

print(f"  Largest LM movements:")
lm_moves.sort(key=lambda x: -x[2])
for n, t, d in lm_moves[:10]:
    print(f"    [{t:10}] dxyz={d:7.2f}m  {n}")


# ── Write output ───────────────────────────────────────────────────────────

if args.dry_run:
    print()
    print("DRY-RUN: not writing.")
else:
    # Build output JSON
    cams_out = {}
    for n in opt_cams:
        xyz_f, ypr_f, hfov_f = get_cam_params(p_final, n)
        cams_out[n] = {
            'xyz': [float(x) for x in xyz_f],
            'ypr': [float(x) for x in ypr_f],
            'hfov': float(hfov_f),
        }
    lms_out = {}
    for n in opt_lms:
        xyz_f = get_lm_xyz(p_final, n)
        lms_out[n] = [float(x) for x in xyz_f]

    result = {
        'tool': 'bundle_adjust_weighted',
        'initial_loss': round(initial_rms, 4),
        'final_loss': round(final_rms, 4),
        'improvement_pct': round((initial_rms - final_rms) / initial_rms * 100, 2) if initial_rms > 0 else 0,
        'n_observations': len(observations),
        'n_cams': len(opt_cams),
        'n_lms': len(opt_lms),
        'cameras': cams_out,
        'landmarks': lms_out,
    }

    with open(OUT_PATH, 'w') as f:
        json.dump(result, f, indent=2)
    print()
    print(f"✓ Written: {OUT_PATH}")
    print(f"  RMS: {initial_rms:.2f}px → {final_rms:.2f}px ({result['improvement_pct']}%)")
    print()
    print(f"Apply with: python3 tools/bundle_adjust_apply.py")
