#!/usr/bin/env python3
"""hill_stereo.py — la crete d'Ambrosia Hill par stereo de silhouettes. [HILL-STEREO-V1]

Upgrade du rideau plat (HILL-3D-V3): au lieu d'UNE profondeur pour toute la
crete (la corde TW-TE), on resout la profondeur PAR POINT en croisant les
deux silhouettes:

  * Bikers voit la crete en grand (outline valide, corrections d'Alexandre);
  * Empty Lot near Metro Station la voit de ~24 deg plus a l'est — son dome
    est extractible dans le bokeh (bande x ~2900-3230, clics TW/TE dessus).

Pour chaque colonne de l'outline Bikers (un rayon fixe), la profondeur t est
resolue pour que le point 3D projete dans Empty Lot tombe SUR sa silhouette
(correspondance par courbe, pas par point — hypothese: la crete est une
arete assez vive pour que les deux generatrices de silhouette coincident;
vrai au sommet, approximatif sur les flancs arrondis).

La fov d'Empty Lot reste une HYPOTHESE d'echelle (defaut: etat disque).
--fov-sweep imprime la crete obtenue pour fov 40..60 — a confronter aux
contours de la map communautaire pour choisir.

Sortie: crete 3D courbe (profondeur et hauteur variables) -> mesh 'Ambrosia
Hill' (rideau sur ride courbe) + overlay de l'outline EL + table de sweep.

Usage: PYTHONPATH=. python3 tools/hill_stereo.py [--el-fov F] [--fov-sweep]
       [--apply]
"""
import argparse
import importlib.util
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
from PIL import Image, ImageDraw
import common

spec = importlib.util.spec_from_file_location('hm', os.path.join(THIS, 'hill_mesh.py'))
hm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hm)

BIK = 'Ambrosia 01 (Bikers)'
EL = 'Empty Lot near Metro Station'
MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
Z_BASE = 18.87

# bande du dome dans la frame EL; le flanc droit continue jusqu'a ~3300
# (stroke de correction d'Alexandre, 2026-07-26); clics TW/TE en prior
EL_X0, EL_X1 = 2900, 3300


