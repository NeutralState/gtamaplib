#!/usr/bin/env python3
"""anchor_harvest.py — la moisson d'ancres. [ANCHOR-HARVEST-V1]

Doctrine 'map la plus precise ever': les ancres (points triangules 2+ cams)
sont la seule monnaie de precision. Cet outil ramasse TOUS les landmarks
observes par >= 2 cams posees et jamais triangules, et les triangule avec
des gates de qualite:

  * angle minimal entre rayons  >= --min-angle (defaut 2.5 deg — en dessous
    la profondeur est molle)
  * residu perpendiculaire max  <= max(15 m, 1.2% de la distance)
  * resultat dans les bornes monde (|xy| < 17 km, -100 < z < 1200)

Ecrit xyz + source_cameras + error_m (mediane des perps) + method.
Ne touche JAMAIS un landmark qui a deja un xyz. Dry-run par defaut.

Usage: PYTHONPATH=. python3 tools/anchor_harvest.py [--apply] [--min-angle 2.5]
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
import common
import gtamapdata as md
from common import ray_ls_point


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--min-angle', type=float, default=2.5)
    ap.add_argument('--profile', choices=['default', 'mountain'], default='default',
                    help="mountain: cible les massifs — parallaxe MINIMALE plus "
                         "exigeante (5 deg, sinon la profondeur est molle a 3 km) "
                         "mais tolerance perpendiculaire plus large (2 pct), "
                         "parce qu'un clic sur une crete floue est ambigu de "
                         "quelques dizaines de metres, pas de quelques metres")
    args = ap.parse_args()

    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))

    def posed(c):
        e = cams.get(c, {})
        return bool(e.get('xyz') and e.get('ypr') and any(e['ypr'])
                    and e.get('fov') and (e['fov'][0] or e['fov'][1]))

    obs = collections.defaultdict(list)
    for c, marks in px.items():
        if not posed(c):
            continue
        for lm, p in marks.items():
            if p is None or common.is_excluded_marking(c, lm):
                continue
            obs[lm].append((c, p))

    # CIRCULARITE: la pose d'Empty Lot a ete FITTEE sur ses deux seuls clics
    # du massif, donc ces clics-la ne peuvent pas servir de temoin. Ce n'est
    # plus une liste noire de NOMS (le massif s'appelle desormais Mount
    # Ambrosia, et un blacklist global tuerait Mount Ambrosia (D) qui est
    # triangule sur 3 cameras) mais une exclusion par CAMERA, dans
    # gtamapdata/excluded_markings.json — is_excluded_marking la lit deja
    # plus haut dans la collecte.
    BLACKLIST = set()
    MTN = ('mount', 'hill', 'ridge', 'pass', 'massif')
    def is_mtn(name):
        low = name.lower()
        return any(k in low for k in MTN) and 'bridge' not in low
    min_angle = 5.0 if args.profile == 'mountain' else args.min_angle
    perp_frac = 0.020 if args.profile == 'mountain' else 0.012
    # PLANCHER selon la TAILLE de l'objet, pas seulement selon la distance.
    # Le plancher unique de 15 m laissait passer des aberrations sur de
    # petits objets: 'Tall Billboard near Interchange' triangule avec 14 m
    # de residu perpendiculaire — pour un panneau qui mesure quelques
    # metres, ca veut dire que les deux rayons ne visent pas le meme point.
    # Un massif, lui, a le droit a ses dizaines de metres: on ne clique pas
    # une crete brumeuse au metre pres.
    SMALL = ('billboard', 'sign', 'pole', 'pylon', 'antenna', 'window',
             'door', 'parassol', 'tank', 'silo')
    def gate_for(name, dist):
        """Tolerance perpendiculaire admise pour CE landmark a CETTE distance.

        Le terme dominant est la fraction de distance, pas le plancher: a
        1500 m, 1.2 pct vaut deja 18 m et le plancher ne sert a rien. C'est
        donc la FRACTION qu'il faut resserrer sur les petits objets. Un
        panneau publicitaire a des coins nets: deux clics dessus doivent se
        croiser a 0.4 pct de la distance, pas 1.2. Une crete brumeuse, elle,
        garde sa tolerance large — l'ambiguite y est reelle."""
        if args.profile == 'mountain' or is_mtn(name):
            return max(15.0, perp_frac * dist)
        if any(k in name.lower() for k in SMALL):
            return max(4.0, 0.004 * dist)
        return max(15.0, perp_frac * dist)
    accepted, rejected = [], []
    for lm, wits in sorted(obs.items()):
        if lm in BLACKLIST:
            rejected.append((lm, 'circulaire (pose EL fittee sur ce clic)'))
            continue
        e = lms.get(lm)
        if isinstance(e, dict) and e.get('xyz'):
            continue
        if len(wits) < 2:
            continue
        rays = []
        for c, p in wits:
            cam = common.get_cam(c)          # gotcha #5: re-applique chaque fois
            d = np.asarray(cam.get_pixel_direction(p), float)
            rays.append((c, np.asarray(cam.xyz, float), d / np.linalg.norm(d)))
        # angle max entre paires
        amax = 0.0
        for i in range(len(rays)):
            for j in range(i + 1, len(rays)):
                cth = abs(float(np.dot(rays[i][2], rays[j][2])))
                amax = max(amax, math.degrees(math.acos(min(1.0, cth))))
        if args.profile == 'mountain' and not is_mtn(lm):
            continue
        if amax < min_angle:
            rejected.append((lm, f'angle {amax:.1f} deg'))
            continue
        # Z-CONSTRAINT (invariant CI): un landmark contraint en altitude
        # (plan d'eau, sol) ne se triangule pas librement — on intersecte
        # chaque rayon avec SON plan et on moyenne.
        zc = (md.landmarks_meta.get(lm) or {}).get('z_constraint')
        if isinstance(zc, dict) and zc.get('type') == 'fixed':
            zval = float(zc.get('value', 0.0))
            pts = []
            for _, o, d in rays:
                if abs(d[2]) < 1e-6:
                    continue
                t = (zval - o[2]) / d[2]
                if t > 0:
                    pts.append(o + t * d)
            if len(pts) < 2:
                rejected.append((lm, f'z_constraint {zval}: rayons inexploitables'))
                continue
            spread = float(np.linalg.norm(np.asarray(pts[0])[:2] - np.asarray(pts[-1])[:2]))
            if spread > 60.0:
                rejected.append((lm, f'z_constraint {zval}: rayons rasants '
                                     f'(ecart {spread:.0f} m)'))
                continue
            P = np.mean(pts, axis=0)
            P[2] = zval
        else:
            try:
                P = np.asarray(ray_ls_point([(o, d) for _, o, d in rays]), float)
            except Exception as ex:
                rejected.append((lm, f'solve: {ex}'))
                continue
        if not np.all(np.isfinite(P)) or abs(P[0]) > 17000 or abs(P[1]) > 17000 \
                or not (-100 < P[2] < 1200):
            rejected.append((lm, f'hors bornes {np.round(P, 0)}'))
            continue
        perps, dists = [], []
        for _, o, d in rays:
            v = P - o
            perps.append(float(np.linalg.norm(v - np.dot(v, d) * d)))
            dists.append(float(np.linalg.norm(v)))
        perp_med = float(np.median(perps))
        if perp_med > gate_for(lm, float(np.median(dists))):
            rejected.append((lm, f'perp {perp_med:.1f} m @ {np.median(dists):.0f} m'))
            continue
        accepted.append((lm, P, [c for c, _, _ in rays], perp_med, amax,
                         float(np.median(dists))))

    print(f'{len(accepted)} ACCEPTES / {len(rejected)} rejetes\n')
    for lm, P, cs, perp, ang, dist in accepted:
        print(f'  {lm[:42]:42s} ({P[0]:8.1f},{P[1]:8.1f},{P[2]:7.1f}) '
              f'perp {perp:5.1f} m  angle {ang:5.1f}  {len(cs)} cams')
    print('\nrejets (raison):')
    for lm, why in rejected[:25]:
        print(f'  {lm[:42]:42s} {why}')
    if len(rejected) > 25:
        print(f'  ... +{len(rejected) - 25}')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    for lm, P, cs, perp, ang, dist in accepted:
        e = lms.get(lm) if isinstance(lms.get(lm), dict) else {}
        e.update({
            'xyz': [round(float(v), 2) for v in P],
            'source_cameras': cs,
            'error_m': round(max(2.0, perp), 1),
            'method': f'ANCHOR-HARVEST-V1 [{args.profile}]: triangulation {len(cs)} cams, '
                      f'perp med {perp:.1f} m ({100 * perp / max(1, dist):.2f} pct), '
                      f'angle max {ang:.1f} deg',
        })
        lms[lm] = e
    path = os.path.join(REPO, 'gtamapdata', 'landmarks.json')
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(lms, f, indent=1, ensure_ascii=True)
    os.replace(tmp, path)
    print(f'\nAPPLIED: {len(accepted)} nouvelles ancres.')


if __name__ == '__main__':
    main()
