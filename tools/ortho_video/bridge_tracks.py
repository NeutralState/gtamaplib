"""bridge_tracks.py <ka> <kb> <out.npz> [nback] [nfwd] : pistes traversant une coupure de plan.
SIFT ka<->kb (masques), inliers F; puis KLT en arriere depuis ka (nback frames) et en avant depuis kb (nfwd frames).
Ids de pistes decales de 10^6 * kb pour ne pas heurter les autres fichiers."""
import sys, numpy as np, cv2
sys.path.insert(0, '/private/tmp/claude-501/-Users-alexandreleblanc-Downloads-gtamaplib-main/b03356f6-af67-4086-b7cc-fad47ae03b07/scratchpad'); import vo
ka, kb, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]; nback = int(sys.argv[4]) if len(sys.argv) > 4 else 8; nfwd = int(sys.argv[5]) if len(sys.argv) > 5 else 8
ga = cv2.imread('vid/v%04d.jpg' % ka, 0); gb = cv2.imread('vid/v%04d.jpg' % kb, 0); H, W = ga.shape
sift = cv2.SIFT_create(8000); kpa, da = sift.detectAndCompute(ga, vo.dyn_mask(ka)); kpb, db = sift.detectAndCompute(gb, vo.dyn_mask(kb))
m = cv2.BFMatcher().knnMatch(da, db, k=2); good = [a for a, b in m if a.distance < 0.75 * b.distance]
pa = np.float32([kpa[g.queryIdx].pt for g in good]); pb = np.float32([kpb[g.trainIdx].pt for g in good])
F, inl = cv2.findFundamentalMat(pa, pb, cv2.FM_RANSAC, 1.5, 0.999); inl = inl.ravel() > 0; pa, pb = pa[inl], pb[inl]
print('SIFT %d matches, %d inliers' % (len(good), inl.sum()))
lk = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
N = len(pa); ids = np.arange(N) + 1000000 * kb; obs = []
def track(k0, pts0, step, n):
    prev = cv2.imread('vid/v%04d.jpg' % k0, 0); pts = pts0.reshape(-1, 1, 2).astype(np.float32); alive = np.ones(len(pts0), bool)
    for i in range(1, n + 1):
        k = k0 + step * i; cur = cv2.imread('vid/v%04d.jpg' % k, 0)
        if cur is None: break
        p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, cur, pts, None, **lk); p0, st2, _ = cv2.calcOpticalFlowPyrLK(cur, prev, p1, None, **lk)
        fb = np.linalg.norm((p0 - pts).reshape(-1, 2), axis=1); ok = (st.ravel() == 1) & (st2.ravel() == 1) & (fb < 0.8)
        xy = p1.reshape(-1, 2); inside = (xy[:, 0] >= 2) & (xy[:, 0] < W - 2) & (xy[:, 1] >= 2) & (xy[:, 1] < H - 2); ok &= inside
        msk = vo.dyn_mask(k); ok[inside] &= msk[xy[inside, 1].astype(int), xy[inside, 0].astype(int)] > 0
        alive &= ok
        for j in np.nonzero(alive)[0]: obs.append((k, ids[j], float(xy[j, 0]), float(xy[j, 1])))
        pts = p1; prev = cur
obs += [(ka, ids[j], float(pa[j, 0]), float(pa[j, 1])) for j in range(N)] + [(kb, ids[j], float(pb[j, 0]), float(pb[j, 1])) for j in range(N)]
track(ka, pa, -1, nback); track(kb, pb, +1, nfwd)
obs = np.array(obs); tid, cnt = np.unique(obs[:, 1], return_counts=True); keep = np.isin(obs[:, 1], tid[cnt >= 4]); obs = obs[keep]
np.savez_compressed(out, obs=obs); print('pistes pont: %d (>= 4 obs), obs %d -> %s' % (len(np.unique(obs[:, 1])), len(obs), out))
