#!/usr/bin/env python3
"""Meshs One Miami Condominium (East + West + podium) et Southeast Financial Center.

Sources:
  * One Miami: 3 coins de toit trianguls par tour (NE, SE, NW; 4e coin = parallelogramme,
    les tours IRL d'Arquitectonica sont des lames a bouts biais), toit East 182 m / West 188 m,
    couronne = bandeau de 2 etages en leger debord (Vice City 10), podium = polygone V16 2257
    (hauteur ESTIMEE 14 m, visible au pied des tours dans Vice City 10).
  * SEFC: empreinte V16 2267 (dents de scie sur le cote NE, encoche en V sur la face ouest,
    petites encoches au SE -- exactement le plan IRL de SOM 1984), toit 246.5 m (landmarks
    'Southeast Financial Center' 248.9 et '(D)' 246.4), setbacks a partir du 43e etage sur 55
    (= z 192): les faces NE (scie) et SW reculent en gradins symetriques vers une crete NW-SE
    (damier de terrasses de Vice City 10, pyramide dans Port Vice City (A)); mat au landmark
    '(A)' jusqu'a 276.5 m; annexe = polygone V16 2268 (15 etages IRL, hauteur ESTIMEE 58 m).

Usage: gen_onemiami_sefc_mesh.py [--out brouillon.json] [--apply]
"""
import json, sys, os, argparse
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'gtamapdata')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import horizon_resect as HR

LMS = json.load(open(os.path.join(ROOT, 'landmarks.json')))
FP = json.load(open(os.path.join(ROOT, 'v16_footprints.json')))
POLYS = FP['polygons'] if isinstance(FP, dict) and 'polygons' in FP else FP


def ring(i):
    pg = POLYS[i]
    return np.array(pg['ring'] if isinstance(pg, dict) else pg, float)


def ground(poly):
    zs = []
    for x, y in poly:
        g = HR.ground(x, y)
        zs.append(g if g is not None and np.isfinite(g) else 2.0)
    return float(np.median(zs))


def loop_edges(poly, z):
    P = [[float(x), float(y), float(z)] for x, y in poly]
    return [[P[k], P[(k + 1) % len(P)]] for k in range(len(P))]


def vertical_edges(poly, z0, z1):
    return [[[float(x), float(y), float(z0)], [float(x), float(y), float(z1)]] for x, y in poly]


def extrude(poly, z0, z1, ring_step=None, rings=None):
    E = loop_edges(poly, z0) + loop_edges(poly, z1) + vertical_edges(poly, z0, z1)
    levels = rings if rings is not None else (np.arange(z0 + ring_step, z1, ring_step) if ring_step else [])
    for z in levels:
        E += loop_edges(poly, z)
    return E


def clip_halfplane(poly, p0, n):
    """Garde la partie du polygone (liste de xy) telle que dot(P - p0, n) <= 0 (Sutherland-Hodgman)."""
    out = []
    m = len(poly)
    for i in range(m):
        a = np.array(poly[i]); b = np.array(poly[(i + 1) % m])
        da = np.dot(a - p0, n); db = np.dot(b - p0, n)
        if da <= 0:
            out.append(a.tolist())
        if (da <= 0) != (db <= 0):
            t = da / (da - db)
            out.append((a + t * (b - a)).tolist())
    return out


def one_miami():
    def para(ne, se, nw):
        ne, se, nw = (np.array(LMS[k]['xyz'][:2]) for k in (ne, se, nw))
        return np.array([ne, se, se + (nw - ne), nw])
    E = para('One Miami Condominium East (NE)', 'One Miami Condominium East (SE)', 'One Miami Condo East (NW)')
    W = para('One Miami Condominium West (NE)', 'One Miami Condominium West (SE)', 'One Miami Condo West (NW)')
    out = {}
    for name, poly, z_roof, floors in [('One Miami Condominium East', E, 182.0, 44), ('One Miami Condominium West', W, 188.0, 45)]:
        z0 = ground(poly)
        crown = z_roof - 8.0                      # bandeau de couronnement ~2 etages
        step = (crown - z0) / floors
        edges = extrude(poly, z0, crown, ring_step=step)
        # couronne en debord de 0.8 m
        c = poly.mean(axis=0)
        outer = c + (poly - c) * (1 + 0.8 / np.linalg.norm(poly - c, axis=1)[:, None])
        edges += loop_edges(outer, crown) + loop_edges(outer, z_roof) + vertical_edges(outer, crown, z_roof)
        edges += loop_edges(poly, z_roof)
        out[name] = {'color': '#e2c290', 'world_edges': edges,
                     'note': 'Lame a plan parallelogramme (3 coins triangules + 4e coin deduit), %d etages, couronne 8 m en debord de 0.8 m; sol heightmap %.1f m; toit %.0f m' % (floors, z0, z_roof),
                     '_credit': 'gen_onemiami_sefc_mesh.py 2026-09-20 (coins de toit multi-cams, Vice City 10 / Landing Gear (B) pour la forme)'}
    pod = ring(2257)
    z0 = ground(pod)
    out['One Miami (Podium)'] = {'color': '#e2c290', 'world_edges': extrude(pod, z0, z0 + 14.0, rings=[z0 + 7.0]),
                                 'note': 'Podium = empreinte V16 2257; hauteur 14 m ESTIMEE (bloc blanc de ~4 niveaux au pied des tours dans Vice City 10)',
                                 '_credit': 'gen_onemiami_sefc_mesh.py 2026-09-20'}
    return out


