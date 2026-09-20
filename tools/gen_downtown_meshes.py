#!/usr/bin/env python3
"""Lot de tours Downtown / Brickell (2026-09-20): extrusions V16 + quelques formes IRL simples.

Chaque entree: source du plan (polygone V16 ou coins triangules), toit = landmark(s), forme IRL quand elle est
caracteristique. Tout ce qui n'est pas mesure est marque ESTIME dans la note.

  Simples (polygone V16 extrude au z du landmark):
    Flagler on the River 2232/138 | InterContinental Miami 2260/132 (tour triangulaire Belluschi = pentagone V16)
    Carbonell Brickell 3107/123 | Loft Downtown II 3854/123 | 100 Biscayne Blvd 2290/92 | 1450 Brickell Ave 1936/175
    One Broadway 1937/152 | Wells Fargo Center 2269/187 | Wells Fargo Center (S) 2263/192 | Latitude on the River (S) 1978/93
  Coins triangules:
    Citigroup Center: parallelogramme NE/NW/SE (+SW deduit), toit 150
    Infinity at Brickell: quadrilatere NE/NW/SW/SE des coins de toit (177) sur podium V16 1929 (18 m ESTIME)
  Formes IRL:
    Brickell Arch: lame 106 x 34 m (coins E/W a y -1124) avec l'arche parabolique concave sur la face nord
      (recess max 14 m ESTIME au sommet), podium V16 1965 (12 m ESTIME)
    Miami Tower: garage V16 2271 (40 m, 10 niveaux IRL) + tour 3 gradins (0.85 du plan, retraits de 10 m sur la face SE
      a z 105 et 135, toit 160.5) ESTIME
    Miami-Dade County Courthouse: ziggourat 4 paliers depuis V16 2308 (toit 116.5) ESTIME

Usage: gen_downtown_meshes.py [--out brouillon.json] [--apply] [--only "Nom" ...]
"""
import json, sys, os, argparse
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'gtamapdata')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import horizon_resect as HR

LMS = json.load(open(os.path.join(ROOT, 'landmarks.json')))
POLYS = json.load(open(os.path.join(ROOT, 'v16_footprints.json')))['polygons']
DATE = '2026-09-20'


def ring(i):
    return np.array(POLYS[i]['ring'], float)


def ground(poly):
    zs = [HR.ground(x, y) for x, y in poly]
    zs = [z for z in zs if z is not None and np.isfinite(z)]
    return float(np.median(zs)) if zs else 2.0


def lm(name):
    return np.array(LMS[name]['xyz'], float)


def loop_edges(poly, z):
    P = [[float(x), float(y), float(z)] for x, y in poly]
    return [[P[k], P[(k + 1) % len(P)]] for k in range(len(P))]


def vertical_edges(poly, z0, z1):
    return [[[float(x), float(y), float(z0)], [float(x), float(y), float(z1)]] for x, y in poly]


def extrude(poly, z0, z1, ring_step=None):
    E = loop_edges(poly, z0) + loop_edges(poly, z1) + vertical_edges(poly, z0, z1)
    if ring_step:
        for z in np.arange(z0 + ring_step, z1 - 0.01, ring_step):
            E += loop_edges(poly, z)
    return E


def scaled(poly, s, c=None):
    poly = np.asarray(poly, float); c = poly.mean(axis=0) if c is None else np.asarray(c)
    return (poly - c) * s + c


def clip_halfplane(poly, p0, n):
    out = []; m = len(poly)
    for i in range(m):
        a = np.array(poly[i]); b = np.array(poly[(i + 1) % m])
        da = np.dot(a - p0, n); db = np.dot(b - p0, n)
        if da <= 0: out.append(a.tolist())
        if (da <= 0) != (db <= 0):
            t = da / (da - db); out.append((a + t * (b - a)).tolist())
    return out


def entry(name, edges, color, note):
    return {name: {'color': color, 'note': note, '_credit': 'gen_downtown_meshes.py %s' % DATE,
                   'world_edges': [[[round(c, 2) for c in p] for p in e] for e in edges]}}


