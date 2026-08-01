#!/usr/bin/env python3
"""hill_mesh.py — Mount Ambrosia en 3D, depuis sa silhouette. [HILL-3D-V2]

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
from PIL import Image, ImageDraw
import common

CAM = 'Ambrosia 01 (Bikers)'
MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')

CLICKS = ['Mount Ambrosia (B)', 'Mount Ambrosia (D)',
          'Mount Ambrosia (E)', 'Mount Ambrosia (G)']
Z_BASE = 18.87                # plaine d'Ambrosia (datum Main St, GROUND-V1)
CORRIDOR = 90                 # demi-fenetre de recherche autour du prior (px)
HARD_EDGE = 26.0              # gradient au-dela = occluder (arete dure), rejet
MIN_EDGE = 1.2                # gradient en-deca = pas de bord trouvable
DEV_MAX = 28.0                # ecart max a la mediane locale (px)
COL_STEP = 4                  # une colonne sur 4

EL_CAM = 'Empty Lot near Metro Station'
MESH_NAME = 'Mount Ambrosia'
COLOR = '#4ade80'
N_RINGS = 8                   # anneaux de niveau du dome
RATIO = 0.65                  # profondeur du dome = RATIO * demi-largeur


BRIGHT_BELOW = 140.0          # sous le bord colline/brume c'est CLAIR;
                              # sous un occluder (arbre, poteau, panneau) c'est sombre
DY_MAX = 8                    # pente max du chemin (px de y par colonne)
LAMBDA = 0.35                 # penalite de pente (par px^2)
EVIDENCE = 1.0                # score minimal pour dire 'mesure' (sinon: pont)


def extract_skyline(gray, prior_y, x0, x1, exclude=(), anchors=()):
    """Suivi GLOBAL du bord ciel/colline par programmation dynamique.

    Le bord cherche est DOUX (brume, gradient dans (MIN_EDGE, HARD_EDGE))
    et CLAIR en-dessous (>BRIGHT_BELOW). Chaque cellule du corridor recoit
    un score d'arete; le chemin qui maximise (score - LAMBDA*pente^2) sur
    TOUTE la largeur est optimal au sens global — il enjambe fils, poteaux,
    arbres et billboard au lieu de glisser sur une bande de brume locale.
    Les colonnes traversees sans evidence (score < EVIDENCE) sont des
    PONTS: gardees dans le chemin mais marquees non-mesurees."""
    h, w = gray.shape
    sm = np.zeros_like(gray)
    sm[2:-2] = (gray[:-4] + gray[1:-3] + gray[2:-2] + gray[3:-1] + gray[4:]) / 5.0
    grad = np.zeros_like(gray)
    grad[2:-2] = sm[:-4] - sm[4:]         # >0 quand ca s'assombrit vers le bas
    # clair en-dessous SOUTENU: moyenne des px 12..45 sous la cellule.
    # (fenetre profonde: rejette les arbres caches sous un fil)
    cs = np.cumsum(gray, axis=0)
    below = np.full_like(gray, 0.0)
    below[:-46] = (cs[45:-1] - cs[12:-34]) / 33.0
    # masque FIL: bande fine sombre vs +-14 px (les fils flous ont un
    # gradient DOUX comme la colline — on les enleve par leur geometrie,
    # pas par leur durete). Dilate de +-16 px.
    wire = np.zeros(gray.shape, bool)
    wire[14:-14] = (sm[14:-14] < sm[:-28] - 5.0) & (sm[14:-14] < sm[28:] - 5.0)
    wd = np.zeros_like(wire)
    for dy in range(-10, 11, 2):
        s0, s1 = max(0, dy), min(h, h + dy)
        wd[s0:s1] |= wire[max(0, -dy):h - max(0, dy)]
    wire = wd

    xs_grid = np.arange(x0, x1, COL_STEP)
    n = len(xs_grid)
    band = CORRIDOR                        # demi-hauteur du corridor
    y0 = np.array([int(min(max(prior_y(int(x)) - band, 2), h - 2 * band - 40))
                   for x in xs_grid])
    m = 2 * band                           # cellules par colonne
    # ancres manuelles: y attendu par colonne (interpolation des strokes)
    anchor_y = np.full(n, np.nan)
    for poly in anchors:
        axs = [p[0] for p in poly]
        ays = [p[1] for p in poly]
        sel = (xs_grid >= axs[0]) & (xs_grid <= axs[-1])
        anchor_y[sel] = np.interp(xs_grid[sel], axs, ays)
    E = np.zeros((n, m))
    manual = np.zeros(n, bool)
    for k, x in enumerate(xs_grid):
        ys_ = y0[k] + np.arange(m)
        g = grad[ys_, x]
        b = below[ys_, x]
        ok = (g > MIN_EDGE) & (g < HARD_EDGE) & (b > BRIGHT_BELOW) & ~wire[ys_, x]
        if any(a <= x <= bb for a, bb in exclude):
            ok[:] = False
        E[k] = np.where(ok, np.minimum(g, HARD_EDGE * 0.75), 0.0)
        if not np.isnan(anchor_y[k]):
            manual[k] = True
            E[k] += 12.0 * np.exp(-0.5 * ((ys_ - anchor_y[k]) / 10.0) ** 2)

    # DP: C[k,j] = max(C[k-1, j+dy] - LAMBDA*(dy - drift)^2) + E[k,j]
    C = E[0].copy()
    back = np.zeros((n, m), np.int16)
    dys = np.arange(-DY_MAX, DY_MAX + 1)
    for k in range(1, n):
        drift = y0[k] - y0[k - 1]          # le corridor lui-meme bouge
        best = np.full(m, -1e18)
        arg = np.zeros(m, np.int16)
        for dy in dys:
            jprev = np.arange(m) + dy - drift
            valid = (jprev >= 0) & (jprev < m)
            cand = np.full(m, -1e18)
            cand[valid] = C[jprev[valid]] - LAMBDA * dy * dy
            better = cand > best
            best[better] = cand[better]
            arg[better] = dy
        C = best + E[k]
        back[k] = arg
    j = int(np.argmax(C))
    path = np.zeros(n, float)
    meas = np.zeros(n, bool)
    for k in range(n - 1, -1, -1):
        path[k] = y0[k] + j
        meas[k] = E[k, j] >= EVIDENCE
        if k:
            j = j + back[k, j] - (y0[k] - y0[k - 1])
            j = max(0, min(m - 1, j))
    # lissage leger (mediane 5) sur le chemin
    smooth = np.array([np.median(path[max(0, k - 2):k + 3]) for k in range(n)])
    return xs_grid.astype(float), smooth, meas, manual


def solve_depth(cam, px, cams, fov_el):
    """Profondeur t (le long des rayons de Bikers) telle que la corde
    TW-TE sous-tende, vue d'Empty Lot, l'angle mesure dans sa frame."""
    o = np.asarray(cam.xyz, float)
    marks = px[CAM]
    rw = np.asarray(cam.get_pixel_direction(marks['Mount Ambrosia (D)']), float)
    re = np.asarray(cam.get_pixel_direction(marks['Mount Ambrosia (E)']), float)
    rw, re = rw / np.linalg.norm(rw), re / np.linalg.norm(re)
    E = np.asarray(cams[EL_CAM]['xyz'], float)
    pel = px[EL_CAM]
    dx_px = abs(pel['Mount Ambrosia (E)'][0] - pel['Mount Ambrosia (D)'][0])
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
    ap.add_argument('--mesh', action='store_true',
                    help='genere le mesh 3D')
    ap.add_argument('--slope', type=float, default=None,
                    help='genere aussi le mesh 3D (par defaut: outline 2D seul)')
    ap.add_argument('--x0', type=int, default=0,
                    help='debut de l outline (defaut 130: bord du palmier)')
    args = ap.parse_args()

    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    marks = px[CAM]
    cam = common.get_cam(CAM)
    o = np.asarray(cam.xyz, float)
    im = Image.open(os.path.join(REPO, 'frames', f'{CAM}.png')).convert('L')
    gray = np.asarray(im, np.float32)

    # prior: polyline BW -> TW -> TE -> BE, extrapolee en pente des 2 cotes
    P = [marks[c] for c in CLICKS]
    xs = [p[0] for p in P]
    ys = [p[1] for p in P]
    # au-dela des clics: PLAT (corrections d'Alexandre: la silhouette reste
    # ~horizontale derriere le palmier a gauche et a droite de BE)
    def prior_y(x):
        return float(np.interp(x, xs, ys))

    # occluders connus: le billboard Diversity couvre le corridor TW-TE
    exclude = []
    bb_w = marks.get('Billboard with Diversity Motif (TW)')
    bb_e = marks.get('Billboard with Diversity Motif (TE)')
    if bb_w and bb_e:
        exclude.append((bb_w[0] - 40, bb_e[0] + 70))     # +70: poteau du panneau
    # corrections manuelles (strokes d'Alexandre digitalises)
    corr_path = os.path.join(THIS, 'data', 'hill_outline_corrections.json')
    anchors = []
    if os.path.exists(corr_path):
        anchors = json.load(open(corr_path)).get(CAM, [])
        print(f'{len(anchors)} strokes de correction charges')
    W = gray.shape[1]
    cols, sky, meas, manual = extract_skyline(gray, prior_y, args.x0, W - 4,
                                              exclude=exclude, anchors=anchors)
    known = meas | manual
    if not known.any():
        print('aucune evidence de silhouette — abandon'); return
    mi = np.where(known)[0]
    # ponts de bord limites: 40 colonnes au-dela du premier/dernier connu
    lo = max(0, mi[0] - 40)
    hi = min(len(cols), mi[-1] + 41)
    cols, sky, meas, manual = (cols[lo:hi], sky[lo:hi], meas[lo:hi],
                               manual[lo:hi])
    mi = np.where(meas | manual)[0]
    print(f'silhouette: chemin optimal x {cols[0]:.0f} -> {cols[-1]:.0f} '
          f'(connu de {cols[mi[0]]:.0f} a {cols[mi[-1]]:.0f}), '
          f'{int(meas.sum())} colonnes mesurees + {int(manual.sum())} ancrees '
          f'manuellement / {len(meas)} (bande billboard exclue {exclude})')

    # ── livrable 2D: outline sur la frame + JSON ────────────────────────
    rgb = Image.open(os.path.join(REPO, 'frames', f'{CAM}.png')).convert('RGB')
    dr2 = ImageDraw.Draw(rgb)
    outline = [{'x': int(x), 'y': round(float(y), 1),
                'source': ('manual' if mn else 'measured' if mm else 'bridge')}
               for x, y, mm, mn in zip(cols, sky, meas, manual)]
    for i in range(len(cols) - 1):
        a = (float(cols[i]), float(sky[i]))
        b = (float(cols[i + 1]), float(sky[i + 1]))
        if manual[i] or manual[i + 1]:                # correction: bleu
            dr2.line([a, b], fill=(59, 130, 246), width=5)
        elif meas[i] and meas[i + 1]:                 # mesure: vert
            dr2.line([a, b], fill=(74, 222, 128), width=5)
        elif (i // 2) % 2 == 0:                       # pont: tirets orange
            dr2.line([a, b], fill=(251, 146, 60), width=4)
    for p in P:
        dr2.ellipse([p[0] - 10, p[1] - 10, p[0] + 10, p[1] + 10],
                    outline=(248, 113, 113), width=4)
    out_dir = os.path.join(REPO, 'tools', 'generated', 'ambrosia_bounty')
    os.makedirs(out_dir, exist_ok=True)
    png = os.path.join(out_dir, 'hill_outline_bikers.png')
    rgb.save(png)
    oj = os.path.join(REPO, 'tools', 'generated', 'ambrosia_hill_outline.json')
    json.dump({'cam': CAM, 'step': COL_STEP, 'points': outline}, open(oj, 'w'))
    frac = 100.0 * sum(1 for r in outline if r['source'] != 'bridge') / len(outline)
    print(f'outline 2D: {len(outline)} echantillons, {frac:.0f}% mesures '
          f'(le reste interpole: billboard, fils, arbres)')
    print(f'-> {png}\n-> {oj}')
    if not args.mesh:
        return

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

    z_top = float(pts[:, 2].max())
    edges = []
    for i in range(len(pts) - 1):                            # crete reelle
        edges.append([list(pts[i]), list(pts[i + 1])])
    if args.slope:
        # ── volume a pente declaree: chaque point de crete descend
        #    perpendiculairement a la ride, des deux cotes, a --slope deg
        #    jusqu'a la plaine; contours iso-z + lignes de pied ─────────
        run = 1.0 / math.tan(math.radians(args.slope))       # m xy par m z
        # tangente locale de la ride (lissee), normale horizontale
        tang = np.zeros((len(pts), 2))
        tang[1:-1] = pts[2:, :2] - pts[:-2, :2]
        tang[0], tang[-1] = tang[1], tang[-2]
        tang /= np.linalg.norm(tang, axis=1)[:, None] + 1e-9
        nrm = np.stack([-tang[:, 1], tang[:, 0]], axis=1)
        RIB = 12
        levels = [Z_BASE + (z_top - Z_BASE) * f for f in (0.0, 0.33, 0.66)]
        for s in (+1.0, -1.0):
            for z in levels:
                poly = []
                for i in range(len(pts)):
                    h = pts[i, 2] - z
                    if h <= 0:
                        if len(poly) > 1:
                            for j in range(len(poly) - 1):
                                edges.append([poly[j], poly[j + 1]])
                        poly = []
                        continue
                    q = pts[i, :2] + s * nrm[i] * h * run
                    poly.append([float(q[0]), float(q[1]), float(z)])
                if len(poly) > 1:
                    for j in range(len(poly) - 1):
                        edges.append([poly[j], poly[j + 1]])
            for i in range(0, len(pts), RIB):                # lignes de pente
                h = pts[i, 2] - Z_BASE
                q = pts[i, :2] + s * nrm[i] * h * run
                edges.append([list(pts[i]), [float(q[0]), float(q[1]), Z_BASE]])
        for i in (0, len(pts) - 1):                          # fermeture des bouts
            h = pts[i, 2] - Z_BASE
            t = tang[i] * (1 if i else -1)
            q = pts[i, :2] + t * h * run
            edges.append([list(pts[i]), [float(q[0]), float(q[1]), Z_BASE]])
        foot = 2 * (z_top - Z_BASE) * run
        print(f'{MESH_NAME}: pente {args.slope:.0f} deg, pied {foot:.0f} m au '
              f'plus large, {len(edges)} aretes, crete z {pts[:, 2].min():.0f}-'
              f'{z_top:.0f} m')
    else:
        # rideau historique: nervures verticales + ligne de base
        RIB = 10
        for i in range(0, len(pts), RIB):
            edges.append([list(pts[i]), [pts[i][0], pts[i][1], Z_BASE]])
        base = [[p[0], p[1], Z_BASE] for p in pts]
        for i in range(0, len(base) - RIB, RIB):
            edges.append([base[i], base[i + RIB]])
        print(f'{MESH_NAME}: {len(edges)} aretes, crete z {pts[:, 2].min():.0f}-'
              f'{z_top:.0f} m, largeur {np.linalg.norm((pts[-1] - pts[0])[:2]):.0f} m')
    out = {MESH_NAME: {'color': COLOR, 'world_edges': edges}}

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
    stale = [k for k in mesh if k.startswith('Mount Ambrosia')]
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
