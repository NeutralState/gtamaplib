#!/usr/bin/env python3
"""export_named_footprints.py — GeoJSON des structures nommees (nom -> empreinte -> hauteur). [NAMED-FP-V1 2026-09-30]

Pour chaque mesh de building_meshes_procedural.json: empreinte = polygone V16 (v16_footprints.json) qui contient le
centre de la base du mesh et dont l'aire est compatible (0.4..2.5 x l'emprise du mesh); sinon enveloppe convexe de la
base du mesh (source 'mesh_base'). Les ponts (Bridge/Viaduct) = LineString de l'axe (tablier) avec largeur.
Coordonnees: metres monde du jeu (meme repere que la V16 georef: x = px - 16991, y = 11008 - py).
Usage: python3 tools/export_named_footprints.py [out.geojson]
"""
import json, os, re, sys
import numpy as np
from scipy.spatial import ConvexHull

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda f: os.path.join(ROOT, 'gtamapdata', f)
LONG = re.compile(r'Bridge|Viaduct|Causeway', re.I)


def inside(pt, ring):
    x, y = pt; r = np.asarray(ring); n = len(r); c = False
    for i in range(n):
        x1, y1 = r[i]; x2, y2 = r[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1: c = not c
    return c


def area(ring):
    r = np.asarray(ring); return 0.5 * abs(np.dot(r[:, 0], np.roll(r[:, 1], 1)) - np.dot(r[:, 1], np.roll(r[:, 0], 1)))


def main(out):
    M = json.load(open(D('building_meshes_procedural.json')))
    F = json.load(open(D('v16_footprints.json')))['polygons']
    F = [f for f in F if f.get('cat') in ('building', 'structure') and f['area'] < 60000]
    C = np.array([f['centroid'] for f in F])
    feats = []
    for name, v in M.items():
        E = np.asarray(v.get('world_edges') or [], float)
        if not len(E): continue
        P = E.reshape(-1, 3); zmin, zmax = float(P[:, 2].min()), float(P[:, 2].max())
        props = {'name': name, 'height_top_m': round(zmax, 1), 'z_base_m': round(zmin, 1), 'color': v.get('color'),
                 'note': (v.get('note') or '')[:300]}
        if LONG.search(name):
            top = P[np.abs(P[:, 2] - P[:, 2].max()) < 60]; xy = top[:, :2]; c = xy.mean(0)
            u = np.linalg.svd(xy - c, full_matrices=False)[2][0]; s = (xy - c) @ u; w = (xy - c) @ np.array([-u[1], u[0]])
            pts = []
            for s0 in np.linspace(s.min(), s.max(), 12):
                m = np.abs(s - s0) < (s.max() - s.min()) / 20 + 1
                if m.sum(): pts.append((c + u * s0 + np.array([-u[1], u[0]]) * np.median(w[m])).round(2).tolist())
            props.update(kind='bridge', width_m=round(float(np.percentile(w, 97) - np.percentile(w, 3)), 1), footprint_source='mesh_axis')
            feats.append({'type': 'Feature', 'properties': props, 'geometry': {'type': 'LineString', 'coordinates': pts}})
            continue
        base = P[P[:, 2] < zmin + 3][:, :2]
        if len(base) < 3: base = P[:, :2]
        try: hull = base[ConvexHull(base).vertices]
        except Exception: continue
        ctr = hull.mean(0); ha = area(hull)
        best = None
        for i in np.argsort(np.hypot(*(C - ctr).T))[:25]:
            f = F[i]
            if inside(ctr, f['ring']) and 0.4 < f['area'] / max(ha, 1) < 2.5:
                if best is None or abs(np.log(f['area'] / ha)) < abs(np.log(best['area'] / ha)): best = f
        if best:
            ring = best['ring']; props.update(kind='building', v16_polygon_id=best['id'], footprint_source='v16')
        else:
            ring = hull.round(2).tolist(); props.update(kind='building', v16_polygon_id=None, footprint_source='mesh_base')
        ring = [list(map(float, p)) for p in ring]; ring.append(ring[0])
        props['footprint_area_m2'] = round(area(ring[:-1]), 0)
        feats.append({'type': 'Feature', 'properties': props, 'geometry': {'type': 'Polygon', 'coordinates': [ring]}})
    fc = {'type': 'FeatureCollection', 'name': 'gtavi_named_structures',
          'crs_note': 'GTA VI world metres (x east, y north); V16 georef x = px - 16991, y = 11008 - py',
          'features': feats}
    json.dump(fc, open(out, 'w'), indent=1)
    from collections import Counter
    print(len(feats), 'features', Counter(f['properties']['kind'] + '/' + f['properties']['footprint_source'] for f in feats))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else D('named_structures.geojson'))
