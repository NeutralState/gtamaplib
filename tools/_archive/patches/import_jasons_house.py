#!/usr/bin/env python3
# JASONS-HOUSE-IMPORT (2026-07-13): import gated de la maison de Jason.
# Gate de coherence interne (lecon de l'import rlx casse du matin): House
# (Keys) PASSE a 1.26' mediane / 41 obs via NOTRE lib; House with Boat (X)
# et Jason's Safehouse Vehicles (X) BLOQUES (fov incomplet / 2.93' > gate 2').
# Import: cam House (Keys) (schema complet) + ses 42 markings + les LMs
# Jason's House xyz rlx (tier unverified = inoffensifs jusqu'a validation).
# Idempotent.
import json, sys, re, importlib.util
sys.path.insert(0, 'tools'); sys.path.insert(0, '.')
from common import log_event
spec = importlib.util.spec_from_file_location('rlxdata', '/tmp/rlx_data.py')
rlx = importlib.util.module_from_spec(spec); spec.loader.exec_module(rlx)
cams = json.load(open('gtamapdata/cameras.json'))
lms = json.load(open('gtamapdata/landmarks.json'))
px = json.load(open('gtamapdata/pixels.json'))
C = 'House (Keys)'
if C in cams:
    print('ok  deja importe'); sys.exit(0)
r = rlx.cameras[C]
cams[C] = {'id': r.get('id') or 'K/HK1', 'player': list(r['player']) if r.get('player') else None,
           'xyz': list(r['xyz']), 'ypr': list(r['ypr']),
           'fov': [r['fov'][0], r['fov'][1] if len(r['fov']) > 1 else None],
           'size': list(r['size']), 'source': r.get('source', 'House (Keys)')}
n_mk = n_lm = 0
for l, p in rlx.pixels[C].items():
    px.setdefault(C, {})[l] = list(p); n_mk += 1
need = set(re.findall(r'md\.landmarks\["([^"]+)"\]', open('/tmp/jasons.py').read()))
for l in set(rlx.pixels[C]) | need:
    rx = rlx.landmarks.get(l)
    if l not in lms:
        lms[l] = {'xyz': list(rx) if rx else None, 'source_cameras': [],
                  'error_m': None, 'zone': 'jasons_house_rlx'}; n_lm += 1
    elif rx and not lms[l].get('xyz'):
        lms[l]['xyz'] = list(rx); n_lm += 1
json.dump(cams, open('gtamapdata/cameras.json','w'), indent=2, ensure_ascii=True)
json.dump(lms, open('gtamapdata/landmarks.json','w'), indent=2, ensure_ascii=True)
json.dump(px, open('gtamapdata/pixels.json','w'), indent=2, ensure_ascii=True)
log_event('jasons_house_import', 'gated_import', cams=[C],
          reason=f'gate 1.26 mediane; +{n_mk} markings, +{n_lm} LMs xyz rlx (unverified)')
print(f'cam {C} + {n_mk} markings + {n_lm} LMs')
