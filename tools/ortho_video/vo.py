"""Odometrie visuelle ancree terrain: pose de chaque frame par PnP sur des points sol dont le 3D vient de
l'intersection rayon/heightmap depuis la frame precedente (deja posee). usage: vo.py <start> <end> <step:+1|-1> <out.json>"""
import sys, os, json, numpy as np, cv2
sys.path.insert(0, '/Users/alexandreleblanc/Downloads/gtamaplib-main'); sys.path.insert(0, '/Users/alexandreleblanc/Downloads/gtamaplib-main/tools')
import gtamaplib as G, horizon_resect as HR
from scipy.spatial.transform import Rotation as R
from scipy.optimize import least_squares
W, H = 1920, 1080; HFOV = float(os.environ.get('HFOV', '89.677')); VFOV = G.get_vfov(HFOV, (W, H))
fx = (W / 2) / np.tan(np.radians(HFOV) / 2); fy = (H / 2) / np.tan(np.radians(VFOV) / 2); cx, cy = (W - 1) / 2, (H - 1) / 2
K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], float)
M = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)     # gta cam (x droite, y avant, z haut) -> cv (x, y bas, z avant)
HF = [HFOV]
def setK(hf):
    global fx, fy, K; HF[0] = hf; vf = G.get_vfov(hf, (W, H)); fx = (W / 2) / np.tan(np.radians(hf) / 2); fy = (H / 2) / np.tan(np.radians(vf) / 2); K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], float)
def pose_to_cv(xyz, ypr):
    Rg = R.from_quat(G.get_q(ypr)).as_matrix()               # cam->monde
    Rcv = M @ Rg.T; t = -Rcv @ np.asarray(xyz, float); return Rcv, t
def cv_to_pose(Rcv, t):
    C = -Rcv.T @ t; Rg = (M.T @ Rcv).T                        # Rcv = M Rg^T  ->  Rg = (M^T Rcv)^T
    q = R.from_matrix(Rg).as_quat(); return C, list(G.get_ypr(q))
def project(Rcv, t, X):
    Y = (Rcv @ X.T).T + t; ok = Y[:, 2] > 1
    p = np.c_[fx * Y[:, 0] / Y[:, 2] + cx, fy * Y[:, 1] / Y[:, 2] + cy]; return p, ok
def ray_terrain(C, dirs, tmax=4000.0, dt=2.0):
    T = np.arange(20.0, tmax, dt); P = C[None, None, :] + dirs[:, None, :] * T[None, :, None]
    dz = P[..., 2] - HR.ground(P[..., 0], P[..., 1]); below = dz < 0
    hit = below.any(axis=1); i = np.argmax(below, axis=1)
    # affinage lineaire entre i-1 et i
    i0 = np.maximum(i - 1, 0); a = dz[np.arange(len(i)), i0]; b = dz[np.arange(len(i)), i]
    f = np.where(np.abs(a - b) > 1e-6, a / (a - b), 0.0); tt = T[i0] + f * (T[i] - T[i0])
    return C[None, :] + dirs * tt[:, None], hit
def pixel_dirs(Rcv, pts):
    d = np.c_[(pts[:, 0] - cx) / fx, (pts[:, 1] - cy) / fy, np.ones(len(pts))]
    return (Rcv.T @ d.T).T / np.linalg.norm(d, axis=1)[:, None]
