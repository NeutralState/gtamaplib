#!/usr/bin/env python3
"""mesh_pose_audit.py — audit des poses de TOUTES les cams contre les meshes mesures (skyline). [POSE-AUDIT-V1 2026-10-06]

Idee: 186 meshes mesures (135 volumes pleins via mesh_solids) sont devenus la meilleure verite independante. Pour chaque cam:
  1. les volumes sont projetes et peints du plus loin au plus proche (largeur de travail 1280 px) -> skyline rendue R(x)
     et proprietaire de chaque colonne (le volume qui forme le haut);
  2. skyline de la frame S(x) = bas de la composante de ciel (SegFormer ADE20K classe 2) reliee au haut de l'image
     (ou la plus grande), par colonne;
  3. par volume: colonnes ou il forme le haut de la skyline rendue. e = S - R: |e| <= 2 px bon, e > 2 px = le mesh
     deborde dans le ciel (erreur de pose ou de mesh), e < -2 px = masque par un objet non modelise (non jugeable);
     cout robuste min(|e|, 6) et recherche du decalage (dx, dy) qui le minimise -> direction de l'erreur.
Agregat par cam: volumes jugeables, volumes qui collent, volumes qui debordent, decalage horizontal coherent
(= erreur de cap, en degres). Un mesh qui deborde dans plusieurs cams bien posees = mesh suspect.
Sorties: tools/generated/pose_audit.json, tools/generated/pose_audit/<cam>.jpg (planches, derivees des frames, ignorees),
docs/pose_audit.md (tableau public, anglais).
Usage: python3 tools/mesh_pose_audit.py [--only "cam"] [--sheets]
"""
import json, os, sys, math, re
import numpy as np
import cv2
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import common
import mesh_solids as MS
from facade_colors import prisms, CAMS, SEG

WORK = 1280
TOL, CAP = 2.0, 6.0               # px a 1280 de large (1 px = 3 px en 4K)
SKY = 2
OUTJ = os.path.join(THIS, 'generated', 'pose_audit.json')
OUTD = os.path.join(THIS, 'generated', 'pose_audit')
OUTMD = os.path.join(REPO, 'docs', 'pose_audit.md')


def basis(cm):
    """comme facade_colors.basis mais fpx depuis cm.hfov (marche aussi pour les cams a fov vertical)."""
    W, H = cm.size
    f = np.array(cm.get_pixel_direction((W / 2, H / 2)), float); f /= np.linalg.norm(f)
    r = np.array(cm.get_pixel_direction((W / 2 + 100, H / 2)), float); r /= np.linalg.norm(r); r -= f * (r @ f); r /= np.linalg.norm(r)
    u = np.array(cm.get_pixel_direction((W / 2, H / 2 - 100)), float); u /= np.linalg.norm(u); u -= f * (u @ f) + r * (u @ r); u /= np.linalg.norm(u)
    return np.array(cm.xyz, float), f, r, u, (W / 2) / math.tan(math.radians(cm.hfov) / 2), W, H


def proj(B, X, s):
    o, f, r, u, fpx, W, H = B; D = X - o; z = D @ f
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.c_[(W / 2 + fpx * (D @ r) / z) * s, (H / 2 - fpx * (D @ u) / z) * s], z


def clip_near(F, B, zmin=2.0):
    """polygone 3D coupe au plan z_cam >= zmin (Sutherland-Hodgman) — garde les grands volumes proches."""
    o, f = B[0], B[1]; d = (F - o) @ f - zmin; out = []
    for i in range(len(F)):
        a, b, da, db = F[i], F[(i + 1) % len(F)], d[i], d[(i + 1) % len(F)]
        if da >= 0: out.append(a)
        if (da >= 0) != (db >= 0): out.append(a + (b - a) * (da / (da - db)))
    return np.array(out) if len(out) >= 3 else None


