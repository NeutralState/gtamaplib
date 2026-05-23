#!/usr/bin/env python3
"""
compute_venetian_xyz.py — Calcule les xyz des LMs 1000 Venetian Way qui sont
markés sur le cam 'Venetian Islands' mais pas encore triangulés.

Strategy: ray-plane intersection
  - Each marked pixel defines a ray from the camera through that pixel
  - The z coordinate is known (from floor counting × 2.95m/floor)
  - Intersect ray with horizontal plane at z = z_known → get (x, y, z_known)

Usage:
    python3 tools/compute_venetian_xyz.py            # dry-run, print propositions
    python3 tools/compute_venetian_xyz.py --apply    # write to landmarks.json
"""

import sys
import os
import argparse
import json
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
sys.path.insert(0, ".")

import gtamapdata as md
import gtamaplib as ml


# Floor height calibrated from triangulated LMs:
# (SE)/(SW) at z=65 = top of main roof = 22 floors → 65/22 ≈ 2.95 m/floor
FLOOR_HEIGHT = 65.0 / 22.0  # ≈ 2.954 m

# LMs to compute via ray-plane intersection from Venetian Islands cam.
# Only LMs where the ray clearly descends to the target z plane are reliable.
# Top-of-building LMs (NW, T-NW, T-SW, W-Box-NW) are skipped here — the
# OneThousandVenetian class infers them from geometry instead.
# Format: lm_name -> floor_count (0 = ground, 22 = main roof)
LM_FLOOR_MAP = {
    # Podium corners at ground level (rays descend steeply, accurate)
    "1000 Venetian Way (B-NW)": 0,
    "1000 Venetian Way (B-SW)": 0,
    # West-facing pyramid palier corners (rays descend, accurate)
    "1000 Venetian Way (W1)": 3,
    "1000 Venetian Way (W2)": 7,
    "1000 Venetian Way (W3)": 11,
    "1000 Venetian Way (W4)": 15,
}

ANCHOR_CAM = "Venetian Islands"


def ray_plane_intersect(cam, pixel_xy, z_target):
    """
    Cast a ray from cam through pixel_xy and intersect with the horizontal
    plane z = z_target. Returns (x, y, z_target) or None if ray is parallel.
    """
    # Get ray origin (cam position) and direction (towards pixel)
    cam_xyz = cam.xyz
    # get_pixel_direction returns a unit direction vector from cam through that pixel
    ray_dir = cam.get_pixel_direction(pixel_xy)
    # Intersect with plane z = z_target
    # cam_xyz[2] + t * ray_dir[2] = z_target
    if abs(ray_dir[2]) < 1e-9:
        return None  # Ray parallel to plane
    t = (z_target - cam_xyz[2]) / ray_dir[2]
    if t <= 0:
        return None  # Plane is behind the camera
    x = cam_xyz[0] + t * ray_dir[0]
    y = cam_xyz[1] + t * ray_dir[1]
    return (x, y, z_target)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Actually write computed xyz to landmarks.json")
    ap.add_argument("--cam", default=ANCHOR_CAM,
                    help=f"Anchor cam (default: {ANCHOR_CAM})")
    args = ap.parse_args()

    cam = ml.get_camera(args.cam)
    if cam is None:
        print(f"ERROR: cam '{args.cam}' not found")
        return 1

    print(f"Anchor cam: {args.cam}")
    print(f"  pos: ({cam.xyz[0]:.1f}, {cam.xyz[1]:.1f}, {cam.xyz[2]:.1f})")
    print(f"Floor height: {FLOOR_HEIGHT:.3f} m")
    print()
    print(f"{'LM name':<35} {'floor':>6} {'z':>7}  {'computed (x, y, z)':<35}  status")
    print("-" * 110)

    pixels_for_cam = md.pixels.get(args.cam, {})
    proposals = {}  # lm_name -> (x, y, z)
    
    for lm_name, floor in LM_FLOOR_MAP.items():
        if lm_name not in pixels_for_cam:
            print(f"{lm_name:<35} {floor:>6}        ----  NOT MARKED on {args.cam}")
            continue
        pixel = pixels_for_cam[lm_name]
        z_target = floor * FLOOR_HEIGHT
        xyz = ray_plane_intersect(cam, pixel, z_target)
        if xyz is None:
            print(f"{lm_name:<35} {floor:>6} {z_target:>6.1f}   "
                  f"<ray parallel to plane>")
            continue
        existing = md.landmarks.get(lm_name)
        if existing is not None and len(existing) >= 3:
            dx = xyz[0] - existing[0]
            dy = xyz[1] - existing[1]
            dz = xyz[2] - existing[2]
            status = f"existing diff: dx={dx:+.1f}, dy={dy:+.1f}, dz={dz:+.1f}"
        else:
            status = "new"
        print(f"{lm_name:<35} {floor:>6} {z_target:>6.1f}   "
              f"({xyz[0]:7.1f}, {xyz[1]:7.1f}, {xyz[2]:5.1f})  {status}")
        proposals[lm_name] = xyz

    print()
    print(f"{len(proposals)} LMs computed.")

    # Sanity check: ratio of building width vs height
    if "1000 Venetian Way (B-NW)" in proposals and "1000 Venetian Way (B-SW)" in proposals:
        b_nw = proposals["1000 Venetian Way (B-NW)"]
        b_sw = proposals["1000 Venetian Way (B-SW)"]
        ground_width = math.hypot(b_sw[0] - b_nw[0], b_sw[1] - b_nw[1])
        print(f"\nSanity: podium B-NW <-> B-SW distance: {ground_width:.1f} m")
        print(f"        (real building footprint should be ~50-80m)")

    if "1000 Venetian Way (NW)" in proposals:
        nw = proposals["1000 Venetian Way (NW)"]
        # Compare with existing (SE) and (SW)
        se = md.landmarks.get("1000 Venetian Way (SE)")
        sw = md.landmarks.get("1000 Venetian Way (SW)")
        if se and sw:
            roof_width = math.hypot(se[0] - sw[0], se[1] - sw[1])
            nw_to_sw = math.hypot(nw[0] - sw[0], nw[1] - sw[1])
            print(f"\nSanity: main roof SE<->SW (triangulated): {roof_width:.1f} m")
            print(f"        main roof NW<->SW (computed vs trian.): {nw_to_sw:.1f} m")
            print(f"        (should be similar if NW is at correct depth)")

    if args.apply:
        # Write to landmarks.json
        lms_path = "gtamapdata/landmarks.json"
        with open(lms_path) as f:
            data = json.load(f)
        lms = data.get("landmarks", data)  # support both schemas

        updated = 0
        for lm_name, xyz in proposals.items():
            entry = lms.get(lm_name, {})
            if not isinstance(entry, dict):
                entry = {}
            entry["xyz"] = [round(xyz[0], 1), round(xyz[1], 1), round(xyz[2], 1)]
            # Preserve other keys if present (source_cameras, error_m, zone)
            entry.setdefault("source_cameras", [])
            entry.setdefault("error_m", None)
            entry.setdefault("zone", "unknown")
            lms[lm_name] = entry
            updated += 1

        with open(lms_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nWrote {updated} xyz to {lms_path}")
        print("Don't forget to: ml.get_camera.cache_clear() if reusing in same session")
    else:
        print("\n(dry-run; use --apply to write to landmarks.json)")


if __name__ == "__main__":
    sys.exit(main() or 0)
