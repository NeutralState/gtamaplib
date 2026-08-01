#!/usr/bin/env python3
# RLX-MARKINGS-0713: import de TOUS les markings rlx absents chez nous.
# Les markings sont des OBSERVATIONS PURES (pixels sur un frame) — independants
# des poses; importables meme des cams au gate BLOQUE (c'est les poses/xyz qui
# etaient le danger, pas les observations). Les nouveaux LMs entrent en
# skeleton (xyz rlx si dispo, tier unverified = inoffensifs). Matching
# CASE-INSENSITIVE des noms (piege attrape par invariants au sandbox:
# 'Anchor island' vs 'Anchor Island'). Les guards/harvest/war-scan jugent
# chaque triangulation individuellement. Idempotent.
import json, sys, importlib.util
sys.path.insert(0, 'tools'); sys.path.insert(0, '.')
from common import log_event
spec = importlib.util.spec_from_file_location('rlxdata', '/tmp/rlx_data.py')
rlx = importlib.util.module_from_spec(spec); spec.loader.exec_module(rlx)
cams = json.load(open('gtamapdata/cameras.json'))
lms = json.load(open('gtamapdata/landmarks.json'))
px = json.load(open('gtamapdata/pixels.json'))
lower_map = {n.lower(): n for n in lms}
n_mk = n_lm = n_case = 0
for c, marks in rlx.pixels.items():
    if c not in cams:
        continue
    for l, p in marks.items():
        ln = lower_map.get(l.lower(), l)   # route vers NOTRE casse si existante
        if ln != l:
            n_case += 1
        if ln in px.get(c, {}):
            continue
        px.setdefault(c, {})[ln] = list(p); n_mk += 1
        if ln not in lms:
            rx = rlx.landmarks.get(l)
            lms[ln] = {'xyz': list(rx) if rx else None, 'source_cameras': [],
                       'error_m': None, 'zone': 'rlx_markings_0713'}
            lower_map[ln.lower()] = ln
            n_lm += 1
json.dump(lms, open('gtamapdata/landmarks.json','w'), indent=2, ensure_ascii=True)
json.dump(px, open('gtamapdata/pixels.json','w'), indent=2, ensure_ascii=True)
log_event('rlx_markings_0713', 'markings_import', count=n_mk,
          reason=f'observations pures upstream; +{n_lm} skeletons, {n_case} noms re-cases')
print(f'+{n_mk} markings | +{n_lm} nouveaux LMs | {n_case} re-casings')
