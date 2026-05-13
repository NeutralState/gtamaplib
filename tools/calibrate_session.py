#!/usr/bin/env python3
"""
calibrate_session.py — Interactive calibration session for a list of cams.

For each cam in the list, runs through this loop:
  1. Show calibrate_cam.py-style report
  2. Wait for user input:
     - [Enter] re-check state (after marking in UI)
     - [o] optimize via batch_optimize
     - [u] update LMs via /api/update_landmarks (if loss < threshold)
     - [s] skip to next cam
     - [b] bundle_adjust (run global polish at the end)
     - [q] quit

Requires:
  - tools/server.py running on http://localhost:8765
  - UI accessible at the same URL for manual marking

Usage:
    python3 tools/calibrate_session.py --cams "Motorboats (A),Yacht (1)"
    python3 tools/calibrate_session.py --tier unverified --limit 5
    python3 tools/calibrate_session.py --from-order  # uses calibration_order
"""

import argparse
import json
import math
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(THIS_DIR)
DATA_DIR = os.path.join(REPO_DIR, 'gtamapdata')
GEN_DIR = os.path.join(THIS_DIR, 'generated')

CAMERAS_JSON = os.path.join(DATA_DIR, 'cameras.json')
PIXELS_JSON = os.path.join(DATA_DIR, 'pixels.json')
LANDMARKS_JSON = os.path.join(DATA_DIR, 'landmarks.json')
TIERS_JSON = os.path.join(GEN_DIR, 'confidence_tiers.json')

SERVER_BASE = 'http://localhost:8765'

# ── Helpers ───────────────────────────────────────────────────────────

def load_data():
    with open(CAMERAS_JSON) as f:
        cameras = json.load(f)
    with open(PIXELS_JSON) as f:
        pixels = json.load(f)
    with open(LANDMARKS_JSON) as f:
        landmarks = json.load(f)
    try:
        with open(TIERS_JSON) as f:
            tiers_data = json.load(f)
    except Exception:
        tiers_data = {'cameras': {}, 'landmarks': {}}
    cam_tiers = {n: (d.get('tier') if isinstance(d, dict) else d)
                 for n, d in tiers_data.get('cameras', {}).items()}
    lm_tiers = {n: (d.get('tier') if isinstance(d, dict) else d)
                for n, d in tiers_data.get('landmarks', {}).items()}
    return cameras, pixels, landmarks, cam_tiers, lm_tiers


def check_server():
    try:
        urllib.request.urlopen(f'{SERVER_BASE}/api/cameras', timeout=3)
        return True
    except Exception:
        return False


def run_calibrate_cam(cam_name):
    """Run calibrate_cam.py and capture output."""
    script = os.path.join(THIS_DIR, 'calibrate_cam.py')
    result = subprocess.run(
        [sys.executable, script, cam_name],
        capture_output=True, text=True
    )
    return result.stdout + result.stderr


def run_batch_optimize(cam_name):
    """Run batch_optimize.py for this single cam with --apply."""
    script = os.path.join(THIS_DIR, 'batch_optimize.py')
    result = subprocess.run(
        [sys.executable, script, '--cams', cam_name, '--apply'],
        capture_output=True, text=True
    )
    return result.stdout + result.stderr


def call_update_lms(cam_name, cameras):
    """Call /api/update_landmarks via HTTP. Returns response dict."""
    c = cameras[cam_name]
    xyz = c['xyz']
    ypr = c['ypr']
    hfov = c['fov'][0]
    qs = urllib.parse.urlencode({
        'cam': cam_name,
        'x': xyz[0], 'y': xyz[1], 'z': xyz[2],
        'yaw': ypr[0], 'pitch': ypr[1], 'roll': ypr[2] if len(ypr) > 2 else 0,
        'hfov': hfov,
    })
    try:
        with urllib.request.urlopen(f'{SERVER_BASE}/api/update_landmarks?{qs}', timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {'error': f'HTTP {e.code}'}
    except Exception as e:
        return {'error': str(e)}


def run_bundle_adjust():
    """Run bundle_adjust.py."""
    script = os.path.join(THIS_DIR, 'bundle_adjust.py')
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True, text=True
    )
    return result.stdout + result.stderr


def get_cam_url(cam_name):
    """Build URL to open this cam in the UI."""
    return f'{SERVER_BASE}/?cam={urllib.parse.quote(cam_name)}'


# ── Main session loop ──────────────────────────────────────────────────

