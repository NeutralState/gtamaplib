#!/usr/bin/env python3
"""canyon_lines.py — les lignes du canyon de Mountain Pass. [CANYON-2D-V1]

Etape 2D du canyon (meme doctrine que la colline: le 2D valide par
Alexandre AVANT toute 3D). On trace les lignes structurantes de la frame
Mount Kalaga National Park 04 (Mountain Pass) (X):

  * rim_left / rim_right : haut des parois (roche rouge vs vegetation/fond
    — le score DP combine gradient de luminance ET transition R-G, la
    signature roche/vert)
  * road_center           : la highway au fond du canyon (bande claire)
  * bridge_deck           : le tablier du pont (ligne droite, 2 bouts)

Chaque ligne = prior digitalise + snap DP dans un corridor + corrections
manuelles d'Alexandre via tools/data/canyon_corrections.json (strokes,
meme format que hill_outline_corrections).

Sortie: overlay solide (snappe) / tirets (prior tenu) sur la frame +
tools/generated/canyon_lines.json pour la future 3D (ancres de profondeur
prevues: pont triangulable helico x pass, Quarry, Billboard Delights).

Usage: PYTHONPATH=. python3 tools/canyon_lines.py
"""
import json
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
from PIL import Image, ImageDraw, ImageFont

CAM = 'Mount Kalaga National Park 04 (Mountain Pass) (X)'

# priors digitalises (pleine resolution) — la forme approximative; le DP
# snappe dans un corridor autour, les corrections d'Alexandre priment
PRIORS = {
    'rim_right': [[2100, 869], [2256, 792], [2400, 600], [2544, 380],
                  [2620, 355], [2760, 396], [3072, 340], [3400, 300],
                  [3839, 264]],
    'rim_left': [[336, 1128], [560, 1060], [792, 996], [1032, 948],
                 [1248, 720], [1344, 684], [1536, 720]],
    'road_center': [[1680, 2136], [1830, 1900], [2050, 1650], [2140, 1450],
                    [2090, 1250], [1990, 1080], [1900, 980], [1830, 890]],
    'bridge_deck': [[1572, 715], [1890, 722], [2208, 732]],
}
COLORS = {'rim_right': (248, 113, 113), 'rim_left': (251, 146, 60),
          'road_center': (125, 211, 252), 'bridge_deck': (167, 139, 250)}
CORRIDOR = 60
DY_MAX = 6
LAMBDA = 0.5
EVIDENCE = 2.0
STEP = 4


def snap(gray, rg, prior_pts, kind):
    """DP dans un corridor autour du prior. Score selon le type de ligne:
    rims = gradient lumi + transition R-G (roche rouge dessous);
    road = bande CLAIRE (asphalte) -> crete de luminance;
    bridge = arete horizontale sombre/claire."""
    xs = [p[0] for p in prior_pts]
    ys = [p[1] for p in prior_pts]
    x0, x1 = int(xs[0]), int(xs[-1])
    prior = lambda x: float(np.interp(x, xs, ys))
    h, w = gray.shape
    grid = np.arange(x0, x1, STEP)
    n = len(grid)
    m = 2 * CORRIDOR
    y0 = np.array([int(min(max(prior(int(x)) - CORRIDOR, 2), h - m - 8))
                   for x in grid])
    E = np.zeros((n, m))
    gy = np.zeros_like(gray)
    gy[2:-2] = gray[:-4] - gray[4:]          # >0: plus sombre en bas
    rgy = np.zeros_like(rg)
    rgy[2:-2] = rg[4:] - rg[:-4]             # >0: plus ROUGE en bas
    for k, x in enumerate(grid):
        ys_ = y0[k] + np.arange(m)
        if kind.startswith('rim'):
            E[k] = np.clip(np.abs(gy[ys_, x]), 0, 25) * 0.5 + \
                   np.clip(rgy[ys_, x], 0, 30)
        elif kind == 'road_center':
            band = gray[ys_, x]
            E[k] = np.clip(band - np.median(band), 0, 40)   # bande claire
        else:                                 # bridge: arete nette
            E[k] = np.clip(np.abs(gy[ys_, x]), 0, 40)
    C = E[0].copy()
    back = np.zeros((n, m), np.int16)
    for k in range(1, n):
        drift = y0[k] - y0[k - 1]
        best = np.full(m, -1e18)
        arg = np.zeros(m, np.int16)
        for dy in range(-DY_MAX, DY_MAX + 1):
            jp = np.arange(m) + dy - drift
            v = (jp >= 0) & (jp < m)
            cand = np.full(m, -1e18)
            cand[v] = C[jp[v]] - LAMBDA * dy * dy
            b = cand > best
            best[b] = cand[b]
            arg[b] = dy
        C = best + E[k]
        back[k] = arg
    j = int(np.argmax(C))
    path = np.zeros(n)
    meas = np.zeros(n, bool)
    for k in range(n - 1, -1, -1):
        path[k] = y0[k] + j
        meas[k] = E[k, j] >= EVIDENCE
        if k:
            j = max(0, min(m - 1, j + back[k, j] - (y0[k] - y0[k - 1])))
    sm = np.array([np.median(path[max(0, k - 2):k + 3]) for k in range(n)])
    return grid.astype(float), sm, meas


def main():
    im = Image.open(os.path.join(REPO, 'frames', f'{CAM}.png')).convert('RGB')
    a = np.asarray(im, np.float32)
    gray = a.mean(axis=2)
    rg = a[:, :, 0] - a[:, :, 1]              # signature roche rouge

    corr_path = os.path.join(THIS, 'data', 'canyon_corrections.json')
    corr = json.load(open(corr_path)).get(CAM, {}) if os.path.exists(corr_path) else {}

    dr = ImageDraw.Draw(im)
    F = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 30)
    out = {}
    for name, prior in PRIORS.items():
        pts = corr.get(name, prior)           # les strokes d'Alexandre priment
        if name == 'road_center':
            # la route est quasi VERTICALE dans l'image (S-curve): on la
            # suit en x(y) sur l'image transposee
            pts_t = [[p[1], p[0]] for p in reversed(pts)]
            cols, ys, meas = snap(gray.T, rg.T, pts_t, name)
            cols, ys = ys, cols               # re-swap -> (x, y)
        else:
            cols, ys, meas = snap(gray, rg, pts, name)
        col = COLORS[name]
        for i in range(len(cols) - 1):
            if meas[i] and meas[i + 1]:
                dr.line([(cols[i], ys[i]), (cols[i + 1], ys[i + 1])], fill=col, width=5)
            elif (i // 2) % 2 == 0:
                dr.line([(cols[i], ys[i]), (cols[i + 1], ys[i + 1])], fill=col, width=3)
        dr.text((cols[0] + 6, ys[0] - 40), name, fill=col, font=F,
                stroke_width=3, stroke_fill=(0, 0, 0))
        out[name] = {'x': cols.tolist(), 'y': ys.tolist(),
                     'measured': meas.tolist()}
        print(f'{name:12s}: {int(np.sum(meas))}/{len(meas)} colonnes avec evidence')
    od = os.path.join(REPO, 'tools', 'generated')
    json.dump(out, open(os.path.join(od, 'canyon_lines.json'), 'w'))
    png = os.path.join(od, 'ambrosia_bounty', 'canyon_lines_kalaga04.png')
    im.save(png)
    print(f'-> {png}')


if __name__ == '__main__':
    main()
