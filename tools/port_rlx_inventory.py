#!/usr/bin/env python3
"""
port_rlx_inventory.py v4 — Read-only inventory of rlx upstream data.

Uses importlib to load rlx's gtamapdata.py as a module, which handles
the DictComp definitions that ast.literal_eval can't parse.

Side effect: rlx's gtamapdata.py extracts 3 zip files (frames, fonts, maps)
on import. We isolate this to a temp directory (/tmp/rlx_import_workspace)
so it doesn't touch our repo.

Usage:
    python3 tools/port_rlx_inventory.py            # generate report
    python3 tools/port_rlx_inventory.py --verbose
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys

THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
REPO_DIR    = os.path.dirname(THIS_DIR)
DATA_DIR    = os.path.join(REPO_DIR, 'gtamapdata')
GENERATED   = os.path.join(THIS_DIR, 'generated')
REPORT_PATH = os.path.join(GENERATED, 'rlx_port_inventory.json')

RLX_WORKSPACE = '/tmp/rlx_import_workspace'


def fetch_rlx_file_to_workspace(filename, dest_dir):
    result = subprocess.run(
        ['git', 'show', f'upstream/main:{filename}'],
        cwd=REPO_DIR,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    dest_path = os.path.join(dest_dir, filename)
    with open(dest_path, 'wb') as f:
        f.write(result.stdout)
    return True


def setup_rlx_workspace():
    os.makedirs(RLX_WORKSPACE, exist_ok=True)
    print(f"Setting up rlx import workspace at {RLX_WORKSPACE}...")
    files_to_fetch = ['gtamapdata.py', 'gtamaplib.py', 'gtamaputils.py', '__init__.py']
    for fname in files_to_fetch:
        ok = fetch_rlx_file_to_workspace(fname, RLX_WORKSPACE)
        if ok:
            size = os.path.getsize(os.path.join(RLX_WORKSPACE, fname))
            print(f"  ✓ {fname:<25} ({size:,} bytes)")
        else:
            print(f"  ⚠ {fname:<25} (skipped — not in upstream)")

    # rlx's gtamapdata.py tries to extract fonts.zip/frames.zip/maps.zip on
    # import. We don't need them (we only want cameras/landmarks/pixels dicts).
    # Create the target directories as empty so the extraction loop skips them.
    for stub in ('fonts', 'frames', 'maps'):
        os.makedirs(os.path.join(RLX_WORKSPACE, stub), exist_ok=True)
    print("  ✓ created empty fonts/, frames/, maps/ dirs to skip zip extraction")


def load_rlx_module():
    setup_rlx_workspace()
    print("\nImporting rlx's gtamapdata as a module...")
    spec_path = os.path.join(RLX_WORKSPACE, 'gtamapdata.py')
    spec = importlib.util.spec_from_file_location("rlx_gtamapdata", spec_path)
    if spec is None or spec.loader is None:
        print("ERROR: importlib could not create a module spec")
        sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, RLX_WORKSPACE)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f"ERROR: rlx's gtamapdata.py failed to import: {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        sys.path.pop(0)
    return mod


def strip_id_prefix(name):
    if name.startswith('[') and '] ' in name:
        end = name.index('] ')
        return name[end + 2:], name[1:end]
    return name, None


def load_our_data():
    out = {}
    for name in ('cameras', 'landmarks', 'pixels'):
        path = os.path.join(DATA_DIR, f'{name}.json')
        if not os.path.exists(path):
            print(f"ERROR: {path} not found")
            sys.exit(1)
        with open(path) as f:
            out[name] = json.load(f)
    return out


def extract_cam_fields(rlx_data):
    """Get {player_xyz, cam_xyz, ypr, fov, size, source} from rlx entry (dict or tuple)."""
    if isinstance(rlx_data, dict):
        return {
            'player_xyz': list(rlx_data['player']) if rlx_data.get('player') else None,
            'cam_xyz':    list(rlx_data['xyz']) if rlx_data.get('xyz') else None,
            'ypr':        list(rlx_data['ypr']) if rlx_data.get('ypr') else None,
            'fov':        list(rlx_data['fov']) if rlx_data.get('fov') else None,
            'size':       list(rlx_data['size']) if rlx_data.get('size') else None,
            'source':     rlx_data.get('source'),
        }
    if not isinstance(rlx_data, (tuple, list)):
        return {'_raw': rlx_data, '_note': 'unexpected entry shape'}

    def _safe(v):
        if v is None: return None
        if isinstance(v, (tuple, list)): return list(v)
        return v

    return {
        'player_xyz': _safe(rlx_data[0]) if len(rlx_data) > 0 else None,
        'cam_xyz':    _safe(rlx_data[1]) if len(rlx_data) > 1 else None,
        'ypr':        _safe(rlx_data[2]) if len(rlx_data) > 2 else None,
        'fov':        _safe(rlx_data[3]) if len(rlx_data) > 3 else None,
        'size':       _safe(rlx_data[4]) if len(rlx_data) > 4 else None,
        'source':     rlx_data[5]        if len(rlx_data) > 5 else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    rlx_mod = load_rlx_module()

    rlx_cameras = getattr(rlx_mod, 'cameras', None)
    rlx_landmarks = getattr(rlx_mod, 'landmarks', None)
    rlx_pixels = getattr(rlx_mod, 'pixels', None)

    if rlx_cameras is None:
        print("ERROR: rlx module has no 'cameras' attribute")
        sys.exit(1)

    print(f"\nrlx data loaded:")
    print(f"  cameras   : {len(rlx_cameras)} entries")
    print(f"  landmarks : {len(rlx_landmarks) if rlx_landmarks else 0} entries")
    print(f"  pixels    : {len(rlx_pixels) if rlx_pixels else 0} cameras with pixels")

    print("\nLoading our data...")
    ours = load_our_data()
    print(f"  cameras   : {len(ours['cameras'])} entries")
    print(f"  landmarks : {len(ours['landmarks'])} entries")
    print(f"  pixels    : {len(ours['pixels'])} cameras with pixels")

    sample_cam = next(iter(rlx_cameras.values()), None)
    cam_format = 'dict' if isinstance(sample_cam, dict) else 'tuple'
    print(f"\nrlx camera format detected: {cam_format}")

    # ── Compare cameras ───────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("CAMERA COMPARISON")
    print("─" * 70)

    our_cam_names = set(ours['cameras'].keys())
    rlx_cam_entries = []
    for rlx_key, rlx_data in rlx_cameras.items():
        stripped, id_part = strip_id_prefix(rlx_key)
        rlx_cam_entries.append({
            'rlx_key': rlx_key,
            'stripped_name': stripped,
            'id': id_part,
            'data': rlx_data,
        })

    unique_to_rlx = [e for e in rlx_cam_entries if e['stripped_name'] not in our_cam_names]
    in_both = [e for e in rlx_cam_entries if e['stripped_name'] in our_cam_names]
    rlx_stripped_names = {e['stripped_name'] for e in rlx_cam_entries}
    unique_to_us = sorted(our_cam_names - rlx_stripped_names)

    print(f"Unique to rlx : {len(unique_to_rlx)} cameras")
    print(f"In both       : {len(in_both)} cameras")
    print(f"Unique to us  : {len(unique_to_us)} cameras")

    if args.verbose and unique_to_rlx:
        print("\nCameras unique to rlx (candidates for porting):")
        for e in unique_to_rlx[:50]:
            fields = extract_cam_fields(e['data'])
            src = fields.get('source') or '?'
            id_str = f"[{e['id']:>6}]" if e['id'] else "[       ]"
            print(f"  {id_str} {e['stripped_name']:<50}  {src}")
        if len(unique_to_rlx) > 50:
            print(f"  ... and {len(unique_to_rlx) - 50} more (see report JSON)")

    # ── Compare landmarks ────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("LANDMARK COMPARISON")
    print("─" * 70)

    rlx_lms = rlx_landmarks or {}
    our_lm_names = set(ours['landmarks'].keys())
    rlx_lm_names = set(rlx_lms.keys())
    unique_lms_rlx = sorted(rlx_lm_names - our_lm_names)
    in_both_lms = sorted(rlx_lm_names & our_lm_names)
    unique_lms_us = sorted(our_lm_names - rlx_lm_names)

    print(f"Unique to rlx : {len(unique_lms_rlx)} landmarks")
    print(f"In both       : {len(in_both_lms)} landmarks")
    print(f"Unique to us  : {len(unique_lms_us)} landmarks")

    # ── Compare pixels ───────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("PIXEL COMPARISON")
    print("─" * 70)

    rlx_pixels = rlx_pixels or {}
    rlx_pixels_by_stripped = {}
    for rlx_key, lm_pixels in rlx_pixels.items():
        stripped, _ = strip_id_prefix(rlx_key)
        rlx_pixels_by_stripped[stripped] = lm_pixels

    new_pixels = []
    same_pixels = 0
    unexpected_struct_cams = []

    for cam, lm_pix in rlx_pixels_by_stripped.items():
        if not isinstance(lm_pix, dict):
            unexpected_struct_cams.append((cam, type(lm_pix).__name__))
            continue
        our_lm_pix = ours['pixels'].get(cam, {})
        if not isinstance(our_lm_pix, dict):
            our_lm_pix = {}
        for lm, px in lm_pix.items():
            if lm in our_lm_pix:
                same_pixels += 1
                continue
            new_pixels.append({
                'cam': cam,
                'lm': lm,
                'px': list(px) if isinstance(px, (tuple, list)) else px,
            })

    print(f"Pixels both have   : {same_pixels} (cam, lm) pairs")
    print(f"New pixels in rlx  : {len(new_pixels)} (cam, lm) pairs")
    if unexpected_struct_cams:
        print(f"  ⚠ {len(unexpected_struct_cams)} cams have unexpected pixel structure (skipped)")

    # ── Build the final report ───────────────────────────────────────────
    os.makedirs(GENERATED, exist_ok=True)
    rlx_commit = subprocess.run(
        ['git', 'rev-parse', '--short', 'upstream/main'],
        cwd=REPO_DIR, capture_output=True, text=True
    ).stdout.strip()
    now_iso = subprocess.run(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'],
                             capture_output=True, text=True).stdout.strip()

    cameras_unique_to_rlx_serialized = []
    for e in unique_to_rlx:
        fields = extract_cam_fields(e['data'])
        n_pix = 0
        if e['stripped_name'] in rlx_pixels_by_stripped:
            lp = rlx_pixels_by_stripped[e['stripped_name']]
            if isinstance(lp, dict):
                n_pix = len(lp)
        cameras_unique_to_rlx_serialized.append({
            'rlx_key': e['rlx_key'],
            'stripped_name': e['stripped_name'],
            'id': e['id'],
            **fields,
            'has_pixels': e['stripped_name'] in rlx_pixels_by_stripped,
            'n_pixels': n_pix,
        })

    report = {
        'generated_at': now_iso,
        'rlx_commit': rlx_commit,
        'cam_format': cam_format,
        'totals': {
            'rlx_cameras': len(rlx_cameras),
            'rlx_landmarks': len(rlx_lms),
            'rlx_pixels_cams': len(rlx_pixels),
            'our_cameras': len(ours['cameras']),
            'our_landmarks': len(ours['landmarks']),
            'our_pixels_cams': len(ours['pixels']),
            'cameras_unique_to_rlx': len(unique_to_rlx),
            'landmarks_unique_to_rlx': len(unique_lms_rlx),
            'pixels_new': len(new_pixels),
            'pixels_shared': same_pixels,
        },
        'cameras_unique_to_rlx': cameras_unique_to_rlx_serialized,
        'landmarks_unique_to_rlx': [
            {
                'name': n,
                'xyz': list(rlx_lms[n]) if isinstance(rlx_lms[n], (tuple, list)) else rlx_lms[n],
            }
            for n in unique_lms_rlx
        ],
        'pixels_new': new_pixels,
        'cameras_unique_to_us': unique_to_us,
        'landmarks_unique_to_us': unique_lms_us,
    }

    with open(REPORT_PATH, 'w') as f:
        json.dump(report, f, indent=2)

    print("\n" + "─" * 70)
    print(f"REPORT WRITTEN: {REPORT_PATH}")
    print("─" * 70)
    print()
    print("Quick scan commands:")
    print(f"  jq '.totals' {REPORT_PATH}")
    print(f"  jq '[.cameras_unique_to_rlx[] | select(.has_pixels and .source != \"?\")] | length' {REPORT_PATH}")
    print(f"  jq '[.cameras_unique_to_rlx[] | select(.has_pixels and .source != \"?\") | {{name: .stripped_name, n_pixels, source}}]' {REPORT_PATH}")


if __name__ == '__main__':
    main()
