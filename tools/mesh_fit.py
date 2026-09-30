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
FOLIAGE_MAX = 0.75           # >75 % des points du contour du mesh sur de la vegetation (segmentation SegFormer) -> cache
THIN_PX = 14                 # objets fins (cheminees, treillis): pas de test feuillage (leur structure est texturee)
HIDDEN = set()                # meshes caches declares a la main (cameras.json: hidden_meshes)
EVID_ALL, EVID_TOP, EVID_REGION = 1.6, 3.0, 0.01       # [VIS-EVIDENCE] seuils etalonnes sur Thunderstorm (orage) / Water Tower / Fires
MEASURABLE_CS = 5.0          # distance moyenne au bord (decale) au-dela de laquelle un mesh n'est pas jugeable
SIL = True                   # contour exterieur (silhouette) seulement
import re
LONG = re.compile(r'Bridge|Viaduct|Causeway', re.I)   # [KEYS-BRIDGES-V1] objets longs et fins: aretes reelles, pas d'enveloppe
DIRS = [(np.cos(a), np.sin(a)) for a in np.linspace(0, 2 * np.pi, 8, endpoint=False)]


class _Ctx:
    def __init__(self, cam_name, state=None):
        self.name = cam_name
        self.cam = common.get_cam(cam_name, state) if state else common.get_cam(cam_name)
        img = np.asarray(Image.open(os.path.join(REPO, 'frames', cam_name + '.png')).convert('L'), float)
        self.H, self.W = img.shape
        g = ndimage.gaussian_filter(img, 1.2)
        gm = np.hypot(ndimage.sobel(g, 0), ndimage.sobel(g, 1))
        # bords normalises par le contraste local: un contour doux dans la brume compte autant
        # qu'un contour net au premier plan (sinon les meshes lointains n'ont 'aucun bord')
        gn = gm / (ndimage.gaussian_filter(gm, 25) + 0.5 * np.median(gm) + 1e-6)
        edges = (gn > np.percentile(gn, 85)) & (gm > np.percentile(gm, 20))
        self.dist = ndimage.distance_transform_edt(~edges)
        hp = img - ndimage.gaussian_filter(img, 2)          # texture fine (feuillage) pour la visibilite
        self.tex = np.sqrt(np.maximum(ndimage.uniform_filter(hp ** 2, 7), 0))
        self.tex_thr = np.percentile(self.tex, 70)
        # [VIS-EVIDENCE 2026-09-30] force du bord relative au fond local (mediane 31 px), tolerance de pose +-2 px:
        # un mesh noye dans la brume / l'orage n'a aucun bord la ou sa silhouette tombe (~1.0)
        g1 = ndimage.gaussian_filter(img, 1.0); G = np.hypot(ndimage.sobel(g1, 0), ndimage.sobel(g1, 1))
        self.edge_rel = ndimage.maximum_filter(G / (ndimage.median_filter(G, size=31) + 1.0), size=5)
        try:
            import seg_occlusion
            self.veg = seg_occlusion.load_mask(cam_name)        # masque vegetation (SegFormer ADE20K), None si pas calcule
        except Exception:
            self.veg = None


