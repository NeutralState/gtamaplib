#!/usr/bin/env python3
"""rms_snapshot.py — READ-ONLY. Per-cam RMS (arcmin) computed FRESH from disk.

Same arcmin formula as compute_confidence_tiers.py (dx*hfov/w*60, dy*vfov/h*60).
Writes tools/generated/rms_snapshot_<tag>.json for before/after diffing.

Usage: python3 tools/audit/rms_snapshot.py --tag baseline
"""
import argparse, json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import gtamapdata as md
sys.path.insert(0, os.path.join(ROOT, "tools"))
from common import cam_rms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    args = ap.parse_args()

    cameras = md.cameras
    landmarks = md.landmarks          # name -> xyz
    landmarks_meta = md.landmarks_meta
    pixels = md.pixels

    out = {}
    for cam_name, lm_pixels in pixels.items():
        if cam_name not in cameras:
            continue
        rms = cam_rms(cam_name)
        if rms is not None:
            n_obs = sum(1 for l, p in lm_pixels.items()
                        if p is not None and landmarks.get(l) is not None)
            out[cam_name] = {"rms_arcmin": round(rms, 3), "n_obs": n_obs}

    # global + zone rollup (zone inferred from landmarks seen, majority vote)
    lm_zone = {n: (landmarks_meta.get(n) or {}).get("zone") for n in landmarks}
    zone_acc = {}
    for cam_name, lm_pixels in pixels.items():
        if cam_name not in out:
            continue
        zones = [lm_zone.get(l) for l in lm_pixels if lm_zone.get(l)]
        zone = max(set(zones), key=zones.count) if zones else "unknown"
        out[cam_name]["zone"] = zone
        zone_acc.setdefault(zone, []).append(out[cam_name]["rms_arcmin"])

    summary = {
        "n_cams": len(out),
        "global_median_arcmin": round(sorted(v["rms_arcmin"] for v in out.values())[len(out) // 2], 3),
        "global_mean_arcmin": round(sum(v["rms_arcmin"] for v in out.values()) / len(out), 3),
        "zones": {z: {"n": len(v), "median": round(sorted(v)[len(v) // 2], 3)} for z, v in sorted(zone_acc.items())},
    }

    dest = os.path.join(ROOT, "tools", "generated", f"rms_snapshot_{args.tag}.json")
    with open(dest, "w") as f:
        json.dump({"summary": summary, "cams": out}, f, indent=1, sort_keys=True)

    print(f"# rms_snapshot tag={args.tag} | cams={summary['n_cams']} "
          f"median={summary['global_median_arcmin']}' mean={summary['global_mean_arcmin']}'")
    for z, s in summary["zones"].items():
        print(f"  {z:<16} n={s['n']:<4} median={s['median']}'")
    print(f"-> {dest}")


if __name__ == "__main__":
    main()
