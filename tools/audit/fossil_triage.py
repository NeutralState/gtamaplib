#!/usr/bin/env python3
# fossil_triage.py -- diagnostic des fossiles (LM rejetes par leur source).
# [PROVENANCE-V2 tranche 2, 2026-07-08]
#
# Le fossil-scan du CI compte; ce tool explique POURQUOI et QUOI FAIRE.
# Classifications:
#   DEGENERATE_POSE  source a z quasi-nul (ray-z impossible, no-proj probable);
#                    le xyz existant est peut-etre bon, c'est la POSE a reparer
#                    (decouverte 0708: Beach z=-0.003m, map-proof valide x,y
#                    PAS z -> session pose dediee + re-validation map)
#   WAR_PENDING      le LM est une guerre connue (outlier dual) -> crop UI
#   BLOCKED_ON_POSE  source a sigma pose > 30m -> bloque sur la reparation de
#                    la pose (ex: famille Ambrosia 02)
#   SUB_WAR          multi-observers en desaccord sous le seuil WAR -> crop
#                    eventuel, le harvest les tient en review (all-obs guard)
#   RESEEDABLE       mono-source saine + z_constraint + ray-z non degenere ->
#                    re-seed possible (aucun cas actuel; le code le detectera)
#
# READ-ONLY. Usage: PYTHONPATH=. python3 tools/audit/fossil_triage.py
import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from common import find_fossils, cam_sigma_pos, get_cam, residual_dual, is_excluded_marking
import gtamapdata as md


def main():
    fossils = find_fossils()
    lms = json.load(open('gtamapdata/landmarks.json'))
    print(f'FOSSIL-TRIAGE — {len(fossils)} fossile(s)\n')
    counts = {}
    for f in fossils:
        lm, src = f['lm'], f['source']
        e = lms.get(lm) or {}
        xyz = e.get('xyz')
        zc = bool(e.get('z_constraint'))
        sig = cam_sigma_pos(src)
        cam_z = md.cameras.get(src, {}).get('xyz', [0, 0, 99])
        cam_z = cam_z[2] if isinstance(cam_z, (list, tuple)) else 99
        observers = [c for c in md.pixels if lm in md.pixels[c]
                     and not is_excluded_marking(c, lm)]
        is_war = False
        for c in observers:
            cam = get_cam(c)
            if cam is None or md.pixels[c].get(lm) is None:
                continue
            a, g, _ = residual_dual(cam, md.pixels[c][lm], xyz)
            if a is not None and a > 15 and (g is None or g > 3.0):
                is_war = True
                break

        if abs(cam_z) < 0.5 and zc:
            kind = 'DEGENERATE_POSE'
            action = f'reparer la POSE de {src} (z={cam_z:.3f}m irrealiste, session dediee + re-validation map)'
        elif is_war:
            kind = 'WAR_PENDING'
            action = 'crop UI (deja au WAR board / reviews)'
        elif sig is not None and sig > 30:
            kind = 'BLOCKED_ON_POSE'
            action = f'bloque sur la pose de {src} (sigma {sig:.0f}m)'
        elif len(observers) >= 2:
            kind = 'SUB_WAR'
            action = 'observers en desaccord sous seuil — crop eventuel, harvest le tient en review'
        elif zc:
            kind = 'RESEEDABLE'
            action = f're-seed ray-z possible depuis {src} (verifier au dry)'
        else:
            kind = 'REVIEW'
            action = 'mono-source sans contrainte — jugement humain'
        counts[kind] = counts.get(kind, 0) + 1
        r = f"{f['resid']}'" if f['resid'] is not None else 'no-proj'
        print(f'  [{kind:15s}] {r:>8s}  {lm}')
        print(f'                    -> {action}')
    print('\nresume:', ', '.join(f'{k}:{v}' for k, v in sorted(counts.items())))


if __name__ == '__main__':
    main()
