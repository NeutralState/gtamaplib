#!/usr/bin/env python3
"""gen_misc_meshes.py — lot de meshes par extrusion V16 avec hauteur landmark. [MISC-MESH-V1 2026-09-30]

Chaque entree: nom -> liste de (polygones V16, hauteur toit (m abs) ou 'LM:<landmark>', sol heightmap).
Park Grove: 3 tours (V16 1621 / 1488 = etages courbes, 1756 = tour N), sommets = LMs (S)/(C)/(N) ~99-100 m.
Usage: PYTHONPATH=. python3 tools/gen_misc_meshes.py [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
D = lambda f: os.path.join(ROOT, 'gtamapdata', f)
SPEC = {
    'Park Grove Condominium': ([1756], 'LM:Park Grove Condominium (N)', '#67e8f9'),
    'Park Grove Condominium (C)': ([1621], 'LM:Park Grove Condominium (C)', '#67e8f9'),
    'Park Grove Condominium (S)': ([1488], 'LM:Park Grove Condominium (S)', '#67e8f9'),
    'Bank of America Financial Center (Miami Beach)': ([3466, 3465], 'LM:Bank of America Financial Center (NW)', '#93c5fd'),
}


def build():
    import v16_resect as RR
    F = {f['id']: f for f in json.load(open(D('v16_footprints.json')))['polygons']}
    L = json.load(open(D('landmarks.json'))); out = {}
    for name, (pids, h, col) in SPEC.items():
        E = []
        def seg(a, b): E.append([[round(float(v), 2) for v in a], [round(float(v), 2) for v in b]])
        for pid in pids:
            r = np.array(F[pid]['ring'], float); g = RR.ground(*r.mean(0))
            zt = float(L[h[3:]]['xyz'][2]) if isinstance(h, str) else float(h)
            zs = [g] + list(np.arange(g + 12, zt, 12.0)) + [zt]
            step = max(1, len(r) // 24)
            for z in zs:
                for i in range(len(r)): seg([*r[i], z], [*r[(i + 1) % len(r)], z])
            for p in r[::step]: seg([*p, g], [*p, zt])
        out[name] = {'color': col, 'world_edges': E, '_credit': 'Alexandre Leblanc (V16 + landmarks) + Claude Opus 5.5',
                     'note': 'MISC-MESH-V1 2026-09-30: extrusion V16 %s, toit = %s.' % (pids, h)}
    return out


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print(k, len(v['world_edges']))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = D('building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_misc_0930')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