SIMPLE = [
    ('Flagler on the River', 2232, 'Flagler on the River', '#7dd3fc', 'Empreinte V16 2232 extrudee; toit = landmark 138.1; le coin (SE) a 20 m au sud est probablement une aile plus basse'),
    ('InterContinental Miami', 2260, 'InterContinental Miami (N)', '#fde68a', 'Empreinte V16 2260 (pentagone = tour triangulaire Belluschi 1982) extrudee; toit = landmark (N) 131.7'),
    ('Carbonell Brickell', 3107, 'Carbonell Brickell', '#c4b5fd', 'Empreinte V16 3107 (plan courbe) extrudee; toit = landmark 123.1; la V16 inclut peut-etre le socle (a verifier dans une cam proche)'),
    ('Loft Downtown II', 3854, 'Loft Downtown II', '#fca5a5', 'Empreinte V16 3854 (L) extrudee; toit = landmark 123.1'),
    ('100 Biscayne Blvd', 2290, '100 Biscayne Blvd (SE)', '#a7f3d0', 'Empreinte V16 2290 extrudee; coins (SE)/(NE) sur le bord; toit 92.2'),
    ('1450 Brickell Ave', 1936, '1450 Brickell Ave', '#fdba74', 'Empreinte V16 1936 extrudee; toit = landmark 174.8'),
    ('One Broadway', 1937, 'One Broadway (W)', '#93c5fd', 'Empreinte V16 1937 (lame) extrudee; toit = coins (W)/(E) 151.6; coins (NW)/(SW) a 140 = aile basse non modelisee'),
    ('Wells Fargo Center', 2269, 'Wells Fargo Center (N)', '#86efac', 'Empreinte V16 2269 (4149 m2 = plan IRL ~55x75) extrudee; toit = coin (N) 186.6'),
    ('Wells Fargo Center (S)', 2263, 'Wells Fargo Center (S)', '#86efac', 'Deuxieme tour du complexe Metropolitan (hotel IRL): empreinte V16 2263 extrudee; toit = coin (S) 191.8'),
    ('Latitude on the River (S)', 1978, 'Latitude on the River (S) (NW)', '#f9a8d4', 'Empreinte V16 1978 extrudee; toit = coins (S) (NW)/(SW) 93'),
]


def build_simple():
    out = {}
    for name, pid, lmk, color, note in SIMPLE:
        p = ring(pid); z0 = ground(p); zr = float(lm(lmk)[2])
        out.update(entry(name, extrude(p, z0, zr, ring_step=max(4.0, (zr - z0) / 12)), color, note + '; sol %.1f' % z0))
    return out


def build_citigroup():
    ne, nw, se = lm('Citigroup Center (NE)')[:2], lm('Citigroup Center (NW)')[:2], lm('Citigroup Center (SE)')[:2]
    sw = se + (nw - ne); poly = np.array([ne, nw, sw, se]); z0 = ground(poly)
    return entry('Citigroup Center', extrude(poly, z0, 150.3, ring_step=4.4), '#d1d5db',
                 'Parallelogramme sur 3 coins de toit triangules (NE/NW/SE, 4e deduit); toit 150.3; sol %.1f; la V16 (2259) ne dessine que le quart NE' % z0)


def build_infinity():
    poly = np.array([lm('Infinity at Brickell (NE)')[:2], lm('Infinity at Brickell (NW)')[:2], lm('Infinity at Brickell (SW)')[:2], lm('Infinity at Brickell (SE)')[:2]])
    pod = ring(1929); z0 = ground(pod)
    E = extrude(poly, z0, 177.2, ring_step=4.3) + extrude(pod, z0, z0 + 18.0, ring_step=6.0)
    return entry('Infinity at Brickell', E, '#67e8f9', 'Tour = quadrilatere des 4 coins de toit (177.2), en retrait/decale du podium V16 1929 (18 m ESTIME); sol %.1f' % z0)


