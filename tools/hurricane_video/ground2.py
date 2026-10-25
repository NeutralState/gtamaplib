"""ground2.py — 2 m/px ground for the Vice City close-ups (V17 tiles z4), same land / ocean composite as space.py -> WORK/_ground2.npz."""
import sys, os, numpy as np, cv2
from common import REPO, WORK, TILES, DEEP, SHAL
sys.path.insert(0, os.path.join(REPO, 'tools')); from horizon_resect import HM, SC, ZX, ZY
T = os.path.join(TILES, '4')
xa, xb, ya, yb = -4600, 3600, -3600, 4200
tx0, tx1 = int((16384 + xa) // 512), int((16384 + xb) // 512); ty0, ty1 = int((16384 - yb) // 512), int((16384 - ya) // 512)
mos = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256, 3), np.uint8); miss = 0
for ty in range(ty0, ty1 + 1):
    for tx in range(tx0, tx1 + 1):
        p = os.path.join(T, '4,%d,%d.jpg' % (ty, tx)); im = cv2.imread(p) if os.path.exists(p) else None
        if im is None: miss += 1; continue
        mos[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = im
x0 = tx0 * 512 - 16384; y0 = 16384 - ty0 * 512
Z = 706.07 * HM - 301.01; A = cv2.imread(os.path.join(REPO, 'tools', 'generated', 'hurricane', 'arrival.png'), 0)
hh, ww = mos.shape[:2]; jj, ii = np.mgrid[0:hh, 0:ww]
X = x0 + ii * 2 + 1; Y = y0 - jj * 2 - 1
mu = (ZX + X * SC).astype(np.float32); mv = (ZY - Y * SC).astype(np.float32)
land = cv2.GaussianBlur(cv2.remap((A > 0).astype(np.float32), mu, mv, cv2.INTER_LINEAR, borderValue=0), (0, 0), 2.0)
depth = -cv2.remap(Z.astype(np.float32), mu, mv, cv2.INTER_LINEAR, borderValue=-80.0)
k = np.clip(depth / 14.0, 0, 1)[..., None] ** 0.6
g = (SHAL * (1 - k) + DEEP * k) * (1 - land[..., None]) + mos.astype(np.float32) * land[..., None]
np.savez(os.path.join(WORK, '_ground2.npz'), g=g.astype(np.uint8), x0=x0, y0=y0); print(mos.shape, miss, x0, y0)
