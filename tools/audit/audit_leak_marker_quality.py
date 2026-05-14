#!/usr/bin/env python3
"""
audit_leak_marker_quality.py — Audit reprojection errors for all markings
on LEAK cams.

LEAK cams have fixed xyz/ypr/fov (extracted from game debug overlay).
So for any LM marked on a LEAK cam, the reprojection error in arcmin
quantifies either:
  - bad marker pixel placement, OR
  - bad LM xyz position

Critically, we distinguish two cases per marking:
  CASE A: LEAK cam IS a source camera for this LM
          → high error = bug at triangulation time (geometrically impossible
            unless marker drifted or LM was edited without retriangulation)
  CASE B: LEAK cam is NOT a source for this LM
          → high error = either marker placement or LM xyz tension between
            this cam's view and the triangulated position

CASE A errors are diagnostic and easy to fix.
CASE B errors are signals of LM xyz problems somewhere in the dataset.

Purely read-only. Reports tier breakdown of outliers.

Run from gtamaplib-main/:
    python3 tools/audit/audit_leak_marker_quality.py
    python3 tools/audit/audit_leak_marker_quality.py --threshold 30
    python3 tools/audit/audit_leak_marker_quality.py --cam "Diner (NE)"
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

CAMERAS_JSON   = os.path.join(DATA_DIR, 'cameras.json')
PIXELS_JSON    = os.path.join(DATA_DIR, 'pixels.json')
LANDMARKS_JSON = os.path.join(DATA_DIR, 'landmarks.json')


def is_leak(cam_data):
    s = cam_data.get('source', '') if isinstance(cam_data, dict) else ''
    return bool(re.match(r'\d{4}-\d{2}-\d{2}', s))


def reproj_error_arcmin(cam, lm_xyz, marker_px):
    """Compute reprojection error in arcmin between projected LM and marker."""
    try:
        proj = cam.get_pixel(lm_xyz)
        if proj is None:
            return None
        px, py = float(proj[0]), float(proj[1])
        mx, my = float(marker_px[0]), float(marker_px[1])
        dpx = px - mx
        dpy = py - my
        # Convert pixel error to angular error.
        # Approximate: arcmin = sqrt(dpx² + dpy²) * (hfov_arcmin / image_width)
        # We use cam.hfov (degrees) and cam.w if available.
        hfov_deg = cam.fov[0] if cam.fov else 60.0
        hfov_arcmin = hfov_deg * 60.0
        w = cam.w
        pixel_dist = math.sqrt(dpx*dpx + dpy*dpy)
        arcmin = pixel_dist * (hfov_arcmin / w)
        return arcmin
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--threshold', type=float, default=10.0,
                        help='Arcmin threshold for "outlier" (default 10)')
    parser.add_argument('--cam', type=str, default=None,
                        help='Detail report for one LEAK cam')
    parser.add_argument('--top', type=int, default=30,
                        help='Show top N worst outliers (default 30)')
    args = parser.parse_args()

    with open(CAMERAS_JSON) as f:
        cameras = json.load(f)
    with open(LANDMARKS_JSON) as f:
        landmarks = json.load(f)
    with open(PIXELS_JSON) as f:
        pixels = json.load(f)

    leak_cams = {n for n, d in cameras.items() if is_leak(d)}

    # Collect all markings with their reprojection errors
    # Each entry: (cam_name, lm_name, error_arcmin, case_A_or_B)
    all_records = []

    for cam_name in leak_cams:
        cam_data = cameras[cam_name]
        if not cam_data.get('xyz') or not cam_data.get('ypr') or not cam_data.get('fov'):
            continue
        try:
            cam = ml.get_camera(cam_name)
        except Exception:
            continue

        marked = pixels.get(cam_name, {})
        for lm_name, marker_px in marked.items():
            lm_data = landmarks.get(lm_name, {})
            lm_xyz = lm_data.get('xyz') if isinstance(lm_data, dict) else None
            if not lm_xyz:
                continue
            err = reproj_error_arcmin(cam, lm_xyz, marker_px)
            if err is None:
                continue
            sources = lm_data.get('source_cameras', [])
            case = 'A' if cam_name in sources else 'B'
            all_records.append((cam_name, lm_name, err, case))

    print(f"Audited {len(all_records)} LEAK markings across {len(leak_cams)} LEAK cams.")
    print()

    # Detailed report for one cam
    if args.cam:
        cam_records = [r for r in all_records if r[0] == args.cam]
        if not cam_records:
            print(f"No data for LEAK cam '{args.cam}'.")
            return
        cam_records.sort(key=lambda r: -r[2])
        print(f"═" * 70)
        print(f"  {args.cam}  ({len(cam_records)} marked LMs)")
        print(f"═" * 70)
        print(f"  {'err':>7s}   case  LM")
        print(f"  {'-'*7}   ----  {'-'*40}")
        for cam_name, lm_name, err, case in cam_records:
            flag = ' ⚠' if err >= args.threshold else ''
            print(f"  {err:6.1f}'   {case}     {lm_name}{flag}")
        return

    # Aggregate stats
    outliers = [r for r in all_records if r[2] >= args.threshold]
    case_A = [r for r in all_records if r[3] == 'A']
    case_B = [r for r in all_records if r[3] == 'B']
    case_A_outliers = [r for r in outliers if r[3] == 'A']
    case_B_outliers = [r for r in outliers if r[3] == 'B']

    print(f"=== Summary ===")
    print(f"  All markings:                       {len(all_records)}")
    print(f"  CASE A (cam IS source of LM):       {len(case_A)}")
    print(f"  CASE B (cam NOT source of LM):      {len(case_B)}")
    print()
    print(f"  Outliers (err ≥ {args.threshold:.0f}'):                {len(outliers)}")
    print(f"    of which CASE A (BUG-LEVEL):      {len(case_A_outliers)}")
    print(f"    of which CASE B (LM XYZ TENSION): {len(case_B_outliers)}")
    print()

    # Histogram by error bucket
    buckets = [(0, 1), (1, 3), (3, 10), (10, 30), (30, 60), (60, 9999)]
    print(f"=== Error distribution ===")
    print(f"  {'bucket':>10s}  {'total':>6s}  {'caseA':>6s}  {'caseB':>6s}")
    for lo, hi in buckets:
        total = sum(1 for r in all_records if lo <= r[2] < hi)
        ca = sum(1 for r in all_records if lo <= r[2] < hi and r[3] == 'A')
        cb = sum(1 for r in all_records if lo <= r[2] < hi and r[3] == 'B')
        bucket_label = f"{lo:.0f}'-{hi:.0f}'" if hi < 9999 else f"≥ {lo:.0f}'"
        print(f"  {bucket_label:>10s}  {total:>6d}  {ca:>6d}  {cb:>6d}")
    print()

    # Top outliers
    if outliers:
        outliers.sort(key=lambda r: -r[2])
        print(f"=== Top {min(args.top, len(outliers))} worst outliers ===")
        print(f"  {'err':>7s}   case  cam → LM")
        print(f"  {'-'*7}   ----  {'-'*55}")
        for cam_name, lm_name, err, case in outliers[:args.top]:
            print(f"  {err:6.1f}'   {case}     {cam_name} → {lm_name}")
        print()

    # CASE A outliers focus — these are the most actionable
    if case_A_outliers:
        case_A_outliers.sort(key=lambda r: -r[2])
        print(f"=== ALL CASE A outliers (likely bugs to fix) ===")
        print(f"  These are markings where the cam IS a source of the LM.")
        print(f"  Geometrically, the marker pixel SHOULD reproject to the LM xyz.")
        print(f"  Any drift here means: marker bad, OR LM xyz updated w/o retriangulation.")
        print()
        print(f"  {'err':>7s}   cam → LM")
        print(f"  {'-'*7}   {'-'*55}")
        for cam_name, lm_name, err, case in case_A_outliers:
            print(f"  {err:6.1f}'   {cam_name} → {lm_name}")
        print()

    print("Next steps:")
    print(f"  python3 tools/audit/audit_leak_marker_quality.py --cam 'CAM_NAME'")
    print(f"  to see all markings for a specific LEAK cam.")
    print(f"  python3 tools/audit/audit_leak_marker_quality.py --threshold 30")
    print(f"  to filter for severe outliers only.")


if __name__ == '__main__':
    main()
