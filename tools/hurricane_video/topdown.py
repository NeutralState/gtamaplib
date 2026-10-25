"""topdown.py <segment B|D> [stride] [K I] — HURRICANE video top-down shots on the V17 map -> WORK/top/NNNNNN.jpg + meta_<seg>[_I].json.
B (11.0-23.0 s): under the storm over Vice City, the surge floods the streets 0 -> 7.15 m (scud, cloud shadows, lightning).
D (31.0-57.2 s): the storm passes, the sea keeps rising 20 -> 404 m: zoom out to all of Leonida, then in on Mount Kalaga.
Water: every cell the connected sea reaches at the level (arrival_hi.npy), coloured by depth over the game heightmap, the map
showing through (drowned streets stay visible), foam on the moving waterline. K I: render chunk I of K (run at most 2 at once:
8 GB of RAM)."""
import sys, os, json, numpy as np, cv2
from common import REPO, WORK, W, H, FPS, DEEP, tile_noise, ss, ease, lerp, elerp
sys.path.insert(0, os.path.join(REPO, 'tools')); from horizon_resect import HM, SC, ZX, ZY
SEG = sys.argv[1]; STRIDE = int(sys.argv[2]) if len(sys.argv) > 2 else 1
OUT = os.path.join(WORK, 'top'); os.makedirs(OUT, exist_ok=True)
z4 = np.load(os.path.join(WORK, '_ground.npz')); G4, G4X, G4Y = z4['g'], float(z4['x0']), float(z4['y0'])
z2 = np.load(os.path.join(WORK, '_ground2.npz')); G2, G2X, G2Y = z2['g'], float(z2['x0']), float(z2['y0'])
PYR = [G4]
for _ in range(4): PYR.append(cv2.pyrDown(PYR[-1]))
A = np.load(os.path.join(WORK, 'arrival_hi.npy')); A = np.where(np.isfinite(A), A, 1e4).astype(np.float32)
Z = (706.07 * HM - 301.01).astype(np.float32)
MURK = np.array([150, 138, 70], np.float32); DROWN = np.array([120, 70, 28], np.float32)
NZ = [tile_noise(1024, 64, s) for s in range(3)]
def fbm(u, v, oct=4, seed=0):
    s = np.zeros(u.shape, np.float32); a = 0.5; N = NZ[seed]; n = N.shape[0]
    for i in range(oct):
        s += a * cv2.remap(N, ((u * 16) % n).astype(np.float32), ((v * 16) % n).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        u = u * 2.03 + 0.37; v = v * 2.03 + 0.21; a *= 0.5
    return s / 0.94
def fbm_h(X, Y, oct, seed):
    """fbm on a half-resolution grid, upsampled (the noise is smooth: 4x cheaper, same look)"""
    return cv2.resize(fbm(X[::2, ::2], Y[::2, ::2], oct, seed), (X.shape[1], X.shape[0]), interpolation=cv2.INTER_LINEAR)
STRIKES_B = [14.0, 18.4, 21.7]
def cam(T):
    """center x, y, metres per pixel, sea level, storm 0..1"""
    if SEG == 'B':
        k = ease((T - 11.0) / 12.0)
        return lerp(-800, -620, k), lerp(300, 240, k), elerp(1.75, 3.3, k), 7.146 * ease((T - 11.6) / 11.2) ** 1.15, 1.0
    zo = ease((T - 31.0) / 6.0); zi = ease((T - 49.0) / 5.5)
    cx = lerp(lerp(-620, -1700, zo), -3432, zi); cy = lerp(lerp(240, 900, zo), 6372, zi)
    mpp = elerp(elerp(3.3, 13.8, zo), 1.7, zi)
    u = ease((T - 31.3) / 23.7); lv = 20.0 * (402.2 / 20.0) ** u
    if T > 56.2: lv = 402.2 + (404.5 - 402.2) * ease((T - 56.2) / 0.7)
    return cx, cy, mpp, lv, 1.0 - ease((T - 31.0) / 3.0)
jj, ii = np.mgrid[0:H, 0:W].astype(np.float32)
def sample(img, x0, y0, res, X, Y, border):
    return cv2.remap(img, ((X - x0) / res).astype(np.float32), ((y0 - Y) / res).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=border)
def render(n):
    T = n / FPS; cx, cy, mpp, L, storm = cam(T)
    X = cx + (ii - W / 2) * mpp; Y = cy - (jj - H / 2) * mpp
    lvl = int(np.clip(np.floor(np.log2(max(mpp / 4.0, 1.0))), 0, len(PYR) - 1)); f = 2 ** lvl
    img = sample(PYR[lvl], G4X, G4Y, 4.0 * f, X, Y, tuple(int(v) for v in DEEP)).astype(np.float32)
    if mpp < 4.0:
        g2 = sample(G2, G2X, G2Y, 2.0, X, Y, (0, 0, 0)).astype(np.float32)
        inside = ((X > G2X + 40) & (X < G2X + G2.shape[1] * 2 - 40) & (Y < G2Y - 40) & (Y > G2Y - G2.shape[0] * 2 + 40)).astype(np.float32)[..., None]
        img = g2 * inside + img * (1 - inside); del g2
    cu = (ZX + X * SC).astype(np.float32); cv = (ZY - Y * SC).astype(np.float32)
    arr = cv2.remap(A, cu, cv, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
    z = cv2.remap(Z, cu, cv, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=-80.0)
    if L > 0.02:
        landc = ss(0.02, 0.15, arr)                                   # 0 = open sea (already drawn as sea on the ground)
        wet = np.clip((L - arr) / max(0.35, L * 0.004) + 0.5, 0, 1) * landc
        depth = np.maximum(L - z, 0)
        k = np.clip(depth / 9.0, 0, 1) ** 0.7
        wc = MURK * (1 - k[..., None]) + DROWN * k[..., None]
        wc = wc * (1.0 + 0.10 * (fbm_h(X / 90.0 + T * 0.35, Y / 90.0 - T * 0.12, 3, 1) - 0.5))[..., None]
        a = (wet * (0.50 + 0.30 * k))[..., None]                     # drowned streets stay visible under the water
        img = img * (1 - a) + wc * a
        sd = (1 - landc) * ss(0.5, 25.0, L) * (1 - np.clip(-z / 14.0, 0, 1)) * 0.85   # the sea's shallow banks darken as it rises
        img = img * (1 - sd[..., None]) + DEEP * sd[..., None]
        band = wet * np.clip(1 - (L - arr) / max(0.6, L * 0.006), 0, 1)
        foam = band * ss(0.40, 0.70, fbm_h(X / 25.0 + T * 0.5, Y / 25.0, 3, 2))
        img = img * (1 - 0.75 * foam[..., None]) + 245 * 0.75 * foam[..., None]
    if storm > 0.01:
        sc = fbm_h(X / 900.0 + T * 0.09, Y / 900.0 + T * 0.05, 4, 0)
        shadow = ss(0.45, 0.75, fbm_h((X + 600) / 900.0 + T * 0.09, (Y - 400) / 900.0 + T * 0.05, 4, 0))
        img *= (1 - 0.35 * storm * shadow)[..., None]
        img = img * (1 - 0.30 * storm) + np.array([70, 62, 58], np.float32) * 0.30 * storm * (img.mean(axis=2, keepdims=True) / 128.0)
        scud = ss(0.50, 0.85, sc) * storm
        img = img * (1 - 0.5 * scud[..., None]) + np.array([150, 150, 152], np.float32) * 0.5 * scud[..., None]
        fl = 0.0
        for s in STRIKES_B:
            d = T - s
            if 0 <= d < 0.36: fl = max(fl, 1.0 if d < 0.08 else 0.25 if d < 0.16 else 0.8 if d < 0.24 else 0.2)
        if fl > 0: img = img * (1 + 0.28 * fl * storm) + 14 * fl * storm
    q = ((ii - W / 2) / W) ** 2 + ((jj - H / 2) / H) ** 2; img *= (1 - 0.32 * q)[..., None]
    cv2.imwrite(os.path.join(OUT, '%06d.jpg' % n), np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 93])
    return dict(n=n, T=T, level=float(L), mpp=float(mpp), cx=float(cx), cy=float(cy), storm=float(storm))
if __name__ == '__main__':
    import time
    cv2.setNumThreads(2)
    t0s, t1s = (11.0, 23.0) if SEG == 'B' else (31.0, 57.2)
    todo = list(range(int(round(t0s * FPS)), int(round(t1s * FPS)), STRIDE))
    tagc = ''
    if len(sys.argv) > 4: K, I = int(sys.argv[3]), int(sys.argv[4]); todo = todo[I::K]; tagc = '_%d' % I
    meta = []; tt = time.time()
    for k, n in enumerate(todo):
        meta.append(render(n))
        if k % 60 == 0: print(SEG, k, '/', len(todo), '%.2f s/frame' % ((time.time() - tt) / (k + 1)), flush=True)
    json.dump(meta, open(os.path.join(OUT, 'meta_%s%s.json' % (SEG, tagc)), 'w')); print('done', SEG, len(todo))
