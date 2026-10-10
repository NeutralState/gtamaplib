#!/usr/bin/env python3
"""gen_interchange.py — echangeur I-97 / I-404 (Downtown) en mesh. [INTERCHANGE-V1 2026-10-03]

Plan = V16 (Alexandre: l'autoroute V16 = leak map, exacte): chaque bretelle est un trace #727272 distinct de la SVG
(axe + largeur 12); les deux autoroutes sont des contours fermes (I-97 = trace 6, I-404 = trace 15).
Topologie lue dans la SVG (croisements / raccords des traces): bretelles exterieures 2,3,4,5 (raccordees aux deux
autoroutes), bretelles interieures 7,8 (partent de 5, finissent sur 3) et 9,10 (partent de 2, finissent sur 4) qui
traversent le centre du stack (~(-940, 570)).
Hauteurs (haut du tablier):
  - I-404 au centre: ~37 m MESURE (Explosion: dessus du tablier 37-40 m sur 7 colonnes; Jason 05: bande eclairee sous le
    tablier a 33-34 m); x=-1075: 33 m (Jason 05: 29-30 m sous le tablier);
    21 m a x=-68 MESURE (Convertible, cam sur le tablier: 22.6 m - 1.3 m); 20.6 m au pont Downtown (CREST, deja mesure).
  - I-97: 12 m ESTIME (Explosion est sur l'I-97 a 15.5 m, 1.2 km au sud; passe sous tout le stack).
  - niveaux des bretelles interieures ESTIMES par l'ordre des niveaux (ordre de dessin SVG: 6 < 7,8 < 9,10 < 15,
    coherent avec l'I-404 mesuree au sommet): 7/8 = 18.5 m, 9/10 = 25 m (degagement 6.5 m).
  - I-404 prolongee jusqu'au pont deja mesure (I-404 Causeway Bridge (Downtown), x=-164, 20.6 m) ou se trouve la cam
    Convertible (21 m mesure); entre les deux l'I-404 DESCEND (Alexandre, vu dans Convertible: crete a ~30 m de la cam, voitures
    au-dela a ~4-9 m vers x=-450): ~8 m a x=-600..-450 MESURE dans Biplane (Video) v2811 (bord droit du tablier + piles); remontee lue dans Jason 05
    (bande eclairee ~3.3 m sous le dessus: dessus ~30 m a x=-800, ~36.5 m a -880); troncon -600..-800 cache par le fusil (pente ~10 % ESTIMEE). Voies laterales 13/14 a la hauteur de l'I-404.
  - raccords: une bretelle prend la hauteur du trace qu'elle rejoint a ses extremites; profil lineaire entre points
    de controle, pente limitee.
Usage: PYTHONPATH=. python3 tools/gen_interchange.py [--out f.json] [--apply]
"""
import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import paths as _P   # [PATHS-V1]
import json, os, sys, shutil, subprocess
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from gen_keys_bridges import Bridge
import v16_resect as RR
SVG = _P.asset('GTA VI Community Mapping Project-3.svg')
CACHE = os.path.join(ROOT, 'tools', 'generated', 'interchange_strokes.json')
WIN = (-1300, -600, 300, 1100)
CENTER = np.array([-940.0, 570.0])
LEVEL = {6: 12.0, 7: 18.5, 8: 18.5, 9: 25.0, 10: 25.0}
COLOR = '#9ca3af'


def strokes():
    if not os.path.exists(CACHE):
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'v16', 'svg_strokes.py'), SVG, *map(str, WIN), CACHE],
                       check=True, env=dict(os.environ, V16_X0='16991'), capture_output=True)
    return [np.array(s['ring'], float) for s in json.load(open(CACHE))['strokes'] if s['color'] == '#727272']


