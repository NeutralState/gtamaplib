#!/usr/bin/env python3
"""night_lights.py — eclairages decoratifs REELS des batiments (neons, couronnes), mesures sur les frames de nuit. [NIGHT-LIGHTS-V1 2026-10-05]

Regle (Alexandre): rien de decoratif « pour le style »; un batiment n'a un neon que si une frame le montre.
Pour chaque cam de nuit/crepuscule (luminance moyenne < 0.30, pose connue), les volumes pleins (tools/mesh_solids.py) sont
projetes FACE par face et peints du plus loin au plus proche (carte d'appartenance pixel -> face). Pixels neon: lumineux
(V > 0.55) et satures (S > 0.45), teinte HORS des oranges/jaunes (15-62 deg = fenetres, sodium). Chaque pixel neon est
rapporte en 3D par intersection de son rayon avec le plan de SA face -> hauteur reelle. Par batiment: couleur (mediane,
normalisee en luminosite), bande de hauteur (p5-p95), part verticale vs horizontale de la repartition, pixels, cams.
Seuls les pixels classes bati par SegFormer (mur/batiment/maison/gratte-ciel, dilate 3 px) comptent: les personnages,
objets, le ciel du couchant et les incrustations au premier plan sont exclus.
Garde: >= 60 px neon (a 1280 px de large) dans au moins une cam, et >= 0.4 % de la surface vue du batiment.
Ecrit 'night_light' = {rgb (sRGB 0-1), z0, z1, top, pattern band|vertical, n_px, frac, cams, _src} dans
building_meshes_procedural.json avec --apply (le rendu 3D n'allume QUE ces batiments).
Usage: python3 tools/night_lights.py [--apply] [--only "Nom"] [--debug DIR]
"""
import json, os, sys, shutil, math, colorsys
import numpy as np
import cv2
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import common
import mesh_solids as MS
from facade_colors import basis, prisms, MESHES, CAMS, WORK, SEG, BUILD_CLS


# batiments vus avec neon dans UNE seule cam, verifies a l'oeil sur la frame (attribution sans ambiguite: pas de
# batiment non modelise devant). Ajouter ici seulement apres verification visuelle, avec la raison.
VERIFIED_SINGLE = {
    'Vizcayne North Condominium': ('Jason Duval 05 (Machine Gun)', 'twin green crowns, labels land on both crowns (2026-10-05)'),
}
# EN ATTENTE (ambigu): Vice Beach Panorama, neon vert sur l'immeuble a toit courbe au premier plan — 1500 Ocean Dr (label au
# bout du toit) ou McAlpin Ocean Plaza (projection sous les neons, mesh plus bas que le toit vu)? a trancher avant d'allumer.
# jumeaux: meme eclairage vu sur la frame -> la bande de hauteur du jumeau le mieux mesure (relative au sommet)
TWINS = {'Vizcayne North Condominium': ('Vizcayne South Condominium', 'JD05 shows two identical green crowns; North has only 214 px')}
# attributions automatiques REFUTEES a l'oeil (ne jamais allumer): neons d'un batiment non modelise ou faux positifs de segmentation
REJECTED = {'One Broadway': 'Grotti: car interior segmented as building', 'Quantum on the Bay (South)': 'Strip Club: pink on the near club wall',
            'Jade Ocean Condos': 'Ocean View Hotel neon (hotel not modelled)', 'Flamingo South Beach': 'Ocean View sign (Ocean Drive)'}