def sky_profile(cls):
    """S(x): ligne sous le ciel 'exterieur' (composante reliee au haut, sinon la plus grande); nan si pas de ciel."""
    sky = (cls == SKY).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(sky, 4)
    if n <= 1: return np.full(cls.shape[1], np.nan)
    top = set(np.unique(lab[0][lab[0] > 0]).tolist())
    keep = top if top else {int(np.argmax(stats[1:, cv2.CC_STAT_AREA])) + 1}
    m = np.isin(lab, list(keep))
    h = cls.shape[0]; rows = np.arange(h)[:, None]
    low = np.where(m, rows, -1).max(0).astype(float)
    low[low < 0] = np.nan
    return low + 1


def edge_match(fr, mine, sk, bl, i, SR=25, K=4):
    """arete du rendu en i (fr[i-1] libre, mine[i] au volume), le long d'une ligne: transition ciel -> non-ciel de la frame
    la plus proche, cherchee seulement dans l'etendue libre a gauche et dans le volume a droite (pas chez le voisin),
    avec >= K px de ciel avant et >= K px de BATI (segmentation: mur/batiment/maison/gratte-ciel) apres — une personne,
    une voiture ou un arbre au premier plan ne compte pas. Renvoie l'indice t (premier pixel non-ciel) ou None."""
    n = len(fr); kf = 0
    while kf < SR and i - 1 - kf >= 0 and fr[i - 1 - kf]: kf += 1
    km = 0
    while km < SR and i + km < n and mine[i + km]: km += 1
    if kf < 6 or km < 4: return None
    lo, hi = max(K, i - kf + 2), min(n - K, i + km - 1)
    best = None
    for t in range(lo, hi + 1):
        if sk[t - 1] and not sk[t] and sk[t - K:t].all() and bl[t:t + K].all():
            if best is None or abs(t - i) < abs(best - i): best = t
    return best


