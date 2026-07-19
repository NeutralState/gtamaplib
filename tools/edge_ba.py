#!/usr/bin/env python3
"""edge_ba.py — bundle adjustment joint clics + bords + structures. [EDGE-BA-V1]

Etage 2 de la pyramide (2026-07-19): UN solve qui pese ensemble
  1. les CLICS (reprojection des markings, tous azimuts, non biaises)
  2. les BORDS sub-pixel (edgefit_core V3, denses mais sector-biased)
  3. les STRUCTURES (implicites: buildings rigides, z gele)
au lieu de les laisser s'arbitrer a la main (le conflit dy=-3m de V3).

Parametres (anti-degenerescence, lecons de la semaine):
  - cams pilotes: dyaw/dpitch/droll SEULEMENT (xyz + fov geles)
  - buildings pilotes: dx/dy/dtheta (z gele — les rooflines sont des structures)
  - jauge: le champ des LMs NON-pilotes reste fixe -> chaque cam est ancree
    en absolu par ses clics hors-pilote; les cams classe A sont exclues des
    parametres (verite HUD).

Cout: soft-l1, normalise PAR FAMILLE (somme clics = somme bords en poids)
pour qu'aucune famille ne domine par son simple compte.
Descente par coordonnees avec CACHE INCREMENTAL: changer un param ne
re-evalue que les termes qui le touchent (cam i -> ses termes; building b ->
les termes qui le voient).

Garde: rapport par famille x cam AVANT/APRES; --apply refuse si une famille
se degrade au-dela du bruit.

Usage:
  PYTHONPATH=. python3 tools/edge_ba.py            # pilote downtown par defaut
  PYTHONPATH=. python3 tools/edge_ba.py --apply
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
import common
from edgefit_core import FrameCtx, sample as edge_sample
from leak_cam_audit import get_class

BUILDINGS = ['Vizcayne North Condominium', 'Vizcayne South Condominium',
             'Stephen P. Clark Government Center']
EDGE_CAMS = ['Port Vice City (A)', 'Port Vice City (B)',
             'Vice City 03 (Basketball)', 'Shitzu Squalo 01 (Bay)']
SIGMA_CLICK = 2.0
SIGMA_EDGE = 5.0
B_YPR = 0.5      # bornes: deg
B_XY = 4.0       # bornes: m
B_TH = math.radians(0.5)


def soft(x):
    return math.sqrt(1.0 + x * x) - 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--freeze-cams', default='', help='cams pilotes a geler (csv) — ex: bound-slammers non resolus')
    args = ap.parse_args()

    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    cams_json = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    bp = json.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')))
    meshes = {b: bp[b]['world_edges'] for b in BUILDINGS}

    def is_pilot_lm(n):
        return any(n.startswith(b + ' (') for b in BUILDINGS)

    # cams pilotes = celles qui cliquent un building pilote (pose libre en ypr),
    # hors classe A/_legacy (verite) et hors cams sans pose fiable
    pilot_cams = set()
    for cn, marks in px.items():
        cls = get_class(cn) or ''
        if cls.startswith('A_') or cls == '_legacy_date':
            continue
        if any(is_pilot_lm(l) and marks[l] is not None and not common.is_excluded_marking(cn, l)
               for l in marks):
            try:
                assert common.get_cam(cn) is not None
                pilot_cams.add(cn)
            except Exception:
                pass
    pilot_cams = sorted(pilot_cams)
    frozen = {c.strip() for c in args.freeze_cams.split(',') if c.strip()}

    # observations clics: (cam, lm, pixel) — TOUTES les obs des cams pilotes
    # (les LMs non-pilotes = ancres de jauge, les pilotes bougent avec dx/dy/dth)
    clicks = []
    for cn in pilot_cams:
        for l, mk in px[cn].items():
            if mk is None or common.is_excluded_marking(cn, l):
                continue
            e = lms.get(l) or {}
            if not isinstance(e, dict) or not e.get('xyz'):
                continue
            clicks.append((cn, l, np.array(mk, float), np.array(e['xyz'], float), is_pilot_lm(l)))
    n_anchor = sum(1 for c in clicks if not c[4])
    print(f'pilote: {len(BUILDINGS)} buildings, {len(pilot_cams)} cams, '
          f'{len(clicks)} clics ({n_anchor} ancres hors-pilote), {len(EDGE_CAMS)} cams-bords')

    # contexts bords
    edge_ctxs = {c: FrameCtx(c) for c in EDGE_CAMS if c in pilot_cams or True}
    centroids = {b: np.mean([p for ab in meshes[b] for p in ab], axis=0) for b in BUILDINGS}

    # ---- parametres ----
    # cams: [dyaw, dpitch, droll] par cam pilote; buildings: [dx, dy, dth]
    cam_idx = {c: i for i, c in enumerate(pilot_cams)}
    b_idx = {b: i for i, b in enumerate(BUILDINGS)}
    theta = np.zeros(3 * len(pilot_cams) + 3 * len(BUILDINGS))

    def cam_state(cn, th):
        e0 = cams_json[cn]
        i = 3 * cam_idx[cn]
        return {'xyz': e0['xyz'],
                'ypr': [e0['ypr'][0] + th[i], e0['ypr'][1] + th[i + 1], e0['ypr'][2] + th[i + 2]],
                'fov': e0['fov']}

    def move_pt(p, b, th):
        j = 3 * len(pilot_cams) + 3 * b_idx[b]
        dx, dy, dth = th[j], th[j + 1], th[j + 2]
        c0 = centroids[b]
        cth, sth = math.cos(dth), math.sin(dth)
        x = c0[0] + cth * (p[0] - c0[0]) - sth * (p[1] - c0[1]) + dx
        y = c0[1] + sth * (p[0] - c0[0]) + cth * (p[1] - c0[1]) + dy
        return [x, y, p[2]]

    def building_of(l):
        for b in BUILDINGS:
            if l.startswith(b + ' ('):
                return b
        return None

    # ---- termes de cout (caches) ----
    # clic terme t = (cn, lm, ...) depend de cam(cn) et building(lm) eventuel
    W_CLICK = 1.0 / max(1, len(clicks))
    # bords: pairs (cam_bords, building)
    edge_pairs = [(c, b) for c in edge_ctxs for b in BUILDINGS]
    W_EDGE = 1.0 / max(1, len(edge_pairs) * 800)   # ~n moyen d'echantillons

    def click_term(t, th):
        cn, l, mk, xyz, pilot = t
        cam = common.get_cam(cn, cam_state(cn, th))
        p = xyz
        if pilot:
            p = move_pt(xyz, building_of(l), th)
        pr = cam.get_pixel(list(p))
        if pr is None:
            return 10.0
        d = math.hypot(pr[0] - mk[0], pr[1] - mk[1])
        return soft(d / SIGMA_CLICK)

    def edge_term(pair, th):
        cn, b = pair
        ctx = edge_ctxs[cn]
        if cn in cam_idx:
            ctx.recam(cam_state(cn, th))
        te = [[move_pt(a, b, th), move_pt(bb, b, th)] for a, bb in meshes[b]]
        r = edge_sample(ctx, te, collect=True)
        off = r['offsets']
        if len(off) < 15:
            return 0.0
        return float(np.sum(np.sqrt(1.0 + (off / SIGMA_EDGE) ** 2) - 1.0))

    click_cache = np.array([click_term(t, theta) for t in clicks])
    edge_cache = {pair: edge_term(pair, theta) for pair in edge_pairs}

    def total():
        return W_CLICK * float(click_cache.sum()) + W_EDGE * sum(edge_cache.values())

    # index: quels termes dependent de quel parametre
    clicks_by_cam = {}
    clicks_by_b = {}
    for k, t in enumerate(clicks):
        clicks_by_cam.setdefault(t[0], []).append(k)
        if t[4]:
            clicks_by_b.setdefault(building_of(t[1]), []).append(k)

    def refresh(param_i, th):
        """Recalcule uniquement les termes touches par le parametre param_i."""
        ncam = 3 * len(pilot_cams)
        if param_i < ncam:
            cn = pilot_cams[param_i // 3]
            for k in clicks_by_cam.get(cn, []):
                click_cache[k] = click_term(clicks[k], th)
            for pair in edge_pairs:
                if pair[0] == cn:
                    edge_cache[pair] = edge_term(pair, th)
        else:
            b = BUILDINGS[(param_i - ncam) // 3]
            for k in clicks_by_b.get(b, []):
                click_cache[k] = click_term(clicks[k], th)
            for pair in edge_pairs:
                if pair[1] == b:
                    edge_cache[pair] = edge_term(pair, th)

    def family_report(th, label):
        import statistics
        cg = []
        for t in clicks:
            cn, l, mk, xyz, pilot = t
            cam = common.get_cam(cn, cam_state(cn, th))
            p = move_pt(xyz, building_of(l), th) if pilot else xyz
            a, g, d = common.residual_dual(cam, mk.tolist(), list(p))
            if g is not None:
                cg.append(g)
        eb = {}
        for pair in edge_pairs:
            cn, b = pair
            ctx = edge_ctxs[cn]
            ctx.recam(cam_state(cn, th)) if cn in cam_idx else None
            te = [[move_pt(a, b, th), move_pt(bb, b, th)] for a, bb in meshes[b]]
            r = edge_sample(ctx, te, collect=True)
            if len(r['offsets']) > 30:
                eb[f'{cn.split("(")[0].strip()[:12]}/{b.split()[0][:8]}'] = float(np.median(r['offsets']))
        print(f'── {label}: clics median {statistics.median(cg):.3f}m (n={len(cg)}) | '
              f'bords biais: ' + '  '.join(f'{k}={v:+.1f}' for k, v in eb.items()))
        return statistics.median(cg), eb

    med0, eb0 = family_report(theta, 'AVANT')

    # ---- descente par coordonnees, cache incremental ----
    ncam = 3 * len(pilot_cams)
    steps = np.array([0.05] * ncam + [0.5, 0.5, math.radians(0.1)] * len(BUILDINGS))
    for c in frozen:
        if c in cam_idx:
            steps[3 * cam_idx[c]:3 * cam_idx[c] + 3] = 0.0
    bounds = np.array([B_YPR] * ncam + [B_XY, B_XY, B_TH] * len(BUILDINGS))
    best_cost = total()
    print(f'cout initial {best_cost:.4f} — descente ({len(theta)} params)...')
    for rnd in range(40):
        improved = False
        for i in range(len(theta)):
            s = steps[i]
            if s < 1e-4:
                continue
            for sgn in (1, -1):
                old = theta[i]
                cand = old + sgn * s
                if abs(cand) > bounds[i]:
                    continue
                theta[i] = cand
                refresh(i, theta)
                c = total()
                if c < best_cost - 1e-9:
                    best_cost = c
                    improved = True
                else:
                    theta[i] = old
                    refresh(i, theta)
        if not improved:
            steps = steps / 2
            if steps.max() < 5e-3:
                break
    print(f'cout final {best_cost:.4f}')

    ncam_ = 3 * len(pilot_cams)
    print('\n── deltas cams (dyaw dpitch droll, deg):')
    for c in pilot_cams:
        i = 3 * cam_idx[c]
        d = theta[i:i + 3]
        if np.abs(d).max() > 0.005:
            print(f'   {c[:32]:32} {d[0]:+.3f} {d[1]:+.3f} {d[2]:+.3f}')
    print('── deltas buildings (dx dy m, dth deg):')
    for b in BUILDINGS:
        j = ncam_ + 3 * b_idx[b]
        print(f'   {b[:36]:36} {theta[j]:+.2f} {theta[j+1]:+.2f} {math.degrees(theta[j+2]):+.3f}')

    med1, eb1 = family_report(theta, 'APRES')

    if not args.apply:
        print('\nDRY-RUN. --apply pour ecrire.')
        return
    if med1 > med0 * 1.03:
        sys.exit(f'REFUSE: clics {med0:.3f} -> {med1:.3f} (degradation famille clics)')
    # ecrire: cams ypr + coins buildings
    for c in pilot_cams:
        i = 3 * cam_idx[c]
        if np.abs(theta[i:i + 3]).max() < 0.005:
            continue
        e0 = cams_json[c]
        e0['ypr'] = [round(e0['ypr'][0] + theta[i], 4), round(e0['ypr'][1] + theta[i + 1], 4),
                     round(e0['ypr'][2] + theta[i + 2], 4)]
    tmp = os.path.join(REPO, 'gtamapdata', 'cameras.json.tmp')
    json.dump(cams_json, open(tmp, 'w'), indent=2, ensure_ascii=True)
    os.replace(tmp, os.path.join(REPO, 'gtamapdata', 'cameras.json'))
    lms_path = os.path.join(REPO, 'gtamapdata', 'landmarks.json')
    lms2 = json.load(open(lms_path))
    for n, e in lms2.items():
        b = building_of(n)
        if b and isinstance(e, dict) and e.get('xyz'):
            e['xyz'] = [round(v, 3) for v in move_pt(e['xyz'], b, theta)]
    tmp = lms_path + '.tmp'
    json.dump(lms2, open(tmp, 'w'), indent=2, ensure_ascii=True)
    os.replace(tmp, lms_path)
    common.log_event('edge_ba', 'joint_applied',
                     reason=f'EDGE-BA pilote: {len(pilot_cams)} cams ypr + {len(BUILDINGS)} buildings, '
                            f'clics {med0:.3f}->{med1:.3f}m')
    print('APPLIED. Regenerer les meshes procedureaux + cycle!')


if __name__ == '__main__':
    main()
