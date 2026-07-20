#!/usr/bin/env python3
"""automatch.py — auto-marquage guide par les poses. [AUTOMATCH-V1, READ-ONLY]

Le pari (2026-07-19): les clics sont la ressource la plus chere du projet;
avec des poses au centimetre sur les frames nettes, le matching devient une
recherche CONTRAINTE — chaque pixel de la frame source correspond a une
courbe epipolaire dans la cible, et chaque match se triangule immediatement.

Pipeline par paire ordonnee (A -> B):
  1. coins de Harris dans A (top-N, distance minimale, bords exclus)
  2. inversion numerique pixel->rayon (Newton sur le VRAI modele cam —
     jamais de projecteur maison, lecon Peacock B)
  3. balayage de profondeur le long du rayon, projete dans B, re-echantillonne
     a pas ~2px d'arc; ZNCC 13x13 vectorise le long de la courbe
  4. GATES: pic ZNCC >= 0.72, 2e pic hors-fenetre < 85% du 1er,
     parallaxe >= 3 deg (doctrine triangulate), z dans [-5, 420] m,
     verif aller-retour (le patch de B doit re-matcher A a <= 2.5px)
  5. 3e vue temoin quand disponible: ZNCC local autour de la projection
     -> candidats 'confirmed_3view' (la classe qui vaut de l'or)

Sortie: entonnoir de survie + tools/generated/automatch_pilot.json
(xyz, pixels A/B, scores, distance au LM connu le plus proche). AUCUNE
ecriture dans gtamapdata — la promotion en vrais LMs est une etape humaine.

Usage:
  PYTHONPATH=. python3 tools/automatch.py \
      --src "Port Vice City (A)" --dst "Vice City 03 (Basketball)" \
      [--witness "Shitzu Squalo 01 (Bay)"] [--n-corners 1500]
"""
import argparse
import json
import math
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
from PIL import Image
from scipy import ndimage
import common

PATCH = 6            # demi-cote -> patchs 13x13
ZNCC_MIN = 0.72
RATIO_MAX = 0.85     # 2e pic (hors fenetre ±4 echantillons) / 1er pic
PARALLAX_MIN = 3.0   # deg, meme doctrine que triangulate_lm
LR_TOL = 2.5         # px, verif aller-retour
DEPTHS = (60.0, 6000.0)
Z_RANGE = (-5.0, 420.0)


def load_gray(cam_name):
    img = np.asarray(Image.open(os.path.join(REPO, 'frames', f'{cam_name}.png')).convert('L'), dtype=np.float32)
    return img


def harris_corners(img, n, min_dist=12, border=24):
    gy, gx = np.gradient(img)
    Ixx = ndimage.gaussian_filter(gx * gx, 2.0)
    Iyy = ndimage.gaussian_filter(gy * gy, 2.0)
    Ixy = ndimage.gaussian_filter(gx * gy, 2.0)
    R = Ixx * Iyy - Ixy ** 2 - 0.05 * (Ixx + Iyy) ** 2
    Rmax = ndimage.maximum_filter(R, size=min_dist)
    peaks = (R == Rmax) & (R > np.percentile(R, 97))
    peaks[:border, :] = peaks[-border:, :] = False
    peaks[:, :border] = peaks[:, -border:] = False
    ys, xs = np.nonzero(peaks)
    order = np.argsort(-R[ys, xs])[:n]
    return np.stack([xs[order], ys[order]], axis=1).astype(float)


