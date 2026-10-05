#!/usr/bin/env python3
"""ground_colors.py — couleurs REELLES du sol et de la vegetation du jeu, mesurees sur les frames de jour. [GROUND-COLOR-V1 2026-10-05]

Les materiaux du sol de l'onglet 3D (GROUND-V1) etaient choisis a la main pour chaque couleur de la V16. Ici on les mesure:
pour chaque cam de jour (luminance >= 0.22, pose connue, segmentation SegFormer), les pixels de SOL (route, trottoir,
herbe, sable, terre, champ, chemin, piste) sont rapportes en 3D par lancer de rayon sur la heightmap; la classe V16 du
point touche (tuiles V16 z5, 1 m/px: sable, gazon, parc, ilot urbain, emprise de batiment, rue, autoroute) recoit la
couleur du pixel (corrigee: balance monde gris + exposition ramenee a 0.42, comme facade_colors.py). Vegetation: pixels
arbre / palmier (couleur seule). Agregat: mediane ponderee par cam (chaque cam pese pareil, plafond 4000 px).
Sortie (couche visuelle, ignoree par git): tools/threejs/_ground_colors.json {classes: {nom: {rgb sRGB, n_cams, n_px}}, foliage: {...}}
Usage: python3 tools/ground_colors.py
"""
import json, os, sys, math
import numpy as np
import cv2
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import common
import horizon_resect as HR
from facade_colors import basis, CAMS, SEG, WORK

TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,16', '5')
OUT = os.path.join(THIS, 'threejs', '_ground_colors.json')
GROUND_CLS = (6, 9, 11, 13, 29, 46, 52, 54, 91)     # ADE20K: road, grass, sidewalk, earth, field, sand, path, runway, dirt track
FOLIAGE = {'tree': (4,), 'palm': (72,)}
# [GROUND-COLOR-V1b] couleur PAR CLASSE SEGMENTEE (independante du calage carte/jeu: a quelques metres pres, les pixels de
# route tombaient dans le gazon de la V16 et grisaient l'herbe) -> materiau V16 correspondant dans le rendu
SEGCLS = {'grass': (9, 29), 'sand': (46,), 'road': (6,), 'sidewalk': (11, 52), 'earth': (13, 91)}
V16 = {'sand': (244, 228, 131), 'grass': (193, 217, 131), 'park': (151, 192, 116), 'urban': (217, 217, 217),
       'building': (176, 176, 176), 'road': (83, 83, 83), 'hwy': (114, 114, 114)}
_tc = {}


