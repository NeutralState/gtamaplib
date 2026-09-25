"""Orthophoto depuis les poses VO: ortho_video.py <res_m> <step_frames> <dmax_m> <out.png> poses1.json [poses2.json ...]
Grille sol = bbox des empreintes; par frame on ne projette que les cellules dans la bbox de son empreinte au sol."""
import sys, os, json, numpy as np, cv2
sys.path.insert(0, '/Users/alexandreleblanc/Downloads/gtamaplib-main'); sys.path.insert(0, '/Users/alexandreleblanc/Downloads/gtamaplib-main/tools')
import gtamaplib as G, horizon_resect as HR
from scipy.spatial.transform import Rotation as R
res, step, dmax, out = float(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
poses = {}
for f in sys.argv[5:]:
    for k, v in json.load(open(f)).items():
        if v[3] >= 0: poses[int(k)] = v
FMIN = int(os.environ.get('FMIN', '0')); FMAX = int(os.environ.get('FMAX', '100000'))
frames = [k for k in sorted(poses) if FMIN <= k <= FMAX][::step]
W, H = 1920, 1080; HFOV = float(os.environ.get('HFOV', '89.677')); VFOV = G.get_vfov(HFOV, (W, H))
DMAXK = {k: (v[5] if len(v) > 5 else dmax) for k, v in poses.items()}   # dmax par frame (6e element optionnel)
def tans(k):
    hf = poses[k][4] if len(poses[k]) > 4 else HFOV; vf = G.get_vfov(hf, (W, H)); return np.tan(np.radians(hf) / 2), np.tan(np.radians(vf) / 2)
# masque image (fraction): HUD haut-centre, colonne centrale (avion + textes + QR), bas
def img_mask():
    m = np.ones((H, W), bool)
    m[:int(0.32 * H), int(0.26 * W):int(0.74 * W)] = False
    m[:int(0.82 * H), int(0.37 * W):int(0.67 * W)] = False
    m[int(0.96 * H):, :] = False
    return m
MASK = img_mask()
HUD = {int(k): v for k, v in json.load(open('hud_track.json')).items()} if os.path.exists('hud_track.json') else None
YY_, XX_ = np.mgrid[0:H, 0:W]; WING = (XX_ < 300 + (YY_ - 640) * (800 / 440)) & (YY_ > 560); WING[:, :260] = True
WING3 = (YY_ > -0.422 * XX_ + 1419.4 - 40) & (XX_ > 1020)   # aile droite, plan ~1350-1410 (mesuree sur la frame 1380)
WING2 = (YY_ > -0.444 * XX_ + 1433.1 - 40) & (XX_ > 1000)   # aile droite, plan 701-843 (mesuree sur la frame 770)
def frame_mask(k, img):
    """masque par frame: HUD suivi (hud_track.json, elements mobiles), avion (bleu/jaune vif dilate), bande basse, aile (plan A)."""
    if HUD is None: m = MASK.copy()
    else:
        m = np.ones((H, W), bool); m[:64, :] = False; m[1016:, :] = False    # letterbox: bandes noires 0-59 et 1020-1079 (mesurees), + marge
        kk = min(HUD, key=lambda q: abs(q - k))
        for n, (x, y, w, h, s) in HUD[kk].items():
            if s > 0.45 and n in ('mascot', 'qr'): m[max(0, y - 14):y + h + 14, max(0, x - 14):x + w + 14] = False
    wm = np.ones((H, W), np.float32)
    if HUD is not None:
        for n, (x, y, w, h, s) in HUD[kk].items():
            if s > 0.45 and n not in ('mascot', 'qr'): wm[max(0, y - 10):y + h + 10, max(0, x - 10):x + w + 10] = float(os.environ.get('HUDTXT_W', '0.15'))
    frame_mask.wm = wm
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); hh, sat, v = cv2.split(hsv)
    blue = (hh > 100) & (hh < 130) & (sat > 90) & (v > 50); yellow = (hh > 18) & (hh < 38) & (sat > 110) & (v > 120)
    pm = (blue | yellow).astype(np.uint8) * 255; pm = cv2.morphologyEx(pm, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)); pm = cv2.dilate(pm, np.ones((61, 61), np.uint8))
    m &= pm == 0
    if k < 92: m &= ~WING
    if 701 <= k <= 843: m &= ~WING2
    if 1300 <= k <= 1500: m &= ~WING3
    elif k >= 844: m[460:730, 760:1280] = False   # chase-cam apres Southside (844-930): avion plus a droite (aile jaune jusqu'a x~1220)
    else: m[420:700, 380:1060] = False      # boite fixe de l'avion (chase-cam plans B/C: bbox mesuree sur 94/110/140/160/200/330/500/650), la couleur seule rate les ailes dans la brume
    return m
