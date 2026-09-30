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
HEIGHTS = {'hall': 30.0, 'w_bldg': 20.0, 'small': 12.0, 'boiler': 53.0, 'boiler_w': 22.0, 'slope_frac': 0.62, 'yard': 8.0,
           'shoulder': 54.0, 'vent': 62.0, 'stack_r0': 6.3, 'stack_z1': 57.0, 'stack_r1': 2.5}
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


def ring_at(E, pts, z):
    n = len(pts)
    for i in range(n): E.append([[*map(float, np.round(pts[i], 2)), round(z, 2)], [*map(float, np.round(pts[(i + 1) % n], 2)), round(z, 2)]])


def seg(E, a, b): E.append([[*map(float, np.round(a[:2], 2)), round(float(a[2]), 2)], [*map(float, np.round(b[:2], 2)), round(float(b[2]), 2)]])


def cylinder(E, c, r, z0, z1, n=20, rings=10.0, verts=10):
    for z in [z0] + list(np.arange(z0 + rings, z1, rings)) + [z1]: ring_at(E, circle(c, r, n), z)
    for p in circle(c, r, verts): seg(E, [*p, z0], [*p, z1])


def build():
    F = {f['id']: f for f in json.load(open(D('v16_footprints.json')))['polygons']}
    L = json.load(open(D('landmarks.json')))
    lm = lambda k: np.array(L['Turkey Point Nuclear Power Station (%s)' % k]['xyz'])
    H = HEIGHTS; out = {}
    # --- enceintes: cylindre jusqu a l epaule (54 m, Grassrivers 02) + dome tres surbaisse jusqu au sommet triangule;
    #     event (tube fin ~62 m) au sud-est de l enceinte sud (vu dans Grassrivers 02 et Airplane)
    E = []
    for fid, k in ((904, 'N'), (900, 'S')):
        rr = np.array(ring(F, fid)); c = rr.mean(0); r = float(np.mean(np.linalg.norm(rr - c, axis=1)))
        zg = ground(*c); zt = float(lm(k)[2]); zs = H['shoulder']
        cylinder(E, c, r, zg, zs, n=28, verts=14)
        prev = None
        for a in np.linspace(0, np.pi / 2, 7)[1:]:           # calotte surbaissee: anneaux
            ring_at(E, circle(c, r * np.cos(a) if a < np.pi / 2 else 0.8, 28), zs + (zt - zs) * np.sin(a))
        for th in np.linspace(0, 2 * np.pi, 12, endpoint=False):
            pts = [[*(c + r * np.cos(a) * np.array([np.cos(th), np.sin(th)])), zs + (zt - zs) * np.sin(a)] for a in np.linspace(0, np.pi / 2, 7)]
            for a_, b_ in zip(pts[:-1], pts[1:]): seg(E, a_, b_)
        ring_at(E, circle(c, r + 1.0, 28), zg + 3.0)          # socle
        if k == 'S':
            v = c + (r + 2.5) * np.array([np.cos(-np.pi / 4), np.sin(-np.pi / 4)])
            cylinder(E, v, 1.4, zs - 6, H['vent'], n=8, rings=20.0, verts=4)
    out['Turkey Point Nuclear Power Station (Containments)'] = E
    # --- salle des machines (905 = contour avec avancees) + lanterneau, batiment ouest 907, petit batiment 908
    E = []
    hall = ring(F, 905); zg = ground(*np.mean(hall, 0))
    prism(E, hall, zg, H['hall'])
    hb = np.array(hall); c = hb.mean(0)
    x0, x1, y0, y1 = hb[:, 0].min(), hb[:, 0].max(), hb[:, 1].min(), hb[:, 1].max(); xm = (x0 + x1) / 2
    lant = [np.array(p) for p in ((xm - 5, y0 + 8), (xm + 5, y0 + 8), (xm + 5, y1 - 8), (xm - 5, y1 - 8))]
    prism(E, lant, H['hall'], H['hall'] + 4.0, rings=4.0)
    prism(E, ring(F, 907), ground(*np.mean(ring(F, 907), 0)), H['w_bldg'])
    prism(E, ring(F, 908), ground(*np.mean(ring(F, 908), 0)), H['small'])
    out['Turkey Point Nuclear Power Station (Turbine Hall)'] = E
    # --- unites fossiles: chaudiere a profil incline (bas a l ouest -> toit plat a l est, lu dans Thunderstorm + Airplane),
    #     cheminee en deux troncons (fut large jusqu a 57 m puis fut fin, lu dans Grassrivers 02) avec couronnes, poste 871
    E = []
    for fid in (892, 894, 896):
        rr = np.array(ring(F, fid)); zg = ground(*rr.mean(0))
        xw, xe = rr[:, 0].min(), rr[:, 0].max(); ys, yn = rr[:, 1].min(), rr[:, 1].max()
        xk = xw + H['slope_frac'] * (xe - xw)                   # arete du toit (debut du plat)
        prof = [(xw, H['boiler_w']), (xk, H['boiler']), (xe, H['boiler'])]
        for y in (ys, yn):                                      # faces nord/sud: pentagone
            poly = [(xw, zg), (xw, H['boiler_w']), (xk, H['boiler']), (xe, H['boiler']), (xe, zg)]
            for a_, b_ in zip(poly, poly[1:] + poly[:1]): seg(E, [a_[0], y, a_[1]], [b_[0], y, b_[1]])
        for x, z in prof + [(xw, zg), (xe, zg)]: seg(E, [x, ys, z], [x, yn, z])
        for x in np.arange(xw + 8, xe, 8.0):                    # nervures de facade
            zt = float(np.interp(x, [xw, xk, xe], [H['boiler_w'], H['boiler'], H['boiler']]))
            for y in (ys, yn): seg(E, [x, y, zg], [x, y, zt])
            seg(E, [x, ys, zt], [x, yn, zt])
    for fid, k in ((897, '1'), (895, '2'), (893, '3')):
        c = np.mean(ring(F, fid), 0); zt = float(lm(k)[2]); zg = ground(*c)
        cylinder(E, c, H['stack_r0'], zg, H['stack_z1'], n=14, rings=15.0, verts=6)
        ring_at(E, circle(c, H['stack_r0'] + 0.8, 14), H['stack_z1'])        # plateforme
        cylinder(E, c, H['stack_r1'], H['stack_z1'], zt, n=12, rings=12.5, verts=6)
        ring_at(E, circle(c, H['stack_r1'] + 0.6, 12), zt - 2.0)             # couronne
    prism(E, ring(F, 871), ground(*np.mean(ring(F, 871), 0)), H['yard'])
    out['Turkey Point Nuclear Power Station (Fossil Units)'] = E
    # --- portiques (grues a portique) aux landmarks CNE/CNW (nord) et CSE/CSW (prise d eau): pieds aux xy triangules, poutre a leur z
    E = []
    for a_, b_ in (('CNW', 'CNE'), ('CSW', 'CSE')):
        A, B = lm(a_), lm(b_); zt = float((A[2] + B[2]) / 2); u = (B[:2] - A[:2]) / np.linalg.norm(B[:2] - A[:2]); n = np.array([-u[1], u[0]])
        for P_ in (A[:2], B[:2]):
            zg = ground(*P_)
            for dn in (-3.0, 3.0):
                seg(E, [*(P_ + n * dn), zg], [*(P_ + n * dn), zt - 3.0])
            seg(E, [*(P_ - n * 3), zg + 1], [*(P_ + n * 3), zg + 1]); seg(E, [*(P_ - n * 3), zt - 3], [*(P_ + n * 3), zt - 3])
        for dn in (-3.0, 3.0):
            for dz in (-3.0, 0.0): seg(E, [*(A[:2] - u * 4 + n * dn), zt + dz], [*(B[:2] + u * 4 + n * dn), zt + dz])
        for t in np.linspace(0, 1, 6):
            P_ = A[:2] + (B[:2] - A[:2]) * t
            seg(E, [*(P_ - n * 3), zt], [*(P_ + n * 3), zt]); seg(E, [*(P_ - n * 3), zt - 3], [*(P_ - n * 3), zt])
    out['Turkey Point Nuclear Power Station (Gantry Cranes)'] = E
    note = ('VALIDE Alexandre 2026-09-30 (decalage V16 correct) | TURKEY-POINT-V2 2026-09-30 (Alexandre: V1 trop simple): formes V16 '
            'translatees de (%.1f, %.1f) m (5 reperes triangules 3-4 cams). Enceintes = cylindre jusqu a l epaule %.0f m + dome surbaisse '
            'jusqu aux sommets triangules (Grassrivers 02), event %.0f m; cheminees en 2 troncons (fut %.1f m de rayon jusqu a %.0f m puis '
            '%.1f m jusqu aux sommets triangules, Grassrivers 02); chaudieres a profil incline %.0f -> %.0f m sur %.0f %% de la longueur '
            'puis toit plat (Thunderstorm + Airplane, graduations); portiques aux landmarks CNE/CNW et CSE/CSW. %s' % (SHIFT[0], SHIFT[1], H['shoulder'], H['vent'], H['stack_r0'],
            H['stack_z1'], H['stack_r1'], H['boiler_w'], H['boiler'], 100 * H['slope_frac'], json.dumps(H)))
    cols = {'Containments': '#e5e7eb', 'Turbine Hall': '#9ca3af', 'Fossil Units': '#f87171', 'Gantry Cranes': '#fbbf24'}
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
