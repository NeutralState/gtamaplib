#!/usr/bin/env python3
"""
patch_investigate_lm.py — Updates investigate_landmark.py to also display the
angular error (arcmin) for each camera. Ground-plane projection distance can
be misleading for elevated landmarks seen at low pitch — angular error is
what bundle adjust actually optimizes and should drive decisions.

Run from gtamaplib-main/:
    python3 tools/patch_investigate_lm.py
"""
import os
GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'tools' \
    else os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(GTAMAP_DIR, 'tools', 'investigate_landmark.py')

with open(SCRIPT_PATH) as f:
    content = f.read()

if '# ang err' in content:
    print("• investigate_landmark.py already patched")
else:
    # Replace the table header to include "ang err"
    OLD_HEADER = '''print(f"  {'camera':<28}  {'pixel':<14}  {'ground point at z=0':<30}  {'dist from cur':>12}")
print(f"  {'-'*28}  {'-'*14}  {'-'*30}  {'-'*12}")'''
    NEW_HEADER = '''print(f"  {'camera':<28}  {'pixel':<14}  {'ground point at z=0':<30}  {'dist from cur':>12}  {'ang err':>9}")
print(f"  {'-'*28}  {'-'*14}  {'-'*30}  {'-'*12}  {'-'*9}")'''
    content = content.replace(OLD_HEADER, NEW_HEADER)

    # Update the loop that prints each row to also compute & display angular err
    OLD_LOOP = '''ground_points = []
for cam_name, pixel in cams_with_lm:
    cam = ml.get_camera(cam_name)
    try:
        gp = cam.get_point_at_zero_elevation(pixel)
    except Exception:
        gp = None
    if gp is None:
        # Above horizon: print ray direction instead
        try:
            ray_dir = cam.get_landmark_direction(LM)
            ray_str = f"above horizon, dir=({ray_dir[0]:.2f},{ray_dir[1]:.2f},{ray_dir[2]:.2f})"
        except Exception:
            ray_str = "could not compute ray"
        print(f"  {cam_name[:28]:<28}  {str(pixel):<14}  {ray_str}")
    else:
        gx, gy = gp[0], gp[1]
        dist_from_cur = ((gx - cur_xyz[0])**2 + (gy - cur_xyz[1])**2) ** 0.5
        ground_str = f"({gx:.0f}, {gy:.0f})"
        print(f"  {cam_name[:28]:<28}  {str(pixel):<14}  {ground_str:<30}  {dist_from_cur:>10.0f}m")
        ground_points.append((cam_name, gx, gy))'''

    NEW_LOOP = '''import math as _math
ground_points = []
ang_errs = {}  # cam_name -> arcmin error vs current xyz
for cam_name, pixel in cams_with_lm:
    cam = ml.get_camera(cam_name)
    # Compute angular error: where does the cam project current xyz vs marked pixel?
    ang_err = None
    try:
        proj = cam.get_pixel(cur_xyz)
        if proj is not None:
            dx = (float(proj[0]) - pixel[0]) * cam.hfov / cam.w * 60
            dy = (float(proj[1]) - pixel[1]) * cam.vfov / cam.h * 60
            ang_err = _math.hypot(dx, dy)
    except Exception:
        pass
    ang_errs[cam_name] = ang_err
    ang_str = f"{ang_err:.1f}'" if ang_err is not None else "—"

    try:
        gp = cam.get_point_at_zero_elevation(pixel)
    except Exception:
        gp = None
    if gp is None:
        # Above horizon: print ray direction instead
        try:
            ray_dir = cam.get_landmark_direction(LM)
            ray_str = f"above horizon, dir=({ray_dir[0]:.2f},{ray_dir[1]:.2f},{ray_dir[2]:.2f})"
        except Exception:
            ray_str = "could not compute ray"
        print(f"  {cam_name[:28]:<28}  {str(pixel):<14}  {ray_str:<30}  {'—':>10}    {ang_str:>9}")
    else:
        gx, gy = gp[0], gp[1]
        dist_from_cur = ((gx - cur_xyz[0])**2 + (gy - cur_xyz[1])**2) ** 0.5
        ground_str = f"({gx:.0f}, {gy:.0f})"
        print(f"  {cam_name[:28]:<28}  {str(pixel):<14}  {ground_str:<30}  {dist_from_cur:>10.0f}m  {ang_str:>9}")
        ground_points.append((cam_name, gx, gy))'''

    content = content.replace(OLD_LOOP, NEW_LOOP)

    # Add a new ANGULAR section before the existing VERDICT
    OLD_VERDICT = '''# Compute pairwise distances between ground points to detect divergence
print()
if len(ground_points) >= 2:
    print("Pairwise distances between ground points (z=0 projections):")'''

    NEW_VERDICT = '''# Show angular error summary first — this is the truth, ground gap can mislead
print()
if any(e is not None for e in ang_errs.values()):
    print("Angular error per camera (this is what bundle adjust optimizes):")
    print(f"  {'camera':<28}  {'ang err':>9}  {'verdict'}")
    print(f"  {'-'*28}  {'-'*9}  {'-'*8}")
    real_outliers = []
    for cn, err in sorted(ang_errs.items(), key=lambda kv: -(kv[1] or 0)):
        if err is None:
            verdict = '—'
        elif err > 15:
            verdict = '🔴 outlier'
            real_outliers.append((cn, err))
        elif err > 5:
            verdict = '⚠ suspect'
        else:
            verdict = '✓ ok'
        err_str = f"{err:.1f}'" if err is not None else "—"
        print(f"  {cn[:28]:<28}  {err_str:>9}  {verdict}")
    print()
    if real_outliers:
        print(f"💡 {len(real_outliers)} cam(s) have angular error > 15' — these are the actual bad pixels.")
        print(f"   Ground-plane gaps below may be misleading for elevated landmarks at low pitch.")
        print()

# Compute pairwise distances between ground points to detect divergence
if len(ground_points) >= 2:
    print("Pairwise distances between ground points (z=0 projections):")'''

    content = content.replace(OLD_VERDICT, NEW_VERDICT)

    with open(SCRIPT_PATH, 'w') as f:
        f.write(content)
    print("✓ Patched investigate_landmark.py with angular error column + summary section")

print("\nTest it:")
print("  python3 tools/investigate_landmark.py 'Easy Hill'")
