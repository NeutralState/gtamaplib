#!/usr/bin/env python3
# import_rlx_zone_0710.py -- IMPORT ZONE Grassrivers/Ambrosia depuis rlx.
# CONTEXTE: rlx a fait du map-evidence terrain massif dans la zone (Paths,
# Factories, Airfield, Train Tracks, Pylons + find_camera upgrade lm_z_limits).
# Ses poses divergent des notres de 33-219m sur le trio Ambrosia — la vallee
# molle N-S diagnostiquee le 07-10: nos deux solvers avaient converge a des
# endroits differents. ARBITRAGE: nos ancres externes (toutes a 5km+) donnent
# des residuels IDENTIQUES sous les deux poses (elles ne peuvent pas trancher);
# la solution rlx satisfait tout ce que la notre satisfait PLUS ses contraintes
# terrain a courte portee -> strictement plus contrainte -> adoptee.
# PHASES: (1) poses zone (5 cams) + cam Grassrivers 04 (schema complet id/
# player!) + 88 markings + 116 LMs; (2) retriangulation du blast (51 LMs
# trio-sources; ~36 passent, mono-temoins restent); (3) adoption xyz rlx pour
# les mono-temoins (~9). Valide au sandbox: CYCLE VERT, mediane 1.965'.
# NOTE: les 3 exclusions A02 (Tank R/Sugar Mill/Wheelabrator W) restent
# exclues (residuels pires sous la nouvelle geometrie = vrais mauvais clics).
# Idempotent (skip si Grassrivers 04 deja presente).
import json, subprocess, sys
import importlib.util
sys.path.insert(0, 'tools'); sys.path.insert(0, '.')
from common import log_event

spec = importlib.util.spec_from_file_location('rlxdata', '/tmp/rlx_data.py')
rlx = importlib.util.module_from_spec(spec); spec.loader.exec_module(rlx)
cams = json.load(open('gtamapdata/cameras.json'))
lms = json.load(open('gtamapdata/landmarks.json'))
px = json.load(open('gtamapdata/pixels.json'))
NEW_CAM = 'Grassrivers 04 (Police Chase)'
if NEW_CAM in cams:
    print('ok  import deja fait'); sys.exit(0)

POSES = ['Ambrosia 02 (Panorama)', 'Ambrosia 04 (Fires)', 'Ambrosia Postcard (X)',
         'Grassrivers Postcard (X)', 'Grassrivers 02 (Watson Bay)']
for n in POSES:
    r = rlx.cameras[n]
    cams[n]['xyz'] = list(r['xyz']); cams[n]['ypr'] = list(r['ypr'])
    cams[n]['fov'] = [r['fov'][0], r['fov'][1] if len(r['fov']) > 1 else None]
r = rlx.cameras[NEW_CAM]
cams[NEW_CAM] = {'id': r.get('id') or 'S2/64',
                 'player': list(r['player']) if r.get('player') else None,
                 'xyz': list(r['xyz']), 'ypr': list(r['ypr']),
                 'fov': [r['fov'][0], r['fov'][1]], 'size': list(r['size']),
                 'source': r.get('source', 'Grassrivers 04 [1]')}
ZONE_CAMS = POSES + [NEW_CAM]
n_mk = 0; new_lm = set()
for cn in ZONE_CAMS:
    for l, p in rlx.pixels.get(cn, {}).items():
        px.setdefault(cn, {})
        if l not in px[cn]:
            px[cn][l] = list(p); n_mk += 1
        if l not in lms:
            new_lm.add(l)
for l in new_lm:
    rx = rlx.landmarks.get(l)
    lms[l] = {'xyz': list(rx) if rx else None, 'source_cameras': [],
              'error_m': None, 'zone': 'ambrosia_grassrivers_rlx'}
json.dump(cams, open('gtamapdata/cameras.json','w'), indent=2, ensure_ascii=True)
json.dump(lms, open('gtamapdata/landmarks.json','w'), indent=2, ensure_ascii=True)
json.dump(px, open('gtamapdata/pixels.json','w'), indent=2, ensure_ascii=True)
log_event('rlx_import_0710', 'zone_import', cams=ZONE_CAMS,
          reason=f'poses zone rlx (terrain-contraint) + Grassrivers 04 + {n_mk} markings + {len(new_lm)} LMs')
print(f'PHASE 1: poses {len(POSES)} | +1 cam | +{n_mk} markings | +{len(new_lm)} LMs')

TRIO = set(POSES) - {'Grassrivers 02 (Watson Bay)'}
blast = [n for n, e in lms.items() if (e or {}).get('xyz') and set(e.get('source_cameras') or []) & TRIO]
ok = blocked = 0
for n in blast:
    rr = subprocess.run(['python3', 'tools/triangulate_lm.py', n, '--apply'],
                        capture_output=True, text=True, timeout=120)
    ok += 1 if 'APPLIED' in rr.stdout else 0
    blocked += 0 if 'APPLIED' in rr.stdout else 1
print(f'PHASE 2: blast {len(blast)} LMs -> retriangules {ok}, bloques {blocked} (mono-temoins)')

lms = json.load(open('gtamapdata/landmarks.json'))
adopted = 0
for n, e in lms.items():
    if not (e or {}).get('xyz'): continue
    if not (set(e.get('source_cameras') or []) & TRIO): continue
    if len([c for c in px if n in px[c]]) >= 2: continue
    rx = rlx.landmarks.get(n)
    if rx is not None:
        e['xyz'] = list(rx); e['error_m'] = None
        e['zone'] = e.get('zone') or 'ambrosia_grassrivers_rlx'
        adopted += 1
json.dump(lms, open('gtamapdata/landmarks.json','w'), indent=2, ensure_ascii=True)
print(f'PHASE 3: xyz rlx adoptes pour {adopted} mono-temoins')
print('Suite: cycle --update-baseline.')
