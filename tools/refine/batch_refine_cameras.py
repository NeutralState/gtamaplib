#!/usr/bin/env python3
"""
batch_refine_cameras.py — Refine multiple cameras at once using consensus
landmarks, with safety checks before applying.

For each camera in the list:
  - Build the consensus landmark set
  - Run a 6D refinement (xyz + ypr + hfov)
  - Print before/after summary with sanity checks (loss drop, xyz movement)

Cameras with insufficient consensus or suspicious refinement are flagged
and excluded from --apply by default. Use --force to apply everything.

Run from gtamaplib-main/:
    python3 tools/batch_refine_cameras.py
    python3 tools/batch_refine_cameras.py --apply
"""

import argparse
import os
import sys
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]
import gtamaplib as ml
import gtamapdata as md

# ── Cameras to refine ─────────────────────────────────────────────────────────

CAMS_TO_REFINE = [
    "U-Turn (NW)",
    "U-Turn (NE)",
    "Beach",
    "Jet Ski",
    "Ocean Drive (NW)",
    "Vice City 03 (Basketball)",
    "Vice City Postcard",
    "Chase (2) (A)",
]

CONSENSUS_THRESHOLD = 5.0  # arcmin
XYZ_RADIUS = 300.0         # max xyz movement in m
MIN_CONSENSUS_LMS = 4      # need at least this many to refine

# Sanity thresholds for auto-applying:
MAX_XYZ_MOVE_AUTO = 250.0  # don't auto-apply if xyz moves more than this
MIN_LOSS_REDUCTION = 0.30  # only auto-apply if loss drops at least this fraction

# ── Args ──────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true',
                    help='Apply changes that pass safety checks')
parser.add_argument('--force', action='store_true',
                    help='Skip safety checks (apply all that converged)')
args = parser.parse_args()

# ── Helper: build consensus set for a camera ──────────────────────────────────

def consensus_landmarks(cam_name):
    cam_pixels = md.pixels.get(cam_name, {})
    if not cam_pixels:
        return []
    consensus = []
    for lm_name in cam_pixels:
        lm_xyz = md.landmarks.get(lm_name)
        if lm_xyz is None:
            continue
        n_agreeing = 0
        for other_cam, other_pixels in md.pixels.items():
            if other_cam == cam_name or lm_name not in other_pixels:
                continue
            if not md.cameras.get(other_cam, {}).get('xyz'):
                continue
            try:
                oc = ml.get_camera(other_cam)
                proj = oc.get_pixel(lm_xyz)
                if proj is None:
                    continue
                opx, opy = other_pixels[lm_name]
                dx = (float(proj[0]) - float(opx)) * oc.hfov / oc.w * 60.0
                dy = (float(proj[1]) - float(opy)) * oc.vfov / oc.h * 60.0
                err = (dx*dx + dy*dy) ** 0.5
                if err < CONSENSUS_THRESHOLD:
                    n_agreeing += 1
            except Exception:
                continue
        if n_agreeing >= 1:
            consensus.append((lm_name, n_agreeing))
    return consensus

# ── Helper: refine a single camera (6D) ───────────────────────────────────────

def refine(cam_name, consensus_lms):
    cam_data = md.cameras.get(cam_name)
    if not cam_data or not cam_data.get('xyz'):
        return None
    cam = ml.get_camera(cam_name)
    cam_pixels = md.pixels[cam_name]
    xyz = tuple(cam_data['xyz'])
    ypr0 = list(cam_data.get('ypr') or [0, 0, 0])
    fov0 = cam_data.get('fov') or [60, None]
    size = cam_data.get('size') or [1920, 1080]
    hfov0 = fov0[0]
    if hfov0 is None:
        hfov0 = ml.get_hfov(fov0[1], size) if fov0[1] is not None else 60.0

    def loss(params):
        x, y, z, yaw, pitch, hfov = params
        dist_sq = (x - xyz[0])**2 + (y - xyz[1])**2 + (z - xyz[2])**2
        penalty = 0.0
        if dist_sq > XYZ_RADIUS**2:
            penalty = (dist_sq - XYZ_RADIUS**2) * 1e3
        cam.set_xyz((x, y, z))
        cam.set_ypr((yaw, pitch, 0.0))
        cam.set_fov((hfov, None))
        cam.clear_landmark_directions()
        total = 0.0
        n = 0
        for lm_name, _ in consensus_lms:
            try:
                proj = cam.get_pixel(md.landmarks[lm_name])
                if proj is None:
                    continue
                px, py = cam_pixels[lm_name]
                dx = (float(proj[0]) - float(px)) * cam.hfov / cam.w * 60.0
                dy = (float(proj[1]) - float(py)) * cam.vfov / cam.h * 60.0
                total += dx*dx + dy*dy
                n += 1
            except Exception:
                continue
        if n == 0:
            return 1e10
        return (total / n) ** 0.5 + penalty

    x0 = [xyz[0], xyz[1], xyz[2], ypr0[0], ypr0[1], hfov0]
    initial_loss = loss(x0)
    res = minimize(loss, x0, method='Nelder-Mead',
                   options={'xatol': 1e-5, 'fatol': 1e-6,
                            'maxiter': 20000, 'adaptive': True})
    final_loss = res.fun
    x_new, y_new, z_new, yaw_new, pitch_new, hfov_new = res.x
    xyz_move = ((x_new - xyz[0])**2 + (y_new - xyz[1])**2 + (z_new - xyz[2])**2) ** 0.5

    return {
        'cam_name': cam_name,
        'xyz_old': list(xyz),
        'xyz_new': [round(x_new, 4), round(y_new, 4), round(z_new, 4)],
        'ypr_old': ypr0,
        'ypr_new': [round(yaw_new, 4), round(pitch_new, 4), 0.0],
        'hfov_old': round(hfov0, 4),
        'hfov_new': round(hfov_new, 4),
        'fov_orig': fov0,
        'initial_loss': initial_loss,
        'final_loss': final_loss,
        'xyz_move': xyz_move,
        'n_consensus': len(consensus_lms),
    }

