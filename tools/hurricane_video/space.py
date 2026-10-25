"""space.py [stride] — HURRICANE video opening (0-11 s): Leonida seen from orbit (nadir), a hurricane spiral crossing the sea toward
the map, then a dive through the cloud deck (clouds at 3.5 km scale faster than the ground: parallax) ending in a white-out.
Ground: V17 tiles z3 (4 m/px) for land (land = arrival map > 0, i.e. not open sea), ocean coloured from the game heightmap depth.
Clouds: log-spiral rain bands, central dense overcast, ragged clear eye, swirled fbm; lit by the sun, with their shadow on the ground.
Frames -> WORK/space/NNNNNN.jpg; the ground composite is cached in WORK/_ground.npz (also used by topdown.py)."""
import sys, os, numpy as np, cv2
from common import REPO, WORK, TILES, W, H, FPS, DEEP, SHAL, SUF, frames_override, tile_noise, ss, ease, lerp
STRIDE = int(sys.argv[1]) if len(sys.argv) > 1 else 1
OUT = os.path.join(WORK, 'space' + SUF); os.makedirs(OUT, exist_ok=True)
DUR = 11.0; CACHE = os.path.join(WORK, '_ground.npz')
def build_ground():
    if os.path.exists(CACHE):
        z = np.load(CACHE); return z['g'], float(z['x0']), float(z['y0'])
    T = os.path.join(TILES, '3'); tx0, tx1, ty0, ty1 = 5, 25, 5, 24
    mos = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256, 3), np.uint8)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            p = os.path.join(T, '3,%d,%d.jpg' % (ty, tx)); im = cv2.imread(p) if os.path.exists(p) else None
            if im is not None: mos[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = im
    x0 = tx0 * 256 * 4 - 16384; y0 = 16384 - ty0 * 256 * 4          # world coords of the mosaic's top-left corner (4 m/px)
    sys.path.insert(0, os.path.join(REPO, 'tools'))
    from horizon_resect import HM, SC, ZX, ZY
    Z = 706.07 * HM - 301.01
    A = cv2.imread(os.path.join(REPO, 'tools', 'generated', 'hurricane', 'arrival.png'), 0)
    hh, ww = mos.shape[:2]; jj, ii = np.mgrid[0:hh, 0:ww]
    X = x0 + ii * 4 + 2; Y = y0 - jj * 4 - 2
    mu = (ZX + X * SC).astype(np.float32); mv = (ZY - Y * SC).astype(np.float32)
    land = cv2.remap((A > 0).astype(np.float32), mu, mv, cv2.INTER_LINEAR, borderValue=0)
    depth = -cv2.remap(Z.astype(np.float32), mu, mv, cv2.INTER_LINEAR, borderValue=-80.0)
    land = cv2.GaussianBlur(land, (0, 0), 1.2)
    k = np.clip(depth / 14.0, 0, 1)[..., None] ** 0.6
    sea = SHAL * (1 - k) + DEEP * k
    g = sea * (1 - land[..., None]) + mos.astype(np.float32) * land[..., None]
    e = np.minimum(np.minimum(ii, ww - 1 - ii), np.minimum(jj, hh - 1 - jj)).astype(np.float32)
    f = np.clip(e / 120.0, 0, 1)[..., None]; g = g * f + DEEP * (1 - f)      # the mosaic edge melts into the deep ocean
    g = g.astype(np.uint8); np.savez(CACHE, g=g, x0=x0, y0=y0); return g, float(x0), float(y0)
G, GX0, GY0 = build_ground()
PYR = [G]
for _ in range(5): PYR.append(cv2.pyrDown(PYR[-1]))
NZ = [tile_noise(2048, 128, s) for s in range(3)]
CELL = 16.0                                        # texture px per noise cell: u, v are in noise cells
def fbm(u, v, oct=5, seed=0):
    s = np.zeros(u.shape, np.float32); a = 0.5; N = NZ[seed]; n = N.shape[0]
    for i in range(oct):
        s += a * cv2.remap(N, ((u * CELL) % n).astype(np.float32), ((v * CELL) % n).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        u = u * 2.03 + 0.37; v = v * 2.03 + 0.21; a *= 0.5
    return s / 0.97
def rot(x, y, a): c, s = np.cos(a), np.sin(a); return c * x - s * y, s * x + c * y
def density(qx, qy, R, eye, rotv):
    r = np.sqrt(qx * qx + qy * qy) + 1e-3; rn = r / R; lr = np.log(np.maximum(r, 1.0) / eye)
    spin = rotv * (0.65 + 0.35 * (eye * 3.0 / np.maximum(r, eye * 3.0)) ** 0.5)      # mild shear: strong shear winds the noise into rings
    rx, ry = rot(qx, qy, -spin)
    sx, sy = rot(rx, ry, 1.3 * np.log(np.maximum(r, 1.0) / R))
    n = fbm(sx / R * 6.0, sy / R * 6.0, 5, 0); n2 = fbm(sx / R * 18.0 + 3.3, sy / R * 18.0, 5, 1); n3 = fbm(sx / R * 55.0, sy / R * 55.0 + 7.6, 4, 2)
    th = np.arctan2(ry, rx)
    arms = ss(0.30, 0.80, 0.5 + 0.5 * np.cos(2.0 * th - 5.0 * lr + (n - 0.5) * 4.0))
    cdo = 1.0 - ss(eye * 2.5, R * 0.30, r + (n - 0.5) * R * 0.12)
    eyeC = ss(eye * 0.75, eye * 1.25, r + (n2 - 0.5) * eye * 0.9)
    env = 1.0 - ss(0.55, 1.0, rn + (n - 0.5) * 0.35)
    d = eyeC * env * (1.10 * cdo + 0.80 * arms * ss(0.12, 0.35, rn) + 0.50 * (n2 - 0.5) + 0.35 * (n3 - 0.5))
    return ss(0.12, 0.90, d)
CLOUD_Z = 3500.0; FOVK = 0.90                       # ground width = altitude * FOVK
def state(T):
    if T < 6.0: h = lerp(95000, 72000, ease(T / 6.0))
    else: h = float(np.exp(lerp(np.log(72000), np.log(3650), ease((T - 6.0) / 4.8) ** 0.85)))
    c = (lerp(-1500, -800, ease((T - 5.0) / 5.5)), lerp(-1500, 300, ease((T - 5.0) / 5.5)))
    sc = (lerp(38000, 8000, ease(T / 8.5)), lerp(-34000, -6500, ease(T / 8.5)))
    return h, c, sc, 0.45 * T
jj, ii = np.mgrid[0:H, 0:W].astype(np.float32)
def render(n):
    T = n / FPS; h, (cx, cy), (scx, scy), rotv = state(T)
    mpp = h * FOVK / W
    lvl = int(np.clip(np.floor(np.log2(max(mpp / 4.0, 1.0))), 0, len(PYR) - 1)); P = PYR[lvl]; f = 2 ** lvl
    X = cx + (ii - W / 2) * mpp; Y = cy - (jj - H / 2) * mpp
    gu = ((X - GX0) / 4.0) / f; gv = ((GY0 - Y) / 4.0) / f
    img = cv2.remap(P, gu.astype(np.float32), gv.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=tuple(int(v) for v in DEEP)).astype(np.float32)
    cm = mpp * (h - CLOUD_Z) / h                       # the deck at CLOUD_Z looks h / (h - Z) times bigger
    Xc = cx + (ii - W / 2) * cm; Yc = cy - (jj - H / 2) * cm
    R, eye = 38000.0, 1900.0
    d = density(Xc - scx, Yc - scy, R, eye, rotv)
    sh_off = CLOUD_Z / np.tan(np.radians(40)); ox, oy = np.sin(np.radians(150)) * sh_off, np.cos(np.radians(150)) * sh_off
    ds = cv2.resize(density((cx + (ii[::4, ::4] - W / 2) * mpp + ox) - scx, (cy - (jj[::4, ::4] - H / 2) * mpp + oy) - scy, R, eye, rotv), (W, H))
    img *= (1 - 0.45 * ds)[..., None]
    gy, gx = np.gradient(d); lit = np.clip(0.80 + 2.2 * (gx * 0.5 - gy * 0.8) / max(cm / 40.0, 0.25), 0.55, 1.15)
    ccol = (np.array([0.50, 0.53, 0.57])[None, None, :] * (1 - d[..., None] ** 0.6) + np.array([0.98, 0.97, 0.96])[None, None, :] * d[..., None] ** 0.6) * 255 * lit[..., None]
    a = np.clip(d * 1.15, 0, 1)[..., None]
    img = img * (1 - a) + ccol * a
    haze = np.clip((h - 20000) / 130000, 0, 1) * 0.18; img = img * (1 - haze) + np.array([235, 200, 160]) * haze
    q = ((ii - W / 2) / W) ** 2 + ((jj - H / 2) / H) ** 2; img *= (1 - 0.35 * q)[..., None]
    wo = ease((T - 10.1) / 0.8); img = img * (1 - wo) + 238 * wo
    cv2.imwrite(os.path.join(OUT, '%06d.jpg' % n), np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 93])
if __name__ == '__main__':
    import time
    cv2.setNumThreads(3)
    N = int(DUR * FPS); todo = frames_override([n for n in range(0, N, STRIDE) if not os.path.exists(os.path.join(OUT, '%06d.jpg' % n))])
    t0 = time.time()
    for k, n in enumerate(todo):
        render(n)
        if k % 60 == 0: print(k, '/', len(todo), '%.2f s/frame' % ((time.time() - t0) / (k + 1)), flush=True)
    print('done', len(todo))
