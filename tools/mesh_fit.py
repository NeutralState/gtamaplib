#!/usr/bin/env python3
"""mesh_fit.py — score « mesh fit » d'une cam, SANS clics. [MESH-FIT-V2 2026-09-29]

Principe (contraste de decalage): on echantillonne les aretes projetees de chaque
mesh visible (occlusion inter-buildings), on mesure la distance au bord d'image
le plus proche (carte de distance sur les bords forts), puis on refait la meme
mesure en DECALANT toute la projection de quelques pixels dans 8 directions.
Un mesh bien aligne est un creux net: tout decalage degrade le score.

  gain = (cout moyen decale - cout a la pose) / cout moyen decale
  score (0-100) = gain rapporte au gain d'un alignement parfait

Un pourcentage brut « bords a <= 2 px » ne marche pas (V1 refutee: 18-23 % avec la
bonne pose comme avec 1 deg d'erreur, a cause des facades texturees). Le contraste
de decalage annule ce fond commun.

API: compute(cam_name) -> {'score','buildings':{nom:{'score','n','color'}},...}
CLI: PYTHONPATH=. python3 tools/mesh_fit.py "Cam" [--test]
"""
import hashlib, json, os, sys
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import numpy as np
from PIL import Image
from scipy import ndimage
import common
from edgefit_core import build_hulls, _project_pts, _signed_dist_hull

MESHES = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
CAMS = os.path.join(REPO, 'gtamapdata', 'cameras.json')
CACHE = os.path.join(THIS, 'generated', 'mesh_fit')
MIN_PROJ_PX = 18
STEP = 2.0
CAP = 8.0                    # distance max comptee (px)
SHIFT = 5.0                  # decalage de reference (px)
MEASURABLE_CS = 5.0          # distance moyenne au bord (decale) au-dela de laquelle un mesh n'est pas jugeable
SIL = True                   # contour exterieur (silhouette) seulement
DIRS = [(np.cos(a), np.sin(a)) for a in np.linspace(0, 2 * np.pi, 8, endpoint=False)]


class _Ctx:
    def __init__(self, cam_name, state=None):
        self.name = cam_name
        self.cam = common.get_cam(cam_name, state) if state else common.get_cam(cam_name)
        img = np.asarray(Image.open(os.path.join(REPO, 'frames', cam_name + '.png')).convert('L'), float)
        self.H, self.W = img.shape
        g = ndimage.gaussian_filter(img, 1.2)
        gm = np.hypot(ndimage.sobel(g, 0), ndimage.sobel(g, 1))
        edges = gm > np.percentile(gm, 88)
        self.dist = ndimage.distance_transform_edt(~edges)


def _samples(ctx, edges, name, hulls):
    proj = _project_pts(ctx, edges); P = []
    if SIL:
        from scipy.spatial import ConvexHull
        A = np.array([p for ab in proj for p in ab])
        try: hv = A[ConvexHull(A).vertices]
        except Exception: return np.zeros((0, 2))
        proj = [(hv[i], hv[(i + 1) % len(hv)]) for i in range(len(hv))]
    for pa, pb in proj:
        L = float(np.hypot(*(pb - pa)))
        if L < 6: continue
        t = (pb - pa) / L
        for s in np.arange(1, L - 1, STEP): P.append(pa + t * s)
    if not P: return np.zeros((0, 2))
    P = np.array(P)
    m = (P[:, 0] > 8) & (P[:, 0] < ctx.W - 9) & (P[:, 1] > 8) & (P[:, 1] < ctx.H - 9)
    P = P[m]
    if hulls and name in hulls and len(P):
        d0 = hulls[name][1]
        for b2, (eq, d2) in hulls.items():
            if b2 == name or d2 >= d0 or not len(P): continue
            P = P[~(_signed_dist_hull(eq, P) < -1.0)]
    return P


def _cost(ctx, P, dx=0.0, dy=0.0):
    x = np.clip((P[:, 0] + dx).astype(int), 0, ctx.W - 1); y = np.clip((P[:, 1] + dy).astype(int), 0, ctx.H - 1)
    return float(np.mean(np.minimum(ctx.dist[y, x], CAP)))


def _gain(ctx, P, shift=SHIFT):
    c0 = _cost(ctx, P)
    cs = np.mean([_cost(ctx, P, shift * a, shift * b) for a, b in DIRS])
    return (cs - c0) / max(cs, 1e-6), c0, cs


