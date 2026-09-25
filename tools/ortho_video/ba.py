"""ba.py <out_poses.json> <poses.json...> --tracks tr1.npz [tr2.npz ...]
Bundle adjustment terrain-contraint: poses (xyz, ypr, hfov) par frame + points sol (x,y; z = heightmap),
ancres = clics d'Alexandre sur les cams video (landmarks xyz connus), priors: continuite fov, lissage position/orientation, roulis ~0.
"""
import sys, os, json, numpy as np, time
sys.path.insert(0, '/Users/alexandreleblanc/Downloads/gtamaplib-main'); sys.path.insert(0, '/Users/alexandreleblanc/Downloads/gtamaplib-main/tools')
import gtamaplib as G, horizon_resect as HR
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
from scipy.spatial.transform import Rotation as R
R_ = '/Users/alexandreleblanc/Downloads/gtamaplib-main/gtamapdata/'
args = sys.argv[1:]; out = args[0]; i_t = args.index('--tracks'); pose_files = args[1:i_t]; track_files = args[i_t + 1:]
W, H = 1920, 1080
MAXOBS_PER_FRAME = int(os.environ.get('MAXOBS', '500')); SUB = int(os.environ.get('SUBFRAMES', '1'))
# ---- poses initiales
poses = {}
for f in pose_files:
    for k, v in json.load(open(f)).items(): poses[int(k)] = v
frames = sorted(k for k in poses if k % SUB == 0); fidx = {k: i for i, k in enumerate(frames)}; NF = len(frames)
P0 = np.array([list(poses[k][0]) + list(poses[k][1]) + [poses[k][4] if len(poses[k]) > 4 else 89.677] for k in frames], float)
# coupures: frames consecutives dans la liste mais pas dans le meme plan
CUTS = {92, 313, 701, 844}
def same_shot(a, b): return not any(a < c <= b for c in CUTS)
# ---- ancres (clics)
CAMFRAME = {'Prison (Video) v091 (Wing)': 91, 'Prison (Video) v160': 160, 'Prison (Video) v250': 250, 'Prison (Video) v310': 310,
            'Prison (Video) f100': 325, 'Prison (Video) f140': 365, 'Prison (Video) f180': 405, 'Prison (Video) v500': 500, 'Prison (Video) v600': 600,
            'Prison (Video) v680': 680, 'Biplane (Video) v0770': 770, 'Biplane (Video) v0820': 820, 'Biplane (Video) v0900': 900}
PX = json.load(open(R_ + 'pixels.json')); LM = json.load(open(R_ + 'landmarks.json')); EX = json.load(open(R_ + 'excluded_markings.json'))
A_f, A_X, A_p = [], [], []
for cam, k in CAMFRAME.items():
    if k not in fidx or cam not in PX: continue
    for n, p in PX[cam].items():
        if n in EX.get(cam, []) or not LM.get(n, {}).get('xyz'): continue
        if not (0 <= p[0] < W and 0 <= p[1] < H): continue
        A_f.append(fidx[k]); A_X.append(LM[n]['xyz']); A_p.append(p)
A_f = np.array(A_f); A_X = np.array(A_X, float); A_p = np.array(A_p, float); print('ancres:', len(A_f), 'sur', len(set(A_f.tolist())), 'frames')
# ---- observations
obs = np.concatenate([np.load(f)['obs'] for f in track_files])
obs = obs[np.isin(obs[:, 0].astype(int), frames)]
# sous-echantillonnage par frame
rng = np.random.default_rng(0); keep = np.zeros(len(obs), bool)
for k in frames:
    idx = np.nonzero(obs[:, 0].astype(int) == k)[0]
    if len(idx) > MAXOBS_PER_FRAME: idx = rng.choice(idx, MAXOBS_PER_FRAME, replace=False)
    keep[idx] = True
obs = obs[keep]
tid, inv, cnt = np.unique(obs[:, 1].astype(int), return_inverse=True, return_counts=True)
good = cnt[inv] >= 3; obs = obs[good]; tid, inv = np.unique(obs[:, 1].astype(int), return_inverse=True); NT = len(tid)
O_f = np.array([fidx[int(k)] for k in obs[:, 0]]); O_t = inv; O_p = obs[:, 2:4]
print('frames %d, pistes %d, observations %d' % (NF, NT, len(obs)))
# ---- init des points: rayon ∩ heightmap depuis l'observation mediane de la piste
def ray_ground(C, d, tmax=3000.0):
    T = np.arange(20.0, tmax, 3.0); P = C[None, :] + d[None, :] * T[:, None]; below = P[:, 2] < HR.ground(P[:, 0], P[:, 1])
    if not below.any(): return None
    i = int(np.argmax(below)); return P[max(0, i - 1)][:2] if i > 0 else P[0][:2]
