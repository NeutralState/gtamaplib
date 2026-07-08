#!/usr/bin/env python3
"""
sync_rlx.py -- l'archeologie upstream automatisee. [SYNC-RLX-V1, 2026-07-07]

Parse le gtamapdata.py de rlx (upstream/main), diffe contre le dernier sync
(gtamapdata/rlx_sync_state.json) ou --since <ref>, classe CHAQUE changement
et sort le plan d'import gate.

Classification et politique (doctrine codee une fois pour toutes):
  MARK_ADD      marking neuf sur une cam qu'on a -> IMPORT (--apply)
                (+ skeleton LM si absent, zone = zone majoritaire de la cam)
  MARK_SNAP     move <= 2px -> IMPORT si notre pixel == ancien pixel rlx
  MARK_MOVE     move > 2px  -> REPORT (jugement humain; ex: House with Boat)
  MARK_RENAME   DEL+ADD a pixel identique -> REPORT (fusion/provenance,
                ex: Island K -> Vake Island, prouver par geometrie d'abord)
  MARK_DEL      -> REPORT seulement (on ne supprime jamais aveuglement)
  CAM_POSE      xyz/ypr/fov changes -> SKIP doctrinal (solves, pas donnees —
                preuve 07-07: fov Jason X 58.8->57.0 entre deux jours)
  LM_XYZ        -> SKIP doctrinal (derives de SES poses; nos triangulations
                a nous via cycle --harvest apres l'import)
  SKIP_LIST     markings en collision de nom connue -> jamais importes

Usage:
  git fetch upstream
  PYTHONPATH=. python3 tools/sync_rlx.py                  # vs dernier sync
  PYTHONPATH=. python3 tools/sync_rlx.py --since 396e7af  # vs ref explicite
  PYTHONPATH=. python3 tools/sync_rlx.py --apply          # ecrit ADD+SNAP,
                                                          # backups .bak_rlxsync,
                                                          # gele sync_state
Apres --apply: python3 tools/cycle.py --tag rlx_sync --harvest --scan
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

STATE = 'gtamapdata/rlx_sync_state.json'
SNAP_PX = 2.0

SKIP_MARKINGS = {
    'House with Boat (X)',   # 67.2 deg vs notre LM (0.133m, 2 cams X) — 2026-07-06
}


def git_show(ref, path='gtamapdata.py'):
    r = subprocess.run(['git', 'show', f'{ref}:{path}'], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'git show {ref}:{path} a echoue — as-tu fait git fetch upstream?')
    return r.stdout


def parse_rlx(src):
    cams, pixels = {}, {}
    for m in re.finditer(r'"(\[[^\]]+\]) ([^"]+)": \((.*?)\),\n', src):
        cams[m.group(2)] = (m.group(1), m.group(3))
    for m in re.finditer(r'"(\[[^\]]+\]) ([^"]+)": \[\n(.*?)\n    \]', src, re.S):
        marks = {}
        for pm in re.finditer(r'\(\(([\d.]+), ([\d.]+)\), "([^"]+)"\)', m.group(3)):
            marks[pm.group(3)] = [float(pm.group(1)), float(pm.group(2))]
        pixels[m.group(2)] = marks
    return cams, pixels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', default=None, help='ref rlx de depart (defaut: sync_state)')
    ap.add_argument('--ref', default='upstream/main', help='ref rlx cible')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    since = args.since
    if since is None:
        if os.path.exists(STATE):
            since = json.load(open(STATE))['last_synced']
        else:
            sys.exit('Pas de sync_state — premiere fois: --since <ref rlx deja integre>')

    head = subprocess.run(['git', 'rev-parse', '--short', args.ref],
                          capture_output=True, text=True).stdout.strip()
    print(f'══ SYNC-RLX {since} -> {args.ref} ({head}) ══\n')

    o_cams, o_px = parse_rlx(git_show(since))
    n_cams, n_px = parse_rlx(git_show(args.ref))

    ours_cams = json.load(open('gtamapdata/cameras.json'))
    ours_px = json.load(open('gtamapdata/pixels.json'))
    ours_lms = json.load(open('gtamapdata/landmarks.json'))
    lm_zone = {n: (e or {}).get('zone') for n, e in ours_lms.items()}

    plan_add, plan_snap = [], []
    n_pose = 0
    reports = []

    for c in n_cams:
        if c in o_cams and o_cams[c][1] != n_cams[c][1]:
            n_pose += 1

    for cam, n_marks in n_px.items():
        o_marks = o_px.get(cam, {})
        if n_marks == o_marks:
            continue
        we_have = cam in ours_cams
        mine = ours_px.get(cam, {})
        added = {k: v for k, v in n_marks.items() if k not in o_marks}
        removed = {k: v for k, v in o_marks.items() if k not in n_marks}
        moved = {k: (o_marks[k], v) for k, v in n_marks.items()
                 if k in o_marks and o_marks[k] != v}

        renames = []
        for old_name, old_p in list(removed.items()):
            for new_name, new_p in list(added.items()):
                if old_p == new_p:
                    renames.append((old_name, new_name, old_p))
                    del removed[old_name]
                    del added[new_name]
                    break

        for lm, p in sorted(added.items()):
            if lm in SKIP_MARKINGS:
                reports.append(f'SKIP-LIST  {cam} :: {lm} (collision de nom connue)')
                continue
            if not we_have:
                reports.append(f'CAM-ABSENTE  {cam} :: ADD {lm} @ {p}')
                continue
            if lm in mine:
                if mine[lm] == p:
                    continue
                reports.append(f'CONFLIT  {cam} :: {lm} nous={mine[lm]} rlx={p}')
                continue
            plan_add.append((cam, lm, p))

        for lm, (a, b) in sorted(moved.items()):
            d = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
            if lm in SKIP_MARKINGS:
                reports.append(f'SKIP-LIST  {cam} :: MOVE {lm} ({d:.1f}px, collision connue)')
                continue
            if not we_have or lm not in mine:
                reports.append(f'MOVE-CIBLE-ABSENTE  {cam} :: {lm} {a}->{b} ({d:.1f}px)')
                continue
            if mine[lm] != a and mine[lm] != b:
                reports.append(f'MOVE-DIVERGENT  {cam} :: {lm} nous={mine[lm]} rlx {a}->{b}')
                continue
            if mine[lm] == b:
                continue
            if d <= SNAP_PX:
                plan_snap.append((cam, lm, a, b, d))
            else:
                reports.append(f'MOVE>2px  {cam} :: {lm} {a}->{b} ({d:.1f}px) — jugement requis')

        for old_name, new_name, p in renames:
            reports.append(f'RENAME  {cam} :: {old_name} -> {new_name} @ {p} — '
                           f'fusion/provenance, prouver par geometrie (cf. Vake 07-07)')
        for lm, p in sorted(removed.items()):
            reports.append(f'DEL(rlx)  {cam} :: {lm} @ {p} — non applique')

    print(f'PLAN — ADD: {len(plan_add)} | SNAP<= {SNAP_PX}px: {len(plan_snap)} | '
          f'poses rlx changees (SKIP): {n_pose} | reports: {len(reports)}\n')
    for cam, lm, p in plan_add:
        print(f'  ADD   {cam} :: {lm} @ {p}')
    for cam, lm, a, b, d in plan_snap:
        print(f'  SNAP  {cam} :: {lm} {a} -> {b} ({d:.1f}px)')
    if reports:
        print('\nREPORTS (jugement humain / doctrine):')
        for r in reports:
            print(f'  {r}')

    if not args.apply:
        print('\nDRY-RUN. --apply pour ecrire ADD+SNAP et geler le sync_state.')
        return

    if plan_add or plan_snap:
        shutil.copy('gtamapdata/pixels.json', 'gtamapdata/pixels.json.bak_rlxsync')
        shutil.copy('gtamapdata/landmarks.json', 'gtamapdata/landmarks.json.bak_rlxsync')
        n_skel = 0
        for cam, lm, p in plan_add:
            ours_px.setdefault(cam, {})[lm] = p
            if lm not in ours_lms:
                zones = [lm_zone.get(l) for l in ours_px.get(cam, {}) if lm_zone.get(l)]
                zone = max(set(zones), key=zones.count) if zones else None
                ours_lms[lm] = {"xyz": None, "source_cameras": [], "error_m": None,
                                "zone": zone, "author": "rlx"}
                n_skel += 1
        for cam, lm, a, b, d in plan_snap:
            ours_px[cam][lm] = b
        with open('gtamapdata/pixels.json', 'w') as f:
            json.dump(ours_px, f, indent=2, ensure_ascii=True); f.write('\n')
        with open('gtamapdata/landmarks.json', 'w') as f:
            json.dump(ours_lms, f, indent=2, ensure_ascii=True); f.write('\n')
        print(f'\nECRIT: +{len(plan_add)} markings, {len(plan_snap)} snaps, '
              f'{n_skel} skeletons (backups .bak_rlxsync)')
    with open(STATE, 'w') as f:
        json.dump({'last_synced': head, 'ref': args.ref,
                   'date': __import__('datetime').date.today().isoformat()}, f, indent=1)
        f.write('\n')
    print(f'sync_state gele a {head}. Suite: python3 tools/cycle.py --tag rlx_sync --harvest --scan')


if __name__ == '__main__':
    main()
