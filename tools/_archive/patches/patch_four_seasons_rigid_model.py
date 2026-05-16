#!/usr/bin/env python3
"""
patch_four_seasons_rigid_model.py — Niveau 1

Apply rlx's FourSeasons rigid-body model (vendor/gtamaplib/gtamaplib.py:1317)
to your landmarks.json.

Three operations:

A. Fix corrupted LM:
   - "Four Seasons Hotel Miami (W)" has garbage xyz (~3e14 m).
     Override with model value.

B. Override 4 drifted LMs to model values (preserves rigid-body coherence):
   - BE  (drift 4.79m) → -814.289, -1306.504, 263.568
   - BW  (drift 2.02m) → -859.904, -1289.449, 263.568
   - NW  (drift 2.95m) → -847.739, -1256.913, 258.306
   - SE  (drift 1.37m) → -817.997, -1316.422, 253.608
   (E, NE, SW are already <0.5m drift, left alone; modifying them
    would break their existing marker reproj which is good.)

C. Add 9 LMs that are marked on Tennis Stadium (4K) and/or
   Metro (SE) (A) (4K) but don't exist in landmarks.json:
   - 40NW, 40W, 40E, 32NE, 56NE, HB28SE, HB8SE, HB58SE, HB58NE
   All assigned model xyz, sources are the LEAK cams that marked them.

Sentinel: [FOUR-SEASONS-RIGID-V1] (idempotent via comments key in landmarks.json,
or via separate ledger). Re-running is a no-op.

Run from gtamaplib-main/:
  python3 patch_four_seasons_rigid_model.py             # dry-run
  python3 patch_four_seasons_rigid_model.py --apply     # write to disk
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).parent.resolve()
VENDOR = REPO / "vendor"
LANDMARKS_JSON = REPO / "gtamapdata" / "landmarks.json"
PIXELS_JSON = REPO / "gtamapdata" / "pixels.json"
SENTINEL = "FOUR-SEASONS-RIGID-V1"

# Insert vendor for FourSeasons import
sys.path.insert(0, str(VENDOR))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write changes to disk")
    args = ap.parse_args()

    # Load rlx's FourSeasons rigid model
    from gtamaplib.gtamaplib import FourSeasons
    fs = FourSeasons()

    # Build the full set of LMs the model defines + their sources
    # Sources determined by what your cameras actually marked, cross-referenced
    # with rlx's gtamapdata.py
    model_lms = {
        # ── Override existing (Niveau 1B) ──
        "Four Seasons Hotel Miami (BE)": {
            "xyz": list(fs.hb58se),
            "source_cameras": ["Handlebar (SE)"],
            "comment": "Handlebar (SE) — rigid model",
        },
        "Four Seasons Hotel Miami (BW)": {
            "xyz": list(fs.hb58sw),
            "source_cameras": ["Handlebar (SW)"],
            "comment": "Handlebar (SW) — rigid model",
        },
        "Four Seasons Hotel Miami (NW)": {
            "xyz": list(fs.fs57nw),
            "source_cameras": ["Penthouse (NW)"],
            "comment": "Penthouse (NW) — rigid model",
        },
        "Four Seasons Hotel Miami (SE)": {
            "xyz": list(fs.fs56se),
            "source_cameras": ["Rooftop (SE)"],
            "comment": "Rooftop (SE) — rigid model",
        },
        # ── Fix corrupted W (Niveau 1A) ──
        "Four Seasons Hotel Miami (W)": {
            "xyz": list(fs.fs57e),  # rlx defines W = SE penthouse (same xyz as E)
            "source_cameras": ["Penthouse (SW)"],
            "comment": "Penthouse (SW) — rigid model (was corrupted ~3e14m)",
        },
        # ── Add missing (Niveau 1C) ──
        "Four Seasons Hotel Miami (40NW)": {
            "xyz": list(fs.fs40nw),
            "source_cameras": ["Metro (SE) (A) (4K)"],
            "comment": "rigid model — 40th floor NW corner",
        },
        "Four Seasons Hotel Miami (40W)": {
            "xyz": list(fs.fs40w),
            "source_cameras": ["Metro (SE) (A) (4K)"],
            "comment": "rigid model — 40th floor W corner",
        },
        "Four Seasons Hotel Miami (40E)": {
            "xyz": list(fs.fs40e),
            "source_cameras": ["Tennis Stadium (4K)"],
            "comment": "rigid model — 40th floor E corner",
        },
        "Four Seasons Hotel Miami (32NE)": {
            "xyz": list(fs._get_point_at_floor(fs.fs40ne, 32)),
            "source_cameras": ["Tennis Stadium (4K)"],
            "comment": "rigid model — 32nd floor NE corner",
        },
        "Four Seasons Hotel Miami (56NE)": {
            "xyz": list(fs.fs56ne),
            "source_cameras": ["Tennis Stadium (4K)"],
            "comment": "rigid model — 56th floor NE (rooftop)",
        },
        "Four Seasons Hotel Miami (HB28SE)": {
            "xyz": list(fs.hb28se),
            "source_cameras": ["Tennis Stadium (4K)"],
            "comment": "rigid model — handlebar 28 SE",
        },
        "Four Seasons Hotel Miami (HB8SE)": {
            "xyz": list(fs.hb8se),
            "source_cameras": ["Tennis Stadium (4K)"],
            "comment": "rigid model — handlebar 8 SE",
        },
        "Four Seasons Hotel Miami (HB58SE)": {
            "xyz": list(fs.hb58se),
            "source_cameras": ["Tennis Stadium (4K)"],
            "comment": "rigid model — handlebar 58 SE",
        },
        "Four Seasons Hotel Miami (HB58NE)": {
            "xyz": list(fs.hb58ne),
            "source_cameras": ["Tennis Stadium (4K)"],
            "comment": "rigid model — handlebar 58 NE",
        },
    }

    # Load current data
    with open(LANDMARKS_JSON) as f:
        landmarks = json.load(f)

    # Categorize changes
    overrides = []
    additions = []
    skipped_already_patched = []

    for name, model_data in model_lms.items():
        if name in landmarks:
            existing = landmarks[name]
            existing_meta = existing.get("author", "")
            # Idempotent check: if author or notes already mark this as rigid model
            if SENTINEL in existing.get("notes", "") or SENTINEL in existing_meta:
                skipped_already_patched.append(name)
                continue
            # Compute current drift
            cur_xyz = existing.get("xyz")
            if cur_xyz and abs(cur_xyz[0]) < 1e6:  # not corrupted
                drift = sum((a - b) ** 2 for a, b in zip(cur_xyz, model_data["xyz"])) ** 0.5
            else:
                drift = float('inf')
            overrides.append((name, cur_xyz, model_data["xyz"], drift))
        else:
            additions.append((name, model_data["xyz"]))

    # Dry-run report
    print(f"=== Mode: {'APPLY' if args.apply else 'DRY-RUN'} ===")
    print()
    if skipped_already_patched:
        print(f"Already patched ({SENTINEL}), skipping {len(skipped_already_patched)}:")
        for n in skipped_already_patched:
            print(f"  {n}")
        print()

    if overrides:
        print(f"OVERRIDES ({len(overrides)}):")
        for name, cur, new, drift in overrides:
            drift_s = "CORRUPTED" if drift == float('inf') else f"{drift:6.2f}m drift"
            print(f"  {name:<45s}  [{drift_s}]")
        print()

    if additions:
        print(f"ADDITIONS ({len(additions)}):")
        for name, new in additions:
            print(f"  {name:<45s}  xyz=({new[0]:.2f}, {new[1]:.2f}, {new[2]:.2f})")
        print()

    if not overrides and not additions:
        print("Nothing to do — all LMs already match the rigid model.")
        return

    if not args.apply:
        print("Dry-run only. Re-run with --apply to write changes.")
        return

    # APPLY
    # Backup
    backup_path = LANDMARKS_JSON.with_suffix(f".json.bak_pre_{SENTINEL.lower()}")
    shutil.copy(LANDMARKS_JSON, backup_path)
    print(f"Backup: {backup_path}")

    # Apply overrides
    for name, _, new_xyz, _ in overrides:
        landmarks[name]["xyz"] = new_xyz
        existing_notes = landmarks[name].get("notes", "") or ""
        if SENTINEL not in existing_notes:
            sep = " | " if existing_notes else ""
            landmarks[name]["notes"] = f"{existing_notes}{sep}[{SENTINEL}] xyz from FourSeasons rigid model"

    # Apply additions
    for name, new_xyz in additions:
        model_data = model_lms[name]
        landmarks[name] = {
            "xyz": new_xyz,
            "source_cameras": model_data["source_cameras"],
            "author": "rlx",
            "notes": f"[{SENTINEL}] {model_data['comment']}",
        }

    # Write
    with open(LANDMARKS_JSON, "w") as f:
        json.dump(landmarks, f, indent=2)
    print(f"Wrote {LANDMARKS_JSON}")
    print(f"  - {len(overrides)} overrides")
    print(f"  - {len(additions)} additions")
    print()
    print("Next steps:")
    print("  1. Run bundle_adjust to see impact: python3 tools/bundle_adjust.py")
    print("  2. Compare RMS before vs after")
    print("  3. If happy, commit the changes")
    print("  4. If not, restore from backup:")
    print(f"     mv {backup_path} {LANDMARKS_JSON}")


if __name__ == "__main__":
    main()
