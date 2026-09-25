"""v16fit.py <ortho_graded.png> <meta.json> <out.jpg> <cx> <cy> <half> : crop de l'ortho avec les contours V16 (batiments orange, routes magenta,
autoroutes cyan, eau bleu) dessines au sol -> juge visuellement l'accord ortho/V16. Imprime aussi un score: fraction des pixels de bord de route V16
qui tombent sur un bord (gradient fort) de l'ortho, a +-2 px."""
import sys, json, numpy as np, cv2
o = cv2.imread(sys.argv[1]); m = json.load(open(sys.argv[2])); out = sys.argv[3]; cx, cy, half = float(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6])
r = m['res']; c0 = int((cx - half - m['x0']) / r); r0 = int((m['y1'] - cy - half) / r); n = int(2 * half / r)
crop = o[r0:r0 + n, c0:c0 + n].copy(); H, W = crop.shape[:2]
V = cv2.imread('/Users/alexandreleblanc/Downloads/gtamaplib-main/maps/yanis,16svg.png')
u0, v0 = int(cx - half + 16991), int(11008 - (cy + half)); vc = V[v0:v0 + int(2 * half), u0:u0 + int(2 * half)]
vc = cv2.resize(vc, (W, H), interpolation=cv2.INTER_NEAREST)
layers = [((176, 176, 176), (0, 165, 255)), ((83, 83, 83), (255, 0, 255)), ((114, 114, 114), (255, 255, 0)), ((202, 150, 49), (255, 128, 0))]
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY); gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0); gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1); grad = np.hypot(gx, gy)
strong = (grad > np.percentile(grad[gray > 0], 75)).astype(np.uint8); strong = cv2.dilate(strong, np.ones((5, 5), np.uint8))
scores = {}
for col, draw in layers:
    mask = np.all(vc == col, axis=2).astype(np.uint8)
    if mask.sum() == 0: continue
    edges = cv2.Canny(mask * 255, 50, 150); ys, xs = np.nonzero(edges); ok = gray[ys, xs] > 0
    if ok.sum() > 50: scores[str(col)] = float(strong[ys[ok], xs[ok]].mean())
    crop[edges > 0] = draw
cv2.imwrite(out, crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
print(out, 'accord bords V16/ortho:', {k: round(v, 2) for k, v in scores.items()})