def _band_masks(ctx, meshes_vis):
    """profondeur la plus proche par pixel, occulteurs = enveloppes convexes par TRANCHE de hauteur
    (une enveloppe unique d'un chateau d'eau - boule + colonne + pieds - masquait tout ce qui est derriere)."""
    from scipy.spatial import ConvexHull
    from PIL import ImageDraw
    depth = np.full((ctx.H, ctx.W), np.inf, np.float32); own = {}
    cam = np.asarray(ctx.cam.xyz, float)
    for name, e in meshes_vis.items():
        if LONG.search(name):                                 # pont: enveloppes par troncons (pas de corde au-dessus de l'eau)
            m = Image.new('L', (ctx.W, ctx.H), 0); dr = ImageDraw.Draw(m); dist = []
            for sel in _chunks(e):
                pr = _project_pts(ctx, sel)
                if len(pr) < 2: continue
                A = np.array([p for ab in pr for p in ab])
                try: dr.polygon([tuple(map(float, p)) for p in A[ConvexHull(A).vertices]], fill=1)
                except Exception: continue
            mk = np.asarray(m, bool); d = float(np.linalg.norm(np.asarray(e, float).reshape(-1, 3).mean(0) - cam))
            own[name] = 0.0; depth[mk] = np.minimum(depth[mk], d); continue
        E = np.asarray(e, float); z = E[..., 2]; zmin, zmax = z.min(), z.max()
        nb = max(1, min(12, int((zmax - zmin) / 6)))
        dist = float(np.linalg.norm(E.reshape(-1, 3).mean(0) - cam))
        m = Image.new('L', (ctx.W, ctx.H), 0); dr = ImageDraw.Draw(m)
        for b in range(nb):
            lo = zmin + (zmax - zmin) * b / nb; hi = zmin + (zmax - zmin) * (b + 1) / nb
            sel = [ab for ab in e if max(ab[0][2], ab[1][2]) >= lo - 1e-6 and min(ab[0][2], ab[1][2]) <= hi + 1e-6]
            pr = _project_pts(ctx, sel)
            if len(pr) < 2: continue
            A = np.array([p for ab in pr for p in ab])
            try: hv = A[ConvexHull(A).vertices]
            except Exception: continue
            dr.polygon([tuple(map(float, p)) for p in hv], fill=1)
        mk = np.asarray(m, bool); own[name] = dist
        depth[mk] = np.minimum(depth[mk], dist)
    return depth, own


def _chunks(edges, L=30.0):
    """decoupe un mesh long en troncons de L m le long de son axe principal (xy)."""
    E = np.asarray(edges, float); M = E.mean(1)[:, :2]; c = M.mean(0)
    u = np.linalg.svd(M - c, full_matrices=False)[2][0]; t = (M - c) @ u
    k = np.floor((t - t.min()) / L).astype(int)
    return [[edges[i] for i in np.nonzero(k == j)[0]] for j in range(k.max() + 1) if (k == j).any()]


def _samples_long(ctx, edges):
    """contour d'un pont: bord des enveloppes par troncon, sans les coutures (points interieurs au troncon voisin)."""
    from scipy.spatial import ConvexHull
    def inside(hv, pts, m=1.5):   # enveloppe convexe (sens trigo de ConvexHull): dedans a plus de m px du bord
        a = hv; b = np.roll(hv, -1, 0); e = b - a; ln = np.hypot(e[:, 0], e[:, 1]) + 1e-9
        cr = (e[None, :, 0] * (pts[:, None, 1] - a[None, :, 1]) - e[None, :, 1] * (pts[:, None, 0] - a[None, :, 0])) / ln[None]
        return (cr > m).all(1)
    H = []
    for sel in _chunks(edges):
        pr = _project_pts(ctx, sel)
        if len(pr) < 2: continue
        A = np.array([p for ab in pr for p in ab])
        try: H.append(A[ConvexHull(A).vertices])
        except Exception: continue
    P = []
    for i, hv in enumerate(H):
        pts = []
        for j in range(len(hv)):
            pa, pb = hv[j], hv[(j + 1) % len(hv)]; Lg = float(np.hypot(*(pb - pa)))
            if Lg < 6: continue
            tt = (pb - pa) / Lg; pts += [pa + tt * s_ for s_ in np.arange(1, Lg - 1, STEP)]
        if not pts: continue
        pts = np.array(pts); keep = np.ones(len(pts), bool)
        for j in (i - 1, i + 1):
            if 0 <= j < len(H): keep &= ~inside(H[j], pts)
        P += list(pts[keep])
    return P


def _samples(ctx, edges, name, hulls):
    if LONG.search(name):
        P = _samples_long(ctx, edges)
        return _clip_occ(ctx, np.array(P) if P else np.zeros((0, 2)), name, hulls)
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
    return _clip_occ(ctx, np.array(P) if P else np.zeros((0, 2)), name, hulls)


