#!/usr/bin/env python3
"""water_colors.py — couleur REELLE de l'eau du jeu, mesuree sur les frames de jour. [WATER-COLOR-V1 2026-10-05]

Le bleu vif de la V16 est une convention de carte; l'onglet 3D doit montrer l'eau du JEU (riviere vert sombre, baie
bleu-vert, hauts-fonds turquoise...). Pour chaque cam de jour (luminance moyenne >= 0.22, pose connue, segmentation
SegFormer dispo): pixels d'eau (ADE20K water/sea/river/lake; pas les piscines), erodes de 3 px; rayon de chaque pixel
(1 sur 4) intersecte avec z = 0 -> position monde. Gardes: rayon plongeant d'au moins 8 deg (moins de reflet du ciel,
poids = sin(angle)), distance < max(3 km, 12 x altitude), la heightmap dit eau (sol < 0.3 m). Couleur corrigee comme les facades (balance
monde gris + exposition ramenee a 0.42). Agregat par case de 150 m: mediane ponderee + nombre de cams.
Sortie (couche visuelle, ignoree par git): tools/threejs/_water_colors.json {cell, cells:[[x, y, r, g, b, n_cams, w]], median}
Usage: python3 tools/water_colors.py
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

WATER_CLS = (21, 26, 60, 128)
CELL = 150.0
OUT = os.path.join(THIS, 'threejs', '_water_colors.json')


def main():
    C = json.load(open(CAMS)); acc = {}
    used = 0
    for cam, c in C.items():
        if c.get('constraint_class') == 'X_excluded': continue
        fp = os.path.join(REPO, 'frames', cam + '.png'); sp = os.path.join(SEG, cam.replace('/', '_') + '_cls.npy')
        if not (os.path.exists(fp) and os.path.exists(sp)): continue
        try:
            cm = common.get_cam(cam); o, f, r, u, fpx, W, H = basis(cm, {'fov': c['fov']})
        except Exception: continue
        if fpx is None or o[2] < 1.0: continue
        s = WORK / W; w, h = WORK, int(round(H * s))
        img = np.asarray(Image.open(fp).convert('RGB').resize((w, h), Image.BILINEAR)).astype(np.float32) / 255.0
        if img.mean() < 0.22: continue
        cls = np.asarray(Image.fromarray(np.load(sp).astype(np.uint8)).resize((w, h), Image.NEAREST))
        wm = cv2.erode(np.isin(cls, WATER_CLS).astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
        wm[::1, :] &= (np.arange(w)[None, :] % 4 == 0); wm &= (np.arange(h)[:, None] % 4 == 0)
        ys, xs = np.nonzero(wm)
        if len(xs) < 50: continue
        mch = img.reshape(-1, 3).mean(0); lum = float(mch.mean())
        wb = (lum / np.maximum(mch, 1e-3)) * float(np.clip(0.42 / max(lum, 1e-3), 0.75, 1.6))
        X = (xs / s - W / 2) / fpx; Y = (H / 2 - ys / s) / fpx
        d = f[None, :] + X[:, None] * r[None, :] + Y[:, None] * u[None, :]; d /= np.linalg.norm(d, axis=1, keepdims=True)
        sel = d[:, 2] < -math.sin(math.radians(8))
        if sel.sum() < 30: continue
        xs, ys, d = xs[sel], ys[sel], d[sel]
        t = -o[2] / d[:, 2]; P = o[None, :] + t[:, None] * d
        ok = t < max(3000.0, 12.0 * o[2])                                # vues aeriennes: la portee suit l'altitude
        P, xs, ys, d = P[ok], xs[ok], ys[ok], d[ok]
        if len(P) < 30: continue
        g = HR.ground(P[:, 0], P[:, 1]); ok = g < 0.3
        P, xs, ys, d = P[ok], xs[ok], ys[ok], d[ok]
        if len(P) < 30: continue
        col = np.clip(img[ys, xs] * wb, 0, 1); wt = -d[:, 2]
        used += 1
        keys = np.floor(P[:, :2] / CELL).astype(int)
        for k in set(map(tuple, keys)):
            m = (keys[:, 0] == k[0]) & (keys[:, 1] == k[1])
            if m.sum() < 8: continue
            acc.setdefault(k, []).append((np.median(col[m], axis=0), float(wt[m].sum()), cam))
    cells = []
    allc, allw = [], []
    for k, L in acc.items():
        cols = np.array([a[0] for a in L]); wts = np.array([a[1] for a in L])
        med = []
        for ch in range(3):
            o_ = np.argsort(cols[:, ch]); cw = np.cumsum(wts[o_]); med.append(float(cols[o_[np.searchsorted(cw, cw[-1] / 2)], ch]))
        ncam = len({a[2] for a in L})
        cells.append([round((k[0] + 0.5) * CELL, 1), round((k[1] + 0.5) * CELL, 1)] + [round(v, 3) for v in med] + [ncam, round(float(wts.sum()), 1)])
        allc.append(med); allw.append(float(wts.sum()))
    allc = np.array(allc); allw = np.array(allw)
    gmed = [float(np.average(allc[:, ch], weights=allw)) for ch in range(3)] if len(allc) else [0.2, 0.35, 0.4]
    # champ lisse pour le rendu: grille de 150 m, noyau gaussien sigma 450 m, alpha = confiance (poids cumule)
    grid = None
    if cells:
        cc = np.array(cells); pad = 2000.0
        x0, y0 = cc[:, 0].min() - pad, cc[:, 1].min() - pad; x1, y1 = cc[:, 0].max() + pad, cc[:, 1].max() + pad
        nx, ny = int((x1 - x0) / CELL) + 1, int((y1 - y0) / CELL) + 1
        num = np.zeros((ny, nx, 3)); den = np.zeros((ny, nx))
        for x, y, r_, g_, b_, ncam, wt in cells:
            i, j = int((x - x0) / CELL), int((y - y0) / CELL); w_ = min(wt, 200.0) * ncam
            num[j, i] += w_ * np.array([r_, g_, b_]); den[j, i] += w_
        k = cv2.getGaussianKernel(21, 3.0); K = k @ k.T
        num = np.dstack([cv2.filter2D(num[..., ch], -1, K, borderType=cv2.BORDER_CONSTANT) for ch in range(3)])
        den = cv2.filter2D(den, -1, K, borderType=cv2.BORDER_CONSTANT)
        rgb = num / np.maximum(den, 1e-6)[..., None]
        conf = den / (den + 6.0)
        A = np.dstack([np.clip(rgb, 0, 1), conf[..., None]])
        grid = {'x0': round(x0, 1), 'y0': round(y0, 1), 'cell': CELL, 'nx': nx, 'ny': ny,
                'rgba': [int(round(v * 255)) for v in A.reshape(-1)]}
    json.dump({'cell': CELL, 'cells': cells, 'median': [round(v, 3) for v in gmed], 'grid': grid, '_src': 'MEASURED day frames (water_colors.py)'},
              open(OUT, 'w'), separators=(',', ':'))
    print('%d cams, %d cases de %.0f m, couleur moyenne sRGB %s -> %s' % (used, len(cells), CELL, [round(v, 3) for v in gmed], OUT))
    for cc in sorted(cells, key=lambda q: -q[6])[:15]: print('  (%7.0f, %7.0f) rgb %s  %d cams' % (cc[0], cc[1], cc[2:5], cc[5]))


if __name__ == '__main__':
    main()
