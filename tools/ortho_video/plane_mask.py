"""Masque de l'avion (chase-cam): l'avion est quasi immobile dans l'image alors que le sol defile.
static = max_j |gray_k - gray_j| < seuil sur j = k±4, k±8 (meme plan), dans une boite large; + couleur vive bleu/jaune.
usage: plane_mask.py test  -> planemask_test.jpg ;  plane_mask.py all -> pmask/p%04d.png"""
import sys, os, cv2, json, numpy as np
HUD = {int(k): v for k, v in json.load(open('hud_track.json')).items()}
H, W = 1080, 1920
SHOTS = [(0, 91), (92, 312), (313, 700), (701, 719)]
cache = {}
def gray(k):
    if k not in cache:
        img = cv2.imread('vid/v%04d.jpg' % k)
        cache[k] = None if img is None else cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (0, 0), 1.5).astype(np.int16)
        if len(cache) > 40: cache.pop(next(iter(cache)))
    return cache[k]
def shot(k): return next((a, b) for a, b in SHOTS if a <= k <= b)
def mask(k, thr=7):
    if k < 92: return np.zeros((H, W), np.uint8)          # plan A: POV aile, pas d'avion devant
    a, b = shot(k); g = gray(k); mx = np.zeros((H, W), np.int16); n = 0
    for d in (-8, -4, 4, 8):
        j = min(max(k + d, a), b)
        if j == k: continue
        gj = gray(j)
        if gj is None: continue
        mx = np.maximum(mx, np.abs(g - gj)); n += 1
    gf = g.astype(np.float32); gx = cv2.Sobel(gf, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(gf, cv2.CV_32F, 0, 1, ksize=3); grad = np.hypot(gx, gy)
    # preuve de "statique": contour net (texture) ET aucun changement sur +-8 frames; le sol sans texture n'est pas une preuve
    static = ((mx < thr + 1) & (n > 0) & (grad > 40)).astype(np.uint8) * 255
    box = np.zeros((H, W), np.uint8); box[int(0.25 * H):int(0.90 * H), int(0.08 * W):int(0.62 * W)] = 255
    static &= box
    static = cv2.morphologyEx(static, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    static = cv2.morphologyEx(static, cv2.MORPH_CLOSE, np.ones((45, 45), np.uint8))
    img = cv2.imread('vid/v%04d.jpg' % k); hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); hh, sat, v = cv2.split(hsv)
    col = (((hh > 100) & (hh < 130) & (sat > 90) & (v > 50)) | ((hh > 18) & (hh < 38) & (sat > 110) & (v > 120))).astype(np.uint8) * 255
    col = cv2.morphologyEx(col, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    # blobs statiques hors HUD = fuselage; on etend en boite (les ailes fines/brumeuses ne sont pas detectees)
    kk = min(HUD, key=lambda q: abs(q - k)); nohud = static.copy()
    for nme, (x, y, w, h, s) in HUD[kk].items(): nohud[max(0, y - 20):y + h + 20, max(0, x - 20):x + w + 20] = 0
    nl, lab, st, cen = cv2.connectedComponentsWithStats(nohud)
    boxes = np.zeros((H, W), np.uint8)
    for i in range(1, nl):
        x, y, w, h, area = st[i]
        if area < 250: continue
        cx, cy = x + w / 2, y + h / 2; w2, h2 = max(w * 1.3, 120), max(h * 1.1, 60)
        boxes[int(max(0, cy - h2)):int(cy + h2), int(max(0, cx - w2)):int(cx + w2)] = 255
    m = cv2.dilate(static | col | boxes, np.ones((25, 25), np.uint8))
    return m
if sys.argv[1] == 'test':
    tiles = []
    for k in (94, 140, 200, 330, 500, 650):
        img = cv2.imread('vid/v%04d.jpg' % k); m = mask(k) > 0; vis = img.copy(); vis[m] = (vis[m] * 0.3 + np.array([0, 0, 200]) * 0.7).astype(np.uint8)
        tiles.append(cv2.resize(vis, (960, 540)))
    cv2.imwrite('planemask_test.jpg', np.vstack([np.hstack(tiles[i:i + 2]) for i in range(0, 6, 2)]), [cv2.IMWRITE_JPEG_QUALITY, 80]); print('ok test')
else:
    os.makedirs('pmask', exist_ok=True)
    for k in range(0, 720):
        cv2.imwrite('pmask/p%04d.png' % k, mask(k))
        if k % 100 == 0: print(k, flush=True)
    print('ok all')
