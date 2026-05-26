#!/usr/bin/env python3
"""
intake_camera.py — Validate a new (or existing) camera against the
trustworthy-skeleton subset of landmarks before letting it influence the
bundle adjust pool. Phase B of the T3 intake pipeline.

Reads `tools/generated/confidence_tiers.json` (produced by Phase A's
compute_confidence_tiers.py) to identify which landmarks are anchor+high
("trustworthy ground truth") vs. medium ("acceptable backup reference").

The cam's ypr (and optionally hfov, xyz) is solved against ONLY those
trustworthy landmarks — the wobbly parts of the current state never
influence new-cam placement. Reports a tier verdict + recommendation
(commit / review / reject), but does NOT modify cameras.json.

Usage:
    python3 tools/intake_camera.py "Some Cam Name"                  # ypr + hfov
    python3 tools/intake_camera.py "Some Cam Name" --refine-xyz     # also xyz, ±300m
    python3 tools/intake_camera.py "Some Cam Name" --no-hfov        # ypr only

Workflow:
    1. Run compute_confidence_tiers.py first (produces tier JSON)
    2. Run this for each new cam → see verdict + diff
    3. If verdict is `commit`: refine_camera.py --apply to actually write
       (or apply manually via the calib UI)
    4. After committing changes, re-run compute_confidence_tiers.py to
       update the tier JSON, then bundle_adjust as usual.

Why not auto-commit? In v1 we want eyes on each commit decision while we
build trust in the tool. A `--auto-commit` flag may be added later.
"""

import argparse
import json
import math
import os
import sys
import time

import numpy as np
from scipy.optimize import minimize

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
TIERS_PATH = os.path.join(TOOLS_DIR, 'generated', 'confidence_tiers.json')
INTAKE_DIR = os.path.join(TOOLS_DIR, 'generated', 'intake')


# ── Args ────────────────────────────────────────────────────────────────────

ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('cam_name')
ap.add_argument('--no-hfov', action='store_true',
                help='Keep hfov fixed (only refine yaw + pitch [+ roll, + xyz if --refine-xyz])')
ap.add_argument('--no-roll', action='store_true',
                help='Keep roll fixed at cam\'s current value (default: roll IS optimized)')
ap.add_argument('--refine-xyz', action='store_true',
                help='Also refine x, y, z within ±xyz_radius m')
ap.add_argument('--xyz-radius', type=float, default=300.0,
                help='Max xyz movement in meters (default: 300)')
ap.add_argument('--quiet', action='store_true',
                help='Suppress per-landmark residual table')
ap.add_argument('--ignore-class', action='store_true',
                help='Skip the V2 constraint_class gating. Use with caution: '
                     'class A cams have ground-truth ypr/fov that should not be refined.')
args = ap.parse_args()

CAM_NAME = args.cam_name

# V2: auto-derive DOF flags from constraint_class. CLI flags override
# the auto-derived values. Pass --ignore-class to bypass this entirely.
from leak_cam_audit import (
    get_class,
    get_locked_dof,
    is_anchor,
    is_excluded,
    DOF_XYZ, DOF_FOV,
)

if not args.ignore_class:
    if is_excluded(CAM_NAME, cameras=md.cameras):
        print(f"ERROR: '{CAM_NAME}' is class X_invalid_ground_truth — "
              f"excluded from intake.")
        sys.exit(1)
    if is_anchor(CAM_NAME, cameras=md.cameras):
        print(f"ERROR: '{CAM_NAME}' is anchor (all DOF HUD-locked). There is "
              f"nothing to intake; this cam is already an anchor. Pass "
              f"--ignore-class to override (not recommended).")
        sys.exit(1)
    # Derive DOF flags from the locked set
    _cls = get_class(CAM_NAME, cameras=md.cameras)
    if _cls is not None:
        _locked = get_locked_dof(CAM_NAME, cameras=md.cameras)
        # fov is HUD-locked → force --no-hfov on
        if DOF_FOV in _locked and not args.no_hfov:
            print(f"  V2 class {_cls}: auto-setting --no-hfov "
                  f"(fov is HUD ground-truth).")
            args.no_hfov = True
        # fov is NOT locked but user requested --no-hfov → clear it
        if DOF_FOV not in _locked and args.no_hfov:
            print(f"  V2 class {_cls}: fov is NOT HUD-locked, "
                  f"--no-hfov ignored.")
            args.no_hfov = False
        # xyz is HUD-locked → force --refine-xyz off
        if DOF_XYZ in _locked and args.refine_xyz:
            print(f"  V2 class {_cls}: xyz is HUD-locked, "
                  f"--refine-xyz ignored.")
            args.refine_xyz = False
    # For cams with no audit entry (and no _legacy_date fallback): nothing
    # is auto-set, all flags stay user-controlled.


