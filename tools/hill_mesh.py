#!/usr/bin/env python3
"""hill_mesh.py — Ambrosia Hill en 3D, depuis sa silhouette. [HILL-3D-V2]

UN SEUL hill, profondeur RESOLUE (plus d'hypotheses en eventail):

  1. SILHOUETTE VRAIE: extraite de la frame Bikers au subpixel (gradient
     de luminance dans un corridor autour des clics BW/TW/TE/BE), robuste
     aux occluders (billboard exclu via ses propres clics; aretes dures
     rejetees — le bord colline/ciel est DOUX a cause de la brume).
  2. PROFONDEUR PAR STEREO ANGULAIRE avec Empty Lot near Metro Station:
     les deux cams cliquent TW et TE. La corde TW-TE a une longueur fixe;
     elle sous-tend 6.5 deg depuis Bikers et ~2.5 deg depuis Empty Lot ->
     une seule profondeur satisfait les deux. d ~ 2236 m (fov EL 50),
     crete ~362 m — a 20 m de l'argument independant de continuite du
     massif Mt Mountain (le clic BW a +5.10 deg prolonge le sommet de
     Mt Mountain, 5.7 deg a 3.5 deg hors-cadre gauche), et sur le label
     AMBROSIA HILL de la map communautaire. ATTENTION: sensible a la fov
     d'Empty Lot (defaut 50, non resolue): 45 -> 1902 m, 55 -> 2614 m.
     La pose complete d'Empty Lot ou de la cam helico Kalaga raffinera.
  3. VRAI DOME, pas un rideau: anneaux de niveau (iso-z) deduits de la
     silhouette (la largeur du crest au-dessus de chaque z donne le grand
     axe de l'anneau), crete 3D reelle par-dessus.

Usage: PYTHONPATH=. python3 tools/hill_mesh.py [--depth D] [--el-fov F]
       [--apply] [--check]
"""
import argparse
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
import common

CAM = 'Ambrosia 01 (Bikers)'
MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')

CLICKS = ['Ambrosia Hill (BW)', 'Ambrosia Hill (TW)',
          'Ambrosia Hill (TE)', 'Ambrosia Hill (BE)']
Z_BASE = 18.87                # plaine d'Ambrosia (datum Main St, GROUND-V1)
CORRIDOR = 90                 # demi-fenetre de recherche autour du prior (px)
HARD_EDGE = 26.0              # gradient au-dela = occluder (arete dure), rejet
MIN_EDGE = 1.2                # gradient en-deca = pas de bord trouvable
DEV_MAX = 28.0                # ecart max a la mediane locale (px)
COL_STEP = 4                  # une colonne sur 4

EL_CAM = 'Empty Lot near Metro Station'
MESH_NAME = 'Ambrosia Hill'
COLOR = '#4ade80'
N_RINGS = 8                   # anneaux de niveau du dome
RATIO = 0.65                  # profondeur du dome = RATIO * demi-largeur


def extract_skyline(gray, prior_y, x0, x1, exclude=()):
    """Bord ciel/colline par colonne: max du gradient vertical descendant
    (ciel clair au-dessus, colline sombre dessous), dans le corridor.
    Rejette les aretes DURES (occluders), les deviations locales et les
    bandes x exclues (occluders connus, ex: billboard clique)."""
    h, w = gray.shape
    sm = np.zeros_like(gray)
    # lissage vertical leger (le bord brume est large)
    sm[2:-2] = (gray[:-4] + gray[1:-3] + gray[2:-2] + gray[3:-1] + gray[4:]) / 5.0
    cols, raw = [], []
    for x in range(x0, x1, COL_STEP):
        if any(a <= x <= b for a, b in exclude):
            continue
        yc = prior_y(x)
        a = max(3, int(yc - CORRIDOR))
        b = min(h - 3, int(yc + CORRIDOR))
        col = sm[a:b, x]
        g = col[:-3] - col[3:]            # >0 quand ca s'assombrit vers le bas
        if not len(g):
            continue
        i = int(np.argmax(g))
        if g[i] < MIN_EDGE or g[i] > HARD_EDGE:
            continue                       # invisible ou occluder
        cols.append(x)
        raw.append(a + i + 1.5)
    cols = np.array(cols, float)
    raw = np.array(raw, float)
    # rejet des deviations vs mediane glissante, puis lissage
    keep = np.ones(len(cols), bool)
    for k in range(len(cols)):
        lo, hi = max(0, k - 8), min(len(cols), k + 9)
        if abs(raw[k] - np.median(raw[lo:hi])) > DEV_MAX:
            keep[k] = False
    cols, ys = cols[keep], raw[keep]
    smooth = np.array([np.median(ys[max(0, k - 4):k + 5]) for k in range(len(ys))])
    return cols, smooth


