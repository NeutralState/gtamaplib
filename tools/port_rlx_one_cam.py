#!/usr/bin/env python3
"""
port_rlx_one_cam.py — Port a single camera (and its pixels) from rlx's
upstream data into our cameras.json + pixels.json.

This is the pilot script for the rlx port v2. Designed to:
  - Load rlx's gtamapdata module (via /tmp/rlx_import_workspace)
  - Extract one cam by name (after stripping the [Lx/y] prefix)
  - Map rlx's schema to ours
  - Write the new entry to cameras.json
  - Write the cam's pixels (filtered to landmarks we already have)
  - Backup originals to .bak_pre_port_<cam_safe_name>
  - Idempotent: refuses if cam already exists in our cameras.json

After porting, the user runs:
    python3 tools/intake_camera.py "<cam name>"
to validate the ported cam against our world skeleton. If intake commits
the verdict, the user applies refined params via:
    python3 tools/refine/refine_camera.py "<cam name>" --apply

Usage:
    python3 tools/port_rlx_one_cam.py "Yacht (2)"             # dry run
    python3 tools/port_rlx_one_cam.py "Yacht (2)" --apply     # writes changes
"""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(THIS_DIR)
DATA_DIR = os.path.join(REPO_DIR, 'gtamapdata')

CAMERAS_JSON = os.path.join(DATA_DIR, 'cameras.json')
PIXELS_JSON  = os.path.join(DATA_DIR, 'pixels.json')
LANDMARKS_JSON = os.path.join(DATA_DIR, 'landmarks.json')

RLX_WORKSPACE = '/tmp/rlx_import_workspace'


def fetch_rlx_file_to_workspace(filename, dest_dir):
    result = subprocess.run(
        ['git', 'show', f'upstream/main:{filename}'],
        cwd=REPO_DIR, capture_output=True, check=False,
    )
    if result.returncode != 0:
        return False
    with open(os.path.join(dest_dir, filename), 'wb') as f:
        f.write(result.stdout)
    return True


def setup_rlx_workspace():
    os.makedirs(RLX_WORKSPACE, exist_ok=True)
    files_to_fetch = ['gtamapdata.py', 'gtamaplib.py', 'gtamaputils.py', '__init__.py']
    for fname in files_to_fetch:
        fetch_rlx_file_to_workspace(fname, RLX_WORKSPACE)
    # Prevent zip extraction (rlx's import-time code)
    for stub in ('fonts', 'frames', 'maps'):
        os.makedirs(os.path.join(RLX_WORKSPACE, stub), exist_ok=True)


def load_rlx_module():
    setup_rlx_workspace()
    spec_path = os.path.join(RLX_WORKSPACE, 'gtamapdata.py')
    spec = importlib.util.spec_from_file_location("rlx_gtamapdata", spec_path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, RLX_WORKSPACE)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f"ERROR: rlx's gtamapdata.py failed to import: {e}")
        sys.exit(1)
    finally:
        sys.path.pop(0)
    return mod


def parse_rlx_tuple_cameras(rlx_src):
    """
    rlx's gtamapdata.py has TWO definitions of `cameras`:
      1. A tuple-form dict literal (with [Lx/y] id prefixes in keys)
      2. A dict-comprehension that transforms (1) into our-like schema
         but strips the [Lx/y] prefix from keys

    The dict-comp version is what's exposed as `rlx_mod.cameras` after import,
    but it loses the id. To recover ids for cams that were renamed-and-stripped,
    we parse the tuple-form version too.

    Returns: dict {stripped_name: id_str} mapping cam name → original id prefix.
    Note: tuple version has 244 entries (commented + uncommented), so we extract
    every '[X/Y] Name' string that appears as a dict key in the source.
    """
    import re
    # Match dict keys like "[L1/4] Diner (NE)" or "[ L1/4] Diner" (possibly padded)
    pattern = re.compile(r'"\[\s*([^\]\s/]+/[^\]\s]+)\s*\]\s+([^"]+)"\s*:')
    id_by_name = {}
    for m in pattern.finditer(rlx_src):
        id_part = m.group(1).strip()
        name_part = m.group(2).strip()
        # Last-write-wins for the rare case where same name has multiple definitions
        # (e.g. commented-out variants in rlx's source)
        id_by_name[name_part] = id_part
    return id_by_name


def strip_id_prefix(name):
    if name.startswith('[') and '] ' in name:
        end = name.index('] ')
        return name[end + 2:], name[1:end]
    return name, None


