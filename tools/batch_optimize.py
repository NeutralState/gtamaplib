#!/usr/bin/env python3
"""
batch_optimize.py — Batch-optimize multiple cams via the running server API.

For each cam in the input list (or all cams matching a filter):
  1. Fetch current params from cameras.json
  2. POST to /api/optimize to refine params (uses tier-weighted loss now)
  3. If --update-lms and loss < threshold, also POST /api/update_landmarks
  4. Print before/after report
  5. Optionally chain into bundle_adjust at the end

Safety:
  - Server must be running on http://localhost:8765
  - Defaults: --no-update-lms (won't touch landmarks unless explicitly asked)
  - Dry-run by default (just shows what would happen)
  - --apply actually writes through the API

Usage:
    python3 tools/batch_optimize.py --tier unverified           # dry-run all unverified
    python3 tools/batch_optimize.py --tier unverified --apply   # actually run
    python3 tools/batch_optimize.py --cams "Yacht (1),Yacht (2)" --apply
    python3 tools/batch_optimize.py --tier low --apply --update-lms --update-threshold 5.0
    python3 tools/batch_optimize.py --apply --polish            # batch optimize + bundle_adjust
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import subprocess

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(THIS_DIR)
DATA_DIR = os.path.join(REPO_DIR, 'gtamapdata')
GEN_DIR = os.path.join(THIS_DIR, 'generated')

CAMERAS_JSON = os.path.join(DATA_DIR, 'cameras.json')
PIXELS_JSON = os.path.join(DATA_DIR, 'pixels.json')
TIERS_JSON = os.path.join(GEN_DIR, 'confidence_tiers.json')

SERVER_BASE = 'http://localhost:8765'


def fetch_url(url, timeout=30):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.URLError as e:
        return {'error': f'connection failed: {e}'}
    except Exception as e:
        return {'error': f'fetch failed: {e}'}


def optimize_cam(cam_name, xyz, ypr, hfov):
    """Call /api/optimize with given params. Returns response dict."""
    qs = urllib.parse.urlencode({
        'cam': cam_name,
        'x': xyz[0], 'y': xyz[1], 'z': xyz[2],
        'yaw': ypr[0], 'pitch': ypr[1], 'roll': ypr[2] if len(ypr) > 2 else 0,
        'hfov': hfov,
    })
    return fetch_url(f'{SERVER_BASE}/api/optimize?{qs}')


def update_landmarks(cam_name, xyz, ypr, hfov):
    """Call /api/update_landmarks. Returns response dict."""
    qs = urllib.parse.urlencode({
        'cam': cam_name,
        'x': xyz[0], 'y': xyz[1], 'z': xyz[2],
        'yaw': ypr[0], 'pitch': ypr[1], 'roll': ypr[2] if len(ypr) > 2 else 0,
        'hfov': hfov,
    })
    return fetch_url(f'{SERVER_BASE}/api/update_landmarks?{qs}', timeout=60)


def save_cam(cam_name, xyz, ypr, hfov):
    """Call /api/save to persist the cam params. Returns response dict."""
    qs = urllib.parse.urlencode({
        'cam': cam_name,
        'x': xyz[0], 'y': xyz[1], 'z': xyz[2],
        'yaw': ypr[0], 'pitch': ypr[1], 'roll': ypr[2] if len(ypr) > 2 else 0,
        'hfov': hfov,
    })
    return fetch_url(f'{SERVER_BASE}/api/save?{qs}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tier', help='Filter by tier (anchor/high/medium/low/unverified). Can be comma-separated.')
    ap.add_argument('--cams', help='Comma-separated cam names (overrides --tier)')
    ap.add_argument('--apply', action='store_true', help='Actually run (default: dry-run)')
    ap.add_argument('--update-lms', action='store_true',
                    help='Also call /api/update_landmarks after optimize (default: skip)')
    ap.add_argument('--update-threshold', type=float, default=5.0,
                    help='Only update LMs if loss < this arcmin (default: 5.0, server default is 10.0)')
    # ── BATCH-SAFETY-V1 ──
    ap.add_argument('--save-threshold', type=float, default=10.0,
                    help='Refuse save if loss_after > this arcmin (default: 10.0)')
    ap.add_argument('--regression-tolerance', type=float, default=1.05,
                    help='Refuse save if loss_after > loss_before * this (default: 1.05)')
    ap.add_argument('--polish', action='store_true',
                    help='Run bundle_adjust after all cams optimized')
    ap.add_argument('--limit', type=int, help='Limit to N cams (for testing)')
    args = ap.parse_args()

    # Load data
    with open(CAMERAS_JSON) as f:
        cameras = json.load(f)
    with open(TIERS_JSON) as f:
        tiers = json.load(f)
    cam_tiers = {n: (d.get('tier') if isinstance(d, dict) else d)
                 for n, d in tiers.get('cameras', {}).items()}

    # Build cam list
    if args.cams:
        cam_list = [c.strip() for c in args.cams.split(',')]
    elif args.tier:
        wanted = set(t.strip() for t in args.tier.split(','))
        cam_list = [c for c, t in cam_tiers.items() if t in wanted]
    else:
        print("ERROR: must specify --cams or --tier")
        sys.exit(1)

    # Filter to cams that exist + have pixels
    valid = []
    for c in cam_list:
        if c not in cameras:
            print(f"  ⚠ skip {c}: not in cameras.json")
            continue
        if not cameras[c].get('xyz'):
            print(f"  ⚠ skip {c}: no xyz")
            continue
        valid.append(c)

    if args.limit:
        valid = valid[:args.limit]

    print(f"\n{len(valid)} cams to process")
    if not args.apply:
        print("(dry-run — re-run with --apply)")
        for c in valid[:10]:
            print(f"  {cam_tiers.get(c, '?'):<12} {c}")
        if len(valid) > 10:
            print(f"  ... and {len(valid) - 10} more")
        return

    # Check server is up
    print("\nChecking server...")
    health = fetch_url(f'{SERVER_BASE}/api/cameras')
    if 'error' in health:
        print(f"ERROR: server not reachable at {SERVER_BASE}")
        print(f"       {health['error']}")
        print("       Start it with: python3 tools/server.py &")
        sys.exit(1)
    print(f"  ✓ server is up")

    # Process each cam
    print(f"\n{'cam':<35} {'tier':<10} {'before':>10} {'after':>10} {'Δ':>10} status")
    print("─" * 90)

    n_ok = n_skipped = n_failed = n_lms_updated = 0
    for cam_name in valid:
        cam = cameras[cam_name]
        xyz = cam['xyz']
        ypr = cam['ypr']
        fov = cam.get('fov', [60, None])
        hfov = fov[0] if fov and fov[0] is not None else 60
        tier = cam_tiers.get(cam_name, '?')

        # Optimize
        res = optimize_cam(cam_name, xyz, ypr, hfov)
        if 'error' in res:
            print(f"  {cam_name[:33]:<33} {tier:<10} {'?':>10} {'?':>10} {'?':>10} ERROR: {res['error']}")
            n_failed += 1
            continue

        # ── BATCH-OPTIMIZE-KEYS-FIX ──
        # Server returns 'loss' (after), not 'loss_after'
        loss_before = res.get('loss_before')
        loss_after = res.get('loss')
        if loss_before is None or loss_after is None:
            print(f"  {cam_name[:33]:<33} {tier:<10} {'?':>10} {'?':>10} {'?':>10} no loss data — skipped (under-constrained?)")
            n_skipped += 1
            continue

        # Safety checks before save  # ── BATCH-SAFETY-V1 ──
        delta = loss_before - loss_after
        if loss_after > args.save_threshold:
            print(f"  {cam_name[:33]:<33} {tier:<10} {loss_before:>10.3f} {loss_after:>10.3f} {delta:>+10.3f}  REFUSED (loss > {args.save_threshold}')")
            n_skipped += 1
            continue
        if loss_after > loss_before * args.regression_tolerance:
            print(f"  {cam_name[:33]:<33} {tier:<10} {loss_before:>10.3f} {loss_after:>10.3f} {delta:>+10.3f}  REFUSED (regression)")
            n_skipped += 1
            continue

        # Save params
        new_xyz = res['xyz']
        new_ypr = res['ypr']
        new_hfov = res['hfov']
        save_res = save_cam(cam_name, new_xyz, new_ypr, new_hfov)
        if 'error' in save_res:
            print(f"  {cam_name[:33]:<33} {tier:<10} {loss_before:>10.3f} {loss_after:>10.3f} {'?':>10} save ERROR: {save_res['error']}")
            n_failed += 1
            continue

        status = f"saved"

        # Optionally update LMs
        if args.update_lms and loss_after < args.update_threshold:
            upd = update_landmarks(cam_name, new_xyz, new_ypr, new_hfov)
            if 'error' not in upd:
                n_up = upd.get('updated', 0)
                status += f" · {n_up} LMs"
                n_lms_updated += n_up
            else:
                status += f" · LM-update failed"

        print(f"  {cam_name[:33]:<33} {tier:<10} {loss_before:>10.3f} {loss_after:>10.3f} {delta:>+10.3f}  {status}")
        n_ok += 1

    # Summary
    print("─" * 90)
    print(f"\nProcessed: {n_ok} optimized, {n_skipped} skipped, {n_failed} failed")
    if args.update_lms:
        print(f"           {n_lms_updated} landmark positions updated")

    # Optional: chain into bundle_adjust
    if args.polish:
        print(f"\nRunning bundle_adjust...")
        bundle_path = os.path.join(THIS_DIR, 'bundle_adjust.py')
        try:
            subprocess.run([sys.executable, bundle_path], check=True)
            print(f"  ✓ bundle_adjust complete")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ bundle_adjust failed: {e}")


if __name__ == '__main__':
    main()