def v16_class(x, y):
    """classe V16 aux points monde (x, y) — tuiles z5 (1 m/px)."""
    px = np.floor(x + 16384).astype(int); py = np.floor(16384 - y).astype(int)
    out = np.full(len(x), '', dtype=object)
    ref = np.array(list(V16.values()), float); names = list(V16.keys())
    for k in set(zip(px // 256, py // 256)):
        if k not in _tc:
            fp = os.path.join(TILES, '5,%d,%d.jpg' % (k[1], k[0]))
            _tc[k] = np.asarray(Image.open(fp).convert('RGB')).astype(float) if os.path.exists(fp) else None
        T = _tc[k]
        m = (px // 256 == k[0]) & (py // 256 == k[1])
        if T is None: continue
        c = T[py[m] % 256, px[m] % 256]
        d = np.linalg.norm(c[:, None, :] - ref[None, :, :], axis=2); j = d.argmin(1)
        out[np.nonzero(m)[0]] = np.where(d[np.arange(len(j)), j] < 14, np.array(names, dtype=object)[j], '')
    return out


def march(o, d, tmax=2500.0):
    """premier point ou le rayon passe sous la heightmap (pas croissant), NaN sinon."""
    n = len(d); hit = np.full((n, 3), np.nan); alive = np.ones(n, bool); t = np.full(n, 2.0)
    prev = None
    while alive.any():
        P = o[None, :] + t[:, None] * d
        idx = np.nonzero(alive)[0]
        g = HR.ground(P[idx, 0], P[idx, 1])
        below = P[idx, 2] <= np.maximum(g, 0.0)
        hit[idx[below]] = P[idx[below]]; alive[idx[below]] = False
        t[alive] += np.maximum(1.0, 0.015 * t[alive])
        alive &= t < tmax
    return hit


def wmedian(cols, wts):
    out = []
    for ch in range(3):
        o_ = np.argsort(cols[:, ch]); cw = np.cumsum(wts[o_]); out.append(float(cols[o_[np.searchsorted(cw, cw[-1] / 2)], ch]))
    return out


def main():
    C = json.load(open(CAMS)); acc = {k: [] for k in V16}; fol = {k: [] for k in FOLIAGE}; seg = {k: [] for k in SEGCLS}; used = 0
    for cam, c in C.items():
        if c.get('constraint_class') == 'X_excluded': continue
        fp = os.path.join(REPO, 'frames', cam + '.png'); sp = os.path.join(SEG, cam.replace('/', '_') + '_cls.npy')
        if not (os.path.exists(fp) and os.path.exists(sp)): continue
        try:
            cm = common.get_cam(cam); o, f, r, u, fpx, W, H = basis(cm, {'fov': c['fov']})
        except Exception: continue
        if fpx is None: continue
        s = WORK / W; w, h = WORK, int(round(H * s))
        img = np.asarray(Image.open(fp).convert('RGB').resize((w, h), Image.BILINEAR)).astype(np.float32) / 255.0
        if img.mean() < 0.22: continue
        mch = img.reshape(-1, 3).mean(0); lum = float(mch.mean())
        wb = (lum / np.maximum(mch, 1e-3)) * float(np.clip(0.42 / max(lum, 1e-3), 0.75, 1.6))
        cls = np.asarray(Image.fromarray(np.load(sp).astype(np.uint8)).resize((w, h), Image.NEAREST))
        er = lambda m: cv2.erode(m.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        for k, ids in SEGCLS.items():
            m = er(np.isin(cls, ids))
            if m.sum() > 300: seg[k].append((np.median(np.clip(img[m] * wb, 0, 1), axis=0), cam))
        for k, ids in FOLIAGE.items():
            m = er(np.isin(cls, ids))
            if m.sum() > 300: fol[k].append((np.median(np.clip(img[m] * wb, 0, 1), axis=0), cam))
        gm = er(np.isin(cls, GROUND_CLS))
        ys, xs = np.nonzero(gm)
        if len(xs) < 200: continue
        sel = np.random.default_rng(0).choice(len(xs), min(len(xs), 5000), replace=False); xs, ys = xs[sel], ys[sel]
        X = (xs / s - W / 2) / fpx; Y = (H / 2 - ys / s) / fpx
        d = f[None, :] + X[:, None] * r[None, :] + Y[:, None] * u[None, :]; d /= np.linalg.norm(d, axis=1, keepdims=True)
        ok = d[:, 2] < -0.02
        xs, ys, d = xs[ok], ys[ok], d[ok]
        if len(xs) < 100: continue
        P = march(o, d); ok = np.isfinite(P[:, 0])
        if ok.sum() < 100: continue
        k = v16_class(P[ok, 0], P[ok, 1]); col = np.clip(img[ys[ok], xs[ok]] * wb, 0, 1)
        used += 1
        for name in V16:
            m = k == name
            if m.sum() >= 40: acc[name].append((np.median(col[m], axis=0), min(int(m.sum()), 4000), cam))
    res = {'classes': {}, 'foliage': {}, '_src': 'MEASURED day frames (ground_colors.py)', 'n_cams': used}
    for name, L in acc.items():
        if len(L) < 3: continue
        res['classes'][name] = {'rgb': [round(v, 3) for v in wmedian(np.array([a[0] for a in L]), np.ones(len(L)))],
                                'n_cams': len(L), 'n_px': int(sum(a[1] for a in L))}
    res['seg'] = {}
    for name, L in seg.items():
        if len(L) < 3: continue
        res['seg'][name] = {'rgb': [round(v, 3) for v in wmedian(np.array([a[0] for a in L]), np.ones(len(L)))], 'n_cams': len(L)}
    for name, L in fol.items():
        if len(L) < 3: continue
        res['foliage'][name] = {'rgb': [round(v, 3) for v in wmedian(np.array([a[0] for a in L]), np.ones(len(L)))], 'n_cams': len(L)}
    json.dump(res, open(OUT, 'w'), indent=1)
    print('%d cams' % used)
    for grp in ('classes', 'seg', 'foliage'):
        for n, v in res[grp].items(): print('  %-9s rgb %s  (%d cams)' % (n, v['rgb'], v['n_cams']))


if __name__ == '__main__':
    main()