def footprint(xyz, ypr, k_fp):
    """bbox sol de la frame: rayons des bords/grille de pixels sous l'horizon, coupes a dmax."""
    tanh, tanv = tans(k_fp); rot = R.from_quat(G.get_q(ypr)); C = np.array(xyz)
    u = np.linspace(0, W - 1, 25); v = np.linspace(0, H - 1, 15); U, V = np.meshgrid(u, v)
    ndx = 2 * ((U.ravel() + 0.5) / W) - 1; ndy = 2 * ((V.ravel() + 0.5) / H) - 1
    d = np.c_[ndx * tanh, np.ones(ndx.size), -ndy * tanv]; d = rot.apply(d); d /= np.linalg.norm(d, axis=1)[:, None]
    dm = DMAXK.get(k_fp, dmax); T = np.arange(20.0, dm, 4.0); P = C[None, None, :] + d[:, None, :] * T[None, :, None]
    below = (P[..., 2] - HR.ground(P[..., 0], P[..., 1])) < 0; hit = below.any(1); i = np.argmax(below, 1)
    # rayons sous l'horizon qui ne touchent pas le sol avant dmax: on prend le point a dmax, sinon la bbox est tronquee
    # en escalier (la zone rasante entre le dernier impact et dmax n'etait jamais projetee)
    i = np.where(hit, i, len(T) - 1); ok_ = hit | (d[:, 2] < 0)
    pts = P[np.arange(len(d)), i][ok_]
    if len(pts) < 4: return None
    return pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max()
fps = {}
for k in frames:
    fp = footprint(poses[k][0], poses[k][1], k)
    if fp: fps[k] = fp
X0 = min(f[0] for f in fps.values()); X1 = max(f[1] for f in fps.values()); Y0 = min(f[2] for f in fps.values()); Y1 = max(f[3] for f in fps.values())
X0, Y0 = np.floor(X0 / 50) * 50, np.floor(Y0 / 50) * 50; X1, Y1 = np.ceil(X1 / 50) * 50, np.ceil(Y1 / 50) * 50
if os.environ.get('BBOX'): X0, X1, Y0, Y1 = [float(a) for a in os.environ['BBOX'].split(',')]   # emprise forcee x0,x1,y0,y1 (tests rapides)
xs = np.arange(X0, X1, res); ys = np.arange(Y1, Y0, -res); GW, GH = len(xs), len(ys)
print('%d frames, grille %d x %d @ %.1f m  (x %.0f..%.0f, y %.0f..%.0f)' % (len(fps), GW, GH, res, X0, X1, Y0, Y1))
USE_DSM = os.environ.get('DSM', '1') == '1'
if USE_DSM:
    import dsm as _dsm; DSM, WALLS = _dsm.build_dsm(xs, ys, res)
    if os.environ.get('DSM_V16', '1') == '1':
        D2, W2 = _dsm.build_dsm_v16(xs, ys, res, HR.ground, float(os.environ.get('DSM_DEFAULT_H', '12')))
        DSM = np.maximum(DSM, D2); WALLS = np.concatenate([WALLS, W2]) if len(W2) else WALLS
    if os.environ.get('HEIGHTS'):
        D3, W3 = _dsm.build_dsm_est(xs, ys, res, HR.ground, os.environ['HEIGHTS'].split(','), float(os.environ.get('HCONF', '2.5')))
        DSM = np.maximum(DSM, D3); WALLS = np.concatenate([WALLS, W3]) if len(W3) else WALLS
    print('DSM: %d cellules batiments, %d points murs' % (int(np.isfinite(DSM).sum()), len(WALLS)), flush=True)