def z_i404(x):
    """haut du tablier de l'I-404 en fonction de x (mesures: centre 37 (Explosion 37-40 / Jason 05 33-34 sous le tablier), x=-1075 33 (Jason 05), pont Downtown 20.6 (Convertible 21); ouest de -1100 ESTIME)."""
    return float(np.interp(x, [-1440, -1250, -1075, -980, -880, -800, -600, -450, -164, 68, 78, 118, 156, 200], [20.0, 28.0, 33.0, 37.0, 36.5, 30.0, 8.0, 8.0, 20.6, 20.6, 19.5, 16.9, 14.2, 14.2]))


def zmain(i, p):
    return LEVEL[6] if i == 6 else z_i404(p[0])


def cum(r): return np.concatenate([[0], np.cumsum(np.hypot(*np.diff(r, axis=0).T))])


def proj(r, p):
    """abscisse curviligne du point de r le plus proche de p, et distance."""
    C = cum(r); best = (1e9, 0.0)
    for k in range(len(r) - 1):
        a, b = r[k], r[k + 1]; L = np.hypot(*(b - a))
        t = np.clip(np.dot(p - a, b - a) / max(L * L, 1e-9), 0, 1); d = np.hypot(*(a + t * (b - a) - p))
        if d < best[0]: best = (d, C[k] + t * L)
    return best[1], best[0]


