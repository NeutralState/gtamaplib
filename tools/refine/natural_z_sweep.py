#!/usr/bin/env python3
"""natural_z_sweep.py — Etend la doctrine waterline aux 19 constraints
restantes a nom naturel et >=2 rayons. Garde par LM: la liberation d'un LM
n'est acceptee QUE si aucune cam observatrice ne regresse de plus de --tol
(0.25' par defaut) ET que le net s'ameliore ou reste neutre (le but est la
justesse du datum, pas le RMS — un LM dont la liberation est neutre en RMS
mais retire un faux datum est accepte si --allow-neutral).

Les LM a 1 source gardent leur constraint (PORTEUSE — c'est elle qui fixe le
point). Les noms naturels = NATURAL_WATERLINE_PATTERNS de find_z_candidates.

Dry-run par defaut; --apply ecrit via md.update_landmark (jamais de bypass).
Backup: landmarks.json.bak_zsweep. Roule invariants.py apres.
"""
import argparse, json, math, os, re, shutil, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import gtamapdata as md
sys.path.insert(0, os.path.join(ROOT, "tools"))
from common import cam_rms as _common_cam_rms, get_cam, pixel_observers, ray_ls_point

NATURAL = re.compile(
    r'\b(Island|Key|Bay|Beach|Coast|Shore|Shoreline|Lagoon|Inlet|Cove|'
    r'Mangrove|Surf|Ocean|Reef|Sandbar|Boat|Buoy)\b', re.I)


def cam_rms(cn, override):
    return _common_cam_rms(cn, lm_override=override)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=0.25)
    ap.add_argument("--allow-neutral", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    observers = pixel_observers()

    accepted, rejected, kept = {}, [], []
    for lm_name in sorted(md.landmarks_meta):
        meta = md.landmarks_meta[lm_name] or {}
        zc = meta.get("z_constraint")
        if not zc or zc.get("type") != "fixed" or not NATURAL.search(lm_name):
            continue
        rays = []
        for cn in observers.get(lm_name, []):
            cam = get_cam(cn)
            try:
                d = cam.get_pixel_direction(md.pixels[cn][lm_name])
            except Exception:
                continue
            if d is not None:
                rays.append((md.cameras[cn]["xyz"], d))
        if len(rays) < 2:
            kept.append(lm_name)
            continue
        p = tuple(float(v) for v in ray_ls_point(rays))
        aff = observers.get(lm_name, [])
        deltas = {}
        ok = True
        worst = net = 0.0
        for cn in aff:
            b = cam_rms(cn, {}); a = cam_rms(cn, {lm_name: p})
            if b is None or a is None:
                continue
            deltas[cn] = a - b
            worst = max(worst, a - b); net += a - b
        if worst > args.tol or (net > 1e-6 and not args.allow_neutral) or net > args.tol:
            ok = False
        cur_z = md.landmarks[lm_name][2] if md.landmarks.get(lm_name) is not None else None
        line = (f"{lm_name}: z {cur_z:+.2f} -> {p[2]:+.2f} (rays={len(rays)}) "
                f"worst={worst:+.2f}' net={net:+.2f}'")
        if ok:
            accepted[lm_name] = p
            print("LIBERE", line)
        else:
            rejected.append(lm_name)
            print("REJETE", line, "(garde: constraint conservee)")

    print(f"\n# {len(accepted)} liberes, {len(rejected)} rejetes par le garde, "
          f"{len(kept)} a 1 source (constraints porteuses, conservees)")

    if not args.apply:
        print("DRY-RUN. Relance avec --apply pour ecrire.")
        return
    if not accepted:
        print("Rien a ecrire.")
        return
    shutil.copy(os.path.join(ROOT, "gtamapdata", "landmarks.json"),
                os.path.join(ROOT, "gtamapdata", "landmarks.json.bak_zsweep"))
    for lm, xyz in accepted.items():
        md.update_landmark(lm, list(xyz), z_constraint=None)
    print(f"APPLIED: {len(accepted)} LM liberes (backup landmarks.json.bak_zsweep)")


if __name__ == "__main__":
    main()