def audit_cam(cam, c, S, names, cents, faces):
    fp = os.path.join(REPO, 'frames', cam + '.png'); sp = os.path.join(SEG, cam.replace('/', '_') + '_cls.npy')
    if not (os.path.exists(fp) and os.path.exists(sp)): return None
    cm = common.get_cam(cam); B = basis(cm)
    W, H = B[5], B[6]; s = WORK / W; w, h = WORK, int(round(H * s)); o = B[0]
    near = [n for n in names if 30 < np.hypot(*(cents[n] - o[:2])) < 6000]
    if not near: return None
    order = sorted(near, key=lambda n: -np.hypot(*(cents[n] - o[:2])))
    owner = np.full((h, w), -1, np.int32); drawn = set()
    for idx, n in enumerate(order):
        for F in faces[n]:
            Fc = clip_near(F, B)
            if Fc is None: continue
            P, z = proj(B, Fc, s)
            if not np.isfinite(P).all() or np.abs(P).max() > 1e5: continue
            if P[:, 0].max() < 0 or P[:, 0].min() > w or P[:, 1].max() < 0 or P[:, 1].min() > h: continue
            cv2.fillPoly(owner, [np.round(P).astype(np.int32)], idx); drawn.add(idx)
    if not drawn: return {'cam': cam, 'meshes': {}, 'night': None}
    has = owner >= 0
    R = np.where(has.any(0), has.argmax(0), h).astype(float)
    lab = np.where(has.any(0), owner[np.clip(R.astype(int), 0, h - 1), np.arange(w)], -1)
    cls = np.asarray(Image.fromarray(np.load(sp).astype(np.uint8)).resize((w, h), Image.NEAREST))
    Sx = sky_profile(cls)
    img = np.asarray(Image.open(fp).convert('L').resize((w, h), Image.LANCZOS)).astype(np.float32)
    night = bool(img.mean() < 0.22 * 255)
    g = cv2.GaussianBlur(img, (3, 3), 0.8)
    gx = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)); gy = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))
    RF = 4

    def peak(v, a_, fallback):
        """position sous-pixel de la frontiere (pic parabolique du gradient); fallback = frontiere de la segmentation."""
        k = int(np.argmax(v))
        if v[k] <= 12: return fallback
        off = 0.0
        if 0 < k < len(v) - 1:
            den = v[k - 1] - 2 * v[k] + v[k + 1]
            if den < 0: off = 0.5 * (v[k - 1] - v[k + 1]) / den
        return a_ + k + off

    def refx(y, b0):                                         # frontiere seg b0 (entre pixels) -> arete reelle (+-4 px)
        a_, b_ = max(1, int(b0) - RF), min(w - 2, int(b0) + RF)
        return peak(gx[y, a_:b_ + 1], a_, b0)

    def refy(x, b0):
        a_, b_ = max(1, int(b0) - RF), min(h - 2, int(b0) + RF)
        return peak(gy[a_:b_ + 1, x], a_, b0)

    sky = cls == SKY
    bld = np.isin(cls, (0, 1, 25, 48))
    free = ~has                                              # ciel du rendu (aucun volume)
    res = {}
    SR = 25
    for idx in sorted(drawn):
        M = owner == idx
        if M.sum() < 60: continue
        ys, xs = np.nonzero(M)
        meas = {'L': [], 'R': [], 'T': []}
        # aretes exposees au ciel du rendu: gauche (voisin gauche libre), droite, haut
        for y, x in zip(ys, xs):
            if 0 < x < w - 1 and free[y, x - 1]:
                t = edge_match(free[y], M[y], sky[y], bld[y], x)
                if t is not None: meas['L'].append(refx(y, t - 0.5) - (x - 0.5))
            if 0 < x < w - 1 and free[y, x + 1]:
                t = edge_match(free[y][::-1], M[y][::-1], sky[y][::-1], bld[y][::-1], w - 1 - x)
                if t is not None: meas['R'].append(refx(y, w - 1 - t + 0.5) - (x + 0.5))
            if 0 < y < h - 1 and free[y - 1, x]:
                t = edge_match(free[:, x], M[:, x], sky[:, x], bld[:, x], y)
                if t is not None: meas['T'].append(refy(x, t - 0.5) - (y - 0.5))
        ex = {}
        for k, v in meas.items():
            if len(v) >= 6:
                v = np.array(v, float); md = float(np.median(v))
                ex[k] = {'n': int(len(v)), 'd': round(md, 2), 'mad': round(float(np.median(np.abs(v - md))), 2)}
        if not ex: continue
        cx = float(np.median(xs))
        res[order[idx]] = {'edges': ex, 'x': round(cx, 1), 'y_top': int(ys.min()), 'px': int(M.sum()),
                           'dist': round(float(np.hypot(*(cents[order[idx]] - o[:2]))), 0)}
    fpx_s = B[4] * s
    # par cam: d(x) = a + b (x - w/2) sur les aretes laterales -> a = decalage (cap), b = echelle (fov)
    pts = []
    for m in res.values():
        E = {k: m['edges'][k] for k in ('L', 'R') if k in m['edges'] and m['edges'][k]['mad'] <= 3}
        if len(E) == 2:                                       # centre (L+R)/2: insensible a une largeur de mesh fausse
            m['center_d'] = round((E['L']['d'] + E['R']['d']) / 2, 2); m['width_d'] = round(E['R']['d'] - E['L']['d'], 2)
            pts.append((m['x'], m['center_d'], min(E['L']['n'], E['R']['n']) * 2))
        elif len(E) == 1:
            pts.append((m['x'], list(E.values())[0]['d'], list(E.values())[0]['n'] * 0.3))
    fit = None
    if len(pts) >= 3:
        P = np.array(pts, float); A_ = np.c_[np.ones(len(P)), (P[:, 0] - w / 2) / (w / 2)]
        wt = np.sqrt(np.minimum(P[:, 2], 40))
        sol = np.linalg.lstsq(A_ * wt[:, None], P[:, 1] * wt, rcond=None)[0]
        rr = P[:, 1] - A_ @ sol
        fit = {'shift_px': round(float(sol[0]), 2), 'scale_px_at_edge': round(float(sol[1]), 2), 'n': len(P),
               'rms_px': round(float(np.sqrt(np.average(rr ** 2, weights=wt ** 2))), 2)}
    return {'cam': cam, 'night': night, 'fpx1280': round(fpx_s, 1), 'meshes': res, 'fit': fit,
            '_owner': owner, '_order': order, '_sky': sky, '_wh': (w, h)}