def _clip_occ(ctx, P, name, hulls):
    if not len(P): return np.zeros((0, 2))
    m = (P[:, 0] > 8) & (P[:, 0] < ctx.W - 9) & (P[:, 1] > 8) & (P[:, 1] < ctx.H - 9)
    P = P[m]
    if hulls is not None and len(P):
        depth, own = hulls
        d0 = own.get(name, np.inf)
        yi = np.clip(P[:, 1].astype(int), 0, ctx.H - 1); xi = np.clip(P[:, 0].astype(int), 0, ctx.W - 1)
        P = P[depth[yi, xi] >= d0 - 1.0]      # garde si aucun mesh plus proche ne couvre le pixel
    return P


def _foliage(ctx, edges):
    """part de l'empreinte ecran du mesh couverte de texture fine (arbres devant). None si objet fin."""
    from scipy.spatial import ConvexHull
    from PIL import ImageDraw
    pr = _project_pts(ctx, edges)
    A = np.array([p for ab in pr for p in ab])
    try: hv = A[ConvexHull(A).vertices]
    except Exception: return None
    m = Image.new('L', (ctx.W, ctx.H), 0); ImageDraw.Draw(m).polygon([tuple(map(float, p)) for p in hv], fill=1)
    m = np.asarray(m, bool)
    if m.sum() < 50: return None
    if ctx.veg is not None and ctx.veg.shape == m.shape:
        # les arbres cachent par le bas: on juge la moitie HAUTE de l'empreinte (un chateau d'eau dont
        # la colonne est dans les arbres mais la boule depasse reste visible)
        ys = np.nonzero(m.any(1))[0]; top = m.copy(); top[int((ys[0] + ys[-1]) / 2):, :] = False
        return float(ctx.veg[top].mean()) if top.sum() >= 25 else float(ctx.veg[m].mean())                     # part de l'empreinte couverte d'arbres (segmentation)
    return None                                             # pas de segmentation: pas de decision


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
        if LONG.search(name):      # ponts: a plus de 6 km ils sont caches par le decor (arbres, iles) que les meshes ne modelisent pas
            E_ = np.asarray(e, float).reshape(-1, 3)
            if np.hypot(E_[:, 0] - cx, E_[:, 1] - cy).min() > 6000: continue
        pr = _project_pts(ctx, e)
        if len(pr) < 3: continue
        A = np.array([p for ab in pr for p in ab])
        if A[:, 0].max() < 0 or A[:, 0].min() > ctx.W or A[:, 1].max() < 0 or A[:, 1].min() > ctx.H: continue
        if max(np.ptp(A[:, 0]), np.ptp(A[:, 1])) < MIN_PROJ_PX: continue
        out[name] = e
    return out


def _region_edges(ctx, edges):
    """densite de bords detectes dans l'enveloppe projetee du mesh (0 = zone lisse: ciel, nuage, pluie)."""
    from scipy.spatial import ConvexHull
    from PIL import ImageDraw
    pr = _project_pts(ctx, edges); A = np.array([p for ab in pr for p in ab])
    try: hv = A[ConvexHull(A).vertices]
    except Exception: return 1.0
    m = Image.new('L', (ctx.W, ctx.H), 0); ImageDraw.Draw(m).polygon([tuple(map(float, p)) for p in hv], fill=1); m = np.asarray(m, bool)
    return float((ctx.dist[m] < 1).mean()) if m.sum() >= 30 else 1.0


def _to_score(g, full=0.06):
    # etalonnage 2026-09-29 (silhouettes): global ~0.03-0.06 sur les cams bien calees
    # (Port Vice City A, Gameinformer, Postcard, Fires), ~0.003 sur Convertible (pose
    # decalee), ~0 a 1 deg d'erreur. Par mesh: 0.20 = bord net et colle.
    return int(round(100 * float(np.clip(g / full, 0, 1))))


