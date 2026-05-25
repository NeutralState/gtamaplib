#!/usr/bin/env python3
"""
calibration_plan.py — Analyze cams not currently in the dependency tree
(docs/index.html) and suggest where they should be inserted.

For each non-leak, non-tree cam:
  1. Find LMs it marks (in pixels.json)
  2. For each LM with xyz, list its source cameras
  3. Determine the "earliest position" in the tree at which all LM sources
     would be calibrated
  4. Compute available trusted LMs at that position
  5. Suggest insertion: "Cam X → insert after #N (Y anchor + Z high LMs)"

Output:
  - For each cam: insertion position + available LMs by tier
  - Warning if < 4 trusted LMs (insufficient for calibration)
  - Warning if cam depends on cams not in tree (circular or detached)

Usage:
    python3 tools/calibration_plan.py                       # analyze all
    python3 tools/calibration_plan.py --cam "Amphitheater"  # single cam
    python3 tools/calibration_plan.py --zone vice_city      # filter by zone
    python3 tools/calibration_plan.py --include-leak        # also include leak cams
"""

import argparse
import json
import re
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

# Tree mapping (key → real cam name)
KEY_TO_NAME = {
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
    'motorboats': 'Motorboats (A)',  # represents A and B
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


def is_leak_cam(cam_data):
    """Cam is leak if its source matches YYYY-MM-DD."""
    if not isinstance(cam_data, dict):
        return False
    src = cam_data.get('source', '') or ''
    return bool(re.match(r'\d{4}-\d{2}-\d{2}', src))


def parse_tree_order():
    """Extract ordered list of cam names from docs/index.html."""
    html = DEPS_HTML.read_text()
    pattern = re.compile(
        r"'([^']+)':\s*\{[^}]*?label:\s*'([^']+)'[^}]*?author:\s*'([^']+)'",
        re.DOTALL
    )
    cam_names = []
    for m in pattern.finditer(html):
        key = m.group(1)
        if key == 'motorboats':
            cam_names.append('Motorboats (A)')
            cam_names.append('Motorboats (B)')
        else:
            name = KEY_TO_NAME.get(key)
            if name:
                cam_names.append(name)
    return cam_names


def load_data():
    cameras = json.loads(CAMERAS_JSON.read_text())
    pixels = json.loads(PIXELS_JSON.read_text())
    landmarks = json.loads(LANDMARKS_JSON.read_text())
    tiers_data = {}
    if TIERS_JSON.exists():
        tiers_data = json.loads(TIERS_JSON.read_text())
    lm_tiers = {}
    for n, d in tiers_data.get('landmarks', {}).items():
        lm_tiers[n] = d.get('tier') if isinstance(d, dict) else d
    return cameras, pixels, landmarks, lm_tiers


def find_lms_marked_by(cam_name, pixels, landmarks):
    """Return list of LM names this cam marks AND that have xyz set."""
    cam_pixels = pixels.get(cam_name, {})
    lms_with_xyz = []
    for lm_name in cam_pixels:
        lm = landmarks.get(lm_name)
        if not isinstance(lm, dict):
            continue
        if not lm.get('xyz'):
            continue
        lms_with_xyz.append(lm_name)
    return lms_with_xyz


def analyze_cam(cam_name, tree_order, tree_set, leak_set, cameras, pixels, landmarks, lm_tiers):
    """Analyze where this cam should be inserted in the tree.

    Leak cams are treated as implicitly available at "position 0" (foundation).
    A source is "satisfied" if it's a leak cam OR in the tree at position < cam's insertion.

    Returns dict with:
      - lms_marked: total LMs marked (with xyz)
      - lms_by_tier: {tier: count}
      - source_dependencies: list of (lm_name, latest_tree_position)
      - earliest_insertion: int (1-indexed, position after which cam is calibratable)
      - earliest_insertion_label: string (after which cam in tree)
      - available_trusted_at_insertion: dict {tier: count}
      - issues: list of warnings
    """
    result = {
        'cam_name': cam_name,
        'lms_marked': 0,
        'lms_by_tier': {},
        'source_dependencies': [],
        'earliest_insertion': 0,
        'earliest_insertion_label': '(start of tree, leak cams only)',
        'available_trusted_at_insertion': {},
        'issues': []
    }

    lm_names = find_lms_marked_by(cam_name, pixels, landmarks)
    result['lms_marked'] = len(lm_names)

    if not lm_names:
        result['issues'].append("No LMs with xyz marked by this cam")
        return result

    # Per-LM analysis
    # max_source_position = max position in tree_order of any non-leak source
    # If only leak sources, max stays at -1 (meaning: insertable at any position, including #0)
    max_source_position = -1

    for lm_name in lm_names:
        lm = landmarks[lm_name]
        sources = lm.get('source_cameras', []) or []
        tier = lm_tiers.get(lm_name, 'unverified')
        result['lms_by_tier'][tier] = result['lms_by_tier'].get(tier, 0) + 1

        latest_pos = -1  # -1 means LM is satisfied by leak only or has no tree source
        latest_source = None
        leak_sources_for_lm = []
        non_tree_non_leak_sources = []

        for s in sources:
            if s == cam_name:
                continue  # skip self-circular
            if s in leak_set:
                leak_sources_for_lm.append(s)
                # Leak doesn't push max_source_position; it's always available
            elif s in tree_set:
                pos = tree_order.index(s)
                if pos > latest_pos:
                    latest_pos = pos
                    latest_source = s
            else:
                # Non-leak, not in tree — out-of-band source
                non_tree_non_leak_sources.append(s)

        # An LM is "satisfied" if it has at least one leak source OR at least one tree source
        is_satisfied = bool(leak_sources_for_lm) or (latest_pos >= 0)

        result['source_dependencies'].append({
            'lm': lm_name,
            'tier': tier,
            'latest_tree_source': latest_source,
            'latest_tree_position': latest_pos,
            'leak_sources': leak_sources_for_lm,
            'non_tree_non_leak_sources': non_tree_non_leak_sources,
            'satisfied': is_satisfied,
        })

        if latest_pos > max_source_position:
            max_source_position = latest_pos

    # Insertion position is after the max tree-position source (leak sources don't push this)
    insertion = max_source_position + 1
    result['earliest_insertion'] = insertion + 1  # 1-indexed for display
    if max_source_position < 0:
        result['earliest_insertion_label'] = "start of tree (leak cams only as sources)"
    elif 0 <= max_source_position < len(tree_order):
        result['earliest_insertion_label'] = f"after #{insertion} ({tree_order[max_source_position]})"
    else:
        result['earliest_insertion_label'] = "after end of tree"

    # Compute available trusted LMs at this insertion point
    # An LM is "available" if it's satisfied (leak or tree source within max_source_position)
    available_by_tier = {'anchor': 0, 'high': 0, 'medium': 0, 'low': 0, 'unverified': 0}
    for dep in result['source_dependencies']:
        if dep['satisfied'] and dep['latest_tree_position'] <= max_source_position:
            tier = dep['tier']
            available_by_tier[tier] = available_by_tier.get(tier, 0) + 1
    result['available_trusted_at_insertion'] = available_by_tier

    # Warnings
    trusted_count = available_by_tier.get('anchor', 0) + available_by_tier.get('high', 0)
    if trusted_count < 2:
        result['issues'].append(f"Only {trusted_count} anchor+high LMs available (need >=2 for fit)")
    if result['lms_marked'] < 4:
        result['issues'].append(f"Only {result['lms_marked']} LMs marked (need >=4 for 7-param fit)")
    detached_lms = [d['lm'] for d in result['source_dependencies'] if not d['satisfied']]
    if detached_lms:
        result['issues'].append(f"{len(detached_lms)} LMs are detached (no leak or tree source)")
    return result


def print_analysis(analysis, verbose=False):
    print()
    print("─" * 78)
    print(f"  {analysis['cam_name']}")
    print("─" * 78)
    print(f"  LMs marked: {analysis['lms_marked']}")
    if analysis['lms_by_tier']:
        tier_str = ", ".join(f"{t}={c}" for t, c in sorted(analysis['lms_by_tier'].items()))
        print(f"  LMs by tier: {tier_str}")
    print(f"  Earliest insertion: {analysis['earliest_insertion_label']}")
    if analysis['available_trusted_at_insertion']:
        avail = analysis['available_trusted_at_insertion']
        avail_str = ", ".join(f"{t}={c}" for t, c in avail.items() if c > 0)
        print(f"  Available at insertion: {avail_str}")
    if analysis['issues']:
        for issue in analysis['issues']:
            print(f"  ⚠ {issue}")
    else:
        print(f"  ✓ Ready to calibrate at this position")

    if verbose:
        print(f"  Per-LM dependencies:")
        for dep in analysis['source_dependencies'][:15]:
            src = dep['latest_tree_source'] or '(none)'
            pos = dep['latest_tree_position']
            pos_str = f"#{pos+1}" if pos >= 0 else "—"
            n_leak = len(dep.get('leak_sources', []))
            n_otb = len(dep.get('non_tree_non_leak_sources', []))
            extras = []
            if n_leak:
                extras.append(f"+{n_leak} leak")
            if n_otb:
                extras.append(f"+{n_otb} non-tree")
            extra_str = " " + ", ".join(extras) if extras else ""
            sat = "✓" if dep['satisfied'] else "✗"
            print(f"    {sat} [{dep['tier']:10}] {dep['lm'][:35]:<35} tree: {pos_str} ({src}){extra_str}")
        if len(analysis['source_dependencies']) > 15:
            print(f"    ... and {len(analysis['source_dependencies']) - 15} more")


def main():
    parser = argparse.ArgumentParser(description="Analyze where to insert cams in the calibration tree.")
    parser.add_argument('--cam', default=None, help="Analyze a specific cam name only.")
    parser.add_argument('--include-leak', action='store_true', help="Include leak cams in analysis.")
    parser.add_argument('--verbose', '-v', action='store_true', help="Show per-LM details.")
    parser.add_argument('--sort-by', default='ready',
                        choices=['ready', 'insertion', 'name', 'lms'],
                        help="Sort cams: ready (sortable first), insertion position, name, or LM count.")
    args = parser.parse_args()

    tree_order = parse_tree_order()
    tree_set = set(tree_order)
    print(f"Tree contains {len(tree_order)} cams")

    cameras, pixels, landmarks, lm_tiers = load_data()

    # Build the set of leak cams (foundation, always available)
    leak_set = {n for n, c in cameras.items() if is_leak_cam(c)}
    print(f"Leak cams (foundation): {len(leak_set)}")

    # Determine cams to analyze
    if args.cam:
        if args.cam not in cameras:
            print(f"ERROR: '{args.cam}' not in cameras.json")
            return 1
        cams_to_analyze = [args.cam]
    else:
        # All non-tree cams (filtered by leak)
        cams_to_analyze = []
        for n, c in cameras.items():
            if n in tree_set:
                continue
            if not args.include_leak and is_leak_cam(c):
                continue
            cams_to_analyze.append(n)
        cams_to_analyze.sort()
        print(f"Analyzing {len(cams_to_analyze)} non-tree cams "
              f"({'including' if args.include_leak else 'excluding'} leak)")
    print()

    # Analyze each
    analyses = []
    for cam_name in cams_to_analyze:
        analyses.append(analyze_cam(cam_name, tree_order, tree_set, leak_set,
                                     cameras, pixels, landmarks, lm_tiers))

    # Sort
    if args.sort_by == 'ready':
        # Cams without issues first, then by insertion position
        analyses.sort(key=lambda a: (len(a['issues']), a['earliest_insertion']))
    elif args.sort_by == 'insertion':
        analyses.sort(key=lambda a: a['earliest_insertion'])
    elif args.sort_by == 'name':
        analyses.sort(key=lambda a: a['cam_name'])
    elif args.sort_by == 'lms':
        analyses.sort(key=lambda a: -a['lms_marked'])

    # Print
    if args.cam or args.verbose:
        for a in analyses:
            print_analysis(a, verbose=args.verbose)
    else:
        # Compact summary
        print(f"{'Cam':<45}{'Insert':<10}{'LMs':<7}{'Trusted':<10}{'Issues'}")
        print("-" * 95)
        for a in analyses:
            insertion = f"#{a['earliest_insertion']}"
            lms = str(a['lms_marked'])
            trusted = a['available_trusted_at_insertion'].get('anchor', 0) + \
                      a['available_trusted_at_insertion'].get('high', 0)
            issues = "✓" if not a['issues'] else f"⚠ {len(a['issues'])}"
            print(f"  {a['cam_name'][:42]:<43}{insertion:<10}{lms:<7}{trusted:<10}{issues}")

    # Summary
    ready = [a for a in analyses if not a['issues']]
    not_ready = [a for a in analyses if a['issues']]
    print()
    print("=" * 78)
    print(f"  Summary: {len(ready)} cams ready to calibrate, {len(not_ready)} have issues")
    print("=" * 78)

    return 0


if __name__ == '__main__':
    sys.exit(main())