acc = np.zeros((GH, GW, 3), np.float32); wsum = np.zeros((GH, GW), np.float32); cnt = np.zeros((GH, GW), np.uint16); maxw = np.zeros((GH, GW), np.float32)
def samples(k):
    xyz, ypr = poses[k][0], poses[k][1]; fx0, fx1, fy0, fy1 = fps[k]
    c0, c1 = max(0, int((fx0 - X0) / res)), min(GW, int((fx1 - X0) / res) + 1); r0, r1 = max(0, int((Y1 - fy1) / res)), min(GH, int((Y1 - fy0) / res) + 1)
    if c1 <= c0 or r1 <= r0: return None
    tanh, tanv = tans(k); img = cv2.imread('vid/v%04d.jpg' % k)
    Xg, Yg = np.meshgrid(xs[c0:c1], ys[r0:r1]); Zg = HR.ground(Xg, Yg)
    if USE_DSM: Zg = np.maximum(Zg, DSM[r0:r1, c0:c1])          # toits des batiments a leur hauteur
    rot = R.from_quat(G.get_q(ypr)).inv(); C = np.array(xyz)
    P = np.stack([Xg.ravel() - C[0], Yg.ravel() - C[1], Zg.ravel() - C[2]], 1); d = rot.apply(P); front = d[:, 1] > 1
    px = ((d[:, 0] / np.where(front, d[:, 1], 1)) / tanh + 1) * 0.5 * W - 0.5; py = (1 - ((d[:, 2] / np.where(front, d[:, 1], 1)) / tanv + 1) * 0.5) * H - 0.5
    ok = front & (px >= 1) & (px < W - 2) & (py >= 1) & (py < H - 2)
    dist = np.linalg.norm(P, axis=1); graz = -P[:, 2] / np.maximum(dist, 1)
    dmk = DMAXK.get(k, dmax); ok &= (graz > float(os.environ.get("GRAZ", "0.10"))) & (dist < dmk)
    pxi = np.clip(px.astype(int), 0, W - 1); pyi = np.clip(py.astype(int), 0, H - 1); fm = frame_mask(k, img); ok &= fm[pyi, pxi]
    # fondu aux bords du masque ET de l'image (distance au bord en px / FEATHER): sinon chaque frame laisse une coupure nette
    # (escaliers au bord gauche = bord d'image des frames successives, trapezes = boite avion / HUD)
    fmu = fm.astype(np.uint8); fmu[0, :] = 0; fmu[-1, :] = 0; fmu[:, 0] = 0; fmu[:, -1] = 0
    feath = np.clip(cv2.distanceTransform(fmu, cv2.DIST_L2, 3) / float(os.environ.get('FEATHER', '80')), 0, 1)
    idx = np.nonzero(ok)[0]
    if len(idx) == 0: return None
    flat = pyi[idx] * W + pxi[idx]; zbuf = np.full(H * W, np.inf, np.float32); np.minimum.at(zbuf, flat, dist[idx].astype(np.float32))
    if USE_DSM and len(WALLS):                                    # murs = occulteurs: ce qui est derriere une facade est rejete
        wb = (WALLS[:, 0] >= xs[c0] - 5) & (WALLS[:, 0] <= xs[c1 - 1] + 5) & (WALLS[:, 1] >= ys[r1 - 1] - 5) & (WALLS[:, 1] <= ys[r0] + 5)
        if wb.any():
            Pw = WALLS[wb] - C; dw = rot.apply(Pw); fw = dw[:, 1] > 1
            pxw = ((dw[:, 0] / np.where(fw, dw[:, 1], 1)) / tanh + 1) * 0.5 * W - 0.5; pyw = (1 - ((dw[:, 2] / np.where(fw, dw[:, 1], 1)) / tanv + 1) * 0.5) * H - 0.5
            okw = fw & (pxw >= 0) & (pxw < W) & (pyw >= 0) & (pyw < H)
            if okw.any():
                fw_ = pyw[okw].astype(int) * W + pxw[okw].astype(int); np.minimum.at(zbuf, fw_, np.linalg.norm(Pw[okw], axis=1).astype(np.float32) - 1.0)
    # tolerance z-buffer = empreinte au sol d'un pixel le long du rayon (dist * angle_pixel / graz), sinon les cellules
    # rasantes qui tombent dans le meme pixel sont rejetees une sur deux -> moire en bandes
    apix = 2 * tanh / W
    tol = np.maximum(2.0, 1.5 * dist[idx] * apix / np.maximum(graz[idx], 0.05))
    idx = idx[dist[idx] <= zbuf[flat] + tol]
    fx_, fy_ = px[idx], py[idx]; ix, iy = fx_.astype(int), fy_.astype(int); u, v = (fx_ - ix)[:, None], (fy_ - iy)[:, None]
    col = (img[iy, ix] * (1 - u) * (1 - v) + img[iy, ix + 1] * u * (1 - v) + img[iy + 1, ix] * (1 - u) * v + img[iy + 1, ix + 1] * u * v).astype(np.float32)
    wgt = ((graz[idx] ** 2.0) / (dist[idx] / 100.0) ** 3).astype(np.float32)
    # bords doux: roll-off sur 150 m avant dmax et sur 0.04 d'incidence au-dessus de GRAZ (sinon arcs/coupures nettes)
    g0 = float(os.environ.get("GRAZ", "0.10"))
    wgt *= np.clip((dmk - dist[idx]) / 150.0, 0, 1).astype(np.float32) * np.clip((graz[idx] - g0) / 0.04, 0, 1).astype(np.float32)
    wgt = (wgt / 1e-4) ** float(os.environ.get("WPOW", "1.0"))    # normalise (evite le sous-depassement float32 pour WPOW>2)
    fe = feath[pyi[idx], pxi[idx]].astype(np.float32)
    if os.environ.get('FEATHER_BEFORE', '0') == '1': wgt = wgt * fe ** float(os.environ.get("WPOW", "1.0"))   # transition large (risque de fantomes)
    else: wgt = wgt * fe                                                   # defaut: transition courte, pas de double image
    wgt *= frame_mask.wm[pyi[idx], pxi[idx]]    # WPOW>1 = la meilleure vue domine (plus net, moins de fantomes)
    ii, jj = np.unravel_index(idx, Xg.shape); ii += r0; jj += c0
    return ii, jj, col, wgt
