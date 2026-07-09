#!/usr/bin/env python3
# orphan_triage.py -- triage des LM orphelins (xyz sans marking vivant).
# [PROVENANCE-V2, 2026-07-08]
#
# Un orphelin est INERTE pour le solver mais DANGEREUX: un futur marking du
# meme nom heriterait d'un xyz perime d'une source morte (fossile/guerre
# instantane). Traitement: QUARANTAINE REVERSIBLE (xyz -> None, l'ancien xyz
# est loggue dans gtamapdata/events.jsonl).
#
# PROTEGES (jamais quarantines): notes non vides (modeles rigides, ports
# documentes ex. mat WDNA), map_validated, z_constraint, references dans
# lines.json.
#
# Usage:
#   PYTHONPATH=. python3 tools/audit/orphan_triage.py               (scan)
#   PYTHONPATH=. python3 tools/audit/orphan_triage.py --quarantine  (applique)
import argparse
import json
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quarantine', action='store_true')
    args = ap.parse_args()

    lms = json.load(open('gtamapdata/landmarks.json'))
    px = json.load(open('gtamapdata/pixels.json'))
    try:
        mv = json.load(open('gtamapdata/map_validated.json'))
    except Exception:
        mv = {}
    lines_txt = ''
    try:
        lines_txt = open('gtamapdata/lines.json').read()
    except Exception:
        pass

    marked = set()
    for c in px:
        marked |= set(px[c])

    ghosts, protected = [], []
    for n, e in lms.items():
        if not e or not e.get('xyz') or n in marked:
            continue
        why = []
        if e.get('notes'):
            why.append('notes')
        if n in mv:
            why.append('map_validated')
        if e.get('z_constraint'):
            why.append('z_constraint')
        if f'"{n}"' in lines_txt:
            why.append('lines.json')
        if why:
            protected.append((n, why))
        else:
            ghosts.append(n)

    print(f'orphelins: {len(ghosts) + len(protected)} | '
          f'proteges: {len(protected)} | purs fantomes: {len(ghosts)}')
    for n, why in protected:
        print(f'  PROTEGE ({",".join(why)}): {n}')
    for n in ghosts[:10]:
        srcs = (lms[n].get('source_cameras') or [])
        print(f'  FANTOME: {n}  (sources mortes: {srcs})')
    if len(ghosts) > 10:
        print(f'  ... +{len(ghosts) - 10} fantomes')

    if not args.quarantine:
        print('\nDRY. --quarantine pour appliquer (xyz -> None, '
              'anciens xyz dans events.jsonl).')
        return

    from common import log_event
    shutil.copy('gtamapdata/landmarks.json',
                'gtamapdata/landmarks.json.bak_orphan_triage')
    for n in ghosts:
        e = lms[n]
        log_event('orphan_triage', 'quarantine', lm=n,
                  old_xyz=e['xyz'], old_sources=e.get('source_cameras'),
                  zone=e.get('zone'))
        e['xyz'] = None
        e['source_cameras'] = []
        e['error_m'] = None
    with open('gtamapdata/landmarks.json', 'w') as f:
        json.dump(lms, f, indent=2, ensure_ascii=True)
        f.write('\n')
    print(f'\nQUARANTINE: {len(ghosts)} fantomes (xyz -> None, '
          f'recuperables via events.jsonl). Backup .bak_orphan_triage.')


if __name__ == '__main__':
    main()
