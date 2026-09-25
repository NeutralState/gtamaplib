"""DSM batiments a partir des meshs proceduraux (building_meshes_procedural.json):
- niveaux horizontaux de chaque mesh (points a la meme cote) -> enveloppe convexe par niveau -> raster de hauteur (max)
- points 'murs' (contour de chaque niveau, echantillonne le long et en hauteur) = occulteurs pour le z-buffer.
build_dsm(xs, ys) -> (dsm HxW en z absolu ou -inf, walls Nx3)"""
import json, numpy as np, cv2
MESH = '/Users/alexandreleblanc/Downloads/gtamaplib-main/gtamapdata/building_meshes_procedural.json'
def levels(E, tol=0.4):
    pts = E.reshape(-1, 3); zs = np.round(pts[:, 2] / tol) * tol; out = []
    for z in np.unique(zs):
        p = pts[np.abs(pts[:, 2] - z) < tol][:, :2]; p = np.unique(np.round(p, 2), axis=0)
        if len(p) < 3: continue
        hull = cv2.convexHull(p.astype(np.float32)).reshape(-1, 2)
        if cv2.contourArea(hull.astype(np.float32)) < 4: continue
        out.append((float(z), hull))
    return out
def build_dsm(xs, ys, res, zmin_ground=None, names=None):
    M = json.load(open(MESH)); GW, GH = len(xs), len(ys); X0, Y1 = xs[0], ys[0]
    dsm = np.full((GH, GW), -np.inf, np.float32); walls = []
    for name, m in M.items():
        if names and name not in names: continue
        E = np.array(m['world_edges'], float)
        if E[:, :, 0].max() < xs[0] - 50 or E[:, :, 0].min() > xs[-1] + 50 or E[:, :, 1].max() < ys[-1] - 50 or E[:, :, 1].min() > ys[0] + 50: continue
        lv = levels(E)
        if not lv: continue
        zb = min(z for z, _ in lv); ztop = max(z for z, _ in lv)
        for z, hull in lv:
            if z <= zb + 0.5: continue           # le niveau du sol n'eleve rien
            poly = np.c_[(hull[:, 0] - X0) / res, (Y1 - hull[:, 1]) / res].astype(np.int32)
            layer = np.zeros((GH, GW), np.uint8); cv2.fillPoly(layer, [poly], 1)
            dsm[layer > 0] = np.maximum(dsm[layer > 0], z)
            # murs: contour du niveau, du bas du mesh jusqu'a z
            if z < ztop - 0.5 and (ztop - z) < 0.5 * (ztop - zb): continue   # murs: sommet + gros decrochements seulement (evite 14 M de points)
            per = np.r_[hull, hull[:1]]
            for a, b in zip(per[:-1], per[1:]):
                L = np.linalg.norm(b - a); n = max(2, int(L / 2.0))
                seg = a[None, :] + (b - a)[None, :] * np.linspace(0, 1, n)[:, None]
                hz = np.arange(zb, z, 2.0)
                walls.append(np.c_[np.repeat(seg, len(hz), axis=0), np.tile(hz, len(seg))])
    walls = np.concatenate(walls) if walls else np.zeros((0, 3))
    return dsm, walls

