#!/usr/bin/env python3
"""
calibrate_cam.py — Narrative calibration assistant for a single camera.

For a given cam, prints a structured report:
  1. State: tier, source, marked LMs (by tier), current loss
  2. Suggested action (based on what's marked)
  3. Post-optimize self-source divergence check (if cam was optimized)
  4. Update LMs suggestion (if safe)
  5. Likely-visible anchor LMs (projected into frame)

Usage:
    python3 tools/calibrate_cam.py "Yacht (1)"
    python3 tools/calibrate_cam.py "Leonida Keys 02 (Sidewalk)"
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

CAMERAS_JSON = os.path.join(DATA_DIR, 'cameras.json')
PIXELS_JSON = os.path.join(DATA_DIR, 'pixels.json')
LANDMARKS_JSON = os.path.join(DATA_DIR, 'landmarks.json')
TIERS_JSON = os.path.join(GEN_DIR, 'confidence_tiers.json')

sys.path.insert(0, REPO_DIR)
import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]
import gtamaplib as ml


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


def compute_pixel_err(cam, lm_xyz, marked_px):
    """Returns error in arcmin between projected and marked pixel."""
    try:
        proj = cam.get_pixel(lm_xyz)
        if proj is None:
            return None
        dx = (float(proj[0]) - marked_px[0]) * cam.hfov / cam.w * 60.0
        dy = (float(proj[1]) - marked_px[1]) * cam.vfov / cam.h * 60.0
        return math.sqrt(dx*dx + dy*dy)
    except Exception:
        return None


def find_likely_visible(cam, landmarks, lm_tiers, cam_pixels_set,
                       only_tiers=('anchor', 'high'), max_count=15):
    """For each LM not already marked, check if it would project in-frame."""
    candidates = []
    w, h = cam.w, cam.h
    for lm_name, lm_data in landmarks.items():
        if lm_name in cam_pixels_set:
            continue  # already marked
        tier = lm_tiers.get(lm_name, 'unverified')
        if tier not in only_tiers:
            continue
        xyz = lm_data.get('xyz') if isinstance(lm_data, dict) else lm_data
        if not xyz:
            continue
        try:
            proj = cam.get_pixel(xyz)
            if proj is None:
                continue
            px, py = float(proj[0]), float(proj[1])
            if 0 <= px <= w and 0 <= py <= h:
                # Distance from cam (for sorting)
                dx = xyz[0] - cam.xyz[0]
                dy = xyz[1] - cam.xyz[1]
                dz = xyz[2] - cam.xyz[2]
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                candidates.append((lm_name, tier, (round(px, 0), round(py, 0)), dist))
        except Exception:
            continue
    candidates.sort(key=lambda x: x[3])  # nearest first
    return candidates[:max_count]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cam_name', help='Camera name (e.g. "Yacht (1)")')
    ap.add_argument('--max-visible', type=int, default=10,
                    help='Max likely-visible LMs to suggest (default 10)')
    ap.add_argument('--include-medium', action='store_true',
                    help='Also suggest medium-tier LMs as visible candidates')
    args = ap.parse_args()

    cam_name = args.cam_name
    cameras, pixels, landmarks, cam_tiers, lm_tiers = load_data()

    if cam_name not in cameras:
        print(f"ERROR: cam '{cam_name}' not found in cameras.json")
        print(f"\nMaybe you meant:")
        for c in sorted(cameras.keys()):
            if cam_name.lower() in c.lower():
                print(f"  {c}")
        sys.exit(1)

    cam_data = cameras[cam_name]
    cam = ml.get_camera(cam_name)
    cam_pixels = pixels.get(cam_name, {})
    cam_tier = cam_tiers.get(cam_name, 'unverified')

    # Header
    print("═" * 70)
    print(f"  {cam_name}")
    print("═" * 70)
    print(f"  Tier:   {cam_tier}")
    print(f"  Source: {cam_data.get('source', '?')}")
    print(f"  xyz:    {cam_data.get('xyz')}")
    print(f"  ypr:    {cam_data.get('ypr')}")
    print(f"  fov:    {cam_data.get('fov')}")
    print()

    # Marked LMs breakdown
    by_tier = {'anchor': [], 'high': [], 'medium': [], 'low': [], 'unverified': []}
    for lm_name, mp in cam_pixels.items():
        lm_data = landmarks.get(lm_name)
        if lm_data is None:
            continue
        tier = lm_tiers.get(lm_name, 'unverified')
        lm_xyz = lm_data.get('xyz') if isinstance(lm_data, dict) else lm_data
        if not lm_xyz:
            continue
        err = compute_pixel_err(cam, lm_xyz, mp)
        by_tier.setdefault(tier, []).append((lm_name, err))

    print(f"  Marked LMs ({len(cam_pixels)} total):")
    for tier in ('anchor', 'high', 'medium', 'low', 'unverified'):
        items = by_tier.get(tier, [])
        if not items:
            continue
        print(f"    {tier:<10}: {len(items)}")
        # Show top errors for this tier
        items_sorted = sorted([i for i in items if i[1] is not None],
                              key=lambda x: -x[1])
        for lm, err in items_sorted[:3]:
            flag = '⚠' if err and err > 10 else ' '
            err_str = f"{err:.2f}'" if err is not None else "?"
            print(f"        {flag} {err_str:>8}  {lm}")
    print()

    # Compute current loss (RMS over anchor+high only — the "trusted" loss)
    trusted_errs = []
    for tier in ('anchor', 'high'):
        for lm, err in by_tier.get(tier, []):
            if err is not None:
                trusted_errs.append(err)
    if trusted_errs:
        rms = math.sqrt(sum(e*e for e in trusted_errs) / len(trusted_errs))
        loss_flag = '✓' if rms < 5 else ('⚠' if rms < 20 else '✗')
        print(f"  Loss (RMS anchor+high): {loss_flag} {rms:.2f}' over {len(trusted_errs)} LMs")
    else:
        print(f"  Loss: — (no anchor/high LMs marked)")
    print()

    # Self-source divergence check
    self_source_lms = []
    for lm_name, mp in cam_pixels.items():
        lm_data = landmarks.get(lm_name, {})
        if not isinstance(lm_data, dict):
            continue
        src = lm_data.get('source_cameras', [])
        if cam_name in src:
            lm_xyz = lm_data.get('xyz')
            if lm_xyz:
                err = compute_pixel_err(cam, lm_xyz, mp)
                if err is not None:
                    self_source_lms.append((lm_name, err))

    if self_source_lms:
        max_ss = max(e for _, e in self_source_lms)
        diverged = [(lm, e) for lm, e in self_source_lms if e > 10]
        if diverged:
            print(f"  ⚠ SELF-SOURCE DIVERGENCE detected ({len(diverged)} LMs > 10'):")
            for lm, e in sorted(diverged, key=lambda x: -x[1])[:5]:
                print(f"      {e:.1f}'  {lm}")
            print(f"  → Cam params may have drifted from self-source LMs.")
            print(f"    Consider reverting cam params OR re-triangulating these LMs.")
        else:
            print(f"  ✓ Self-source LMs OK (max err {max_ss:.1f}', {len(self_source_lms)} LMs)")
        print()

    # Decide action and print
    n_anchor = len(by_tier.get('anchor', []))
    n_high = len(by_tier.get('high', []))
    n_strong = n_anchor + n_high

    print("─" * 70)
    print("  SUGGESTED ACTION")
    print("─" * 70)

    if n_strong >= 3:
        print(f"  Cam has {n_strong} anchor+high LMs marked — can be auto-optimized.")
        print()
        print(f"  Run:")
        cam_arg = cam_name.replace("'", "'\\''")
        print(f"    python3 tools/batch_optimize.py --cams '{cam_arg}' --apply")
        if trusted_errs and rms < 5:
            print()
            print(f"  Loss is already low ({rms:.2f}'). Re-optimize will only polish.")
    elif n_strong > 0 or len(cam_pixels) > 0:
        print(f"  Cam has only {n_strong} anchor+high (need ≥3 for auto-optimize).")
        print(f"  Other tiers: {sum(len(by_tier.get(t, [])) for t in ('medium', 'low'))} medium+low LMs marked.")
        print()
        print(f"  → Mark MORE anchor+high LMs in the UI to enable auto-optimize.")
        print(f"  → Likely-visible suggestions below.")
    else:
        print(f"  Cam has 0 LMs marked — fresh start needed.")
        print()
        print(f"  → Open '{cam_name}' in UI: http://localhost:8765")
        print(f"  → Mark at least 3 anchor LMs visible in the scene.")
        print(f"  → Likely-visible suggestions below.")
    print()

    # Likely visible
    tiers_filter = ('anchor', 'high')
    if args.include_medium:
        tiers_filter = ('anchor', 'high', 'medium')

    marked_set = set(cam_pixels.keys())
    visible = find_likely_visible(cam, landmarks, lm_tiers, marked_set,
                                   only_tiers=tiers_filter, max_count=args.max_visible)

    if visible:
        print("─" * 70)
        print(f"  LIKELY VISIBLE LMS (not yet marked, sorted by distance)")
        print("─" * 70)
        for lm_name, tier, (px, py), dist in visible:
            print(f"    [{tier:<6}]  dist={dist:>6.0f}m  px≈({px:>5.0f}, {py:>4.0f})  {lm_name}")
        print()
        print(f"  Note: these are PROJECTED positions assuming current cam params are roughly correct.")
        print(f"  If cam params are very wrong, these projections won't help. Calibrate first with what you can see.")
    else:
        if tiers_filter == ('anchor', 'high'):
            print("  No anchor/high LMs project in-frame with current params.")
            print("  → Try --include-medium to broaden the suggestions.")
            print("  → Or cam params may be too far off for projection to be useful.")
        else:
            print("  No likely-visible LMs found even with medium tier included.")

    print()
    print("─" * 70)
    print("  AFTER YOU OPTIMIZE / SAVE")
    print("─" * 70)
    print(f"  Re-run this script to see updated state.")
    print(f"  If trusted RMS < 5' AND no self-source divergence, you can:")
    print(f"    → Click 'Update LMs' in UI to propagate calibration to LMs this cam is source for")
    print(f"    → Or run bundle_adjust to polish the whole system")
    print()


if __name__ == '__main__':
    main()
