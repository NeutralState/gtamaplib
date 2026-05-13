#!/usr/bin/env python3
"""find_outlier_pixels.py — List pixels with angular err > threshold that have
at least 1 other camera observing the same landmark cleanly (err < 10').

These are safe candidates to delete — the landmark is still constrained by
the clean observers.
"""
import os, sys, math, json
GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]
import gtamaplib as ml
import gtamapdata as md

THRESHOLD = 15.0
CLEAN_THRESHOLD = 10.0

def angular_err(cam, pixel, lm_xyz):
    proj = cam.get_pixel(lm_xyz)
    if proj is None: return None
    dx = (proj[0] - pixel[0]) * cam.hfov / cam.w * 60
    dy = (proj[1] - pixel[1]) * cam.vfov / cam.h * 60
    return math.hypot(dx, dy)

# Cache cams
cams = {}
for cn in md.cameras:
    if not md.cameras[cn].get('xyz'): continue
    try:
        cams[cn] = ml.get_camera(cn)
    except:
        pass

# Compute all errors
all_errs = {}  # (cn, lm) -> err
for cn, cam in cams.items():
    if cn not in md.pixels: continue
    for lm_name, pixel in md.pixels[cn].items():
        if lm_name not in md.landmarks: continue
        try:
            err = angular_err(cam, pixel, md.landmarks[lm_name])
            if err is not None:
                all_errs[(cn, lm_name)] = err
        except:
            pass

# Find outliers with clean observers
problematic = []
for (cn, lm_name), err in all_errs.items():
    if err <= THRESHOLD: continue
    # Check other observers
    clean_observers = 0
    for (cn2, lm2), err2 in all_errs.items():
        if cn2 == cn or lm2 != lm_name: continue
        if err2 < CLEAN_THRESHOLD:
            clean_observers += 1
    if clean_observers >= 1:
        problematic.append((err, cn, lm_name, clean_observers))

problematic.sort(reverse=True)
print(f"Found {len(problematic)} outlier pixels (err >{THRESHOLD}) with >=1 clean observer (err <{CLEAN_THRESHOLD})")
print()
print(f"  {'err':>6}  {'camera':<32}  {'landmark':<35}  {'clean obs':>9}")
print("-" * 95)
for err, cn, lm, n_clean in problematic:
    print(f"  {err:>5.1f}'  {cn[:32]:<32}  {lm[:35]:<35}  {n_clean:>9}")

# Also save to JSON for easy delete
with open('/tmp/outlier_pixels.json', 'w') as f:
    json.dump([{'err': e, 'cam': c, 'lm': l, 'clean_obs': n}
               for e, c, l, n in problematic], f, indent=2)
print(f"\nSaved to /tmp/outlier_pixels.json — to delete all, run:")
print(f"  python3 tools/delete_outlier_pixels.py")
