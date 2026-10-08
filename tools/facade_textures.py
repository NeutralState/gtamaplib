#!/usr/bin/env python3
"""facade_textures.py — facades REELLES du jeu redressees depuis les frames et posees sur les faces des meshes mesures. [FACADE-TEX-V1 2026-10-07]

Generalise led_facades.py a toutes les faces des volumes pleins (tools/mesh_solids.py):
  - cams: frames de JOUR dont la pose est confirmee par l'audit (tools/generated/pose_audit.json: >= 6 volumes juges et
    decalage global |shift| <= 1.5 px; ce decalage horizontal est corrige a l'echantillonnage);
  - pour chaque face (arete du contour d'une couche, z0 -> z1): la meilleure vue = face vue de face (cos >= 0.35),
    grande (>= 90 px de large dans la frame), degagee: un texel est valide si le volume vu a ce pixel est bien CE batiment
    (rendu peintre de tous les volumes) et si la segmentation y voit un mur/batiment (pas d'arbre, de personne, de ciel);
  - texture RGBA (1 texel ~ 1 px de frame, borne 0.15-2 m, <= 1024 px), alpha 0 la ou la facade est cachee (la couleur
    de base du volume reste visible dessous), au moins 45 % de texels valides.
Sorties (DERIVEES DES FRAMES, ignorees par git): tools/threejs/_fac_<id>.png + tools/threejs/_facade_tex.json
[{building, a, b, z0, z1, n, img, cam, tod (day/night), valid, px}]; les frames de nuit donnent une texture de NUIT (fenetres allumees). Usage: python3 tools/facade_textures.py [--only "Nom"] [--max-cams N]
"""
import json, os, sys, math, hashlib
import numpy as np
import cv2
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import common
import mesh_solids as MS
from facade_colors import prisms, CAMS, SEG
from mesh_pose_audit import basis, clip_near

AUD = os.path.join(THIS, 'generated', 'pose_audit.json')
OUTD = os.path.join(THIS, 'threejs')                 # a plat: le serveur ne sert pas de sous-dossier de /threejs/
OUTJ = os.path.join(THIS, 'threejs', '_facade_tex.json')
BUILD_CLS = (0, 1, 25, 48)
RW = 1920                       # largeur du rendu d'occultation
EXCLUDE = {'Vice Beach (B)': 'titre "Rockstar Games presents" incruste sur les facades'}
DAY_MIN, NIGHT_MAX = 0.42, 0.34   # luminance moyenne de la frame: jour >= 0.42; nuit/crepuscule tardif <= 0.34 (lumieres de fenetres)


def faces_of(so):
    """faces verticales: (a, b, z0, z1, n_out) par arete de contour exterieur de chaque couche."""
    out = []
    for L in so['layers']:
        for p in L['polys']:
            O = np.array(p['outer'], float)
            if len(O) < 3: continue
            ar = np.sum(O[:, 0] * np.roll(O[:, 1], -1) - np.roll(O[:, 0], -1) * O[:, 1]) / 2
            for k in range(len(O)):
                a, b = O[k], O[(k + 1) % len(O)]; L_ = float(np.hypot(*(b - a)))
                if L_ < 3.0 or L['z1'] - L['z0'] < 3.0: continue
                t = (b - a) / L_; n = np.array([t[1], -t[0]]) if ar > 0 else np.array([-t[1], t[0]])   # normale exterieure
                out.append((a, b, float(L['z0']), float(L['z1']), n))
    return out


