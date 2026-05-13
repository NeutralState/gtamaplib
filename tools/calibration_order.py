#!/usr/bin/env python3
"""
calibration_order.py — Suggest optimal calibration order for a set of cams.

Algorithm (greedy, with virtual promotion):
  1. Score each cam by # of anchor+high LMs it has marked
  2. Pick the highest-scoring cam → it goes first in the order
  3. "Promote" its self-source LMs: assume they become anchor-quality
     once this cam is calibrated. This may boost the score of other cams
     that mark these LMs.
  4. Repeat until all cams are ordered.

Tie-breaking: by cam tier (anchor > high > medium > low > unverified),
then by total pixels marked.

Output: ordered list of cams with rationale for each.

Usage:
    python3 tools/calibration_order.py --tier unverified
    python3 tools/calibration_order.py --cams "Yacht (1),Yacht (2),Vice Beach (A)"
    python3 tools/calibration_order.py --tier unverified,low
"""

import argparse
import json
import math
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(THIS_DIR)
DATA_DIR = os.path.join(REPO_DIR, 'gtamapdata')
GEN_DIR = os.path.join(THIS_DIR, 'generated')

sys.path.insert(0, REPO_DIR)
import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]
import gtamaplib as ml

CAMERAS_JSON = os.path.join(DATA_DIR, 'cameras.json')
PIXELS_JSON = os.path.join(DATA_DIR, 'pixels.json')
LANDMARKS_JSON = os.path.join(DATA_DIR, 'landmarks.json')
TIERS_JSON = os.path.join(GEN_DIR, 'confidence_tiers.json')

TIER_ORDER = {'anchor': 5, 'high': 4, 'medium': 3, 'low': 2, 'unverified': 1}


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


def score_cam(cam_name, pixels, lm_tiers, promoted_lms):
    """Returns (n_strong, n_total). n_strong = anchor+high (including promoted)."""
    cam_pixels = pixels.get(cam_name, {})
    n_strong = 0
    for lm_name in cam_pixels:
        tier = lm_tiers.get(lm_name, 'unverified')
        if tier in ('anchor', 'high') or lm_name in promoted_lms:
            n_strong += 1
    return n_strong, len(cam_pixels)


# ── CO-LOSS-GOLDMINE-V1 ──
def compute_trusted_loss(cam_name, pixels, landmarks, lm_tiers):
    """RMS error in arcmin over anchor+high LMs. Returns None if no such LMs."""
    try:
        cam = ml.get_camera(cam_name)
    except Exception:
        return None
    cam_pixels = pixels.get(cam_name, {})
    errs = []
    for lm_name, mp in cam_pixels.items():
        tier = lm_tiers.get(lm_name, 'unverified')
        if tier not in ('anchor', 'high'):
            continue
        lm_data = landmarks.get(lm_name)
        lm_xyz = lm_data.get('xyz') if isinstance(lm_data, dict) else lm_data
        if not lm_xyz:
            continue
        try:
            proj = cam.get_pixel(lm_xyz)
            if proj is None:
                continue
            dx = (float(proj[0]) - mp[0]) * cam.hfov / cam.w * 60.0
            dy = (float(proj[1]) - mp[1]) * cam.vfov / cam.h * 60.0
            errs.append(math.sqrt(dx*dx + dy*dy))
        except Exception:
            continue
    if not errs:
        return None
    return math.sqrt(sum(e*e for e in errs) / len(errs))


