#!/usr/bin/env python3
"""
compare_rlx_vs_current.py — Compare camera positions between rlx (Initial commit)
and the current state. Prints a top-10 by xyz movement (in meters), formatted
for a Discord post.

Usage:
    python3 compare_rlx_vs_current.py /tmp/cameras_rlx.json gtamapdata/cameras.json
"""

import json
import math
import re
import sys

if len(sys.argv) < 3:
    print("Usage: python3 compare_rlx_vs_current.py <rlx.json> <current.json>")
    sys.exit(1)

with open(sys.argv[1]) as f:
    rlx = json.load(f)
with open(sys.argv[2]) as f:
    cur = json.load(f)

LEAK_RE = re.compile(r'\d{4}-\d{2}-\d{2}')

def is_ground_truth(cam):
    src = cam.get('source', '') or ''
    return bool(LEAK_RE.match(src)) or src.startswith('Trailer')

def angle_diff(a, b):
    """Smallest signed difference between two angles (degrees), wrap-aware."""
    if a is None or b is None: return 0.0
    d = (b - a + 180) % 360 - 180
    return d

rows = []
for name, c_new in cur.items():
    if name not in rlx: continue
    c_old = rlx[name]
    if is_ground_truth(c_new): continue  # only compare optimizable cams

    xyz_old = c_old.get('xyz') or [0, 0, 0]
    xyz_new = c_new.get('xyz') or [0, 0, 0]
    ypr_old = c_old.get('ypr') or [0, 0, 0]
    ypr_new = c_new.get('ypr') or [0, 0, 0]
    fov_old = (c_old.get('fov') or [None, None])[0]
    fov_new = (c_new.get('fov') or [None, None])[0]

    dx = xyz_new[0] - xyz_old[0]
    dy = xyz_new[1] - xyz_old[1]
    dz = xyz_new[2] - xyz_old[2]
    dist = math.sqrt(dx*dx + dy*dy + dz*dz)

    dyaw   = angle_diff(ypr_old[0], ypr_new[0])
    dpitch = angle_diff(ypr_old[1], ypr_new[1])
    dhfov  = (fov_new - fov_old) if (fov_old and fov_new) else None

    rows.append({
        'name': name,
        'dist': dist,
        'dx': dx, 'dy': dy, 'dz': dz,
        'dyaw': dyaw, 'dpitch': dpitch, 'dhfov': dhfov,
        'xyz_old': xyz_old, 'xyz_new': xyz_new,
    })

rows.sort(key=lambda r: r['dist'], reverse=True)

# ── Discord output ───────────────────────────────────────────────────────────
print("```")
print(f"{'camera':<32}  {'Δxyz':>8}  {'Δyaw':>7}  {'Δpitch':>7}  {'Δhfov':>7}")
print("─" * 70)
for r in rows[:15]:
    hfov_str = f"{r['dhfov']:+.2f}°" if r['dhfov'] is not None else "  —  "
    print(f"{r['name'][:32]:<32}  {r['dist']:>6.0f}m  "
          f"{r['dyaw']:>+6.2f}°  {r['dpitch']:>+6.2f}°  {hfov_str:>7}")
print("```")

# ── Summary stats ────────────────────────────────────────────────────────────
print()
print(f"Total optimizable cams compared: {len(rows)}")
print(f"  moved > 100m : {sum(1 for r in rows if r['dist'] > 100)}")
print(f"  moved > 50m  : {sum(1 for r in rows if r['dist'] > 50)}")
print(f"  moved > 10m  : {sum(1 for r in rows if r['dist'] > 10)}")
print(f"  median move  : {sorted(r['dist'] for r in rows)[len(rows)//2]:.1f}m")
