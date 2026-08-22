#!/usr/bin/env python3
"""make_terrain_hd.py — height map HD par upsampling guide par la leak map.

[TERRAIN-HD-GUIDED-V1] La height map (DDS L16) est la VERITE mais a 12.8 m/px;
la clean map leak (5.65 m/px) contient du relief PEINT plus fin (parois de
canyon, ravines). On transfere ses hautes frequences dans la height map la ou
elles correlent localement avec le vrai relief:

  1. Z_base  = height map upsamplee bicubique a 6 m
  2. L_hp    = hautes frequences de la luminance leak (L - boxblur)
  3. beta    = regression locale Z_hp ~ L_hp par fenetres (240 m), fiabilisee
               par la correlation locale r (fondu 0 sous |r|<0.25)
  4. Z_hd    = Z_base + clip(beta * L_hp, -5, +5)   [0 sur l'eau/hors leak]

COUCHE D'AFFICHAGE SEULEMENT: relief infere du dessin de la carte, pas mesure.
Toute calibration (horizon_resect, players HUD...) reste sur le DDS pur.

Sortie: gtamapdata/heightmap/terrain_hd_f32.npy + terrain_hd_meta.json
"""
import json
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)

SC, ZX, ZY = 0.083188297, 1108.532, 938.091      # georef rlx du DDS
WX0, WY0, MPP = -10740.0, 9736.0, 5.65           # georef leak clean map
STEP = 6.0                                        # m/px de la grille HD
AMP = 5.0                                         # bornes du detail ajoute (m)
WIN = 20                                          # fenetre regression (px HD = 120 m rayon)


def box(A, r):
    """moyenne locale par fenetre carree (2r+1), via cumsum — O(1)/px."""
    A = A.astype(np.float64)
    P = np.pad(A, ((r + 1, r), (r + 1, r)), mode='edge')
    S = P.cumsum(0).cumsum(1)
    n = 2 * r + 1
    return (S[n:, n:] - S[:-n, n:] - S[n:, :-n] + S[:-n, :-n]) / (n * n)


def catrom_up(Z, U, V):
    """Catmull-Rom separable de Z aux coordonnees pixel (U 1D, V 1D)."""
    def w(t):
        return (-0.5*t**3 + t**2 - 0.5*t, 1.5*t**3 - 2.5*t**2 + 1.0,
                -1.5*t**3 + 2.0*t**2 + 0.5*t, 0.5*t**3 - 0.5*t**2)
    U = np.clip(U, 1, Z.shape[1] - 2.001); V = np.clip(V, 1, Z.shape[0] - 2.001)
    iu = U.astype(int); iv = V.astype(int)
    wu = w((U - iu)[None, :]); wv = w((V - iv)[:, None])
    out = np.zeros((len(V), len(U)), np.float64)
    for b in range(4):
        rr = np.clip(iv + b - 1, 0, Z.shape[0] - 1)
        row = np.zeros_like(out)
        for a in range(4):
            cc = np.clip(iu + a - 1, 0, Z.shape[1] - 1)
            row += wu[a] * Z[rr][:, cc]
        out += wv[b] * row
    return out


def main():
    d = open(os.path.join(REPO, 'gtamapdata', 'heightmap', 'GTA6HeightMap_L16.dds'), 'rb').read()
    Z = (np.frombuffer(d[128:128 + 1536*1748*2], dtype='<u2')
         .reshape(1748, 1536).astype(np.float64) / 65535.0) * 706.07 - 301.01
    print('height map chargee', flush=True)

    # grille HD en monde: emprise du DDS
    x0, x1 = (0 - ZX)/SC, (1536 - ZX)/SC
    y0, y1 = (ZY - 1748)/SC, ZY/SC
    xs = np.arange(x0, x1, STEP)
    ys = np.arange(y0, y1, STEP)          # sud -> nord
    print(f'grille HD {len(xs)}x{len(ys)} @ {STEP} m', flush=True)

    Zb = catrom_up(Z, ZX + xs*SC, ZY - ys[::-1]*SC)[::-1]   # rangee 0 = sud
    print('Z_base upsample ok', flush=True)

    leak = np.asarray(Image.open(os.path.expanduser('~/Downloads/fullmap.png'))
                      .convert('L')).astype(np.float64)
    lu = (xs - WX0)/MPP
    lv = (WY0 - ys[::-1])/MPP
    inside = ((lu >= 1) & (lu < leak.shape[1]-2))[None, :] & \
             ((lv >= 1) & (lv < leak.shape[0]-2))[:, None]
    inside = inside[::-1]
    L = catrom_up(leak, np.clip(lu, 1, leak.shape[1]-2.01),
                  np.clip(lv, 1, leak.shape[0]-2.01))[::-1]
    print('leak reechantillonnee ok', flush=True)

    r_hp = 4                               # ~24 m: micro-relief
    Lh = L - box(L, r_hp)
    Zh = Zb - box(Zb, r_hp)
    # regression locale Zh ~ Lh (fenetre WIN px) + fiabilite par correlation
    mLZ = box(Lh*Zh, WIN); mLL = box(Lh*Lh, WIN); mZZ = box(Zh*Zh, WIN)
    beta = mLZ / (mLL + 1e-6)
    r = mLZ / np.sqrt((mLL + 1e-6) * (mZZ + 1e-6))
    conf = np.clip((np.abs(r) - 0.25) / 0.25, 0, 1)         # fondu 0.25..0.50
    detail = np.clip(beta * Lh, -AMP, AMP) * conf
    detail[~inside] = 0.0
    detail[Zb < 0.5] = 0.0                 # jamais sur l'eau / plages basses
    Zhd = (Zb + detail).astype(np.float32)
    print(f'detail: ampl mediane {np.median(np.abs(detail[detail!=0])):.2f} m, '
          f'max {np.abs(detail).max():.1f} m, couverture {(detail!=0).mean()*100:.0f}%', flush=True)

    out = os.path.join(REPO, 'gtamapdata', 'heightmap')
    np.save(os.path.join(out, 'terrain_hd_f32.npy'), Zhd)
    json.dump({'x0': float(xs[0]), 'y0': float(ys[0]), 'step': STEP,
               'nx': len(xs), 'ny': len(ys),
               'note': 'DISPLAY ONLY — detail infere de la clean map leak '
                       '(TERRAIN-HD-GUIDED-V1); calibrations sur le DDS pur.'},
              open(os.path.join(out, 'terrain_hd_meta.json'), 'w'), indent=1)
    print('ecrit: terrain_hd_f32.npy +', f'{Zhd.nbytes/1e6:.0f} MB', flush=True)


if __name__ == '__main__':
    main()
