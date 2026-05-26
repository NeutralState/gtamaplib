#!/usr/bin/env python3
"""
migrate_constraint_classes.py — Migration step from V1 (no class info in
cameras.json) to V2 (every audited cam carries its constraint_class).

What this does
--------------

For every cam in `gtamapdata/cameras.json` that has an entry in
`gtamapdata/leak_cam_audit.json`:

  1. Compares the HUD ground-truth values from the audit against the values
     currently stored in cameras.json. Reports diffs.

  2. Writes `constraint_class` into the cameras.json entry.

  3. For class A cams (full HUD ground truth): optionally overwrites the
     stored xyz / ypr / fov with the HUD values. This is the only step that
     touches numerical calibration data and is gated behind --overwrite-a.

  4. For class X cams: writes `constraint_class` but does not modify other
     fields. Downstream tools will skip these.

Cams with no audit entry are untouched.

Default mode is DRY-RUN: nothing is written. Use --apply to write.

Recommended sequence
--------------------

    1) python3 tools/migrate_constraint_classes.py
         # dry-run, no overwrites. Inspect the diff table.

    2) python3 tools/migrate_constraint_classes.py --report-only
         # same diff table, plus per-class summary, no other side effects.

    3) python3 tools/migrate_constraint_classes.py --apply
         # write constraint_class into cameras.json.
         # xyz/ypr/fov UNCHANGED.

    4) python3 tools/migrate_constraint_classes.py --apply --overwrite-a
         # additionally overwrite xyz/ypr/fov of class A cams with HUD
         # ground truth. Only do this after reviewing the diff table.

Safety
------

- The pre-modification cameras.json is backed up to
  `gtamapdata/cameras.json.pre-v2-migration` before any write.
- Intersection (W) has dir_convention_verified=False — by default it is
  EXCLUDED from --overwrite-a. Pass --include-unverified-dir to override.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from collections import Counter, defaultdict
from typing import Optional

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(THIS_DIR)
DATA_DIR = os.path.join(REPO_DIR, "gtamapdata")
CAMERAS_PATH = os.path.join(DATA_DIR, "cameras.json")
AUDIT_PATH = os.path.join(DATA_DIR, "leak_cam_audit.json")
BACKUP_PATH = os.path.join(DATA_DIR, "cameras.json.pre-v2-migration")

# Tolerance for "values are effectively the same" diff. The audit HUD values
# come from console readouts that have at most 4 decimals visible, so anything
# below ~0.05 in coordinate space and ~0.05 deg in angle is noise.
XYZ_TOL_M = 0.5      # 0.5 m: a typical HUD readout precision
YPR_TOL_DEG = 1.0    # 1 deg: small refinements during prior optimization
FOV_TOL_DEG = 0.5    # 0.5 deg


def _load_audit() -> dict:
    with open(AUDIT_PATH) as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if k != "_meta"}


def _load_cameras() -> dict:
    with open(CAMERAS_PATH) as f:
        return json.load(f)


def _vec_diff(a, b) -> float:
    """Max |a[i] - b[i]| over components. Returns inf if either is None."""
    if a is None or b is None:
        return float("inf")
    if len(a) != len(b):
        return float("inf")
    return max(abs(float(a[i]) - float(b[i])) for i in range(len(a)))


def _fov_components(fov_field):
    """cameras.json stores fov as [hfov, vfov] where either component may
    be None. Return (hfov, vfov) tuple."""
    if fov_field is None:
        return (None, None)
    if isinstance(fov_field, (int, float)):
        return (float(fov_field), None)
    if isinstance(fov_field, list) and fov_field:
        hfov = fov_field[0]
        vfov = fov_field[1] if len(fov_field) > 1 else None
        return (
            float(hfov) if hfov is not None else None,
            float(vfov) if vfov is not None else None,
        )
    return (None, None)


def _aspect(cam_data) -> Optional[float]:
    """Frame aspect ratio (w/h) from cameras.json size field. None if absent."""
    size = cam_data.get("size")
    if not isinstance(size, (list, tuple)) or len(size) != 2:
        return None
    try:
        w, h = float(size[0]), float(size[1])
        if h <= 0:
            return None
        return w / h
    except (TypeError, ValueError):
        return None


def _hfov_from_vfov(vfov_deg: float, aspect: float) -> float:
    return math.degrees(2 * math.atan(math.tan(math.radians(vfov_deg) / 2) * aspect))


def _vfov_from_hfov(hfov_deg: float, aspect: float) -> float:
    return math.degrees(2 * math.atan(math.tan(math.radians(hfov_deg) / 2) / aspect))


def _audit_hud_fov_v(audit_entry, cam_data) -> Optional[float]:
    """Return the HUD vertical FOV from an audit entry. Prefers the explicit
    hud_fov_v field (set by fix_audit_orientations.py); falls back to the
    legacy hud_fov field (which we now know to be the vfov by convention)."""
    v = audit_entry.get("hud_fov_v")
    if v is not None:
        return float(v)
    legacy = audit_entry.get("hud_fov")
    if legacy is not None:
        return float(legacy)
    return None


def diff_cam(cam_data: dict, audit_entry: dict) -> dict:
    """Compute a diff record between what's in cameras.json today and what
    the audit says is HUD ground truth. Pure function — no side effects.

    Fov diff is done in vfov space (the natural HUD unit). If cameras.json
    has only hfov stored, we compute the vfov via the aspect ratio."""
    cur_xyz = cam_data.get("xyz")
    cur_ypr = cam_data.get("ypr")
    cur_hfov, cur_vfov = _fov_components(cam_data.get("fov"))

    hud_xyz = audit_entry.get("hud_C_xyz")
    hud_ypr = audit_entry.get("hud_dir_ypr")
    hud_vfov = _audit_hud_fov_v(audit_entry, cam_data)

    # Pick the best comparable vfov from cameras.json
    cur_vfov_comparable = cur_vfov
    if cur_vfov_comparable is None and cur_hfov is not None:
        a = _aspect(cam_data)
        if a is not None:
            cur_vfov_comparable = _vfov_from_hfov(cur_hfov, a)

    dfov = (abs(cur_vfov_comparable - hud_vfov)
            if (cur_vfov_comparable is not None and hud_vfov is not None)
            else None)

    return {
        "cur_xyz": cur_xyz,  "hud_xyz": hud_xyz,
        "cur_ypr": cur_ypr,  "hud_ypr": hud_ypr,
        "cur_vfov": cur_vfov_comparable,
        "hud_vfov": hud_vfov,
        "dxyz": _vec_diff(cur_xyz, hud_xyz) if hud_xyz else None,
        "dypr": _vec_diff(cur_ypr, hud_ypr) if hud_ypr else None,
        "dfov": dfov,
    }


def severity(diff: dict) -> str:
    """Classify the diff record as 'ok', 'minor', 'major', or 'missing'."""
    if diff["hud_xyz"] is None and diff["hud_ypr"] is None and diff["hud_vfov"] is None:
        return "missing"  # audit has no numerical ground truth (e.g. class D)

    flags = []
    if diff["dxyz"] is not None:
        flags.append("MAJOR" if diff["dxyz"] > XYZ_TOL_M else "ok")
    if diff["dypr"] is not None:
        flags.append("MAJOR" if diff["dypr"] > YPR_TOL_DEG else "ok")
    if diff["dfov"] is not None:
        flags.append("MAJOR" if diff["dfov"] > FOV_TOL_DEG else "ok")

    if "MAJOR" in flags:
        return "major"
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Write constraint_class into cameras.json.")
    ap.add_argument("--overwrite-a", action="store_true",
                    help="For class A cams, additionally overwrite "
                         "xyz/ypr/fov with HUD ground truth. Requires --apply.")
    ap.add_argument("--include-unverified-dir", action="store_true",
                    help="Allow --overwrite-a on cams with "
                         "dir_convention_verified=False. Off by default.")
    ap.add_argument("--report-only", action="store_true",
                    help="Print the full diff table and exit. No writes.")
    args = ap.parse_args()

    if not os.path.exists(CAMERAS_PATH):
        print(f"ERROR: {CAMERAS_PATH} not found", file=sys.stderr)
        return 2
    if not os.path.exists(AUDIT_PATH):
        print(f"ERROR: {AUDIT_PATH} not found", file=sys.stderr)
        return 2

    audit = _load_audit()
    cameras = _load_cameras()

    cam_names = set(cameras.keys())
    audit_names = set(audit.keys())

    in_both = sorted(cam_names & audit_names)
    audit_only = sorted(audit_names - cam_names)
    cam_only_count = len(cam_names - audit_names)

    print("=" * 78)
    print("CONSTRAINT-CLASS MIGRATION")
    print("=" * 78)
    print(f"cameras.json:        {len(cam_names)} cams")
    print(f"leak_cam_audit.json: {len(audit_names)} entries")
    print(f"in both:             {len(in_both)} cams (will receive constraint_class)")
    print(f"cameras.json only:   {cam_only_count} cams (ordinary cams, untouched)")
    if audit_only:
        print(f"audit only:          {len(audit_only)} cams (no match in cameras.json):")
        for n in audit_only:
            print(f"    {n}")
    print()

    # Build per-cam diff records
    diffs = {}
    severities = {}
    for name in in_both:
        d = diff_cam(cameras[name], audit[name])
        diffs[name] = d
        severities[name] = severity(d)

    # Group by class for the summary
    by_class = defaultdict(list)
    for name in in_both:
        cls = audit[name].get("constraint_class", "?")
        by_class[cls].append(name)

    # --- Diff table -------------------------------------------------------
    print("Per-class diff summary")
    print("-" * 78)
    sev_counts_per_class = {}
    for cls in sorted(by_class):
        cams = by_class[cls]
        sc = Counter(severities[n] for n in cams)
        sev_counts_per_class[cls] = sc
        pieces = [f"{k}={v}" for k, v in sorted(sc.items())]
        print(f"  {cls:25s} ({len(cams):>3d} cams)  " + "  ".join(pieces))
    print()

    # --- Major diffs --------------------------------------------------------
    majors = [n for n in in_both if severities[n] == "major"]
    if majors:
        print(f"Cams with MAJOR diffs (HUD vs current cameras.json), {len(majors)} total")
        print("-" * 78)
        print(f"  {'cam':<32} {'cls':<22} {'dxyz':>7} {'dypr':>7} {'dfov':>7}")
        for n in majors:
            d = diffs[n]
            cls = audit[n].get("constraint_class", "?")
            dxyz = f"{d['dxyz']:.2f}" if d['dxyz'] is not None else "  -  "
            dypr = f"{d['dypr']:.2f}" if d['dypr'] is not None else "  -  "
            dfov = f"{d['dfov']:.2f}" if d['dfov'] is not None else "  -  "
            print(f"  {n:<32} {cls:<22} {dxyz:>7} {dypr:>7} {dfov:>7}")
        print()
        print(f"  Tolerances: dxyz>{XYZ_TOL_M}m  dypr>{YPR_TOL_DEG}deg  dfov>{FOV_TOL_DEG}deg")
        print()

    # --- Pre-overwrite preview for class A ----------------------------------
    # Only relevant if the user intends to pass --overwrite-a. Shown by default
    # is just noise — the recommended path is to keep cameras.json values as
    # source of truth.
    a_cams = by_class.get("A_full_hud", [])
    if a_cams and args.overwrite_a:
        print(f"Class A overwrite preview ({len(a_cams)} cams)")
        print("-" * 78)
        skipped_unverified = []
        will_overwrite = []
        for n in sorted(a_cams):
            e = audit[n]
            unverified = (e.get("dir_convention_verified") is False)
            if unverified and not args.include_unverified_dir:
                skipped_unverified.append(n)
            else:
                will_overwrite.append(n)
        print(f"  would overwrite xyz/ypr/fov for: {len(will_overwrite)} cams")
        if skipped_unverified:
            print(f"  skipped (dir_convention_verified=False): "
                  f"{len(skipped_unverified)} cams")
            for n in skipped_unverified:
                print(f"      {n}")
        print()
    else:
        a_cams = by_class.get("A_full_hud", [])  # keep accessible below

    if args.report_only:
        return 0

    # --- Apply --------------------------------------------------------------
    if not args.apply:
        print("DRY-RUN: no changes written. Re-run with --apply to write "
              "constraint_class into cameras.json.")
        if args.overwrite_a:
            print("(--overwrite-a requires --apply; ignored.)")
        return 0

    # Sanity: --overwrite-a requires --apply (already enforced by being here)
    if args.overwrite_a and not a_cams:
        print("INFO: --overwrite-a passed but no class A cams in scope.")

    # Back up cameras.json before any write. Preserve the original backup if
    # one already exists — re-running --apply must NOT clobber the pre-V1
    # state.
    if not os.path.exists(BACKUP_PATH):
        shutil.copy2(CAMERAS_PATH, BACKUP_PATH)
        print(f"Backed up {CAMERAS_PATH} -> {BACKUP_PATH}")
    else:
        print(f"Backup already exists at {BACKUP_PATH} (not overwriting).")

    write_count = 0
    overwrite_count = 0
    excluded_count = 0
    for name in in_both:
        cls = audit[name].get("constraint_class")
        if cls not in {
            "A_full_hud", "B_pos_fov_player", "C_pos_fov_only",
            "Cm_pos_only", "D_no_ground_truth", "X_invalid_ground_truth",
        }:
            continue
        cameras[name]["constraint_class"] = cls
        write_count += 1
        if cls == "X_invalid_ground_truth":
            excluded_count += 1

        if args.overwrite_a and cls == "A_full_hud":
            e = audit[name]
            unverified = (e.get("dir_convention_verified") is False)
            if unverified and not args.include_unverified_dir:
                continue
            gt_xyz = e.get("hud_C_xyz")
            gt_ypr = e.get("hud_dir_ypr")
            gt_vfov = _audit_hud_fov_v(e, cameras[name])
            if gt_xyz is not None:
                cameras[name]["xyz"] = list(gt_xyz)
            if gt_ypr is not None:
                cameras[name]["ypr"] = list(gt_ypr)
            if gt_vfov is not None:
                # cameras.json fov field is [hfov, vfov]. The HUD value is
                # the vfov.
                #
                # If cameras.json already has an hfov (set by an earlier
                # solver run), we PRESERVE it and only update the vfov
                # slot. The hfov from prior calibration is usually more
                # accurate than what we'd compute from the HUD vfov via a
                # nominal aspect ratio (the effective aspect of the
                # in-game viewport sometimes differs from w/h of the
                # captured frame by a small amount).
                #
                # If cameras.json has no hfov, we compute one from the
                # frame aspect ratio. If we can't derive aspect, we
                # refuse to write — never put a vfov in the hfov slot.
                old_fov = cameras[name].get("fov")
                cur_hfov, _ = _fov_components(old_fov)
                aspect = _aspect(cameras[name])
                if cur_hfov is not None:
                    cameras[name]["fov"] = [round(cur_hfov, 4),
                                            round(float(gt_vfov), 4)]
                elif aspect is not None:
                    new_hfov = _hfov_from_vfov(gt_vfov, aspect)
                    cameras[name]["fov"] = [round(new_hfov, 4),
                                            round(float(gt_vfov), 4)]
                else:
                    print(f"  WARN: {name!r} has no usable hfov or size; "
                          f"fov NOT overwritten.")
            overwrite_count += 1

    with open(CAMERAS_PATH, "w") as f:
        json.dump(cameras, f, indent=2)

    print()
    print(f"WROTE constraint_class on {write_count} cams "
          f"(including {excluded_count} excluded class X cams).")
    if args.overwrite_a:
        print(f"OVERWROTE xyz/ypr/fov on {overwrite_count} class A cams.")
    print(f"Backup at {BACKUP_PATH}. If anything looks wrong, restore with:")
    print(f"    cp {BACKUP_PATH} {CAMERAS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
