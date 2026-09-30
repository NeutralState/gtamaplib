#!/usr/bin/env python3
"""gen_turkey_point.py — mesh de la centrale de Turkey Point (Peregrine Bay). [TURKEY-POINT-V1 2026-09-30]

Plan = formes V16 (v16_footprints.json: salle des machines 899/905, enceintes 904/900, batiments 907/908,
chaudieres 892/894/896, cheminees 893/895/897, poste 871) TRANSLATEES de SHIFT: les 5 reperes triangules
3-4 cams (sommets des 3 cheminees, sommets des 2 domes) sont tous a (-4.9, -16.4) m de leur cercle V16
(ecart-type 1.5 m) -> decalage local rigide de la V16, comme sous Allied (Postcard V4).
Hauteurs: cheminees = landmarks (1)(2)(3) ~82 m; domes = landmarks (N)(S) ~57 m; le reste lu dans les cams
(voir HEIGHTS: chaudieres 56 m lues dans Thunderstorm + Airplane par graduations verticales; salle des machines 30 m au rendu Airplane). Usage: PYTHONPATH=. python3 tools/gen_turkey_point.py [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda f: os.path.join(ROOT, 'gtamapdata', f)
SHIFT = np.array([-4.9, -16.4])
HEIGHTS = {'hall': 30.0, 'w_bldg': 20.0, 'small': 12.0, 'boiler': 56.0, 'yard': 8.0, 'shoulder': 42.0}
HEIGHTS.update(json.loads(sys.argv[sys.argv.index('--h') + 1]) if '--h' in sys.argv else {})


def ring(F, i): return [np.array(p) + SHIFT for p in F[i]['ring']]


def ground(x, y):
    try:
        sys.path.insert(0, os.path.join(ROOT, 'tools')); import v16_resect as R
        return max(R.ground(x, y), 0.0)
    except Exception: return 1.0


def prism(E, pts, z0, z1, rings=10.0):
    n = len(pts); zs = [z0] + list(np.arange(z0 + rings, z1, rings)) + [z1]
    for z in zs:
        for i in range(n): E.append([[*map(float, np.round(pts[i], 2)), round(z, 2)], [*map(float, np.round(pts[(i + 1) % n], 2)), round(z, 2)]])
    for p in pts: E.append([[*map(float, np.round(p, 2)), round(z0, 2)], [*map(float, np.round(p, 2)), round(z1, 2)]])


def circle(c, r, n=20): return [c + r * np.array([np.cos(a), np.sin(a)]) for a in np.linspace(0, 2 * np.pi, n, endpoint=False)]


def build():
    F = {f['id']: f for f in json.load(open(D('v16_footprints.json')))['polygons']}
    L = json.load(open(D('landmarks.json')))
    lm = lambda k: np.array(L['Turkey Point Nuclear Power Station (%s)' % k]['xyz'])
    out = {}
    # enceintes de confinement: cylindre + dome (calotte) jusqu au sommet triangule
    E = []
    for fid, k in ((904, 'N'), (900, 'S')):
        rr = np.array(ring(F, fid)); c = rr.mean(0); r = float(np.mean(np.linalg.norm(rr - c, axis=1)))
        zg = ground(*c); zt = float(lm(k)[2]); zs = HEIGHTS['shoulder']
        prism(E, circle(c, r), zg, zs)
        for a in np.linspace(0, np.pi / 2, 6)[1:]:            # calotte: anneaux + meridiens
            rz = r * np.cos(a); z = zs + (zt - zs) * np.sin(a)
            cc = circle(c, rz)
            for i in range(len(cc)): E.append([[*map(float, np.round(cc[i], 2)), round(z, 2)], [*map(float, np.round(cc[(i + 1) % len(cc)], 2)), round(z, 2)]])
        for th in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            prev = None
            for a in np.linspace(0, np.pi / 2, 7):
                p = c + r * np.cos(a) * np.array([np.cos(th), np.sin(th)]); z = zs + (zt - zs) * np.sin(a)
                cur = [*map(float, np.round(p, 2)), round(z, 2)]
                if prev: E.append([prev, cur])
                prev = cur
    out['Turkey Point Nuclear Power Station (Containments)'] = E
    # salle des machines (905 = contour complet avec avancees), batiment ouest 907, petit batiment 908
    E = []
    prism(E, ring(F, 905), ground(*np.mean(ring(F, 905), 0)), HEIGHTS['hall'])
    prism(E, ring(F, 907), ground(*np.mean(ring(F, 907), 0)), HEIGHTS['w_bldg'])
    prism(E, ring(F, 908), ground(*np.mean(ring(F, 908), 0)), HEIGHTS['small'])
    out['Turkey Point Nuclear Power Station (Turbine Hall)'] = E
    # unites fossiles: chaudieres + cheminees (centre du cercle V16 translate, sommet = landmark) + poste
    E = []
    for fid in (892, 894, 896): prism(E, ring(F, fid), ground(*np.mean(ring(F, fid), 0)), HEIGHTS['boiler'])
    for fid, k in ((897, '1'), (895, '2'), (893, '3')):
        c = np.mean(ring(F, fid), 0); zt = float(lm(k)[2]); zg = ground(*c)
        for z, r in ((zg, 4.5), (zt, 3.2)):
            cc = circle(c, r, 12)
            for i in range(12): E.append([[*map(float, np.round(cc[i], 2)), round(z, 2)], [*map(float, np.round(cc[(i + 1) % 12], 2)), round(z, 2)]])
        for th in np.linspace(0, 2 * np.pi, 6, endpoint=False):
            E.append([[*map(float, np.round(c + 4.5 * np.array([np.cos(th), np.sin(th)]), 2)), round(zg, 2)],
                      [*map(float, np.round(c + 3.2 * np.array([np.cos(th), np.sin(th)]), 2)), round(zt, 2)]])
    prism(E, ring(F, 871), ground(*np.mean(ring(F, 871), 0)), HEIGHTS['yard'])
    out['Turkey Point Nuclear Power Station (Fossil Units)'] = E
    note = ('VALIDE Alexandre 2026-09-30 (decalage V16 correct) | TURKEY-POINT-V1 2026-09-30 (demande Alexandre: mesh de l usine pour placer Thunderstorm [Gameinformer]): formes V16 '
            'translatees de (%.1f, %.1f) m = decalage moyen des 5 reperes triangules 3-4 cams (3 cheminees, 2 domes) a leur cercle V16 '
            '(ecart-type 1.5 m). Cheminees et domes: sommets = landmarks; hauteurs %s.' % (SHIFT[0], SHIFT[1], json.dumps(HEIGHTS)))
    cols = {'Containments': '#e5e7eb', 'Turbine Hall': '#9ca3af', 'Fossil Units': '#f87171'}
    return {k: {'color': cols[k.split('(')[-1][:-1]], 'world_edges': v, 'note': note, '_credit': 'Alexandre Leblanc (landmarks) + Claude Opus 5.5'}
            for k, v in out.items()}


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print(k, len(v['world_edges']), 'aretes')
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = D('building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_turkeypoint_0930')
        M = json.load(open(mp)); M.update(out)
        json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