# ── Load tier data ──────────────────────────────────────────────────────────

if not os.path.exists(TIERS_PATH):
    print(f"ERROR: {TIERS_PATH} not found.")
    print(f"  Run `python3 tools/compute_confidence_tiers.py` first.")
    sys.exit(1)

with open(TIERS_PATH) as f:
    tiers = json.load(f)

cam_tier_info = tiers['cameras'].get(CAM_NAME)
if cam_tier_info is None:
    print(f"ERROR: '{CAM_NAME}' not found in tier data.")
    print(f"  Cam may not exist in cameras.json, or tier JSON is stale.")
    sys.exit(1)

# What tier is each LM right now? — fast lookup
lm_tier = {n: info['tier'] for n, info in tiers['landmarks'].items()}


# ── Cam basic checks ────────────────────────────────────────────────────────

cam_data = md.cameras.get(CAM_NAME)
if not cam_data:
    print(f"ERROR: cam '{CAM_NAME}' not in cameras.json")
    sys.exit(1)
if not cam_data.get('xyz'):
    print(f"ERROR: cam '{CAM_NAME}' has no xyz set — cannot intake without "
          f"a starting position. Use the calib UI to set rough xyz first.")
    sys.exit(1)

cam_pixels = md.pixels.get(CAM_NAME, {})
if not cam_pixels:
    print(f"ERROR: cam '{CAM_NAME}' has no marked pixels — cannot validate.")
    print(f"  Mark some landmarks in the calib UI first.")
    sys.exit(1)


# ── Residual computation ────────────────────────────────────────────────────

def project_residual(cam, lm_xyz, marked_pixel):
    """Returns arcmin pixel error for one observation, or None on failure."""
    try:
        proj = cam.get_pixel(lm_xyz)
        if proj is None:
            return None
        dx = (float(proj[0]) - float(marked_pixel[0])) * cam.hfov / cam.w * 60.0
        dy = (float(proj[1]) - float(marked_pixel[1])) * cam.vfov / cam.h * 60.0
        return math.sqrt(dx * dx + dy * dy)
    except Exception:
        return None


# ── Build intake observation set ────────────────────────────────────────────

# Three buckets: anchor+high (trusted), medium (acceptable), low/unverified
# (excluded from the solve — we don't want them influencing placement)
ah_obs = []   # anchor+high: (lm_name, lm_xyz, marked_pixel)
med_obs = []  # medium: same
excluded_count = 0

for lm_name, marked_pixel in cam_pixels.items():
    lm_xyz = md.landmarks.get(lm_name)
    if lm_xyz is None:
        excluded_count += 1
        continue
    tier = lm_tier.get(lm_name, 'unknown')
    if tier in ('anchor', 'high'):
        ah_obs.append((lm_name, lm_xyz, marked_pixel))
    elif tier == 'medium':
        med_obs.append((lm_name, lm_xyz, marked_pixel))
    else:  # low, unverified, unknown
        excluded_count += 1

n_ah = len(ah_obs)
n_med = len(med_obs)
n_total_usable = n_ah + n_med


# ── Print intake header ─────────────────────────────────────────────────────

print(f"\n{'═' * 78}")
print(f"INTAKE — {CAM_NAME}")
print(f"{'═' * 78}")
print(f"Current tier: {cam_tier_info['tier']}")
print(f"Reason:       {cam_tier_info['reason']}")
print()
print(f"Available observations:")
print(f"  anchor+high (trusted reference) : {n_ah}")
print(f"  medium      (acceptable backup) : {n_med}")
print(f"  excluded    (low/unverified/no-xyz LMs) : {excluded_count}")
print()


# ── Reject path: not enough to evaluate ─────────────────────────────────────

