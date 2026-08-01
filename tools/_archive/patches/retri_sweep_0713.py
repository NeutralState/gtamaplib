#!/usr/bin/env python3
# retri_sweep_0713.py -- sweep de retriangulation des LMs perimes.
# CONTEXTE: des semaines de cycles BA ont fait evoluer les poses pendant que
# les SIGMA-GATES bloquaient les gros rattrapages individuels (pattern Round
# Water Tower: 78m perime). L'audit retriangulation_candidates flagge 58
# candidats (delta>=2m, parallaxe>=15deg, >=2 sources) — dont White Silos (W)
# a 1559m (!), Lamp Post (SW) 253m, Reworld 98m. Chaque apply repasse par
# l'OBSERVER-GUARD (<8' all-observer) et les gates: les sales se bloquent
# eux-memes. Sandbox: 51/58 appliques, cycle vert, mediane 1.911'/0.201m
# (+0.014' vs avant = les points corriges mesurent des residuels honnetes;
# la verite de position gagne 8-1559m par point), Highway Peacock -17.8'.
import subprocess, sys, os
print('Audit des candidats (2-3 min)...')
r = subprocess.run(['python3', 'tools/audit/retriangulation_candidates.py'],
                   capture_output=True, text=True, timeout=1200,
                   env={**os.environ, 'PYTHONPATH': '.'})
cands = [l.split('\t')[1] for l in r.stdout.splitlines() if l.startswith('CAND\t')]
print(f'{len(cands)} candidats flagges')
ok = blocked = 0
for n in cands:
    rr = subprocess.run(['python3', 'tools/triangulate_lm.py', n, '--apply'],
                        capture_output=True, text=True, timeout=120)
    if 'APPLIED' in rr.stdout:
        ok += 1
        print(f'  OK  {n}')
    else:
        blocked += 1
print(f'\nappliques: {ok} | bloques par les guards: {blocked}')
print('Suite: cycle --update-baseline.')