# ── Main loop ─────────────────────────────────────────────────────────────────

print(f"Refining {len(CAMS_TO_REFINE)} cameras using consensus landmarks...")
print()

results = []
for cam_name in CAMS_TO_REFINE:
    print(f"  {cam_name}...", end=' ', flush=True)
    cons = consensus_landmarks(cam_name)
    if len(cons) < MIN_CONSENSUS_LMS:
        print(f"SKIP — only {len(cons)} consensus landmarks (need {MIN_CONSENSUS_LMS})")
        results.append({'cam_name': cam_name, 'skipped': True,
                        'reason': f'{len(cons)} consensus lms'})
        continue
    r = refine(cam_name, cons)
    if r is None:
        print(f"SKIP — no xyz")
        results.append({'cam_name': cam_name, 'skipped': True, 'reason': 'no xyz'})
        continue
    print(f"{r['initial_loss']:.0f}' → {r['final_loss']:.1f}'  "
          f"(xyz {r['xyz_move']:.0f}m, {r['n_consensus']} lms)")
    results.append(r)

# ── Summary table ─────────────────────────────────────────────────────────────

print()
print("─" * 105)
print(f"{'cam':<32}  {'#lms':>5}  {'init':>7}  {'final':>7}  {'xyz Δ':>7}  "
      f"{'Δyaw':>7}  {'Δpitch':>7}  {'Δhfov':>7}  {'verdict':<12}")
print("─" * 105)

to_apply = []
for r in results:
    if r.get('skipped'):
        print(f"{r['cam_name'][:32]:<32}  ----   skipped: {r.get('reason','?')}")
        continue
    dyaw   = r['ypr_new'][0] - r['ypr_old'][0]
    dpitch = r['ypr_new'][1] - r['ypr_old'][1]
    dhfov  = r['hfov_new']   - r['hfov_old']
    reduction = (r['initial_loss'] - r['final_loss']) / max(r['initial_loss'], 1e-9)

    # Verdict
    issues = []
    if r['final_loss'] > 50:
        issues.append('high-final-loss')
    if r['xyz_move'] > MAX_XYZ_MOVE_AUTO:
        issues.append('big-xyz-move')
    if reduction < MIN_LOSS_REDUCTION:
        issues.append('low-improvement')
    if abs(dhfov) > 15:
        issues.append('hfov-suspect')

    if issues:
        verdict = 'REVIEW: ' + ','.join(issues)
        ok = False
    else:
        verdict = 'auto-apply'
        ok = True
        to_apply.append(r)

    print(f"{r['cam_name'][:32]:<32}  {r['n_consensus']:>4}   "
          f"{r['initial_loss']:>6.0f}'  {r['final_loss']:>6.1f}'  "
          f"{r['xyz_move']:>5.0f}m  {dyaw:>+6.2f}°  {dpitch:>+6.2f}°  {dhfov:>+6.2f}°  {verdict}")

print()
print(f"Auto-apply candidates: {len(to_apply)} / {len([r for r in results if not r.get('skipped')])}")

# ── Apply ─────────────────────────────────────────────────────────────────────

if args.apply:
    if args.force:
        candidates = [r for r in results if not r.get('skipped')]
        print(f"\n--force: applying ALL {len(candidates)} non-skipped cameras")
    else:
        candidates = to_apply
        print(f"\nApplying {len(candidates)} cameras (those that passed safety checks)")

    if not candidates:
        print("Nothing to apply.")
        sys.exit(0)

    confirm = input(f"\nProceed with applying {len(candidates)} camera updates? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Aborted.")
        sys.exit(0)

    for r in candidates:
        new_fov = [r['hfov_new'], r['fov_orig'][1]]
        md.update_camera(
            r['cam_name'],
            xyz=r['xyz_new'],
            ypr=r['ypr_new'],
            fov=new_fov,
        )
        print(f"  ✓ {r['cam_name']}")

    print(f"\nDone. Review with: git diff gtamapdata/cameras.json")
else:
    print(f"\n(dry run — re-run with --apply to write changes that pass safety checks)")
    print(f"            re-run with --apply --force to write everything that converged)")
