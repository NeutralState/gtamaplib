#!/usr/bin/env python3
"""keys_z_bias_analysis.py — READ-ONLY. Where do the rays say sea level is?

For every LM with z_constraint {"type":"fixed","value":0.0}, re-triangulate
the point FREELY (least-squares closest point to all observer rays, current
cam poses) and report the free z per zone. A coherent per-zone offset means
referential bias; scatter means the markings aren't at the waterline.
"""
import json, math, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import gtamaplib as ml
import gtamapdata as md


def ray_ls_point(rays):
    """Least-squares point minimizing distance to all rays (origin, dir)."""
    A = np.zeros((3, 3)); b = np.zeros(3)
    for o, d in rays:
        d = np.asarray(d, float); d = d / np.linalg.norm(d)
        P = np.eye(3) - np.outer(d, d)
        A += P; b += P @ np.asarray(o, float)
    return np.linalg.solve(A, b)


def main():
    observers = {}
    for c, obs in md.pixels.items():
        for l, px in obs.items():
            if px is not None:
                observers.setdefault(l, []).append(c)

    rows = []
    for lm_name, meta in md.landmarks_meta.items():
        zc = (meta or {}).get("z_constraint")
        if not zc or zc.get("type") != "fixed" or abs(zc.get("value", 1)) > 1e-9:
            continue
        obs_cams = observers.get(lm_name, [])
        rays = []
        for cn in obs_cams:
            if cn not in md.cameras:
                continue
            cam = ml.get_camera(cn)
            st = md.cameras[cn]
            cam.set_xyz(tuple(st["xyz"])); cam.set_ypr(tuple(st["ypr"])); cam.set_fov(tuple(st["fov"]))
            try:
                d = cam.get_pixel_direction(md.pixels[cn][lm_name])
            except Exception:
                continue
            if d is None:
                continue
            rays.append((st["xyz"], d))
        if len(rays) < 2:
            continue
        try:
            p = ray_ls_point(rays)
        except np.linalg.LinAlgError:
            continue
        zone = (meta or {}).get("zone") or "?"
        disk_z = md.landmarks[lm_name][2] if md.landmarks.get(lm_name) is not None else None
        rows.append((zone, lm_name, len(rays), float(p[2]), disk_z))

    byzone = {}
    for zone, name, n, free_z, disk_z in rows:
        byzone.setdefault(zone, []).append((name, n, free_z, disk_z))

    print(f"# {len(rows)} LM contraints z=0 avec >=2 rayons, re-triangules librement\n")
    for zone in sorted(byzone):
        zs = sorted(v[2] for v in byzone[zone])
        med = zs[len(zs)//2]
        q1, q3 = zs[len(zs)//4], zs[3*len(zs)//4]
        print(f"## {zone}: n={len(zs)}  median_free_z={med:+.2f}m  IQR=[{q1:+.2f}, {q3:+.2f}]")
        for name, n, fz, dz in sorted(byzone[zone], key=lambda v: v[2]):
            tag = " <-- VIOLATION DISK" if dz is not None and abs(dz) > 0.5 else ""
            print(f"    {fz:+7.2f}m  (rays={n}, disk_z={dz:+.2f})  {name}{tag}")
        print()


if __name__ == "__main__":
    main()