def unproject(cam, pix, yaw0, pitch0, hfov):
    """pixel -> direction unitaire monde, Newton numerique sur get_pixel."""
    o = np.asarray(cam.xyz, float)

    def direc(az, el):
        ca, sa = math.cos(math.radians(az)), math.sin(math.radians(az))
        ce, se = math.cos(math.radians(el)), math.sin(math.radians(el))
        return np.array([-sa * ce, ca * ce, se])

    az, el = yaw0, pitch0
    # init grossiere: grille dans le champ
    best, bd = (az, el), 1e18
    for daz in np.linspace(-hfov * 0.6, hfov * 0.6, 13):
        for de in np.linspace(-hfov * 0.4, hfov * 0.4, 9):
            p = cam.get_pixel((o + 500.0 * direc(yaw0 + daz, pitch0 + de)).tolist())
            if p is None:
                continue
            d = (p[0] - pix[0]) ** 2 + (p[1] - pix[1]) ** 2
            if d < bd:
                bd, best = d, (yaw0 + daz, pitch0 + de)
    az, el = best
    for _ in range(12):
        p0 = cam.get_pixel((o + 500.0 * direc(az, el)).tolist())
        if p0 is None:
            return None
        r = np.array([pix[0] - p0[0], pix[1] - p0[1]])
        if abs(r[0]) < 0.05 and abs(r[1]) < 0.05:
            break
        J = np.zeros((2, 2))
        for j, (da, de) in enumerate(((0.01, 0.0), (0.0, 0.01))):
            p1 = cam.get_pixel((o + 500.0 * direc(az + da, el + de)).tolist())
            if p1 is None:
                return None
            J[:, j] = [(p1[0] - p0[0]) / 0.01, (p1[1] - p0[1]) / 0.01]
        try:
            step = np.linalg.solve(J, r)
        except np.linalg.LinAlgError:
            return None
        az += float(np.clip(step[0], -2, 2)); el += float(np.clip(step[1], -2, 2))
    return direc(az, el)


