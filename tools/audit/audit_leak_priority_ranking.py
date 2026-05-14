#!/usr/bin/env python3
"""
audit_leak_priority_ranking.py — Cross-reference LEAK cam influence with
marker quality outliers to produce an actionable priority ranking.

For each LEAK cam, compute 3 independent dimensions (sector scores, not
weighted-aggregated, to preserve the "why" behind each ranking):

  1. DIRECT CONTRIBUTION:
     - gen1_lms_sourced: how many LMs this cam directly triangulated
     - gen1_all_leak: how many of those are 100% LEAK-sourced
       (pure ground truth)

  2. DOWNSTREAM REACH (from influence tree, B-strict criterion):
     - downstream_cams: calibrated cams that depend on this LEAK
       transitively via anchor+high markings
     - downstream_lms: LMs in the transitive closure
     - tree_depth: max hops

  3. OUTLIER RISK (from marker quality audit):
     - case_A_outlier_count: bugs (cam IS source, error ≥ 10')
     - case_A_outlier_max: worst error in arcmin
     - case_B_outlier_count: tensions (cam NOT source)
     - case_B_outlier_max

Each cam is then classified into one of 4 quadrants:

  HIGH PRIORITY — high influence AND has outliers → fix URGENT
  HIGH IMPACT   — high influence AND no outliers → keep clean (protect)
  LOW PRIORITY  — low influence AND has outliers → fix later
  IGNORE        — low influence AND no outliers → passive

"high influence" threshold: gen1_lms ≥ 10 OR downstream_cams ≥ 5
"has outliers" threshold: any case_A or case_B ≥ 10 arcmin

Outputs:
  - JSON: tools/generated/leak_priority_ranking.json
  - Console: 4 quadrants with cam-by-cam breakdown

Run from gtamaplib-main/:
  python3 tools/audit/audit_leak_priority_ranking.py
"""

import json
import math
import os
import re
import sys
from collections import defaultdict

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml

DATA_DIR = os.path.join(GTAMAP_DIR, 'gtamapdata')
GEN_DIR  = os.path.join(GTAMAP_DIR, 'tools', 'generated')

CAMERAS_JSON   = os.path.join(DATA_DIR, 'cameras.json')
PIXELS_JSON    = os.path.join(DATA_DIR, 'pixels.json')
LANDMARKS_JSON = os.path.join(DATA_DIR, 'landmarks.json')
INFLUENCE_JSON = os.path.join(GEN_DIR, 'leak_influence_tree.json')
OUT_JSON       = os.path.join(GEN_DIR, 'leak_priority_ranking.json')

OUTLIER_THRESHOLD = 10.0  # arcmin
HIGH_INFLUENCE_GEN1_LMS = 10
HIGH_INFLUENCE_DOWNSTREAM_CAMS = 5


def is_leak(cam_data):
    s = cam_data.get('source', '') if isinstance(cam_data, dict) else ''
    return bool(re.match(r'\d{4}-\d{2}-\d{2}', s))


def reproj_error_arcmin(cam, lm_xyz, marker_px):
    try:
        proj = cam.get_pixel(lm_xyz)
        if proj is None:
            return None
        px, py = float(proj[0]), float(proj[1])
        mx, my = float(marker_px[0]), float(marker_px[1])
        dpx = px - mx
        dpy = py - my
        hfov_deg = cam.fov[0] if cam.fov else 60.0
        hfov_arcmin = hfov_deg * 60.0
        w = cam.w
        pixel_dist = math.sqrt(dpx*dpx + dpy*dpy)
        return pixel_dist * (hfov_arcmin / w)
    except Exception:
        return None


def compute_outliers_for_leak_cams(cameras, landmarks, pixels, leak_cams):
    """Returns dict[cam] -> {'case_A_outliers': [(lm, err)], 'case_B_outliers': [(lm, err)]}"""
    result = {cam: {'case_A_outliers': [], 'case_B_outliers': []} for cam in leak_cams}
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
            if err is None or err < OUTLIER_THRESHOLD:
                continue
            sources = lm_data.get('source_cameras', [])
            if cam_name in sources:
                result[cam_name]['case_A_outliers'].append((lm_name, err))
            else:
                result[cam_name]['case_B_outliers'].append((lm_name, err))
    # Sort outliers by error descending
    for cam in result:
        result[cam]['case_A_outliers'].sort(key=lambda x: -x[1])
        result[cam]['case_B_outliers'].sort(key=lambda x: -x[1])
    return result