def neon_mask(img):
    hsv = cv2.cvtColor((img * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    H, S, V = hsv[..., 0] * 2.0, hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    warm = (H >= 15) & (H <= 62)
    return (V > 0.55) & (S > 0.45) & ~warm


def run(only=None, debug=None):
    S = MS.build(); C = json.load(open(CAMS))
    names = [n for n, so in S.items() if so['layers'] and (not only or n == only)]
    cents = {n: np.mean([q for L in S[n]['layers'] for p in L['polys'] for q in p['outer']], axis=0) for n in names}
    tops = {n: max(L['z1'] for L in S[n]['layers']) for n in names}
    faces = {n: prisms(S[n]) for n in names}
    acc = {n: [] for n in names}
    for cam, c in C.items():
        if c.get('constraint_class') == 'X_excluded': continue
        fp = os.path.join(REPO, 'frames', cam + '.png'); sp = os.path.join(SEG, cam.replace('/', '_') + '_cls.npy')
        if not (os.path.exists(fp) and os.path.exists(sp)): continue      # sans segmentation: personnages/objets au premier plan indiscernables
        try:
            cm = common.get_cam(cam); B = basis(cm, {'fov': c['fov']})
        except Exception: continue
        if B[4] is None: continue
        o, f, r, u, fpx, W, H = B; s = WORK / W; w, h = WORK, int(round(H * s))
        near = [n for n in names if 30 < np.hypot(*(cents[n] - o[:2])) < 5000]
        if not near: continue
        img = np.asarray(Image.open(fp).convert('RGB').resize((w, h), Image.BILINEAR)).astype(np.float32) / 255.0
        if img.mean() >= 0.30: continue                                    # jour: pas de neon mesurable
        # toutes les faces visibles, triees du plus loin au plus proche (centroide)
        FL = []
        for n in near:
            for F in faces[n]:
                D = F - o; z = D @ f
                if (z <= 2).any(): continue
                P = np.c_[(W / 2 + fpx * (D @ r) / z) * s, (H / 2 - fpx * (D @ u) / z) * s]
                if not np.isfinite(P).all() or P[:, 0].max() < 0 or P[:, 0].min() > w or P[:, 1].max() < 0 or P[:, 1].min() > h: continue
                nrm = np.cross(F[1] - F[0], F[2] - F[0]); ln = np.linalg.norm(nrm)
                if ln < 1e-6: continue
                FL.append((float(np.linalg.norm(F.mean(0) - o)), n, P, F[0], nrm / ln))
        if not FL: continue
        FL.sort(key=lambda t: -t[0])
        owner = np.full((h, w), -1, np.int32)
        for i, (_, n, P, p0, nrm) in enumerate(FL):
            cv2.fillPoly(owner, [np.round(P).astype(np.int32)], i)
        cls = np.asarray(Image.fromarray(np.load(sp).astype(np.uint8)).resize((w, h), Image.NEAREST))
        bmask = cv2.dilate(np.isin(cls, BUILD_CLS).astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
        nm = neon_mask(img) & bmask                                       # seulement sur du bati (pas les gens, le ciel, les objets)
        ys, xs = np.nonzero(nm & (owner >= 0))
        if not len(xs): continue
        fid = owner[ys, xs]
        # rayons des pixels neon -> intersection avec le plan de leur face
        X = (xs / s - W / 2) / fpx; Y = (H / 2 - ys / s) / fpx
        d = f[None, :] + X[:, None] * r[None, :] + Y[:, None] * u[None, :]
        P0 = np.array([FL[i][3] for i in fid]); N = np.array([FL[i][4] for i in fid])
        den = np.einsum('ij,ij->i', N, d); t = np.einsum('ij,ij->i', N, P0 - o) / np.where(np.abs(den) < 1e-9, 1e-9, den)
        Pw = o[None, :] + t[:, None] * d
        bn = np.array([FL[i][1] for i in fid])
        seen = {}
        for i, (_, n, *_r) in enumerate(FL): seen.setdefault(n, []).append(i)
        area = {n: int(np.isin(owner, ids).sum()) for n, ids in seen.items()}
        for n in set(bn.tolist()):
            m = bn == n
            if m.sum() < 60 or m.sum() < 0.004 * max(area.get(n, 1), 1): continue
            col = img[ys[m], xs[m]]
            acc[n].append(dict(cam=cam, px=int(m.sum()), frac=float(m.sum() / max(area[n], 1)),
                               rgb=np.median(col / np.maximum(col.max(1, keepdims=True), 1e-3), axis=0),
                               z=Pw[m, 2], xy=Pw[m, :2], ix=xs[m], iy=ys[m]))
        if debug:
            os.makedirs(debug, exist_ok=True)
            vis = (img * 255).astype(np.uint8).copy(); vis[nm & (owner >= 0)] = (255, 0, 255)
            Image.fromarray(vis).save(os.path.join(debug, cam.replace('/', '_') + '.jpg'), quality=85)
    out = {}
    def hue(c): return colorsys.rgb_to_hsv(*[float(v) for v in c])[0] * 360.0
    for n, L in acc.items():
        if not L: continue
        # ACCORD: >= 2 cams independantes, meme teinte (< 35 deg) — un batiment non modelise au premier plan (enseigne d'un
        # hotel bas) fait attribuer ses neons a la tour derriere dans UNE vue, jamais de facon coherente dans deux
        best = []
        for a in L:
            grp = [b for b in L if min(abs(hue(a['rgb']) - hue(b['rgb'])), 360 - abs(hue(a['rgb']) - hue(b['rgb']))) < 35]
            if len({b['cam'] for b in grp}) > len({b['cam'] for b in best}): best = grp
        if n in REJECTED: continue
        if len({b['cam'] for b in best}) >= 2: L = best
        elif n in VERIFIED_SINGLE: L = [a for a in L if a['cam'] == VERIFIED_SINGLE[n][0]]
        else: continue
        if not L: continue
        z = np.concatenate([a['z'] for a in L]); px = sum(a['px'] for a in L)
        z0, z1 = np.percentile(z, 5), np.percentile(z, 95)
        rgb = np.median(np.array([a['rgb'] for a in L]), axis=0)
        # vertical si l'etendue en hauteur domine l'etendue au sol des pixels (lignes verticales aux aretes)
        xy = np.concatenate([a['xy'] for a in L])
        horiz = float(np.percentile(np.linalg.norm(xy - np.median(xy, 0), axis=1), 90))
        pat = 'vertical' if (z1 - z0) > 1.5 * max(horiz, 1.0) else 'band'
        out[n] = {'rgb': [round(float(v), 3) for v in rgb], 'z0': round(float(z0), 1), 'z1': round(float(z1), 1),
                  'top': round(float(tops[n]), 1), 'pattern': pat, 'n_px': int(px),
                  'frac': round(max(a['frac'] for a in L), 4), 'cams': [a['cam'] for a in sorted(L, key=lambda a: -a['px'])[:5]],
                  '_src': 'MEASURED night frames (night_lights.py)'}
    for n, (twin, why) in TWINS.items():
        if n in out and twin in out:
            t = out[twin]; out[n]['z0'] = round(out[n]['top'] - (t['top'] - t['z0']), 1); out[n]['z1'] = round(out[n]['top'] - (t['top'] - t['z1']), 1)
            out[n]['pattern'] = t['pattern']; out[n]['_band_from'] = twin + ' (' + why + ')'
    return out


if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    debug = sys.argv[sys.argv.index('--debug') + 1] if '--debug' in sys.argv else None
    out = run(only, debug)
    for n, v in sorted(out.items(), key=lambda t: -t[1]['n_px']):
        print('%-38s rgb %s  z %5.1f-%5.1f / top %5.1f  %-8s %5d px  frac %.3f  (%s)' % (n[:38], v['rgb'], v['z0'], v['z1'], v['top'], v['pattern'], v['n_px'], v['frac'], ', '.join(v['cams'][:2])))
    print('%d batiments avec eclairage mesure' % len(out))
    if '--apply' in sys.argv:
        shutil.copy(MESHES, MESHES + '.bak_nightlights')
        M = json.load(open(MESHES))
        for n in M:
            M[n].pop('night_light', None)
        for n, v in out.items():
            if n in M: M[n]['night_light'] = v
        json.dump(M, open(MESHES, 'w'), indent=1, ensure_ascii=True); print('applique')
