#!/usr/bin/env python3
"""plane_sweep.py — de la vraie profondeur MESUREE, pas devinee. [PSWEEP-V1]

Le reproche qui declenche l'outil (Alexandre, 2026-07-31): "on tourne en rond
[...] on dirait t'as aucune perspective et tu vois tout juste en 2D".

Il a raison, et c'est structurel. Tout ce qu'on a fait sur le relief etait
2D: une silhouette extraite d'une frame, un contour lu sur la carte, une
polyligne de crete. Dans les trois cas la PROFONDEUR n'etait jamais mesuree
— elle etait posee apres coup comme une hypothese (un plan ajuste, un
rideau vertical, une distance declaree). D'ou des modeles qui reprojettent
bien sur leur propre frame (c'est tautologique) et qui ne tiennent pas
ailleurs.

Or nous avons ce qu'il faut pour mesurer: des cameras POSEES et CALIBREES
qui voient le meme massif. C'est exactement l'entree d'un stereo multi-vues.

METHODE (plane sweep, la methode classique du domaine):
  1. une camera REFERENCE et une camera CIBLE regardant le meme massif
  2. on balaie une famille de plans fronto-paralleles a la reference, de
     --near a --far, echantillonnes en profondeur INVERSE (c'est la
     disparite qui est lineaire, pas la distance)
  3. chaque plan induit une HOMOGRAPHIE exacte entre les deux images: on
     rectifie la cible dans le repere de la reference
  4. correlation croisee normalisee (NCC) sur une fenetre glissante —
     normalisee parce que les deux frames n'ont ni la meme exposition ni
     la meme heure
  5. pour chaque pixel, le plan qui maximise la NCC donne sa profondeur

Le resultat est un NUAGE DE POINTS 3D: chaque point est une mesure de
triangulation dense, au meme titre qu'un landmark clique, sauf qu'il y en a
des centaines de milliers et que personne n'a clique.

CHOIX DE LA PAIRE (mesure sur nos 9 massifs, cf. --survey):
  * il faut de la parallaxe pour la profondeur, mais PAS trop: a 100 deg
    les deux cameras voient deux faces differentes du massif et aucun
    appariement photometrique n'existe. La bande utile est 5-30 deg.
  * meilleure paire disponible: Mount Waffles vu par Diner (N) et
    Gas Station (Lucia) — 19.3 deg, base 1758 m, cible a 2100 m, soit
    4.5 m de profondeur par pixel d'appariement.

VALIDATION (non tautologique): les ancres triangulees du massif ne servent
PAS a la reconstruction. On mesure ensuite leur distance a la surface
reconstruite. Si le nuage est juste, elles tombent dessus.

Usage:
  PYTHONPATH=. python3 tools/plane_sweep.py --survey
  PYTHONPATH=. python3 tools/plane_sweep.py --ref 'Gas Station (Lucia)' \
      --target 'Diner (N)' --roi 1150,380,1800,560 --near 1500 --far 4000
"""
import argparse
import collections
import json
import math
import os
import sys
import tempfile

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
from PIL import Image

MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
KEY = ('mount', 'hill', 'ridge', 'pass')
SKIP = ('bridge', 'sign', 'billboard', 'road', 'st ', 'tower', 'station')


def massif_of(name):
    lo = name.lower()
    if not any(k in lo for k in KEY) or any(s in lo for s in SKIP):
        return None
    return name.split(' (')[0]


def gray(cam_name):
    p = os.path.join(REPO, 'frames', f'{cam_name}.png')
    if not os.path.exists(p):
        raise SystemExit(f'frame absente: {p}')
    return np.asarray(Image.open(p).convert('L'), np.float32)


