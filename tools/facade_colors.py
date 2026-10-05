#!/usr/bin/env python3
"""facade_colors.py — couleur reelle des facades lue sur les frames. [FACADE-COLOR-V1 2026-10-04]

Pour chaque cam (frame de jour, pose connue), les volumes pleins (tools/mesh_solids.py) sont projetes et peints du plus
loin au plus proche (les batiments proches masquent les lointains); on garde les pixels que la segmentation SegFormer
(tools/generated/seg_veg/<cam>_cls.npy) classe en mur/batiment/maison/gratte-ciel (pas les arbres, le ciel, les voitures),
erodes de 2 px. Par batiment et par cam: couleur mediane si >= 300 px, corrigee de la dominante de la frame (balance des
blancs monde gris) et de son exposition (luminance moyenne ramenee a 0.42, facteur borne 0.75-1.6). Agregat: mediane ponderee par le nombre de pixels
sur toutes les cams (frames de nuit exclues: luminance moyenne < 0.22). Ecrit 'facade_color' = {rgb (sRGB 0-1), n_cams,
n_px, cams} dans building_meshes_procedural.json (le rendu 3D l'utilise si aucun 'facade' manuel ne fixe la couleur).
Usage: python3 tools/facade_colors.py [--apply] [--only "Nom"]
"""
import json, os, sys, shutil, math
import numpy as np
import cv2
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import common
import mesh_solids as MS

MESHES = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
CAMS = os.path.join(REPO, 'gtamapdata', 'cameras.json')
SEG = os.path.join(THIS, 'generated', 'seg_veg')
BUILD_CLS = (0, 1, 25, 48)          # ADE20K: wall, building, house, skyscraper
WORK = 1280                         # largeur de travail (px)


def basis(cm, st):
    W, H = cm.size
    f = np.array(cm.get_pixel_direction((W / 2, H / 2)), float); f /= np.linalg.norm(f)
    r = np.array(cm.get_pixel_direction((W / 2 + 100, H / 2)), float); r /= np.linalg.norm(r); r -= f * (r @ f); r /= np.linalg.norm(r)
    u = np.array(cm.get_pixel_direction((W / 2, H / 2 - 100)), float); u /= np.linalg.norm(u); u -= f * (u @ f) + r * (u @ r); u /= np.linalg.norm(u)
    fpx = (W / 2) / math.tan(math.radians(st['fov'][0]) / 2) if st['fov'][0] else None
    return np.array(cm.xyz, float), f, r, u, fpx, W, H


def proj(B, X, s):
    o, f, r, u, fpx, W, H = B; D = X - o; z = D @ f
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.c_[(W / 2 + fpx * (D @ r) / z) * s, (H / 2 - fpx * (D @ u) / z) * s], z


def prisms(so):
    """faces des prismes: [(points 3D d'un polygone ferme), ...] (murs + chapeaux)."""
    out = []
    for L in so['layers']:
        for p in L['polys']:
            O = np.array(p['outer'], float)
            for k in range(len(O)):
                a, b = O[k], O[(k + 1) % len(O)]
                out.append(np.array([[a[0], a[1], L['z0']], [b[0], b[1], L['z0']], [b[0], b[1], L['z1']], [a[0], a[1], L['z1']]]))
            out.append(np.c_[O, np.full(len(O), L['z1'])])
    return out


def run(only=None, S=None, min_px=300):
    S = S or MS.build(); C = json.load(open(CAMS))
    names = [n for n, so in S.items() if so['layers'] and (not only or n == only)]
    cents = {n: np.mean([q for L in S[n]['layers'] for p in L['polys'] for q in p['outer']], axis=0) for n in names}
    faces = {n: prisms(S[n]) for n in names}
    acc = {n: [] for n in names}
    for cam, c in C.items():
        if c.get('constraint_class') == 'X_excluded': continue
        fp = os.path.join(REPO, 'frames', cam + '.png'); sp = os.path.join(SEG, cam.replace('/', '_') + '_cls.npy')
        if not (os.path.exists(fp) and os.path.exists(sp)): continue
        try:
            cm = common.get_cam(cam); st = {'fov': c['fov']}
            B = basis(cm, st)
        except Exception: continue
        if B[4] is None: continue
        W, H = B[5], B[6]; s = WORK / W; w, h = WORK, int(round(H * s))
        o = B[0]
        near = [n for n in names if 40 < np.hypot(*(cents[n] - o[:2])) < 4500]
        if not near: continue
        img = np.asarray(Image.open(fp).convert('RGB').resize((w, h), Image.BILINEAR)).astype(np.float32) / 255.0
        if img.mean() < 0.22: continue                                  # nuit
        # balance des blancs (monde gris) + exposition: un coucher de soleil ou une frame sombre ne doivent pas teinter les facades
        mch = img.reshape(-1, 3).mean(0); lum = float(mch.mean())
        wb = (lum / np.maximum(mch, 1e-3)) * float(np.clip(0.42 / max(lum, 1e-3), 0.75, 1.6))
        cls = np.load(sp)
        cls = np.asarray(Image.fromarray(cls.astype(np.uint8)).resize((w, h), Image.NEAREST))
        bmask = np.isin(cls, BUILD_CLS)
        owner = np.full((h, w), -1, np.int32)
        order = sorted(near, key=lambda n: -np.hypot(*(cents[n] - o[:2])))   # du plus loin au plus proche
        drawn = []
        for idx, n in enumerate(order):
            any_ = False
            for F in faces[n]:
                P, z = proj(B, F, s)
                if (z <= 2).any() or not np.isfinite(P).all(): continue
                if P[:, 0].max() < 0 or P[:, 0].min() > w or P[:, 1].max() < 0 or P[:, 1].min() > h: continue
                cv2.fillPoly(owner, [np.round(P).astype(np.int32)], idx); any_ = True
            if any_: drawn.append(idx)
        if not drawn: continue
        k = np.ones((5, 5), np.uint8)
        for idx in drawn:
            m = (owner == idx)
            m = cv2.erode(m.astype(np.uint8), k).astype(bool) & bmask
            npx = int(m.sum())
            if npx < min_px: continue
            acc[order[idx]].append((np.clip(np.median(img[m], axis=0) * wb, 0, 1), npx, cam))
    out = {}
    for n, L in acc.items():
        if not L: continue
        cols = np.array([x[0] for x in L]); wts = np.array([x[1] for x in L], float)
        med = []
        for ch in range(3):                                            # mediane ponderee par canal
            o_ = np.argsort(cols[:, ch]); cw = np.cumsum(wts[o_]); med.append(float(cols[o_[np.searchsorted(cw, cw[-1] / 2)], ch]))
        out[n] = {'rgb': [round(v, 3) for v in med], 'n_cams': len(L), 'n_px': int(wts.sum()),
                  'cams': [x[2] for x in sorted(L, key=lambda t: -t[1])[:5]]}
    return out


if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    out = run(only)
    for n, v in sorted(out.items(), key=lambda t: -t[1]['n_px'])[:30]:
        print('%-40s rgb %s  %d cams  %d px  (%s)' % (n[:40], v['rgb'], v['n_cams'], v['n_px'], ', '.join(v['cams'][:2])))
    print('%d batiments colores' % len(out))
    if '--apply' in sys.argv:
        shutil.copy(MESHES, MESHES + '.bak_facadecolor')
        M = json.load(open(MESHES))
        for n, v in out.items():
            if n in M: M[n]['facade_color'] = v
        json.dump(M, open(MESHES, 'w'), indent=1, ensure_ascii=True); print('applique')
