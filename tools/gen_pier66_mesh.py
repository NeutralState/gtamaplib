#!/usr/bin/env python3
"""gen_pier66_mesh.py — Pier Sixty-Six hotel, Waning Sands (GTADB L1977). [PIER66-V1 2026-10-13]

Identification: GTADB L1977 "?, Waning Sands" (hotel) = IRL Pier Sixty-Six / Hyatt Regency Pier Sixty-Six,
2301 SE 17th St, Fort Lauderdale (OSM way 272811104, tourism=hotel). Alexandre pointed it out on the latest V16.
Plan: the latest V16 (gtadb tiles yanis,16 z6, 0.5 m/px, fetched 2026-10-13; our local yanis,16svg.png predates
the buildings here). Tile frame -> our V16 frame: +9.0 m E, +8.0 m N (water and pier edges, NCC 0.994, exact
overlay over the whole 384 m crop). The hotel is the GTADB-highlighted lot (5468 m2).
Shape (PIER66-V4, Alexandre: "make it look like the real building"; V1 was a plain cylinder on a 12 m slab):
- the round V16 roof drawing is the crown, not the shaft: the IRL aerial (Esri World Imagery, 0.27 m/px) shows the
  starburst of ~44 radial fins with tips at r 16.6 m around the drum of the revolving Pier Top lounge, r 9.7 m -
  the V16 draws the same two circles (16.5 / 9.7). Photos: a white tower with stacked cantilevered balconies, the
  finned crown wrapping its top floor and flaring up and out.
- the lot is split along the strokes the V16 draws: tower body = the hexagonal part around the crown (Y_S..Y_N),
  17 floors x 3.2 m = 54.4 m (IRL floor count, Wikipedia / skydb; project rule for levels-only heights), with floor
  lines; north part = the new hotel built just north of the tower (Gardiner: 10 storeys; a developer page says 9)
  -> 10 x 3.2 m ESTIMATED; south block = 12 m ESTIMATED (gtadb_meshes convention).
- crown: lounge drum 4 m + fins up to 9 m above the roof, leaning out ~40 deg, profile by eye from photos.
- V5: sawtooth balconies on the free facades of the tower body (photos + aerial), white.
- V6 (Alexandre's pool-side photo): slim shaft = the 34 x 29 m frame the V16 draws around the crown, with its two
  pointed bays (W, E) = the stacked angled balconies; the rest of the hexagonal part = low base; tall service slab on
  the north face 7 m above the roof with a mast to +12.6 m (67.0 m above ground ~ the 221 ft overall figure);
  two-storey lounge drum, fins leaving it at mid-height; balcony bands on the north hotel.
- V6b/c (Alexandre's 2020 photos): the pointed bays are stacks of smooth triangular balconies (no teeth); a central
  balcony bay stands proud on the long N/S faces (facade recessed 1.5 m on both sides); deeper fin dish whose rim
  rises above the drum. Limits of the 2.5D solids: no open gaps between stacked balconies, no pilotis at the base.
  Ground = heightmap.
Frame check (PIER66-V3 2026-10-13, Alexandre: "le mieux c'est biplane night"): Biplane Night (Video) v086 (Build 2026, night,
2577 m, pose RMS 8.4') shows a lone lit tower with a bright crown at the projected spot: its top-band ray passes 11-39 m from
the tower axis (left edge inside the 16.5 m ring) and reaches 58-60 m above ground there (+-6 m at 3.7 px RMS) -> consistent
with the 54.4 m IRL value, which is kept. A single camera only: no two-ray triangulation yet (the tower is visible in the video
from t~83 to 87.5 s, so a second calibrated frame would give ~4 deg of parallax). Highway (N)/(NE) (2022 build, daylight) show
empty sky where a 57 m top would be: weak evidence (older build); their dark block is a rooftop ~500 m from them near 3800 NE
Miami Ct (two-ray fix), not this tower.
Wings (PIER66-V2, Alexandre: "ajoute aussi le U de batiments autour"): separate mesh NAME_WINGS = the grey U of low
buildings east of the tower on the same V16 (one connected outline, 9132 m2, interior strokes = roof details).
Height ESTIMATED 2 floors x 3.2 = 6.4 m: before the 2019 closure the complex was mostly two-story room wings around
the tower (guest account, 2014), demolished after 2019; the game plan matches that continuous ring of wings. If the
game follows the 2024-25 rebuild instead (two 4-story Resort Residences + 11-story Azul / Indigo towers), this is wrong.
Usage: /usr/local/bin/python3 tools/gen_pier66_mesh.py [--apply]
"""
import json, math, os, shutil, sys
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS)
from horizon_resect import ground