def compute_gen1(leak_cam, landmarks, leak_cams_set):
    """Return (gen1_lms_count, gen1_all_leak_count, gen1_lm_names)."""
    gen1 = []
    for lm_name, lm_data in landmarks.items():
        srcs = lm_data.get('source_cameras', []) if isinstance(lm_data, dict) else []
        if leak_cam in srcs:
            all_leak = all(s in leak_cams_set for s in srcs)
            gen1.append((lm_name, all_leak))
    return gen1


def main():
    # Load all the things
    with open(CAMERAS_JSON) as f:
        cameras = json.load(f)
    with open(LANDMARKS_JSON) as f:
        landmarks = json.load(f)
    with open(PIXELS_JSON) as f:
        pixels = json.load(f)

    if not os.path.isfile(INFLUENCE_JSON):
        print(f"ERROR: {INFLUENCE_JSON} not found.")
        print(f"Run first: python3 tools/audit/audit_leak_influence_tree.py")
        sys.exit(1)
    with open(INFLUENCE_JSON) as f:
        influence = json.load(f)

    leak_cams = sorted(n for n, d in cameras.items() if is_leak(d))
    leak_cams_set = set(leak_cams)
    print(f"Loaded {len(cameras)} cams ({len(leak_cams)} LEAK), "
          f"{len(landmarks)} LMs, "
          f"{sum(len(m) for m in pixels.values())} marker pixels")
    print(f"Computing outliers (threshold {OUTLIER_THRESHOLD:.0f}')...")
    outliers = compute_outliers_for_leak_cams(cameras, landmarks, pixels, leak_cams)

    # Per-cam analysis
    records = {}
    for cam in leak_cams:
        # Direct contribution
        gen1 = compute_gen1(cam, landmarks, leak_cams_set)
        gen1_lms = len(gen1)
        gen1_all_leak = sum(1 for _, al in gen1 if al)

        # Downstream reach
        inf = influence['leak_cams'].get(cam, {})
        downstream_cams = inf.get('total_cams_reached_downstream', 0)
        downstream_lms  = inf.get('total_lms_reached', 0)
        tree_depth      = inf.get('max_depth', 0)

        # Outliers
        out = outliers[cam]
        cA_count = len(out['case_A_outliers'])
        cA_max   = out['case_A_outliers'][0][1] if cA_count else 0.0
        cB_count = len(out['case_B_outliers'])
        cB_max   = out['case_B_outliers'][0][1] if cB_count else 0.0

        # Classification
        high_influence = (gen1_lms >= HIGH_INFLUENCE_GEN1_LMS) or \
                         (downstream_cams >= HIGH_INFLUENCE_DOWNSTREAM_CAMS)
        has_outliers = (cA_count + cB_count) > 0

        if high_influence and has_outliers:
            quadrant = 'HIGH_PRIORITY'
        elif high_influence and not has_outliers:
            quadrant = 'HIGH_IMPACT'
        elif not high_influence and has_outliers:
            quadrant = 'LOW_PRIORITY'
        else:
            quadrant = 'IGNORE'

        records[cam] = {
            'quadrant': quadrant,
            'high_influence': high_influence,
            'has_outliers': has_outliers,
            'direct_contribution': {
                'gen1_lms_sourced': gen1_lms,
                'gen1_all_leak': gen1_all_leak,
                'gen1_lm_names': [n for n, _ in gen1],
            },
            'downstream_reach': {
                'cams': downstream_cams,
                'lms':  downstream_lms,
                'depth': tree_depth,
            },
            'outlier_risk': {
                'case_A_count':  cA_count,
                'case_A_max':    round(cA_max, 2),
                'case_B_count':  cB_count,
                'case_B_max':    round(cB_max, 2),
                'case_A_outliers': [(n, round(e, 2)) for n, e in out['case_A_outliers']],
                'case_B_outliers': [(n, round(e, 2)) for n, e in out['case_B_outliers']],
            },
        }

    # Group by quadrant
    by_quadrant = defaultdict(list)
    for cam, rec in records.items():
        by_quadrant[rec['quadrant']].append((cam, rec))

    # Sort each quadrant: by combined importance (gen1_lms + downstream_cams desc), then outlier severity
    for q in by_quadrant:
        by_quadrant[q].sort(
            key=lambda kv: (
                -kv[1]['direct_contribution']['gen1_lms_sourced'],
                -kv[1]['downstream_reach']['cams'],
                -kv[1]['outlier_risk']['case_A_max'],
            )
        )

    # JSON output
    os.makedirs(GEN_DIR, exist_ok=True)
    output = {
        'meta': {
            'outlier_threshold_arcmin': OUTLIER_THRESHOLD,
            'high_influence_threshold': {
                'gen1_lms': HIGH_INFLUENCE_GEN1_LMS,
                'downstream_cams': HIGH_INFLUENCE_DOWNSTREAM_CAMS,
            },
            'counts_by_quadrant': {
                q: len(by_quadrant[q]) for q in ['HIGH_PRIORITY', 'HIGH_IMPACT', 'LOW_PRIORITY', 'IGNORE']
            },
        },
        'cams': records,
    }
    with open(OUT_JSON, 'w') as f:
        json.dump(output, f, indent=2)

    # Console output
    print()
    print(f"{'═' * 78}")
    print(f"  LEAK PRIORITY RANKING")
    print(f"{'═' * 78}")
    print(f"  Outlier threshold: {OUTLIER_THRESHOLD:.0f} arcmin")
    print(f"  High-influence criteria: gen1_lms ≥ {HIGH_INFLUENCE_GEN1_LMS} "
          f"OR downstream_cams ≥ {HIGH_INFLUENCE_DOWNSTREAM_CAMS}")
    print()
    for q in ['HIGH_PRIORITY', 'HIGH_IMPACT', 'LOW_PRIORITY', 'IGNORE']:
        cams = by_quadrant[q]
        print(f"── {q}  ({len(cams)} cams)  " + "─" * (78 - 4 - len(q) - len(f"({len(cams)} cams)") - 2))
        if not cams:
            print(f"   (none)")
            print()
            continue
        print(f"   {'cam':<45s}  {'gen1':>4s}  {'g1L':>4s}  {'dn':>4s}  {'dL':>4s}  {'cA':>3s}  {'cAm':>5s}  {'cB':>3s}  {'cBm':>5s}")
        # Show all in HIGH_PRIORITY / HIGH_IMPACT, top 15 in LOW_PRIORITY, top 10 in IGNORE
        limit = {'HIGH_PRIORITY': 99, 'HIGH_IMPACT': 99, 'LOW_PRIORITY': 15, 'IGNORE': 10}[q]
        for cam, rec in cams[:limit]:
            dc = rec['direct_contribution']
            dr = rec['downstream_reach']
            o  = rec['outlier_risk']
            print(f"   {cam:<45s}  {dc['gen1_lms_sourced']:>4d}  {dc['gen1_all_leak']:>4d}  "
                  f"{dr['cams']:>4d}  {dr['lms']:>4d}  "
                  f"{o['case_A_count']:>3d}  {o['case_A_max']:>5.1f}  "
                  f"{o['case_B_count']:>3d}  {o['case_B_max']:>5.1f}")
        if len(cams) > limit:
            print(f"   ... and {len(cams) - limit} more (see JSON)")
        print()

    print(f"Legend: gen1=LMs directly sourced, g1L=of which all_leak, "
          f"dn=downstream cams, dL=downstream lms, cA/cAm=CASE A count/max err, "
          f"cB/cBm=CASE B count/max err")
    print()
    print(f"Full ranking written to: {OUT_JSON}")
    print()
    print(f"Suggested next action: fix the HIGH_PRIORITY outliers in order shown.")
    print(f"Top-of-list cams have the most influence; their bugs cascade the most.")


if __name__ == '__main__':
    main()