def build():
    R = strokes(); out = {}
    Z = {}                                  # trace -> (s_knots, z_knots)
    # bretelles: points de controle = extremites (hauteur du trace rejoint) + passage au centre (niveau)
    PARENT = {2: (6, 15), 3: (15, 6), 4: (6, 15), 5: (15, 6), 7: (5, 3), 8: (5, 3), 9: (2, 4), 10: (2, 4)}
    order = [2, 3, 4, 5, 7, 8, 9, 10]
    for it in range(3):
        for i in order:
            r = R[i]; C = cum(r); a, b = PARENT[i]
            def zat(j, p):
                if j in (6, 15): return zmain(j, p)
                s, _ = proj(R[j], p); return float(np.interp(s, *Z[j])) if j in Z else 15.0
            ks, kz = [0.0, C[-1]], [zat(a, r[0]), zat(b, r[-1])]
            if i in LEVEL:
                s, d = proj(r, CENTER)
                if d < 60: ks.insert(1, s); kz.insert(1, LEVEL[i])
            Z[i] = (np.array(ks), np.array(kz))
    for i in (13, 14):                         # voies laterales est (les 2 bouts touchent l'I-404): hauteur de l'I-404
        r = R[i]; C = cum(r); Z[i] = (np.array([0.0, C[-1]]), np.array([z_i404(r[0][0]), z_i404(r[-1][0])]))
    order = order + [13, 14]
    E_all = {}
    # bretelles: tablier 12 m (axe V16), piles tous les 35 m
    for i in order:
        r = R[i]; C = cum(r); br = Bridge(poly=r)
        zt = lambda s, i=i: float(np.interp(s, *Z[i]))
        zb = lambda s, zt=zt: zt(s) - 1.8
        # parties au-dessus du sol seulement (+2.5 m)
        ss = np.arange(0, C[-1], 5.0); up = [zt(s) - RR.ground(*br.frame(s)[0]) > 2.5 for s in ss]
        runs = []; st = None
        for s, u in zip(ss, up):
            if u and st is None: st = s
            if not u and st is not None: runs.append((st, s)); st = None
        if st is not None: runs.append((st, C[-1]))
        for s0, s1 in runs:
            if s1 - s0 < 10: continue
            br.deck(s0, s1, zb, -6.0, 6.0, depth=1.8, parapet=1.0, step=8.0, frame=24.0)
            for s in np.arange(s0 + 15, s1 - 10, 35.0):
                g = RR.ground(*br.frame(s)[0])
                if zb(s) - g > 4: br.bent(s, zb, -5.0, 5.0, ncol=1, col=1.8, zw=g, cap=1.4)
        E_all['Interchange I-97/I-404 Ramp %d' % i] = br.E
    # autoroutes (contours fermes): bords du tablier a la hauteur de la fonction, traverses + piles sur l'axe
    for i, name in ((6, 'I-97 Viaduct (Interchange)'), (15, 'I-404 Viaduct (Interchange)')):
        r = R[i]; E = []
        P = np.vstack([np.linspace(a, b, max(2, int(np.hypot(*(b - a)) / 6))) for a, b in zip(r[:-1], r[1:])])
        xmax = 180.0 if i == 15 else WIN[1] + 100           # [I404-UNIFIED] I-404 continue: echangeur + pont Downtown (20.6 m, Shoreline) + troncon est (Postcard)
        mm = (P[:, 0] > WIN[0] - 150) & (P[:, 0] < xmax) & (P[:, 1] > WIN[2] - 150) & (P[:, 1] < WIN[3] + 50)
        for a, b, ka, kb in zip(P[:-1], P[1:], mm[:-1], mm[1:]):
            if not (ka and kb): continue
            za, zb_ = zmain(i, a), zmain(i, b)
            for dz in (-1.8, 0.0, 1.0):
                E.append([[*map(lambda v: round(float(v), 2), a), round(za + dz, 2)], [*map(lambda v: round(float(v), 2), b), round(zb_ + dz, 2)]])
        # traverses: chaque point du bord gauche relie au point le plus proche du bord oppose (tous les ~30 m)
        Pm = P[mm]; idx = np.arange(0, len(Pm), 5)
        for k in idx:
            p = Pm[k]; d = np.hypot(*(Pm - p).T); d[max(0, k - 12):k + 12] = 1e9
            j = int(d.argmin())
            if d[j] > 45: continue
            q = Pm[j]; z = zmain(i, (p + q) / 2)
            for dz in (-1.8, 0.0):
                E.append([[round(float(p[0]), 2), round(float(p[1]), 2), round(zmain(i, p) + dz, 2)], [round(float(q[0]), 2), round(float(q[1]), 2), round(zmain(i, q) + dz, 2)]])
            c = (p + q) / 2; g = max(RR.ground(*c), 0.0)        # au-dessus de l'eau: pile depuis z=0
            if k % 10 == 0 and z - 1.8 - g > 4:      # pile centrale
                for ox, oy in ((-0.9, -0.9), (0.9, -0.9), (0.9, 0.9), (-0.9, 0.9)):
                    E.append([[round(c[0] + ox, 2), round(c[1] + oy, 2), round(g, 2)], [round(c[0] + ox, 2), round(c[1] + oy, 2), round(z - 1.8, 2)]])
        E_all[name] = E
    for k, E in E_all.items():
        out[k] = {'color': COLOR, 'world_edges': E, '_credit': 'Alexandre Leblanc (V16 leak) + Claude Opus 5.5',
                  'note': 'INTERCHANGE-V1 2026-10-03: plan = trace V16 (leak map, exact); hauteurs: I-404 UNIFIEE (echangeur -> pont Downtown -> troncon est, un seul mesh, meme profil): 37 m au centre MESUREE (Explosion + Jason 05), 33 m a x=-1075 (Jason 05), 20.6 m sur le pont (Shoreline), 14.2 m a x=156 (Postcard), '
                          '21 m a x=-68 MESUREE (Convertible); I-97 12 m ESTIMEE; niveaux des bretelles interieures ESTIMES par l ordre des niveaux '
                          '(ordre de dessin SVG) 7/8 18.5 m, 9/10 25 m; raccords aux extremites. Voir tools/gen_interchange.py'}
    return out, Z


if __name__ == '__main__':
    out, Z = build()
    for k, v in out.items(): print('%-36s %5d aretes' % (k, len(v['world_edges'])))
    for i, (s, z) in Z.items(): print('  trace %2d  s %s  z %s' % (i, np.round(s).tolist(), np.round(z, 1).tolist()))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = os.path.join(ROOT, 'gtamapdata', 'building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_interchange_1003')
        M = json.load(open(mp))
        for k in ('I-404 Causeway Bridge (Downtown)', 'I-404 Viaduct (East of Downtown Bridge) N', 'I-404 Viaduct (East of Downtown Bridge) S'): M.pop(k, None)   # [I404-UNIFIED]
        M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
