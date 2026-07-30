#!/usr/bin/env python3
"""pose_revert.py — revenir a une pose alternative conservee. [POSE-REVERT-V1]

Les poses mises de cote (avec leur provenance et la raison) vivent dans
tools/data/pose_alternatives.json. Cet outil les liste et les restaure.

    PYTHONPATH=. python3 tools/pose_revert.py --list
    PYTHONPATH=. python3 tools/pose_revert.py --cam '<nom>' --pose RESECTION-V1 --apply
"""
import argparse, json, os, sys, tempfile
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
ALT = os.path.join(THIS, 'data', 'pose_alternatives.json')
CAMS = os.path.join(REPO, 'gtamapdata', 'cameras.json')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--cam'); ap.add_argument('--pose'); ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    alt = json.load(open(ALT))
    if a.list or not (a.cam and a.pose):
        for cam, poses in alt.items():
            if cam.startswith('_'): continue
            print(f'{cam}')
            for k, v in poses.items():
                print(f'   {k:16s} xyz {v["xyz"]} ypr {v["ypr"]} fov {v["fov"][0]}')
                print(f'   {"":16s} {v.get("statut","")}')
        return
    v = alt[a.cam][a.pose]
    cams = json.load(open(CAMS))
    e = cams[a.cam]
    print(f'{a.cam}\n  actuel : {e["xyz"]} {e["ypr"]} fov {e["fov"][0]}')
    print(f'  cible  : {v["xyz"]} {v["ypr"]} fov {v["fov"][0]}  [{a.pose}]')
    if not a.apply:
        print('\nDRY-RUN (--apply pour ecrire).'); return
    e['xyz'], e['ypr'], e['fov'] = v['xyz'], v['ypr'], v['fov']
    e['note'] = f'pose {a.pose} restauree par pose_revert.py. ' + v.get('methode', '')
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(CAMS), suffix='.tmp')
    with os.fdopen(fd, 'w') as f: json.dump(cams, f, indent=1, ensure_ascii=True)
    os.replace(tmp, CAMS)
    print(f'\nAPPLIED. Regenerer ensuite: python3 tools/terrain.py --only "Canyon (Kalaga Pass)"')

if __name__ == '__main__':
    main()
