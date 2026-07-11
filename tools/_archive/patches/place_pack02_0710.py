#!/usr/bin/env python3
# place_pack02_0710.py -- placement PROVISOIRE de Vintage VC Pack 02 (Port).
# SAGA: cam placeholder jamais calibree (1000,-1250,0.5, roll 0.0), ses 3
# seuls markings (les grues) exclus au lieu d'etre resolus -> "menteurs" a
# 62-282'. Enquete: pas de swap d'etiquettes (permutations 4P3 toutes >185'),
# pas de grues mobiles (une pose PHYSIQUE z>=1 reconcilie les 3 a 1.0':
# l'hypothese split est morte), le placeholder etait off ~115m/12 deg.
# Pose ecrite: (905.7,-1179.1,1.5) ypr (343.2,3.7,-0.8) fov 39.7 — PROVISOIRE
# (3 obs / 7 params = quasi-interpolant), tier low donc rayons inoffensifs,
# a consolider via markings skyline + refine_cam_full. Idempotent.
import json, math, sys
sys.path.insert(0, 'tools'); sys.path.insert(0, '.')
from common import log_event

CAM = 'Vintage Vice City Pack 02 (Port)'
POSE = {'xyz': [905.7, -1179.1, 1.5], 'ypr': [343.2, 3.7, -0.8], 'fov': [39.7, None]}

cams = json.load(open('gtamapdata/cameras.json'))
if math.dist(cams[CAM]['xyz'], POSE['xyz']) < 2:
    print('ok  deja place'); sys.exit(0)
old = {k: cams[CAM][k] for k in ('xyz', 'ypr', 'fov')}
cams[CAM].update(POSE)
with open('gtamapdata/cameras.json', 'w') as f:
    json.dump(cams, f, indent=2, ensure_ascii=True); f.write('\n')
log_event('pack02_placement', 'provisional_pose', cam=CAM, old=old, new=POSE,
          reason='placeholder jamais resolu; fit borne z>=1 sur les 3 grues (RMS 1.0), pas de swap ni de grues mobiles; PROVISOIRE a consolider')

e = json.load(open('gtamapdata/excluded_markings.json'))
if CAM in e:
    del e[CAM]
    with open('gtamapdata/excluded_markings.json', 'w') as f:
        json.dump(e, f, indent=2, ensure_ascii=True, sort_keys=True); f.write('\n')
    print('exclusions des grues retirees (appuis legitimes)')
print('pose provisoire ecrite. Suite: cycle, puis consolidation UI (Assist).')
