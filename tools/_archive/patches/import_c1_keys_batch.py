#!/usr/bin/env python3
# CHANTIER-1 KEYS BATCH (2026-07-14): import gated des 4 poses rlx de la
# zone Keys/Grassrivers. Gate rlx_pose_gate.py (coherence interne rlx mk x
# rlx LM x rlx pose via NOTRE lib, mediane < 2'):
#   Grassrivers Postcard (X)        PASS 0.78'/23 obs   delta  88.3m
#   Keys                            PASS 0.00'/106 obs  delta 269.8m
#   Leonida Keys 01 (Airplane) (X)  PASS 0.39'/178 obs  delta  30.0m
#   Leonida Keys Postcard (X)       PASS 0.00'/144 obs  delta  15.5m
# Batch (pas un-par-un): ces cams partagent massivement leurs LMs — un
# import partiel laisserait le reseau en tension mixte vieux/nouveau.
# POSES SEULES (schema complet id/player/fov). Markings rlx = hors scope
# (sync_rlx). Cascade ensuite: rederive_mono + retri sweep + cycle.
# Idempotent. Backup .bak_c1_keys.
import json, math, shutil, sys
sys.path.insert(0, 'tools'); sys.path.insert(0, '.')
from common import log_event

TARGETS = ['Grassrivers Postcard (X)', 'Keys',
           'Leonida Keys 01 (Airplane) (X)', 'Leonida Keys Postcard (X)']

rlx = json.load(open('/tmp/rlx_dump.json'))
cams = json.load(open('gtamapdata/cameras.json'))

done = []
for C in TARGETS:
    r = rlx['cameras'][C]
    cur = cams[C]
    if (max(abs(a - b) for a, b in zip(cur['xyz'], r['xyz'])) < 1e-6
            and abs((cur['fov'][0] or 0) - (r['fov'][0] or 0)) < 1e-6):
        print(f'ok  {C}: deja importe')
        continue
    delta = math.dist(cur['xyz'], r['xyz'])
    cur['id'] = r.get('id') or cur.get('id')
    cur['player'] = list(r['player']) if r.get('player') else None
    cur['xyz'] = list(r['xyz'])
    cur['ypr'] = list(r['ypr'])
    cur['fov'] = [r['fov'][0], r['fov'][1] if len(r['fov']) > 1 else None]
    done.append((C, delta))
    print(f'IMPORT {C}: delta {delta:.1f}m, fov {r["fov"]}')

if not done:
    print('rien a faire')
    sys.exit(0)

shutil.copy('gtamapdata/cameras.json', 'gtamapdata/cameras.json.bak_c1_keys')
with open('gtamapdata/cameras.json', 'w') as f:
    json.dump(cams, f, indent=2, ensure_ascii=True)
    f.write('\n')
log_event('c1_keys_batch', 'gated_pose_import',
          cams=[c for c, _ in done],
          reason='rlx_pose_gate PASS (0.00-0.78 arcmin mediane interne); '
                 'deltas ' + ', '.join(f'{c} {d:.0f}m' for c, d in done))
print(f'{len(done)} poses importees. Cascade: rederive_mono + retri sweep + cycle.')
