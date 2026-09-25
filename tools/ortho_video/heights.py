"""heights.py <poses.json> <x0> <x1> <y0> <y1> <out.json> [--debug N]
Hauteur de chaque silhouette V16 (gris 176) de l'emprise: pour h de 2 a HMAX m, on projette le toit (polygone a z=sol+h)
et les aretes verticales des coins dans chaque frame qui voit le batiment, et on mesure l'energie de contour (gradient)
le long de ces aretes. h* = argmax de la somme des scores normalises par frame; confiance = pic / mediane.
Sortie: {id: {cx, cy, area, h, conf, nframes, poly}}"""
import sys, os, json, numpy as np, cv2
sys.path.insert(0, '/Users/alexandreleblanc/Downloads/gtamaplib-main'); sys.path.insert(0, '/Users/alexandreleblanc/Downloads/gtamaplib-main/tools')
import gtamaplib as G, horizon_resect as HR
sys.path.insert(0, '/private/tmp/claude-501/-Users-alexandreleblanc-Downloads-gtamaplib-main/b03356f6-af67-4086-b7cc-fad47ae03b07/scratchpad'); import vo
from scipy.spatial.transform import Rotation as R
poses_f, x0, x1, y0, y1, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), sys.argv[6]
DEBUG = int(sys.argv[sys.argv.index('--debug') + 1]) if '--debug' in sys.argv else 0
W, H = 1920, 1080; HMAX = float(os.environ.get('HMAX', '120')); GRAZMIN = float(os.environ.get('GRAZMIN', '0.12')); FR = os.environ.get('FRAMES'); MINAREA = float(os.environ.get('MINAREA', '150')); DMAX = float(os.environ.get('DMAX', '1000'))
poses = {int(k): v for k, v in json.load(open(poses_f)).items()}
if FR: a_, b_ = [int(x) for x in FR.split(',')]; poses = {k: v for k, v in poses.items() if a_ <= k <= b_}
frames = sorted(poses)
ROT = {k: R.from_quat(G.get_q(list(poses[k][1]))) for k in frames}
def proj(k, X):
    p = poses[k]; hf = p[4] if len(p) > 4 else 89.677; d = ROT[k].inv().apply(np.atleast_2d(X) - np.array(p[0])); front = d[:, 1] > 1
    th = np.tan(np.radians(hf) / 2); tv = th * H / W; y = np.where(front, d[:, 1], 1.0)
    return ((d[:, 0] / y) / th + 1) * 0.5 * W - 0.5, (1 - ((d[:, 2] / y) / tv + 1) * 0.5) * H - 0.5, front
# ---- silhouettes V16
V = cv2.imread('/Users/alexandreleblanc/Downloads/gtamaplib-main/maps/yanis,16svg.png')
u0, v0 = int(x0 + 16991), int(11008 - y1); u1, v1 = int(x1 + 16991), int(11008 - y0)
crop = V[v0:v1, u0:u1]; mask = np.all(crop == (176, 176, 176), axis=2).astype(np.uint8)
n, lab, st, cen = cv2.connectedComponentsWithStats(mask, 8)
cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
builds = []
for c in cnts:
    a = cv2.contourArea(c)
    if a < MINAREA: continue
    poly = cv2.approxPolyDP(c, 1.2, True).reshape(-1, 2).astype(float)
    wx = poly[:, 0] + u0 - 16991 + 0.5; wy = 11008 - (poly[:, 1] + v0) - 0.5
    builds.append(dict(poly=np.c_[wx, wy], area=float(a), cx=float(wx.mean()), cy=float(wy.mean())))
print('%d silhouettes >= %.0f m2 dans l emprise' % (len(builds), MINAREA), flush=True)
# ---- gradient des frames (cache)
GC = {}
def grad(k):
    if k not in GC:
        g = cv2.imread('vid/v%04d.jpg' % k, 0)
        if g is None: GC[k] = None
        else:
            g = cv2.GaussianBlur(g, (0, 0), 1.2).astype(np.float32); gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
            m = np.sqrt(gx * gx + gy * gy); GC[k] = m / (np.percentile(m, 99) + 1e-6)
        if len(GC) > 60: GC.pop(next(iter(GC)))
    return GC[k]
def sample_edges(P2):
    """points echantillonnes le long d'un polyligne (N,2) image, tous les ~2 px"""
    out = []
    for a, b in zip(P2[:-1], P2[1:]):
        L = np.hypot(*(b - a)); m = max(2, int(L / 2)); out.append(a[None, :] + (b - a)[None, :] * np.linspace(0, 1, m)[:, None])
    return np.concatenate(out) if out else np.zeros((0, 2))
