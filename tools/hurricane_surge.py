"""hurricane_surge.py — HURRICANE-V1: storm-surge flooding of Leonida on the game heightmap.

For each surge level (metres above the sea, z 0) the flooded land is the set of heightmap cells below the level that are
CONNECTED to the open sea (4-connectivity flood fill from the ocean; closed inland basins stay dry, like a real surge). Each
cell is ~12 m (heightmap L16, 0.0832 px/m). Land = cells the V17 base map does not draw as water (map_water). Regions: every cell / building takes the region of its nearest GTADB landmark
(third field of tools/generated/gtadb_locations.json: Vice Beach, Vice City, Leonida Keys, ...), approximate at borders.
Buildings: mesh solids (tools/mesh_solids.py) + V16 massing boxes; a building floods when its footprint centroid is in the
flood and the water depth there exceeds 0.3 m.

Outputs (tools/generated/hurricane/): surge_stats.json, flood_<level>m.png masks (uint8, heightmap grid), and arrival.png +
arrival.json (the level at which the sea reaches each cell, up to 74 m, see encode_arrival) used by view3d's sea shader;
surge_curve.json: buildings flooded and % land per 0.1 m (video counters). ESTIMATED: the heightmap is the game's terrain (no levees, no drainage, still water).
"""
import json, os, sys, numpy as np, cv2
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
from horizon_resect import HM, SC, ZX, ZY
OUT = os.path.join(THIS, 'generated', 'hurricane'); os.makedirs(OUT, exist_ok=True)
LEVELS = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0, 15.0, 20.0]   # 7.5-20 m: extreme scenario (far beyond any recorded surge)
Z = 706.07 * HM - 301.01                                         # terrain z per heightmap cell
VALID = HM > 0.005                                               # cells outside the data
CELL = 1.0 / SC                                                  # metres per cell
def cell_xy(iu, iv): return (iu - ZX) / SC, (ZY - iv) / SC
def xy_cell(x, y): return np.clip(np.round(ZX + np.asarray(x) * SC).astype(int), 0, Z.shape[1] - 1), np.clip(np.round(ZY - np.asarray(y) * SC).astype(int), 0, Z.shape[0] - 1)


def map_water():
    """cells the V17 base map draws as water (blue: b > r + 40 and b > g + 8), sampled at each heightmap cell centre from the local
    tile cache (vendor/gtadb.org/maps/tiles/6/yanis,17/5, 1 m/px, tile frame = our frame). The game heightmap keeps shallow banks
    and flats slightly above 0 m where the map shows sea: without this mask they count as flooded land."""
    cache = os.path.join(THIS, 'generated', 'hurricane', 'map_water.png')
    if os.path.exists(cache): return cv2.imread(cache, 0) > 0
    T = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,17', '5')
    iv, iu = np.mgrid[0:Z.shape[0], 0:Z.shape[1]]; x, y = cell_xy(iu.ravel(), iv.ravel())
    px, py = 16384 + x, 16384 - y; tx, ty = (px // 256).astype(int), (py // 256).astype(int)
    W = np.zeros(px.shape, bool); key = tx * 100000 + ty
    order = np.argsort(key); ks = key[order]; cuts = np.r_[0, np.nonzero(np.diff(ks))[0] + 1, len(ks)]
    for a, b in zip(cuts[:-1], cuts[1:]):
        idx = order[a:b]; tp = os.path.join(T, '5,%d,%d.jpg' % (ty[idx[0]], tx[idx[0]])); t = cv2.imread(tp) if os.path.exists(tp) else None
        if t is None: W[idx] = True; continue                      # no tile: open sea around the map
        u = np.clip((px[idx] - tx[idx] * 256).astype(int), 0, 255); v = np.clip((py[idx] - ty[idx] * 256).astype(int), 0, 255)
        bgr = t[v, u].astype(int); W[idx] = (bgr[:, 0] > bgr[:, 2] + 40) & (bgr[:, 0] > bgr[:, 1] + 8)
    W = W.reshape(Z.shape); cv2.imwrite(cache, (W * 255).astype(np.uint8)); return W


def ocean_mask():
    """open sea = cells at or below 0 m, or drawn as water on the V17 map, connected to the grid border."""
    wet = ((Z <= 0.0) | ~VALID | map_water()).astype(np.uint8)
    n, lab = cv2.connectedComponents(wet, connectivity=4)
    border = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]]).tolist()) - {0}
    return np.isin(lab, list(border)) & (wet > 0)


def flood(level, sea):
    low = ((Z < level) | sea).astype(np.uint8)
    n, lab = cv2.connectedComponents(low, connectivity=4)
    ids = np.unique(lab[sea]); ids = ids[ids > 0]
    return np.isin(lab, ids) & ~sea & VALID


def regions():
    G = json.load(open(os.path.join(THIS, 'generated', 'gtadb_locations.json')))
    P, R = [], []
    for e in G.values():
        if not isinstance(e, list) or len(e) < 2 or not e[1] or len(e[1]) < 2: continue
        parts = [s.strip() for s in str(e[0]).split(',')]
        reg = parts[-1] if parts and parts[-1] not in ('', '?') else None
        if reg: P.append(e[1]); R.append(reg)
    return np.array(P, float), R


def nearest_region(P, R, xy):
    from scipy.spatial import cKDTree
    _, i = cKDTree(P).query(np.atleast_2d(xy)); return [R[j] for j in i]


