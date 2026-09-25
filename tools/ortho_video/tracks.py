"""tracks.py <a> <b> <out.npz> : pistes KLT sur les frames a..b (meme plan, pas de coupure), masques HUD/avion/aile de vo.py.
Sortie: obs = array (N,4) [frame, track_id, x, y] ; pistes de >= MINLEN frames."""
import sys, numpy as np, cv2
sys.path.insert(0, '/private/tmp/claude-501/-Users-alexandreleblanc-Downloads-gtamaplib-main/b03356f6-af67-4086-b7cc-fad47ae03b07/scratchpad')
import vo
a, b, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]; MINLEN = 6
lk = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
prev = cv2.imread('vid/v%04d.jpg' % a, 0); H, W = prev.shape
pts = np.zeros((0, 1, 2), np.float32); ids = np.zeros(0, int); nid = 0; obs = []
def detect(gray, k, existing):
    m = vo.dyn_mask(k).copy()
    if len(existing):
        for x, y in existing.reshape(-1, 2): cv2.circle(m, (int(x), int(y)), 14, 0, -1)
    p = cv2.goodFeaturesToTrack(gray, maxCorners=1800, qualityLevel=0.008, minDistance=14, blockSize=7, mask=m)
    return np.zeros((0, 1, 2), np.float32) if p is None else p.astype(np.float32)
new = detect(prev, a, pts); pts = np.vstack([pts, new]); ids = np.r_[ids, np.arange(nid, nid + len(new))]; nid += len(new)
for x, y in pts.reshape(-1, 2): pass
obs += [(a, i, float(x), float(y)) for i, (x, y) in zip(ids, pts.reshape(-1, 2))]
for k in range(a + 1, b + 1):
    cur = cv2.imread('vid/v%04d.jpg' % k, 0)
    if cur is None or len(pts) == 0: break
    p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, cur, pts, None, **lk); p0, st2, _ = cv2.calcOpticalFlowPyrLK(cur, prev, p1, None, **lk)
    fb = np.linalg.norm((p0 - pts).reshape(-1, 2), axis=1); ok = (st.ravel() == 1) & (st2.ravel() == 1) & (fb < 0.8)
    m = vo.dyn_mask(k); xy = p1.reshape(-1, 2); inside = (xy[:, 0] >= 2) & (xy[:, 0] < W - 2) & (xy[:, 1] >= 2) & (xy[:, 1] < H - 2)
    ok &= inside; ok[inside] &= m[xy[inside, 1].astype(int), xy[inside, 0].astype(int)] > 0
    # rejet des points statiques (HUD residuel) quand la scene bouge
    flow = np.linalg.norm(xy - pts.reshape(-1, 2), axis=1); med = np.median(flow[ok]) if ok.any() else 0
    if med > 2: ok &= flow > 0.6
    pts = p1[ok]; ids = ids[ok]
    if len(pts) < 1100:
        new = detect(cur, k, pts); pts = np.vstack([pts, new]); ids = np.r_[ids, np.arange(nid, nid + len(new))]; nid += len(new)
    obs += [(k, i, float(x), float(y)) for i, (x, y) in zip(ids, pts.reshape(-1, 2))]
    prev = cur
    if k % 50 == 0: print(k, len(pts), 'points', len(obs), 'obs', flush=True)
obs = np.array(obs); tid, cnt = np.unique(obs[:, 1], return_counts=True); keep = np.isin(obs[:, 1], tid[cnt >= MINLEN]); obs = obs[keep]
np.savez_compressed(out, obs=obs); print('pistes >= %d frames: %d, obs %d -> %s' % (MINLEN, len(np.unique(obs[:, 1])), len(obs), out))