if n_total_usable < 3:
    print("─" * 78)
    print(f"VERDICT: REJECT — too few usable observations ({n_total_usable} < 3)")
    print("─" * 78)
    print(f"  This cam needs more pixel observations against trustworthy landmarks.")
    print(f"  Mark additional landmarks via the calib UI, prioritizing those with")
    print(f"  anchor or high tier (LEAK-sourced or LEAK-cross-validated).")
    sys.exit(2)


# ── Solver setup ────────────────────────────────────────────────────────────

# Decide which LMs to use for the solve. Prefer anchor+high if available;
# fall back to medium if needed. We'll run TWO solves: one against anchor+high
# only, one against all medium-or-better. The first is the "trust" verdict;
# the second is reported as a sanity-check (should be similar).

# ── INTAKE-ROLL-PATCH-V1 ──
cam = ml.get_camera(CAM_NAME)
xyz0 = tuple(cam_data['xyz'])
ypr0 = list(cam_data.get('ypr') or [0.0, 0.0, 0.0])
# Ensure ypr0 has 3 components even for older cam data
while len(ypr0) < 3:
    ypr0.append(0.0)
roll0 = float(ypr0[2])  # roll starting value (was hardcoded 0 before V1-ROLL patch)
fov0 = cam_data.get('fov') or [60.0, None]
hfov0 = fov0[0]
size = cam_data.get('size') or [1920, 1080]
if hfov0 is None:
    hfov0 = ml.get_hfov(fov0[1], size) if fov0[1] is not None else 60.0


def loss_fn_factory(obs_list):
    """Build a loss function that evaluates against a specific obs list."""
    def loss(params, return_residuals=False):
        # V1-ROLL: roll inserted between yaw/pitch and hfov in the param vector
        base = 3 if args.refine_xyz else 0
        if args.refine_xyz:
            x, y, z = params[0], params[1], params[2]
            cur_xyz = (x, y, z)
            dist_sq = ((x - xyz0[0])**2 + (y - xyz0[1])**2 + (z - xyz0[2])**2)
            penalty = (dist_sq - args.xyz_radius**2) * 1e3 if dist_sq > args.xyz_radius**2 else 0.0
        else:
            cur_xyz = xyz0
            penalty = 0.0

        yaw = params[base + 0]
        pitch = params[base + 1]
        idx = base + 2
        if args.no_roll:
            roll = roll0
        else:
            roll = params[idx]
            idx += 1
        if args.no_hfov:
            hfov = hfov0
        else:
            hfov = params[idx] if idx < len(params) else hfov0

        cam.set_xyz(cur_xyz)
        cam.set_ypr((yaw, pitch, roll))
        cam.set_fov((hfov, None))
        cam.clear_landmark_directions()

        sq_total = 0.0
        n = 0
        residuals = []
        for lm_name, lm_xyz, marked_pixel in obs_list:
            r = project_residual(cam, lm_xyz, marked_pixel)
            if r is None:
                continue
            sq_total += r * r
            n += 1
            residuals.append((lm_name, r))
        if n == 0:
            return (1e10, []) if return_residuals else 1e10
        rms = math.sqrt(sq_total / n)
        if return_residuals:
            return rms, residuals
        return rms + penalty
    return loss


def build_x0(use_roll, use_hfov):
    if args.refine_xyz:
        v = [xyz0[0], xyz0[1], xyz0[2], ypr0[0], ypr0[1]]
    else:
        v = [ypr0[0], ypr0[1]]
    if use_roll:
        v.append(roll0)
    if use_hfov:
        v.append(hfov0)
    return v


def unpack(x):
    """Unpack solver result vector into named params (V1-ROLL adds roll)."""
    base = 3 if args.refine_xyz else 0
    if args.refine_xyz:
        new_xyz = (x[0], x[1], x[2])
    else:
        new_xyz = xyz0
    yaw = x[base + 0]
    pitch = x[base + 1]
    idx = base + 2
    if args.no_roll:
        roll = roll0
    else:
        roll = float(x[idx])
        idx += 1
    if args.no_hfov:
        hfov = hfov0
    else:
        hfov = float(x[idx]) if idx < len(x) else hfov0
    return new_xyz, yaw, pitch, roll, hfov


# ── Compute pre-solve residuals (current cameras.json state) ────────────────