MASK = np.ones((H, W), np.uint8) * 255
MASK[:int(0.32 * H), int(0.28 * W):int(0.72 * W)] = 0        # HUD crypto
MASK[:int(0.82 * H), int(0.40 * W):int(0.67 * W)] = 0        # colonne de textes semi-transparents (statiques!) + QR
MASK[int(0.22 * H):int(0.62 * H), int(0.36 * W):int(0.66 * W)] = 0   # avion (chase-cam, ~centre)
MASK[int(0.95 * H):, :] = 0
def dyn_mask(gray_frame_index):
    img = cv2.imread('vid/v%04d.jpg' % gray_frame_index); hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); h, sat, v = cv2.split(hsv)
    blue = (h > 100) & (h < 130) & (sat > 90) & (v > 50); yellow = (h > 18) & (h < 38) & (sat > 110) & (v > 120)
    m = ((blue | yellow).astype(np.uint8) * 255); m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)); m = cv2.dilate(m, np.ones((61, 61), np.uint8))
    out = cv2.bitwise_and(MASK, cv2.bitwise_not(m))
    if 92 <= gray_frame_index < 313: out[int(0.34 * H):int(0.70 * H), int(0.12 * W):int(0.66 * W)] = 0   # avion enorme au premier plan (plan 92-312)
    if 701 <= gray_frame_index <= 843:   # aile droite (plan 701-843): bord superieur de l'aile de (1000,1080) a (1920,640)
        yy, xx = np.mgrid[0:H, 0:W]; out[(yy > -0.444 * xx + 1433.1 - 40) & (xx > 1000)] = 0
    if 1300 <= gray_frame_index <= 1500:   # aile droite 1380: bord de (840,1080) a (1920,670)
        yy, xx = np.mgrid[0:H, 0:W]; out[(yy > -0.422 * xx + 1419.4 - 40) & (xx > 1020)] = 0
    if gray_frame_index < 92:   # plan A (POV aile): aile en bas a gauche sous la diagonale (300,640)->(1100,1080), + fuselage a gauche
        yy, xx = np.mgrid[0:H, 0:W]; out[(xx < 300 + (yy - 640) * (800 / 440)) & (yy > 560)] = 0; out[:, :260] = 0
    return out
