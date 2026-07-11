#!/usr/bin/env python3
# fix_round_water_tower.py -- retriangulation du fossile Round Water Tower.
# DIAGNOSTIC: 3 temoins tous mauvais (12/26/38') sur le xyz actuel — mais
# anti-swap NEGATIF (le marking Postcard ne colle a AUCUNE des 8 autres
# water towers, 1717'+ partout): pas de collision de nom. Le xyz etait
# PERIME (triangule sous de vieilles poses, upgrade bloque par le guard).
# Le duo Postcard x PVC (A) croise a 2.2' avec 39 deg de parallaxe, a 78m
# du point perime. Dissident: Ambrosia 02 a 68.8' — sa vallee nord-sud
# molle (sigma 39m, diagnostic du 2026-07-10) + une tour a 4.6km = temoignage
# faible -> exclusion ciblee documentee. Idempotent.
import json, subprocess, sys

e = json.load(open('gtamapdata/excluded_markings.json'))
cam = 'Ambrosia 02 (Panorama)'
if 'Round Water Tower' in e.get(cam, []):
    print('ok  exclusion deja posee')
else:
    e.setdefault(cam, []).append('Round Water Tower')
    e[cam].sort()
    with open('gtamapdata/excluded_markings.json', 'w') as f:
        json.dump(e, f, indent=2, ensure_ascii=True, sort_keys=True); f.write('\n')
    print('exclusion Ambrosia02::Round Water Tower posee')

r = subprocess.run(['python3', 'tools/triangulate_lm.py', 'Round Water Tower', '--apply'],
                   capture_output=True, text=True)
print(' | '.join(l.strip() for l in r.stdout.splitlines()
                 if 'All-observer' in l or 'Delta' in l or 'APPLIED' in l))
if r.returncode != 0:
    print(r.stdout[-400:]); sys.exit(1)
print('Suite: cycle.')