def buildings():
    import mesh_solids
    out = []
    for name, so in mesh_solids.cached().items():
        pts = [q for L in so['layers'] for p in L['polys'] for q in p['outer']]
        if pts: out.append((name, np.mean(pts, axis=0), so['zmax'] - so['zmin']))
    for i, m in enumerate(json.load(open(os.path.join(THIS, 'threejs', '_v16_massing.json')))):
        out.append(('V16 building #%d' % (i + 1), np.mean(np.array(m['o'], float), axis=0), m['h']))
    return out


def arrival_map(sea):
    """per cell: the lowest sea level at which the connected flood reaches it (0.1 m steps to 20 m, 1 m steps to 74 m), inf = never;
    sea = 0. Encoded for view3d's sea shader by encode_arrival()."""
    A = np.full(Z.shape, np.inf, np.float32); A[sea] = 0
    for lv in list(np.round(np.arange(0.1, 20.0001, 0.1), 2)) + list(np.arange(21.0, 74.01, 1.0)):
        f = flood(lv, sea); A[f & np.isinf(A)] = lv
    return A


def encode_arrival(A):
    """uint8 arrival.png: v <= 200 -> v * 0.1 m (0-20 m), 201-254 -> 20 + (v - 200) m (21-74 m), 255 = never (above 74 m)."""
    v = np.where(A <= 20.0, np.round(A / 0.1), 200 + np.round(A - 20.0))
    return np.where(np.isfinite(A), np.clip(v, 0, 254), 255).astype(np.uint8)


def main():
    sea = ocean_mask(); land = VALID & ~sea
    A = arrival_map(sea); E = encode_arrival(A); cv2.imwrite(os.path.join(OUT, 'arrival.png'), E)
    cv2.imwrite(os.path.join(THIS, 'threejs', '_hurricane_arrival.png'), E)                       # served to view3d (gitignored, regenerated here)
    json.dump({'w': int(Z.shape[1]), 'h': int(Z.shape[0]), 'SC': SC, 'ZX': ZX, 'ZY': ZY, 'encoding': 'v<=200: v*0.1 m; 201-254: 20+(v-200) m; 255 never'}, open(os.path.join(OUT, 'arrival.json'), 'w'))
    P, R = regions()
    iv, iu = np.nonzero(land)
    cx, cy = cell_xy(iu, iv)
    creg = np.array(nearest_region(P, R, np.c_[cx, cy]))
    reg_names = sorted(set(creg.tolist()))
    land_area = {r: float((creg == r).sum() * CELL * CELL / 1e6) for r in reg_names}
    B = buildings(); bxy = np.array([b[1] for b in B]); bu, bv = xy_cell(bxy[:, 0], bxy[:, 1])
    breg = nearest_region(P, R, bxy)
    stats = {'cell_m': round(CELL, 2), 'land_km2': round(float(land.sum() * CELL * CELL / 1e6), 1), 'regions_land_km2': {r: round(v, 2) for r, v in land_area.items()},
             'buildings_total': len(B), 'levels': []}
    for lv in LEVELS:
        f = flood(lv, sea)
        cv2.imwrite(os.path.join(OUT, 'flood_%.1fm.png' % lv), (f * 255).astype(np.uint8))
        fr = f[iv, iu]
        per = {r: round(float(((creg == r) & fr).sum() * CELL * CELL / 1e6), 2) for r in reg_names}
        depth = lv - Z[bv, bu]
        hit = f[bv, bu] & (depth > 0.3)
        named = sorted(((B[i][0], round(float(depth[i]), 1)) for i in np.nonzero(hit)[0] if not B[i][0].startswith('V16 ')), key=lambda t: -t[1])
        bper = {}
        for i in np.nonzero(hit)[0]: bper[breg[i]] = bper.get(breg[i], 0) + 1
        stats['levels'].append({'level_m': lv, 'flooded_km2': round(float(f.sum() * CELL * CELL / 1e6), 2),
                                'flooded_pct_land': round(100.0 * f.sum() / land.sum(), 2), 'regions_km2': per,
                                'regions_pct': {r: round(100 * per[r] / land_area[r], 1) for r in reg_names if land_area[r] > 0.5},
                                'buildings_flooded': int(hit.sum()), 'buildings_by_region': bper, 'named_flooded': named[:60]})
        print('%.1f m: %.1f km2 flooded (%.1f %% of land), %d buildings' % (lv, stats['levels'][-1]['flooded_km2'], stats['levels'][-1]['flooded_pct_land'], int(hit.sum())))
    json.dump(stats, open(os.path.join(OUT, 'surge_stats.json'), 'w'), indent=1)
    curve = []                                                   # per 0.1 m: [level, buildings flooded, % land] (from the arrival map)
    for lv in np.round(np.arange(0, 20.01, 0.1), 2):
        f = (A > 0) & (A <= lv + 1e-4) & land if lv > 0 else np.zeros_like(land)
        hit = f[bv, bu] & (lv - Z[bv, bu] > 0.3)
        curve.append([float(lv), int(hit.sum()), round(float(100.0 * f.sum() / land.sum()), 2)])
    json.dump(curve, open(os.path.join(OUT, 'surge_curve.json'), 'w'))


if __name__ == '__main__':
    main()