LMS = json.load(open('/Users/alexandreleblanc/Downloads/gtamaplib-main/gtamapdata/landmarks.json'))
LM_NAMES = ['WDNA FM', 'WDNA FM (N1)', 'Homestead Water Tower'] + ['Prison Tower (%d)' % i for i in range(1, 7)]
LM_XYZ = np.array([LMS[k]['xyz'] for k in LM_NAMES], float)
LM_XYZ = np.vstack([LM_XYZ, [[-2522.9, -2301.8, float(HR.ground(-2522.9, -2301.8)) + 2.0]]]); LM_NAMES = LM_NAMES + ['WDNA base']
def run(start, end, step, anchors, out):
    poses = {}; i = start
    if start in anchors: xyz, ypr = anchors[start]
    else:
        st = json.load(open(os.environ.get('START_JSON', 'vo_back2.json')))[str(start)]; xyz, ypr = st[0], st[1]
        if len(st) > 4: setK(float(st[4]))
    poses[start] = (list(xyz), list(ypr), 0, 0.0, HF[0])
    prev = cv2.imread('vid/v%04d.jpg' % i, 0); Rcv, t = pose_to_cv(xyz, ypr)
    lmp, _lmok = project(Rcv, t, LM_XYZ); lmvis = _lmok & (lmp[:, 0] > 20) & (lmp[:, 0] < W - 20) & (lmp[:, 1] > 20) & (lmp[:, 1] < H - 20)
    lmpix = lmp.copy(); nlm = 0
    pts = None; X3 = None; lk = dict(winSize=(21, 21), maxLevel=4, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    while (i != end):
        j = i + step; img = cv2.imread('vid/v%04d.jpg' % j, 0)
        if img is None: break
        if pts is None or len(pts) < 400:
            f = cv2.goodFeaturesToTrack(prev, 1500, 0.01, 12, mask=dyn_mask(i), blockSize=7)
            newp = f.reshape(-1, 2) if f is not None else np.zeros((0, 2))
            C = -Rcv.T @ t; X, hit = ray_terrain(C, pixel_dirs(Rcv, newp)); newp, X = newp[hit], X[hit]
            if pts is None: pts, X3 = newp, X
            else: pts, X3 = np.vstack([pts, newp]), np.vstack([X3, X])
        def track_and_pnp(pts, X3):
            p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, img, pts.astype(np.float32).reshape(-1, 1, 2), None, **lk)
            p0b, st2, _ = cv2.calcOpticalFlowPyrLK(img, prev, p1, None, **lk)
            fb = np.linalg.norm(p0b.reshape(-1, 2) - pts, axis=1); good = (st.ravel() == 1) & (st2.ravel() == 1) & (fb < 0.8)
            flow = np.linalg.norm(p1.reshape(-1, 2) - pts, axis=1)
            if np.median(flow[good]) > 2.0: good &= flow > 0.6          # overlay statique (HUD, aile, avion)
            p1 = p1.reshape(-1, 2)[good]; X3g = X3[good]
            inb = (p1[:, 0] > 2) & (p1[:, 0] < W - 3) & (p1[:, 1] > 2) & (p1[:, 1] < H - 3); p1, X3g = p1[inb], X3g[inb]
            if len(p1) < 12: return None
            nl = int(lmvis.sum()) * 6
            if nl: p1 = np.vstack([np.repeat(lmpix[lmvis], 6, axis=0), p1]); X3g = np.vstack([np.repeat(LM_XYZ[lmvis], 6, axis=0), X3g])
            rvec0, _ = cv2.Rodrigues(Rcv)
            ok, rvec, tvec, inl = cv2.solvePnPRansac(X3g.astype(np.float64), p1.astype(np.float64), K, None, rvec0.copy(), t.reshape(3, 1).copy(), useExtrinsicGuess=True, iterationsCount=300, reprojectionError=2.5, flags=cv2.SOLVEPNP_ITERATIVE)
            if not ok or inl is None or len(inl) < 30: return None
            inl = inl.ravel(); rvec, tvec = cv2.solvePnPRefineLM(X3g[inl].astype(np.float64), p1[inl].astype(np.float64), K, None, rvec, tvec)
            return rvec, tvec, p1[nl:], X3g[nl:], inl[inl >= nl] - nl
        # suivi des landmarks connus (points hauts: brise la degenerescence sol plan)
        if lmvis.any():
            q0 = lmpix[lmvis].astype(np.float32).reshape(-1, 1, 2)
            q1, s1, _ = cv2.calcOpticalFlowPyrLK(prev, img, q0, None, winSize=(31, 31), maxLevel=4)
            q0b, s2, _ = cv2.calcOpticalFlowPyrLK(img, prev, q1, None, winSize=(31, 31), maxLevel=4)
            okl = (s1.ravel() == 1) & (s2.ravel() == 1) & (np.linalg.norm(q0b.reshape(-1, 2) - q0.reshape(-1, 2), axis=1) < 1.0)
            idxv = np.nonzero(lmvis)[0]; lmpix[idxv[okl]] = q1.reshape(-1, 2)[okl]; lmvis[idxv[~okl]] = False
        res = track_and_pnp(pts, X3)
        if res is None:   # redetection fraiche sur prev et nouvel essai
            f = cv2.goodFeaturesToTrack(prev, 2500, 0.005, 8, mask=dyn_mask(i), blockSize=7)
            if f is not None:
                newp = f.reshape(-1, 2); C = -Rcv.T @ t; X, hit = ray_terrain(C, pixel_dirs(Rcv, newp)); res = track_and_pnp(newp[hit], X[hit])
        if res is None:
            print('  frame %d: suivi perdu, pose recopiee' % j); poses[j] = (list(map(float, xyz)), list(map(float, ypr)), 0, -1.0); prev = img; i = j; pts = None; continue
        rvec, tvec, p1, X3, inl = res
        Rcv, t = cv2.Rodrigues(rvec)[0], tvec.ravel()
        # [PRIORS] raffinement contraint: roulis ~ 0 (camera de poursuite), altitude continue (|dz| ~ 1.5 m/frame)
        C0, y0 = cv_to_pose(Rcv, t); zprev = float(xyz[2]); Xi, Pi = X3[inl], p1[inl]
        Xl, Pl = (LM_XYZ[lmvis], lmpix[lmvis]) if lmvis.any() else (np.zeros((0, 3)), np.zeros((0, 2)))
        hfprev = HF[0]
        def resid(v):
            setK(v[6]); Rc, tc = pose_to_cv(v[:3], [v[3], v[4], v[5]])
            pr, _ = project(Rc, tc, Xi); r = (pr - Pi).ravel()
            if len(Xl): pl, _ = project(Rc, tc, Xl); r = np.r_[r, 3.0 * (pl - Pl).ravel()]
            return np.r_[r, [v[5] / 0.3 * 1.0, (v[2] - zprev) / 1.5 * 1.0, (v[6] - hfprev) / 0.15 * 1.0]]
        v0 = np.r_[C0, y0, hfprev]; sol = least_squares(resid, v0, x_scale=[5, 5, 5, 0.2, 0.2, 0.2, 0.2], max_nfev=40)
        setK(float(sol.x[6])); Rcv, t = pose_to_cv(sol.x[:3], list(sol.x[3:6]))
        lp, lo = project(Rcv, t, LM_XYZ)
        for a_ in np.nonzero(lmvis)[0]:
            if np.linalg.norm(lp[a_] - lmpix[a_]) > 8: lmvis[a_] = False
        newvis = lo & ~lmvis & (lp[:, 0] > 40) & (lp[:, 0] < W - 40) & (lp[:, 1] > 40) & (lp[:, 1] < H - 40)
        lmpix[newvis] = lp[newvis]; lmvis |= newvis
        pr, _ = project(Rcv, t, X3[inl]); rms = float(np.sqrt(((pr - p1[inl]) ** 2).sum(1).mean()))
        xyz, ypr = cv_to_pose(Rcv, t); poses[j] = (list(map(float, xyz)), list(map(float, ypr)), int(len(inl)), rms, float(HF[0]))
        pts, X3 = p1[inl], X3[inl]; prev = img; i = j
        if j in anchors:
            ax, ay = anchors[j]; d = np.linalg.norm(np.array(ax) - xyz); dy = (np.array(ay) - np.array(ypr) + 180) % 360 - 180
            print('  ANCRE %d: ecart position %.1f m, ypr %s' % (j, d, np.round(dy, 2)))
        if j % 20 == 0: print('frame %d: xyz %s ypr %s hfov %.1f inl %d rms %.2f lm %d' % (j, np.round(xyz, 1), np.round(ypr, 2), HF[0], len(inl), rms, int(lmvis.sum())))
    json.dump({str(k): v for k, v in poses.items()}, open(out, 'w'))
    lost = sum(1 for v in poses.values() if v[3] < 0); print('poses:', len(poses), 'perdues:', lost)
    return poses