# ---- DSM depuis les silhouettes V16 (remplissage batiment = BGR 176,176,176 exact) ----
V16 = '/Users/alexandreleblanc/Downloads/gtamaplib-main/maps/yanis,16svg.png'
LMS = '/Users/alexandreleblanc/Downloads/gtamaplib-main/gtamapdata/landmarks.json'
def build_dsm_v16(xs, ys, res, ground_fn, default_h=12.0, min_area=30):
    """dsm (z absolu ou -inf) + murs, pour TOUS les batiments dessines sur la V16 dans l'emprise.
    hauteur = max(z landmark - sol) des landmarks tombant dans la silhouette, sinon default_h."""
    X0, X1, Y0, Y1 = xs[0], xs[-1] + res, ys[-1] - res, ys[0]
    V = cv2.imread(V16); u0, u1 = int(X0 + 16991), int(X1 + 16991) + 1; v0, v1 = int(11008 - Y1), int(11008 - Y0) + 1
    u0c, v0c = max(0, u0), max(0, v0); crop = V[v0c:min(V.shape[0], v1), u0c:min(V.shape[1], u1)]
    mask = np.all(crop == (176, 176, 176), axis=2).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask, 8)
    LM = json.load(open(LMS)); lm = [(v['xyz'][0], v['xyz'][1], v['xyz'][2]) for v in LM.values() if v.get('xyz') and v['xyz'][2] > 12]
    lmx = np.array([a[0] for a in lm]); lmy = np.array([a[1] for a in lm]); lmz = np.array([a[2] for a in lm])
    lu = (lmx + 16991 - u0c).astype(int); lv = (11008 - lmy - v0c).astype(int)
    inside = (lu >= 0) & (lu < mask.shape[1]) & (lv >= 0) & (lv < mask.shape[0])
    comp_of_lm = np.full(len(lm), 0); comp_of_lm[inside] = lab[lv[inside], lu[inside]]
    GW, GH = len(xs), len(ys); dsm = np.full((GH, GW), -np.inf, np.float32); walls = []; nb = 0
    Hm = np.zeros(n, np.float32)
    for i in range(1, n):
        if st[i, 4] < min_area: continue
        cx, cy = cen[i]; wx, wy = cx + u0c - 16991, 11008 - (cy + v0c); g = float(ground_fn(np.array([wx]), np.array([wy]))[0])
        sel = comp_of_lm == i; h = float((lmz[sel] - g).max()) if sel.any() else default_h
        if h <= 0: continue                    # pas de hauteur connue et defaut 0 -> pas de toit ni de mur
        Hm[i] = g + h; nb += 1
    zmap = Hm[lab]; zmap[lab == 0] = -np.inf                       # z absolu par pixel V16 (1 m)
    # transfert vers la grille ortho (res m): nearest
    gx = ((xs - (u0c - 16991)) ).astype(int); gy = ((11008 - v0c) - ys).astype(int)
    okx = (gx >= 0) & (gx < zmap.shape[1]); oky = (gy >= 0) & (gy < zmap.shape[0])
    sub = zmap[np.clip(gy, 0, zmap.shape[0] - 1)][:, np.clip(gx, 0, zmap.shape[1] - 1)]
    sub[~oky, :] = -np.inf; sub[:, ~okx] = -np.inf; dsm = sub.astype(np.float32)
    # murs: contours des composantes, echantillonnes tous les 1 m et en hauteur
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        if cv2.contourArea(c) < min_area: continue
        c = cv2.approxPolyDP(c, 1.0, True).reshape(-1, 2).astype(float)
        i = lab[int(c[0, 1]), int(c[0, 0])]
        if i <= 0 or Hm[i] <= 0: continue
        wx = c[:, 0] + u0c - 16991; wy = 11008 - (c[:, 1] + v0c); g = float(ground_fn(np.array([wx.mean()]), np.array([wy.mean()]))[0])
        per = np.c_[np.r_[wx, wx[:1]], np.r_[wy, wy[:1]]]; hz = np.arange(g, Hm[i], 1.0)
        for a, b in zip(per[:-1], per[1:]):
            L = np.linalg.norm(b - a); m_ = max(2, int(L / 1.0)); seg = a[None, :] + (b - a)[None, :] * np.linspace(0, 1, m_)[:, None]
            walls.append(np.c_[np.repeat(seg, len(hz), axis=0), np.tile(hz, len(seg))])
    walls = np.concatenate(walls) if walls else np.zeros((0, 3))
    print('DSM V16: %d batiments, %d avec hauteur landmark' % (nb, int((Hm > 0).sum() - (np.array([not (comp_of_lm == i).any() for i in range(n)])[Hm > 0]).sum())), flush=True)
    return dsm, walls


# ---- hauteurs estimees depuis la video (heights.py) : env HEIGHTS=fichier1.json,fichier2.json ; HCONF = confiance minimale
def build_dsm_est(xs, ys, res, ground_fn, files, hconf=2.5):
    import os
    GW, GH = len(xs), len(ys); X0, Y1 = xs[0], ys[0]; dsm = np.full((GH, GW), -np.inf, np.float32); walls = []; nb = 0
    for f in files:
        if not os.path.exists(f): continue
        for k, r in json.load(open(f)).items():
            if r['conf'] < hconf or r['h'] < 3: continue
            poly = np.array(r['poly'], float); g = float(ground_fn(np.array([r['cx']]), np.array([r['cy']]))[0]); z = g + r['h']
            pix = np.c_[(poly[:, 0] - X0) / res, (Y1 - poly[:, 1]) / res].astype(np.int32)
            if pix[:, 0].max() < 0 or pix[:, 1].max() < 0 or pix[:, 0].min() >= GW or pix[:, 1].min() >= GH: continue
            layer = np.zeros((GH, GW), np.uint8); cv2.fillPoly(layer, [pix], 1); dsm[layer > 0] = np.maximum(dsm[layer > 0], z); nb += 1
            per = np.r_[poly, poly[:1]]; hz = np.arange(g, z, 1.0)
            for a, b_ in zip(per[:-1], per[1:]):
                L = np.linalg.norm(b_ - a); m_ = max(2, int(L / 1.0)); seg = a[None, :] + (b_ - a)[None, :] * np.linspace(0, 1, m_)[:, None]
                walls.append(np.c_[np.repeat(seg, len(hz), axis=0), np.tile(hz, len(seg))])
    walls = np.concatenate(walls) if walls else np.zeros((0, 3)); print('DSM estime (video): %d batiments' % nb, flush=True)
    return dsm, walls