def get_self_source_lms(cam_name, pixels, landmarks):
    """Returns set of LM names where this cam is in source_cameras."""
    result = set()
    cam_pixels = pixels.get(cam_name, {})
    for lm_name in cam_pixels:
        lm_data = landmarks.get(lm_name, {})
        if not isinstance(lm_data, dict):
            continue
        src = lm_data.get('source_cameras', [])
        if cam_name in src:
            result.add(lm_name)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tier', help='Comma-separated tiers (anchor/high/medium/low/unverified)')
    ap.add_argument('--cams', help='Comma-separated cam names (overrides --tier)')
    ap.add_argument('--limit', type=int, help='Limit to N cams in output')
    args = ap.parse_args()

    cameras, pixels, landmarks, cam_tiers, lm_tiers = load_data()

    # Build cam list
    if args.cams:
        cam_list = [c.strip() for c in args.cams.split(',')]
    elif args.tier:
        wanted = set(t.strip() for t in args.tier.split(','))
        cam_list = [c for c, t in cam_tiers.items() if t in wanted]
    else:
        print("ERROR: must specify --cams or --tier")
        sys.exit(1)

    # Validate
    cam_list = [c for c in cam_list if c in cameras]
    if not cam_list:
        print("ERROR: no valid cams")
        sys.exit(1)

    print(f"Computing calibration order for {len(cam_list)} cams...")
    print()

    # Greedy ordering
    remaining = set(cam_list)
    ordered = []
    promoted_lms = set()  # LMs that became "anchor-quality" via prior calibrations
    promotion_source = {}  # lm_name -> cam_name that promoted it

    while remaining:
        # Score all remaining cams
        scored = []
        for cn in remaining:
            n_strong, n_total = score_cam(cn, pixels, lm_tiers, promoted_lms)
            cam_tier = cam_tiers.get(cn, 'unverified')
            tier_priority = TIER_ORDER.get(cam_tier, 0)
            scored.append((n_strong, tier_priority, n_total, cn))

        # Sort: highest n_strong first, then higher tier_priority, then more pixels
        scored.sort(reverse=True)

        # Pick the best
        best_n_strong, best_tier_p, best_n_total, best_cam = scored[0]

        # Compute what this cam will "give back"
        ss_lms = get_self_source_lms(best_cam, pixels, landmarks)
        new_promotions = ss_lms - promoted_lms

        loss = compute_trusted_loss(best_cam, pixels, landmarks, lm_tiers)
        ordered.append({
            'cam': best_cam,
            'tier': cam_tiers.get(best_cam, 'unverified'),
            'n_strong': best_n_strong,
            'n_total': best_n_total,
            'promotions': new_promotions,
            'loss': loss,
        })

        for lm in new_promotions:
            promoted_lms.add(lm)
            promotion_source[lm] = best_cam

        remaining.discard(best_cam)

    # Print output
    if args.limit:
        ordered = ordered[:args.limit]

    print("─" * 78)
    print(f"  CALIBRATION ORDER ({len(ordered)} cams)")
    print("─" * 78)
    print()

    for i, entry in enumerate(ordered, 1):
        cn = entry['cam']
        n_s = entry['n_strong']
        n_t = entry['n_total']
        tier = entry['tier']
        promos = entry['promotions']

        loss = entry.get('loss')
        # Status icon + action logic with loss check + goldmine flag
        is_goldmine = n_t >= 20 and n_s <= 2
        if n_s >= 3:
            if loss is not None and loss > 10:
                status = "⚠"
                action = f"BROKEN (loss={loss:.1f}') — investigate before optimize"
            else:
                status = "✓"
                action = "AUTO-OPTIMIZE READY"
                if loss is not None:
                    action += f" (loss={loss:.2f}')"
        elif n_s > 0:
            status = "⭐" if is_goldmine else "◐"
            need = 3 - n_s
            goldmine_note = " GOLDMINE!" if is_goldmine else ""
            action = f"NEEDS {need} MORE ANCHOR+HIGH{goldmine_note}"
            if loss is not None:
                action += f" (current loss={loss:.2f}')"
        else:
            status = "⭐" if is_goldmine else "○"
            goldmine_note = " GOLDMINE!" if is_goldmine else ""
            action = f"FRESH START (0 anchors){goldmine_note}"

        print(f"  {i:>2}. {status} [{tier:<10}] {cn}")
        print(f"      {n_s} anchor+high · {n_t} total marked · {action}")
        if promos:
            print(f"      Will promote: {len(promos)} self-source LMs")
            for lm in sorted(promos)[:3]:
                print(f"        • {lm}")
            if len(promos) > 3:
                print(f"        • ... and {len(promos) - 3} more")
        print()

    # Summary
    n_ready = sum(1 for e in ordered if e['n_strong'] >= 3)
    n_partial = sum(1 for e in ordered if 0 < e['n_strong'] < 3)
    n_fresh = sum(1 for e in ordered if e['n_strong'] == 0)
    total_promoted = sum(len(e['promotions']) for e in ordered)

    print("─" * 78)
    print(f"  SUMMARY")
    print("─" * 78)
    print(f"  Auto-optimize ready:     {n_ready}")
    print(f"  Need more marking:       {n_partial}")
    print(f"  Fresh start (0 anchors): {n_fresh}")
    print(f"  LMs promoted along way:  {total_promoted}")
    print()
    print(f"  Next step: tackle #1 with:")
    if ordered:
        cn = ordered[0]['cam']
        print(f"    python3 tools/calibrate_cam.py '{cn}'")
    print()


if __name__ == '__main__':
    main()