# V1-ROLL: pre-solve evaluation uses current roll value as well
x0_init = build_x0(use_roll=True, use_hfov=True)
pre_loss_ah = loss_fn_factory(ah_obs)
pre_loss_mob = loss_fn_factory(ah_obs + med_obs)
pre_rms_ah, pre_resids_ah = pre_loss_ah(x0_init, return_residuals=True) if ah_obs else (None, [])
pre_rms_mob, pre_resids_mob = pre_loss_mob(x0_init, return_residuals=True)

pre_med_ah = (np.median([r for _, r in pre_resids_ah]) if pre_resids_ah else None)
pre_med_mob = np.median([r for _, r in pre_resids_mob])
pre_max_mob = max(r for _, r in pre_resids_mob)

print(f"Pre-solve residuals (current cameras.json state):")
if pre_med_ah is not None:
    print(f"  anchor+high        : RMS {pre_rms_ah:.2f}'  median {pre_med_ah:.2f}'")
print(f"  medium-or-better   : RMS {pre_rms_mob:.2f}'  median {pre_med_mob:.2f}'  max {pre_max_mob:.1f}'")
print()


# ── Solve: try anchor+high first, fall back to all medium-or-better ─────────

def solve(obs_list, label):
    """Run the solver against an obs list; return (params, rms, residuals)."""
    loss_for = loss_fn_factory(obs_list)
    x0 = build_x0(use_roll=not args.no_roll, use_hfov=not args.no_hfov)
    print(f"Solving against {len(obs_list)} {label} observations...")
    t0 = time.time()
    result = minimize(loss_for, x0, method='Nelder-Mead',
                      options={'xatol': 1e-5, 'fatol': 1e-6,
                               'maxiter': 20000, 'adaptive': True})
    elapsed = time.time() - t0
    final_rms, final_resids = loss_for(result.x, return_residuals=True)
    print(f"  done in {elapsed:.1f}s, RMS {final_rms:.2f}', "
          f"converged={result.success}, nfev={result.nfev}")
    return result.x, final_rms, final_resids, result.success


# Primary solve: anchor+high if we have ≥3, else fall back to all
use_obs = ah_obs if n_ah >= 3 else (ah_obs + med_obs)
use_label = 'anchor+high' if n_ah >= 3 else 'medium-or-better (sparse anchor coverage)'
solve_x, solve_rms, solve_resids, solve_ok = solve(use_obs, use_label)

# Sanity solve: against all medium-or-better, using the primary solve as start
# This tells us if the cam works against the broader observation set too.
# (If the primary solve was already against all medium-or-better, skip.)
if use_obs is not (ah_obs + med_obs):
    print()
    sanity_loss = loss_fn_factory(ah_obs + med_obs)
    sanity_rms, sanity_resids = sanity_loss(solve_x, return_residuals=True)
    sanity_med = np.median([r for _, r in sanity_resids])
    sanity_max = max(r for _, r in sanity_resids)
    print(f"Sanity check on {len(ah_obs) + len(med_obs)} medium-or-better obs:")
    print(f"  RMS {sanity_rms:.2f}'  median {sanity_med:.2f}'  max {sanity_max:.1f}'")
else:
    sanity_rms = solve_rms
    sanity_resids = solve_resids
    sanity_med = np.median([r for _, r in sanity_resids])
    sanity_max = max(r for _, r in sanity_resids)

# ── Compute verdict ─────────────────────────────────────────────────────────

new_xyz, yaw_new, pitch_new, roll_new, hfov_new = unpack(solve_x)
post_med = np.median([r for _, r in solve_resids])
post_max = max(r for _, r in solve_resids) if solve_resids else None

# Movement summary (V1-ROLL adds roll_delta)
xyz_delta = math.sqrt(sum((a - b)**2 for a, b in zip(new_xyz, xyz0)))
yaw_delta = yaw_new - ypr0[0]
pitch_delta = pitch_new - ypr0[1]
roll_delta = roll_new - roll0
hfov_delta = hfov_new - hfov0

# Verdict logic
if not solve_ok:
    verdict = 'reject'
    would_be_tier = 'unverified'
    verdict_reason = 'solver failed to converge'
elif post_med > 8.0:
    verdict = 'reject'
    would_be_tier = 'low'
    verdict_reason = f'median residual {post_med:.2f}\' > 8\' even after solve'
