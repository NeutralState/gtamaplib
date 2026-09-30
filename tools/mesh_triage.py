#!/usr/bin/env python3
"""mesh_triage.py — qui a tort, le mesh ou la cam ? [MESH-TRIAGE-V1 2026-09-30]

Pour chaque clic sur un landmark qui est un point d'un mesh (meme nom), on mesure si le RAYON du clic
passe par le volume du mesh (distance minimale rayon <-> volume, en m) et, s'il le rate, le decalage en
pixels entre le clic et la projection du point du mesh le plus proche du rayon.
  - par LANDMARK: si la plupart des cams (>=3) ratent le mesh alors que leurs rayons se croisent serre
    -> le MESH est faux (mauvais polygone / mauvais batiment)
  - par CAM: si une cam rate les meshes pour plusieurs batiments, dans une direction COHERENTE
    -> la CAM est a recaler (biais yaw/pitch mesure en arcmin)
Rapport seulement. Usage: PYTHONPATH=. python3 tools/mesh_triage.py [--json out]
"""
import json, os, sys
THIS = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, THIS); sys.path.insert(0, os.path.dirname(THIS))
import numpy as np
import common
from mesh_triangulate import prisms, solid_dist, SUFFIX, D
import re

MISS_M = 6.0


def main():
    C = json.load(open(D('cameras.json'))); P = json.load(open(D('pixels.json'))); L = json.load(open(D('landmarks.json')))
    M = json.load(open(D('building_meshes_procedural.json')))
    norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower()); NM = {norm(k): k for k in M}

    def own(lm):
        r = lm
        for _ in range(4):
            if norm(r) in NM: return NM[norm(r)]
            r2 = SUFFIX.sub('', r).strip()
            if r2 == r: return None
            r = r2
        return None
    PR = {}; EG = {}; CM = {}
    try:
        X_ = json.load(open(D('excluded_markings.json')))
        EXCL = set()
        for cam_, lms_ in (X_.items() if isinstance(X_, dict) else []):
            for l_ in (lms_ if isinstance(lms_, list) else []): EXCL.add((cam_, l_))
        for e in ([] if isinstance(X_, dict) else X_):
            if isinstance(e, dict) and e.get('cam') and e.get('lm'): EXCL.add((e['cam'], e['lm']))
            elif isinstance(e, (list, tuple)) and len(e) >= 2: EXCL.add((e[0], e[1]))
    except Exception: EXCL = set()
    skip_cam = lambda n: 'EXCLU' in ((C[n].get('note') or '') + (C[n].get('notes') or ''))[:40]
    obs = []
    for k, v in L.items():
        if not isinstance(v, dict) or not v.get('xyz'): continue
        m = own(k)
        if not m or not M[m].get('world_edges'): continue
        if m not in PR: PR[m] = prisms(M[m]['world_edges']); EG[m] = np.asarray(M[m]['world_edges'], float)
        X = np.array(v['xyz'], float)
        for n, p in P.items():
            if not isinstance(p, dict) or k not in p or n not in C or not C[n].get('xyz') or not C[n].get('ypr'): continue
            if skip_cam(n) or (n, k) in EXCL: continue
            try:
                if n not in CM: CM[n] = common.get_cam(n)
                cm = CM[n]; d = np.array(cm.get_pixel_direction(tuple(p[k])), float); d /= np.linalg.norm(d)
            except Exception: continue
            o = np.array(C[n]['xyz'], float); tl = float((X - o) @ d)
            if tl <= 0: continue
            ts = np.linspace(max(1.0, tl - 400), tl + 400, 161)
            ds = [solid_dist(o + d * t, PR[m]) for t in ts]; i = int(np.argmin(ds)); miss = float(ds[i]); Q = o + d * ts[i]
            # point du mesh le plus proche du rayon (sur les aretes) -> projection -> decalage en pixels
            E = EG[m]; a = E[:, 0]; ab = E[:, 1] - a; t = np.clip(((Q - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-9), 0, 1)
            Z = a + ab * t[:, None]; Zc = Z[np.argmin(np.linalg.norm(Z - Q, axis=1))]
            q = cm.get_pixel(list(Zc)); du = None
            if q is not None and miss > 0.5:
                W = C[n]['size'][0]; hf = cm.fov[0] if cm.fov[0] else None
                du = ((np.array(q, float) - np.array(p[k], float)) / W * (hf or 60) * 60).tolist()   # arcmin
            obs.append({'lm': k, 'mesh': m, 'cam': n, 'miss_m': round(miss, 1), 'dist_m': round(tl, 0), 'shift_arcmin': du})
    return obs


if __name__ == '__main__':
    obs = main()
    # --- par landmark
    by_lm = {}
    for o in obs: by_lm.setdefault(o['lm'], []).append(o)
    mesh_bad = {}
    for k, os_ in by_lm.items():
        if len(os_) < 3: continue
        f = np.mean([o['miss_m'] > MISS_M for o in os_])
        if f >= 0.7: mesh_bad.setdefault(os_[0]['mesh'], []).append((k, len(os_), f, float(np.median([o['miss_m'] for o in os_]))))
    print('== A. MESHES A REFAIRE (>=3 cams et >=70 %% des cams ratent le mesh): %d' % len(mesh_bad))
    for m, ks in sorted(mesh_bad.items(), key=lambda kv: -max(x[3] for x in kv[1])):
        print('   %-38s ' % m[:38] + ' | '.join('%s: %d cams, %.0f%% ratent, mediane %.0f m' % (SUFFIX.findall(k)[-1].strip() if SUFFIX.findall(k) else k, n, 100 * f, md) for k, n, f, md in ks))
    bad_meshes = set(mesh_bad)
    # --- par cam (hors meshes deja juges faux)
    by_cam = {}
    for o in obs:
        if o['mesh'] in bad_meshes: continue
        by_cam.setdefault(o['cam'], []).append(o)
    rows = []
    for n, os_ in by_cam.items():
        bld = {o['mesh'] for o in os_}
        if len(bld) < 2: continue
        miss = [o for o in os_ if o['miss_m'] > MISS_M and o['shift_arcmin']]
        fm = len({o['mesh'] for o in miss}) / len(bld)
        if not miss: continue
        S = np.array([o['shift_arcmin'] for o in miss]); mv = np.median(S, 0)
        coh = float(np.linalg.norm(S.mean(0)) / max(np.mean(np.linalg.norm(S, axis=1)), 1e-6))
        rows.append((fm, n, len(bld), len({o['mesh'] for o in miss}), mv, coh, sorted({o['mesh'] for o in miss})))
    print('\n== B. CAMS A RECALER (ratent les meshes de >=50 %% de leurs batiments, direction coherente >= 0.7)')
    for fm, n, nb, nm, mv, coh, ms in sorted(rows, key=lambda r: (-r[0], -r[3])):
        if fm >= 0.5 and coh >= 0.7:
            print('   %-40s %d/%d batiments rates, biais median  u %+.1f\'  v %+.1f\'  (coherence %.2f)  %s' % (n[:40], nm, nb, mv[0], mv[1], coh, ', '.join(x[:22] for x in ms[:5])))
    print('\n   (a surveiller: rate >=50 % mais direction incoherente)')
    for fm, n, nb, nm, mv, coh, ms in sorted(rows, key=lambda r: -r[0]):
        if fm >= 0.5 and coh < 0.7: print('   %-40s %d/%d batiments, coherence %.2f' % (n[:40], nm, nb, coh))
    if '--json' in sys.argv: json.dump(obs, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
