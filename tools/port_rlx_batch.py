#!/usr/bin/env python3
"""
port_rlx_batch.py — Port all cams unique to rlx (with sourced timestamps)
into our cameras.json + pixels.json in one batch.

Filters:
  - Skips Minimap/Player/AIWE pixels (rlx ignores these in his own solver
    too — they're decorative annotations, not real constraints)
  - Skips pixels pointing to landmarks we don't have
  - Skips cams already in our cameras.json (idempotent)
  - Optionally limits to cams with .source != "?" (sourced only)

After porting, prints a per-cam summary: how many pixels were portable,
how many manual marks the user will need to add in the UI to validate.

Backs up cameras.json + pixels.json before any write (single backup,
not per-cam — keeps it simple).

Usage:
    python3 tools/port_rlx_batch.py                # dry run (sourced cams only)
    python3 tools/port_rlx_batch.py --apply        # write changes
    python3 tools/port_rlx_batch.py --all          # include "?" sourced cams too
"""

import argparse
import importlib.util
import json
import os
import re
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

# Pixels rlx himself ignores in his solver (see gtamaplib.py L683, L1056)
SKIP_LM_PREFIXES = ('Minimap', 'Player', 'AIWE')


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
    for fname in ['gtamapdata.py', 'gtamaplib.py', 'gtamaputils.py', '__init__.py']:
        fetch_rlx_file_to_workspace(fname, RLX_WORKSPACE)
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


def strip_id_prefix(name):
    if name.startswith('[') and '] ' in name:
        end = name.index('] ')
        return name[end + 2:], name[1:end]
    return name, None


def parse_rlx_tuple_cameras(rlx_src):
    """Parse rlx's tuple-form cameras dict to recover [Lx/y] id prefixes."""
    pattern = re.compile(r'"\[\s*([^\]\s/]+/[^\]\s]+)\s*\]\s+([^"]+)"\s*:')
    id_by_name = {}
    for m in pattern.finditer(rlx_src):
        id_part = m.group(1).strip()
        name_part = m.group(2).strip()
        id_by_name[name_part] = id_part
    return id_by_name


def extract_cam_fields(rlx_data):
    if isinstance(rlx_data, dict):
        return {
            'player': list(rlx_data['player']) if rlx_data.get('player') else None,
            'xyz':    list(rlx_data['xyz']),
            'ypr':    list(rlx_data['ypr']),
            'fov':    list(rlx_data['fov']),
            'size':   list(rlx_data['size']),
            'source': rlx_data.get('source'),
        }
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


def is_skippable_lm(lm_name):
    """Check if a landmark name is one rlx skips in his solver (Minimap etc)."""
    return any(lm_name.startswith(p) for p in SKIP_LM_PREFIXES)