elif n_ah >= 5 and post_med <= 3.0 and (post_max is None or post_max <= 30.0):
    verdict = 'commit'
    would_be_tier = 'high'
    verdict_reason = f'median {post_med:.2f}\' over {len(solve_resids)} anchor+high obs'
elif (len(ah_obs) + len(med_obs)) >= 8 and sanity_med <= 4.0 and sanity_max <= 20.0:
    verdict = 'commit'
    would_be_tier = 'medium'
    verdict_reason = (f'median {sanity_med:.2f}\' over {len(ah_obs) + len(med_obs)} '
                      f'medium-or-better obs')
elif (len(ah_obs) + len(med_obs)) >= 3 and sanity_med <= 6.0:
    verdict = 'commit'
    would_be_tier = 'medium'
    verdict_reason = (f'median {sanity_med:.2f}\' over {len(ah_obs) + len(med_obs)} '
                      f'obs (low coverage — borderline pass)')
else:
    verdict = 'review'
    would_be_tier = 'low'
    verdict_reason = (f'median {sanity_med:.2f}\' is acceptable but doesn\'t '
                      f'meet commit criteria — manual review recommended')


# ── Print results ───────────────────────────────────────────────────────────

print()
print("─" * 78)
print(f"REFINED PARAMETERS (would change to):")
print("─" * 78)
if args.refine_xyz:
    print(f"  x      {xyz0[0]:>10.2f}  →  {new_xyz[0]:>10.2f}   (Δ {new_xyz[0]-xyz0[0]:+.2f} m)")
    print(f"  y      {xyz0[1]:>10.2f}  →  {new_xyz[1]:>10.2f}   (Δ {new_xyz[1]-xyz0[1]:+.2f} m)")
    print(f"  z      {xyz0[2]:>10.2f}  →  {new_xyz[2]:>10.2f}   (Δ {new_xyz[2]-xyz0[2]:+.2f} m)")
    print(f"  total xyz movement: {xyz_delta:.1f} m")
print(f"  yaw    {ypr0[0]:>10.3f}  →  {yaw_new:>10.3f}   (Δ {yaw_delta:+.3f}°)")
print(f"  pitch  {ypr0[1]:>10.3f}  →  {pitch_new:>10.3f}   (Δ {pitch_delta:+.3f}°)")
if not args.no_roll:
    print(f"  roll   {roll0:>10.3f}  →  {roll_new:>10.3f}   (Δ {roll_delta:+.3f}°)")
if not args.no_hfov:
    print(f"  hfov   {hfov0:>10.3f}  →  {hfov_new:>10.3f}   (Δ {hfov_delta:+.3f}°)")
print()


# Per-LM residual table
if not args.quiet:
    print("─" * 78)
    print(f"PER-LANDMARK RESIDUALS (post-solve):")
    print("─" * 78)
    pre_resids_dict = dict(pre_resids_mob)
    post_resids_all_dict = dict(sanity_resids)
    print(f"  {'tier':<10}  {'landmark':<40}  {'before':>8}  {'after':>8}")
    print(f"  {'-'*10}  {'-'*40}  {'-'*8}  {'-'*8}")
    # Show anchor+high first, then medium, sorted by post-solve residual desc
    rows = []
    for lm_name, lm_xyz, _ in ah_obs:
        rows.append(('anchor+high', lm_name,
                     pre_resids_dict.get(lm_name),
                     post_resids_all_dict.get(lm_name)))
    for lm_name, lm_xyz, _ in med_obs:
        rows.append(('medium', lm_name,
                     pre_resids_dict.get(lm_name),
                     post_resids_all_dict.get(lm_name)))
    # Sort by post-solve residual, worst first
    rows.sort(key=lambda r: -(r[3] if r[3] is not None else 0))
    for tier_label, lm_name, b, a in rows:
        b_s = f"{b:>7.1f}'" if b is not None else "    n/a"
        a_s = f"{a:>7.1f}'" if a is not None else "    n/a"
        print(f"  {tier_label:<10}  {lm_name[:40]:<40}  {b_s}  {a_s}")
    print()


# Verdict box
print("═" * 78)
print(f"VERDICT: {verdict.upper()}")
print(f"would-be tier (after commit): {would_be_tier}")
print(f"reason: {verdict_reason}")
print("═" * 78)
print()
print("Pre-solve residuals (current state):")
if pre_med_ah is not None:
    print(f"  anchor+high      : median {pre_med_ah:.2f}'")
