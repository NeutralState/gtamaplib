#!/usr/bin/env python3
"""
calibrate_batch.py — Interactive batch calibration following the topological
order defined in docs/index.html.

For each cam in the canonical order:
  1. Run refine_cam_full.py in dry-run, show summary
  2. Prompt user: [A]pply / [S]kip / [Q]uit / [D]etails
  3. If apply: write the new ypr/xyz/fov, then re-triangulate the LMs that
     this cam triangulates (where Tennis SE / etc. is in their sources).
  4. Every 5 cams, re-run compute_confidence_tiers.py to propagate trust.

At the end:
  - Summary of applied/skipped/quit
  - Tier diff (before/after)
  - List of LMs re-triangulated

Usage:
    python3 tools/calibrate_batch.py
    python3 tools/calibrate_batch.py --start-from "Vice Beach (B)"
    python3 tools/calibrate_batch.py --auto   # accept all without prompting (DANGEROUS)
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent.absolute()
REPO_DIR = THIS_DIR.parent
DATA_DIR = REPO_DIR / 'gtamapdata'
GEN_DIR = THIS_DIR / 'generated'

CAMERAS_JSON = DATA_DIR / 'cameras.json'
PIXELS_JSON = DATA_DIR / 'pixels.json'
LANDMARKS_JSON = DATA_DIR / 'landmarks.json'
TIERS_JSON = GEN_DIR / 'confidence_tiers.json'
DEPS_HTML = REPO_DIR / 'docs' / 'index.html'

# Tools we'll invoke
REFINE_FULL = THIS_DIR / 'refine_cam_full.py'
REFINE_YPR = THIS_DIR / 'refine_cam_ypr.py'
TRIANGULATE_LM = THIS_DIR / 'triangulate_lm.py'
COMPUTE_TIERS = THIS_DIR / 'compute_confidence_tiers.py'

# How often to re-run tiers during the batch
RETIER_INTERVAL = 5

# Mapping from docs/index.html keys to actual cameras.json keys
KEY_TO_CAM_NAME = {
    'lka': 'Leonida Keys 01 (Airplane) (X)',
    'lkp': 'Leonida Keys Postcard (X)',
    'kl': 'Key Lento',
    'gw': 'Grassrivers 02 (Watson Bay)',
    'prison': 'Prison',
    'vb_a': 'Vice Beach (A)',
    'vb_b': 'Vice Beach (B)',
    'rooftop': 'Rooftop Party',
    'vi': 'Venetian Islands',
    'beach': 'Beach',
    'skyline': 'Skyline',
    'basketball': 'Vice City 03 (Basketball)',
    'vcp': 'Vice City Postcard',
    'motorboats': None,  # ambiguous; we expand to A + B below
    'ferris': 'Vice City 08 (Ferris Wheel)',
    'amb02': 'Ambrosia 02 (Panorama)',
    'amb04': 'Ambrosia 04 (Fires)',
    'pgp': 'Port Gellhorn Postcard (X)',
    'pg04': 'Port Gellhorn 04 (Delights) (X)',
    'peacock_a': 'Highway (Peacock Bay) (A)',
    'peacock_b': 'Highway (Peacock Bay) (B)',
    'keys': 'Keys',
    'convertible': 'Convertible',
    'raul': 'Raul Bautista 03 (Motorboat)',
    'chase2a': 'Chase (2) (A)',
    'chase2b': 'Chase (2) (B)',
    'mkp04': 'Mount Kalaga National Park 04 (Mountain Pass) (X)',
    'amb01': 'Ambrosia 01 (Bikers)',
    'amb_post_x': 'Ambrosia Postcard (X)',
    'jd05': 'Jason Duval 05 (Machine Gun)',
    'lka_boats': 'Leonida Keys 05 (Boats)',
}


def parse_order_from_html():
    """Extract the ordered list of cam keys from docs/index.html."""
    html = DEPS_HTML.read_text()
    pattern = re.compile(
        r"'([^']+)':\s*\{[^}]*?label:\s*'([^']+)'[^}]*?author:\s*'([^']+)'",
        re.DOTALL
    )
    keys_in_order = []
    for m in pattern.finditer(html):
        key, label, author = m.groups()
        keys_in_order.append((key, label, author))
    return keys_in_order


def resolve_cam_names(keys_in_order):
    """Resolve docs/index.html keys to cameras.json keys.

    Some keys (e.g. 'motorboats') map to multiple cams. We expand them.
    """
    cameras = json.loads(CAMERAS_JSON.read_text())
    resolved = []
    for key, label, author in keys_in_order:
        if key == 'motorboats':
            # Expand to A and B
            for sub in ['Motorboats (A)', 'Motorboats (B)']:
                if sub in cameras:
                    resolved.append((sub, label + f' [{sub.split()[-1]}]', author))
        else:
            name = KEY_TO_CAM_NAME.get(key)
            if name is None:
                print(f"  WARN: No mapping for key '{key}', skipping")
                continue
            if name not in cameras:
                print(f"  WARN: Cam '{name}' not in cameras.json, skipping")
                continue
            resolved.append((name, label, author))
    return resolved


# V2: dispatch refine tool via the audit helper. cameras.json is reloaded
# from disk on each call to track --apply writes; the helper's API supports
# passing the dict directly to avoid the audit JSON lookup.
sys.path.insert(0, str(THIS_DIR))
from leak_cam_audit import (
    get_locked_dof,
    is_anchor,
    is_excluded,
    DOF_XYZ, DOF_FOV,
)


def _load_cameras():
    return json.loads(CAMERAS_JSON.read_text())


def _refine_tool_for(cam_name):
    """Pick the right refine tool for this cam based on its constraint_class.
    Returns (tool_path, reason_str) or (None, skip_reason).

    Routing rules (mirrors the per-tool gates in refine_cam_ypr.py and
    refine_cam_full.py):
      - excluded (X)            → skip
      - all DOF locked (A/legacy) → skip (already anchor)
      - xyz+fov locked, ypr free (B/C) → refine_cam_ypr
      - xyz locked, ypr+fov free (Cm)  → refine_cam_full --no-refine-xyz
      - all DOF free (D / no audit)    → refine_cam_full
    """
    cameras = _load_cameras()
    if is_excluded(cam_name, cameras=cameras):
        return (None, 'class X_invalid_ground_truth — excluded')
    if is_anchor(cam_name, cameras=cameras):
        return (None, 'all DOF locked (anchor) — nothing to refine')
    locked = get_locked_dof(cam_name, cameras=cameras)
    if DOF_XYZ in locked and DOF_FOV in locked:
        return (REFINE_YPR, 'xyz+fov locked, ypr free → ypr-only refinement')
    if DOF_XYZ in locked:
        return (REFINE_FULL, 'xyz locked, ypr+fov free → joint ypr+fov refinement')
    return (REFINE_FULL, 'all DOF free → full xyz/ypr/fov solve')


def run_refine_dry_run(cam_name):
    """Run the appropriate refine tool in dry-run mode based on constraint_class.
    Returns (stdout, success_bool)."""
    tool, reason = _refine_tool_for(cam_name)
    if tool is None:
        return f'SKIPPED: {reason}\n', False
    cmd = ['python3', str(tool), cam_name]
    # Class Cm needs --no-refine-xyz to honor the HUD-locked xyz. refine_cam_full
    # already enforces this internally (logging an "ignored" warning if the
    # user passed --refine-xyz). We rely on that here rather than duplicating
    # the per-class flag logic.
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_DIR)
    return result.stdout, result.returncode == 0


def run_refine_apply(cam_name):
    """Run the appropriate refine tool in --apply mode."""
    tool, reason = _refine_tool_for(cam_name)
    if tool is None:
        return f'SKIPPED: {reason}\n', False
    cmd = ['python3', str(tool), cam_name, '--apply']
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_DIR)
    return result.stdout, result.returncode == 0


def extract_summary(stdout):
    """Extract a short summary from refine_cam_*.py output.
    Returns dict with: visible_lms, selected, init_rms, final_rms, final_max,
    delta_xyz, top_outliers (list of (name, weight, residual) tuples).
    """
    summary = {}
    
    # Visible LMs count
    m = re.search(r'Visible LMs \((\d+)\):', stdout)
    if m:
        summary['visible_lms'] = int(m.group(1))
    
    # Selected
    m = re.search(r'Selected LMs \((\d+)\):\s*(.+)', stdout)
    if m:
        summary['selected_count'] = int(m.group(1))
        summary['selected_reason'] = m.group(2).strip()
    
    # Initial weighted RMS
    m = re.search(r'Weighted RMS:\s*([\d.]+)\s*arcmin', stdout)
    if m:
        summary['init_rms'] = float(m.group(1))
    
    # Final weighted RMS
    m = re.search(r'Final Weighted RMS:\s*([\d.]+)\s*arcmin\s*\(was\s*([\d.]+)', stdout)
    if m:
        summary['final_rms'] = float(m.group(1))
    
    # Final max
    m = re.search(r'Final Max:\s*([\d.]+)\s*arcmin\s*\(was\s*([\d.]+)', stdout)
    if m:
        summary['final_max'] = float(m.group(1))
    
    # Delta xyz norm (only for refine_cam_full)
    m = re.search(r'xyz:\s*\[[^\]]+\]\s*\(Δ\s*([\d.]+)\s*m\)', stdout)
    if m:
        summary['delta_xyz'] = float(m.group(1))
    
    # Top 5 outliers (per-LM residuals)
    outliers = []
    for line in stdout.split('\n'):
        m = re.match(r'\s*weight=\s*([\d.]+)\s*\[(\w+)\s*\]\s*([\d.]+)[\'"]\s*(.+)', line)
        if m:
            weight, tier, residual, lm_name = m.groups()
            outliers.append({
                'weight': float(weight),
                'tier': tier.strip(),
                'residual': float(residual),
                'name': lm_name.strip()
            })
        if len(outliers) >= 5:
            break
    summary['top_outliers'] = outliers
    
    # Status line
    if '✓ Final RMS' in stdout:
        summary['status'] = 'solid'
    elif '~ Final RMS' in stdout:
        summary['status'] = 'acceptable'
    elif '⚠' in stdout:
        summary['status'] = 'elevated'
    elif '✗' in stdout:
        summary['status'] = 'suspect'
    else:
        summary['status'] = 'unknown'
    
    # ERROR cases
    if 'ERROR:' in stdout:
        summary['error'] = True
    
    return summary


def print_cam_summary(cam_name, summary, index, total, author):
    print()
    print("─" * 78)
    print(f"  [{index}/{total}] {cam_name}  ({author})")
    print("─" * 78)
    if summary.get('error'):
        print("  ERROR — see full output with [D]etails")
        return
    print(f"  Visible LMs: {summary.get('visible_lms', '?')}")
    print(f"  Selection:   {summary.get('selected_reason', '?')}")
    if 'delta_xyz' in summary:
        print(f"  Delta xyz:   {summary['delta_xyz']:.2f} m")
    print(f"  RMS:         {summary.get('init_rms', '?')}' → {summary.get('final_rms', '?')}'")
    print(f"  Max:         {summary.get('final_max', '?')}'")
    status = summary.get('status', 'unknown')
    status_icon = {'solid': '✓', 'acceptable': '~', 'elevated': '⚠', 'suspect': '✗'}.get(status, '?')
    print(f"  Status:      {status_icon} {status}")
    if summary.get('top_outliers'):
        print(f"  Top 5 outliers:")
        for o in summary['top_outliers']:
            print(f"    weight={o['weight']:4.1f} [{o['tier']:10}] {o['residual']:6.2f}'  {o['name']}")


def find_lms_marked_by(cam_name):
    """Return list of LM names that this cam marks in pixels.json."""
    pixels = json.loads(PIXELS_JSON.read_text())
    cam_pixels = pixels.get(cam_name, {})
    return list(cam_pixels.keys())


def retriangulate_lms_for_cam(cam_name, verbose=True):
    """For each LM marked by cam_name, run triangulate_lm.py --apply.
    Skip LMs with fewer than 2 sources (not triangulable).
    Returns (n_retriangulated, n_skipped)."""
    lms = json.loads(LANDMARKS_JSON.read_text())
    lm_names = find_lms_marked_by(cam_name)
    n_done = 0
    n_skip = 0
    
    for lm_name in lm_names:
        lm = lms.get(lm_name)
        if not isinstance(lm, dict):
            n_skip += 1
            continue
        sources = lm.get('source_cameras', [])
        if not isinstance(sources, list) or len(sources) < 2:
            n_skip += 1
            continue
        
        cmd = ['python3', str(TRIANGULATE_LM), lm_name, '--apply']
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_DIR)
        if result.returncode == 0:
            n_done += 1
        else:
            n_skip += 1
    
    if verbose:
        print(f"  → Re-triangulated {n_done} LMs (skipped {n_skip} non-triangulable)")
    return n_done, n_skip


def snapshot_tiers():
    """Return current tier counts as dict."""
    if not TIERS_JSON.exists():
        return {}
    data = json.loads(TIERS_JSON.read_text())
    snap = {'cameras': {}, 'landmarks': {}}
    for kind in ['cameras', 'landmarks']:
        items = data.get(kind, {})
        for name, info in items.items():
            tier = info.get('tier') if isinstance(info, dict) else info
            snap[kind].setdefault(tier, 0)
            snap[kind][tier] += 1
    return snap


def rerun_tiers():
    """Re-run compute_confidence_tiers.py silently."""
    cmd = ['python3', str(COMPUTE_TIERS)]
    subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_DIR)


def print_tier_diff(before, after):
    print()
    print("─" * 78)
    print("  TIER DIFF (before → after)")
    print("─" * 78)
    for kind in ['cameras', 'landmarks']:
        print(f"  {kind.upper()}:")
        all_tiers = set(before.get(kind, {}).keys()) | set(after.get(kind, {}).keys())
        for tier in ['anchor', 'high', 'medium', 'low', 'unverified']:
            if tier in all_tiers:
                b = before.get(kind, {}).get(tier, 0)
                a = after.get(kind, {}).get(tier, 0)
                delta = a - b
                sign = '+' if delta > 0 else ''
                print(f"    {tier:12}  {b:4d} → {a:4d}  ({sign}{delta})")


def main():
    parser = argparse.ArgumentParser(description="Interactive batch calibration in topological order.")
    parser.add_argument('--start-from', default=None,
                        help="Skip cams until this name (inclusive).")
    parser.add_argument('--auto', action='store_true',
                        help="Auto-apply all cams without prompting (DANGEROUS).")
    parser.add_argument('--no-retriangulate', action='store_true',
                        help="Don't re-triangulate LMs after each cam apply.")
    parser.add_argument('--no-retier', action='store_true',
                        help="Don't re-run compute_confidence_tiers during the batch.")
    args = parser.parse_args()

    # Parse order
    keys_in_order = parse_order_from_html()
    cams_in_order = resolve_cam_names(keys_in_order)
    print(f"Loaded {len(cams_in_order)} cams from docs/index.html order")
    print()

    # Skip until --start-from
    if args.start_from:
        for i, (name, _, _) in enumerate(cams_in_order):
            if name == args.start_from:
                cams_in_order = cams_in_order[i:]
                print(f"Starting from #{i+1}: {args.start_from}")
                print()
                break
        else:
            print(f"ERROR: --start-from '{args.start_from}' not found in order")
            return 1

    # Snapshot tiers before
    print("Initial tier state:")
    tiers_before = snapshot_tiers()
    for kind in ['cameras', 'landmarks']:
        counts = tiers_before.get(kind, {})
        print(f"  {kind}: " + ", ".join(f"{t}={counts.get(t, 0)}" for t in ['anchor', 'high', 'medium', 'low', 'unverified']))
    print()

    applied = []
    skipped = []
    failed = []
    total_lms_retriangulated = 0
    quit_batch = False

    for i, (cam_name, label, author) in enumerate(cams_in_order, 1):
        if quit_batch:
            break

        # Run dry-run
        stdout, ok = run_refine_dry_run(cam_name)
        if not ok:
            failed.append(cam_name)
            print(f"  [{i}/{len(cams_in_order)}] {cam_name} — FAILED to run, skipping")
            continue

        summary = extract_summary(stdout)
        print_cam_summary(cam_name, summary, i, len(cams_in_order), author)

        if summary.get('error'):
            failed.append(cam_name)
            print(f"  Skipping due to error.")
            continue

        # Prompt
        if args.auto:
            choice = 'a'
        else:
            choice = None
            while choice not in ['a', 's', 'q', 'd']:
                inp = input("  [A]pply / [S]kip / [Q]uit / [D]etails: ").strip().lower()
                choice = inp if inp else 's'
                if choice == 'd':
                    print()
                    print(stdout)
                    print()
                    choice = None

        if choice == 'q':
            quit_batch = True
            print("  Quitting batch.")
            break

        if choice == 's':
            skipped.append(cam_name)
            continue

        # Apply
        apply_stdout, apply_ok = run_refine_apply(cam_name)
        if not apply_ok:
            failed.append(cam_name)
            print(f"  APPLY FAILED — skipping.")
            print(apply_stdout[-500:])
            continue
        applied.append(cam_name)
        print(f"  ✓ APPLIED")

        # Re-triangulate LMs marked by this cam
        if not args.no_retriangulate:
            n_done, _ = retriangulate_lms_for_cam(cam_name, verbose=True)
            total_lms_retriangulated += n_done

        # Re-tier every RETIER_INTERVAL cams
        if not args.no_retier and len(applied) % RETIER_INTERVAL == 0:
            print(f"  → Re-running compute_confidence_tiers...")
            rerun_tiers()

    # Final re-tier
    if not args.no_retier and applied:
        rerun_tiers()

    tiers_after = snapshot_tiers()

    # Summary
    print()
    print("═" * 78)
    print("  BATCH COMPLETE")
    print("═" * 78)
    print(f"  Applied:  {len(applied)} cams")
    if applied:
        for n in applied:
            print(f"    ✓ {n}")
    print(f"  Skipped:  {len(skipped)} cams")
    if skipped:
        for n in skipped:
            print(f"    - {n}")
    print(f"  Failed:   {len(failed)} cams")
    if failed:
        for n in failed:
            print(f"    ✗ {n}")
    print(f"  LMs re-triangulated: {total_lms_retriangulated}")

    print_tier_diff(tiers_before, tiers_after)

    return 0


if __name__ == '__main__':
    sys.exit(main())
