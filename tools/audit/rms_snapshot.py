#!/usr/bin/env python3
"""rms_snapshot.py — READ-ONLY. Per-cam RMS (arcmin) computed FRESH from disk.

Same arcmin formula as compute_confidence_tiers.py (dx*hfov/w*60, dy*vfov/h*60).
Writes tools/generated/rms_snapshot_<tag>.json for before/after diffing.

Usage: python3 tools/audit/rms_snapshot.py --tag baseline
"""
import argparse, json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import gtamaplib as ml
import gtamapdata as md


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
        cam = ml.get_camera(cam_name)
        if cam is None:
            continue
        residuals = []
        for lm_name, pixel in lm_pixels.items():
            lm_xyz = landmarks.get(lm_name)
            if lm_xyz is None or pixel is None:
                continue
            try:
                proj = cam.get_pixel(lm_xyz)
                if proj is None:
                    continue
                dx = (proj[0] - pixel[0]) * cam.hfov / cam.w * 60
                dy = (proj[1] - pixel[1]) * cam.vfov / cam.h * 60
                residuals.append(math.hypot(dx, dy))
            except Exception:
                continue
        if residuals:
            rms = math.sqrt(sum(r * r for r in residuals) / len(residuals))
            out[cam_name] = {"rms_arcmin": round(rms, 3), "n_obs": len(residuals)}

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