def extract_cam_fields(rlx_data):
    """Get our-schema fields from rlx entry (works for dict or tuple form)."""
    if isinstance(rlx_data, dict):
        return {
            'player': list(rlx_data['player']) if rlx_data.get('player') else None,
            'xyz':    list(rlx_data['xyz']),
            'ypr':    list(rlx_data['ypr']),
            'fov':    list(rlx_data['fov']),
            'size':   list(rlx_data['size']),
            'source': rlx_data.get('source'),
        }
    # tuple form
    def _safe(v):
        return list(v) if isinstance(v, (tuple, list)) else v

    return {
        'player': _safe(rlx_data[0]),
        'xyz':    _safe(rlx_data[1]),
        'ypr':    _safe(rlx_data[2]),
        'fov':    _safe(rlx_data[3]),
        'size':   _safe(rlx_data[4]),
        'source': rlx_data[5] if len(rlx_data) > 5 else None,
    }


def find_rlx_cam(rlx_cameras, target_name):
    """Find rlx's cam entry by stripped name. Returns (key, data) or (None, None)."""
    for rlx_key, data in rlx_cameras.items():
        stripped, _ = strip_id_prefix(rlx_key)
        if stripped == target_name:
            return rlx_key, data
    return None, None


def find_rlx_pixels(rlx_pixels, target_name):
    """Find rlx's pixels for a cam by stripped name. Returns dict {lm: (x,y)} or None."""
    if not rlx_pixels:
        return None
    for rlx_key, lm_pix in rlx_pixels.items():
        stripped, _ = strip_id_prefix(rlx_key)
        if stripped == target_name:
            return lm_pix if isinstance(lm_pix, dict) else None
    return None


