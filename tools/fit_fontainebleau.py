#!/usr/bin/env python3
"""fit_fontainebleau.py — the Mid-Beach Fontainebleau block (mesh 'Sorrento Tower', GTADB L11) re-fitted on T4/7. [FONTAINEBLEAU-V1 2026-10-20]

Alexandre (T4 video tour, scene 4 'Skyline at Night', pose SOLVED on the far field): the near hotel of the frame is the
whole V17 grey lot (x 1938..2020, y 1897..1962): its base corners project on the hotel's base corners and the roof line
back-projected on the lot's east / north faces gives 60.0-65.6 m (5 points), crown 72.6 m. The previous mesh was a small
V16 lot (437 m2) at 77 m (OSM height of the IRL Sorrento tower), which drew a tall box in the middle of the hotel.
New mesh: the lot prism, ground = heightmap, roof 64 m (median of the frame points); the crown and the neon are scene
props (tools/scene_props.py). Also: Soho Beach House (lot just south) brought to 50 m measured on the same frame.
Usage: python3 tools/fit_fontainebleau.py [--apply]
"""
import json, os, sys, tempfile
import numpy as np
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS)
from horizon_resect import ground
MESHES = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
LOT = [(1938.0, 1897.0), (2020.0, 1897.0), (2020.0, 1962.0), (1938.0, 1962.0)]
ROOF = 64.0


def edges():
    g = float(np.median([ground(x, y) for x, y in LOT])); E = []
    for z in (g, ROOF):
        for a, b in zip(LOT, LOT[1:] + LOT[:1]): E.append([[a[0], a[1], round(z, 2)], [b[0], b[1], round(z, 2)]])
    for a in LOT: E.append([[a[0], a[1], round(g, 2)], [a[0], a[1], ROOF]])
    return E, g


def main():
    E, g = edges(); M = json.load(open(MESHES)); m = M['Sorrento Tower']
    m['world_edges'] = E
    m['note'] = ('FONTAINEBLEAU-V1 2026-10-20: re-fitted on T4/7 Skyline at Night (pose SOLVED on the far field): footprint = the '
                 'whole V17 grey lot x 1938..2020, y 1897..1962 (its base corners project on the hotel base corners), roof %.0f m '
                 '(frame roof line back-projected on the east / north faces: 60.0-65.6 m), ground %.1f. Crown (72.6 m) and neon are '
                 'scene props. | was: ' % (ROOF, g) + (m.get('note') or '').split(' | was: ')[0])
    m['_credit'] = 'identification: GTA VI Landmarks Data (CC BY 4.0) https://map.gtadb.org; plan: V17 (yanis); height: measured on T4/7'
    # Soho Beach House (lot just south): its front block is 48.4-51.9 m on T4/7 (east face x 2020) -> 50 m (was 78.8, OSM)
    sb = M['Soho Beach House']; Es = np.asarray(sb['world_edges'], float); z0 = Es[..., 2].min(); z1 = Es[..., 2].max()
    if abs(z1 - 50.0) > 0.05:
        Es[..., 2] = z0 + (Es[..., 2] - z0) * (50.0 - z0) / (z1 - z0); sb['world_edges'] = np.round(Es, 2).tolist()
        sb['note'] = 'FONTAINEBLEAU-V1 2026-10-20: height 50 m measured on T4/7 (front block top 48.4-51.9 m on the east face x 2020; was %.1f m from OSM). | %s' % (z1, sb.get('note') or '')
    print(len(E), 'edges, ground', round(g, 2))
    if '--apply' in sys.argv:
        fd, t = tempfile.mkstemp(dir=os.path.dirname(MESHES))
        with os.fdopen(fd, 'w') as fh: json.dump(M, fh, indent=1, ensure_ascii=True)
        os.replace(t, MESHES); print('applied')


if __name__ == '__main__':
    main()
