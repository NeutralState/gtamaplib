#!/usr/bin/env python3
"""
cycle.py -- LE cycle standard en une commande. [CYCLE-V1, 2026-07-07]

Remplace la sequence memorisee de 10+ lignes. Roule le DAG dans l'ordre,
s'arrete au premier FAIL, imprime un resume condense (avant/apres).

Usage:
  python3 tools/cycle.py --tag ma_session                    # cycle standard
  python3 tools/cycle.py --tag t --harvest --scan            # apres imports/markings
  python3 tools/cycle.py --tag t --update-baseline           # si amelioration a geler
  python3 tools/cycle.py --tag t --commit "message"          # + git add/commit (pas de push)

Cycle standard:  tiers -> BA weighted --cleanup -> guarded dry -> guarded
--apply -> snapshot --tag -> tiers -> invariants -> ci_healthcheck.
--harvest insere harvest_run apres le 1er tiers; --scan insere
collision_scan --apply avant le BA (doctrine: apres chaque batch de markings).

Le commit ajoute gtamapdata/ + tools/ci_baseline.json seulement; le push reste
manuel (doctrine: relire le resume avant de pousser).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
ENV = {**os.environ, 'PYTHONPATH': ROOT}


def run(label, cmd, must_pass=True, quiet=True):
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, env=ENV)
    dt = time.time() - t0
    status = 'OK ' if r.returncode == 0 else 'FAIL'
    print(f'[{status}] {label:<28s} {dt:6.1f}s')
    if r.returncode != 0:
        print('--- stdout (tail) ---')
        print(r.stdout[-2000:])
        print('--- stderr (tail) ---')
        print(r.stderr[-800:])
        if must_pass:
            print(f'\nCYCLE ARRETE a l etape: {label}')
            sys.exit(1)
    return r.stdout


def grab(pattern, text, default=None):
    m = re.search(pattern, text)
    return m.group(1) if m else default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', required=True)
    ap.add_argument('--harvest', action='store_true',
                    help='harvest_run apres le 1er tiers (apres imports/markings)')
    ap.add_argument('--scan', action='store_true',
                    help='collision_scan --apply avant le BA (apres markings)')
    ap.add_argument('--max-iter', type=int, default=30)
    ap.add_argument('--update-baseline', action='store_true')
    ap.add_argument('--commit', metavar='MSG', default=None)
    args = ap.parse_args()

    t_start = time.time()
    print(f'══ CYCLE tag={args.tag} '
          f'{"+harvest " if args.harvest else ""}{"+scan " if args.scan else ""}══')

    out = run('snapshot avant', ['python3', 'tools/audit/rms_snapshot.py',
                                 '--tag', f'{args.tag}_avant'])
    med0 = grab(r"median=([\d.]+)'", out)
    medm0 = grab(r"median_m=([\d.]+)m", out)

    run('tiers', ['python3', 'tools/compute_confidence_tiers.py'])

    if args.harvest:
        out = run('harvest', ['python3', 'harvest_run.py'])
        print(f'      harvest: ' + (grab(r'(traites: .*)', out) or '?'))

    if args.scan:
        out = run('war-scan --apply',
                  ['python3', 'tools/audit/collision_scan.py', '--apply'])
        print(f'      scan: ' + (grab(r'(applied: .*)', out) or '?'))
        run('tiers (post-scan)', ['python3', 'tools/compute_confidence_tiers.py'])

    run('bundle weighted', ['python3', 'tools/bundle_adjust_weighted.py',
                            '--cleanup', '--max-iter', str(args.max_iter)])

    out = run('guarded dry', ['python3', 'tools/refine/guarded_apply.py'])
    acc = grab(r'ACCEPTED (\d+) deltas', out, '0')
    top = [l.strip() for l in out.splitlines() if re.match(r'\s+-[\d.]+\'', l)][:3]

    out = run('guarded --apply', ['python3', 'tools/refine/guarded_apply.py', '--apply'])
    applied = grab(r'(APPLIED: .*)', out, '?')

    out = run('snapshot', ['python3', 'tools/audit/rms_snapshot.py', '--tag', args.tag])
    med1 = grab(r"median=([\d.]+)'", out)
    medm1 = grab(r"median_m=([\d.]+)m", out)

    run('tiers (final)', ['python3', 'tools/compute_confidence_tiers.py'])
    run('invariants', ['python3', 'tools/audit/invariants.py'])

    ci_cmd = ['python3', 'tools/ci_healthcheck.py']
    if args.update_baseline:
        run('ci_healthcheck', ci_cmd)
        run('baseline gel', ci_cmd + ['--update-baseline'])
    else:
        run('ci_healthcheck', ci_cmd)

    print()
    print('══ RESUME ══')
    print(f"  mediane : {med0}' -> {med1}'   |   metres: {medm0}m -> {medm1}m")
    print(f'  guarded : {acc} deltas acceptes | {applied}')
    for l in top:
        print(f'     {l}')
    print(f'  duree   : {time.time() - t_start:.0f}s')

    if args.commit:
        run('git add', ['git', 'add', 'gtamapdata/', 'tools/ci_baseline.json'])
        run('git commit', ['git', 'commit', '-m', args.commit])
        print('  commit fait — push MANUEL apres relecture: git push origin feature-solver')

    print('CYCLE OK')


if __name__ == '__main__':
    main()