def sefc():
    tower = ring(2267)
    z0 = ground(tower)
    z_roof = 246.5
    z_set = 192.0                                 # 43e etage sur 55
    # Gradins des deux cotes (vu dans Vice City 10 depuis le SE: pyramide a gradins symetrique,
    # toit = 1/3 de la largeur NE-SW; Sunrise depuis l'ouest: crete presque pleine longueur NW-SE;
    # Port Vice City (A) depuis l'ENE: sommet retreci). Les faces NE (scie) et SW reculent
    # perpendiculairement a la ligne des dents, en 12 paliers, de FRAC_NE / FRAC_SW de la profondeur.
    p23 = tower[23]; p3 = tower[3]
    t = p3 - p23; t /= np.linalg.norm(t)              # le long des dents (NW -> SE)
    n = np.array([t[1], -t[0]])                       # perpendiculaire
    if np.dot(n, p3 - tower.mean(axis=0)) < 0:
        n = -n                                         # pointe vers l'exterieur NE
    proj = (tower - p23) @ n
    depth = proj.max() - proj.min()
    # fractions ajustees (scratchpad sefc_crownfit.py) sur l'etendue du bloc sommital lue dans
    # Vice City 10, Port Vice City (A), Sunrise et Skyline (rms 5 px): les 4 faces reculent.
    frac_ne = float(os.environ.get('FRAC_NE', '0.24'))
    frac_sw = float(os.environ.get('FRAC_SW', '0.48'))
    frac_se = float(os.environ.get('FRAC_SE', '0.45'))
    frac_nw = float(os.environ.get('FRAC_NW', '0.36'))
    pt = (tower - p23) @ t
    depth_t = pt.max() - pt.min()
    edges = []
    floor = (z_roof - z0) / 55.0
    edges += extrude(tower, z0, z_set, ring_step=floor * 2)
    n_steps = 12
    prev = tower.tolist()
    for k in range(1, n_steps + 1):
        z_lo = z_set + (k - 1) * (z_roof - z_set) / n_steps
        z_hi = z_set + k * (z_roof - z_set) / n_steps
        d_ne = proj.max() - depth * frac_ne * k / n_steps
        d_sw = proj.min() + depth * frac_sw * k / n_steps
        cut = clip_halfplane(prev, p23 + n * d_ne, n)          # retire au-dela de d_ne cote NE
        cut = clip_halfplane(cut, p23 + n * d_sw, -n)          # retire en-deca de d_sw cote SW
        cut = clip_halfplane(cut, p23 + t * (pt.max() - depth_t * frac_se * k / n_steps), t)    # face SE
        cut = clip_halfplane(cut, p23 + t * (pt.min() + depth_t * frac_nw * k / n_steps), -t)   # face NW
        if len(cut) < 3:
            break
        edges += loop_edges(prev, z_lo) + loop_edges(cut, z_hi)
        edges += vertical_edges(cut, z_lo, z_hi)
        prev = cut
    edges += loop_edges(prev, z_roof)
    # mat(s) au landmark (A)
    A = LMS['Southeast Financial Center (A)']['xyz']
    edges += [[[A[0], A[1], z_roof], [A[0], A[1], float(A[2])]]]
    edges += [[[A[0] + 6.0, A[1] - 2.0, z_roof], [A[0] + 6.0, A[1] - 2.0, float(A[2]) - 4.0]]]
    # annexe
    ann = ring(2268)
    za = ground(ann)
    edges += extrude(ann, za, za + 58.0, ring_step=(58.0 / 15))
    return {'Southeast Financial Center': {
        'color': '#d9d9e6', 'world_edges': edges,
        'note': 'Empreinte V16 2267 (dents de scie NE, encoche en V ouest, encoches SE = plan IRL SOM 1984); toit %.1f m; setbacks a partir de z %.0f (43e/55e etage): pyramide a gradins sur les 4 faces en 12 paliers (retraits NE 24 %% / SW 48 %% / SE 45 %% / NW 36 %% ajustes sur le bloc sommital dans 4 cams, rms 5 px; damier de terrasses de Vice City 10, sommet retreci dans Port Vice City A, crete pleine longueur dans Sunrise); mats jusqu a %.1f m; annexe = V16 2268, 58 m ESTIME (15 etages IRL)' % (z_roof, z_set, A[2]),
        '_credit': 'gen_onemiami_sefc_mesh.py 2026-09-20 (V16 + landmarks multi-cams + IRL)'}}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    meshes = {}
    meshes.update(one_miami()); meshes.update(sefc())
    for k, v in meshes.items():
        v['world_edges'] = [[[round(c, 2) for c in p] for p in e] for e in v['world_edges']]
        print('%-32s %5d aretes' % (k, len(v['world_edges'])))
    if a.out:
        json.dump(meshes, open(a.out, 'w'), indent=1, ensure_ascii=True); print('brouillon ->', a.out)
    if a.apply:
        path = os.path.join(ROOT, 'building_meshes_procedural.json')
        M = json.load(open(path)); M.update(meshes)
        json.dump(M, open(path, 'w'), indent=1, ensure_ascii=True); print('applique ->', path)
