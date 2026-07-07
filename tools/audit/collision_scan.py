#!/usr/bin/env python3
"""
collision_scan.py -- WAR-SCAN-V1. Detecte a l'echelle les collisions de nom
et les pixels isoles qui polluent les triangulations.

Genese: session 2026-07-06, review manuelle de 4 outliers VC -> 4/4 etaient
des collisions de nom (des cams marquant des objets physiques differents sous
le meme nom de LM). Ce tool generalise ce diagnostic a tous les LM.

Methode, par LM avec xyz et >=2 observers non-exclus:
  1. erreur angulaire par observer (formule canonique cam_rms)
  2. MAJORITY = observers <= T_OK (8'), OUTLIERS = > T_BAD (15')
  3. les outliers sont pairwise-triangules ENTRE EUX:
     - sous-groupe coherent (<50m entre eux, >100m du LM) = COLLISION
       (ils marquent un VRAI autre objet -> renommer en sub-LM un jour)
     - isole = BADPIXEL (marking rate -> Fix Pixel ou exclusion)
  4. si majorite >=2 -> proposition: exclure les outliers, retrianguler.
     GATES apply: resid post <8', delta <15m, sinon REVIEW.
     Pas de majorite -> WAR, review manuel (crop map).

Usage:
  PYTHONPATH=. python3 tools/audit/collision_scan.py            # scan seul
  PYTHONPATH=. python3 tools/audit/collision_scan.py --plan     # + plan gated
  PYTHONPATH=. python3 tools/audit/collision_scan.py --apply    # execute le plan
  (--apply: exclude_marking + triangulate_lm CLI + snap z_constraint)

READ-ONLY sans --apply. Respecte excluded_markings.json et la blacklist.
"""
import argparse, json, math, os, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import numpy as np
import common

T_OK = 8.0        # arcmin: en dessous = majorite saine
T_BAD = 15.0      # arcmin: au dessus = outlier a classifier
CLUSTER_M = 50.0  # coherence interne d'une collision
FAR_M = 100.0     # distance min du LM courant pour parler d'un autre objet
GATE_RESID = 8.0  # arcmin, gate apply
GATE_DELTA = 15.0 # m, gate apply
BLACKLIST_LM = {'Amphitheater'}  # poses/LM proteges par preuve map

def ang_err(cam, mk, xyz):
    p = cam.get_pixel(xyz)
    if p is None:
        return None
    dx = (p[0] - mk[0]) * cam.hfov / cam.w * 60
    dy = (p[1] - mk[1]) * cam.vfov / cam.h * 60
    return math.hypot(dx, dy)

