#!/usr/bin/env python3
"""
batch_retriangulate_aiwe_fixed.py — Retriangulate all FIXED landmarks that are
sourced by AI World Editor Map (4K) only and have at least one other camera
with a pixel mark.

Pattern discovered: these landmarks were placed via AIWE single-cam (top-down,
ground-truth xy from the world editor) but never validated against perspective
cameras. Adding a second camera observation lets us refine the xy by a few
meters without breaking the AIWE anchor (AIWE is top-down so xy bounded errors
project to ~0' angular error).

Each retriangulation: typically <30m movement, <5' final max residual.

Run from gtamaplib-main/:
    python3 tools/batch_retriangulate_aiwe_fixed.py        # dry run
    python3 tools/batch_retriangulate_aiwe_fixed.py --apply
"""

import argparse
import json
import math
import os
import sys

import numpy as np
from scipy.optimize import minimize

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]
import gtamaplib as ml
import gtamapdata as md

LANDMARKS_PATH = os.path.join(GTAMAP_DIR, "gtamapdata", "landmarks.json")
AIWE = "AI World Editor Map (4K)"

# Safety thresholds
MAX_MOVE_METERS = 100.0  # don't apply if landmark moves more than this
MIN_INITIAL_ERROR = 5.0  # only retriangulate if at least one cam has > 5' error

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
parser.add_argument('--max-move', type=float, default=MAX_MOVE_METERS)
parser.add_argument('--min-error', type=float, default=MIN_INITIAL_ERROR)
args = parser.parse_args()

# ── Identify candidates ───────────────────────────────────────────────────────

candidates = []
for lm_name, meta in md.landmarks_meta.items():
    if md.landmarks.get(lm_name) is None:
        continue
    sources = meta.get('source_cameras', [])
    if sources != [AIWE]:  # exactly AIWE-only sourced
        continue
    # Must have at least one OTHER cam with this pixel
    other_observers = [cn for cn, pxs in md.pixels.items()
                       if lm_name in pxs and cn != AIWE]
    if not other_observers:
        continue
    candidates.append((lm_name, other_observers))

print(f"Found {len(candidates)} AIWE-sourced FIXED landmarks with other observers")
print()

# ── Compute current residuals to filter ──────────────────────────────────────

def angular_residual(cam_name, lm_name, lm_xyz):
    """Return arcmin error of cam projecting lm_xyz vs marked pixel."""
    if cam_name not in md.cameras or lm_name not in md.pixels.get(cam_name, {}):
        return None
    if not md.cameras[cam_name].get('xyz'):
        return None
    cam = ml.get_camera(cam_name)
    pixel = md.pixels[cam_name][lm_name]
    try:
        proj = cam.get_pixel(lm_xyz)
        if proj is None:
            return None
        dx = (float(proj[0]) - pixel[0]) * cam.hfov / cam.w * 60
        dy = (float(proj[1]) - pixel[1]) * cam.vfov / cam.h * 60
        return math.sqrt(dx*dx + dy*dy)
    except Exception:
        return None

# Filter to candidates where at least one observer has > MIN_INITIAL_ERROR
filtered = []
for lm_name, observers in candidates:
    lm_xyz = md.landmarks[lm_name]
    max_err = 0.0
    for cn in observers:
        err = angular_residual(cn, lm_name, lm_xyz)
        if err is not None:
            max_err = max(max_err, err)
    if max_err >= args.min_error:
        filtered.append((lm_name, observers, max_err))

filtered.sort(key=lambda x: -x[2])  # worst first

print(f"After filter (max initial error >= {args.min_error}'): {len(filtered)} candidates")
print()

# ── Retriangulate each ───────────────────────────────────────────────────────

results = []

for lm_name, observers, max_err_init in filtered:
    rays = []
    cam_p = ml.get_camera(AIWE)
    rays.append((AIWE, np.asarray(cam_p.xyz, dtype=float),
                 np.asarray(cam_p.get_landmark_direction(lm_name), dtype=float)))
    for cn in observers:
        cam = ml.get_camera(cn)
        d = np.asarray(cam.get_landmark_direction(lm_name), dtype=float)
        d = d / np.linalg.norm(d)
        o = np.asarray(cam.xyz, dtype=float)
        rays.append((cn, o, d))

    # Loss: sum of squared angular errors
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

    p0 = np.asarray(md.landmarks[lm_name], dtype=float)
    result = minimize(loss, p0, method='Nelder-Mead',
                      options={'xatol': 1e-3, 'fatol': 1e-12,
                               'maxiter': 10000, 'adaptive': True})
    p_new = result.x
    move = float(np.linalg.norm(p_new - p0))

    # Final residuals
    aiwe_err = angular_residual(AIWE, lm_name, p_new.tolist())
    other_errs = [(cn, angular_residual(cn, lm_name, p_new.tolist())) for cn in observers]
    max_final = max([e for _, e in other_errs if e is not None] or [0])
    if aiwe_err is not None:
        max_final = max(max_final, aiwe_err)

    safe = move <= args.max_move and max_final < 5.0

    results.append({
        'lm': lm_name,
        'init_max_err': max_err_init,
        'final_max_err': max_final,
        'move_m': move,
        'new_xyz': [round(float(v), 4) for v in p_new],
        'sources': observers,
        'safe': safe,
    })

# ── Print summary ────────────────────────────────────────────────────────────

print("─" * 90)
print(f"  {'#':>3}  {'landmark':<35}  {'init':>6}  {'final':>6}  {'move':>6}  {'verdict'}")
print("─" * 90)
for i, r in enumerate(results):
    verdict = '✓ apply' if r['safe'] else '⚠ review'
    print(f"  {i+1:>3}  {r['lm'][:35]:<35}  "
          f"{r['init_max_err']:>5.1f}'  {r['final_max_err']:>5.1f}'  "
          f"{r['move_m']:>5.1f}m  {verdict}")

n_safe = sum(1 for r in results if r['safe'])
print()
print(f"Safe to apply: {n_safe} / {len(results)}")

if not args.apply:
    print(f"\n(dry run — re-run with --apply to write changes to landmarks.json)")
    sys.exit(0)

# ── Apply ────────────────────────────────────────────────────────────────────

if n_safe == 0:
    print("\nNo safe changes to apply.")
    sys.exit(0)

backup = LANDMARKS_PATH + ".bak_batch_aiwe"
import shutil
shutil.copy(LANDMARKS_PATH, backup)
print(f"\n✓ Backup: {backup}")

with open(LANDMARKS_PATH) as f:
    lm_data = json.load(f)

n_applied = 0
for r in results:
    if not r['safe']:
        continue
    zone = lm_data[r['lm']].get('zone', 'unknown')
    lm_data[r['lm']] = {
        "xyz": r['new_xyz'],
        "source_cameras": [AIWE] + r['sources'],
        "error_m": None,
        "zone": zone,
    }
    n_applied += 1

tmp = LANDMARKS_PATH + ".tmp"
with open(tmp, "w") as f:
    json.dump(lm_data, f, indent=2)
os.replace(tmp, LANDMARKS_PATH)

print(f"✓ Applied {n_applied} retriangulations to landmarks.json")
print(f"  source_cameras updated to include the new observer cams")
print(f"\nReview with: git diff gtamapdata/landmarks.json")
print(f"Then re-run: python3 tools/bundle_adjust.py")