def solve_depth(cam, px, cams, fov_el):
    """Profondeur t (le long des rayons de Bikers) telle que la corde
    TW-TE sous-tende, vue d'Empty Lot, l'angle mesure dans sa frame."""
    o = np.asarray(cam.xyz, float)
    marks = px[CAM]
    rw = np.asarray(cam.get_pixel_direction(marks['Ambrosia Hill (TW)']), float)
    re = np.asarray(cam.get_pixel_direction(marks['Ambrosia Hill (TE)']), float)
    rw, re = rw / np.linalg.norm(rw), re / np.linalg.norm(re)
    E = np.asarray(cams[EL_CAM]['xyz'], float)
    pel = px[EL_CAM]
    dx_px = abs(pel['Ambrosia Hill (TE)'][0] - pel['Ambrosia Hill (TW)'][0])
    ang_e = math.radians(dx_px * fov_el / 3840.0)

    def ang(t):
        va, vb = o + t * rw - E, o + t * re - E
        c = float(np.dot(va, vb) / np.linalg.norm(va) / np.linalg.norm(vb))
        return math.acos(max(-1.0, min(1.0, c)))

    lo, hi = 200.0, 50000.0
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        if ang(mid) < ang_e:            # l'angle vu d'EL croit avec t
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi), math.degrees(ang_e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--depth', type=float, default=None,
                    help='forcer la profondeur (m, xy) au lieu du solve Empty Lot')
    ap.add_argument('--el-fov', type=float, default=None,
                    help='hfov supposee d Empty Lot (defaut: son etat disque)')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    marks = px[CAM]
    cam = common.get_cam(CAM)
    o = np.asarray(cam.xyz, float)
    im = Image.open(os.path.join(REPO, 'frames', f'{CAM}.png')).convert('L')
    gray = np.asarray(im, np.float32)

    # prior: polyline BW -> TW -> TE -> BE
    P = [marks[c] for c in CLICKS]
    xs = [p[0] for p in P]
    ys = [p[1] for p in P]
    prior_y = lambda x: float(np.interp(x, xs, ys))
    # occluders connus: le billboard Diversity couvre le corridor TW-TE
    exclude = []
    bb_w = marks.get('Billboard with Diversity Motif (TW)')
    bb_e = marks.get('Billboard with Diversity Motif (TE)')
    if bb_w and bb_e:
        exclude.append((bb_w[0] - 40, bb_e[0] + 70))     # +70: poteau du panneau
    cols, sky = extract_skyline(gray, prior_y, int(xs[0]), int(xs[-1]),
                                exclude=exclude)
    # les 4 clics humains sont des points de confiance: on les insere
    cols = np.concatenate([cols, [float(x) for x in xs]])
    sky = np.concatenate([sky, [float(y) for y in ys]])
    order = np.argsort(cols)
    cols, sky = cols[order], sky[order]
    print(f'silhouette: {len(cols)} points entre x={xs[0]} et x={xs[-1]} '
          f'(extraction + 4 clics; bande billboard exclue {exclude})')

    # rayons + geometrie de la degenerescence
    rays = []
    for x, y in zip(cols, sky):
        d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
        rays.append(d / np.linalg.norm(d))
    rays = np.array(rays)
    elev = np.degrees(np.arcsin(rays[:, 2]))
    bear = np.degrees(np.arctan2(rays[:, 0], rays[:, 1])) % 360
    print(f'bearings {bear.min():.1f} -> {bear.max():.1f}, '
          f'elevation crete max {elev.max():.2f} deg')
    print(f'degenerescence mono-cam: z_crete = {o[2]:.1f} + d * tan(elev) '
          f'= {o[2]:.1f} + {math.tan(math.radians(elev.max())):.4f} * d\n')

    # ── profondeur: stereo angulaire Bikers x Empty Lot ─────────────────
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    fov_el = args.el_fov or cams[EL_CAM]['fov'][0]
    if args.depth:
        d = float(args.depth)
        print(f'profondeur FORCEE: d_xy = {d:.0f} m')
    else:
        t_sol, ang_e = solve_depth(cam, px, cams, fov_el)
        b0 = math.radians(float(np.median(bear)))
        d = t_sol * math.cos(math.radians(float(np.mean(elev))))
        print(f'stereo angulaire: corde TW-TE = 6.5 deg (Bikers) / '
              f'{ang_e:.2f} deg (Empty Lot, fov {fov_el:.0f} px->deg)')
        print(f'  -> d_xy = {d:.0f} m  (sensibilite: fov EL 45 -> 1902, '
              f'55 -> 2614; la pose complete d Empty Lot raffinera)')
    zc = o[2] + d * math.tan(math.radians(float(elev.max())))
    print(f'  -> z crete max = {zc:.0f} m  '
          f'(Mt Waffles 197, Mt Mountain 241, tous deux triangules)\n')

    # ── crete 3D sur le plan vertical a distance d ──────────────────────
    b0 = math.radians(float(np.median(bear)))
    n = np.array([math.sin(b0), math.cos(b0)])
    pts = []
    for r in rays:
        t = d / (r[0] * n[0] + r[1] * n[1])
        if t > 0:
            pts.append(o + t * r)
    pts = np.array(pts)

    # ── dome: anneaux de niveau deduits de la silhouette ────────────────
    edges = []
    for i in range(len(pts) - 1):                            # crete reelle
        edges.append([list(pts[i]), list(pts[i + 1])])
    z_top = float(pts[:, 2].max())
    for k in range(N_RINGS):
        z = Z_BASE + (z_top - Z_BASE) * (k / N_RINGS) ** 0.8
        above = pts[:, 2] >= z
        if above.sum() < 2:
            continue
        idx = np.where(above)[0]
        A, B = pts[idx[0]], pts[idx[-1]]                     # bord du span
        M = 0.5 * (A + B)
        u = (B - A)[:2]
        nu = float(np.linalg.norm(u))
        half = 0.5 * nu
        if half < 20:
            continue
        u = u / nu
        v = np.array([-u[1], u[0]])                          # perpendiculaire
        ring = []
        for a in np.linspace(0, 2 * math.pi, 33):
            p = M[:2] + half * math.cos(a) * u + RATIO * half * math.sin(a) * v
            ring.append([float(p[0]), float(p[1]), float(z)])
        for i in range(len(ring) - 1):
            edges.append([ring[i], ring[i + 1]])
    out = {MESH_NAME: {'color': COLOR, 'world_edges': edges}}
    print(f'{MESH_NAME}: {len(edges)} aretes, crete z {pts[:, 2].min():.0f}-'
          f'{z_top:.0f} m, {N_RINGS} anneaux de niveau, footprint '
          f'{2 * 0.5 * np.linalg.norm((pts[-1] - pts[0])[:2]):.0f} x '
          f'{2 * RATIO * 0.5 * np.linalg.norm((pts[-1] - pts[0])[:2]):.0f} m')

    if args.check:
        worst = 0.0
        for (x, y, r) in zip(cols, sky, rays):
            t = d / (r[0] * n[0] + r[1] * n[1])
            pr = cam.get_pixel([float(v) for v in (o + t * r)])
            if pr is not None:
                worst = max(worst, math.hypot(pr[0] - x, pr[1] - y))
        print(f'check aller-retour crete -> Bikers: pire ecart {worst:.2f} px')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire dans building_meshes_procedural.json).')
        return
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    stale = [k for k in mesh if k.startswith('Ambrosia Hill')]
    for k in stale:
        mesh.pop(k)                       # re-generation: on remplace les notres
    mesh.update(out)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=False)
    os.replace(tmp, MESH_PATH)
    print(f'\nAPPLIED: {list(out)} ({len(stale)} anciens remplaces)')


if __name__ == '__main__':
    main()
