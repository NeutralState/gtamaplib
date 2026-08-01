#!/usr/bin/env python3
"""terrain.py — l'orchestrateur des terrains 3D. [TERRAIN-V1]

LE point d'entree unique de la modelisation de terrain (but d'Alexandre:
'les tools necessaires pour modeliser un terrain adequatement en 3D').
Lit tools/data/terrains.json (registre declaratif: moteur + parametres
valides + provenance de chaque hypothese) et regenere les meshs de l'UI.

    PYTHONPATH=. python3 tools/terrain.py --all
    PYTHONPATH=. python3 tools/terrain.py --only 'Mount Ambrosia'
    PYTHONPATH=. python3 tools/terrain.py --list

Le pipeline terrain complet (cf. tools/TERRAIN_PIPELINE.md):
  1. 2D    — lignes tracees/corrigees par Alexandre (annotation directe du
             PNG genere, extraction pixel-exact par diff)
  2. 3D    — ce fichier: moteurs hill_mesh/canyon_mesh pilotes par le
             registre (donnees et hypotheses declarees separees)
  3. MESURE— anchor_harvest (triangulation de masse), crossclick_guide
             (clics croises guides), depth_terrain (profondeur dense
             calibree) -> les hypotheses deviennent des mesures
  4. BOUCLE— nouvelle mesure -> mettre a jour le registre -> --all
"""
import argparse
import json
import os
import subprocess
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
REGISTRY = os.path.join(THIS, 'data', 'terrains.json')
PY = sys.executable


def run_engine(engine, args):
    cmd = [PY, os.path.join(THIS, engine)] + list(args)
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       env={**os.environ, 'PYTHONPATH': REPO})
    ok = r.returncode == 0
    tail = (r.stdout.strip().split('\n') or [''])[-1]
    print(('  OK   ' if ok else '  FAIL ') + f'{engine} {" ".join(args)}  | {tail}')
    if not ok:
        print(r.stdout[-800:])
        print(r.stderr[-800:])
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--only')
    ap.add_argument('--list', action='store_true')
    args = ap.parse_args()

    reg = {k: v for k, v in json.load(open(REGISTRY)).items()
           if not k.startswith('_')}
    if args.list or not (args.all or args.only):
        for name, t in reg.items():
            print(f'{name}')
            print(f'    moteur : {t["engine"]} {" ".join(t.get("args", []))}')
            print(f'    lignes : {t.get("lines_source", "?")}')
            print(f'    prof.  : {t.get("depth_provenance", "?")}')
            print(f'    params : {t.get("params_provenance", "?")}')
        return

    targets = [args.only] if args.only else list(reg)
    ok_all = True
    for name in targets:
        t = reg.get(name)
        if not t:
            print(f'{name}: inconnu au registre')
            ok_all = False
            continue
        print(f'== {name} ==')
        if t.get('pre'):
            ok_all &= run_engine(t['pre']['engine'], t['pre'].get('args', []))
        ok_all &= run_engine(t['engine'], t.get('args', []))
    sys.exit(0 if ok_all else 1)


if __name__ == '__main__':
    main()
