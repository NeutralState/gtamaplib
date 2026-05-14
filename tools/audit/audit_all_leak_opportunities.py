#!/usr/bin/env python3
"""
audit_all_leak_opportunities.py — For each non-LEAK cam with zero all_leak LMs
currently marked, find all_leak LMs that are likely visible in its frame
(would project in-bounds with current cam params).

Output: opportunities ranked by # of all_leak LMs that are likely visible.

This is purely read-only. It does NOT modify any data. It tells you where
to focus your manual marking efforts in the UI to maximize ground-truth
anchoring of your calibrated cams.

Run from gtamaplib-main/:
    python3 tools/audit/audit_all_leak_opportunities.py
    python3 tools/audit/audit_all_leak_opportunities.py --top 10
    python3 tools/audit/audit_all_leak_opportunities.py --cam "Prison"
"""

import argparse
import json
import math
import os
import re
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml

DATA_DIR = os.path.join(GTAMAP_DIR, 'gtamapdata')
GEN_DIR  = os.path.join(GTAMAP_DIR, 'tools', 'generated')

CAMERAS_JSON   = os.path.join(DATA_DIR, 'cameras.json')
PIXELS_JSON    = os.path.join(DATA_DIR, 'pixels.json')
LANDMARKS_JSON = os.path.join(DATA_DIR, 'landmarks.json')
TIERS_JSON     = os.path.join(GEN_DIR, 'confidence_tiers.json')


def is_leak(cam_data):
    """LEAK cam = source starts with date pattern."""
    s = cam_data.get('source', '') if isinstance(cam_data, dict) else ''
    return bool(re.match(r'\d{4}-\d{2}-\d{2}', s))


def lm_ancestry(lm_data, leak_cams):
    """Returns 'all_leak' / 'partial_leak' / 'no_leak' / 'no_source'."""
    src = lm_data.get('source_cameras', []) if isinstance(lm_data, dict) else []
    if not src:
        return 'no_source'
    leak_count = sum(1 for c in src if c in leak_cams)
    if leak_count == len(src):
        return 'all_leak'
    elif leak_count > 0:
        return 'partial_leak'
    return 'no_leak'


def find_likely_visible_all_leak(cam, landmarks_dict, ancestry_map, marked_set):
    """For a given Camera object, find all_leak LMs that project in-frame.

    Returns list of (lm_name, (px, py), distance_m) sorted by distance.
    """
    candidates = []
    w, h = cam.w, cam.h
    for lm_name, lm_data in landmarks_dict.items():
        if lm_name in marked_set:
            continue
        if ancestry_map.get(lm_name) != 'all_leak':
            continue
        xyz = lm_data.get('xyz') if isinstance(lm_data, dict) else None
        if not xyz:
            continue
        try:
            proj = cam.get_pixel(xyz)
            if proj is None:
                continue
            px, py = float(proj[0]), float(proj[1])
            if not (0 <= px <= w and 0 <= py <= h):
                continue
            dx = xyz[0] - cam.xyz[0]
            dy = xyz[1] - cam.xyz[1]
            dz = xyz[2] - cam.xyz[2]
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            candidates.append((lm_name, (round(px), round(py)), dist))
        except Exception:
            continue
    candidates.sort(key=lambda x: x[2])
    return candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--top', type=int, default=20,
                        help='Show top N opportunities (default 20)')
    parser.add_argument('--cam', type=str, default=None,
                        help='Show detailed visible LMs for one specific cam')
    parser.add_argument('--min-visible', type=int, default=1,
                        help='Only list cams with at least N visible all_leak LMs (default 1)')
    args = parser.parse_args()

    # Load data
    with open(CAMERAS_JSON) as f:
        cameras = json.load(f)
    with open(LANDMARKS_JSON) as f:
        landmarks = json.load(f)
    with open(PIXELS_JSON) as f:
        pixels = json.load(f)

    # Identify LEAK cams
    leak_cams = {n for n, d in cameras.items() if is_leak(d)}

    # Build ancestry map for all LMs
    ancestry_map = {n: lm_ancestry(d, leak_cams) for n, d in landmarks.items()}

    # Non-LEAK cams with zero all_leak LMs marked
    targets = []
    for cam_name, cam_data in cameras.items():
        if is_leak(cam_data):
            continue
        marked = pixels.get(cam_name, {})
        if not marked:
            continue
        all_leak_marked = sum(1 for lm in marked if ancestry_map.get(lm) == 'all_leak')
        if all_leak_marked == 0:
            targets.append((cam_name, len(marked)))

    print(f"Found {len(targets)} non-LEAK cams with marked LMs but zero all_leak anchored.")
    print(f"Computing likely-visible all_leak LMs for each...")
    print()

    # For each target, compute likely-visible all_leak LMs
    results = []  # (cam_name, total_marked, visible_count, visible_list)
    for cam_name, total_marked in targets:
        if args.cam and cam_name != args.cam:
            continue
        cam_data = cameras[cam_name]
        # Need cam params to instantiate Camera
        if not cam_data.get('xyz') or not cam_data.get('ypr') or not cam_data.get('fov'):
            continue
        try:
            cam = ml.get_camera(cam_name)
        except Exception as e:
            continue
        marked_set = set(pixels.get(cam_name, {}).keys())
        visible = find_likely_visible_all_leak(cam, landmarks, ancestry_map, marked_set)
        results.append((cam_name, total_marked, len(visible), visible))

    # Sort by # of visible all_leak LMs (opportunity descending)
    results.sort(key=lambda x: -x[2])

    if args.cam:
        # Detailed report for one cam
        if not results:
            print(f"No data for cam '{args.cam}' (not a target, or params missing).")
            return
        cam_name, total_marked, visible_count, visible_list = results[0]
        print(f"═" * 72)
        print(f"  {cam_name}")
        print(f"═" * 72)
        print(f"  Currently marked LMs: {total_marked} (0 all_leak)")
        print(f"  Likely-visible all_leak LMs not yet marked: {visible_count}")
        print()
        if visible_list:
            print(f"  {'LM name':50s}  px            dist")
            print(f"  {'-' * 50}  ------------  ------")
            for lm_name, (px, py), dist in visible_list:
                print(f"  {lm_name:50s}  ({px:4d}, {py:4d})  {dist:6.0f}m")
        return

    # Summary table
    filtered = [r for r in results if r[2] >= args.min_visible]
    print(f"Cams with ≥{args.min_visible} likely-visible all_leak LM (top {args.top}):")
    print()
    print(f"  {'cam':40s} marked  visible  best 3 LMs")
    print(f"  {'-' * 40}  ------  -------  -------------------------")
    for cam_name, total_marked, visible_count, visible_list in filtered[:args.top]:
        top3 = ", ".join(v[0][:25] for v in visible_list[:3])
        print(f"  {cam_name:40s}  {total_marked:6d}  {visible_count:7d}  {top3}")

    print()
    print(f"Total cams with opportunities: {len(filtered)}")
    print(f"Sum of likely-visible all_leak LMs across all cams: {sum(r[2] for r in filtered)}")
    print()
    print("Next step:")
    print("  python3 tools/audit/audit_all_leak_opportunities.py --cam 'CAM_NAME'")
    print("  to see the full list of suggestions for a specific cam.")


if __name__ == '__main__':
    main()
