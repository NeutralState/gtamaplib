#!/usr/bin/env python3
"""WAR-TASKS-V1: extension --tasks du WAR-SCAN — chaque guerre 1v1 devient une
tache UI concrete: les 3 meilleurs 3e temoins (cams calibrees qui voient le
point, pas encore marquantes), tries par DISTANCE (un medium a 800m bat un
anchor a 9km), avec pixel projete et distance. Idempotent."""
import sys
p = 'tools/audit/collision_scan.py'
src = open(p).read()
if 'WAR-TASKS-V1' in src:
    print('ok  deja patche'); sys.exit(0)

a1 = "    ap.add_argument('--top', type=int, default=40)"
b1 = """    ap.add_argument('--top', type=int, default=40)
    ap.add_argument('--tasks', action='store_true',
                    help='pour chaque WAR: suggerer les 3e temoins (taches UI)')"""
assert a1 in src, 'ancre argparse introuvable'
src = src.replace(a1, b1, 1)

a2 = """    if not (args.plan or args.apply):
        return"""
b2 = """    # ── WAR-TASKS-V1: chaque guerre 1v1 -> tache UI concrete ────────────
    # Une WAR n'a pas de majorite; la resolution = un 3e temoin independant.
    # On projette le xyz courant dans toutes les cams calibrees (anchor/high/
    # medium) qui ne marquent pas deja le LM, triees par DISTANCE puis tier
    # (un medium a 800m bat un anchor a 9km). Le xyz courant peut etre faux
    # (c'est la guerre) — le 3e temoin tranche peu importe ou il tombe.
    if args.tasks:
        import math as _math
        tc = {}
        try:
            _tiers = json.load(open('tools/generated/confidence_tiers.json'))
            tc = _tiers.get('cameras', _tiers.get('cams', {}))
        except Exception:
            pass
        cams_meta = json.load(open('gtamapdata/cameras.json'))
        rank = {'anchor': 0, 'high': 1, 'medium': 2}
        print('\\n=== WAR-TASKS (3e temoins candidats, taches UI) ===')
        wars = [f for f in findings if f['kind'] == 'WAR']
        for f in wars:
            xyz = (lms.get(f['lm']) or {}).get('xyz')
            if not xyz:
                continue
            cands = []
            for cn, meta in cams_meta.items():
                tier = (tc.get(cn) or {}).get('tier')
                if tier not in rank:
                    continue
                if f['lm'] in px.get(cn, {}):
                    continue
                cam = get_cam(cn)
                if cam is None:
                    continue
                try:
                    p2 = cam.get_pixel(xyz)
                except Exception:
                    continue
                w, h = meta.get('size', [0, 0])
                if p2 is None or not (0 <= p2[0] <= w and 0 <= p2[1] <= h):
                    continue
                d = _math.dist(xyz, meta['xyz'])
                if d > 12000:
                    continue
                cands.append((d, rank[tier], cn, tier, p2))
            cands.sort()
            wm = f.get('worst_m')
            print(f"\\n  WAR {f['lm']}  (worst {f['worst']:.0f}'"
                  + (f'/{wm:.1f}m' if wm is not None else '') + ')')
            if not cands:
                print('      aucun 3e temoin calibre ne voit ce point — '
                      'frame/marking manuel requis')
            for d, _r, cn, tier, p2 in cands[:3]:
                print(f'      marquer sur {cn} [{tier}] @ ({p2[0]:.0f},{p2[1]:.0f}), {d:.0f}m')

    if not (args.plan or args.apply):
        return"""
assert a2 in src, 'ancre plan/apply introuvable'
src = src.replace(a2, b2, 1)
open(p, 'w').write(src)
print('collision_scan patche: WAR-TASKS-V1')
