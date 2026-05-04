#!/usr/bin/env python3
"""
diagnose_camera.py — Show every observation made by a given camera, ranked by
error, with the projected pixel position vs the marked pixel.

If the errors all point in the SAME DIRECTION (e.g. all 200px to the right),
the camera's yaw or pitch is off by a constant amount → quick fix.
If errors are random, the issue is more likely in the pixels themselves.

Usage:
    python3 tools/diagnose_camera.py "Ambrosia 04 (Fires)"
    python3 tools/diagnose_camera.py "Diner (W) (B)"

Or run with no args to scan all suspect cams from a hardcoded list:
    python3 tools/diagnose_camera.py
"""

import os
import sys
from collections import defaultdict

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib as ml
import gtamapdata as md

SUSPECT_CAMS = [
    "Ambrosia 04 (Fires)",
    "Diner (W) (B)",
    "U-Turn (NW)",
    "U-Turn (NE)",
    "Gas Station (Jason)",
]

# ── Pre-compute consensus position for each landmark ──────────────────────────
# For each landmark, find which cams "agree" on it (sub-5 arcmin error against
# the current xyz). The consensus cams give us a confidence baseline.

lm_consensus = {}  # lm_name -> {n_agreeing, agreeing_cams, total_obs}

for lm_name in md.landmarks:
    lm_xyz = md.landmarks[lm_name]
    if lm_xyz is None:
        continue
    agreeing = []
    total = 0
    for cam_name, cam_pixels in md.pixels.items():
        if lm_name not in cam_pixels:
            continue
        cam_data = md.cameras.get(cam_name, {})
        if not cam_data.get('xyz'):
            continue
        total += 1
        try:
            cam = ml.get_camera(cam_name)
            proj = cam.get_pixel(lm_xyz)
            if proj is None:
                continue
            px, py = cam_pixels[lm_name]
            dx = (float(proj[0]) - float(px)) * cam.hfov / cam.w * 60.0
            dy = (float(proj[1]) - float(py)) * cam.vfov / cam.h * 60.0
            err = (dx*dx + dy*dy) ** 0.5
            if err < 5.0:
                agreeing.append(cam_name)
        except Exception:
            continue
    lm_consensus[lm_name] = {
        'n_agreeing': len(agreeing),
        'agreeing_cams': agreeing,
        'total': total,
    }

# ── Diagnose one camera ───────────────────────────────────────────────────────

def diagnose(cam_name):
    print()
    print("═" * 100)
    print(f"  {cam_name}")
    print("═" * 100)

    cam_data = md.cameras.get(cam_name)
    if not cam_data:
        print("  Not found in cameras.json")
        return
    if not cam_data.get('xyz'):
        print("  No xyz set")
        return

    print(f"  xyz  = {cam_data['xyz']}")
    print(f"  ypr  = {cam_data['ypr']}")
    print(f"  fov  = {cam_data['fov']}")
    print(f"  src  = {cam_data.get('source')}")

    cam = ml.get_camera(cam_name)
    cam_pixels = md.pixels.get(cam_name, {})

    rows = []
    for lm_name, pixel in cam_pixels.items():
        lm_xyz = md.landmarks.get(lm_name)
        if lm_xyz is None:
            continue
        try:
            proj = cam.get_pixel(lm_xyz)
            if proj is None:
                continue
            px_marked = float(pixel[0])
            py_marked = float(pixel[1])
            px_proj   = float(proj[0])
            py_proj   = float(proj[1])
            dpx = px_proj - px_marked  # in pixels
            dpy = py_proj - py_marked
            dx_arc = dpx * cam.hfov / cam.w * 60.0
            dy_arc = dpy * cam.vfov / cam.h * 60.0
            err    = (dx_arc**2 + dy_arc**2) ** 0.5

            cons = lm_consensus.get(lm_name, {})
            n_agree = cons.get('n_agreeing', 0)
            other_agree = n_agree - (1 if cam_name in cons.get('agreeing_cams', []) else 0)
            rows.append({
                'lm': lm_name, 'err': err,
                'dpx': dpx, 'dpy': dpy,
                'px_marked': px_marked, 'py_marked': py_marked,
                'px_proj': px_proj, 'py_proj': py_proj,
                'other_agree': other_agree,
                'total_obs': cons.get('total', 1),
            })
        except Exception:
            continue

    rows.sort(key=lambda r: r['err'], reverse=True)

    print()
    print(f"  {'lm':<40}  {'err':>7}  {'Δpx':>7}  {'Δpy':>7}  {'consensus':>10}")
    print(f"  {'-'*40}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*10}")
    for r in rows[:25]:
        cons_str = f"{r['other_agree']}/{r['total_obs']-1} agree" if r['total_obs'] > 1 else 'isolated'
        name = r['lm'] if len(r['lm']) <= 40 else r['lm'][:37] + '...'
        print(f"  {name:<40}  {r['err']:>6.1f}'  {r['dpx']:>+7.0f}  {r['dpy']:>+7.0f}  {cons_str:>10}")

    if len(rows) > 25:
        print(f"  ... and {len(rows)-25} more")

    # ── Summary stats ────────────────────────────────────────────────────────
    if rows:
        # Global pattern: are dpx/dpy systematically biased?
        n = len(rows)
        mean_dpx = sum(r['dpx'] for r in rows) / n
        mean_dpy = sum(r['dpy'] for r in rows) / n
        bad = [r for r in rows if r['err'] > 30]
        bad_with_consensus = [r for r in bad if r['other_agree'] >= 2]

        print()
        print(f"  Total obs           : {n}")
        print(f"  Mean Δpx, Δpy       : {mean_dpx:+.0f}, {mean_dpy:+.0f}  (systematic bias indicator)")
        print(f"  Obs > 30 arcmin     : {len(bad)} ({len(bad)/n*100:.0f}%)")
        print(f"  Bad + others agree  : {len(bad_with_consensus)}  "
              f"← these are the smoking-gun cases (others see the lm fine, only THIS cam disagrees)")

        # Verdict
        if len(bad_with_consensus) >= 5:
            if abs(mean_dpx) > 100 or abs(mean_dpy) > 100:
                print()
                print(f"  VERDICT: Camera ypr is likely OFF.")
                print(f"           Systematic Δ of ({mean_dpx:+.0f}, {mean_dpy:+.0f}) px suggests")
                print(f"           yaw/pitch needs adjustment (not random pixel errors).")
            else:
                print()
                print(f"  VERDICT: Mixed errors. Could be hfov, partial calibration drift,")
                print(f"           or a few bad pixels mixed with cam drift.")

# ── Main ─────────────────────────────────────────────────────────────────────

if len(sys.argv) > 1:
    targets = [sys.argv[1]]
else:
    targets = SUSPECT_CAMS

for cam_name in targets:
    diagnose(cam_name)
