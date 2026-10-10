#!/usr/bin/env python3
"""v16_roads.py — le reseau routier de la V16 en VRAIE geometrie 3D (onglet 3D). [ROADS-V1 2026-10-05]

Source: les traits du SVG V16 (tools/v16/svg_strokes.py): rues #535353 (8-20 m), autoroutes #727272 (8-32 m),
petites rues #636363 (5 m), marquages #FAFAFA (blanc) / #FFF4B0 (jaune). Chaque trait -> polyligne reechantillonnee
tous les ~6 m; z = sol (heightmap, v16_resect.ground) + 0.3 m, SAUF la ou un mesh de pont/viaduc/bretelle passe au-dessus:
la route prend la hauteur du tablier mesure (grille 4 m des aretes des meshes: max z - 1.0 m de garde-corps, si > sol + 2.5 m)
-> viaducs, echangeur I-97/I-404, ponts des Keys en 3D, a leurs hauteurs mesurees. Couche VISUELLE (rien n'est ecrit dans
les meshes). Sortie: tools/threejs/_v16_roads.json (ignore par git).
Usage: python3 tools/v16_roads.py
"""
import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import paths as _P   # [PATHS-V1]
import json, os, sys, subprocess, math
import numpy as np

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import v16_resect as RR

SVG = _P.asset('GTA VI Community Mapping Project-3.svg')
CACHE = os.path.join(THIS, 'generated', 'v16_all_strokes.json')
OUT = os.path.join(THIS, 'threejs', '_v16_roads.json')
CLS = {'#535353': 'road', '#727272': 'hwy', '#636363': 'small', '#FAFAFA': 'mark_w', '#FFF4B0': 'mark_y'}
DECK_WORDS = ('Bridge', 'Viaduct', 'Ramp', 'Interchange', 'Causeway', 'Overpass')
CELL = 4.0


def strokes():
    if not os.path.exists(CACHE):
        subprocess.run([sys.executable, os.path.join(THIS, 'v16', 'svg_strokes.py'), SVG, '-11000', '4500', '-9000', '12500', CACHE],
                       check=True, env=dict(os.environ, V16_X0='16991'), capture_output=True)
    return json.load(open(CACHE))['strokes']


