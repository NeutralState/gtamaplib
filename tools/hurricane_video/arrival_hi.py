"""arrival_hi.py — sea-level rise to the top of the map: per heightmap cell the level (m) at which the connected sea reaches it
(0.1 m steps to 25 m, then 0.5 m to 410 m) -> WORK/arrival_hi.npy; buildings / land-left curve and the level at which each
region is fully under -> WORK/arrival_hi.json. ESTIMATED: game heightmap, still water, no levees."""
import sys, os, json, numpy as np
from common import REPO, WORK
sys.path.insert(0, os.path.join(REPO, 'tools')); import hurricane_surge as hs
sea = hs.ocean_mask(); land = hs.VALID & ~sea
NPY = os.path.join(WORK, 'arrival_hi.npy')
levels = list(np.round(np.arange(0.1, 25.0001, 0.1), 2)) + list(np.arange(25.5, 410.01, 0.5))
if os.path.exists(NPY): A = np.load(NPY)
else:
    A = np.full(hs.Z.shape, np.inf, np.float32); A[sea] = 0
    for lv in levels:
        f = hs.flood(lv, sea); A[f & np.isinf(A)] = lv
    np.save(NPY, A)
B = hs.buildings(); bxy = np.array([b[1] for b in B]); bu, bv = hs.xy_cell(bxy[:, 0], bxy[:, 1])
ab = A[bv, bu]; barr = np.where(ab > 0, ab + 0.3, np.inf)       # flooded when the water is 0.3 m deep at its centroid; centroid on open sea = not counted
P, R = hs.regions(); iv, iu = np.nonzero(land); cx, cy = hs.cell_xy(iu, iv)
creg = np.array(hs.nearest_region(P, R, np.c_[cx, cy])); carr = A[iv, iu]
curve = []
for lv in [0] + levels:
    curve.append([float(lv), int((barr <= lv).sum()), round(float(100.0 * (carr > lv).sum() / len(carr)), 3)])
mil = {}
for r in sorted(set(creg.tolist())):
    a = np.sort(carr[creg == r]); a = a[np.isfinite(a)]
    if len(a) * hs.CELL ** 2 / 1e6 < 0.8: continue
    mil[r] = {'km2': round(len(a) * hs.CELL ** 2 / 1e6, 2), 'p50': float(np.percentile(a, 50)), 'p99': float(np.percentile(a, 99)), 'max': float(a.max())}
peak = np.unravel_index(np.argmax(np.where(land, hs.Z, -1e9)), hs.Z.shape)
out = {'curve': curve, 'regions': mil, 'peak_xy': [float(v) for v in hs.cell_xy(peak[1], peak[0])], 'peak_z': float(hs.Z[peak]),
       'buildings_total': len(B), 'buildings_land': int(np.isfinite(barr).sum()), 'land_median_z': float(np.median(hs.Z[land]))}
json.dump(out, open(os.path.join(WORK, 'arrival_hi.json'), 'w'))
for r, v in sorted(mil.items(), key=lambda kv: kv[1]['max']): print('%-32s %6.2f km2  p50 %6.1f  max %6.1f' % (r, v['km2'], v['p50'], v['max']))
print('peak', out['peak_xy'], out['peak_z'], 'land buildings', out['buildings_land'])
