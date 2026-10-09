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
EXCLUDE = {'Vice Beach (B)': 'titre "Rockstar Games presents" incruste sur les facades',
           'Shitzu Squalo 01 (Bay)': 'crepuscule (Kaseya et fenetres allumees) sous un ciel clair: ni jour ni nuit',
           'Skyline': 'coucher de soleil: ciel orange segmente comme facade',
           'Dominion Hotel': 'plan interieur rapproche: les faces lointaines recoivent le premier plan'}
DAY_MIN, NIGHT_MAX = 0.30, 0.24   # luminance des pixels de BATIMENT: jour >= 0.30 (et image >= 0.40); nuit <= 0.24 (et image <= 0.32)


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
    # [FACADE-TEX-V2 2026-10-07] cams: confiance 1.0 = audit fiable (>= 6 volumes, |shift| <= 1.5 px); 0.75 = audit etendu
    # (>= 3 volumes, |shift| <= 3 px corrige, |echelle| <= 4 px, rms <= 4 px); 0.6 = pose SOLVED/VERIFIED/LOCKED sans audit.
    # Le score de chaque vue est multiplie par la confiance: la meilleure cam fiable gagne quand elle existe.
    conf = {}
    for c, o in A.items():
        f_ = o.get('fit')
        if not f_ or c in EXCLUDE: continue
        if o['n_judged'] >= 6 and abs(f_['shift_px']) <= 1.5: conf[c] = 1.0
        elif o['n_judged'] >= 3 and abs(f_['shift_px']) <= 3.0 and abs(f_['scale_px_at_edge']) <= 4.0 and f_.get('rms_px', 9) <= 4.0: conf[c] = 0.75
    for c, v in C.items():
        if c not in conf and c not in EXCLUDE and v.get('constraint_class') != 'X_excluded' and str(v.get('pose_verified') or '').split(' ')[0] in ('SOLVED', 'VERIFIED', 'LOCKED'):
            conf[c] = 0.6
    # + residus des landmarks (snapshot RMS du healthcheck): >= 4 observations a <= 6' = pose fiable meme sans mesh visible
    try:
        RS = json.load(open(os.path.join(THIS, 'generated', 'rms_snapshot_ci.json')))['cams']
        for c, v in RS.items():
            if c in EXCLUDE or c.startswith('AI World') or v.get('n_obs', 0) < 4 or v.get('rms_arcmin') is None or v['rms_arcmin'] > 6: continue
            if (C.get(c) or {}).get('constraint_class') == 'X_excluded': continue
            conf[c] = max(conf.get(c, 0), 0.8 if v['rms_arcmin'] <= 3 else 0.65)
    except Exception as ex: print('snapshot RMS illisible:', ex)
    cams = [c for c in conf if os.path.exists(os.path.join(REPO, 'frames', c + '.png'))]
    tod = {}
    for c in cams:
        sp_ = os.path.join(SEG, c.replace('/', '_') + '_cls.npy')
        if not os.path.exists(sp_): tod[c] = None; continue
        Lm = np.asarray(Image.open(os.path.join(REPO, 'frames', c + '.png')).convert('L').resize((480, 270))).astype(float) / 255
        bm = np.isin(np.asarray(Image.fromarray(np.load(sp_).astype(np.uint8)).resize((480, 270), Image.NEAREST)), BUILD_CLS)
        lum = float(Lm[bm].mean()) if bm.sum() > 500 else float(Lm.mean())
        hot = float((Lm[bm] > 0.92).mean()) if bm.sum() > 500 else 0.0          # points lumineux satures sur les facades = lumieres
        la = float(Lm.mean())
        tod[c] = 'day' if (lum >= DAY_MIN and la >= 0.40) else ('night' if (lum <= NIGHT_MAX and la <= 0.32) else None)
    cams = [c for c in cams if tod[c]]
    print('cams fiables:', {c: tod[c] for c in cams})
    best = {}                                                   # (batiment, i_face, jour/nuit) -> (score, entry, rgba)
    for cam in cams:
        fp = os.path.join(REPO, 'frames', cam + '.png'); sp = os.path.join(SEG, cam.replace('/', '_') + '_cls.npy')
        if not (os.path.exists(fp) and os.path.exists(sp)): continue
        cm = common.get_cam(cam); B = basis(cm); o, f, r, u, fpx, W, H = B
        img = np.asarray(Image.open(fp).convert('RGB')); fh, fw = img.shape[:2]; kf = fw / W     # pixels frame / pixels camera
        cls = np.load(sp); kc = cls.shape[1] / fw
        sh = ((A.get(cam) or {}).get('fit') or {}).get('shift_px', 0.0) * fw / 1280.0   # decalage horizontal mesure (px frame)
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
                if wpx < 70: continue
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
                score = vf * wpx * cosv * conf[cam]
                key = (n, fi, tod[cam])
                if ns < 16 or nz < 16 or z1 - z0 < 6.0: continue                          # tranches trop fines: inutilisables
                mx = P[:, 0].reshape(nz, ns).astype(np.float32); my = P[:, 1].reshape(nz, ns).astype(np.float32)
                rgb = cv2.remap(img, mx, my, cv2.INTER_LINEAR)
                al = (valid.reshape(nz, ns) * 255).astype(np.uint8)
                al = cv2.erode(al, np.ones((3, 3), np.uint8))                                  # pas de franges aux bords
                g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32); m_ = al > 0
                if m_.sum() < 64: continue
                sharp = float(cv2.Laplacian(g, cv2.CV_32F)[m_].var()); contrast = float(g[m_].std())
                if tod[cam] == 'day' and (sharp < 25 or contrast < 10): continue                # flou / brume: la couleur de base vaut mieux
                if tod[cam] == 'day':                                                         # [FACADE-TEX-V3] coherence verticale: un batiment NON
                    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)               # modelise devant la tour peint le bas de la texture
                    rows = np.where(m_.any(1))[0]                                               # d'une autre couleur -> bandes masquees (alpha 0)
                    top = rows[: max(4, len(rows) * 3 // 10)]
                    ref = np.median(lab[top][m_[top]], 0) if m_[top].sum() > 30 else None
                    if ref is not None:
                        band = max(4, nz // 24)
                        for y0 in range(0, nz, band):                                       # du haut vers le bas: a la 1re bande qui diverge,
                            mm = m_[y0:y0 + band]                                           # tout le dessous est masque (ce qui est devant est en bas)
                            if mm.sum() < 10: continue
                            if float(np.linalg.norm(np.median(lab[y0:y0 + band][mm], 0) - ref)) > 30: al[y0:] = 0; break
                        m_ = al > 0
                        if m_.mean() < 0.3: continue
                best.setdefault(key, []).append((score, {'building': n, 'a': [round(float(a[0]), 2), round(float(a[1]), 2)], 'b': [round(float(b[0]), 2), round(float(b[1]), 2)],
                                     'z0': round(z0, 2), 'z1': round(z1, 2), 'n': [round(float(nv[0]), 4), round(float(nv[1]), 4)],
                                     'cam': cam, 'conf': conf[cam], 'tod': tod[cam], 'valid': round(vf, 2), 'px': [ns, nz], 'wpx': round(wpx), 'sharp': round(sharp)}, np.dstack([rgb, al])))
        print('%-45s faces retenues jusqu ici: %d' % (cam[:45], len(best)))
    for fn in os.listdir(OUTD):
        if fn.startswith('_fac_') and fn.endswith('.png'): os.remove(os.path.join(OUTD, fn))
    out = []
    # [FACADE-TEX-V2] decision par face: une vue d'une cam de confiance >= 0.75 est acceptee seule; sinon il faut qu'une vue d'une
    # AUTRE scene voie la meme facade de la meme couleur (dE Lab moyen <= 26; la correlation fine echoue a cause des petits decalages)
    from mesh_click_list import scene as scene_of
    def thumb(rgba):                                          # couleur Lab moyenne des texels valides
        m = rgba[..., 3] > 0
        lab = cv2.cvtColor(rgba[..., :3], cv2.COLOR_RGB2LAB).astype(np.float32)
        return lab[m].mean(0) if m.sum() > 50 else None
    def ncc(A_, B_):                                          # 'similarite' = 1 - dE/40 (dE Lab 8 bits): >= 0.35 <=> dE <= 26
        if A_ is None or B_ is None: return None
        return 1.0 - float(np.linalg.norm(A_ - B_)) / 40.0
    # garde-fou couleur (jour): un batiment NON modelise devant la facade donne une texture d'une autre couleur que la facade
    # mesuree (facade_color des meshes, facades_colors.py) ou IRL -> rejet si dE Lab (8 bits OpenCV) > 60, seulement pour les cams
    # de confiance < 1 (les cams fiables de l'audit sont gardees)
    MJ = json.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')))
    def ref_lab(n):
        m = MJ.get(n) or MJ.get(n.split(' (')[0]) or {}
        c = (m.get('facade_color') or {}).get('rgb') or (m.get('facade_irl') or {}).get('rgb')
        if not c: return None
        return cv2.cvtColor(np.uint8([[np.clip(np.array(c) * 255, 0, 255)]]), cv2.COLOR_RGB2LAB)[0, 0].astype(np.float32)
    n_col = 0
    for key in list(best):
        if key[2] != 'day': continue
        rl = ref_lab(key[0])
        if rl is None: continue
        keep = [t for t in best[key] if t[1]['conf'] >= 1.0 or thumb(t[2]) is None or float(np.linalg.norm(thumb(t[2]) - rl)) <= 60]
        n_col += len(best[key]) - len(keep)
        if keep: best[key] = keep
        else: del best[key]
    print('vues rejetees par le garde-fou couleur:', n_col)
    chosen = {}; n_conf = n_solo = n_rej = 0
    for key, lst in best.items():
        lst.sort(key=lambda t: -t[0]); th = [thumb(t[2]) for t in lst]; pick = None
        for i, (sc, e, rgba) in enumerate(lst):
            ok = [ncc(th[i], th[j]) for j in range(len(lst)) if j != i and scene_of(lst[j][1]['cam']) != scene_of(e['cam'])]
            ok = [v for v in ok if v is not None]
            if ok and max(ok) >= 0.35: e['confirmed'] = round(max(ok), 2); pick = (sc, e, rgba); n_conf += 1; break
            if e['conf'] >= 0.75 and pick is None: pick = (sc, e, rgba)
        if pick is None: n_rej += 1; continue
        if 'confirmed' not in pick[1]: n_solo += 1
        chosen[key] = pick
    print('faces: %d confirmees par une 2e scene, %d acceptees seules (cam fiable), %d rejetees (cam moins sure non confirmee)' % (n_conf, n_solo, n_rej))
    for (n, fi, td), (sc, e, rgba) in sorted(chosen.items()):
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