def atomic_write_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def safe_name(name):
    return ''.join(c if c.isalnum() else '_' for c in name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cam_name', help='Cam name to port (e.g. "Yacht (2)")')
    ap.add_argument('--apply', action='store_true', help='Actually write changes')
    ap.add_argument('--include-missing-pixels', action='store_true',
                    help='Port pixels even for landmarks we don\'t have '
                         '(default: skip those, intake will fail anyway)')
    args = ap.parse_args()

    print(f"Porting cam '{args.cam_name}' from rlx upstream...")
    print()

    # ── Load our current state ────────────────────────────────────────────
    with open(CAMERAS_JSON) as f:
        our_cameras = json.load(f)
    with open(PIXELS_JSON) as f:
        our_pixels = json.load(f)
    with open(LANDMARKS_JSON) as f:
        our_landmarks = json.load(f)

    if args.cam_name in our_cameras:
        print(f"⚠ '{args.cam_name}' already exists in our cameras.json")
        print("  Refusing to overwrite. Delete the entry manually if you want to re-port.")
        sys.exit(1)

    # ── Load rlx data ─────────────────────────────────────────────────────
    print("Loading rlx upstream data...")
    rlx_mod = load_rlx_module()
    rlx_cameras = getattr(rlx_mod, 'cameras', None) or {}
    rlx_pixels  = getattr(rlx_mod, 'pixels', None) or {}

    # Also parse the tuple-form source to recover the [Lx/y] id prefix
    # (dict-comprehension version strips this).
    rlx_src_path = os.path.join(RLX_WORKSPACE, 'gtamapdata.py')
    with open(rlx_src_path) as f:
        rlx_src = f.read()
    id_by_name = parse_rlx_tuple_cameras(rlx_src)
    print(f"  ✓ recovered {len(id_by_name)} cam ids from tuple-form source")

    rlx_key, rlx_data = find_rlx_cam(rlx_cameras, args.cam_name)
    if rlx_data is None:
        print(f"ERROR: cam '{args.cam_name}' not found in rlx upstream")
        sys.exit(1)
    print(f"  ✓ found rlx entry: {rlx_key}")

    # ── Map fields ────────────────────────────────────────────────────────
    fields = extract_cam_fields(rlx_data)

    # Resolve the cam's id (essential — our gtamapdata.py requires it)
    cam_id = id_by_name.get(args.cam_name)
    if cam_id is None:
        # Fall back to a generated id marking the rlx origin
        cam_id = f'RLX/{safe_name(args.cam_name)}'
        print(f"  ⚠ no [Lx/y] id found in rlx source for '{args.cam_name}'")
        print(f"     using generated id: {cam_id}")
    else:
        print(f"  ✓ recovered original id: {cam_id}")

    # Build our schema entry (id field first, matching existing convention)
    new_cam_entry = {'id': cam_id}
    for k, v in fields.items():
        if v is not None or k == 'player':
            new_cam_entry[k] = v

    # Ensure ypr has 3 components (rlx already does this, but defensive)
    while len(new_cam_entry.get('ypr', [])) < 3:
        new_cam_entry['ypr'].append(0.0)

    print()
    print(f"Mapped fields for our schema:")
    for k, v in new_cam_entry.items():
        print(f"  {k:<10}: {v}")

    # ── Find pixels ───────────────────────────────────────────────────────
    rlx_lm_pixels = find_rlx_pixels(rlx_pixels, args.cam_name)
    if rlx_lm_pixels is None:
        print(f"\n⚠ No pixels found for '{args.cam_name}' in rlx upstream")
        print("  The cam will be ported with no pixels — intake will not be able")
        print("  to validate it until you mark pixels manually in the calib UI.")
        new_pixels_entry = None
    else:
        # Filter pixels to landmarks we have (unless --include-missing-pixels)
        kept = {}
        skipped = []
        for lm, px in rlx_lm_pixels.items():
            if lm in our_landmarks or args.include_missing_pixels:
                kept[lm] = list(px) if isinstance(px, (tuple, list)) else px
            else:
                skipped.append(lm)

        print()
        print(f"Pixels:")
        print(f"  Total in rlx        : {len(rlx_lm_pixels)}")
        print(f"  Landmarks we have   : {len(kept)}")
        if skipped:
            print(f"  Skipped (missing LM): {len(skipped)}")
            for lm in skipped:
                print(f"     - {lm}")

        if len(kept) < 3:
            print()
            print(f"⚠ Only {len(kept)} usable pixel(s) after filtering")
            print(f"  intake_camera requires ≥3 obs to validate.")
            print(f"  Cam will still be ported but intake will REJECT it.")

        new_pixels_entry = kept if kept else None

    # ── Show what will change ─────────────────────────────────────────────
    print()
    print("─" * 70)
    print("PLANNED CHANGES")
    print("─" * 70)
    print(f"  cameras.json : add 1 entry for '{args.cam_name}'")
    if new_pixels_entry:
        print(f"  pixels.json  : add {len(new_pixels_entry)} pixel mark(s) for '{args.cam_name}'")
    else:
        print(f"  pixels.json  : no changes (no usable pixels)")

    if not args.apply:
        print()
        print("(dry run — re-run with --apply to write changes)")
        sys.exit(0)

    # ── Apply changes ─────────────────────────────────────────────────────
    sn = safe_name(args.cam_name)
    cameras_bak = CAMERAS_JSON + f'.bak_pre_port_{sn}'
    pixels_bak  = PIXELS_JSON  + f'.bak_pre_port_{sn}'

    print()
    print("Applying changes...")
    shutil.copy(CAMERAS_JSON, cameras_bak)
    print(f"  ✓ backup: {cameras_bak}")
    our_cameras[args.cam_name] = new_cam_entry
    atomic_write_json(CAMERAS_JSON, our_cameras)
    print(f"  ✓ cameras.json updated")

    if new_pixels_entry:
        shutil.copy(PIXELS_JSON, pixels_bak)
        print(f"  ✓ backup: {pixels_bak}")
        if args.cam_name in our_pixels:
            our_pixels[args.cam_name].update(new_pixels_entry)
        else:
            our_pixels[args.cam_name] = new_pixels_entry
        atomic_write_json(PIXELS_JSON, our_pixels)
        print(f"  ✓ pixels.json updated")

    print()
    print("─" * 70)
    print("DONE")
    print("─" * 70)
    print()
    print("Next steps:")
    print(f"  1. Run intake to validate:")
    print(f"     python3 tools/intake_camera.py \"{args.cam_name}\"")
    print(f"  2. If verdict=commit, apply refinement:")
    print(f"     python3 tools/refine/refine_camera.py \"{args.cam_name}\" --apply")
    print(f"  3. Review with: git diff gtamapdata/cameras.json gtamapdata/pixels.json")
    print()
    print(f"To revert: cp {cameras_bak} {CAMERAS_JSON}")
    if new_pixels_entry:
        print(f"           cp {pixels_bak} {PIXELS_JSON}")


if __name__ == '__main__':
    main()