X0 = np.zeros((NT, 2)); okT = np.zeros(NT, bool)
order = np.argsort(O_t, kind='stable'); starts = np.searchsorted(O_t[order], np.arange(NT))
for t in range(NT):
    ii = order[starts[t]:(starts[t + 1] if t + 1 < NT else len(order))]; j = ii[len(ii) // 2]
    f = O_f[j]; pose = P0[f]; hf = pose[6]; tanh = np.tan(np.radians(hf) / 2); tanv = np.tan(np.radians(G.get_vfov(hf, (W, H))) / 2)
    ndx = 2 * ((O_p[j, 0] + 0.5) / W) - 1; ndy = 2 * ((O_p[j, 1] + 0.5) / H) - 1
    d = R.from_quat(G.get_q(list(pose[3:6]))).apply([ndx * tanh, 1.0, -ndy * tanv]); d /= np.linalg.norm(d)
    g = ray_ground(pose[:3], d)
    if g is not None: X0[t] = g; okT[t] = True
sel = okT[O_t]; O_f, O_t, O_p = O_f[sel], O_t[sel], O_p[sel]; tid, O_t = np.unique(O_t, return_inverse=True); X0 = X0[tid]; NT = len(tid)
print('pistes initialisees: %d, obs %d' % (NT, len(O_f)))
# ---- projection vectorisee
def project(Pf, Xw):
    """Pf: (n,7) poses ; Xw: (n,3) points ; -> px, py, front"""
    rot = R.from_quat(np.array([G.get_q(list(p[3:6])) for p in Pf]))
    return project_rot(Pf, rot, Xw)
def project_rot(Pf, rot, Xw):
    d = rot.inv().apply(Xw - Pf[:, :3]); front = d[:, 1] > 1
    hf = Pf[:, 6]; th = np.tan(np.radians(hf) / 2); tv = np.tan(np.radians(hf) / 2) * (H / W)   # vfov via ratio (equivalent a get_vfov)
    y = np.where(front, d[:, 1], 1.0)
    px = ((d[:, 0] / y) / th + 1) * 0.5 * W - 0.5; py = (1 - ((d[:, 2] / y) / tv + 1) * 0.5) * H - 0.5
    return px, py, front
# verif de la formule vfov
hf_ = 80.0; assert abs(np.tan(np.radians(G.get_vfov(hf_, (W, H))) / 2) - np.tan(np.radians(hf_) / 2) * H / W) < 1e-9
# ---- parametres: [poses (NF*7)] + [points (NT*2)]
def unpack(v): return v[:NF * 7].reshape(NF, 7), v[NF * 7:].reshape(NT, 3)
PRI_Z = float(os.environ.get('PRI_Z', '6.0'))
Z0 = HR.ground(X0[:, 0], X0[:, 1]) + 1.0; X0 = np.c_[X0, Z0]
ANCHORED = np.zeros(NF, bool); ANCHORED[np.unique(A_f)] = True
SIG_PX, SIG_A = float(os.environ.get('SIG_PX', '2.0')), float(os.environ.get('SIG_A', '0.15'))
PRI_POS, PRI_ANG, PRI_FOV = float(os.environ.get('PRI_POS', '10')), float(os.environ.get('PRI_ANG', '1.0')), float(os.environ.get('PRI_FOV', '1.0'))
def residuals(v):
    Pf, Xt = unpack(v)
    # rotations par frame (une fois), puis indexation
    quats = np.array([G.get_q(list(p[3:6])) for p in Pf]); rot_all = R.from_quat(quats)
    Xw = Xt[O_t]
    px, py, front = project_rot(Pf[O_f], rot_all[O_f], Xw)
    r_obs = np.c_[px - O_p[:, 0], py - O_p[:, 1]]; r_obs[~front] = 200.0; SAT = float(os.environ.get('SAT', '6.0')); r_obs = SAT * np.tanh(r_obs.ravel() / SAT) / SIG_PX   # saturation douce des aberrants (perte lineaire ailleurs)
    ax, ay, af = project_rot(Pf[A_f], rot_all[A_f], A_X); r_anc = np.c_[ax - A_p[:, 0], ay - A_p[:, 1]]; r_anc[~af] = 200.0; r_anc = r_anc.ravel() / SIG_A
    # priors
    pr = []
    for i in range(NF - 1):
        if same_shot(frames[i], frames[i + 1]) and frames[i + 1] - frames[i] <= 2 * SUB:
            pr.append((Pf[i + 1, 6] - Pf[i, 6]) / (0.12 * SUB))                    # fov continu
    for i in range(1, NF - 1):
        if same_shot(frames[i - 1], frames[i + 1]) and frames[i + 1] - frames[i - 1] <= 4 * SUB:
            acc = Pf[i + 1, :3] - 2 * Pf[i, :3] + Pf[i - 1, :3]; pr += list(acc / (0.35 * SUB * SUB))   # lissage position (2e difference)
            ang = Pf[i + 1, 3:6] - 2 * Pf[i, 3:6] + Pf[i - 1, 3:6]; ang = (ang + 180) % 360 - 180; pr += list(ang / (0.08 * SUB * SUB))
    pr += list(((Pf[:, 5] + 180) % 360 - 180) / 1.0)                                   # roulis ~0 (faible)
    dp = Pf - P0; dp[:, 3:6] = (dp[:, 3:6] + 180) % 360 - 180
    wpos = np.where(ANCHORED, 0.05, PRI_POS)[:, None]; wang = np.where(ANCHORED, 0.005, PRI_ANG)[:, None]; wfov = np.where(ANCHORED, 0.005, PRI_FOV)
    pr += list((dp[:, :3] / wpos).ravel()) + list((dp[:, 3:6] / wang).ravel()) + list(dp[:, 6] / wfov)   # prior vers l'init; frames ancrees quasi figees
    pr += list((Xt[:, 2] - HR.ground(Xt[:, 0], Xt[:, 1]) - 1.0) / PRI_Z)                                     # z des points ~ sol (arbres/batiments toleres)
    return np.r_[r_obs, r_anc, np.array(pr)]
# ---- structure creuse du jacobien
def sparsity():
    n_obs = len(O_f) * 2; n_anc = len(A_f) * 2
    # compter les priors comme dans residuals
    npr = 0
    for i in range(NF - 1):
        if same_shot(frames[i], frames[i + 1]) and frames[i + 1] - frames[i] <= 2 * SUB: npr += 1
    for i in range(1, NF - 1):
        if same_shot(frames[i - 1], frames[i + 1]) and frames[i + 1] - frames[i - 1] <= 4 * SUB: npr += 6
    npr += NF + NF * 7 + NT
    Jn = n_obs + n_anc + npr; Jm = NF * 7 + NT * 3; S = lil_matrix((Jn, Jm), dtype=np.uint8)
    rows = np.repeat(np.arange(len(O_f)) * 2, 2) + np.tile([0, 1], len(O_f))
    for c in range(7): S[rows, np.repeat(O_f * 7 + c, 2)] = 1
    for c in range(3): S[rows, NF * 7 + np.repeat(O_t * 3 + c, 2)] = 1
    rows = n_obs + np.repeat(np.arange(len(A_f)) * 2, 2) + np.tile([0, 1], len(A_f))
    for c in range(7): S[rows, np.repeat(A_f * 7 + c, 2)] = 1
    r = n_obs + n_anc
    for i in range(NF - 1):
        if same_shot(frames[i], frames[i + 1]) and frames[i + 1] - frames[i] <= 2 * SUB: S[r, [i * 7 + 6, (i + 1) * 7 + 6]] = 1; r += 1
    for i in range(1, NF - 1):
        if same_shot(frames[i - 1], frames[i + 1]) and frames[i + 1] - frames[i - 1] <= 4 * SUB:
            for c in range(6): S[r, [(i - 1) * 7 + c, i * 7 + c, (i + 1) * 7 + c]] = 1; r += 1
    for i in range(NF): S[r, i * 7 + 5] = 1; r += 1
    for c in range(3):
        for i in range(NF): S[r, i * 7 + c] = 1; r += 1
    for c in range(3, 6):
        for i in range(NF): S[r, i * 7 + c] = 1; r += 1
    for i in range(NF): S[r, i * 7 + 6] = 1; r += 1
    for t_ in range(NT): S[r, [NF * 7 + t_ * 3, NF * 7 + t_ * 3 + 1, NF * 7 + t_ * 3 + 2]] = 1; r += 1
    assert r == Jn, (r, Jn); return S.tocsr()
v0 = np.r_[P0.ravel(), X0.ravel()]
t = time.time(); r0 = residuals(v0); n_obs = len(O_f) * 2; n_anc = len(A_f) * 2
def report(r, tag):
    ro = np.abs(r[:n_obs] * SIG_PX); ra = np.abs(r[n_obs:n_obs + n_anc] * SIG_A)
    print('%s: reproj mediane %.2f px (p90 %.2f) ; ancres mediane %.1f px (p90 %.1f, max %.1f)' % (tag, np.median(ro), np.percentile(ro, 90), np.median(ra), np.percentile(ra, 90), ra.max()), flush=True)
report(r0, 'init'); print('residus %d, params %d, %.1fs' % (len(r0), len(v0), time.time() - t))
S = sparsity(); print('sparsite ok', S.shape, flush=True)
x_scale = np.r_[np.tile([3, 3, 3, 0.1, 0.1, 0.1, 0.1], NF), np.tile([1.0, 1.0, 1.0], NT)]
sol = least_squares(residuals, v0, jac_sparsity=S, x_scale=x_scale, loss='linear', max_nfev=int(os.environ.get('NFEV', '30')), verbose=1, tr_solver='lsmr')
report(sol.fun, 'final'); Pf, Xt = unpack(sol.x)
d = np.linalg.norm(Pf[:, :3] - P0[:, :3], axis=1); print('deplacement des poses: mediane %.1f m, max %.1f m ; fov: mediane |d| %.2f' % (np.median(d), d.max(), np.median(np.abs(Pf[:, 6] - P0[:, 6]))))
outp = {str(k): [list(map(float, Pf[i, :3])), list(map(float, Pf[i, 3:6])), int(poses[k][2]), float(poses[k][3]), float(Pf[i, 6])] + ([poses[k][5]] if len(poses[k]) > 5 else []) for i, k in enumerate(frames)}
json.dump(outp, open(out, 'w')); print('->', out)
