#!/usr/bin/env python3
"""
fix_audit_orientations.py — Reconcile leak_cam_audit.json with cameras.json
on Dir (ypr) and Fov interpretations.

Background
----------

During the initial audit pass two systematic mis-reads happened:

  - Dir ordering: the in-game HUD writes `Dir:(P, R, Y)` (pitch, roll, yaw)
    but several entries were stored as `[y, p, r]`, swapping the
    components. CameraStar overlays were read correctly because they label
    "P-R-Y" explicitly.

  - Fov interpretation: the HUD `Fov:n` is the vertical FOV. The audit
    stored it as if it were the horizontal FOV.

This script reconciles every audit entry that has a ground-truth value
against the value currently stored in cameras.json (which has been
validated through V1 calibration runs). For each entry we try both
interpretations and adopt the one that matches cameras.json within
tolerance. Entries where neither interpretation matches are flagged
for manual review.

Default mode is DRY-RUN. Use --apply to write the fixes.

What it writes
--------------

For every entry that gets corrected:
  - `hud_dir_ypr`     replaced by the (y, p, r) form matching cameras.json
                      convention (yaw 0..360, pitch, roll).
  - `hud_dir_raw`     added: the original [a, b, c] that was read, plus
                      the interpretation chosen ("PRY" or "yPR").
  - `hud_fov_v`       added: vertical FOV (in degrees) — the HUD value
                      under the corrected interpretation.
  - `hud_fov_h`       added: horizontal FOV computed from hud_fov_v and
                      the frame's aspect ratio (if size available in
                      cameras.json).
  - `hud_fov`         left untouched (deprecated alias for hud_fov_v).

The `dir_convention_verified: False` flag on Intersection (W) is removed
if the reconcile succeeds.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from collections import Counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(THIS_DIR)
DATA_DIR = os.path.join(REPO_DIR, "gtamapdata")
AUDIT_PATH = os.path.join(DATA_DIR, "leak_cam_audit.json")
CAMERAS_PATH = os.path.join(DATA_DIR, "cameras.json")
BACKUP_PATH = os.path.join(DATA_DIR, "leak_cam_audit.json.pre-orientation-fix")

# Match tolerance: if all three (yaw, pitch, roll) deltas are within this,
# consider the interpretation a match.
YPR_TOL_DEG = 3.0

# Same for fov: the HUD reports vfov to 0.1 degree precision typically, so
# 1 degree is plenty of slack.
FOV_TOL_DEG = 1.0


def normalize_yaw(deg: float) -> float:
    """Normalize to 0..360."""
    return deg % 360


def normalize_yaw_diff(d: float) -> float:
    """Wrap a yaw difference into -180..180 for fair comparison across the
    0/360 seam."""
    while d > 180:
        d -= 360
    while d < -180:
        d += 360
    return d


def interpret_dir(audit_dir, mode: str):
    """Return the (yaw_0_360, pitch, roll) implied by the chosen mode.

    Modes:
      'yPR' = audit was stored as (yaw, pitch, roll). Already in cameras.json
              convention except possibly the yaw range. Used by entries where
              CameraStar's explicit P-R-Y row was parsed correctly.
      'PRY' = audit was stored as (pitch, roll, yaw_raw). Yaw_raw is the HUD
              raw value (range -180..180). True ypr = (yaw_raw%360, pitch, roll).
    """
    a, b, c = audit_dir
    if mode == "yPR":
        return [normalize_yaw(a), b, c]
    if mode == "PRY":
        return [normalize_yaw(c), a, b]
    raise ValueError(mode)


def ypr_diff(target, candidate):
    """Component-wise diff (yaw wrapped). Returns (dyaw, dpitch, droll)."""
    return (
        normalize_yaw_diff(target[0] - candidate[0]),
        target[1] - candidate[1],
        target[2] - candidate[2],
    )


def diff_magnitude(diff):
    return max(abs(diff[0]), abs(diff[1]), abs(diff[2]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Write the corrected audit JSON.")
    args = ap.parse_args()

    if not os.path.exists(AUDIT_PATH):
        print(f"ERROR: {AUDIT_PATH} not found", file=sys.stderr)
        return 2
    if not os.path.exists(CAMERAS_PATH):
        print(f"ERROR: {CAMERAS_PATH} not found", file=sys.stderr)
        return 2

    with open(AUDIT_PATH) as f:
        audit = json.load(f)
    with open(CAMERAS_PATH) as f:
        cameras = json.load(f)

    print("=" * 78)
    print("AUDIT ORIENTATION FIX")
    print("=" * 78)
    print(f"audit:    {AUDIT_PATH}")
    print(f"cameras:  {CAMERAS_PATH}")
    print(f"tol:      ypr ±{YPR_TOL_DEG}deg, fov ±{FOV_TOL_DEG}deg")
    print()

    # ----- Dir reconciliation ---------------------------------------------
    print("--- Dir (ypr) reconciliation ---")
    dir_actions = Counter()
    dir_changes = []  # (name, mode, magnitude)
    for name, entry in audit.items():
        if name == "_meta":
            continue
        if not isinstance(entry, dict):
            continue
        audit_dir = entry.get("hud_dir_ypr")
        if audit_dir is None:
            dir_actions["no_hud_dir"] += 1
            continue
        cam = cameras.get(name)
        if not cam or cam.get("ypr") is None:
            dir_actions["no_cameras_match"] += 1
            continue
        target_ypr = list(cam["ypr"])  # cameras.json convention

        # Try both interpretations
        candidates = {}
        for mode in ("yPR", "PRY"):
            try:
                cand = interpret_dir(audit_dir, mode)
            except (TypeError, ValueError):
                continue
            d = ypr_diff(target_ypr, cand)
            candidates[mode] = (cand, d, diff_magnitude(d))

        if not candidates:
            dir_actions["unparseable"] += 1
            continue

        # Best match
        best_mode = min(candidates, key=lambda m: candidates[m][2])
        best_cand, best_diff, best_mag = candidates[best_mode]

        if best_mag <= YPR_TOL_DEG:
            dir_actions[f"fix_{best_mode}"] += 1
            dir_changes.append((name, best_mode, best_mag, audit_dir, best_cand))
        else:
            dir_actions["no_match"] += 1
            dir_changes.append((name, "NO_MATCH", best_mag, audit_dir, target_ypr))

    for action, n in sorted(dir_actions.items()):
        print(f"  {action:25s} {n}")
    print()

    # Print any "needs review" cases
    no_match = [c for c in dir_changes if c[1] == "NO_MATCH"]
    if no_match:
        print(f"Dir entries with NO match to cameras.json (manual review):")
        for name, _, mag, audit_raw, target in no_match:
            print(f"  {name}")
            print(f"    audit raw    = {audit_raw}")
            print(f"    cameras ypr  = {target}")
            print(f"    best mag     = {mag:.2f} deg")
        print()

    # Show the fix table (truncated)
    fix_list = [c for c in dir_changes if c[1] in ("yPR", "PRY")]
    if fix_list:
        # Split by mode to make the systematic nature obvious
        for mode in ("yPR", "PRY"):
            ms = [c for c in fix_list if c[1] == mode]
            if not ms:
                continue
            label = ("already correct (yaw, pitch, roll)" if mode == "yPR"
                     else "needs PRY -> yPR remap")
            print(f"  {mode} mode ({label}): {len(ms)} entries")
            for name, _, mag, audit_raw, fixed in ms[:5]:
                print(f"    {name:32s} audit={audit_raw}  -> ypr={fixed}  (diff {mag:.2f}d)")
            if len(ms) > 5:
                print(f"    ... and {len(ms)-5} more")
            print()

    # ----- Fov reconciliation ---------------------------------------------
    print("--- Fov reconciliation ---")
    fov_actions = Counter()
    fov_changes = []  # (name, mode, hud_fov, hfov_cam, vfov_cam)
    for name, entry in audit.items():
        if name == "_meta":
            continue
        if not isinstance(entry, dict):
            continue
        hud_fov = entry.get("hud_fov")
        if hud_fov is None:
            fov_actions["no_hud_fov"] += 1
            continue
        cam = cameras.get(name)
        if not cam:
            fov_actions["no_cameras_match"] += 1
            continue
        cam_fov = cam.get("fov")
        if not isinstance(cam_fov, list) or len(cam_fov) < 2:
            fov_actions["unparseable_cam_fov"] += 1
            continue
        hfov_cam, vfov_cam = cam_fov[0], cam_fov[1]

        # Compare
        d_as_h = abs(hud_fov - hfov_cam) if hfov_cam is not None else float("inf")
        d_as_v = abs(hud_fov - vfov_cam) if vfov_cam is not None else float("inf")

        if d_as_v <= FOV_TOL_DEG and d_as_v <= d_as_h:
            fov_actions["confirmed_vfov"] += 1
            fov_changes.append((name, "vfov", hud_fov, hfov_cam, vfov_cam))
        elif d_as_h <= FOV_TOL_DEG:
            fov_actions["confirmed_hfov"] += 1
            fov_changes.append((name, "hfov", hud_fov, hfov_cam, vfov_cam))
        else:
            fov_actions["no_match"] += 1
            fov_changes.append((name, "NO_MATCH", hud_fov, hfov_cam, vfov_cam))

    for action, n in sorted(fov_actions.items()):
        print(f"  {action:25s} {n}")
    print()

    no_fov_match = [c for c in fov_changes if c[1] == "NO_MATCH"]
    if no_fov_match:
        print(f"Fov entries with NO match (manual review):")
        for name, _, hud_fov, hfov_cam, vfov_cam in no_fov_match[:20]:
            print(f"  {name:32s} hud_fov={hud_fov}  cameras=[h={hfov_cam}, v={vfov_cam}]")
        if len(no_fov_match) > 20:
            print(f"  ... and {len(no_fov_match)-20} more")
        print()

    # ----- Apply -----------------------------------------------------------
    if not args.apply:
        print("DRY-RUN: no changes written. Re-run with --apply.")
        return 0

    # Backup once
    if not os.path.exists(BACKUP_PATH):
        shutil.copy2(AUDIT_PATH, BACKUP_PATH)
        print(f"Backed up {AUDIT_PATH} -> {BACKUP_PATH}")

    # Apply dir fixes
    for name, mode, mag, audit_raw, fixed in fix_list:
        entry = audit[name]
        entry["hud_dir_ypr"] = list(fixed)
        entry["hud_dir_raw"] = {
            "values": list(audit_raw),
            "interpretation": mode,
            "note": "PRY = HUD writes Dir:(pitch, roll, yaw); yPR = stored as (yaw, pitch, roll) at audit time.",
        }
        # If a dir_convention_verified flag existed, set it true now that
        # we have reconciled against cameras.json.
        if "dir_convention_verified" in entry:
            entry["dir_convention_verified"] = True

    # Apply fov fixes — augment with hud_fov_v and hud_fov_h
    for name, mode, hud_fov, hfov_cam, vfov_cam in fov_changes:
        if mode == "NO_MATCH":
            continue
        entry = audit[name]
        size = (cameras.get(name) or {}).get("size")
        aspect = None
        if isinstance(size, (list, tuple)) and len(size) == 2:
            try:
                aspect = float(size[0]) / float(size[1])
            except (TypeError, ZeroDivisionError):
                pass
        if mode == "vfov":
            entry["hud_fov_v"] = float(hud_fov)
            if aspect is not None:
                hfov = math.degrees(
                    2 * math.atan(math.tan(math.radians(hud_fov) / 2) * aspect))
                entry["hud_fov_h"] = round(hfov, 3)
        elif mode == "hfov":
            entry["hud_fov_h"] = float(hud_fov)
            if aspect is not None:
                vfov = math.degrees(
                    2 * math.atan(math.tan(math.radians(hud_fov) / 2) / aspect))
                entry["hud_fov_v"] = round(vfov, 3)

    # Update _meta
    meta = audit.setdefault("_meta", {})
    meta["status"] = ("ORIENTATION-RECONCILED — hud_dir_ypr now in cameras.json "
                      "convention (yaw 0..360, pitch, roll). hud_fov_v + hud_fov_h "
                      "supersede hud_fov.")
    meta["dir_convention_notes"] = (
        "HUD writes Dir:(pitch, roll, yaw_raw) where yaw_raw is in -180..180. "
        "Stored hud_dir_ypr is the cameras.json convention (yaw 0..360, pitch, roll). "
        "Original audit-time values preserved in hud_dir_raw.")

    with open(AUDIT_PATH, "w") as f:
        json.dump(audit, f, indent=2)

    print(f"APPLIED. Audit at {AUDIT_PATH} updated.")
    print(f"Backup at {BACKUP_PATH} preserved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