NAME = 'Pier Sixty-Six'
NAME_WINGS = 'Pier Sixty-Six (wings)'
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
# the U of low wings around the pool (same V16, same frame)
WINGS = [[482.25, 3579.75], [478.25, 3581.25], [473.75, 3581.25], [472.75, 3579.75], [462.25, 3579.75], [461.25, 3577.75],
         [437.25, 3577.75], [436.25, 3573.75], [434.25, 3574.25], [433.75, 3577.75], [410.25, 3577.75], [409.25, 3573.75],
         [407.25, 3574.25], [406.75, 3577.75], [383.25, 3577.75], [382.75, 3573.75], [376.75, 3570.75], [376.75, 3566.75],
         [380.25, 3565.75], [381.25, 3563.75], [381.25, 3556.25], [383.25, 3555.75], [384.25, 3553.75], [405.25, 3553.75],
         [406.25, 3566.25], [412.25, 3565.75], [411.75, 3554.75], [412.75, 3553.75], [460.25, 3553.75], [461.25, 3565.75],
         [475.25, 3566.25], [475.75, 3553.75], [465.75, 3553.25], [464.75, 3550.75], [462.75, 3549.75], [462.75, 3507.25],
         [475.75, 3506.75], [476.25, 3500.75], [475.25, 3499.75], [464.75, 3499.75], [463.75, 3497.25], [461.75, 3495.75],
         [462.25, 3476.25], [464.25, 3475.75], [464.75, 3473.75], [475.25, 3473.75], [475.75, 3471.75], [459.25, 3470.75],
         [461.75, 3468.75], [461.75, 3467.75], [459.75, 3466.75], [459.75, 3432.25], [461.75, 3430.75], [461.75, 3427.75],
         [463.75, 3426.25], [463.75, 3423.75], [467.75, 3422.25], [468.25, 3417.25], [473.75, 3416.75], [473.75, 3410.25],
         [468.75, 3405.25], [462.75, 3404.75], [462.25, 3416.75], [458.75, 3417.25], [457.75, 3419.75], [445.25, 3419.25],
         [444.25, 3422.25], [440.75, 3422.25], [439.75, 3423.25], [430.75, 3423.25], [429.75, 3422.25], [413.75, 3423.25],
         [412.75, 3422.25], [409.75, 3422.25], [408.25, 3419.75], [406.75, 3419.75], [402.25, 3424.25], [399.25, 3424.25],
         [395.75, 3421.25], [395.75, 3416.75], [391.75, 3416.25], [390.75, 3414.75], [390.75, 3406.25], [388.25, 3406.25],
         [385.75, 3408.75], [381.25, 3408.75], [378.75, 3406.25], [365.75, 3405.75], [365.75, 3392.75], [368.75, 3391.75],
         [373.25, 3392.25], [374.75, 3385.75], [386.75, 3384.75], [392.75, 3385.75], [393.75, 3387.75], [401.25, 3389.25],
         [402.25, 3392.75], [408.25, 3392.75], [409.75, 3390.75], [444.75, 3391.25], [445.25, 3393.75], [451.25, 3394.25],
         [452.25, 3391.25], [483.25, 3390.75], [488.25, 3395.75], [488.25, 3405.75], [487.25, 3406.75], [487.25, 3409.75],
         [488.25, 3410.25], [488.25, 3435.75], [487.25, 3437.25], [488.25, 3440.75], [488.25, 3448.75], [487.25, 3449.75],
         [488.25, 3466.75], [487.25, 3467.25], [486.75, 3471.25], [483.25, 3471.75], [483.25, 3477.25], [488.25, 3478.25],
         [488.25, 3500.75], [483.25, 3501.75], [483.75, 3504.75], [487.75, 3504.75], [488.25, 3527.25], [483.25, 3528.75],
         [483.75, 3531.25], [488.25, 3531.25], [488.25, 3554.25], [487.25, 3555.25], [483.75, 3555.25], [483.25, 3557.75],
         [487.75, 3558.75], [487.75, 3566.25], [489.25, 3568.25], [489.25, 3572.75], [488.25, 3573.75], [483.25, 3573.75]]
