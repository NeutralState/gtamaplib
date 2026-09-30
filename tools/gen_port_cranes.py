#!/usr/bin/env python3
"""gen_port_cranes.py — portiques a conteneurs (STS) de Port Vice City. [PORT-CRANES-V1 2026-09-30]

Plan = polygones V16 3132-3140: chaque grue est dessinee en plan (portique 29 x 21 m, local des machines, arriere-bec,
fleche de 47 m au-dessus de l'eau), axe = grand axe du polygone, fleche du cote s < 0 (eau).
Hauteurs = landmarks: sommet du chevalet 'Container Crane (n)' (72-82 m, 2-6 cams), dessous de fleche 'CC (n) (BB2)'
(40-45 m) -> fleche a z 44 (mediane) pour les grues sans BB2.
Usage: PYTHONPATH=. python3 tools/gen_port_cranes.py [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
D = lambda f: os.path.join(ROOT, 'gtamapdata', f)
POLYS = [3140, 3139, 3138, 3137, 3136, 3135, 3134, 3133, 3132]


def build():
    import v16_resect as RR
    F = {f['id']: f for f in json.load(open(D('v16_footprints.json')))['polygons']}
    L = json.load(open(D('landmarks.json')))
    tops = {k: np.array(v['xyz']) for k, v in L.items() if k.startswith('Container Crane (') and v and v.get('xyz')}
    bb2 = {k: np.array(v['xyz']) for k, v in L.items() if k.startswith('CC (') and k.endswith('(BB2)') and v and v.get('xyz')}
    out = {}
    for pid in POLYS:
        r = np.array(F[pid]['ring'], float); c = r.mean(0); u = np.linalg.svd(r - c)[2][0]; n = np.array([-u[1], u[0]])
        s = (r - c) @ u
        if s.min() > -40: u, n = -u, -n                      # fleche (s = -65) du cote eau
        g = RR.ground(*c)
        top = min(tops.items(), key=lambda kv: np.hypot(*(kv[1][:2] - c)))
        name = top[0]; zt = float(top[1][2]) if np.hypot(*(top[1][:2] - c)) < 30 else 74.0
        b = [v for v in bb2.values() if np.hypot(*(v[:2] - c)) < 40]
        zb = float(np.mean([v[2] for v in b])) if b else 44.0
        E = []
        P = lambda si, wi, z: [round(float((c + u * si + n * wi)[0]), 2), round(float((c + u * si + n * wi)[1]), 2), round(float(z), 2)]
        def seg(a, b_): E.append([a, b_])
        def box(s0, s1, w0, w1, z0, z1):
            cs = [(s0, w0), (s1, w0), (s1, w1), (s0, w1)]
            for z in (z0, z1):
                for i in range(4): seg(P(*cs[i], z), P(*cs[(i + 1) % 4], z))
            for q in cs: seg(P(*q, z0), P(*q, z1))
        zp = zb - 4.0                                        # poutre du portique sous la fleche
        for si in (-15.5, 9.8):                              # 4 jambes + traverses
            for wi in (-9.2, 9.2): box(si - 0.8, si + 0.8, wi - 0.8, wi + 0.8, g, zp)
            seg(P(si, -9.2, zp), P(si, 9.2, zp)); seg(P(si, -9.2, g + 6), P(si, 9.2, g + 6))
            seg(P(si, -9.2, g + 6), P(si, 9.2, zp)); seg(P(si, 9.2, g + 6), P(si, -9.2, zp))
        for wi in (-9.2, 9.2):
            seg(P(-15.5, wi, zp), P(9.8, wi, zp)); seg(P(-15.5, wi, g + 1.2), P(9.8, wi, g + 1.2))   # longerons + bogies
        box(-65.0, 38.4, -3.6, 3.6, zb, zb + 3.0)                                  # fleche + arriere-bec (caisson)
        for si in np.arange(-60, 38, 8.0): seg(P(si, -3.6, zb), P(si + 4, 3.6, zb + 3))
        box(11.8, 18.8, -6.0, 6.0, zb + 3.0, zb + 8.0)                             # local des machines
        box(-17.4, -12.0, 3.8, 9.5, zp - 4, zp)                                    # cabine sous la fleche
        ap = [P(-2.0, -4.0, zt), P(-2.0, 4.0, zt)]                                 # chevalet (A-frame)
        seg(*ap)
        for wi, a in ((-4.0, ap[0]), (4.0, ap[1])):
            w2 = -9.2 if wi < 0 else 9.2
            seg(P(-15.5, w2, zp), a); seg(P(9.8, w2, zp), a)
            for si in (-64.0, -40.0, -25.0): seg(a, P(si, wi * 0.8, zb + 3))    # haubans avant
            for si in (25.0, 38.0): seg(a, P(si, wi * 0.8, zb + 3))             # haubans arriere
        out[name] = {'color': '#f59e0b', 'world_edges': E, '_credit': 'Alexandre Leblanc (V16 + landmarks) + Claude Opus 5.5',
                     'note': 'PORT-CRANES-V1 2026-09-30: plan = polygone V16 %d (portique, local, arriere-bec, fleche 47 m au-dessus de l eau); '
                             'sommet du chevalet = landmark %s (z %.1f), fleche z %.1f (%s).' % (pid, name, zt, zb, 'LM BB2' if b else 'mediane des BB2')}
    return out


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print(k, len(v['world_edges']), v['note'][-60:])
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = D('building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_cranes_0930')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