def score_frame(k, poly, g0, hs):
    """score(h) = z(energie du toit projete) + z(marche des aretes verticales: energie dans [h-D,h] moins [h,h+D]).
    None si le batiment est hors image / trop petit (< 8 px de large)."""
    Gm = grad(k)
    if Gm is None: return None
    ring = np.r_[poly, poly[:1]]; bx, by, fb = proj(k, np.c_[poly, np.full(len(poly), g0)])
    if not fb.all() or (bx.max() - bx.min()) < 8: return None
    D = 4.0
    def energy_pts(pts):
        ok = (pts[:, 0] >= 1) & (pts[:, 0] < W - 1) & (pts[:, 1] >= 1) & (pts[:, 1] < H - 1)
        if ok.mean() < 0.7 or ok.sum() < 4: return None
        p = pts[ok]; return Gm[p[:, 1].astype(int), p[:, 0].astype(int)].mean()
    roof = np.zeros(len(hs)); step = np.zeros(len(hs))
    for i, h in enumerate(hs):
        px, py, fr = proj(k, np.c_[ring, np.full(len(ring), g0 + h)])
        if not fr.all(): return None
        e = energy_pts(sample_edges(np.c_[px, py]))
        if e is None: return None
        roof[i] = e
        lo_pts, hi_pts = [], []
        for zlo, zhi, acc in ((max(0.0, h - D), h, lo_pts), (h, h + D, hi_pts)):
            ax, ay, _ = proj(k, np.c_[poly, np.full(len(poly), g0 + zlo)]); cx, cy, _ = proj(k, np.c_[poly, np.full(len(poly), g0 + zhi)])
            for j in range(len(poly)): acc.append(sample_edges(np.array([[ax[j], ay[j]], [cx[j], cy[j]]])))
        elo = energy_pts(np.concatenate(lo_pts)); ehi = energy_pts(np.concatenate(hi_pts))
        step[i] = (elo - ehi) if (elo is not None and ehi is not None) else 0.0
    z = lambda a: (a - a.mean()) / (a.std() + 1e-6)
    return z(roof) + z(step)
hs = np.arange(2.0, HMAX + 0.01, 1.0); results = {}; dbg = []
for bi, b in enumerate(builds):
    g0 = float(HR.ground(np.array([b['cx']]), np.array([b['cy']]))[0]); C = np.array([b['cx'], b['cy'], g0])
    cand = []
    for k in frames[::3]:
        d = np.linalg.norm(C - np.array(poses[k][0])); graz = (poses[k][0][2] - g0) / d
        if d > DMAX or graz < GRAZMIN: continue
        P3 = np.r_[np.c_[b['poly'], np.full(len(b['poly']), g0)], np.c_[b['poly'], np.full(len(b['poly']), g0 + HMAX / 2)]]
        px, py, fr = proj(k, P3)
        if not fr.all() or px.min() < 30 or px.max() > W - 30 or py.min() < 30 or py.max() > H - 30: continue
        m = vo.dyn_mask(k); ii = np.clip(py.astype(int), 0, H - 1); jj = np.clip(px.astype(int), 0, W - 1)
        if (m[ii, jj] > 0).mean() < 0.9: continue
        cand.append((d, k))
    cand.sort(); cand = [k for _, k in cand[:14]]
    if len(cand) < 2: continue
    tot = np.zeros(len(hs)); used = 0
    for k in cand:
        sc = score_frame(k, b['poly'], g0, hs)
        if sc is None: continue
        sc = (sc - sc.mean()) / (sc.std() + 1e-6); tot += sc; used += 1
    if used < 2: continue
    tot /= used; i = int(np.argmax(tot)); h = float(hs[i]); conf = float((tot[i] - np.median(tot)) / (tot.std() + 1e-6))
    results[str(bi)] = dict(cx=b['cx'], cy=b['cy'], area=b['area'], h=h, conf=round(conf, 2), nframes=used, poly=b['poly'].round(1).tolist())
    if DEBUG and len(dbg) < DEBUG: dbg.append((bi, cand[0], h, conf))
    if bi % 25 == 0: print('  %d/%d  h=%.0f conf=%.1f (%d frames)' % (bi, len(builds), h, conf, used), flush=True)
json.dump(results, open(out, 'w')); hsv = np.array([r['h'] for r in results.values()]); cf = np.array([r['conf'] for r in results.values()])
print('%d batiments estimes; h mediane %.0f m, p90 %.0f; conf mediane %.1f, %d avec conf>2.5 -> %s' % (len(results), np.median(hsv), np.percentile(hsv, 90), np.median(cf), int((cf > 2.5).sum()), out))
# debug: toit projete a h* sur la frame la plus proche
for bi, k, h, conf in dbg:
    b = builds[bi]; img = cv2.imread('vid/v%04d.jpg' % k); g0 = float(HR.ground(np.array([b['cx']]), np.array([b['cy']]))[0]); ring = np.r_[b['poly'], b['poly'][:1]]
    for z, col in ((g0, (0, 165, 255)), (g0 + h, (0, 255, 0))):
        px, py, _ = proj(k, np.c_[ring, np.full(len(ring), z)]); cv2.polylines(img, [np.c_[px, py].astype(np.int32)], False, col, 2)
    bx, by, _ = proj(k, np.c_[b['poly'], np.full(len(b['poly']), g0)]); tx, ty, _ = proj(k, np.c_[b['poly'], np.full(len(b['poly']), g0 + h)])
    for j in range(len(bx)): cv2.line(img, (int(bx[j]), int(by[j])), (int(tx[j]), int(ty[j])), (0, 255, 0), 1)
    cx, cy, _ = proj(k, np.array([[b['cx'], b['cy'], g0 + h]])); cv2.putText(img, 'h=%.0f c=%.1f' % (h, conf), (int(cx[0]), int(cy[0]) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    x0_, y0_ = int(max(0, min(bx.min(), tx.min()) - 150)), int(max(0, min(by.min(), ty.min()) - 150)); x1_, y1_ = int(min(W, max(bx.max(), tx.max()) + 150)), int(min(H, max(by.max(), ty.max()) + 150))
    cv2.imwrite('hdbg_%03d_f%04d.jpg' % (bi, k), img[y0_:y1_, x0_:x1_], [cv2.IMWRITE_JPEG_QUALITY, 88])