def build_brickell_arch():
    W = lm('Brickell Arch (W)'); Ecorner = lm('Brickell Arch (E)')
    yN = float((W[1] + Ecorner[1]) / 2); x0, x1 = float(W[0]), float(Ecorner[0]); depth = 34.0; H = 172.2
    pod = ring(1965); z0 = ground(pod); Rmax = 14.0; xc = (x0 + x1) / 2; hwmax = (x1 - x0) / 2
    def ring_at(z):
        s = max(0.0, (z - z0) / (H - z0)); hw = hwmax * np.sqrt(s); d = Rmax * s
        xs = np.linspace(x0, x1, 25); north = []
        for x in xs:
            u = (x - xc) / hw if hw > 1e-6 else 9
            rec = d * (1 - u * u) if abs(u) < 1 else 0.0
            north.append([x, yN - rec])
        return np.array(north + [[x1, yN - depth], [x0, yN - depth]])
    E = []; zs = list(np.arange(z0, H, 5.0)) + [H]; prev = ring_at(zs[0])
    E += loop_edges(prev, zs[0])
    for z in zs[1:]:
        E += loop_edges(ring_at(z), z)
    rect = np.array([[x0, yN], [x1, yN], [x1, yN - depth], [x0, yN - depth]])
    E += vertical_edges(rect, z0, H)
    # arete de l'arche (ligne mediane de la face nord)
    for za, zb in zip(zs[:-1], zs[1:]):
        a = ring_at(za)[12]; b = ring_at(zb)[12]; E.append([[float(a[0]), float(a[1]), float(za)], [float(b[0]), float(b[1]), float(zb)]])
    E += extrude(pod, z0, z0 + 12.0, ring_step=6.0)
    return entry('Brickell Arch', E, '#fcd34d', 'Lame %.0f x %.0f m entre les coins (W)/(E) (face nord y=%.1f), toit 172.2, arche parabolique concave sur la face nord (recess max %.0f m au sommet, ESTIME; IRL KPF 2004); podium V16 1965 a 12 m ESTIME; sol %.1f' % (x1 - x0, depth, yN, Rmax, z0))


def build_miami_tower():
    g = ring(2271); z0 = ground(g); c = lm('Miami Tower'); H = float(c[2])
    E = extrude(g, z0, z0 + 40.0, ring_step=4.0)
    tower = scaled(g, 0.85, c[:2]); n = np.array([np.sin(np.radians(135)), np.cos(np.radians(135))])
    pmax = ((tower - c[:2]) @ n).max()
    t1 = tower.tolist(); t2 = clip_halfplane(t1, c[:2] + n * (pmax - 10), n); t3 = clip_halfplane(t2, c[:2] + n * (pmax - 20), n)
    E += extrude(np.array(t1), z0 + 40.0, 105.0, ring_step=4.0) + extrude(np.array(t2), 105.0, 135.0, ring_step=4.0) + extrude(np.array(t3), 135.0, H, ring_step=4.0)
    return entry('Miami Tower', E, '#a5b4fc', 'Garage V16 2271 (40 m, 10 niveaux IRL) + tour = plan reduit a 0.85 autour du landmark, 3 gradins avec retraits de 10 m sur la face SE a z 105 et 135 (IRL Pei 1987: 3 tiers sur la face SE courbe), toit 160.5; forme ESTIMEE; sol %.1f' % z0)


def build_courthouse():
    p = ring(2308); z0 = ground(p); c = lm('Miami-Dade County Courthouse'); H = float(c[2])
    tiers = [(1.0, 40.0), (0.72, 78.0), (0.52, 100.0), (0.36, H - 6.0)]
    E = []; zprev = z0
    for s, zt in tiers:
        E += extrude(scaled(p, s), zprev, zt, ring_step=6.0); zprev = zt
    top = scaled(p, 0.36); apex = np.r_[top.mean(axis=0), H]
    for x, y in top: E.append([[float(x), float(y), float(zprev)], [float(apex[0]), float(apex[1]), float(apex[2])]])
    return entry('Miami-Dade County Courthouse', E, '#e5e7eb', 'Ziggourat neoclassique (IRL 1928): 4 paliers depuis V16 2308 (echelles 1/0.72/0.52/0.36) + toit pyramidal jusqu au landmark 116.5; paliers ESTIMES; sol %.1f' % z0)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out'); ap.add_argument('--apply', action='store_true'); ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    meshes = {}
    meshes.update(build_simple()); meshes.update(build_citigroup()); meshes.update(build_infinity())
    meshes.update(build_brickell_arch()); meshes.update(build_miami_tower()); meshes.update(build_courthouse())
    if a.only: meshes = {k: v for k, v in meshes.items() if k in a.only}
    for k, v in meshes.items(): print('%-32s %5d aretes' % (k, len(v['world_edges'])))
    if a.out: json.dump(meshes, open(a.out, 'w'), indent=1, ensure_ascii=True); print('brouillon ->', a.out)
    if a.apply:
        path = os.path.join(ROOT, 'building_meshes_procedural.json'); M = json.load(open(path)); M.update(meshes)
        json.dump(M, open(path, 'w'), indent=1, ensure_ascii=True); print('applique ->', path)