TOWER_C, TOWER_R, N_SEG = (358.94, 3482.91), 16.5, 48
PODIUM_H, FLOORS, FLOOR_H = 12.0, 17, 3.2
WING_FLOORS = 2
# [PIER66-V4] split of the lot along the strokes the V16 draws (our frame): north of Y_N = the new hotel, between = tower
# body (hexagonal part around the crown), south of Y_S = low block
Y_N, Y_S = 3501.25, 3464.75
NORTH_FLOORS = 10
DRUM_R, N_FINS = 9.7, 44
DRUM_H = 6.0                      # V6: two-storey lounge drum with windows (photo)
# fin profile (radius, height above the tower roof): inner-bottom, inner-top, outer-top, outer-bottom; V6: the blades
# leave the drum at mid-height and fan up and out past the shaft faces (Alexandre's pool-side photo)
FIN = ((DRUM_R + 0.2, 0.5), (DRUM_R + 0.2, 3.0), (TOWER_R, 7.5), (TOWER_R, 3.5))   # V6b: a deeper dish (2020 photo)
# [PIER66-V6] slim shaft = the frame the V16 draws around the crown (34 x 29 m) with its two pointed bays (W and E):
# the stacked angled balconies. The rest of the hexagonal body part of the lot = low base (PODIUM_H).
# V6b (Alexandre's 2020 photo): a central balcony bay stands proud on the long N and S faces -> the facade is recessed
# 1.5 m on both sides of a 12 m bay (inside the V16 frame)
SHAFT = [[342.25, 3469.75], [353.25, 3469.75], [353.25, 3468.25], [365.25, 3468.25], [365.25, 3469.75], [376.25, 3469.75],
         [376.25, 3477.25], [381.25, 3482.25], [376.25, 3487.25], [376.25, 3495.75], [365.25, 3495.75], [365.25, 3497.25],
         [353.25, 3497.25], [353.25, 3495.75], [342.25, 3495.75], [342.25, 3488.75], [337.25, 3482.75], [342.25, 3476.75]]
SAW_EDGES, SAW_PITCH, SAW_DEPTH = (), 3.5, 1.4   # V6c: the pointed bays are stacks of smooth triangular balconies (Alexandre photo) -> no teeth
# tall service slab on the north face rising above the roof, with a mast (photo); top of mast = roof + MAST_TOP
SLAB = [[344.0, 3494.0], [356.0, 3494.0], [356.0, 3500.5], [344.0, 3500.5]]
SLAB_TOP, MAST_TOP, MAST_W = 7.0, 12.6, 1.2
TOWER_COLOR = '#f1f5f9'


def sawtooth(ring, edges, pitch, depth):
    area2 = sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1] for i in range(len(ring)))
    sgn = 1.0 if area2 > 0 else -1.0                     # CCW: inward = left of the edge direction
    out = []
    for i, a in enumerate(ring):
        b = ring[(i + 1) % len(ring)]; out.append(list(a))
        if i not in edges: continue
        L = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(1, int(round(L / pitch)))
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L; nx, ny = -uy * sgn, ux * sgn
        for k in range(n):
            s1 = (k + 1) * L / n          # oblique face (angled balcony) from the edge to an inward point, then straight back out
            out.append([round(a[0] + ux * s1 + nx * depth, 2), round(a[1] + uy * s1 + ny * depth, 2)])
            if k < n - 1: out.append([round(a[0] + ux * s1, 2), round(a[1] + uy * s1, 2)])
    return out


def clip_y(ring, y, keep_above):
    """Sutherland-Hodgman clip of a polygon by the half-plane y >= y0 (keep_above) or y <= y0."""
    inside = (lambda p: p[1] >= y - 1e-9) if keep_above else (lambda p: p[1] <= y + 1e-9)
    out = []
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        if inside(a): out.append(list(a))
        if inside(a) != inside(b):
            t = (y - a[1]) / (b[1] - a[1]); out.append([round(a[0] + t * (b[0] - a[0]), 2), y])
    # drop consecutive duplicates
    return [p for i, p in enumerate(out) if p != out[i - 1]]


