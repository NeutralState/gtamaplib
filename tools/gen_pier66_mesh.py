#!/usr/bin/env python3
"""gen_pier66_mesh.py — Pier Sixty-Six hotel, Waning Sands (GTADB L1977). [PIER66-V1 2026-10-13]

Identification: GTADB L1977 "?, Waning Sands" (hotel) = IRL Pier Sixty-Six / Hyatt Regency Pier Sixty-Six,
2301 SE 17th St, Fort Lauderdale (OSM way 272811104, tourism=hotel). Alexandre pointed it out on the latest V16.
Plan: the latest V16 (gtadb tiles yanis,16 z6, 0.5 m/px, fetched 2026-10-13; our local yanis,16svg.png predates
the buildings here). Tile frame -> our V16 frame: +9.0 m E, +8.0 m N (water and pier edges, NCC 0.994, exact
overlay over the whole 384 m crop). The hotel is the GTADB-highlighted lot (5468 m2); its V16 roof drawing has a
round tower: a core circle r 9.7 m and an outer ring r 16.5 m with radial room partitions.
Height: no measured or published height. IRL tower = 17 floors (Wikipedia; skydb) -> 17 x 3.2 m = 54.4 m, the
project rule for an IRL height given only as levels. The 221 ft overall figure (photo-site database, likely to the
spire) is not used; the revolving Pier Top lounge and spire are NOT modelled. Rest of the lot = podium 12 m
ESTIMATED (gtadb_meshes convention). Ground = heightmap. Not checked in any camera frame.
The U of low buildings around the pool/marina (same V16, grey) is NOT part of this mesh.
Usage: python3 tools/gen_pier66_mesh.py [--apply]
"""
import json, math, os, shutil, sys
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS)
from horizon_resect import ground

NAME = 'Pier Sixty-Six'
MESHES = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
# V16 lot outline (our frame), traced from the latest V16 at 0.5 m/px, simplified to 0.7 m
OUTER = [[346.25, 3582.75], [346.25, 3570.75], [349.25, 3570.75], [350.75, 3569.25], [350.75, 3552.25], [349.75, 3551.25],
         [344.75, 3551.25], [343.25, 3549.75], [328.75, 3549.75], [328.75, 3529.25], [344.75, 3528.75], [345.75, 3527.75],
         [345.75, 3503.25], [328.75, 3485.75], [328.75, 3473.25], [336.75, 3464.75], [336.75, 3432.75], [341.75, 3427.75],
         [374.25, 3427.75], [374.75, 3435.75], [377.75, 3438.75], [378.25, 3445.25], [380.75, 3447.75], [381.25, 3462.75],
         [380.75, 3463.75], [376.75, 3464.25], [376.75, 3476.25], [380.75, 3482.25], [380.75, 3483.25], [378.75, 3484.25],
         [378.75, 3487.75], [376.75, 3490.75], [376.75, 3498.75], [380.75, 3499.25], [380.75, 3502.75], [376.75, 3507.25],
         [376.75, 3520.75], [374.25, 3523.75], [374.25, 3534.75], [371.75, 3538.25], [371.75, 3545.75], [369.25, 3548.25],
         [369.25, 3561.25], [366.25, 3561.75], [365.75, 3559.25], [362.75, 3559.75], [362.75, 3582.75]]
TOWER_C, TOWER_R, N_SEG = (358.94, 3482.91), 16.5, 48
PODIUM_H, FLOORS, FLOOR_H = 12.0, 17, 3.2


def build():
    E = []
    def seg(a, b): E.append([[round(float(v), 2) for v in a], [round(float(v), 2) for v in b]])
    def prism(ring, z0, z1):
        for k in range(len(ring)):
            a, b = ring[k], ring[(k + 1) % len(ring)]
            seg([*a, z0], [*b, z0]); seg([*a, z1], [*b, z1]); seg([*a, z0], [*a, z1])
    g = float(ground(*[sum(c) / len(OUTER) for c in zip(*OUTER)]))
    tower = [[TOWER_C[0] + TOWER_R * math.cos(2 * math.pi * k / N_SEG), TOWER_C[1] + TOWER_R * math.sin(2 * math.pi * k / N_SEG)] for k in range(N_SEG)]
    hh = FLOORS * FLOOR_H
    prism(OUTER, g, g + PODIUM_H); prism(tower, g + PODIUM_H, g + hh)
    note = ('PIER66-V1 2026-10-13 (Alexandre: add the Pier Sixty-Six hotel in Waning Sands, shown on the latest V16): '
            'GTADB L1977 = IRL Pier Sixty-Six (Hyatt Regency Pier Sixty-Six, 2301 SE 17th St, Fort Lauderdale; OSM way 272811104). '
            'Plan = latest V16 lot (gtadb tiles yanis,16 z6; tile frame +9.0 m E +8.0 m N to ours, water/pier overlay NCC 0.994), 5468 m2. '
            'Tower = the round V16 roof drawing: outer ring r %.1f m (core circle r 9.7 m, radial room partitions), centre (%.1f, %.1f). '
            'Tower roof %.1f m = IRL 17 floors x %.1f m (Wikipedia, skydb; no published height; the 221 ft overall figure from a photo database not used); '
            'revolving Pier Top lounge and spire NOT modelled. Rest of the lot = podium %.0f m ESTIMATED. Ground %.1f (heightmap). '
            'Not checked in any camera frame (identification + IRL floor count only). The grey U of low buildings around it is not included.'
            % (TOWER_R, TOWER_C[0], TOWER_C[1], hh, FLOOR_H, PODIUM_H, g))
    return {'color': '#cbd5e1', 'world_edges': E, 'name_game': None, 'name_irl': 'Pier Sixty-Six', 'gtadb': 'L1977',
            '_credit': 'identification: GTA VI Landmarks Data (CC BY 4.0) https://map.gtadb.org; plan: V16 (yanis); height: IRL floor count (Wikipedia)',
            'note': note}, g, hh


def main():
    m, g, hh = build()
    print('%s: %d edges, ground %.1f, podium to %.1f, tower to %.1f' % (NAME, len(m['world_edges']), g, g + PODIUM_H, g + hh))
    if '--apply' in sys.argv:
        M = json.load(open(MESHES))
        shutil.copy(MESHES, MESHES + '.bak_pier66')
        M[NAME] = m
        tmp = MESHES + '.tmp'; json.dump(M, open(tmp, 'w'), indent=1, ensure_ascii=True); os.replace(tmp, MESHES)
        print('applied ->', len(M), 'meshes')


if __name__ == '__main__':
    main()
