#!/usr/bin/env python3
"""
discover_mesh_candidates.py — Find LM prefixes that could become procedural
                              Landmark classes (à la HanksWaffles, FourSeasons).

Run from repo root:
    python3 tools/discover_mesh_candidates.py
    python3 tools/discover_mesh_candidates.py --min-lms 5 --top 40
    python3 tools/discover_mesh_candidates.py --prefix "Portofino"  # deep-dive one group

Critères évalués par groupe:
  - Count LMs (et combien ont xyz)
  - Cam coverage: nb cams uniques qui voient ≥1 LM, top-5 cams
  - XY footprint diameter (max pairwise XY distance, en mètres)
  - Z range (max - min)
  - Median per-LM observers (signal de redondance)

Score "rigidity" simple:
  - footprint <150m + z_range >5m + median_obs ≥2  → bon candidat compact
  - footprint >300m → probablement quartier/zone, pas un "building"
"""

import sys
import os
import re
import argparse
import math
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
sys.path.insert(0, ".")

import gtamapdata as md


PREFIX_RE = re.compile(r'^([A-Z][^()]+?)(?:\s*\()')


def extract_prefix(name):
    m = PREFIX_RE.match(name)
    if m:
        return m.group(1).strip()
    # fallback: first 2 words if no paren
    parts = name.split()
    if len(parts) >= 2:
        return " ".join(parts[:2])
    return name


def pairwise_max_xy(points):
    """Brute-force max pairwise XY distance. OK pour <500 points."""
    if len(points) < 2:
        return 0.0
    mx = 0.0
    for i in range(len(points)):
        xi, yi = points[i][0], points[i][1]
        for j in range(i + 1, len(points)):
            dx = points[j][0] - xi
            dy = points[j][1] - yi
            d = dx * dx + dy * dy
            if d > mx:
                mx = d
    return math.sqrt(mx)


def median(vals):
    if not vals:
        return 0
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def analyze_group(prefix, lm_names, pixels_by_cam):
    """Compute stats for one group."""
    has_xyz = []
    no_xyz = []
    xyzs = []
    for name in lm_names:
        lm = md.landmarks.get(name)
        # md.landmarks[name] is directly an (x,y,z) tuple, not a dict
        if lm is not None and len(lm) >= 3:
            has_xyz.append(name)
            xyzs.append(lm)
        else:
            no_xyz.append(name)

    # Cam coverage: which cams have ≥1 of these LMs in their pixels
    cam_hits = Counter()
    per_lm_obs = []
    lm_set = set(lm_names)
    for cam_name, lm_pix in pixels_by_cam.items():
        seen = lm_set & set(lm_pix.keys())
        if seen:
            cam_hits[cam_name] = len(seen)
    # per-LM observer count
    lm_obs_count = Counter()
    for cam_name, lm_pix in pixels_by_cam.items():
        for lm_name in lm_pix.keys():
            if lm_name in lm_set:
                lm_obs_count[lm_name] += 1
    per_lm_obs = list(lm_obs_count.values()) + [0] * (len(lm_names) - len(lm_obs_count))

    # Geometry
    footprint = pairwise_max_xy(xyzs) if len(xyzs) >= 2 else 0.0
    zs = [p[2] for p in xyzs]
    z_range = (max(zs) - min(zs)) if zs else 0.0

    return {
        "prefix": prefix,
        "n_lms": len(lm_names),
        "n_with_xyz": len(has_xyz),
        "n_cams_seeing": len(cam_hits),
        "top_cams": cam_hits.most_common(5),
        "footprint_m": footprint,
        "z_range_m": z_range,
        "median_obs": median(per_lm_obs),
        "max_obs": max(per_lm_obs) if per_lm_obs else 0,
    }


