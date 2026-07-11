#!/usr/bin/env python3
"""reviews_fix_0708.py -- reglement des reviews all-obs du 2026-07-08.
Investigation duale: les 6 menteurs sont TOUS des cams a gros sigma de pose
(Green Sports Car 428'/90m sigma=37m, Rooftop sigma=81m, VC Sign sigma=181m,
Ambrosia 02 x2 — le delta rejete #1 du tension-audit). Leurs rayons lointains
portent l'incertitude de pose. Exclusions ciblees + retri sur majorites saines.
FLAGLER PAS TOUCHE (2v1 avec Interchange = crop UI, doctrine).
Idempotent. Note Phase B: ponderer les pools de triangulation par sigma pose."""
import json, subprocess, sys

EXCL = {
    'Brickell Arch': ["'95 Grotti Cheetah 04 (Garage)", 'Ultimate Edition 02 (Green Sports Car)'],
    'FAA Miami ATCT (MIA)': ['Vice City Sign'],
    'Miami-Dade County Courthouse': ['Vintage Vice City Outfits and Hairstyles 04 (Rooftop)'],
    'The Ritz-Carlton Coconut Grove (S)': ['Metro (SE) (C)'],
    'US Sugar Mill (Factory)': ['Ambrosia 02 (Panorama)'],
    'Wheelabrator South Broward (W)': ['Ambrosia 02 (Panorama)'],
}

e = json.load(open('gtamapdata/excluded_markings.json'))
n = 0
for lm, cams in EXCL.items():
    for c in cams:
        if lm not in e.get(c, []):
            e.setdefault(c, []).append(lm)
            n += 1
            print(f'EXCL {c} :: {lm}')
        else:
            print(f'ok   {c} :: {lm} deja exclu')
if n:
    with open('gtamapdata/excluded_markings.json', 'w') as f:
        json.dump(e, f, indent=2, ensure_ascii=True, sort_keys=True); f.write('\n')

for lm in EXCL:
    r = subprocess.run(['python3', 'tools/triangulate_lm.py', lm, '--apply'],
                       capture_output=True, text=True)
    line = [l for l in r.stdout.splitlines() if 'All-observer' in l or 'Delta' in l]
    tag = 'RETRI' if r.returncode == 0 else 'ECHEC'
    print(f'{tag} {lm}: ' + ' | '.join(line))
print('\nSuite: rm -f /tmp/gtamaplib_harvest_state.json && python3 tools/cycle.py --tag reviews_0708 --harvest --update-baseline')