def prism(E, ring, z0, z1):
    def seg(a, b): E.append([[round(float(v), 2) for v in a], [round(float(v), 2) for v in b]])
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        seg([*a, z0], [*b, z0]); seg([*a, z1], [*b, z1]); seg([*a, z0], [*a, z1])


def build_wings():
    E = []; g = float(ground(*[sum(c) / len(WINGS) for c in zip(*WINGS)])); hh = WING_FLOORS * FLOOR_H
    prism(E, WINGS, g, g + hh)
    note = ('PIER66-V2 2026-10-13 (Alexandre: "ajoute aussi le U de batiments autour"): the U of low buildings east of the '
            'Pier Sixty-Six tower (GTADB L1977) on the latest V16 (same tiles and frame as the tower mesh), one outline of 9132 m2. '
            'Height %.1f m ESTIMATED = %d floors x %.1f m: before the 2019 closure the complex was mostly two-story room wings '
            '(guest account 2014), demolished after 2019; the game plan matches that ring of wings. The 2024-25 rebuild '
            '(4-story Resort Residences, 11-story Azul / Indigo) is NOT assumed. Ground %.1f (heightmap). Not checked in any camera frame.'
            % (hh, WING_FLOORS, FLOOR_H, g))
    return {'color': '#cbd5e1', 'world_edges': E, 'name_game': None, 'name_irl': 'Pier Sixty-Six (former two-story wings)', 'gtadb': 'L1977',
            '_credit': 'identification: GTA VI Landmarks Data (CC BY 4.0) https://map.gtadb.org; plan: V16 (yanis); height: estimated (IRL floor count of the former wings)',
            'note': note}, g, hh