def evaluate(cam_name, state=None, meshes=None):
    meshes = meshes or json.load(open(MESHES))
    global HIDDEN
    HIDDEN = set(json.load(open(CAMS)).get(cam_name, {}).get('hidden_meshes') or [])
    ctx = _Ctx(cam_name, state)
    vis = _visible(ctx, meshes); hulls = _band_masks(ctx, vis)
    per = {}; Ps = []; GW = []
    for name, e in vis.items():
        P = _samples(ctx, e, name, hulls)
        if len(P) < 15: continue
        wpx = min(np.ptp(P[:, 0]), np.ptp(P[:, 1]))          # objets fins (cheminees): decalage < demi-largeur
        g, c0, cs = _gain(ctx, P, float(np.clip(0.3 * wpx, 1.5, SHIFT)))
        fol = None
        if ctx.veg is not None:   # part des points du contour du mesh (non occultes) tombant sur de la vegetation
            yi = np.clip(P[:, 1].astype(int), 0, ctx.H - 1); xi = np.clip(P[:, 0].astype(int), 0, ctx.W - 1)
            fol = float(ctx.veg[yi, xi].mean())
        yi = np.clip(P[:, 1].astype(int), 0, ctx.H - 1); xi = np.clip(P[:, 0].astype(int), 0, ctx.W - 1)
        er = ctx.edge_rel[yi, xi]; top = P[:, 1] <= np.percentile(P[:, 1], 15)
        ev_all, ev_top = float(np.median(er)), float(np.median(er[top]))
        seen = ev_all >= EVID_ALL or ev_top >= EVID_TOP        # silhouette entiere, ou seulement le haut (tour qui depasse de la brume)
        if not seen:   # bords faibles: cache SEULEMENT si toute la zone du mesh est lisse (orage/brouillard); sinon (contre-jour,
            # treillis, pose un peu decalee) l'objet est la mais mal aligne -> reste affiche
            seen = _region_edges(ctx, e) >= EVID_REGION
        hidden = 'manuel' if name in HIDDEN else ('arbres' if (fol is not None and fol > FOLIAGE_MAX) else (None if seen else 'brume'))
        if hidden:                  # cache (arbres nets ou liste hidden_meshes de la cam): ni dessin, ni etiquette, ni score
            per[name] = {'score': None, 'visible': False, 'hidden': hidden, 'foliage': fol, 'gain': round(g, 3), 'n': int(len(P)), 'color': meshes[name].get('color', '#facc15')}
            continue
        if (c0 > MEASURABLE_CS and cs > MEASURABLE_CS) or LONG.search(name):   # brume/contre-jour, ou pont (un tablier long ne se
            # localise que perpendiculairement a son axe: le contraste par decalage ne le mesure pas): dessine mais non mesure (—)
            per[name] = {'score': None, 'visible': True, 'hidden': None, 'foliage': fol, 'gain': round(g, 3), 'n': int(len(P)), 'color': meshes[name].get('color', '#facc15')}
            continue
        GW.append((g, len(P)))
        per[name] = {'visible': True, 'foliage': fol, 'score': _to_score(g, 0.20), 'gain': round(g, 3), 'n': int(len(P)), 'color': meshes[name].get('color', '#facc15')}
        Ps.append(P)
    tot = None
    if GW:   # moyenne des gains par mesh ponderee par les points (monotone avec l'erreur de pose, teste 2026-09-29)
        g = float(np.average([x[0] for x in GW], weights=[x[1] for x in GW])); tot = _to_score(g, 0.15)
    return {'score': tot, 'n_meshes': sum(1 for v in per.values() if v.get('visible')), 'n_measured': len(Ps), 'buildings': per}


def compute(cam_name, use_cache=True):
    cams = json.load(open(CAMS)); c = cams.get(cam_name)
    if not c or c.get('xyz') is None or not os.path.exists(os.path.join(REPO, 'frames', cam_name + '.png')): return None
    key = hashlib.md5(json.dumps([os.path.getmtime(os.path.join(THIS, 'generated', 'seg_veg', cam_name.replace('/', '_') + '.png')) if os.path.exists(os.path.join(THIS, 'generated', 'seg_veg', cam_name.replace('/', '_') + '.png')) else 0, c.get('xyz'), c.get('ypr'), c.get('fov'), c.get('hidden_meshes'), os.path.getmtime(MESHES), 'v8evid2']).encode()).hexdigest()
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
        for b, v in sorted(d['buildings'].items(), key=lambda kv: -kv[1]['n']): print('   %-40s %3s  (%d pts)%s' % (b[:40], '-' if v['score'] is None else v['score'], v['n'], '' if v.get('visible') else '  CACHE (%s)' % v.get('hidden')))
