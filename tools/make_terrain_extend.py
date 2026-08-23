#!/usr/bin/env python3
"""make_terrain_extend.py — V3: completer la height map par table
couleur->altitude calibree sur toute la zone connue (idee d'Alexandre: la
vieille leak map detaillee est teintee par l'altitude — comparer la ou on a
les deux, recreer la ou on n'a que la carte).

[TERRAIN-EXTEND-V3]
  1. grille etendue au nord jusqu'a y=13000 (la carte continue au-dela du
     cadre du DDS)
  2. LUT couleur (R,G,B quantifies /8) -> mediane d'altitude, calibree sur
     TOUS les pixels connus; validation croisee 80/20 rapportee
  3. inconnu & terre -> LUT (+ lissage 60 m); eau -> -15; fondu 400 m
  4. Keys (sud) plafonnees a 4 m (bancs de sable)
COUCHE D'AFFICHAGE SEULEMENT. Reference 'connu' = terrain_hd_bak.npy
(le HD pur pre-extension). Ecrit terrain_hd_f32.npy + meta (ny etendu).
"""
import json
import os

import numpy as np
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'leak,1_old_1mpx_0820')
ZL = 4
MPP = 32.0 / (2 ** ZL)
Y_NORTH = 13000.0


def box(A, r):
    P = np.pad(A.astype(np.float64), ((r+1, r), (r+1, r)), mode='edge')
    S = P.cumsum(0).cumsum(1)
    n = 2*r + 1
    return (S[n:, n:] - S[:-n, n:] - S[n:, :-n] + S[:-n, :-n]) / (n*n)


