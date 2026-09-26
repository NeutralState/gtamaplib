#!/usr/bin/env python3
"""v16_resect.py — pose d'une cam par SILHOUETTES + geometrie V16. [V16-RESECT-V1 2026-09-26]

Pourquoi: les landmarks triangules heritent des erreurs de pose des cams qui
les ont produits (Ambrosia: zone glissee de ~130 m le long du rayon de
Panorama). Ici la verite est la V16 (xy exact, calque de la leak map) + la
heightmap (z du sol). Les clics d'image restent la mesure (ils sont precis EN
IMAGE), mais on les apparie a des objets V16, jamais a des landmarks:

  cyl   : bord gauche/droit d'un cylindre vertical (reservoir, silo, chateau
          d'eau) -> le rayon doit etre TANGENT au cercle V16 (independant de
          la hauteur: contrainte de cap + distance pure)
  axis  : point sur l'axe d'un objet vertical fin (cheminee, mat, poteau)
          -> colonne de l'axe V16 a la ligne du clic (hauteur libre)
  ground: point au sol a un xy V16 (coin de route, pied de mur) -> z heightmap
  point : point 3D connu (x,y,z) (a n'utiliser qu'avec une provenance propre)
  rim   : bord superieur d'une cuve = ellipse; lignes du bord lointain (uv[1]) et
          proche (v_near) -> l'aplatissement donne l'angle de vue, donc la hauteur
          de la cam au-dessus du bord (z du bord requis)
  horizon: point de la ligne d'horizon lointaine (colonne u, ligne v) -> horizon
          heightmap dans cet azimut + couvert o['h'] (arbres ~15 m): tient pitch/roll/z

Parametres: x y z yaw pitch roll hfov (bornes autour de l'init), soft-l1,
multi-depart. Sortie: residus par observation avant/apres, pose, et --apply
(sauvegarde cameras.json.bak_v16resect_<cam>).

Fichier d'observations JSON: {"cam": "...", "init": {"xyz":[..],"ypr":[..],"hfov":..}?,
  "obs": [{"type":"cyl","name":"...","uv":[u,v],"c":[x,y],"r":7.0,"side":"L"},
          {"type":"axis","uv":[u,v],"c":[x,y]}, {"type":"ground","uv":[u,v],"c":[x,y]}, ...]}
Usage: PYTHONPATH=. python3 tools/v16_resect.py obs.json [--free xyz,ypr,fov] [--apply]
"""
import json, sys, os, argparse, numpy as np
from scipy.optimize import least_squares
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import gtamaplib as G
import horizon_resect as HR
CAMS = os.path.join(REPO, 'gtamapdata', 'cameras.json')

def ground(x, y): return float(HR.ground(np.array([x]), np.array([y]))[0])

INTR = {'ox': 0.0, 'asp': 1.0}   # decalage du point principal (px) et rapport de pixel (image recadree/etiree)

def mkcam(p, size):
    x, y, z, yaw, pit, rol, hf = p[:7]
    ox = p[7] if len(p) > 7 else INTR['ox']; asp = p[8] if len(p) > 8 else INTR['asp']
    return dict(xyz=[x, y, z], q=G.get_q([yaw, pit, rol]), fov=(hf, G.get_vfov(hf, size)), size=size, ox=ox, asp=asp,
                rinv=G.get_rotation(tuple(G.get_q([yaw, pit, rol]))).inv())

def proj(C, X):
    d = C['rinv'].apply(np.array(X, float) - np.array(C['xyz'], float))
    if d[1] <= 1e-6: return None
    w, h = C['size']; tx = np.tan(np.radians(C['fov'][0]) / 2); ty = np.tan(np.radians(C['fov'][1]) / 2) * C['asp']
    u = ((d[0] / d[1]) / tx + 1) / 2 * w - 0.5 + C['ox']; v = (-(d[2] / d[1]) / ty + 1) / 2 * h - 0.5
    return np.array([u, v])

def col_at_row(C, c, v, zlo=-20, zhi=400):
    """colonne de l'axe vertical en xy=c a la ligne v (bissection sur z)"""
    a, b = proj(C, [c[0], c[1], zlo]), proj(C, [c[0], c[1], zhi])
    if a is None or b is None: return None
    for _ in range(40):
        zm = (zlo + zhi) / 2; m = proj(C, [c[0], c[1], zm])
        if m is None: return None
        if (m[1] - v) * (a[1] - v) > 0: zlo, a = zm, m
        else: zhi, b = zm, m
    return m[0], zm

def tangent_cols(C, c, r, v):
    """colonnes gauche/droite de la silhouette d'un cylindre vertical a la ligne v"""
    cam = np.array(C['xyz'][:2]); d = np.array(c) - cam; D = np.linalg.norm(d)
    if D <= r: return None
    base = np.arctan2(d[1], d[0]); half = np.arcsin(r / D); out = []
    for s in (+1, -1):                                   # deux generatrices tangentes
        a = base + s * (np.pi / 2 + half)                # point tangent sur le cercle
        t = np.array(c) + r * np.array([np.cos(a), np.sin(a)])
        cr = col_at_row(C, t, v)
        if cr is None: return None
        out.append(cr[0])
    return min(out), max(out)