keys = sorted(fps)
for n, k in enumerate(keys):                       # passe 1: moyenne ponderee + poids max par cellule
    s_ = samples(k)
    if s_ is None: continue
    ii, jj, col, wgt = s_
    np.add.at(acc, (ii, jj), col * wgt[:, None]); np.add.at(wsum, (ii, jj), wgt); np.maximum.at(maxw, (ii, jj), wgt)
    if n % 25 == 0: print('  passe 1 frame %d (%d/%d)' % (k, n, len(keys)), flush=True)
mean1 = np.where(wsum[..., None] > 0, acc / np.maximum(wsum, 1e-9)[..., None], 0)
acc[:] = 0; wsum[:] = 0
for n, k in enumerate(keys):                       # passe 2: robuste (rejet des couleurs aberrantes et des vues trop lointaines)
    s_ = samples(k)
    if s_ is None: continue
    ii, jj, col, wgt = s_
    keep = (np.abs(col - mean1[ii, jj]).mean(axis=1) < 36) & (wgt >= float(os.environ.get("KEEP", "0.20")) * maxw[ii, jj])
    ii, jj, col, wgt = ii[keep], jj[keep], col[keep], wgt[keep]
    np.add.at(acc, (ii, jj), col * wgt[:, None]); np.add.at(wsum, (ii, jj), wgt); np.add.at(cnt, (ii, jj), 1)
    if n % 25 == 0: print('  passe 2 frame %d (%d/%d)' % (k, n, len(keys)), flush=True)
wsum2 = wsum.copy(); wsum = np.where(wsum > 0, wsum, 0)
# repli: cellule ou la passe robuste a tout rejete (route contrastee mal recalee) -> moyenne de la passe 1 plutot qu'un trou
blend = np.where(wsum[..., None] > 0, acc / np.maximum(wsum, 1e-9)[..., None], mean1).astype(np.uint8)
cv2.imwrite(out, blend); cv2.imwrite(out.replace('.png', '_count.png'), np.clip(cnt * 8, 0, 255).astype(np.uint8))
json.dump({'res': res, 'x0': float(X0), 'x1': float(X1), 'y0': float(Y0), 'y1': float(Y1), 'frames': len(fps), 'coverage': float((wsum > 0).mean())}, open(out.replace('.png', '.json'), 'w'))
print('couverture %.1f%% -> %s' % (100 * (wsum > 0).mean(), out))