def survey():
    """Toutes les paires de cameras posees voyant le meme massif, avec la
    parallaxe, la base et la sensibilite en profondeur."""
    import common
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))

    def posed(c):
        e = cams.get(c, {})
        return bool(e.get('xyz') and e.get('ypr') and any(e['ypr'])
                    and e.get('fov') and (e['fov'][0] or e['fov'][1]))

    obs = collections.defaultdict(set)
    for c, mk in px.items():
        if not posed(c):
            continue
        for lm, p in mk.items():
            m = massif_of(lm)
            if m and p is not None:
                obs[m].add(c)
    print(f'{"massif":18s} {"par":>5s} {"base":>6s} {"dist":>6s} {"m/px":>6s}  paire')
    out = []
    for m, cs in sorted(obs.items()):
        cs = sorted(cs)
        P = [np.asarray(lms[l]['xyz'], float) for l in lms
             if isinstance(lms.get(l), dict) and lms[l].get('xyz')
             and massif_of(l) == m]
        if not P or len(cs) < 2:
            continue
        T = np.mean(P, axis=0)
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                a = np.asarray(cams[cs[i]]['xyz'], float)
                b = np.asarray(cams[cs[j]]['xyz'], float)
                va, vb = T - a, T - b
                cth = float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb)))
                ang = math.degrees(math.acos(max(-1.0, min(1.0, cth))))
                if not (4.0 <= ang <= 30.0):
                    continue
                if not all(os.path.exists(os.path.join(REPO, 'frames', f'{c}.png'))
                           for c in (cs[i], cs[j])):
                    continue
                d = float((np.linalg.norm(va) + np.linalg.norm(vb)) / 2)
                cam = common.get_cam(cs[i])
                dz = d * math.radians(cam.hfov / cam.w) / math.radians(ang)
                print(f'{m[:18]:18s} {ang:5.1f} {np.linalg.norm(a - b):6.0f} '
                      f'{d:6.0f} {dz:6.1f}  {cs[i][:26]} x {cs[j][:26]}')
                out.append((m, cs[i], cs[j], ang, d))
    print(f'\n{len(out)} paires exploitables (parallaxe 4-30 deg, frames presentes)')
    return out


def homography(ref, tgt, depth, corners):
    """Homographie ref -> cible induite par le plan fronto-parallele a la
    reference situe a `depth` metres. Construite numeriquement en projetant
    les 4 coins du ROI sur le plan puis dans la cible: pas besoin d'extraire
    K et R, et ca reste exact."""
    import cv2
    o = np.asarray(ref.xyz, float)
    f = np.asarray(ref.get_pixel_direction((ref.w / 2.0, ref.h / 2.0)), float)
    f /= np.linalg.norm(f)
    src, dst = [], []
    for (u, v) in corners:
        d = np.asarray(ref.get_pixel_direction((float(u), float(v))), float)
        d /= np.linalg.norm(d)
        den = float(d @ f)
        if den <= 1e-6:
            return None
        P = o + (depth / den) * d
        q = tgt.get_pixel([float(x) for x in P])
        if q is None:
            return None
        src.append([float(u), float(v)])
        dst.append([float(q[0]), float(q[1])])
    return cv2.getPerspectiveTransform(np.float32(src), np.float32(dst))


POP8 = np.array([bin(i).count('1') for i in range(256)], np.uint8)


def census(img, r=2):
    """Transformee census: chaque pixel devient le motif binaire des
    comparaisons avec ses voisins. Ce qui est encode n'est pas l'intensite
    mais son ORDRE local — donc c'est invariant a tout changement monotone
    d'exposition, de gamma ou de lumiere. C'est exactement le probleme ici:
    nos deux frames n'ont ni la meme heure ni la meme meteo."""
    h, w = img.shape
    pad = np.pad(img, r, mode='edge')
    out = np.zeros((h, w), np.uint32)
    bit = 0
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy == 0 and dx == 0:
                continue
            nb = pad[r + dy:r + dy + h, r + dx:r + dx + w]
            out |= ((nb > img).astype(np.uint32) << bit)
            bit += 1
    return out