def pair_point(cam_a, mk_a, cam_b, mk_b):
    try:
        ra = (np.asarray(cam_a.xyz, float), np.asarray(cam_a.get_pixel_direction(mk_a), float))
        rb = (np.asarray(cam_b.xyz, float), np.asarray(cam_b.get_pixel_direction(mk_b), float))
        ang = math.degrees(math.acos(np.clip(np.dot(
            ra[1]/np.linalg.norm(ra[1]), rb[1]/np.linalg.norm(rb[1])), -1, 1)))
        if ang < 2.0:  # parallaxe insuffisante
            return None
        return common.ray_ls_point([ra, rb])
    except Exception:
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', action='store_true', help='afficher le plan gated')
    ap.add_argument('--apply', action='store_true', help='executer le plan gated')
    ap.add_argument('--top', type=int, default=40)
    args = ap.parse_args()

    lms = json.load(open('gtamapdata/landmarks.json'))
    px = json.load(open('gtamapdata/pixels.json'))
    obs_index = {}
    for cam_name, marks in px.items():
        for lm_name, p in marks.items():
            if p is None:
                continue
            if common.is_excluded_marking(cam_name, lm_name):
                continue
            obs_index.setdefault(lm_name, []).append((cam_name, p))

    cams_cache = {}
    def get_cam(name):
        if name not in cams_cache:
            try:
                cams_cache[name] = common.get_cam(name)
            except Exception:
                cams_cache[name] = None
        return cams_cache[name]

    findings = []
    for lm_name, entry in lms.items():
        xyz = (entry or {}).get('xyz')
        if not xyz or lm_name in BLACKLIST_LM:
            continue
        obs = obs_index.get(lm_name, [])
        if len(obs) < 2:
            continue
        errs = []
        for cam_name, mk in obs:
            cam = get_cam(cam_name)
            if cam is None:
                continue
            e = ang_err(cam, mk, xyz)
            if e is not None:
                errs.append((cam_name, mk, e))
        if len(errs) < 2:
            continue
        majority = [t for t in errs if t[2] <= T_OK]
        outliers = [t for t in errs if t[2] > T_BAD]
        if not outliers:
            continue

        # classifier les outliers: collision (coherents entre eux) vs badpixel
        collisions, badpixels = [], []
        used = set()
        for i, (ca, ma, ea) in enumerate(outliers):
            if i in used:
                continue
            group = [(ca, ma, ea)]
            pts = []
            for j in range(i + 1, len(outliers)):
                if j in used:
                    continue
                cb, mb, eb = outliers[j]
                pt = pair_point(get_cam(ca), ma, get_cam(cb), mb)
                if pt is None:
                    continue
                d_lm = np.linalg.norm(pt - np.asarray(xyz))
                if d_lm > FAR_M:
                    # coherence du groupe: tous les points de paire proches
                    if not pts or min(np.linalg.norm(pt - q) for q in pts) < CLUSTER_M:
                        group.append((cb, mb, eb)); pts.append(pt); used.add(j)
            used.add(i)
            if len(group) >= 2:
                collisions.append(group)
            else:
                badpixels.append(group[0])

        kind = 'WAR'
        if len(majority) >= 2:
            kind = 'FIXABLE'
        findings.append({
            'lm': lm_name, 'kind': kind, 'zone': (entry or {}).get('zone'),
            'n_obs': len(errs), 'n_major': len(majority),
            'worst': max(e for _, _, e in errs),
            'collisions': [[(c, round(e, 1)) for c, _, e in g] for g in collisions],
            'badpixels': [(c, round(e, 1)) for c, _, e in badpixels],
            'excl': [c for c, _, e in errs if e > T_BAD],
        })

    findings.sort(key=lambda f: -f['worst'])
    n_fix = sum(1 for f in findings if f['kind'] == 'FIXABLE')
    n_war = len(findings) - n_fix
    print(f'WAR-SCAN: {len(findings)} LM avec outlier(s) >15\'  '
          f'({n_fix} FIXABLE / {n_war} WAR sans majorite)\n')
    for f in findings[:args.top]:
        tags = []
        if f['collisions']:
            tags.append('COLLISION ' + ' | '.join(
                '+'.join(f'{c}({e}\')' for c, e in g) for g in f['collisions']))
        if f['badpixels']:
            tags.append('BADPIXEL ' + ', '.join(f'{c}({e}\')' for c, e in f['badpixels']))
        print(f"{f['kind']:7s} {f['lm'][:44]:44s} {str(f['zone'])[:12]:12s} "
              f"obs={f['n_obs']:2d} maj={f['n_major']:2d} worst={f['worst']:7.1f}'  {'; '.join(tags)}")
    if len(findings) > args.top:
        print(f'  ... +{len(findings) - args.top} (utilise --top)')

    if not (args.plan or args.apply):
        return

    # ---- plan gated sur les FIXABLE ----
    print('\n=== PLAN (FIXABLE seulement, gates resid<%g\' delta<%gm) ===' % (GATE_RESID, GATE_DELTA))
    applied = reviews = 0
    for f in findings:
        if f['kind'] != 'FIXABLE':
            continue
        lm = f['lm']
        cmds = [['python3', 'tools/exclude_marking.py', c, lm, '--apply'] for c in f['excl']]
        if not args.apply:
            print(f"  {lm}: exclure {f['excl']} puis retrianguler (dry)")
            reviews += 1
            continue
        for cmd in cmds:
            subprocess.run(cmd, capture_output=True, text=True)
        dry = subprocess.run(['python3', 'tools/triangulate_lm.py', lm],
                             capture_output=True, text=True).stdout
        import re
        mr = re.search(r'Max residual: ([\d.]+)', dry)
        md = re.search(r'Delta from current: ([\d.]+)', dry)
        if not (mr and md):
            print(f'  REVIEW {lm}: triangulation dry illisible (sources insuffisantes?) — exclusions gardees')
            reviews += 1
            continue
        resid, delta = float(mr.group(1)), float(md.group(1))
        if resid < GATE_RESID and delta < GATE_DELTA:
            subprocess.run(['python3', 'tools/triangulate_lm.py', lm, '--apply'],
                           capture_output=True, text=True)
            zc = (lms[lm] or {}).get('z_constraint')
            if zc and zc.get('type') == 'fixed':
                cur = json.load(open('gtamapdata/landmarks.json'))
                cur[lm]['xyz'][2] = float(zc['value'])
                with open('gtamapdata/landmarks.json', 'w') as fh:
                    json.dump(cur, fh, indent=2, ensure_ascii=True); fh.write('\n')
            print(f"  APPLIED {lm}: excl {f['excl']}, retri {resid:.2f}' / {delta:.1f}m")
            applied += 1
        else:
            print(f"  REVIEW  {lm}: excl gardees, retri HORS GATE ({resid:.2f}' / {delta:.1f}m)")
            reviews += 1
    print(f'\napplied: {applied} | review: {reviews}')
    if args.apply:
        print('Suite: tiers -> bundle --cleanup -> guarded_apply -> snapshot -> CI')

if __name__ == '__main__':
    main()
