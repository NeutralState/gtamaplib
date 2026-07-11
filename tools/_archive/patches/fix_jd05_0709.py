#!/usr/bin/env python3
# fix_jd05_0709.py -- refit complet de Jason Duval 05 (Machine Gun). One-shot.
# CONTEXTE: hypothese communautaire "cam sur un garage ~20m" TESTEE et TUEE:
# sweep z avec x,y,ypr,fov TOUS libres + multistart -> z=22m: RMS 13.9' (xy
# fuit 91m), z=51.5: RMS 1.96'. Le reseau (10 tours a distances variees 1-3km)
# exige l'altitude. Si le spot est un garage, c'est un garage-tour (~16 dalles)
# ou un podium. Refit canonique: RMS 2.43->1.82', max 6.06->3.15', pose
# (-1441.5, 999.4, 50.2), delta 7.3m. Le courthouse (SE) est exclu du fit
# (anti-circularite, pattern Beach) puis retriangule avec la pose neuve.
import json, subprocess, sys

CAM = 'Jason Duval 05 (Machine Gun)'
LM = 'C. Clyde Atkins U.S Courthouse (SE)'

e = json.load(open('gtamapdata/excluded_markings.json'))
if LM not in e.get(CAM, []):
    e.setdefault(CAM, []).append(LM)
    with open('gtamapdata/excluded_markings.json', 'w') as f:
        json.dump(e, f, indent=2, ensure_ascii=True, sort_keys=True); f.write('\n')
print('exclusion temporaire posee (anti-circularite)')

r = subprocess.run(['python3', 'tools/refine_cam_full.py', CAM, '--apply'],
                   capture_output=True, text=True, env={'PYTHONPATH': '.', 'PATH': '/usr/bin:/bin:/usr/local/bin'})
print('refit:', ' | '.join(l.strip() for l in r.stdout.splitlines() if 'RMS' in l or 'xyz:' in l)[:200])
if r.returncode != 0:
    print('REFIT ECHOUE'); print(r.stdout[-400:]); sys.exit(1)

e = json.load(open('gtamapdata/excluded_markings.json'))
e[CAM] = [l for l in e.get(CAM, []) if l != LM]
if not e[CAM]:
    del e[CAM]
with open('gtamapdata/excluded_markings.json', 'w') as f:
    json.dump(e, f, indent=2, ensure_ascii=True, sort_keys=True); f.write('\n')

r = subprocess.run(['python3', 'tools/triangulate_lm.py', LM, '--apply'],
                   capture_output=True, text=True)
print('courthouse:', ' | '.join(l.strip() for l in r.stdout.splitlines() if 'All-observer' in l or 'Delta' in l))
print('Suite: cycle.')