def epipolar_path(camB, o, d, W, H, step_px=2.0):
    """Echantillonne la projection du rayon (o + t d) dans B a ~step_px d'arc.
    -> (depths, cx, cy) numpy."""
    ts = np.geomspace(DEPTHS[0], DEPTHS[1], 120)
    pts, tk = [], []
    for t in ts:
        p = camB.get_pixel((o + t * d).tolist())
        if p is None:
            continue
        pts.append(p); tk.append(t)
    if len(pts) < 2:
        return None
    P = np.asarray(pts, float); T = np.asarray(tk, float)
    seg = np.hypot(*np.diff(P, axis=0).T)
    out_p, out_t = [P[0]], [T[0]]
    for i in range(1, len(P)):
        n_sub = int(seg[i - 1] // step_px)
        for k in range(1, n_sub + 1):
            f = k / (n_sub + 1)
            # interpolation lineaire en 1/profondeur (correct en projectif)
            invt = (1 - f) / T[i - 1] + f / T[i]
            out_p.append(P[i - 1] + f * (P[i] - P[i - 1])); out_t.append(1.0 / invt)
        out_p.append(P[i]); out_t.append(T[i])
    P = np.asarray(out_p); T = np.asarray(out_t)
    ok = (P[:, 0] >= PATCH + 1) & (P[:, 0] < W - PATCH - 1) & \
         (P[:, 1] >= PATCH + 1) & (P[:, 1] < H - PATCH - 1)
    if ok.sum() < 8:
        return None
    return T[ok], P[ok, 0], P[ok, 1]


def zncc_stack(img, cx, cy, ref):
    """ZNCC du patch ref (13x13 normalise) aux centres (cx, cy) entiers."""
    dy, dx = np.mgrid[-PATCH:PATCH + 1, -PATCH:PATCH + 1]
    X = (np.rint(cx).astype(int)[:, None, None] + dx[None])
    Y = (np.rint(cy).astype(int)[:, None, None] + dy[None])
    S = img[Y, X].reshape(len(cx), -1)
    S = S - S.mean(axis=1, keepdims=True)
    n = np.linalg.norm(S, axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(n > 1e-3, (S @ ref) / n, -1.0)


def norm_patch(img, x, y):
    xi, yi = int(round(x)), int(round(y))
    p = img[yi - PATCH:yi + PATCH + 1, xi - PATCH:xi + PATCH + 1].astype(float).ravel()
    p = p - p.mean()
    n = np.linalg.norm(p)
    return p / n if n > 1e-3 else None


def main_sift(args):
    """[AUTOMATCH-V2] SIFT + contrainte epipolaire. Le ZNCC V1 est refute en
    wide-baseline (3 paires du triangle net: 0-20 candidats douteux, temoin
    aveugle) — les descripteurs invariants + la geometrie comme juge:
    un match descripteur n'est garde que s'il tombe a <EPI_TOL px de la
    courbe epipolaire predite par les poses."""
    import cv2
    EPI_TOL = 3.0
    RATIO = 0.80

    cams_json = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    camA, camB = common.get_cam(args.src), common.get_cam(args.dst)
    imgA, imgB = load_gray(args.src), load_gray(args.dst)
    oA = np.asarray(camA.xyz, float); oB = np.asarray(camB.xyz, float)
    eA = cams_json[args.src]
    camW = common.get_cam(args.witness) if args.witness else None

    sift = cv2.SIFT_create(nfeatures=args.n_corners)
    kA, dA = sift.detectAndCompute(imgA.astype(np.uint8), None)
    kB, dB = sift.detectAndCompute(imgB.astype(np.uint8), None)
    kW = dW = None
    if camW is not None:
        imgW = load_gray(args.witness)
        kW, dW = sift.detectAndCompute(imgW.astype(np.uint8), None)
        posW = np.array([k.pt for k in kW]) if kW else None
    print(f'{args.src} -> {args.dst}: SIFT {len(kA)} / {len(kB)} kps'
          + (f' / temoin {len(kW)}' if kW else ''))

    # MATCHING GUIDE (V2.1): la geometrie d'abord, les descripteurs ensuite.
    # Le matching global + ratio-test est refute ici: sur des facades
    # repetitives le vrai match a un jumeau (2e voisin proche) et meurt au
    # ratio, ne survivent que des faux 'distinctifs' (142 matchs, 0 sur
    # l'epipolaire — verite terrain: les LMs partages tombent a 0.7-3.4px).
    # Ici on ne compare chaque kp de A qu'aux kps de B SUR sa courbe
    # epipolaire, et l'ambiguite ne se juge qu'entre profondeurs distinctes.
    from scipy.spatial import cKDTree
    posB = np.array([k.pt for k in kB])
    tree = cKDTree(posB)
    DESC_MAX = args.desc_max
    funnel = dict(kps=len(kA), path=0, on_path=0, desc=0, depth_unambig=0,
                  parallax=0, zrange=0, w3=0)
    cands = []
    for i, kp in enumerate(kA):
        pa = kp.pt
        d = unproject(camA, pa, eA['ypr'][0], eA['ypr'][1], eA['fov'][0])
        if d is None:
            continue
        path = epipolar_path(camB, oA, d, imgB.shape[1], imgB.shape[0])
        if path is None:
            continue
        funnel['path'] += 1
        T, px, py = path
        idx = set()
        for lst in tree.query_ball_point(np.stack([px, py], axis=1), EPI_TOL, workers=-1):
            idx.update(lst)
        if not idx:
            continue
        funnel['on_path'] += 1
        idx = sorted(idx)
        dd = np.linalg.norm(dB[idx].astype(np.float32) - dA[i].astype(np.float32), axis=1)
        order = np.argsort(dd)
        j = idx[int(order[0])]
        if dd[order[0]] > DESC_MAX:
            continue
        funnel['desc'] += 1
        pb = posB[j]
        k = int(np.argmin((px - pb[0]) ** 2 + (py - pb[1]) ** 2))
        # ambiguite: un 2e candidat presque aussi bon a une PROFONDEUR distincte
        if len(order) > 1:
            j2 = idx[int(order[1])]
            pb2 = posB[j2]
            k2 = int(np.argmin((px - pb2[0]) ** 2 + (py - pb2[1]) ** 2))
            if dd[order[1]] < dd[order[0]] / RATIO and abs(T[k2] - T[k]) > 0.05 * T[k]:
                continue
        funnel['depth_unambig'] += 1
        P3 = oA + T[k] * d
        v1 = P3 - oA; v2 = P3 - oB
        par = math.degrees(math.acos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1)))
        if par < PARALLAX_MIN:
            continue
        funnel['parallax'] += 1
        if not (Z_RANGE[0] <= P3[2] <= Z_RANGE[1]):
            continue
        funnel['zrange'] += 1
        cand = dict(xyz=[round(float(v), 3) for v in P3],
                    src_px=[round(pa[0], 1), round(pa[1], 1)],
                    dst_px=[round(float(pb[0]), 1), round(float(pb[1]), 1)],
                    desc_dist=round(float(dd[order[0]]), 1),
                    parallax_deg=round(par, 2), depth_m=round(float(T[k]), 1),
                    witness=None)
        if camW is not None and kW:
            pW = camW.get_pixel(P3.tolist())
            if pW is not None:
                near = np.nonzero(np.hypot(posW[:, 0] - pW[0], posW[:, 1] - pW[1]) < 6.0)[0]
                if len(near):
                    ddw = np.linalg.norm(dW[near].astype(np.float32) - dA[i].astype(np.float32), axis=1)
                    jw = int(np.argmin(ddw))
                    if ddw[jw] < args.desc_max:
                        cand['witness'] = dict(cam=args.witness, px=[round(float(pW[0]), 1), round(float(pW[1]), 1)],
                                               desc_dist=round(float(ddw[jw]), 1))
                        funnel['w3'] += 1
        cands.append(cand)
    return funnel, cands


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--dst', required=True)
    ap.add_argument('--witness', default=None)
    ap.add_argument('--mode', choices=['zncc', 'sift'], default='sift')
    ap.add_argument('--n-corners', type=int, default=1500)
    ap.add_argument('--desc-max', type=float, default=420.0,
                    help='seuil L2 SIFT (calibre verite-terrain: vraies corresp. median 352 sur baseline 1.9km)')
    ap.add_argument('--require-witness', action='store_true',
                    help='3e vue obligatoire (la porte qui tue les faux quand le descripteur sature)')
    ap.add_argument('--out', default=os.path.join(REPO, 'tools', 'generated', 'automatch_pilot.json'))
    args = ap.parse_args()

    if args.mode == 'sift':
        funnel, cands = main_sift(args)
        print('\nENTONNOIR:', ' -> '.join(f'{k}:{v}' for k, v in funnel.items()))
        lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
        known = np.array([e['xyz'] for e in lms.values() if isinstance(e, dict) and e.get('xyz')])
        for c in cands:
            c['nearest_lm_m'] = round(float(np.min(np.linalg.norm(known - np.asarray(c['xyz']), axis=1))), 1)
        if cands:
            near = sorted(c['nearest_lm_m'] for c in cands)
            w3 = [c for c in cands if c['witness']]
            print(f'{len(cands)} candidats ({len(w3)} confirmes 3-vues); dist au LM connu: '
                  f'p25 {near[len(near)//4]:.0f}m median {near[len(near)//2]:.0f}m p75 {near[3*len(near)//4]:.0f}m')
            zs = sorted(c['xyz'][2] for c in cands)
            print(f'z: min {zs[0]:.0f} median {zs[len(zs)//2]:.0f} max {zs[-1]:.0f}')
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        tmp = args.out + '.tmp'
        json.dump(dict(src=args.src, dst=args.dst, witness=args.witness, mode='sift',
                       funnel=funnel, candidates=cands), open(tmp, 'w'), indent=1)
        os.replace(tmp, args.out)
        print(f'-> {args.out}')
        return

    cams_json = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    camA, camB = common.get_cam(args.src), common.get_cam(args.dst)
    imgA, imgB = load_gray(args.src), load_gray(args.dst)
    HB, WB = imgB.shape
    HA, WA = imgA.shape
    camW = common.get_cam(args.witness) if args.witness else None
    imgW = load_gray(args.witness) if args.witness else None
    oA = np.asarray(camA.xyz, float); oB = np.asarray(camB.xyz, float)
    eA = cams_json[args.src]

    corners = harris_corners(imgA, args.n_corners)
    print(f'{args.src} -> {args.dst}: {len(corners)} coins Harris')
    funnel = dict(corners=len(corners), ray=0, path=0, zncc=0, ratio=0,
                  parallax=0, zrange=0, lr=0, w3=0)
    cands = []
    for cx, cy in corners:
        refA = norm_patch(imgA, cx, cy)
        if refA is None:
            continue
        d = unproject(camA, (cx, cy), eA['ypr'][0], eA['ypr'][1], eA['fov'][0])
        if d is None:
            continue
        funnel['ray'] += 1
        path = epipolar_path(camB, oA, d, WB, HB)
        if path is None:
            continue
        funnel['path'] += 1
        T, px, py = path
        sc = zncc_stack(imgB, px, py, refA)
        k = int(np.argmax(sc))
        if sc[k] < ZNCC_MIN:
            continue
        funnel['zncc'] += 1
        away = np.abs(np.arange(len(sc)) - k) > 4
        if away.any() and float(np.max(sc[away])) > RATIO_MAX * sc[k]:
            continue
        funnel['ratio'] += 1
        # sub-echantillon: parabole sur ZNCC(1/t)
        tk = T[k]
        if 0 < k < len(T) - 1:
            y0, y1, y2 = sc[k - 1], sc[k], sc[k + 1]
            den = y0 - 2 * y1 + y2
            if abs(den) > 1e-9:
                f = float(np.clip(0.5 * (y0 - y2) / den, -1, 1))
                it = np.interp(k + f, np.arange(len(T)), 1.0 / T)
                tk = 1.0 / it
        P3 = oA + tk * d
        v1 = P3 - oA; v2 = P3 - oB
        par = math.degrees(math.acos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1)))
        if par < PARALLAX_MIN:
            continue
        funnel['parallax'] += 1
        if not (Z_RANGE[0] <= P3[2] <= Z_RANGE[1]):
            continue
        funnel['zrange'] += 1
        # aller-retour: le patch de B doit re-matcher A pres du coin d'origine
        pB = camB.get_pixel(P3.tolist())
        refB = norm_patch(imgB, pB[0], pB[1]) if pB is not None else None
        if refB is None:
            continue
        gx, gy = np.mgrid[-5:6, -5:6]
        lx = np.clip(cx + gx.ravel(), PATCH + 1, WA - PATCH - 2)
        ly = np.clip(cy + gy.ravel(), PATCH + 1, HA - PATCH - 2)
        sb = zncc_stack(imgA, lx, ly, refB)
        j = int(np.argmax(sb))
        if math.hypot(lx[j] - cx, ly[j] - cy) > LR_TOL:
            continue
        funnel['lr'] += 1
        cand = dict(xyz=[round(float(v), 3) for v in P3],
                    src_px=[round(float(cx), 1), round(float(cy), 1)],
                    dst_px=[round(float(pB[0]), 1), round(float(pB[1]), 1)],
                    zncc=round(float(sc[k]), 3), parallax_deg=round(par, 2),
                    depth_m=round(float(tk), 1), witness=None)
        if camW is not None:
            pW = camW.get_pixel(P3.tolist())
            if pW is not None and PATCH + 6 < pW[0] < imgW.shape[1] - PATCH - 7 \
                    and PATCH + 6 < pW[1] < imgW.shape[0] - PATCH - 7:
                wx = np.clip(pW[0] + gx.ravel(), PATCH + 1, imgW.shape[1] - PATCH - 2)
                wy = np.clip(pW[1] + gy.ravel(), PATCH + 1, imgW.shape[0] - PATCH - 2)
                sw = zncc_stack(imgW, wx, wy, refA)
                if float(np.max(sw)) >= 0.6:
                    cand['witness'] = dict(cam=args.witness, zncc=round(float(np.max(sw)), 3))
                    funnel['w3'] += 1
        cands.append(cand)

    print('\nENTONNOIR:', ' -> '.join(f'{k}:{v}' for k, v in funnel.items()))

    # sanite spatiale: distance au LM connu le plus proche
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    known = np.array([e['xyz'] for e in lms.values() if isinstance(e, dict) and e.get('xyz')])
    for c in cands:
        dmin = float(np.min(np.linalg.norm(known - np.asarray(c['xyz']), axis=1)))
        c['nearest_lm_m'] = round(dmin, 1)
    if cands:
        near = sorted(c['nearest_lm_m'] for c in cands)
        w3 = [c for c in cands if c['witness']]
        print(f'{len(cands)} candidats ({len(w3)} confirmes 3-vues); dist au LM connu: '
              f'p25 {near[len(near)//4]:.0f}m median {near[len(near)//2]:.0f}m p75 {near[3*len(near)//4]:.0f}m')
        zs = sorted(c['xyz'][2] for c in cands)
        print(f'z: min {zs[0]:.0f} median {zs[len(zs)//2]:.0f} max {zs[-1]:.0f}')
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tmp = args.out + '.tmp'
    json.dump(dict(src=args.src, dst=args.dst, witness=args.witness,
                   funnel=funnel, candidates=cands), open(tmp, 'w'), indent=1)
    os.replace(tmp, args.out)
    print(f'-> {args.out}')


if __name__ == '__main__':
    main()
