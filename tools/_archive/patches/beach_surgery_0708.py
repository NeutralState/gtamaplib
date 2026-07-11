#!/usr/bin/env python3
# beach_surgery_0708.py -- chirurgie de la pose Beach. One-shot, idempotent-ish.
#
# DIAGNOSTIC (0708): la cam Beach n'est PAS map-proof (audit null) — juste
# blacklistee BA historiquement. Elle a 17 appuis independants avec xyz
# (buildings VC tries par d'autres cams). Le refit full (les 6 points Beach
# circulaires exclus temporairement) donne RMS 3.32', pose -6.4m, z=0.34m:
# la cam est REELLEMENT au ras du sable (plan de trailer camera basse).
# DECOUVERTE: yaw 13.9 deg = la cam regarde au NORD; les points Beach A-F
# a y=-432 etaient DERRIERE la camera — xyz faux d'une vieille pose, prouves.
# Traitement: refit applique + quarantaine des 6 (journal, reversible).
# Re-seed refuse: ray-z depuis z=0.34m = hypersensible, precision douteuse.
# Beach RESTE blacklistee BA (pose fraiche bien posee, pas besoin de brassage).
import json, subprocess, sys

BEACH_PTS = ['Beach (A)', 'Beach (B)', 'Beach (C)', 'Beach (D)', 'Beach (E)', 'Beach (F)']

lms = json.load(open('gtamapdata/landmarks.json'))
if all(lms[l].get('xyz') is None for l in BEACH_PTS):
    print('ok  chirurgie deja faite (les 6 sont quarantines)')
    sys.exit(0)

e = json.load(open('gtamapdata/excluded_markings.json'))
for lm in BEACH_PTS:
    if lm not in e.get('Beach', []):
        e.setdefault('Beach', []).append(lm)
with open('gtamapdata/excluded_markings.json', 'w') as f:
    json.dump(e, f, indent=2, ensure_ascii=True, sort_keys=True); f.write('\n')
print('exclusions temporaires posees (anti-circularite du fit)')

r = subprocess.run(['python3', 'tools/refine_cam_full.py', 'Beach', '--apply'],
                   capture_output=True, text=True, env={'PYTHONPATH': '.', 'PATH': '/usr/bin:/bin:/usr/local/bin'})
tail = [l for l in r.stdout.splitlines() if 'RMS' in l or 'xyz:' in l]
print('refit:', ' | '.join(tail[-3:]))
if r.returncode != 0:
    print('REFIT A ECHOUE — rien d autre applique'); print(r.stdout[-500:]); sys.exit(1)

sys.path.insert(0, 'tools'); sys.path.insert(0, '.')
from common import log_event
lms = json.load(open('gtamapdata/landmarks.json'))
for lm in BEACH_PTS:
    ent = lms[lm]
    if ent.get('xyz') is None:
        continue
    log_event('beach_surgery', 'quarantine', lm=lm, old_xyz=ent['xyz'],
              reason='xyz derriere la camera (vieille pose), prouve par refit 17 appuis')
    ent['xyz'] = None; ent['source_cameras'] = []; ent['error_m'] = None
with open('gtamapdata/landmarks.json', 'w') as f:
    json.dump(lms, f, indent=2, ensure_ascii=True); f.write('\n')
print('6 points quarantines (journal, reversibles)')

e = json.load(open('gtamapdata/excluded_markings.json'))
e['Beach'] = [l for l in e.get('Beach', []) if l not in BEACH_PTS]
if not e['Beach']:
    del e['Beach']
with open('gtamapdata/excluded_markings.json', 'w') as f:
    json.dump(e, f, indent=2, ensure_ascii=True, sort_keys=True); f.write('\n')
print('exclusions temporaires retirees. Suite: cycle.')
