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
    # Wheelabrator: polygone V16 1302 (etage) decoupe en blocs; hauteurs = LMs (N: W/R/NW 55 m; S: TW/TE 63 m); bande
    # large et bloc median ESTIMES (45 / 40 m, entre les deux); cheminee: xy + sommet = LM (2 cams, colle dans Panorama; le cercle V16 1301 est 46 m plus au NE), r 5 m (V16)
    'Wheelabrator South Broward (North Hall)': ('RECT', [(-2429.2, 2669.0), (-2276.8, 2669.0), (-2278.3, 2704.3), (-2429.2, 2705.1)], 55.2, '#94a3b8'),
    'Wheelabrator South Broward (Boiler Band)': ('RECT', [(-2444.0, 2641.4), (-2262.8, 2642.4), (-2263.0, 2668.6), (-2444.4, 2669.0)], 45.0, '#94a3b8'),
    'Wheelabrator South Broward (Middle)': ('RECT', [(-2387.9, 2615.0), (-2297.8, 2614.5), (-2298.3, 2641.4), (-2388.3, 2641.7)], 40.0, '#94a3b8'),
    'Wheelabrator South Broward (South Hall)': ('RECT', [(-2370.5, 2557.0), (-2312.2, 2557.6), (-2313.1, 2614.2), (-2371.0, 2614.5)], 63.1, '#94a3b8'),
    'Wheelabrator South Broward (Stack)': ('CYL', (-2374.7, 2505.8, 5.1), 'LM:Wheelabrator South Broward', '#94a3b8'),
    'Bank of America Financial Center (Miami Beach)': ([3466, 3465], 'LM:Bank of America Financial Center (NW)', '#93c5fd'),
}


def build():
    import v16_resect as RR
    F = {f['id']: f for f in json.load(open(D('v16_footprints.json')))['polygons']}
    L = json.load(open(D('landmarks.json'))); out = {}
    for name, (pids, h, col) in [(k, v[-3:]) if v[0] not in ('RECT', 'CYL') else (k, (v, v[2], v[3])) for k, v in SPEC.items()]:
        E = []
        def seg(a, b): E.append([[round(float(v), 2) for v in a], [round(float(v), 2) for v in b]])
        if isinstance(pids, tuple) and pids[0] == 'RECT': rings = [np.array(pids[1], float)]
        elif isinstance(pids, tuple) and pids[0] == 'CYL':
            cx, cy, rr = pids[1]; rings = [np.array([(cx + rr * np.cos(a), cy + rr * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 14, endpoint=False)])]
        else: rings = [np.array(F[pid]['ring'], float) for pid in pids]
        for r in rings:
            g = RR.ground(*r.mean(0))
            zt = float(L[h[3:]]['xyz'][2]) if isinstance(h, str) else float(h)
            if name.endswith('(Stack)'): zt -= 0.0
            zs = [g] + list(np.arange(g + 12, zt, 12.0)) + [zt]
            step = max(1, len(r) // 24)
            for z in zs:
                for i in range(len(r)): seg([*r[i], z], [*r[(i + 1) % len(r)], z])
            for p in r[::step]: seg([*p, g], [*p, zt])
        out[name] = {'color': col, 'world_edges': E, '_credit': 'Alexandre Leblanc (V16 + landmarks) + Claude Opus 5.5',
                     'note': 'MISC-MESH-V1 2026-09-30: extrusion V16 %s, toit = %s.' % (pids if not isinstance(pids, tuple) else pids[0] + ' (V16 1302/1301)', h)}
    return out


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print(k, len(v['world_edges']))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = D('building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_misc_0930')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