def sample_leakold(xs, ys):
    out = np.full((len(ys), len(xs), 3), np.nan, dtype=np.float32)
    gx = (16384.0 + xs) / MPP
    gy = (16384.0 - ys) / MPP
    tx = (gx // 256).astype(int); px = (gx % 256).astype(int)
    ty = (gy // 256).astype(int); py = (gy % 256).astype(int)
    cache = {}
    for j in range(len(ys)):
        tyj = ty[j]
        for tX in np.unique(tx):
            key = (tX, tyj)
            if key not in cache:
                p = os.path.join(TILES, str(ZL), f'{ZL},{tyj},{tX}.jpg')
                cache[key] = np.asarray(Image.open(p).convert('RGB')) if os.path.exists(p) else None
            til = cache[key]
            if til is None:
                continue
            sel = tx == tX
            out[j, sel] = til[py[j], px[sel]]
        if len(cache) > 900:
            cache.clear()
    return out


def main():
    hm_dir = os.path.join(REPO, 'gtamapdata', 'heightmap')
    bak = np.load(os.path.join(hm_dir, 'terrain_hd_bak.npy'))     # HD pur
    m = json.load(open(os.path.join(hm_dir, 'terrain_hd_meta.json')))
    step, x0, y0 = m['step'], m['x0'], m['y0']
    ny0, nx = bak.shape
    add = int(round((Y_NORTH - (y0 + ny0*step)) / step))
    ny = ny0 + max(0, add)
    Z = np.full((ny, nx), -301.01, dtype=np.float32)
    Z[:ny0] = bak                                                  # rangee 0 = sud
    xs = x0 + np.arange(nx) * step
    ys = y0 + np.arange(ny) * step
    print(f'grille {nx}x{ny0} -> {nx}x{ny} (nord etendu a y={ys[-1]:.0f})', flush=True)

    C = sample_leakold(xs, ys)
    have = ~np.isnan(C[..., 0])
    print(f'couverture leak old: {have.mean()*100:.0f}%', flush=True)
    Ci = np.nan_to_num(C).astype(int)
    R, G, B = Ci[..., 0], Ci[..., 1], Ci[..., 2]
    water = have & (B > G + 12) & (B > 120)
    land = have & ~water
    key = (R//8)*32*32 + (G//8)*32 + (B//8)                        # bin couleur

    known = (Z > -300.5) & land
    kk = key[known]; zz = Z[known]
    rng = np.random.default_rng(7)
    mask80 = rng.random(len(kk)) < 0.8
    # LUT: mediane par bin (fit sur 80%)
    order = np.argsort(kk[mask80])
    ks, zs = kk[mask80][order], zz[mask80][order]
    uniq, starts = np.unique(ks, return_index=True)
    lut = {}
    for i, u in enumerate(uniq):
        seg = zs[starts[i]: starts[i+1] if i+1 < len(uniq) else len(zs)]
        if len(seg) >= 8:
            lut[int(u)] = float(np.median(seg))
    gmed = float(np.median(zz))
    print(f'LUT: {len(lut)} bins couleur (>=8 px), mediane globale {gmed:.1f} m', flush=True)
    # validation croisee sur les 20%
    tv = np.array([lut.get(int(k), gmed) for k in kk[~mask80][::7]])
    zv = zz[~mask80][::7]
    r2 = 1 - ((zv-tv)**2).sum()/((zv-zv.mean())**2).sum()
    print(f'validation 20%: n={len(zv)}, r2={r2:.3f}, rms={np.std(zv-tv):.1f} m, '
          f'mediane |err|={np.median(np.abs(zv-tv)):.1f} m', flush=True)

    # application au manquant
    fill = (Z <= -300.5) & have
    flat = key.ravel()
    pred = np.fromiter((lut.get(int(k), gmed) for k in flat), dtype=np.float64,
                       count=len(flat)).reshape(ny, nx)
    # [V5] echelle paysage: la carte peint routes/quartiers en couleurs propres
    # -> la LUT les embosse en terrasses rectangulaires si on lisse trop peu.
    pred = box(pred, 40)                                           # lissage 480 m
    ext = np.clip(pred, 1.0, 550.0)

    # [V4a] rampe cotiere: la terre monte depuis la rive (fini les murailles).
    # distance approximative a l'eau par blurs concentriques.
    wat = water.astype(np.float64)
    dist = np.full((ny, nx), 400.0)
    for r in (25, 10, 5, 2):                                       # 300..12 m
        near = box(wat, r) > 1e-6
        dist[near] = r * step
    ramp = np.clip(dist / 180.0, 0.02, 1.0)
    ext = ext * ramp                                               # plages douces
    # profondeur progressive cote eau
    dland = np.full((ny, nx), 400.0)
    lnd = (~water).astype(np.float64)
    for r in (25, 10, 5, 2):
        near = box(lnd, r) > 1e-6
        dland[near] = r * step
    depth = -np.clip(dland / 300.0, 0.03, 1.0) * 15.0
    ext = np.where(water, depth, ext)

    # [V4b] raccord a la frontiere du mesure: diffuser l'ecart (Z_vrai - ext)
    # depuis l'anneau de bord vers la zone inferee, avec decroissance ~2 km.
    known_full = (Z > -300.5)
    kf = known_full.astype(np.float64)
    ring = known_full & (box((~known_full).astype(np.float64), 8) > 1e-6)
    diff = np.where(ring, Z - ext, 0.0)
    rmask = ring.astype(np.float64)
    num = box(diff, 200); den = box(rmask, 200)
    corr = np.where(den > 1e-9, num / np.maximum(den, 1e-9), 0.0)
    dk = np.full((ny, nx), 3000.0)                                 # distance au connu
    for r in (333, 166, 66, 20):                                   # ~2000..120 m
        near = box(kf, r) > 1e-6
        dk[near] = r * step
    w = np.exp(-dk / 2500.0)                                       # [V5] raccord plus long
    ext = ext + corr * w
    ext = np.where(water & (ext > -0.5), depth, ext)               # l'eau reste l'eau
    ext = box(ext, 8)                                              # [V5] douceur finale (~100 m)

    alpha = np.clip((1.0 - box(kf, 66)) * 1.4, 0, 1)
    Z[fill] = (alpha[fill]*ext[fill] + (1-alpha[fill])*ext[fill]).astype(np.float32)
    south = (ys[:, None] < -4500) & fill & (Z > 0)
    Z[south] = np.minimum(Z[south], 4.0)
    np.save(os.path.join(hm_dir, 'terrain_hd_f32.npy'), Z)
    m['ny'] = int(ny)
    m['note'] = (m['note'].split(' | TERRAIN-EXTEND')[0]
                 + f' | TERRAIN-EXTEND-V3: manquant comble par LUT couleur->altitude '
                 f'de la leak map detaillee (validation r2={r2:.2f}, mediane |err| '
                 f'{np.median(np.abs(zv-tv)):.1f} m) — INFERE, affichage seulement; Keys plafonnees 4 m.')
    json.dump(m, open(os.path.join(hm_dir, 'terrain_hd_meta.json'), 'w'), indent=1)
    for lab, zzz in [('nord', fill & (ys[:, None] > 7300)), ('sud', fill & (ys[:, None] < -4500))]:
        if zzz.any():
            v = Z[zzz]; vl = v[v > 0]
            if len(vl):
                print(f'{lab}: {zzz.sum()} px ({(v<0).mean()*100:.0f}% eau), terre 5-95%: '
                      f'{np.percentile(vl,5):.0f}..{np.percentile(vl,95):.0f} m, max {vl.max():.0f}', flush=True)
    print('ecrit.', flush=True)


if __name__ == '__main__':
    main()
