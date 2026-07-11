#!/usr/bin/env python3
"""Patch collision_scan V1 -> V2: classification metrique en metres transverses.
Decouverte 2026-07-06: l'erreur angulaire explose mecaniquement a courte portee
(cam de rue a 15-20m: 0.9m lateral = 188'). Verification port_gellhorn: ecart
median xyz-AIWE vs rayons cams vivantes = 0.1m -> 9 des 20 WAR etaient des
artefacts. V2: outlier = ang>15' ET gap>3m; sain = ang<=8' OU gap<=1m."""
import sys
p = 'tools/audit/collision_scan.py'
src = open(p).read()
if 'GAP_OK' in src:
    print('ok  deja en V2')
    sys.exit(0)

src = src.replace("import argparse, json, math, os, subprocess, sys",
                  "import argparse, json, math, os, subprocess, sys\nimport numpy as np")
src = src.replace("T_OK = 8.0        # arcmin: en dessous = majorite saine",
                  "T_OK = 8.0        # arcmin: en dessous = majorite saine\n"
                  "GAP_OK = 1.0      # m: sous ce gap transverse, observer SAIN peu importe l'angulaire\n"
                  "GAP_BAD = 3.0     # m: outlier requiert ang>T_BAD ET gap>GAP_BAD (anti fausses guerres)")

old_fn = """def ang_err(cam, mk, xyz):
    p = cam.get_pixel(xyz)
    if p is None:
        return None
    dx = (p[0] - mk[0]) * cam.hfov / cam.w * 60
    dy = (p[1] - mk[1]) * cam.vfov / cam.h * 60
    return math.hypot(dx, dy)"""
new_fn = """def ang_err(cam, mk, xyz):
    p = cam.get_pixel(xyz)
    if p is None:
        return None, None
    dx = (p[0] - mk[0]) * cam.hfov / cam.w * 60
    dy = (p[1] - mk[1]) * cam.vfov / cam.h * 60
    ang = math.hypot(dx, dy)
    try:
        o = np.asarray(cam.xyz, float)
        d = np.asarray(cam.get_pixel_direction(mk), float)
        d = d / np.linalg.norm(d)
        v = np.asarray(xyz, float) - o
        t = float(np.dot(v, d))
        gap = float(np.linalg.norm(v - max(t, 0.0) * d))
    except Exception:
        gap = None
    return ang, gap"""
assert old_fn in src, 'fonction ang_err introuvable'
src = src.replace(old_fn, new_fn)

old_loop = """            e = ang_err(cam, mk, xyz)
            if e is not None:
                errs.append((cam_name, mk, e))
        if len(errs) < 2:
            continue
        majority = [t for t in errs if t[2] <= T_OK]
        outliers = [t for t in errs if t[2] > T_BAD]"""
new_loop = """            e, gap = ang_err(cam, mk, xyz)
            if e is not None:
                errs.append((cam_name, mk, e, gap))
        if len(errs) < 2:
            continue
        majority = [t for t in errs if t[2] <= T_OK or (t[3] is not None and t[3] <= GAP_OK)]
        outliers = [t for t in errs if t[2] > T_BAD and (t[3] is None or t[3] > GAP_BAD)]"""
assert old_loop in src, 'boucle errs introuvable'
src = src.replace(old_loop, new_loop)

src = src.replace("for i, (ca, ma, ea) in enumerate(outliers):",
                  "for i, (ca, ma, ea, _ga) in enumerate(outliers):")
src = src.replace("cb, mb, eb = outliers[j]", "cb, mb, eb, _gb = outliers[j]")
src = src.replace("'worst': max(e for _, _, e in errs),",
                  "'worst': max(e for _, _, e, _g in errs),\n"
                  "            'worst_m': max((g for _, _, _e, g in errs if g is not None), default=None),")
src = src.replace("'excl': [c for c, _, e in errs if e > T_BAD],",
                  "'excl': [c for c, _, e, g in errs if e > T_BAD and (g is None or g > GAP_BAD)],")
src = src.replace('''f"obs={f['n_obs']:2d} maj={f['n_major']:2d} worst={f['worst']:7.1f}'  {'; '.join(tags)}")''',
                  '''f"obs={f['n_obs']:2d} maj={f['n_major']:2d} worst={f['worst']:7.1f}'/" + (f"{f['worst_m']:.1f}m" if f['worst_m'] is not None else "?m") + f"  {'; '.join(tags)}")''')
open(p, 'w').write(src)
print('collision_scan patche en V2 (metrique metres)')