def verdict(m):
    """par mesh (pose): centre des aretes laterales (L+R)/2 si les deux sont mesurees (insensible a une largeur de mesh
    fausse), sinon l'arete seule. 'match' <= 2 px, 'off' > 4 px, 'weak' entre; 'occluded' sans arete laterale."""
    if 'center_d' in m: d = abs(m['center_d'])
    else:
        side = [m['edges'][k] for k in ('L', 'R') if k in m['edges'] and m['edges'][k]['mad'] <= 3]
        if not side: return 'occluded'
        d = min(abs(e['d']) for e in side)
    if d <= 2.0: return 'match'
    if d > 4.0: return 'off'
    return 'weak'


def sheet(cam, r):
    fp = os.path.join(REPO, 'frames', cam + '.png'); w, h = r['_wh']
    img = np.asarray(Image.open(fp).convert('RGB').resize((w, h))).copy()
    col = {'match': (0, 230, 0), 'off': (255, 40, 40), 'weak': (255, 200, 0), 'occluded': (150, 150, 150)}
    owner, order = r['_owner'], r['_order']
    for idx, n in enumerate(order):
        m = r['meshes'].get(n)
        if m is None: continue
        v = verdict(m); mask = (owner == idx).astype(np.uint8)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(img, cnts, -1, col[v], 2)
        ys, xs = np.nonzero(mask)
        if len(xs):
            p = (int(np.median(xs)) - 30, int(ys.min()) - 6)
            cv2.putText(img, n[:22], p, cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(img, n[:22], p, cv2.FONT_HERSHEY_SIMPLEX, 0.4, col[v], 1, cv2.LINE_AA)
    sky = r['_sky']; e = cv2.morphologyEx(sky.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    img[e] = (0, 200, 255)
    os.makedirs(OUTD, exist_ok=True)
    Image.fromarray(img).save(os.path.join(OUTD, cam.replace('/', '_') + '.jpg'), quality=85)


def main():
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    S = MS.build(); C = json.load(open(CAMS))
    names = [n for n, so in S.items() if so['layers']]
    cents = {n: np.mean([q for L in S[n]['layers'] for p in L['polys'] for q in p['outer']], axis=0) for n in names}
    faces = {n: prisms(S[n]) for n in names}
    out = {}
    for cam, c in C.items():
        if only and cam != only: continue
        if c.get('constraint_class') == 'X_excluded': continue
        try:
            r = audit_cam(cam, c, S, names, cents, faces)
        except Exception as ex:
            print('!', cam, ex); continue
        if r is None: continue
        if '--sheets' in sys.argv and r['meshes']: sheet(cam, r)
        ms = r['meshes']; v = {n: verdict(m) for n, m in ms.items()}
        jud = [n for n in ms if v[n] != 'occluded']; fit = r.get('fit')
        out[cam] = {'night': r['night'], 'fpx1280': r.get('fpx1280'), 'pose_verified': c.get('pose_verified'),
                    'n_judged': len(jud), 'n_match': sum(v[n] == 'match' for n in jud), 'n_off': sum(v[n] == 'off' for n in jud),
                    'n_weak': sum(v[n] == 'weak' for n in jud), 'fit': fit,
                    'deg_per_px': round(math.degrees(math.atan(1 / r['fpx1280'])), 4) if r.get('fpx1280') else None,
                    'yaw_hint_deg': round(math.degrees(math.atan(fit['shift_px'] / r['fpx1280'])), 2) if fit else None,
                    'meshes': {n: dict(ms[n], verdict=v[n]) for n in ms}}
        o = out[cam]
        print('%-55s judged %2d  match %2d  off %2d  weak %2d  fit %s' % (cam[:55], o['n_judged'], o['n_match'], o['n_off'], o['n_weak'], fit))
    if only: return
    json.dump(out, open(OUTJ, 'w'), indent=1, ensure_ascii=True)
    # mesh suspects: debordent dans >= 2 cams ou ils sont jugeables
    mstat = {}
    for cam, o in out.items():
        for n, m in o['meshes'].items():
            if m['verdict'] == 'occluded': continue
            mstat.setdefault(n, []).append((cam, m['verdict'], m.get('width_d')))
    L = ['# Pose audit against measured meshes', '',
         'Generated by `tools/mesh_pose_audit.py` (POSE-AUDIT-V1). Every measured building volume is projected into every camera;',
         'its left/right silhouette edges against the sky are compared with the sky boundary of the frame (SegFormer), row by row.',
         'Per building: **match** (both edges within 2 px at 1280 px width), **off** (an edge more than 4 px away), **weak** (in between),',
         'or not judged (edges hidden). Per camera, edge errors are fitted as shift + scale across the image (shift = heading, scale = fov). Automatic: every verdict must be eye-checked on the contact sheet before acting.', '',
         '| camera | judged | match | off | weak | edge shift px | edge scale px | rms px | yaw hint (deg) | status |', '|---|---|---|---|---|---|---|---|---|---|']
    for cam, o in sorted(out.items(), key=lambda t: (-t[1]['n_judged'], t[0])):
        if not o['n_judged']: continue
        st = (o['pose_verified'] or '').split(' ')[0]; f = o['fit'] or {}
        L.append('| %s | %d | %d | %d | %d | %s | %s | %s | %s | %s |' % (cam, o['n_judged'], o['n_match'], o['n_off'], o['n_weak'], f.get('shift_px', ''), f.get('scale_px_at_edge', ''), f.get('rms_px', ''),
                                                          o['yaw_hint_deg'] if o['yaw_hint_deg'] is not None else '', st + (' (night)' if o['night'] else '')))
    L += ['', '## Buildings off in several cameras (mesh suspects)', '', '| building | cams judged | off | match |', '|---|---|---|---|']
    for n, lst in sorted(mstat.items(), key=lambda t: -sum(v == 'off' for _, v, _w in t[1])):
        ni = sum(v == 'off' for _, v, _w in lst)
        if ni >= 2: L.append('| %s | %d | %d | %d |' % (n, len(lst), ni, sum(v == 'match' for _, v, _w in lst)))
    L += ['', '## Buildings whose width disagrees in several cameras (footprint/shape suspects)', '',
          'Width error = right edge error - left edge error (px at 1280, positive = the game building looks wider than the mesh).', '',
          '| building | cams with both edges | median width error px | cams |', '|---|---|---|---|']
    for n, lst in sorted(mstat.items(), key=lambda t: -abs(np.median([w_ for _, _, w_ in t[1] if w_ is not None] or [0]))):
        ws = [(c_, w_) for c_, _, w_ in lst if w_ is not None]
        if len(ws) >= 2 and abs(np.median([w_ for _, w_ in ws])) > 3:
            L.append('| %s | %d | %.1f | %s |' % (n, len(ws), float(np.median([w_ for _, w_ in ws])), '; '.join('%s (%+.1f)' % (c_, w_) for c_, w_ in ws[:4])))
    open(OUTMD, 'w').write('\n'.join(L) + '\n')
    print('%d cams auditees -> %s, %s' % (len(out), OUTJ, OUTMD))


if __name__ == '__main__':
    main()