def deck_grid():
    """hauteur du TABLIER (ponts/viaducs/bretelles) sur une grille de 4 m.
    [ROADS-V2] seulement les aretes quasi horizontales (pente < 8 %): les pylones et haubans (Sunshine Skyway...) sont
    ignores; par case, le niveau le plus frequent (bins de 1 m) = le tablier, pas le max (sommet des pylones)."""
    M = json.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')))
    Z = {}
    for n, m in M.items():
        if not any(w in n for w in DECK_WORDS): continue
        for a, b in m.get('world_edges') or []:
            a, b = np.array(a, float), np.array(b, float)
            L = np.linalg.norm(b[:2] - a[:2])
            if L < 0.5 or abs(b[2] - a[2]) / L > 0.08: continue
            k = max(1, int(L / 3))
            for t in np.linspace(0, 1, k + 1):
                p = a + (b - a) * t; Z.setdefault((int(p[0] // CELL), int(p[1] // CELL)), []).append(p[2])
    G = {}
    for key, v in Z.items():
        v = np.array(v); bins = np.round(v)
        u, c = np.unique(bins, return_counts=True); mode = u[c.argmax()]
        near = v[np.abs(v - mode) <= 1.2]
        G[key] = float(np.median(near)) + 0.9          # mediane du paquet (dessous/dessus/garde-corps) ~ dessous + 0.9 -> dessus
    return G


def resample(R, step=6.0):
    R = np.asarray(R, float); s = np.r_[0, np.cumsum(np.hypot(*np.diff(R, axis=0).T))]
    if s[-1] < 1: return R
    t = np.linspace(0, s[-1], max(2, int(s[-1] / step) + 1))
    return np.c_[np.interp(t, s, R[:, 0]), np.interp(t, s, R[:, 1])]


# [TUNNEL-V1 2026-10-06] tunnels: la V16 dessine la route en surface; la heightmap du jeu creuse leur tranchee (tube ouest a
# -28 m sur toute sa longueur, tube est sous le chenal a -16 m) -> ces polylignes vont dans out['tunnel'] (non rendues en 3D,
# pas de lampadaires ni de trafic) au lieu d'etre montees en pont a 6 m au-dessus de l'eau (elles traversaient le paquebot).
# Selection par extremites (tolerance 15 m): Port of Vice City tunnel (= PortMiami Tunnel IRL, Starfish Island -> Port VC, 2 tubes).
TUNNELS = [((323.0, 216.0), (517.0, -632.0)), ((289.0, 248.0), (517.0, -647.0))]


def is_tunnel(R, tol=15.0):
    a, b = R[0], R[-1]
    for p, q in TUNNELS:
        if (np.hypot(a[0] - p[0], a[1] - p[1]) < tol and np.hypot(b[0] - q[0], b[1] - q[1]) < tol) or \
           (np.hypot(a[0] - q[0], a[1] - q[1]) < tol and np.hypot(b[0] - p[0], b[1] - p[1]) < tol): return True
    return False


def main():
    S = strokes(); G = deck_grid()
    def deck_z(x, y):
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                z = G.get((int(x // CELL) + dx, int(y // CELL) + dy))
                if z is not None and (best is None or z > best): best = z
        return best
    out = {'road': [], 'hwy': [], 'small': [], 'mark_w': [], 'mark_y': [], 'tunnel': []}
    n_el = 0
    for s in S:
        c = CLS.get(s['color'].upper() if s['color'].startswith('#') else s['color'])
        if not c or len(s['ring']) < 2: continue
        R = resample(s['ring'])
        if c in ('road', 'hwy', 'small', 'mark_w', 'mark_y') and is_tunnel(R):
            P = []
            for x, y in R:
                try: g = float(RR.ground(x, y))
                except Exception: g = 0.0
                P.append([round(float(x), 1), round(float(y), 1), round(min(g, 0.0) - 8.0, 2)])   # sous le lit / la tranchee
            out['tunnel'].append({'w': float(s['width'] or 4), 'p': P, 'cls': c}); continue
        P = []; deck_hit = False
        on_deck = False                                     # [DECK-RAMP] le trait touche-t-il un tablier (> sol + 2.5 m) quelque part ?
        if c in ('hwy', 'road', 'mark_w', 'mark_y'):
            for x, y in R:
                dz = deck_z(x, y)
                if dz is not None:
                    try: g_ = max(0.0, float(RR.ground(x, y)))
                    except Exception: g_ = 0.0
                    if dz - 1.0 > g_ + 2.5: on_deck = True; break
        for x, y in R:
            try: g = max(0.0, float(RR.ground(x, y)))
            except Exception: g = 0.0
            z = g + 0.3
            if c in ('hwy', 'road', 'mark_w', 'mark_y'):
                dz = deck_z(x, y)
                # [DECK-RAMP 2026-10-09] le tablier mesure est suivi jusqu'au sol (ses rampes descendent a sol + 0.3): seuil 2.5 m ->
                # marche de 2.5 m au bout des rampes (Alexandre: « apres le bridge drop pas de meme »); 0.4 m pour un trait qui monte sur un tablier
                if dz is not None and (dz - 1.0 > g + 2.5 or (on_deck and dz - 1.0 > g + 0.4)): z = dz - 1.0 + 0.05; n_el += 1; deck_hit = True
            P.append([round(float(x), 1), round(float(y), 1), round(z, 2), round(g, 2)])
        # [BRIDGES-V1b 2026-10-05] route V16 au-dessus de l'eau SANS tablier mesure = pont bas (riviere de Miami, canaux):
        # tablier 6 m ESTIME + rampes a 8 % propagees UNIQUEMENT depuis ces points; une route qui touche un tablier MESURE
        # (Bocamar/Sunshine Skyway...) n'est pas concernee (la propagation depuis les pics du tablier mesure avait eclate le pont)
        wetZ = None
        if c in ('road', 'hwy', 'mark_w', 'mark_y') and len(P) >= 2 and not deck_hit:
            wet = [q[3] <= 0.05 and q[2] < q[3] + 2.5 for q in P]
            if any(wet):
                dd = np.r_[0, np.hypot(*np.diff(np.array([[q[0], q[1]] for q in P]), axis=0).T)]
                wetZ = np.array([6.0 if w else 0.0 for w in wet])
                for i in range(1, len(wetZ)): wetZ[i] = max(wetZ[i], wetZ[i - 1] - 0.08 * dd[i])
                for i in range(len(wetZ) - 2, -1, -1): wetZ[i] = max(wetZ[i], wetZ[i + 1] - 0.08 * dd[i + 1])
        # [ROADS-V2] profil lisse: mediane glissante (5) puis pente bornee a 8 % (pas de pics, rampes d'acces douces)
        if len(P) >= 3:
            Zs = np.array([q[2] for q in P]); G0 = np.array([q[3] for q in P])
            el = Zs > G0 + 2.0
            if el.any():
                Zm = Zs.copy()
                for i in range(len(Zs)):
                    w = Zs[max(0, i - 2):i + 3]; Zm[i] = np.median(w)
                d = np.r_[0, np.hypot(*np.diff(np.array([[q[0], q[1]] for q in P]), axis=0).T)]
                for i in range(1, len(Zm)): Zm[i] = min(Zm[i], Zm[i - 1] + 0.08 * d[i])
                for i in range(len(Zm) - 2, -1, -1): Zm[i] = min(Zm[i], Zm[i + 1] + 0.08 * d[i + 1])
                Zm = np.maximum(Zm, G0 + 0.3)
                for q, z in zip(P, Zm): q[2] = round(float(z), 2)
        if wetZ is not None:
            for q, wz in zip(P, wetZ):
                if wz > q[3] + 0.5: q[2] = round(max(q[2], float(wz)), 2)
        out[c].append({'w': float(s['width'] or 4), 'p': [q[:3] for q in P]})
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print({k: len(v) for k, v in out.items()}, 'points sur tablier:', n_el, '-> %s (%.0f ko)' % (OUT, os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
