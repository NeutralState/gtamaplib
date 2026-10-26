"""peaks.py [--min-prom 15] — every summit of Leonida on the game heightmap, ranked: elevation, topographic prominence (height above
the highest col linking it to higher ground) and isolation (distance to the nearest higher point), named after the nearest GTADB
location (tools/generated/gtadb_locations.json; 'Mount', 'Hill', 'Peak', 'Ridge' names preferred within 1.5 km).
Heightmap: GTA6HeightMap_L16 (horizon_resect.HM, z = 706.07 HM - 301.01, ~12 m cells); land = not open sea (hurricane_surge.ocean_mask).
Prominence by a descending flood (union-find): the lower summit of two merging components gets prominence = its height - the merge height.
Output: tools/generated/peaks/peaks.json + peaks.md. ESTIMATED where the heightmap itself is inferred."""
import sys, os, json, argparse, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE); sys.path.insert(0, HERE)
import hurricane_surge as hs
ap = argparse.ArgumentParser(); ap.add_argument('--min-prom', type=float, default=15.0); ap.add_argument('--top', type=int, default=40); a = ap.parse_args()
OUT = os.path.join(HERE, 'generated', 'peaks'); os.makedirs(OUT, exist_ok=True)
Z = hs.Z.astype(np.float64); land = hs.VALID & ~hs.ocean_mask()
Zl = np.where(land, Z, -1e9); Hh, Ww = Z.shape
order = np.argsort(-Zl, axis=None); parent = np.full(Z.size, -1, np.int64); top = {}       # root -> (peak index, peak z)
def find(i):
    r = i
    while parent[r] != r: r = parent[r]
    while parent[i] != r: parent[i], i = r, parent[i]
    return r
prom = {}; col = {}
for i in order:
    z = Zl.flat[i]
    if z < 0.5: break
    parent[i] = i; top[i] = (i, z); y, x = divmod(int(i), Ww)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
        yy, xx = y + dy, x + dx
        if not (0 <= yy < Hh and 0 <= xx < Ww): continue
        j = yy * Ww + xx
        if parent[j] < 0: continue
        ri, rj = find(i), find(j)
        if ri == rj: continue
        (pi, zi), (pj, zj) = top[ri], top[rj]
        lo, hi = ((pi, zi), (pj, zj)) if zi < zj else ((pj, zj), (pi, zi))
        prom[lo[0]] = lo[1] - z; col[lo[0]] = (int(i), float(z))                  # the lower summit dies here
        parent[ri] = rj; top[rj] = hi; top.pop(ri, None)
for r, (p, z) in top.items(): prom.setdefault(p, z); col.setdefault(p, (None, 0.0))   # island high points: prominence = height
peaks = [(p, v) for p, v in prom.items() if v >= a.min_prom]
G = json.load(open(os.path.join(HERE, 'generated', 'gtadb_locations.json')))
L = [(str(e[0]), np.array(e[1][:2], float)) for e in G.values() if isinstance(e, list) and len(e) > 1 and e[1] and len(e[1]) >= 2]
def name_for(xy):
    best = None
    for n, q in L:
        d = float(np.hypot(*(q - xy))); key = d - (1200 if any(w in n for w in ('Mount', 'Mt.', 'Hill', 'Peak', 'Ridge', 'Summit')) and d < 1500 else 0)
        if best is None or key < best[0]: best = (key, d, n)
    return best[2], best[1]
hi_cells = np.argwhere(land & (Z > 0))
rows = []
for p, v in peaks:
    y, x = divmod(int(p), Ww); xy = np.array(hs.cell_xy(x, y), float); z = float(Z[y, x])
    hp = np.argwhere(land & (Z > z + 0.01))                                           # isolation: nearest higher land
    iso = float(np.min(np.hypot(hp[:, 0] - y, hp[:, 1] - x)) * hs.CELL) if len(hp) else None
    nm, d = name_for(xy); cy, cx = divmod(col[p][0], Ww) if col[p][0] is not None else (None, None)
    rows.append(dict(name=nm, name_dist_m=round(d), x=round(float(xy[0]), 1), y=round(float(xy[1]), 1), z=round(z, 1), prominence=round(float(v), 1),
                     isolation_m=None if iso is None else round(iso), col_z=round(col[p][1], 1),
                     col_xy=None if cx is None else [round(float(c), 1) for c in hs.cell_xy(cx, cy)]))
rows.sort(key=lambda r: -r['z'])
json.dump(rows, open(os.path.join(OUT, 'peaks.json'), 'w'), indent=1)
with open(os.path.join(OUT, 'peaks.md'), 'w') as f:
    f.write('| # | Summit (nearest GTADB name) | Elevation m | Prominence m | Isolation km | x, y |\n|---|---|---|---|---|---|\n')
    for k, r in enumerate(rows[:a.top]):
        f.write('| %d | %s | %.0f | %.0f | %s | %.0f, %.0f |\n' % (k + 1, r['name'], r['z'], r['prominence'], '-' if r['isolation_m'] is None else '%.2f' % (r['isolation_m'] / 1000), r['x'], r['y']))
print('%d summits with prominence >= %.0f m' % (len(rows), a.min_prom))
for k, r in enumerate(rows[:a.top]): print('%2d  %6.1f m  prom %6.1f  iso %5s km  %-55s (%4d m)  (%.0f, %.0f)' % (k + 1, r['z'], r['prominence'], '-' if r['isolation_m'] is None else '%.2f' % (r['isolation_m'] / 1000), r['name'][:55], r['name_dist_m'], r['x'], r['y']))
