"""tallmask.py <patch.png> <meta.json> <poses.json> <out.png> [HT] [heights.json,...]
Enleve d'une pastille ortho tout ce qui est dans la « trainee » d'un batiment haut (>= HT m): emprise V16 du batiment + sa projection
au sol depuis la camera (les facades etalees). Batiments hauts = silhouettes V16 (gris 176) contenant un landmark haut ou un mesh,
+ hauteurs estimees (fichiers heights) >= HT. Marge de 8 m."""
import sys, json, numpy as np, cv2
sys.path.insert(0, '/Users/alexandreleblanc/Downloads/gtamaplib-main'); sys.path.insert(0, '/Users/alexandreleblanc/Downloads/gtamaplib-main/tools'); sys.path.insert(0, '.')
import horizon_resect as HR
patch, meta, posesf, out = sys.argv[1:5]; HT = float(sys.argv[5]) if len(sys.argv) > 5 else 30.0; hfiles = sys.argv[6].split(',') if len(sys.argv) > 6 else []
o = cv2.imread(patch); m = json.load(open(meta)); res = m['res']; X0, Y1 = m['x0'], m['y1']; GH, GW = o.shape[:2]
poses = json.load(open(posesf)); C = np.median(np.array([v[0] for v in poses.values()]), axis=0); print('camera mediane', np.round(C, 0))
R = '/Users/alexandreleblanc/Downloads/gtamaplib-main/gtamapdata/'; LM = json.load(open(R + 'landmarks.json')); M = json.load(open(R + 'building_meshes_procedural.json'))
# silhouettes V16 de l'emprise
V = cv2.imread('/Users/alexandreleblanc/Downloads/gtamaplib-main/maps/yanis,16svg.png'); u0, v0 = int(X0 + 16991), int(11008 - Y1)
crop = V[v0:v0 + int(GH * res), u0:u0 + int(GW * res)]; sil = np.all(crop == (176, 176, 176), axis=2).astype(np.uint8)
n, lab, st, cen = cv2.connectedComponentsWithStats(sil, 8); hcomp = {}
def tag(x, y, h):
    u, v = int(x - X0), int(Y1 - y)
    if 0 <= u < lab.shape[1] and 0 <= v < lab.shape[0] and lab[v, u] > 0: hcomp[lab[v, u]] = max(hcomp.get(lab[v, u], 0), h)
for k, v in LM.items():
    X = v.get('xyz')
    if X:
        g = float(HR.ground(np.array([X[0]]), np.array([X[1]]))[0])
        if X[2] - g >= HT: tag(X[0], X[1], X[2] - g)
for k, mm in M.items():
    E = np.array(mm['world_edges'], float); zt, zb = E[:, :, 2].max(), E[:, :, 2].min()
    if zt - zb >= HT:
        for p in E[:, 0, :2][::5]: tag(p[0], p[1], zt - zb)
polys = []
for i, h in hcomp.items():
    cs, _ = cv2.findContours((lab == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cs: polys.append((c.reshape(-1, 2).astype(float) + [u0 - 16991 + 0.5, 0], h, 'v16'))
for f in hfiles:
    for k, r in json.load(open(f)).items():
        if r['h'] >= HT: polys.append((np.array(r['poly'], float), r['h'], 'est'))
mask = np.zeros((GH, GW), np.uint8); nb = 0
for poly, h, src in polys:
    if src == 'v16': wx = poly[:, 0]; wy = 11008 - (poly[:, 1] + v0) - 0.5
    else: wx, wy = poly[:, 0], poly[:, 1]
    g = float(HR.ground(np.array([wx.mean()]), np.array([wy.mean()]))[0]); z = g + h
    t = (C[2] - g) / max(C[2] - z, 1.0)                     # facteur de projection du toit au sol depuis la camera
    px = C[0] + (wx - C[0]) * t; py = C[1] + (wy - C[1]) * t
    pts = np.c_[np.r_[wx, px], np.r_[wy, py]]; pix = np.c_[(pts[:, 0] - X0) / res, (Y1 - pts[:, 1]) / res].astype(np.int32)
    hull = cv2.convexHull(pix); cv2.fillConvexPoly(mask, hull, 1); nb += 1
mask = cv2.dilate(mask, np.ones((int(16 / res) + 1,) * 2, np.uint8))
before = (o.sum(axis=2) > 0).mean(); o[mask > 0] = 0; after = (o.sum(axis=2) > 0).mean()
cv2.imwrite(out, o); print('%d batiments hauts (>= %.0f m); couverture %.1f%% -> %.1f%% -> %s' % (nb, HT, 100 * before, 100 * after, out))