def main():
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    S = MS.build(); C = json.load(open(CAMS)); A = json.load(open(AUD))
    names = [n for n, so in S.items() if so['layers']]
    cents = {n: np.mean([q for L in S[n]['layers'] for p in L['polys'] for q in p['outer']], axis=0) for n in names}
    pr = {n: prisms(S[n]) for n in names}
    F = {n: faces_of(S[n]) for n in names if not only or n == only}
    cams = [c for c, o in A.items() if o.get('fit') and o['n_judged'] >= 6 and abs(o['fit']['shift_px']) <= 1.5 and c not in EXCLUDE]
    tod = {}
    for c in cams:
        lum = float(np.asarray(Image.open(os.path.join(REPO, 'frames', c + '.png')).convert('L').resize((480, 270))).mean() / 255)
        tod[c] = 'day' if lum >= DAY_MIN else ('night' if lum <= NIGHT_MAX else None)
    cams = [c for c in cams if tod[c]]
    print('cams fiables:', {c: tod[c] for c in cams})
    best = {}                                                   # (batiment, i_face, jour/nuit) -> (score, entry, rgba)
    for cam in cams:
        fp = os.path.join(REPO, 'frames', cam + '.png'); sp = os.path.join(SEG, cam.replace('/', '_') + '_cls.npy')
        if not (os.path.exists(fp) and os.path.exists(sp)): continue
        cm = common.get_cam(cam); B = basis(cm); o, f, r, u, fpx, W, H = B
        img = np.asarray(Image.open(fp).convert('RGB')); fh, fw = img.shape[:2]; kf = fw / W     # pixels frame / pixels camera
        cls = np.load(sp); kc = cls.shape[1] / fw
        sh = A[cam]['fit']['shift_px'] * fw / 1280.0            # decalage horizontal mesure (px frame)
        s = RW / W; rh = int(round(H * s))
        order = sorted([n for n in names if 30 < np.hypot(*(cents[n] - o[:2])) < 6000], key=lambda n: -np.hypot(*(cents[n] - o[:2])))
        owner = np.full((rh, RW), -1, np.int32)
        for idx, n in enumerate(order):
            for Fc in pr[n]:
                Fc = clip_near(Fc, B)
                if Fc is None: continue
                D = Fc - o; z = D @ f
                P = np.c_[(W / 2 + fpx * (D @ r) / z) * s, (H / 2 - fpx * (D @ u) / z) * s]
                if not np.isfinite(P).all() or np.abs(P).max() > 1e5: continue
                cv2.fillPoly(owner, [np.round(P).astype(np.int32)], idx)
        oidx = {n: i for i, n in enumerate(order)}
        for n, fl in F.items():
            if n not in oidx: continue
            bi = oidx[n]
            for fi, (a, b, z0, z1, nv) in enumerate(fl):
                mid = np.array([*(a + b) / 2, (z0 + z1) / 2]); v = o - mid; dist = float(np.linalg.norm(v))
                cosv = float(np.dot(nv, v[:2]) / max(np.linalg.norm(v), 1e-9))
                if cosv < 0.35: continue
                def px(X):
                    D = np.asarray(X, float) - o; z = D @ f
                    return np.c_[(W / 2 + fpx * (D @ r) / z) * kf + sh, (H / 2 - fpx * (D @ u) / z) * kf], z
                (pa, za), (pb, zb) = px(np.array([*a, (z0 + z1) / 2])[None]), px(np.array([*b, (z0 + z1) / 2])[None])
                if za[0] < 5 or zb[0] < 5: continue
                wpx = float(np.hypot(*(pb[0] - pa[0])))
                if wpx < 90: continue
                L_ = float(np.hypot(*(b - a))); t = (b - a) / L_
                res = float(np.clip(dist / (fpx * kf) * 1.0, 0.15, 2.0))
                ns, nz = int(min(1024, max(8, L_ / res))), int(min(1024, max(8, (z1 - z0) / res)))
                ss = (np.arange(ns) + 0.5) / ns * L_; zz = z1 - (np.arange(nz) + 0.5) / nz * (z1 - z0)
                SS, ZZ = np.meshgrid(ss, zz)
                X = np.stack([a[0] + t[0] * SS + nv[0] * 0.05, a[1] + t[1] * SS + nv[1] * 0.05, ZZ], -1).reshape(-1, 3)
                P, z = px(X)
                inside = (z > 1) & (P[:, 0] >= 0) & (P[:, 0] < fw - 1) & (P[:, 1] >= 0) & (P[:, 1] < fh - 1)
                if inside.mean() < 0.45: continue
                xi = np.clip(P[:, 0], 0, fw - 1); yi = np.clip(P[:, 1], 0, fh - 1)
                ow = owner[np.clip(((yi) / kf * s).astype(int), 0, rh - 1), np.clip(((xi - sh) / kf * s).astype(int), 0, RW - 1)]
                cl = cls[np.clip((yi * kc).astype(int), 0, cls.shape[0] - 1), np.clip((xi * kc).astype(int), 0, cls.shape[1] - 1)]
                valid = inside & (ow == bi) & np.isin(cl, BUILD_CLS)
                vf = float(valid.mean())
                if vf < 0.45: continue
                score = vf * wpx * cosv
                key = (n, fi, tod[cam])
                if key in best and best[key][0] >= score: continue
                mx = P[:, 0].reshape(nz, ns).astype(np.float32); my = P[:, 1].reshape(nz, ns).astype(np.float32)
                rgb = cv2.remap(img, mx, my, cv2.INTER_LINEAR)
                al = (valid.reshape(nz, ns) * 255).astype(np.uint8)
                al = cv2.erode(al, np.ones((3, 3), np.uint8))                                  # pas de franges aux bords
                g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32); m_ = al > 0
                if m_.sum() < 64: continue
                sharp = float(cv2.Laplacian(g, cv2.CV_32F)[m_].var()); contrast = float(g[m_].std())
                if tod[cam] == 'day' and (sharp < 25 or contrast < 10): continue                # flou / brume: la couleur de base vaut mieux
                best[key] = (score, {'building': n, 'a': [round(float(a[0]), 2), round(float(a[1]), 2)], 'b': [round(float(b[0]), 2), round(float(b[1]), 2)],
                                     'z0': round(z0, 2), 'z1': round(z1, 2), 'n': [round(float(nv[0]), 4), round(float(nv[1]), 4)],
                                     'cam': cam, 'tod': tod[cam], 'valid': round(vf, 2), 'px': [ns, nz], 'wpx': round(wpx), 'sharp': round(sharp)}, np.dstack([rgb, al]))
        print('%-45s faces retenues jusqu ici: %d' % (cam[:45], len(best)))
    for fn in os.listdir(OUTD):
        if fn.startswith('_fac_') and fn.endswith('.png'): os.remove(os.path.join(OUTD, fn))
    out = []
    for (n, fi, td), (sc, e, rgba) in sorted(best.items()):
        fid = hashlib.md5(('%s|%d|%s' % (n, fi, td)).encode()).hexdigest()[:12]
        Image.fromarray(rgba, 'RGBA').save(os.path.join(OUTD, '_fac_' + fid + '.png'), optimize=True)
        e['img'] = '_fac_' + fid + '.png'; out.append(e)
    json.dump(out, open(OUTJ, 'w'), indent=1)
    by = {}
    for e in out: by.setdefault(e['building'], []).append(e)
    print('%d textures (%d jour, %d nuit) sur %d batiments -> %s' % (len(out), sum(e['tod'] == 'day' for e in out), sum(e['tod'] == 'night' for e in out), len(by), OUTJ))
    for n, L in sorted(by.items(), key=lambda t: -len(t[1]))[:25]: print('  %-38s %2d faces  (%s)' % (n[:38], len(L), ', '.join(sorted({e['cam'] for e in L}))[:90]))


if __name__ == '__main__':
    main()