def score(stats):
    """Heuristic score — higher = better candidate."""
    s = 0
    # Compactness: ideal 30-200m
    fp = stats["footprint_m"]
    if 20 <= fp <= 200:
        s += 10
    elif fp < 20:
        s += 3  # might be too small / single point
    elif fp <= 400:
        s += 4
    else:
        s -= 5  # too spread

    # Vertical structure good
    if stats["z_range_m"] >= 5:
        s += 5
    elif stats["z_range_m"] >= 2:
        s += 2

    # Cam coverage
    if stats["n_cams_seeing"] >= 5:
        s += 5
    elif stats["n_cams_seeing"] >= 3:
        s += 3
    elif stats["n_cams_seeing"] >= 2:
        s += 1
    else:
        s -= 3

    # Redundancy
    if stats["median_obs"] >= 3:
        s += 3
    elif stats["median_obs"] >= 2:
        s += 1

    # Has enough calibrated LMs
    coverage_ratio = stats["n_with_xyz"] / max(1, stats["n_lms"])
    if coverage_ratio >= 0.9:
        s += 3
    elif coverage_ratio >= 0.6:
        s += 1
    else:
        s -= 2

    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-lms", type=int, default=5,
                    help="Minimum LMs in group to consider")
    ap.add_argument("--top", type=int, default=30,
                    help="How many top candidates to print")
    ap.add_argument("--prefix", type=str, default=None,
                    help="Deep-dive a specific prefix (lists all LMs + cams)")
    ap.add_argument("--exclude-known", action="store_true",
                    help="Skip prefixes already implemented as classes")
    args = ap.parse_args()

    KNOWN = {"Portofino Tower", "Four Seasons", "Sunshine Skyway", "HanksWaffles"}

    # Group all landmarks by prefix
    groups = defaultdict(list)
    for name in md.landmarks.keys():
        p = extract_prefix(name)
        groups[p].append(name)

    # Build pixels lookup once
    pixels_by_cam = md.pixels  # {cam_name: {lm_name: [px,py]}}

    if args.prefix:
        # Deep-dive mode
        matches = [p for p in groups.keys() if args.prefix.lower() in p.lower()]
        if not matches:
            print(f"No prefix matching '{args.prefix}'. Try one of:")
            close = [p for p in groups.keys()
                     if any(w in p.lower() for w in args.prefix.lower().split())]
            for p in close[:15]:
                print(f"  {p}  ({len(groups[p])} LMs)")
            return
        for p in matches:
            stats = analyze_group(p, groups[p], pixels_by_cam)
            print(f"\n=== {p} ({stats['n_lms']} LMs, {stats['n_with_xyz']} with xyz) ===")
            print(f"  Footprint diameter: {stats['footprint_m']:.1f} m")
            print(f"  Z range: {stats['z_range_m']:.1f} m")
            print(f"  Cams seeing this group: {stats['n_cams_seeing']}")
            print(f"  Median obs per LM: {stats['median_obs']}")
            print(f"  Top cams:")
            for cam, n in stats["top_cams"]:
                print(f"    {n:3} LMs ← {cam}")
            print(f"  LMs ({len(groups[p])}):")
            for name in sorted(groups[p]):
                xyz = md.landmarks.get(name)
                if xyz is not None and len(xyz) >= 3:
                    xyz_s = f"[{xyz[0]:8.1f}, {xyz[1]:8.1f}, {xyz[2]:6.1f}]"
                else:
                    xyz_s = "  (no xyz)"
                n_obs = sum(1 for cn, lp in pixels_by_cam.items() if name in lp)
                print(f"    {xyz_s}  obs={n_obs:2}  {name}")
        return

    # Rank mode
    results = []
    for prefix, lm_names in groups.items():
        if len(lm_names) < args.min_lms:
            continue
        if args.exclude_known and any(k in prefix for k in KNOWN):
            continue
        stats = analyze_group(prefix, lm_names, pixels_by_cam)
        stats["score"] = score(stats)
        results.append(stats)

    results.sort(key=lambda s: (-s["score"], -s["n_cams_seeing"]))

    print(f"{'Score':>5} {'#LMs':>5} {'xyz%':>5} {'#Cams':>6} {'fpDiam':>7} {'zRng':>6} {'medObs':>7}  Prefix")
    print("-" * 95)
    for s in results[:args.top]:
        cov = s["n_with_xyz"] / max(1, s["n_lms"]) * 100
        print(f"{s['score']:>5} {s['n_lms']:>5} {cov:>4.0f}% {s['n_cams_seeing']:>6} "
              f"{s['footprint_m']:>6.0f}m {s['z_range_m']:>5.0f}m {s['median_obs']:>6.1f}  "
              f"{s['prefix']}")

    print(f"\n{len(results)} groups total with ≥{args.min_lms} LMs. "
          f"Showing top {min(args.top, len(results))}.")
    print(f"\nNext: python3 tools/discover_mesh_candidates.py --prefix \"<NAME>\"  "
          f"to deep-dive.")


if __name__ == "__main__":
    main()
