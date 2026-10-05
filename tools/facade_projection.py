#!/usr/bin/env python3
"""facade_projection.py — les VRAIES textures du jeu projetees sur les batiments 3D. [FACADE-PROJ-V1 2026-10-04]

Chaque cam calibree est un projecteur: un fragment de facade 3D prend la couleur du pixel de frame ou il se projette.
Pour ne pas peindre un arbre / un autre batiment sur une face cachee, on prepare pour chaque cam retenue une carte
d'appartenance (owner map): pour chaque pixel, l'id du batiment visible (volumes de tools/mesh_solids.py peints du plus
loin au plus proche) — seulement la ou la segmentation SegFormer voit du bati (mur/batiment/maison/gratte-ciel).
Le shader n'applique la frame que si owner(uv) == id du batiment (et si la face regarde la cam).
Selection: frames de jour (luminance moyenne >= 0.22); par batiment, ses 2 meilleures cams (nombre de pixels propres);
au plus MAX_LAYERS cams au total (les plus utiles). Balance des blancs par cam (monde gris) transmise au shader.
Sorties (servies par la route statique /threejs/, ignorees par git):
  tools/threejs/_fp_frames.jpg   bande verticale des frames (W x H*N), 1024 x 576 par cam
  tools/threejs/_fp_owners.png   bande des cartes d'appartenance (id+1 en niveau de gris), 512 x 288 par cam
  tools/threejs/_fp_meta.json    cams (origine, axes, focales normalisees, gain), et par batiment ses couches
Usage: python3 tools/facade_projection.py
"""
import json, os, sys, math
import numpy as np
import cv2
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import common
import facade_colors as FC

OUT = os.path.join(THIS, 'threejs')        # la route statique /threejs/ ne sert pas de sous-dossier: fichiers a plat, prefixe _fp_
SOLIDS = os.path.join(THIS, 'threejs', '_mesh_solids.json')
MAX_LAYERS = 28
FW, FH = 1024, 576          # texture frame par cam
OW, OH = 512, 288           # carte d'appartenance
WORK = 1024


