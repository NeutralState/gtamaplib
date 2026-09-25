"""mosaic.py <out.jpg> <marge_m> <a.png> <a.json> [<b.png> <b.json> ...] : mosaique de plusieurs orthos (0.5 m) posee sur la V16.
Ordre = priorite (la premiere gagne la ou elles se recouvrent). Bord fondu, petits trous inpaintes (INPAINT_M)."""
import sys, os, json, numpy as np, cv2
out, marg = sys.argv[1], float(sys.argv[2]); items = list(zip(sys.argv[3::2], sys.argv[4::2])); INP = float(os.environ.get('INPAINT_M', '12'))
metas = [json.load(open(j)) for _, j in items]; res = metas[0]['res']
X0 = min(m['x0'] for m in metas) - marg; X1 = max(m['x1'] for m in metas) + marg; Y0 = min(m['y0'] for m in metas) - marg; Y1 = max(m['y1'] for m in metas) + marg
W, H = int((X1 - X0) / res), int((Y1 - Y0) / res); print('canevas %d x %d px (%.0f x %.0f m)' % (W, H, X1 - X0, Y1 - Y0), flush=True)
acc = np.zeros((H, W, 3), np.uint8); filled = np.zeros((H, W), np.uint8)
for (png, _), m in zip(items, metas):
    o = cv2.imread(png); mask = (o.sum(axis=2) > 0).astype(np.uint8)
    holes = (1 - mask).astype(np.uint8)
    if INP > 0:
        dt = cv2.distanceTransform(holes, cv2.DIST_L2, 3); n, lab, st, cen = cv2.connectedComponentsWithStats(holes, 8); small = np.zeros_like(holes)
        for i in range(1, n):
            sel = lab == i
            if st[i, 4] >= 4 and dt[sel].max() * res < INP: small[sel] = 1
        if small.any(): o = cv2.inpaint(o, small, 5, cv2.INPAINT_TELEA); mask = (o.sum(axis=2) > 0).astype(np.uint8)
    mask = cv2.erode(cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)), np.ones((5, 5), np.uint8))
    r0, c0 = int((Y1 - m['y1']) / res), int((m['x0'] - X0) / res); h, w = o.shape[:2]
    free = (filled[r0:r0 + h, c0:c0 + w] == 0) & (mask > 0)
    acc[r0:r0 + h, c0:c0 + w][free] = o[free]; filled[r0:r0 + h, c0:c0 + w][free] = 1
    print('  %s: %.1f%% de sa grille, ajoute %d px' % (os.path.basename(png), 100 * mask.mean(), int(free.sum())), flush=True)
v = cv2.imread('/Users/alexandreleblanc/Downloads/gtamaplib-main/maps/yanis,16svg.png')[int(11008 - Y1):int(11008 - Y0), int(X0 + 16991):int(X1 + 16991)]
canvas = cv2.resize(v, (W, H), interpolation=cv2.INTER_CUBIC)
alpha = cv2.GaussianBlur(filled.astype(np.float32), (0, 0), 2.5)[..., None]
canvas = (canvas.astype(np.float32) * (1 - alpha) + acc.astype(np.float32) * alpha).astype(np.uint8)
cv2.imwrite(out, canvas, [cv2.IMWRITE_JPEG_QUALITY, 90]); json.dump({'res': res, 'x0': X0, 'x1': X1, 'y0': Y0, 'y1': Y1}, open(out.replace('.jpg', '.json'), 'w'))
print('couverture totale %.1f%% -> %s' % (100 * filled.mean(), out))
