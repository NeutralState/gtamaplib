#!/usr/bin/env python3
"""
audit_leak_influence_tree.py — Compute the transitive influence of each LEAK
cam on the dataset by walking the dependency DAG.

Definitions:
  - LEAK cam: source field starts with YYYY-MM-DD (game debug overlay)
  - "Cam C depends on cam B" if there exists an LM L such that:
      * C marks L with tier 'anchor' or 'high' (B-strict definition)
      * B is in L.source_cameras
    Intuition: L's position was triangulated using B's view; C's calibration
    uses L as anchor; therefore drift in B propagates → L → C.

For each LEAK cam, BFS the dependency graph:
  gen 0: the LEAK cam itself
  gen 1: LMs that have this cam in their source_cameras
  gen 2: cams that marked any gen-1 LM with tier anchor+high
  gen 3: LMs sourced by any gen-2 cam
  ... continues until no new nodes added (transitive closure)

Cycles handled: BFS marks visited nodes; revisits are skipped.

Outputs:
  - JSON: tools/generated/leak_influence_tree.json
  - Console: ranked summary of LEAK cams by total reach

Run from gtamaplib-main/:
  python3 tools/audit/audit_leak_influence_tree.py
  python3 tools/audit/audit_leak_influence_tree.py --cam "Metro (SE) (A) (4K)"
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict, deque

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, GTAMAP_DIR)

DATA_DIR = os.path.join(GTAMAP_DIR, 'gtamapdata')
GEN_DIR = os.path.join(GTAMAP_DIR, 'tools', 'generated')

CAMERAS_JSON   = os.path.join(DATA_DIR, 'cameras.json')
PIXELS_JSON    = os.path.join(DATA_DIR, 'pixels.json')
LANDMARKS_JSON = os.path.join(DATA_DIR, 'landmarks.json')
TIERS_JSON     = os.path.join(GEN_DIR, 'confidence_tiers.json')
OUT_JSON       = os.path.join(GEN_DIR, 'leak_influence_tree.json')


def is_leak(cam_data):
    s = cam_data.get('source', '') if isinstance(cam_data, dict) else ''
    return bool(re.match(r'\d{4}-\d{2}-\d{2}', s))


def load_data():
    with open(CAMERAS_JSON) as f:
        cameras = json.load(f)
    with open(LANDMARKS_JSON) as f:
        landmarks = json.load(f)
    with open(PIXELS_JSON) as f:
        pixels = json.load(f)
    with open(TIERS_JSON) as f:
        tiers_data = json.load(f)
    lm_tiers = {n: (d.get('tier') if isinstance(d, dict) else d)
                for n, d in tiers_data.get('landmarks', {}).items()}
    return cameras, landmarks, pixels, lm_tiers


def build_indices(cameras, landmarks, pixels, lm_tiers):
    """
    Build forward and reverse indices for fast BFS.

    Returns:
      lm_to_sources : dict[lm] -> list[cam] (who sourced this LM)
      cam_to_sourced : dict[cam] -> set[lm] (LMs this cam is source for)
      lm_to_anchor_markers : dict[lm] -> set[cam] (who marked this LM at anchor/high)
      cam_to_anchor_marks : dict[cam] -> set[lm] (LMs this cam marked anchor/high)
    """
    lm_to_sources = {}
    cam_to_sourced = defaultdict(set)
    for lm_name, lm_data in landmarks.items():
        srcs = lm_data.get('source_cameras', []) if isinstance(lm_data, dict) else []
        lm_to_sources[lm_name] = list(srcs)
        for s in srcs:
            cam_to_sourced[s].add(lm_name)

    lm_to_anchor_markers = defaultdict(set)
    cam_to_anchor_marks = defaultdict(set)
    for cam_name, marks in pixels.items():
        for lm_name in marks:
            tier = lm_tiers.get(lm_name, 'unverified')
            if tier in ('anchor', 'high'):
                lm_to_anchor_markers[lm_name].add(cam_name)
                cam_to_anchor_marks[cam_name].add(lm_name)

    return lm_to_sources, dict(cam_to_sourced), dict(lm_to_anchor_markers), dict(cam_to_anchor_marks)


def bfs_influence(leak_cam, cam_to_sourced, lm_to_anchor_markers):
    """
    BFS from a LEAK cam. Returns list of generations, each is dict:
      {'kind': 'lms' or 'cams', 'items': sorted_list}
    Also returns dict: cams_reached (set), lms_reached (set).
    """
    visited_cams = {leak_cam}
    visited_lms = set()
    generations = []  # list of (kind, set)

    # gen 1: LMs sourced by this LEAK cam
    current_lms = set(cam_to_sourced.get(leak_cam, set()))
    if not current_lms:
        return generations, visited_cams, visited_lms

    visited_lms |= current_lms
    generations.append(('lms', current_lms))

    while True:
        # next gen: cams that marked any current_lms as anchor+high
        next_cams = set()
        for lm in current_lms:
            for cam in lm_to_anchor_markers.get(lm, set()):
                if cam not in visited_cams:
                    next_cams.add(cam)
        if not next_cams:
            break
        visited_cams |= next_cams
        generations.append(('cams', next_cams))

        # next gen: LMs sourced by any of next_cams
        next_lms = set()
        for cam in next_cams:
            for lm in cam_to_sourced.get(cam, set()):
                if lm not in visited_lms:
                    next_lms.add(lm)
        if not next_lms:
            break
        visited_lms |= next_lms
        generations.append(('lms', next_lms))
        current_lms = next_lms

    return generations, visited_cams, visited_lms


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cam', type=str, default=None,
                        help='Show detailed tree for one LEAK cam')
    parser.add_argument('--top', type=int, default=30,
                        help='Number of top LEAK cams to show in summary')
    args = parser.parse_args()

    cameras, landmarks, pixels, lm_tiers = load_data()
    leak_cams = sorted(n for n, d in cameras.items() if is_leak(d))

    print(f"Loaded {len(cameras)} cams ({len(leak_cams)} LEAK), "
          f"{len(landmarks)} LMs, "
          f"{sum(len(m) for m in pixels.values())} marker pixels")
    print()

    lm_to_sources, cam_to_sourced, lm_to_anchor_markers, cam_to_anchor_marks = \
        build_indices(cameras, landmarks, pixels, lm_tiers)

    # Compute BFS for every LEAK cam
    results = {}
    for cam in leak_cams:
        generations, cams_reached, lms_reached = bfs_influence(
            cam, cam_to_sourced, lm_to_anchor_markers
        )
        # Exclude the cam itself from the count of cams_reached
        # (BFS started with visited_cams = {leak_cam})
        downstream_cams = cams_reached - {cam}

        results[cam] = {
            'gen_count': len(generations),
            'max_depth': len(generations),
            'total_lms_reached': len(lms_reached),
            'total_cams_reached_downstream': len(downstream_cams),
            'generations': [
                {
                    'gen': i + 1,
                    'kind': kind,
                    'count': len(items),
                    'items': sorted(items),
                }
                for i, (kind, items) in enumerate(generations)
            ],
            'downstream_cams': sorted(downstream_cams),
            'downstream_lms': sorted(lms_reached),
        }

    # Save JSON
    os.makedirs(GEN_DIR, exist_ok=True)
    output = {
        'meta': {
            'leak_cam_count': len(leak_cams),
            'total_cam_count': len(cameras),
            'total_lm_count': len(landmarks),
            'definition': 'B-strict: cam C depends on cam B if C marked an LM L at tier anchor/high, and B is in L.source_cameras',
        },
        'leak_cams': results,
    }
    with open(OUT_JSON, 'w') as f:
        json.dump(output, f, indent=2)

    # Detailed view for one cam
    if args.cam:
        if args.cam not in results:
            print(f"ERROR: '{args.cam}' is not a LEAK cam.")
            print(f"LEAK cams (sorted): {leak_cams[:10]} ... ({len(leak_cams)} total)")
            return
        r = results[args.cam]
        print(f"═" * 72)
        print(f"  {args.cam}")
        print(f"═" * 72)
        print(f"  Max depth:                  {r['max_depth']}")
        print(f"  Total LMs reached:          {r['total_lms_reached']}")
        print(f"  Total cams reached (down):  {r['total_cams_reached_downstream']}")
        print()
        for g in r['generations']:
            print(f"── Gen {g['gen']} ({g['kind']}, {g['count']} items) ──")
            for item in g['items'][:30]:
                print(f"     {item}")
            if g['count'] > 30:
                print(f"     ... and {g['count'] - 30} more")
            print()
        return

    # Summary table
    ranked = sorted(
        results.items(),
        key=lambda kv: (-kv[1]['total_cams_reached_downstream'], -kv[1]['total_lms_reached']),
    )

    print(f"=== LEAK cams ranked by total downstream cams reached ===")
    print(f"  (with anchor+high tier requirement on markings)")
    print()
    print(f"  {'rank':>4}  {'cam':45s}  {'cams':>5s}  {'lms':>5s}  {'depth':>5s}")
    print(f"  {'-' * 4}  {'-' * 45}  {'-' * 5}  {'-' * 5}  {'-' * 5}")
    for i, (cam, r) in enumerate(ranked[:args.top], 1):
        print(f"  {i:>4}  {cam:45s}  {r['total_cams_reached_downstream']:>5d}  "
              f"{r['total_lms_reached']:>5d}  {r['max_depth']:>5d}")

    # Count LEAK cams with zero reach
    zero_reach = [c for c, r in results.items() if r['total_cams_reached_downstream'] == 0]
    print()
    print(f"LEAK cams with ZERO downstream cams reached: {len(zero_reach)}")

    print()
    print(f"Full JSON written to: {OUT_JSON}")
    print()
    print(f"Next: python3 tools/audit/audit_leak_influence_tree.py --cam 'CAM_NAME'")
    print(f"      to see the full generational tree for a specific LEAK cam.")


if __name__ == '__main__':
    main()
