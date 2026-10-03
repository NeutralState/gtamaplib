#!/usr/bin/env python3
"""gen_i404_east.py — I-404 a l'est du pont Downtown (x 60 -> 177) + debut des deux bretelles vers le sud. [I404-EAST-V1 2026-10-03]

Manquait dans la Vice City Postcard (Alexandre): le tablier continue a gauche de la grande roue au-dela du pont
'I-404 Causeway Bridge (Downtown)' (x -164..68, 20.6 m mesure).
Plan = traces V16 #727272 (leak map): I-404 = contour ferme (deux chaussees, largeur 18), bretelles = traces largeur 12.
Hauteur (dessus du tablier) LUE dans la Vice City Postcard: ligne du tablier relevee sur 9 colonnes, rayon x trace V16.
Les lectures sont ~2 m au-dessus du pont mesure la ou il existe (x -100..36: 22-23 m lus vs 20.6 mesure, flou + garde-corps):
decalage -2 m applique. Profil: x 60: 20.6, 78: 19.5, 118: 16.9, 156: 14.2; bretelles 14.2 jusqu'au dernier point lu
(y >= 400); au-dela cache par l'immeuble du premier plan -> non emis.
Usage: PYTHONPATH=. python3 tools/gen_i404_east.py [--out f.json] [--apply]
"""
import json, os, sys, shutil, subprocess
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from gen_keys_bridges import Bridge
import v16_resect as RR
SVG = os.path.expanduser('~/Downloads/GTA VI Community Mapping Project-3.svg')
CACHE = os.path.join(ROOT, 'tools', 'generated', 'i404_east_strokes.json')
PROF = ([55, 68, 78, 118, 156, 180], [20.6, 20.6, 19.5, 16.9, 14.2, 14.2])
COLOR = '#9ca3af'


def strokes():
    if not os.path.exists(CACHE):
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'v16', 'svg_strokes.py'), SVG, '-300', '900', '-200', '800', CACHE],
                       check=True, env=dict(os.environ, V16_X0='16991'), capture_output=True)
    return [np.array(s['ring'], float) for s in json.load(open(CACHE))['strokes'] if s['color'] == '#727272']


def dens(r, step=2.0):
    return np.vstack([np.linspace(a, b, max(2, int(np.hypot(*(b - a)) / step))) for a, b in zip(r[:-1], r[1:])])


def chains(P, m):
    """morceaux contigus de P ou m est vrai."""
    out, cur = [], []
    for p, k in zip(P, m):
        if k: cur.append(p)
        elif cur: out.append(np.array(cur)); cur = []
    if cur: out.append(np.array(cur))
    return [c for c in out if len(c) > 10]


def simplify(c, step=6.0):
    s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(c, axis=0).T))]); t = np.arange(0, s[-1], step)
    return np.c_[np.interp(t, s, c[:, 0]), np.interp(t, s, c[:, 1])]


def build():
    S = strokes(); I404 = next(r for r in S if r[:, 0].min() < -1000)
    ramps = [r for r in S if 130 < r[:, 0].min() < 200]
    out = {}
    zt = lambda x: float(np.interp(x, *PROF))
    parts = []
    # [I404-UNIFIED 2026-10-03] le tablier de l'I-404 est maintenant dans tools/gen_interchange.py (viaduc continu); ici seulement les bretelles
    for k, r in enumerate(ramps):
        P = dens(r); parts += [('I-404 Ramp South (East) %d' % (k + 1), c, 6.0) for c in chains(P, P[:, 1] >= 400)]
    for name, c, hw in parts:
        c = simplify(c if c[0][0] < c[-1][0] or 'Ramp' in name else c[::-1])
        br = Bridge(poly=c); L = br.S[-1]
        zfun = (lambda s, br=br: zt(br.frame(s)[0][0]) - 1.8) if 'Viaduct' in name else (lambda s: PROF[1][-1] - 1.8)
        br.deck(0.0, L, zfun, -hw, hw, depth=1.8, parapet=1.0, step=6.0, frame=18.0)
        for s in np.arange(10, L - 5, 30.0):
            g = RR.ground(*br.frame(s)[0])
            if zfun(s) - g > 3: br.bent(s, zfun, -hw + 1, hw - 1, ncol=2 if hw > 7 else 1, col=1.6, zw=g, cap=1.3)
        out[name] = {'color': COLOR, 'world_edges': br.E, '_credit': 'Alexandre Leblanc (V16 leak) + Claude Opus 5.5',
                     'note': 'I404-EAST-V1 2026-10-03: plan = trace V16 (leak); dessus du tablier LU dans la Vice City Postcard (9 colonnes, '
                             'decalage -2 m cale sur le pont I-404 Downtown mesure 20.6 m): x 68 20.6 -> 156 14.2 m; bretelles 14.2 m '
                             'jusqu au dernier point vu (y >= 400). Voir tools/gen_i404_east.py'}
    return out


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print('%-46s %5d aretes' % (k, len(v['world_edges'])))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = os.path.join(ROOT, 'gtamapdata', 'building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_i404east_1003')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