def el_outline(el_state):
    """Silhouette du dome dans Empty Lot (DP de hill_mesh, priors = clics,
    ancres = strokes d'Alexandre dans hill_outline_corrections.json)."""
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    marks = px[EL]
    im = Image.open(os.path.join(REPO, 'frames', f'{EL}.png')).convert('L')
    gray = np.asarray(im, np.float32)
    tw, te = marks['Ambrosia Hill (TW)'], marks['Ambrosia Hill (TE)']
    xs = [EL_X0, tw[0], te[0], EL_X1]
    ys = [tw[1] + 24, tw[1], te[1], te[1] + 36]     # flancs redescendent
    prior = lambda x: float(np.interp(x, xs, ys))
    anchors = []
    corr = os.path.join(THIS, 'data', 'hill_outline_corrections.json')
    if os.path.exists(corr):
        anchors = json.load(open(corr)).get(EL, [])
    # bokeh: bord tres doux -> seuils adoucis
    hm.MIN_EDGE, hm.HARD_EDGE, hm.CORRIDOR = 0.5, 40.0, 70
    cols, sky, meas, manual = hm.extract_skyline(gray, prior, EL_X0, EL_X1,
                                                 anchors=anchors)
    return cols, sky, meas | manual


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--el-fov', type=float, default=None)
    ap.add_argument('--fov-sweep', action='store_true')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    fov_el = args.el_fov or cams[EL]['fov'][0]

    # outline Bikers (le valide, avec corrections)
    oj = json.load(open(os.path.join(REPO, 'tools', 'generated',
                                     'ambrosia_hill_outline.json')))
    bik_out = [(p['x'], p['y']) for p in oj['points'] if p['source'] != 'bridge'
               or True]                     # ponts inclus (crete continue)
    cam_b = common.get_cam(BIK)
    o_b = np.asarray(cam_b.xyz, float)

    def solve(fov):
        """Crete 3D par point pour une fov EL donnee. Re-fitte d'abord
        yaw/pitch d'EL sur la corde TW-TE a la profondeur de cette fov."""
        t_chord, _ = hm.solve_depth(cam_b, px, cams, fov)
        marks_b = px[BIK]
        rw = np.asarray(cam_b.get_pixel_direction(marks_b['Ambrosia Hill (TW)']), float)
        re = np.asarray(cam_b.get_pixel_direction(marks_b['Ambrosia Hill (TE)']), float)
        rw, re = rw / np.linalg.norm(rw), re / np.linalg.norm(re)
        P_tw, P_te = o_b + t_chord * rw, o_b + t_chord * re
        # yaw/pitch EL par grille fine (roll 0)
        st = {'xyz': list(cams[EL]['xyz']), 'ypr': [0, 0, 0], 'fov': [fov, None]}
        clicks = px[EL]
        best = None
        for yaw in np.arange(30, 60, 0.5):
            for pitch in np.arange(-6, 3, 0.5):
                st['ypr'] = [yaw, pitch, 0.0]
                c = common.get_cam(EL, st)
                e = 0.0
                ok = True
                for lm, P in [('Ambrosia Hill (TW)', P_tw), ('Ambrosia Hill (TE)', P_te)]:
                    pr = c.get_pixel([float(v) for v in P])
                    if pr is None:
                        ok = False
                        break
                    e += (pr[0] - clicks[lm][0]) ** 2 + (pr[1] - clicks[lm][1]) ** 2
                if ok and (best is None or e < best[0]):
                    best = (e, yaw, pitch)
        _, yaw, pitch = best
        for stp in (0.1, 0.02):
            for dy in np.arange(-0.5, 0.51, stp):
                for dp in np.arange(-0.5, 0.51, stp):
                    st['ypr'] = [yaw + dy, pitch + dp, 0.0]
                    c = common.get_cam(EL, st)
                    e = 0.0
                    ok = True
                    for lm, P in [('Ambrosia Hill (TW)', P_tw), ('Ambrosia Hill (TE)', P_te)]:
                        pr = c.get_pixel([float(v) for v in P])
                        if pr is None:
                            ok = False
                            break
                        e += (pr[0] - clicks[lm][0]) ** 2 + (pr[1] - clicks[lm][1]) ** 2
                    if ok and e < best[0]:
                        best = (e, yaw + dy, pitch + dp)
        _, yaw, pitch = best
        st['ypr'] = [yaw, pitch, 0.0]
        el_state = dict(st)

        cols_e, sky_e, meas_e = el_outline(el_state)
        sil_e = lambda x: float(np.interp(x, cols_e, sky_e))
        c_el = common.get_cam(EL, el_state)

        # profondeur stereo la ou EL voit la crete; ailleurs la crete
        # COMPLETE de l'outline Bikers est gardee, profondeur prolongee
        # par tenue de bord (np.interp) — on ne coupe pas la montagne.
        rays, sol_i, sol_t = [], [], []
        for i, (x, y) in enumerate(bik_out[::2]):
            r = np.asarray(cam_b.get_pixel_direction((float(x), float(y))), float)
            rays.append(r / np.linalg.norm(r))
        for i, r in enumerate(rays):

            def miss(t):
                pr = c_el.get_pixel([float(v) for v in (o_b + t * r)])
                if pr is None or pr[0] < cols_e[0] or pr[0] > cols_e[-1]:
                    return None
                return pr[1] - sil_e(pr[0])   # >0: sous la silhouette EL

            lo, hi = None, None
            for t in np.arange(800, 6000, 60):
                m = miss(t)
                if m is None:
                    continue
                if m > 0 and lo is None:
                    lo = t
                if m <= 0 and lo is not None:
                    hi = t
                    break
            if lo is None or hi is None:
                continue
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                m = miss(mid)
                if m is None:
                    break
                if m > 0:
                    lo = mid
                else:
                    hi = mid
            sol_i.append(i)
            sol_t.append(0.5 * (lo + hi))
        if not sol_i:
            return np.zeros((0, 3)), el_state, (cols_e, sky_e, meas_e), t_chord, 0
        # lissage des t resolus puis interpolation/tenue de bord partout;
        # lissage LARGE ensuite: le raccord bord/stereo et les flancs
        # arrondis (correspondance approximative) ne meritent pas des
        # virages a 300 m — le terrain est continu.
        sol_t = np.array([np.median(sol_t[max(0, k - 3):k + 4])
                          for k in range(len(sol_t))])
        all_t = np.interp(np.arange(len(rays)), sol_i, sol_t)
        for w in (15, 9):
            all_t = np.array([np.mean(all_t[max(0, k - w // 2):k + w // 2 + 1])
                              for k in range(len(all_t))])
        ridge = np.array([o_b + t * r for t, r in zip(all_t, rays)])
        return ridge, el_state, (cols_e, sky_e, meas_e), t_chord, len(sol_i)

    if args.fov_sweep:
        print(f'{"fov EL":>7s} {"d corde":>8s} {"z max":>7s} {"d min-max ride":>16s} {"n pts":>6s}')
        for fov in range(40, 61, 2):
            ridge, st, _, tc, nsol = solve(float(fov))
            if not len(ridge):
                print(f'{fov:7.0f}  (pas de solution)')
                continue
            d = np.hypot(ridge[:, 0] - o_b[0], ridge[:, 1] - o_b[1])
            print(f'{fov:7.0f} {tc:8.0f} {ridge[:, 2].max():7.0f} '
                  f'{d.min():7.0f}-{d.max():.0f} {len(ridge):6d}')
        return

    ridge, el_state, (cols_e, sky_e, meas_e), t_chord, nsol = solve(fov_el)
    d = np.hypot(ridge[:, 0] - o_b[0], ridge[:, 1] - o_b[1])
    print(f'fov EL {fov_el}: pose EL yaw {el_state["ypr"][0]:.2f} pitch {el_state["ypr"][1]:.2f}')
    print(f'crete COMPLETE: {len(ridge)} points dont {nsol} resolus en stereo '
          f'(le reste: profondeur tenue de bord), profondeur {d.min():.0f} -> {d.max():.0f} m '
          f'(corde: {t_chord:.0f}), z {ridge[:, 2].min():.0f} -> {ridge[:, 2].max():.0f} m')

    # overlay EL: silhouette extraite + crete reprojetee
    rgb = Image.open(os.path.join(REPO, 'frames', f'{EL}.png')).convert('RGB')
    dr = ImageDraw.Draw(rgb)
    pts = list(zip(cols_e, sky_e))
    for i in range(len(pts) - 1):
        col = (74, 222, 128) if meas_e[i] else (251, 146, 60)
        dr.line([pts[i], pts[i + 1]], fill=col, width=4)
    c_el = common.get_cam(EL, el_state)
    prev = None
    for P in ridge:
        pr = c_el.get_pixel([float(v) for v in P])
        if pr is None:
            prev = None
            continue
        if prev is not None:
            dr.line([prev, tuple(pr)], fill=(96, 165, 250), width=2)
        prev = tuple(pr)
    out_png = os.path.join(REPO, 'tools', 'generated', 'ambrosia_bounty',
                           'hill_stereo_el.png')
    rgb.save(out_png)
    print(f'-> {out_png}')

    # mesh: rideau sur ride courbe
    edges = []
    for i in range(len(ridge) - 1):
        edges.append([list(ridge[i]), list(ridge[i + 1])])
    for i in range(0, len(ridge), 5):
        edges.append([list(ridge[i]), [ridge[i][0], ridge[i][1], Z_BASE]])
    base = [[p[0], p[1], Z_BASE] for p in ridge]
    for i in range(0, len(base) - 5, 5):
        edges.append([base[i], base[i + 5]])
    print(f'mesh: {len(edges)} aretes')
    if not args.apply:
        print('DRY-RUN (--apply pour ecrire).')
        return
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    for k in [k for k in mesh if k.startswith('Ambrosia Hill')]:
        mesh.pop(k)
    mesh['Ambrosia Hill'] = {'color': '#4ade80', 'world_edges': edges}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print('APPLIED: Ambrosia Hill (crete stereo courbe)')


if __name__ == '__main__':
    main()