def resid(C, o):
    u, v = o['uv']
    if o['type'] == 'cyl':
        tc = tangent_cols(C, o['c'], o['r'], v)
        if tc is None: return 1e3
        return u - (tc[0] if o['side'] == 'L' else tc[1])
    if o['type'] == 'axis':
        cr = col_at_row(C, o['c'], v)
        return 1e3 if cr is None else u - cr[0]
    if o['type'] == 'rim':
        # ellipse d'un bord de cuve (cercle V16 a la hauteur z): lignes du bord lointain / proche
        t = np.linspace(0, 2 * np.pi, 72); pts = [proj(C, [o['c'][0] + o['r'] * np.cos(a), o['c'][1] + o['r'] * np.sin(a), o['z']]) for a in t]
        if any(q is None for q in pts): return (1e3, 1e3)
        ys = np.array([q[1] for q in pts]); return (o['uv'][1] - ys.min(), o['v_near'] - ys.max())
    if o['type'] == 'horizon':
        # ligne d'horizon du relief (heightmap) + hauteur de couvert o['h'] (arbres) dans la colonne u
        d = G.get_pixel_direction((o['uv'][0] - C['ox'], o['uv'][1]), C['q'], C['fov'], C['size']); az = np.degrees(np.arctan2(d[0], d[1]))
        x, y, z = C['xyz']; hp = HR.horizon_points(x, y, z - o.get('h', 0.0), [az], dmin=o.get('dmin', 800.0))[0]
        p = proj(C, [hp[0], hp[1], hp[2] + o.get('h', 0.0)])
        return 1e3 if p is None else v - p[1]
    if o['type'] in ('ground', 'point'):
        z =ground(*o['c']) + o.get('dz', 0) if o['type'] == 'ground' else o['z']
        p = proj(C, [o['c'][0], o['c'][1], z])
        return (1e3, 1e3) if p is None else (u - p[0], v - p[1])
    raise ValueError(o['type'])

def residuals(p, obs, size):
    C = mkcam(p, size); r = []
    for o in obs:
        e = resid(C, o); w = o.get('w', 1.0)
        r += [w * x for x in (e if isinstance(e, tuple) else (e,))]
    return np.array(r)

def report(p, obs, size, tag):
    C = mkcam(p, size); print('--', tag)
    for o in obs:
        e = resid(C, o); e = np.hypot(*e) if isinstance(e, tuple) else abs(e)
        print('   %-6s %-44s %7.1f px' % (o['type'], o.get('name', '')[:44], e))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('obs'); ap.add_argument('--apply', action='store_true')
    ap.add_argument('--free', default='xyz,ypr,fov'); ap.add_argument('--starts', type=int, default=12)
    ap.add_argument('--bound-xy', type=float, default=250); ap.add_argument('--out')
    ap.add_argument('--intrinsics', action='store_true', help='libere ox (point principal) et asp (rapport de pixel)')
    a = ap.parse_args(); J = json.load(open(a.obs)); CJ = json.load(open(CAMS)); c = CJ[J['cam']]
    size = tuple(c['size']); init = J.get('init', {})
    p0 = np.array(list(init.get('xyz', c['xyz'])) + list(init.get('ypr', c['ypr'])) + [init.get('hfov', c['fov'][0])] + [0.0, 1.0], float)
    free = a.free.split(','); mask = np.array([('xyz' in free)] * 3 + [('ypr' in free)] * 3 + [('fov' in free)] + [a.intrinsics] * 2)
    lo = p0 - np.array([a.bound_xy, a.bound_xy, 60, 40, 15, 5, 25, 600, 0.3]); hi = p0 + np.array([a.bound_xy, a.bound_xy, 120, 40, 15, 5, 25, 600, 0.3])
    obs = J['obs']; report(p0, obs, size, 'INIT')
    def f(q):
        p = p0.copy(); p[mask] = q; return residuals(p, obs, size)
    rng = np.random.default_rng(0); best = None
    for k in range(a.starts):
        q0 = p0[mask] + (0 if k == 0 else rng.normal(0, 1, mask.sum()) * (hi - lo)[mask] * 0.08)
        q0 = np.clip(q0, lo[mask] + 1e-6, hi[mask] - 1e-6)
        try: r = least_squares(f, q0, bounds=(lo[mask], hi[mask]), loss='soft_l1', f_scale=4.0, max_nfev=3000)
        except Exception as e: continue
        if best is None or r.cost < best.cost: best = r
    p = p0.copy(); p[mask] = best.x; report(p, obs, size, 'FIT cost %.1f' % best.cost)
    print('POSE xyz %s ypr %s hfov %.3f  ox %.1f asp %.3f' % (np.round(p[:3], 2).tolist(), np.round(p[3:6], 3).tolist(), p[6], p[7], p[8]))
    print('delta xyz %s' % np.round(p[:3] - np.array(c['xyz']), 1).tolist())
    if a.out: json.dump({'xyz': p[:3].tolist(), 'ypr': p[3:6].tolist(), 'hfov': p[6]}, open(a.out, 'w'))
    if a.apply and a.intrinsics and (abs(p[7]) > 1 or abs(p[8] - 1) > 0.002):
        print('REFUS --apply: intrinseques non standard (ox/asp) non representables dans cameras.json'); return
    if a.apply:
        import shutil; shutil.copy(CAMS, CAMS + '.bak_v16resect_' + J['cam'].replace(' ', '_').replace('(', '').replace(')', ''))
        c['xyz'] = [round(v, 3) for v in p[:3]]; c['ypr'] = [round(v, 4) for v in p[3:6]]; c['fov'] = [round(p[6], 4), c['fov'][1]]
        c['note'] = ('V16-RESECT-V1 2026-09-26: pose par silhouettes appariees a la V16 (%s) | ' % a.obs.split('/')[-1]) + c.get('note', '')
        json.dump(CJ, open(CAMS, 'w'), indent=1, ensure_ascii=True); print('APPLIED')

if __name__ == '__main__': main()