def _visible(ctx, meshes):
    out = {}
    cx, cy = ctx.cam.xyz[0], ctx.cam.xyz[1]
    for name, v in meshes.items():
        e = v.get('world_edges') or []
        if not e or np.hypot(e[0][0][0] - cx, e[0][0][1] - cy) < 25: continue
        pr = _project_pts(ctx, e)
        if len(pr) < 3: continue
        A = np.array([p for ab in pr for p in ab])
        if A[:, 0].max() < 0 or A[:, 0].min() > ctx.W or A[:, 1].max() < 0 or A[:, 1].min() > ctx.H: continue
        if max(np.ptp(A[:, 0]), np.ptp(A[:, 1])) < MIN_PROJ_PX: continue
        out[name] = e
    return out


def _to_score(g, full=0.06):
    # etalonnage 2026-09-29 (silhouettes): global ~0.03-0.06 sur les cams bien calees
    # (Port Vice City A, Gameinformer, Postcard, Fires), ~0.003 sur Convertible (pose
    # decalee), ~0 a 1 deg d'erreur. Par mesh: 0.20 = bord net et colle.
    return int(round(100 * float(np.clip(g / full, 0, 1))))


def evaluate(cam_name, state=None, meshes=None):
    meshes = meshes or json.load(open(MESHES))
    ctx = _Ctx(cam_name, state)
    vis = _visible(ctx, meshes); hulls = build_hulls(ctx, vis)
    per = {}; Ps = []; GW = []
    for name, e in vis.items():
        P = _samples(ctx, e, name, hulls)
        if len(P) < 15: continue
        wpx = min(np.ptp(P[:, 0]), np.ptp(P[:, 1]))          # objets fins (cheminees): decalage < demi-largeur
        g, c0, cs = _gain(ctx, P, float(np.clip(0.3 * wpx, 1.5, SHIFT)))
        if cs > MEASURABLE_CS:      # aucun bord net autour (brume, contre-jour, treillis): non mesurable
            per[name] = {'score': None, 'gain': round(g, 3), 'n': int(len(P)), 'color': meshes[name].get('color', '#facc15')}
            continue
        GW.append((g, len(P)))
        per[name] = {'score': _to_score(g, 0.20), 'gain': round(g, 3), 'n': int(len(P)), 'color': meshes[name].get('color', '#facc15')}
        Ps.append(P)
    tot = None
    if GW:   # moyenne des gains par mesh ponderee par les points (monotone avec l'erreur de pose, teste 2026-09-29)
        g = float(np.average([x[0] for x in GW], weights=[x[1] for x in GW])); tot = _to_score(g, 0.15)
    return {'score': tot, 'n_meshes': len(per), 'n_measured': len(Ps), 'buildings': per}


def compute(cam_name, use_cache=True):
    cams = json.load(open(CAMS)); c = cams.get(cam_name)
    if not c or c.get('xyz') is None or not os.path.exists(os.path.join(REPO, 'frames', cam_name + '.png')): return None
    key = hashlib.md5(json.dumps([c.get('xyz'), c.get('ypr'), c.get('fov'), os.path.getmtime(MESHES), 'v2w']).encode()).hexdigest()
    os.makedirs(CACHE, exist_ok=True); cp = os.path.join(CACHE, cam_name.replace('/', '_') + '.json')
    if use_cache and os.path.exists(cp):
        try:
            d = json.load(open(cp))
            if d.get('key') == key: return d
        except Exception: pass
    d = evaluate(cam_name); d['key'] = key
    json.dump(d, open(cp, 'w'), indent=1, ensure_ascii=True)
    return d


if __name__ == '__main__':
    name = [a for a in sys.argv[1:] if not a.startswith('--')][0]
    if '--test' in sys.argv:
        c = json.load(open(CAMS))[name]; M = json.load(open(MESHES))
        for dy in (0.0, 0.1, 0.3, 1.0):
            st = {'xyz': c['xyz'], 'ypr': [c['ypr'][0] + dy, c['ypr'][1], c['ypr'][2]], 'fov': c['fov']}
            d = evaluate(name, st, M); print('dyaw %.1f deg: score %s (%d meshes)' % (dy, d['score'], d['n_meshes']))
    else:
        d = compute(name, use_cache=False)
        print('score', d['score'], 'meshes', d['n_meshes'])
        for b, v in sorted(d['buildings'].items(), key=lambda kv: -kv[1]['n']): print('   %-40s %3s  (%d pts)' % (b[:40], '-' if v['score'] is None else v['score'], v['n']))