def session_for_cam(cam_name, idx, total, cameras):
    """Run interactive session for one cam. Returns 'next', 'quit', or 'bundle'."""
    while True:
        print()
        print("═" * 78)
        print(f"  CAM {idx}/{total} : {cam_name}")
        print("═" * 78)
        print()
        print(f"  URL: {get_cam_url(cam_name)}")
        print()

        report = run_calibrate_cam(cam_name)
        # Print just the meat (skip the URL prompt line if duplicated)
        print(report)

        print("─" * 78)
        print("  Commands:")
        print("    [Enter]  Re-check state (after marking in UI)")
        print("    o        Optimize via batch_optimize")
        print("    u        Update LMs (will fail if loss too high)")
        print("    s        Skip to next cam")
        print("    b        Run bundle_adjust (global polish)")
        print("    q        Quit session")
        print()

        try:
            choice = input(f"  [{cam_name}] > ").strip().lower()
        except EOFError:
            return 'quit'
        except KeyboardInterrupt:
            print()
            return 'quit'

        if choice == '':
            # Re-render the report (loop continues)
            continue
        elif choice == 'o':
            print()
            print("Running batch_optimize...")
            print("─" * 78)
            output = run_batch_optimize(cam_name)
            print(output)
            print("─" * 78)
            # Reload cameras to get fresh params
            with open(CAMERAS_JSON) as f:
                cameras.clear()
                cameras.update(json.load(f))
            input("  Press Enter to re-check state... ")
        elif choice == 'u':
            print()
            print("Calling Update LMs...")
            res = call_update_lms(cam_name, cameras)
            if 'error' in res:
                print(f"  ✗ Failed: {res['error']}")
                if 'loss' in res:
                    print(f"     Current cam loss: {res['loss']:.2f}' (threshold: {res.get('threshold', 10)}')")
            else:
                print(f"  ✓ Updated {res.get('updated', 0)} landmarks ({res.get('errors', 0)} errors)")
            input("  Press Enter to continue... ")
        elif choice == 's':
            return 'next'
        elif choice == 'b':
            return 'bundle'
        elif choice == 'q':
            return 'quit'
        else:
            print(f"  ? Unknown command: '{choice}'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cams', help='Comma-separated cam names')
    ap.add_argument('--tier', help='Comma-separated tiers (anchor/high/medium/low/unverified)')
    ap.add_argument('--from-order', action='store_true',
                    help='Use calibration_order to determine the cam list')
    ap.add_argument('--limit', type=int, help='Limit to N cams')
    args = ap.parse_args()

    # Check server
    if not check_server():
        print(f"ERROR: server not reachable at {SERVER_BASE}")
        print(f"       Start it: python3 tools/server.py &")
        sys.exit(1)

    cameras, pixels, _, cam_tiers, _ = load_data()

    # Build cam list
    if args.cams:
        cam_list = [c.strip() for c in args.cams.split(',')]
    elif args.tier:
        wanted = set(t.strip() for t in args.tier.split(','))
        cam_list = [c for c, t in cam_tiers.items() if t in wanted]
    elif args.from_order:
        # Run calibration_order silently, parse cam names from output
        script = os.path.join(THIS_DIR, 'calibration_order.py')
        result = subprocess.run(
            [sys.executable, script, '--tier', 'unverified'],
            capture_output=True, text=True
        )
        # Parse cam names from lines like "   1. ✓ [unverified] CAM_NAME"
        cam_list = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or '[' not in line or ']' not in line:
                continue
            # Match lines starting with a number then dot
            import re
            m = re.match(r'^\d+\.\s+\S+\s+\[\s*\w+\s*\]\s+(.+?)$', line)
            if m:
                cam_list.append(m.group(1).strip())
    else:
        print("ERROR: must specify --cams, --tier, or --from-order")
        sys.exit(1)

    # Filter to existing cams
    cam_list = [c for c in cam_list if c in cameras]
    if args.limit:
        cam_list = cam_list[:args.limit]

    if not cam_list:
        print("ERROR: no valid cams in list")
        sys.exit(1)

    print(f"Starting calibration session for {len(cam_list)} cams.")
    print(f"Cams: {', '.join(cam_list[:5])}{' ...' if len(cam_list) > 5 else ''}")
    print()

    idx = 0
    for cam_name in cam_list:
        idx += 1
        action = session_for_cam(cam_name, idx, len(cam_list), cameras)
        if action == 'quit':
            print()
            print(f"Session ended after cam {idx}/{len(cam_list)}.")
            break
        elif action == 'bundle':
            print()
            print("Running bundle_adjust...")
            print("─" * 78)
            output = run_bundle_adjust()
            # Show just the relevant lines
            for line in output.splitlines():
                if any(k in line for k in ('Initial', 'Final', 'Improvement', 'Excluded', 'obs >')):
                    print(line)
            print("─" * 78)
            input("  Press Enter to continue session... ")
        elif action == 'next':
            continue

    print()
    print("Session complete.")


if __name__ == '__main__':
    main()