def atomic_write_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def safe_name(name):
    return ''.join(c if c.isalnum() else '_' for c in name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Actually write changes')
    ap.add_argument('--all', action='store_true',
                    help='Include cams with source "?" (default: sourced only)')
    args = ap.parse_args()

    print("Loading our current state...")
    with open(CAMERAS_JSON) as f:
        our_cameras = json.load(f)
    with open(PIXELS_JSON) as f:
        our_pixels = json.load(f)
    with open(LANDMARKS_JSON) as f:
        our_landmarks = json.load(f)
    print(f"  cams={len(our_cameras)}, pixels_cams={len(our_pixels)}, lms={len(our_landmarks)}")

    print("\nLoading rlx upstream data...")
    rlx_mod = load_rlx_module()
    rlx_cameras = getattr(rlx_mod, 'cameras', None) or {}
    rlx_pixels  = getattr(rlx_mod, 'pixels', None) or {}

    rlx_src_path = os.path.join(RLX_WORKSPACE, 'gtamapdata.py')
    with open(rlx_src_path) as f:
        rlx_src = f.read()
    id_by_name = parse_rlx_tuple_cameras(rlx_src)
    print(f"  rlx cams={len(rlx_cameras)}, recovered ids for {len(id_by_name)} cams")

    # Build lookup of rlx pixels by stripped name
    rlx_pixels_by_stripped = {}
    for rlx_key, lm_pix in rlx_pixels.items():
        stripped, _ = strip_id_prefix(rlx_key)
        if isinstance(lm_pix, dict):
            rlx_pixels_by_stripped[stripped] = lm_pix

    # Identify cams unique to rlx
    candidates = []
    for rlx_key, rlx_data in rlx_cameras.items():
        stripped, _ = strip_id_prefix(rlx_key)
        if stripped in our_cameras:
            continue  # already have it
        fields = extract_cam_fields(rlx_data)
        src = fields.get('source') or '?'

        if not args.all and src == '?':
            continue  # skip unsourced unless --all

        candidates.append({
            'name': stripped,
            'fields': fields,
            'id': id_by_name.get(stripped),
        })

    print(f"\n{len(candidates)} candidate cams to port"
          f" ({'all sources' if args.all else 'sourced only — use --all for unsourced too'})")

    # Plan per cam
    plan = []
    for c in candidates:
        name = c['name']
        rlx_lm_pix = rlx_pixels_by_stripped.get(name, {})

        portable_pixels = {}
        skipped_minimap = []
        skipped_missing_lm = []
        for lm, px in rlx_lm_pix.items():
            if is_skippable_lm(lm):
                skipped_minimap.append(lm)
                continue
            if lm not in our_landmarks:
                skipped_missing_lm.append(lm)
                continue
            portable_pixels[lm] = list(px) if isinstance(px, (tuple, list)) else px

        plan.append({
            'name': name,
            'id': c['id'],
            'fields': c['fields'],
            'portable_pixels': portable_pixels,
            'skipped_minimap': skipped_minimap,
            'skipped_missing_lm': skipped_missing_lm,
            'manual_marks_needed': max(0, 3 - len(portable_pixels)),  # intake needs ≥3
        })

    # Summary table
    print("\n" + "─" * 90)
    print(f"{'cam':<35} {'id':<10} {'source':<25} {'pix':>4} {'manual?':<10}")
    print("─" * 90)
    auto_portable = 0
    needs_manual = 0
    for p in plan:
        src = (p['fields'].get('source') or '?')[:24]
        n_pix = len(p['portable_pixels'])
        manual = f"need {p['manual_marks_needed']}+" if p['manual_marks_needed'] else "—"
        print(f"  {p['name']:<33} {p['id'] or '-':<10} {src:<25} {n_pix:>4} {manual:<10}")
        if p['manual_marks_needed']:
            needs_manual += 1
        else:
            auto_portable += 1
    print("─" * 90)
    print(f"\nTotal: {len(plan)} cams")
    print(f"  {auto_portable} portable as-is (≥3 usable pixels)")
    print(f"  {needs_manual} need manual marking in UI after port")

    if not args.apply:
        print("\n(dry run — re-run with --apply to write changes)")
        sys.exit(0)

    # Apply
    cameras_bak = CAMERAS_JSON + '.bak_pre_batch_port'
    pixels_bak  = PIXELS_JSON  + '.bak_pre_batch_port'
    shutil.copy(CAMERAS_JSON, cameras_bak)
    shutil.copy(PIXELS_JSON, pixels_bak)
    print(f"\n✓ Backups:")
    print(f"  {cameras_bak}")
    print(f"  {pixels_bak}")

    n_cam_added = 0
    n_pix_added = 0
    for p in plan:
        name = p['name']
        cam_id = p['id'] or f'RLX/{safe_name(name)}'
        fields = p['fields']

        new_entry = {'id': cam_id}
        for k, v in fields.items():
            if v is not None or k == 'player':
                new_entry[k] = v
        # Ensure ypr has 3 components
        while len(new_entry.get('ypr', [])) < 3:
            new_entry['ypr'].append(0.0)

        our_cameras[name] = new_entry
        n_cam_added += 1

        if p['portable_pixels']:
            if name in our_pixels:
                our_pixels[name].update(p['portable_pixels'])
            else:
                our_pixels[name] = p['portable_pixels']
            n_pix_added += len(p['portable_pixels'])

    atomic_write_json(CAMERAS_JSON, our_cameras)
    atomic_write_json(PIXELS_JSON, our_pixels)
    print(f"\n✓ Wrote:")
    print(f"  cameras.json: +{n_cam_added} entries")
    print(f"  pixels.json:  +{n_pix_added} pixel marks")

    print("\nNext steps:")
    print("  1. Regen tier data:")
    print("     python3 tools/compute_confidence_tiers.py")
    print("  2. For cams with manual marking needed, open in UI calib:")
    print(f"     open http://localhost:8765/calib.html")
    print("  3. After marking landmarks in UI for a cam, hit Optimize then Save")
    print("  4. Validate via intake:")
    print('     python3 tools/intake_camera.py "<cam name>"')
    print()
    print(f"To revert all: cp {cameras_bak} {CAMERAS_JSON}")
    print(f"               cp {pixels_bak} {PIXELS_JSON}")


if __name__ == '__main__':
    main()
