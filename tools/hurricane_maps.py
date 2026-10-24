"""hurricane_maps.py — HURRICANE-V1 flood maps: the storm-surge extent (tools/hurricane_surge.py arrival map) painted level by
level over the V17 base map (gtadb yanis,17 tiles, z5 = 1 m/px, local cache only). Writes tools/generated/hurricane/map_<area>.jpg."""
import os, sys, numpy as np, cv2
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS)
from horizon_resect import SC, ZX, ZY
TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,17', '5')
OUT = os.path.join(THIS, 'generated', 'hurricane')
AREAS = {'vice_city': (-1600, -1700, 2600, 3200), 'keys': (-9000, -9000, 0, -3000)}
COLS = {1.0: (255, 220, 130), 2.0: (255, 165, 70), 3.0: (235, 95, 45), 4.0: (175, 30, 40)}


def crop(x0, y0, x1, y1):
    X0, X1, Y0, Y1 = 16384 + x0, 16384 + x1, 16384 - y1, 16384 - y0
    tx0, tx1, ty0, ty1 = int(X0 // 256), int(X1 // 256), int(Y0 // 256), int(Y1 // 256)
    out = np.full(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256, 3), 230, np.uint8)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            p = os.path.join(TILES, '5,%d,%d.jpg' % (ty, tx)); t = cv2.imread(p) if os.path.exists(p) else None
            if t is not None: out[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = t
    ox, oy = int(X0 - tx0 * 256), int(Y0 - ty0 * 256)
    return out[oy:oy + int(Y1 - Y0), ox:ox + int(X1 - X0)]


def main(scale=0.45):
    A = cv2.imread(os.path.join(OUT, 'arrival.png'), 0).astype(float) * 0.025
    for name, (x0, y0, x1, y1) in AREAS.items():
        I = crop(x0, y0, x1, y1).astype(np.float32); H, W = I.shape[:2]
        ys, xs = np.mgrid[0:H, 0:W]
        u = np.clip(np.round(ZX + (x0 + xs) * SC).astype(int), 0, A.shape[1] - 1); v = np.clip(np.round(ZY - (y1 - ys) * SC).astype(int), 0, A.shape[0] - 1)
        arr = A[v, u]; out = I.copy()
        for lv in sorted(COLS, reverse=True):
            m = (arr > 0.001) & (arr <= lv); out[m] = out[m] * 0.35 + np.array(COLS[lv][::-1], np.float32) * 0.65
        out = cv2.resize(out.astype(np.uint8), None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        for i, (lv, c) in enumerate(sorted(COLS.items())):
            cv2.rectangle(out, (20, 20 + i * 34), (50, 46 + i * 34), c[::-1], -1); cv2.putText(out, 'surge +%.0f m' % lv, (60, 42 + i * 34), 0, 0.8, (20, 20, 20), 2)
        cv2.imwrite(os.path.join(OUT, 'map_%s.jpg' % name), out, [cv2.IMWRITE_JPEG_QUALITY, 90]); print(name, out.shape)


if __name__ == '__main__':
    main()