if __name__ == '__main__':
    cams = json.load(open('/Users/alexandreleblanc/Downloads/gtamaplib-main/gtamapdata/cameras.json'))
    anchors = {325: (cams["Prison (Video) f100"]["xyz"], cams["Prison (Video) f100"]["ypr"]), 365: (cams['Prison (Video) f140']['xyz'], cams['Prison (Video) f140']['ypr']), 405: (cams["Prison (Video) f180"]['xyz'], cams['Prison (Video) f180']['ypr'])}
    # auto-test des conversions
    Rcv, t = pose_to_cv(*anchors[325]); X = np.array([[-2903.2, -2722.7, 36.7], [-2522.9, -2301.8, 5.0]])
    p, _ = project(Rcv, t, X); ref = [G.get_pixel(x, anchors[325][0], G.get_q(anchors[325][1]), (HFOV, VFOV), (W, H)) for x in X]
    print('autotest projection (doit etre ~0):', np.abs(p - np.array(ref)).max()); C, y = cv_to_pose(Rcv, t); print('autotest pose:', np.round(np.array(C) - anchors[325][0], 3), np.round(np.array(y) - anchors[325][1], 4))
    s, e, st, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    try: run(s, e, st, anchors, out)
    except Exception as ex: print('EXCEPTION', ex)
