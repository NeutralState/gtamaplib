#!/usr/bin/env python3
"""list_extra_observers.py — Finds landmarks that have observers (cams
avec pixels) au-delà de leurs source_cameras declarees. Ces extras sont les
candidats a investiguer:
- Soit name collision (delete pixel divergent)
- Soit drift xyz a fix par retriangulate
"""
import os, sys
GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamapdata as md
import gtamaplib as ml
import math

# Build cam ground projection helper
def project_to_ground(cam_name, pixel, z=0):
    """Project pixel to z=0 plane. Returns (gx, gy) or None."""
    if cam_name not in md.cameras: return None
    if not md.cameras[cam_name].get('xyz'): return None
    try:
        cam = ml.get_camera(cam_name)
        # Use direction from get_pixel_direction
        d = cam.get_pixel_direction(pixel)
        if d is None: return None
        ox, oy, oz = cam.xyz
        dx, dy, dz = d
        if abs(dz) < 1e-6: return None
        t = (z - oz) / dz
        if t < 0: return None  # ray points away from ground
        return (ox + t*dx, oy + t*dy)
    except Exception:
        return None

candidates = []
for lm_name, meta in md.landmarks_meta.items():
    if md.landmarks.get(lm_name) is None:
        continue
    sources = set(meta.get('source_cameras') or [])
    observers = set(cn for cn, pxs in md.pixels.items() if lm_name in pxs)
    extras = observers - sources
    if not extras:
        continue
    if len(sources) > 3:
        continue  # too many sources, probably already triangulated well

    lm_xyz = md.landmarks[lm_name]
    # Pour chaque extra observer, distance entre son ground projection et le xyz du LM
    extra_info = []
    for cn in extras:
        pixel = md.pixels[cn][lm_name]
        gp = project_to_ground(cn, pixel)
        if gp is None:
            extra_info.append((cn, None))
            continue
        d = math.hypot(gp[0] - lm_xyz[0], gp[1] - lm_xyz[1])
        extra_info.append((cn, d))
    
    max_d = max((d for _, d in extra_info if d is not None), default=0)
    candidates.append((lm_name, list(sources), extra_info, max_d))

# Sort by max distance descending
candidates.sort(key=lambda x: -x[3])

print(f"{len(candidates)} landmarks with extra observers")
print()
print(f"{'#':>4}  {'landmark':<40}  {'max_dist':>9}  sources -> extras")
print("-" * 100)
for i, (lm, srcs, extras, max_d) in enumerate(candidates[:50]):
    extra_str = ', '.join(f"{cn}({d:.0f}m)" if d is not None else f"{cn}(?)" for cn, d in extras)
    src_str = ', '.join(srcs) if srcs else '-'
    print(f"{i+1:>4}  {lm[:40]:<40}  {max_d:>7.0f}m  {src_str} -> {extra_str[:50]}")
