#!/usr/bin/env python3
# readd_weekend_markings.py -- reinjecte les 6 markings weekend detruits par
# le checkout du 07-13 (recuperes du diff colle en chat; cams identifiees par
# resolution geometrique inverse: projection des xyz connus -> match <41px,
# candidat suivant a 100px+). Cree les 3 skeletons de coins (nouveaux LMs
# weekend). SELF-GATE: refuse de rouler si le revert 58d3d4a n'est pas HEAD.
import json, subprocess, sys
sys.path.insert(0, 'tools'); sys.path.insert(0, '.')
from common import log_event

head = subprocess.run(['git', 'log', '-1', '--format=%s'], capture_output=True, text=True).stdout
if not head.startswith('Revert'):
    sys.exit(f'GATE: HEAD n est pas le revert ({head[:60]}...) — regle le revert d abord, je ne touche a rien.')

MARKS = {
    'Motorboats (A)': {
        'Three Tequesta Point (SE)': [1716.4, 763.5],
        'Three Tequesta Point (NE)': [1786.7, 766.0],
        'Container Crane (2)': [2030.1, 624.3],
    },
    'Port Vice City (A)': {
        'Three Tequesta Point (SE)': [1181.9, 777.9],
        'Three Tequesta Point (NE)': [1234.7, 777.9],
        'Two Tequesta Point (SE)': [965.0, 849.2],
    },
}
px = json.load(open('gtamapdata/pixels.json'))
lms = json.load(open('gtamapdata/landmarks.json'))
added = 0
for cn, marks in MARKS.items():
    for l, p in marks.items():
        if px.get(cn, {}).get(l):
            print(f'ok  {cn} :: {l} deja present'); continue
        px.setdefault(cn, {})[l] = p; added += 1
        if l not in lms:
            lms[l] = {'xyz': None, 'source_cameras': [], 'error_m': None, 'zone': 'brickell'}
json.dump(px, open('gtamapdata/pixels.json', 'w'), indent=2, ensure_ascii=True)
json.dump(lms, open('gtamapdata/landmarks.json', 'w'), indent=2, ensure_ascii=True)
log_event('readd_0713', 'markings_restored', cams=list(MARKS),
          reason=f'{added} markings weekend reinjectes apres perte au checkout (cams retrouvees par resolution geometrique inverse)')
print(f'{added} markings reinjectes. Suite: cycle --harvest.')