def build():
    E = []
    def seg(a, b): E.append([[round(float(v), 2) for v in a], [round(float(v), 2) for v in b]])
    g = float(ground(*[sum(c) / len(OUTER) for c in zip(*OUTER)]))
    hh = FLOORS * FLOOR_H; t = g + hh
    north, south = clip_y(OUTER, Y_N, True), clip_y(OUTER, Y_S, False)
    base = clip_y(clip_y(OUTER, Y_S, True), Y_N, False)
    shaft = sawtooth(SHAFT, SAW_EDGES, SAW_PITCH, SAW_DEPTH)
    gn = g + NORTH_FLOORS * FLOOR_H
    prism(E, south, g, g + PODIUM_H)                              # low block south of the tower
    prism(E, base, g, g + PODIUM_H)                               # low base around the shaft
    prism(E, north, g, gn)                                        # new hotel north of the tower
    for k in range(1, NORTH_FLOORS):                              # its balcony bands
        z = g + k * FLOOR_H
        for i in range(len(north)): seg([*north[i], z], [*north[(i + 1) % len(north)], z])
    prism(E, shaft, g, t)                                         # slim tower shaft (17 floors)
    for k in range(1, FLOORS):                                    # floor lines (balcony rhythm)
        z = g + k * FLOOR_H
        for i in range(len(shaft)): seg([*shaft[i], z], [*shaft[(i + 1) % len(shaft)], z])
    prism(E, SLAB, g, t + SLAB_TOP)                               # service slab above the roof
    mx, my = sum(p[0] for p in SLAB) / 4, sum(p[1] for p in SLAB) / 4; w = MAST_W / 2
    prism(E, [[mx - w, my - w], [mx + w, my - w], [mx + w, my + w], [mx - w, my + w]], t + SLAB_TOP, t + MAST_TOP)
    cx, cy = TOWER_C
    drum = [[cx + DRUM_R * math.cos(2 * math.pi * k / N_SEG), cy + DRUM_R * math.sin(2 * math.pi * k / N_SEG)] for k in range(N_SEG)]
    prism(E, drum, t, t + DRUM_H)                                 # revolving Pier Top lounge (2 storeys)
    for k in range(N_SEG):                                        # mid band between the two lounge storeys
        a0, a1 = 2 * math.pi * k / N_SEG, 2 * math.pi * (k + 1) / N_SEG
        seg([cx + DRUM_R * math.cos(a0), cy + DRUM_R * math.sin(a0), t + DRUM_H / 2], [cx + DRUM_R * math.cos(a1), cy + DRUM_R * math.sin(a1), t + DRUM_H / 2])
    for k in range(N_FINS):                                       # starburst crown: radial fins fanning up and out
        a = 2 * math.pi * (k + 0.5) / N_FINS; ca, sa = math.cos(a), math.sin(a)
        P = [[cx + r * ca, cy + r * sa, t + dz] for r, dz in FIN]
        for i in range(4): seg(P[i], P[(i + 1) % 4])
    note = ('PIER66-V6 2026-10-13 (Alexandre: "make it look like the real building", then his pool-side photo): '
            'GTADB L1977 = IRL Pier Sixty-Six (Hyatt Regency Pier Sixty-Six, 2301 SE 17th St, Fort Lauderdale; OSM way 272811104). '
            'Plan = latest V16 lot (gtadb tiles yanis,16 z6; tile frame +9.0 m E +8.0 m N to ours, water/pier overlay NCC 0.994), 5468 m2, '
            'split along the strokes the V16 draws: hexagonal part around the crown (y %.2f-%.2f) = low base + slim shaft, new hotel to the north, low block to the south. '
            'Crown = the round V16 roof drawing, which matches the IRL aerial (Esri World Imagery, 0.27 m/px): starburst of ~44 radial fins with tips at r %.1f m '
            '(aerial 16.6) around the drum of the revolving Pier Top lounge, r %.1f m (aerial 9.7), centre (%.1f, %.1f). Tower body %.1f m = IRL 17 floors x %.1f m '
            '(Wikipedia, skydb). Shaft = the 34 x 29 m frame the V16 draws around the crown with its two pointed bays (W, E) = the stacked angled balconies '
            '(smooth wedges, one per floor), a central balcony bay standing proud 1.5 m on the long faces, floor lines every floor, white; a tall service slab on its north face rises 7 m above the roof with a mast to +12.6 m '
            '(top 67.0 m above ground, in line with the 221 ft overall figure), as on the photo. Lounge drum 2 storeys (%.0f m) with 44 blade fins leaving it at '
            'mid-height and fanning out to +%.0f m above the roof, profile by eye from photos. North = the new hotel built just north of the tower in the 2020s rebuild, %d floors x %.1f m '
            'ESTIMATED (Gardiner: new 10-storey hotel; a developer page says 9). South block %.0f m ESTIMATED. Ground %.1f (heightmap). '
            % (Y_S, Y_N, TOWER_R, DRUM_R, cx, cy, hh, FLOOR_H, DRUM_H, FIN[2][1], NORTH_FLOORS, FLOOR_H, PODIUM_H, g)
            + 'Frame check: Biplane Night (Video) v086 (night, 2577 m, RMS 8.4 arcmin) shows a lone lit tower with a bright crown here; its top-band ray passes '
            '11-39 m from the tower axis and reaches 58-60 m above ground at it (+-6 m), consistent with the crown top (+%.1f m above ground). '
            'Single camera, no two-ray triangulation yet (second view Biplane Night (Video) v084 added for clicks). '
            'Highway (N)/(NE) (2022 build) show empty sky where the top would be: weak evidence (older build). '
            'The grey U of low wings is the separate mesh Pier Sixty-Six (wings).' % (hh + FIN[2][1]))
    return {'color': TOWER_COLOR, 'world_edges': E, 'name_game': None, 'name_irl': 'Pier Sixty-Six', 'gtadb': 'L1977',
            '_credit': 'identification: GTA VI Landmarks Data (CC BY 4.0) https://map.gtadb.org; plan: V16 (yanis); height: IRL floor count (Wikipedia)',
            'note': note}, g, hh


def main():
    m, g, hh = build(); mw, gw, hw = build_wings()
    print('%s: %d edges, ground %.1f, south block %.1f, north hotel %.1f, tower roof %.1f, crown top %.1f' % (
        NAME, len(m['world_edges']), g, g + PODIUM_H, g + NORTH_FLOORS * FLOOR_H, g + hh, g + hh + FIN[2][1]))
    print('%s: %d edges, ground %.1f, roof %.1f' % (NAME_WINGS, len(mw['world_edges']), gw, gw + hw))
    if '--apply' in sys.argv:
        M = json.load(open(MESHES))
        shutil.copy(MESHES, MESHES + '.bak_pier66')
        M[NAME] = m; M[NAME_WINGS] = mw
        tmp = MESHES + '.tmp'; json.dump(M, open(tmp, 'w'), indent=1, ensure_ascii=True); os.replace(tmp, MESHES)
        print('applied ->', len(M), 'meshes')


if __name__ == '__main__':
    main()