def hamming(a, b):
    x = np.bitwise_xor(a, b).view(np.uint8).reshape(a.shape + (4,))
    return POP8[x].sum(axis=2).astype(np.float32)


def ncc_maps(A, B, win):
    """NCC locale entre deux images de meme taille, fenetre carree `win`.
    Filtres box => O(1) par pixel, quelle que soit la fenetre."""
    import cv2
    k = (win, win)
    mA = cv2.boxFilter(A, -1, k, normalize=True)
    mB = cv2.boxFilter(B, -1, k, normalize=True)
    vA = cv2.boxFilter(A * A, -1, k, normalize=True) - mA * mA
    vB = cv2.boxFilter(B * B, -1, k, normalize=True) - mB * mB
    cov = cv2.boxFilter(A * B, -1, k, normalize=True) - mA * mB
    return cov / np.sqrt(np.maximum(vA, 1e-3) * np.maximum(vB, 1e-3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--survey', action='store_true')
    ap.add_argument('--ref')
    ap.add_argument('--target', help='une ou plusieurs cibles separees par ";"')
    ap.add_argument('--roi', help='x0,y0,x1,y1 dans la frame de reference')
    ap.add_argument('--near', type=float, default=1200.0)
    ap.add_argument('--far', type=float, default=4500.0)
    ap.add_argument('--steps', type=int, default=256)
    ap.add_argument('--win', type=int, default=15)
    ap.add_argument('--antialias', action='store_true',
                    help="floute la cible a l'echelle du plan avant de la "
                         "deformer (indispensable des que les deux vues "
                         "n'ont pas la meme resolution au sol)")
    ap.add_argument('--census', action='store_true',
                    help='apparie sur la transformee census (invariante a '
                         "l'eclairage) plutot que sur la NCC d'intensite")
    ap.add_argument('--sgm', type=float, default=0.35,
                    help="penalite d'agregation semi-globale (0 = desactivee)")
    ap.add_argument('--min-ncc', type=float, default=0.55)
    ap.add_argument('--step-px', type=int, default=4, help='pas d echantillonnage du nuage')
    ap.add_argument('--name', default='Relief (stereo)')
    ap.add_argument('--dump', help='ecrit la carte de profondeur en PNG')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    if args.survey or not (args.ref and args.target):
        survey()
        return

    import cv2
    import common

    R = common.get_cam(args.ref)
    targets = [t.strip() for t in args.target.split(';') if t.strip()]
    A = gray(args.ref)
    Acen = census(A)
    x0, y0, x1, y1 = ([int(v) for v in args.roi.split(',')] if args.roi
                      else [0, 0, int(R.w), int(R.h)])
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    Aroi = np.ascontiguousarray(A[y0:y1, x0:x1])
    AcenRoi = np.ascontiguousarray(Acen[y0:y1, x0:x1])
    h, w = Aroi.shape
    o = np.asarray(R.xyz, float)
    print(f'reference {args.ref} ({R.w:.0f}x{R.h:.0f}, hfov {R.hfov:.1f}), ROI {w}x{h}')
    for t in targets:
        Tc = common.get_cam(t)
        print(f'  cible {t[:34]:34s} base '
              f'{np.linalg.norm(o - np.asarray(Tc.xyz, float)):6.0f} m')
    print(f'{args.steps} plans de {args.near:.0f} a {args.far:.0f} m '
          f'(pas en profondeur inverse), fenetre NCC {args.win}')

    inv = np.linspace(1.0 / args.far, 1.0 / args.near, args.steps)
    depths = 1.0 / inv

    # VOLUME DE COUT complet (h, w, D). On ne prend plus le meilleur plan a
    # la volee: garder tout le volume est ce qui permet d'agreger ensuite.
    # C'est aussi ce qui permet de cumuler PLUSIEURS cibles: un flanc sans
    # texture est ambigu pour une paire et peut ne pas l'etre pour l'autre.
    cost = np.zeros((h, w, args.steps), np.float32)
    seen = np.zeros((h, w, args.steps), np.float32)
    for tn in targets:
        Tc = common.get_cam(tn)
        B = gray(tn)
        Bcen = census(B).astype(np.float32) if args.census else None
        used = 0
        for di, d in enumerate(depths):
            H = homography(R, Tc, float(d), corners)
            if H is None:
                continue
            Tr = np.array([[1, 0, x0], [0, 1, y0], [0, 0, 1]], np.float64)
            Hroi = H @ Tr
            # ANTI-ALIASING: l'homographie corrige la geometrie mais pas
            # l'ECHANTILLONNAGE. Quand la cible a une resolution au sol plus
            # fine que la reference (ici 0.64 contre 1.36 m/px, soit 2.1x),
            # un pixel de reference couvre deux pixels de cible: la lire au
            # plus proche voisin, c'est de l'aliasing, et l'aliasing detruit
            # la correlation — c'est exactement ce qui faisait preferer un
            # mauvais plan. On floute donc la cible a l'echelle du plan
            # avant de la deformer. Le facteur local vient du jacobien de
            # l'homographie au centre du ROI.
            src = B
            if args.antialias:
                cx, cy = w / 2.0, h / 2.0
                J = np.zeros((2, 2))
                for k, (dx, dy) in enumerate(((1.0, 0.0), (0.0, 1.0))):
                    p0 = Hroi @ np.array([cx, cy, 1.0])
                    p1 = Hroi @ np.array([cx + dx, cy + dy, 1.0])
                    J[:, k] = p1[:2] / p1[2] - p0[:2] / p0[2]
                sc = math.sqrt(abs(float(np.linalg.det(J))) + 1e-9)
                if sc > 1.2:
                    sg = 0.5 * sc
                    src = cv2.GaussianBlur(B, (0, 0), sg)
            warp = cv2.warpPerspective(src, Hroi, (w, h),
                                       flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                                       borderValue=np.nan)
            ok = np.isfinite(warp)
            if ok.mean() < 0.15:
                continue
            if args.census:
                # le motif census est binaire: on le transporte au PLUS
                # PROCHE VOISIN, interpoler des bits n'aurait aucun sens
                wc = cv2.warpPerspective(Bcen, Hroi, (w, h),
                                         flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP,
                                         borderValue=0)
                ham = hamming(AcenRoi, wc.astype(np.uint32))
                # moyenne sur la fenetre, puis normalisation en [0,1]
                c = cv2.boxFilter(ham, -1, (args.win, args.win), normalize=True) / 24.0
            else:
                n = ncc_maps(Aroi, np.where(ok, warp, 0.0).astype(np.float32), args.win)
                c = 1.0 - n
            cost[:, :, di] += np.where(ok, c, 0.0)
            seen[:, :, di] += ok
            used += 1
        print(f'  {tn[:34]:34s} {used}/{args.steps} plans exploitables')
    valid = seen > 0
    cost = np.where(valid, cost / np.maximum(seen, 1), 2.0).astype(np.float32)

    # AGREGATION SEMI-GLOBALE: sur une pente d'herbe, la NCC est plate — le
    # pixel seul ne sait pas sa profondeur. Mais un terrain est CONTINU. On
    # propage donc le cout le long de 4 balayages (gauche-droite, haut-bas
    # et retours) en penalisant les sauts de profondeur, ce qui laisse les
    # zones texturees imposer leur solution aux zones lisses voisines.
    if args.sgm > 0:
        P1, P2 = args.sgm * 0.25, args.sgm
        agg = np.zeros_like(cost)
        for axis, rev in ((1, False), (1, True), (0, False), (0, True)):
            L = np.zeros_like(cost)
            rng = range(cost.shape[axis])
            rng = reversed(rng) if rev else rng
            prev = None
            for k in rng:
                cur = cost[:, k, :] if axis == 1 else cost[k, :, :]
                if prev is None:
                    L_k = cur.copy()
                else:
                    m = prev.min(axis=1, keepdims=True)
                    a = prev
                    b = np.minimum(np.roll(prev, 1, axis=1),
                                   np.roll(prev, -1, axis=1)) + P1
                    L_k = cur + np.minimum(np.minimum(a, b), m + P2) - m
                if axis == 1:
                    L[:, k, :] = L_k
                else:
                    L[k, :, :] = L_k
                prev = L_k
            agg += L
        cost = agg / 4.0

    bi = np.argmin(cost, axis=2)
    ii, jj = np.indices(bi.shape)
    best_cost = cost[ii, jj, bi]
    # SOUS-PLAN: parabole sur les trois couts voisins, en profondeur INVERSE
    lo = cost[ii, jj, np.clip(bi - 1, 0, args.steps - 1)]
    hi = cost[ii, jj, np.clip(bi + 1, 0, args.steps - 1)]
    den = (lo - 2 * best_cost + hi)
    off = np.where(np.abs(den) > 1e-6, 0.5 * (lo - hi) / np.where(den == 0, 1, den), 0.0)
    off = np.clip(off, -1.0, 1.0)
    invd = np.interp(bi + off, np.arange(args.steps), inv)
    bestd = (1.0 / invd).astype(np.float32)

    # CONFIANCE: le minimum doit se DETACHER. On compare au meilleur cout
    # hors du voisinage du gagnant (ratio test) — un flanc uniforme donne un
    # minimum a peine plus bas que le reste et sera rejete.
    m2 = cost.copy()
    for k in range(-3, 4):
        m2[ii, jj, np.clip(bi + k, 0, args.steps - 1)] = 9.9
    second = m2.min(axis=2)
    ratio = best_cost / np.maximum(second, 1e-6)
    thr = 0.46 if args.census else 1.0 - args.min_ncc
    keep = valid.any(axis=2) & (best_cost < thr) & (ratio < 0.92)
    print(f'\npixels retenus: {int(keep.sum())} / {h * w} '
          f'({100.0 * keep.mean():.1f} pct)  [NCC > {args.min_ncc}, '
          f'ratio au second minimum < 0.92]')
    if not keep.any():
        raise SystemExit('aucun appariement fiable — elargir --near/--far '
                         'ou baisser --min-ncc')

    # LISSAGE: la NCC est bruitee pixel a pixel; un filtre median sur la
    # carte de profondeur (et non sur le nuage) enleve les faux appariements
    # isoles sans deplacer les vraies discontinuites de relief.
    dm = np.where(keep, bestd, np.nan).astype(np.float32)
    fill = np.where(keep, bestd, np.nanmedian(bestd[keep])).astype(np.float32)
    med = cv2.medianBlur(fill, 5)
    jump = np.abs(med - bestd) > 0.06 * np.maximum(bestd, 1.0)
    keep = keep & ~jump
    bestd = med
    print(f'lissage median: {int(jump.sum())} pixels ecartes (saut > 6 pct), '
          f'{int(keep.sum())} restants')

    if args.dump:
        vis = np.zeros((h, w, 3), np.uint8)
        v = np.where(keep, bestd, np.nan)
        lo, hi = np.nanpercentile(v, 2), np.nanpercentile(v, 98)
        t = np.clip((v - lo) / max(1e-6, hi - lo), 0, 1)
        vis[..., 0] = np.nan_to_num((1 - t) * 255).astype(np.uint8)
        vis[..., 1] = np.nan_to_num(np.abs(0.5 - t) * 2 * 255).astype(np.uint8)
        vis[..., 2] = np.nan_to_num(t * 255).astype(np.uint8)
        vis[~keep] = (30, 30, 30)
        side = np.concatenate([np.stack([Aroi.astype(np.uint8)] * 3, axis=2), vis], axis=0)
        Image.fromarray(side).resize((w * 2, side.shape[0] * 2),
                                     Image.NEAREST).save(args.dump)
        print(f'carte de profondeur -> {args.dump}  '
              f'(rouge = proche {lo:.0f} m, bleu = loin {hi:.0f} m)')

    f = np.asarray(R.get_pixel_direction((R.w / 2.0, R.h / 2.0)), float)
    f /= np.linalg.norm(f)
    pts = []
    for vy in range(0, h, args.step_px):
        for vx in range(0, w, args.step_px):
            if not keep[vy, vx]:
                continue
            d = np.asarray(R.get_pixel_direction((float(x0 + vx), float(y0 + vy))), float)
            d /= np.linalg.norm(d)
            den = float(d @ f)
            if den <= 1e-6:
                continue
            pts.append(o + (bestd[vy, vx] / den) * d)
    P = np.array(pts)
    print(f'\nnuage: {len(P)} points, '
          f'distance {np.linalg.norm(P[:, :2] - o[:2], axis=1).min():.0f}-'
          f'{np.linalg.norm(P[:, :2] - o[:2], axis=1).max():.0f} m, '
          f'z {P[:, 2].min():.0f} a {P[:, 2].max():.0f} m')

    # VALIDATION: les ancres n'ont pas servi a la reconstruction
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    pxs = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    marks = pxs.get(args.ref) or {}
    print('\nvalidation sur nos ancres (elles n ont PAS servi a reconstruire):')
    print('  On compare la profondeur reconstruite AU PIXEL DE L ANCRE a sa')
    print('  distance vraie — c est la mesure directe, pas un plus-proche-voisin.')
    print(f'  {"landmark":32s} {"vraie":>8s} {"stereo":>8s} {"ecart":>9s}')
    errs, got = [], 0
    for lm, p in marks.items():
        e = lms.get(lm)
        # TOUS les landmarks triangules du ROI, pas seulement le relief:
        # un chateau d'eau ou un poteau est une verite terrain aussi valable
        # et il y en a beaucoup plus.
        if not (isinstance(e, dict) and e.get('xyz')):
            continue
        u, v = int(round(p[0])) - x0, int(round(p[1])) - y0
        if not (0 <= u < w and 0 <= v < h):
            continue
        got += 1
        Q = np.asarray(e['xyz'], float)
        dq = np.asarray(R.get_pixel_direction((float(p[0]), float(p[1]))), float)
        dq /= np.linalg.norm(dq)
        true_along = float((Q - o) @ f)          # profondeur le long de l axe
        # fenetre 7x7 autour du pixel: un clic est a quelques px pres
        sub = bestd[max(0, v - 3):v + 4, max(0, u - 3):u + 4]
        sk = keep[max(0, v - 3):v + 4, max(0, u - 3):u + 4]
        if not sk.any():
            print(f'  {lm[:32]:32s} {true_along:7.0f}m {"—":>8s}   '
                  f'(aucun appariement fiable a ce pixel)')
            continue
        got_d = float(np.median(sub[sk]))
        err = got_d - true_along
        errs.append(abs(err) / max(1.0, true_along))
        print(f'  {lm[:32]:32s} {true_along:7.0f}m {got_d:7.0f}m {err:+8.0f}m '
              f'({100 * abs(err) / max(1, true_along):.1f} pct)')
    if errs:
        print(f'\n  ecart median {100 * float(np.median(errs)):.1f} pct '
              f'sur {len(errs)} ancres')
    elif not got:
        print('  (aucune ancre du massif dans le ROI)')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire le nuage comme mesh).')
        return
    edges = []
    for q in P:
        edges.append([[float(q[0]), float(q[1]), float(q[2])],
                      [float(q[0]), float(q[1]), float(q[2]) + 2.0]])
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    mesh[args.name] = {'color': '#38bdf8', 'world_edges': edges}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as fh:
        json.dump(mesh, fh, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'\nAPPLIED: {args.name} ({len(P)} points)')


if __name__ == '__main__':
    main()