print(f"  medium-or-better : median {pre_med_mob:.2f}'  max {pre_max_mob:.1f}'")
print()
print(f"Post-solve residuals:")
print(f"  primary ({use_label})")
print(f"    median {post_med:.2f}'  max {post_max:.1f}' over {len(solve_resids)} obs")
if use_obs is not (ah_obs + med_obs):
    print(f"  sanity (medium-or-better)")
    print(f"    median {sanity_med:.2f}'  max {sanity_max:.1f}' over {len(sanity_resids)} obs")
print()


# Recommendation prose
if verdict == 'commit':
    print(f"→ Recommended action: COMMIT")
    print(f"  Run: python3 tools/refine/refine_camera.py \"{CAM_NAME}\"" +
          (' --refine-xyz' if args.refine_xyz else '') +
          (' --no-roll' if args.no_roll else '') +
          (' --no-hfov' if args.no_hfov else '') +
          ' --apply')
    print(f"  Or apply manually via the calib UI.")
    print(f"  After applying: re-run compute_confidence_tiers.py to refresh tiers.")
elif verdict == 'review':
    print(f"→ Recommended action: REVIEW")
    print(f"  Residuals are not bad but don't pass commit thresholds. Open the cam")
    print(f"  in the calib UI, eyeball whether the predicted positions make sense,")
    print(f"  and decide whether to apply manually.")
elif verdict == 'reject':
    print(f"→ Recommended action: REJECT")
    print(f"  Do NOT apply these refined parameters. Possible causes:")
    print(f"    - Pixel marks are wrong (mismatched landmarks?)")
    print(f"    - Initial xyz is far off and --refine-xyz wasn't enabled")
    print(f"    - Cam is genuinely incompatible with the current trustworthy state")
    print(f"  Investigate via the calib UI and outliers_report.html.")


# ── Write JSON record ───────────────────────────────────────────────────────

os.makedirs(INTAKE_DIR, exist_ok=True)
safe_name = ''.join(c if c.isalnum() else '_' for c in CAM_NAME)
record_path = os.path.join(INTAKE_DIR, f'{safe_name}.json')

record = {
    'cam_name': CAM_NAME,
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    'verdict': verdict,
    'would_be_tier': would_be_tier,
    'verdict_reason': verdict_reason,
    'current_tier': cam_tier_info['tier'],
    'observations': {
        'anchor_high': n_ah,
        'medium': n_med,
        'excluded_low_unverified_or_missing': excluded_count,
    },
    'pre_solve': {
        'median_anchor_high': round(pre_med_ah, 4) if pre_med_ah is not None else None,
        'median_med_or_better': round(float(pre_med_mob), 4),
        'max_med_or_better': round(float(pre_max_mob), 4),
    },
    'post_solve': {
        'primary_obs_set': use_label,
        'primary_n_obs': len(solve_resids),
        'primary_median': round(float(post_med), 4),
        'primary_max': round(float(post_max), 4) if post_max is not None else None,
        'sanity_median': round(float(sanity_med), 4),
        'sanity_max': round(float(sanity_max), 4),
        'solver_converged': bool(solve_ok),
    },
    'refined_params': {
        'xyz': [round(v, 4) for v in new_xyz],
        'ypr': [round(yaw_new, 4), round(pitch_new, 4), round(roll_new, 4)],
        'hfov': round(hfov_new, 4),
        'xyz_was_refined': args.refine_xyz,
        'roll_was_refined': not args.no_roll,
        'hfov_was_refined': not args.no_hfov,
    },
    'movement': {
        'xyz_delta_m': round(xyz_delta, 4),
        'yaw_delta_deg': round(yaw_delta, 4),
        'pitch_delta_deg': round(pitch_delta, 4),
        'roll_delta_deg': round(roll_delta, 4),
        'hfov_delta_deg': round(hfov_delta, 4),
    },
}

with open(record_path, 'w') as f:
    json.dump(record, f, indent=2)
print()
print(f"Audit record: {record_path}")

# Exit code: 0 = commit, 1 = review, 2 = reject (useful for scripted batches)
sys.exit({'commit': 0, 'review': 1, 'reject': 2}[verdict])