def main():
    S = json.load(open(SOLIDS)); C = json.load(open(FC.CAMS))
    names = list(S.keys()); idx = {n: i for i, n in enumerate(names)}
    assert len(names) < 255, 'owner map 8 bits'
    solid = [n for n in names if S[n]['layers']]
    cents = {n: np.mean([q for L in S[n]['layers'] for p in L['polys'] for q in p['outer']], axis=0) for n in solid}
    faces = {n: FC.prisms(S[n]) for n in solid}
    # occultants sans prisme (peage, chateaux d'eau...): faces reconstruites, peintes en 0 dans l'ordre de profondeur
    occl = {}
    for n, so in S.items():
        if so['layers'] or not so.get('ff'): continue
        V = np.array(so['fv'], float).reshape(-1, 3); F = np.array(so['ff'], int).reshape(-1, 3)
        occl[n] = [V[t] for t in F]
        cents[n] = V[:, :2].mean(0)
    cand = {}                                                 # cam -> (owner map OWxOH, stats {name: npx}, basis, wb, img path)
    for cam, c in C.items():
        if c.get('constraint_class') == 'X_excluded': continue
        fp = os.path.join(REPO, 'frames', cam + '.png'); sp = os.path.join(FC.SEG, cam.replace('/', '_') + '_cls.npy')
        if not (os.path.exists(fp) and os.path.exists(sp)) or not c.get('fov') or not c['fov'][0]: continue
        try: cm = common.get_cam(cam); B = FC.basis(cm, {'fov': c['fov']})
        except Exception: continue
        W, H = B[5], B[6]; o = B[0]
        near = [n for n in solid if 40 < np.hypot(*(cents[n] - o[:2])) < 3500]
        if not near: continue
        w, h = WORK, int(round(H * WORK / W)); s = WORK / W
        img = np.asarray(Image.open(fp).convert('RGB').resize((w, h), Image.BILINEAR)).astype(np.float32) / 255.0
        cls0 = np.asarray(Image.fromarray(np.load(sp).astype(np.uint8)).resize((w, h), Image.NEAREST))
        skym = cls0 == 2
        # jour seulement: ciel segmente clair (les frames de nuit/crepuscule peignaient des neons sur les facades)
        if img.mean() < 0.26 or (skym.sum() > 0.02 * skym.size and img[skym].mean() < 0.50): continue
        mch = img.reshape(-1, 3).mean(0); lum = float(mch.mean())
        wb = (lum / np.maximum(mch, 1e-3)) * float(np.clip(0.42 / max(lum, 1e-3), 0.75, 1.6))
        cls = np.asarray(Image.fromarray(np.load(sp).astype(np.uint8)).resize((w, h), Image.NEAREST))
        bmask = np.isin(cls, FC.BUILD_CLS)
        owner = np.zeros((h, w), np.uint8)
        occ_near = [n for n in occl if 20 < np.hypot(*(cents[n] - o[:2])) < 3500]
        for n in sorted(near + occ_near, key=lambda n: -np.hypot(*(cents[n] - o[:2]))):
            for F in (faces[n] if n in faces else occl[n]):
                P, z = FC.proj(B, F, s)
                if (z <= 2).any() or not np.isfinite(P).all(): continue
                if P[:, 0].max() < 0 or P[:, 0].min() > w or P[:, 1].max() < 0 or P[:, 1].min() > h: continue
                cv2.fillPoly(owner, [np.round(P).astype(np.int32)], (idx[n] + 1) if n in faces else 0)
        owner[~bmask] = 0
        owner = cv2.erode(owner, np.ones((3, 3), np.uint8)) * (owner == cv2.dilate(owner, np.ones((3, 3), np.uint8)))   # bords nets
        ids, cnt = np.unique(owner[owner > 0], return_counts=True)
        stats = {names[i - 1]: int(k) for i, k in zip(ids, cnt) if k >= 400}
        if not stats: continue
        cand[cam] = (cv2.resize(owner, (OW, OH), interpolation=cv2.INTER_NEAREST), stats, B, wb, fp)
        print('%-44s %3d batiments %7d px' % (cam[:44], len(stats), sum(stats.values())), flush=True)
    # selection gloutonne: chaque batiment veut ses 2 meilleures cams; on garde les cams qui servent le plus
    want = {}
    for cam, (_, st, *_r) in cand.items():
        for n, k in st.items(): want.setdefault(n, []).append((k, cam))
    score = {}
    for n, L in want.items():
        for k, cam in sorted(L, reverse=True)[:2]: score[cam] = score.get(cam, 0) + k
    chosen = [cam for cam, _ in sorted(score.items(), key=lambda t: -t[1])[:MAX_LAYERS]]
    strip = Image.new('RGB', (FW, FH * len(chosen))); ostrip = np.zeros((OH * len(chosen), OW), np.uint8)
    meta = {'fw': FW, 'fh': FH, 'ow': OW, 'oh': OH, 'cams': [], 'buildings': {}}
    for li, cam in enumerate(chosen):
        owner, st, B, wb, fp = cand[cam]
        o, f, r, u, fpx, W, H = B
        strip.paste(Image.open(fp).convert('RGB').resize((FW, FH), Image.LANCZOS), (0, FH * li))
        ostrip[OH * li:OH * (li + 1)] = owner
        meta['cams'].append({'name': cam, 'o': [round(float(v), 3) for v in o], 'f': [round(float(v), 6) for v in f],
                             'r': [round(float(v), 6) for v in r], 'u': [round(float(v), 6) for v in u],
                             'kx': round(float(fpx / W), 6), 'ky': round(float(fpx / H), 6), 'wb': [round(float(v), 4) for v in wb]})
        for n, k in st.items(): meta['buildings'].setdefault(n, []).append([li, k])
    for n in meta['buildings']: meta['buildings'][n] = [l for l, k in sorted(meta['buildings'][n], key=lambda t: -t[1])[:2]]
    strip.save(os.path.join(OUT, '_fp_frames.jpg'), quality=88)
    Image.fromarray(ostrip).save(os.path.join(OUT, '_fp_owners.png'))
    json.dump(meta, open(os.path.join(OUT, '_fp_meta.json'), 'w'))
    print('%d cams retenues, %d batiments textures' % (len(chosen), len(meta['buildings'])))


if __name__ == '__main__':
    main()
