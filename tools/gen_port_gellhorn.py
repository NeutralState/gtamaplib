#!/usr/bin/env python3
"""gen_port_gellhorn.py — Draper Island (Port Gellhorn): refinery, paper mill, FEC-style rail bascule bridge. [PORT-GELLHORN-V1 2026-10-15]

Alexandre: "Vertex Energy's Mobile Alabama Refinery, WestRock Paper Mill in Panama City, et le pont next to le Sunshine
Skyway bridge (FEC Strauss Trunnion Bascule Bridge de Jacksonville)". Identification = GTADB: L535 "Refinery?" = Vertex
Energy Mobile Refinery (Saraland AL), L536/L1201 "Factory?" = WestRock Paper Mill (Panama City), L597 "Train Bridge" = FEC
Strauss Trunnion Bascule Bridge (Jacksonville), next to Bocamar Bridge (= Sunshine Skyway). The port cranes are in
gen_port_cranes.py.

Plans = V16 (local yanis,16svg: footprints v16_footprints.json + raster for the red tanks). Heights: no published height for
any of these; MEASURED where the Port Gellhorn Postcard (X) shows them (tier medium, 1.0-1.9 km), otherwise ESTIMATED by
element type (IRL typical values), as noted per element:
- refinery: smokestacks top 66.5 m abs (Postcard: two stack tops at 66.4 / 66.6 m on the refinery line of sight); process
  columns 40 m (d 3-4 m) and vessels 25 m (d 4.5-6.5 m) ESTIMATED; process units 12 m (the 3 largest 15 m) ESTIMATED;
  pipe racks (V16 strips 4-5 m wide) 7 m ESTIMATED; 6 crude tanks (d 23 m, red on V16) 16 m ESTIMATED; red blocks 8 m.
- paper mill: stacks top 70 m abs (Postcard: 63.8 / 73.9 m); main mill 22 m, second hall 14 m, round tank 25 m ESTIMATED.
- rail bridge: axis = the V16 rail line across the bay (Hough fit, bearing 134.8 deg), over water from s -170 to +325 m;
  raised bascule leaf seen nearly end-on in the Postcard at s 103 (-7195.6, 4447.1): top 57.2 m MEASURED, ~16-20 m wide
  at 1071 m; plate-girder approaches (IRL: plate girder approaches, 2 tracks, 5 ft closed clearance) deck top 4.5 m
  ESTIMATED, piers every 30 m; the leaf is modelled RAISED as in the Postcard (the trunnion bascule's open position).
Usage: PYTHONPATH=. /usr/local/bin/python3 tools/gen_port_gellhorn.py [--apply]
"""
import json, math, os, sys, shutil
import numpy as np, cv2
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS)
from horizon_resect import ground
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

MESHES = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
FOOT = os.path.join(REPO, 'gtamapdata', 'v16_footprints.json')
V16 = os.path.join(REPO, 'maps', 'yanis,16svg.png')
CREDIT = 'identification: GTA VI Landmarks Data (CC BY 4.0) https://map.gtadb.org; plan: V16 (yanis); heights: Port Gellhorn Postcard (X) where measured, else estimated'
REF_BOX = (-7700, -7300, 5080, 5420)
MILL_IDS = (1235, 1243, 1238, 1236, 1237, 1239, 1240, 1241, 1242)
STACK_TOP_REF, STACK_TOP_MILL = 66.5, 70.0
RAIL_P1, RAIL_T = np.array([-7269.0, 4520.0]), np.array([0.7095, -0.7047])
BR_S0, BR_S1, LEAF_S, LEAF_TOP, DECK_TOP, BR_HALF_W = -170.0, 325.0, 103.0, 57.2, 4.5, 6.0


class Mesh:
    def __init__(self): self.E = []
    def seg(self, a, b): self.E.append([[round(float(v), 2) for v in a], [round(float(v), 2) for v in b]])
    def prism(self, ring, z0, z1):
        for k in range(len(ring)):
            a, b = ring[k], ring[(k + 1) % len(ring)]
            self.seg([*a, z0], [*b, z0]); self.seg([*a, z1], [*b, z1]); self.seg([*a, z0], [*a, z1])
    def cyl(self, c, r, z0, z1, n=24):
        self.prism([[c[0] + r * math.cos(2 * math.pi * k / n), c[1] + r * math.sin(2 * math.pi * k / n)] for k in range(n)], z0, z1)


def classify(f):
    R = np.array(f['ring'], np.float32); a = f['area']; (w, h) = sorted(cv2.minAreaRect(R)[1]); per = cv2.arcLength(R, True)
    circ = 4 * math.pi * a / per ** 2 if per else 0
    if w < 6.0 and h / max(w, 1e-6) > 5: return 'rack', 7.0
    if circ > 0.76 and abs(w - h) < 0.6:
        d = w
        if d <= 2.5: return 'stack', None
        if d <= 4.2: return 'column', 40.0
        if d <= 6.5: return 'vessel', 25.0
    return 'unit', (15.0 if a > 420 else 12.0)


def refinery(F, V):
    X0, X1, Y0, Y1 = REF_BOX
    proc, stacks = Mesh(), Mesh(); counts = {}
    for f in F:
        if not (X0 < f['centroid'][0] < X1 and Y0 < f['centroid'][1] < Y1): continue
        kind, h = classify(f); R = f['ring']; g = float(ground(*f['centroid'])); counts[kind] = counts.get(kind, 0) + 1
        if kind == 'stack': stacks.prism(R, g, STACK_TOP_REF)
        else: proc.prism(R, g, g + h)
    # red items of the raster: 6 crude tanks (circles) + red blocks
    a = np.asarray(V.crop((X0 + 16991, 11008 - Y1, X1 + 16991, 11008 - Y0)).convert('RGB')).astype(int)
    red = ((a[..., 0] > 200) & (a[..., 1] < 90) & (a[..., 2] < 90)).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(red, 8)
    for l in range(1, n):
        A, w, hh = st[l, cv2.CC_STAT_AREA], st[l, cv2.CC_STAT_WIDTH], st[l, cv2.CC_STAT_HEIGHT]
        c = [X0 + cen[l][0], Y1 - cen[l][1]]; g = float(ground(*c))
        if abs(w - hh) <= 2 and 0.72 < A / (w * hh) < 0.86:
            proc.cyl(c, math.sqrt(A / math.pi), g, g + 16.0); counts['tank'] = counts.get('tank', 0) + 1
        else:
            cs, _ = cv2.findContours((lab == l).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            box = cv2.boxPoints(cv2.minAreaRect(cs[0])); ring = [[X0 + p[0], Y1 - p[1]] for p in box]
            proc.prism(ring, g, g + 8.0); counts['red block'] = counts.get('red block', 0) + 1
    note = ('PORT-GELLHORN-V1 2026-10-15 (Alexandre): GTADB L535 "Refinery?" = IRL Vertex Energy Mobile Refinery (Saraland AL). '
            'Plan = the V16 refinery (%s). Heights ESTIMATED by type (no published height): process units 12 m (largest 15 m), columns 40 m, vessels 25 m, '
            'pipe racks 7 m, crude tanks (d 23 m) 16 m, red blocks 8 m; smokestacks are the separate mesh "(Stacks)". Ground = heightmap.'
            % ', '.join('%d %s' % (v, k) for k, v in sorted(counts.items()) if k != 'stack'))
    snote = ('PORT-GELLHORN-V1 2026-10-15: the %d smallest round V16 items of the refinery (d <= 2.5 m) as smokestacks, top %.1f m abs MEASURED '
             '(Port Gellhorn Postcard (X): two stack tops at 66.4 / 66.6 m on the refinery line of sight, 1.9 km).' % (counts.get('stack', 0), STACK_TOP_REF))
    return {'Draper Island Refinery': ('#94a3b8', proc, note, 'Vertex Energy Mobile Refinery', 'L535'),
            'Draper Island Refinery (Stacks)': ('#64748b', stacks, snote, 'Vertex Energy Mobile Refinery', 'L535')}


def mill(F):
    body, stacks = Mesh(), Mesh(); Fi = {f['id']: f for f in F}
    H = {1235: 22.0, 1243: 14.0, 1238: 25.0}
    for pid in MILL_IDS:
        f = Fi[pid]; g = float(ground(*f['centroid']))
        if pid in H: body.prism(f['ring'], g, g + H[pid])
        else: stacks.prism(f['ring'], g, STACK_TOP_MILL)
    note = ('PORT-GELLHORN-V1 2026-10-15 (Alexandre): GTADB L536 / L1201 "Factory?" = IRL WestRock Paper Mill (Panama City; closed 2022). '
            'Plan = V16 polygons 1235 (main mill, 586 m2) 22 m, 1243 (second hall) 14 m, 1238 (round tank) 25 m, all ESTIMATED; stacks = separate mesh.')
    snote = ('PORT-GELLHORN-V1 2026-10-15: the 6 small round V16 items of the paper mill as stacks, top %.1f m abs MEASURED (Port Gellhorn Postcard (X): '
             'stack tops 63.8 / 73.9 m on the mill line of sight, 1.5 km).' % STACK_TOP_MILL)
    return {'Draper Island Paper Mill': ('#a8a29e', body, note, 'WestRock Paper Mill', 'L536'),
            'Draper Island Paper Mill (Stacks)': ('#78716c', stacks, snote, 'WestRock Paper Mill', 'L536')}


def rail_bridge():
    t = RAIL_T / np.linalg.norm(RAIL_T); n = np.array([-t[1], t[0]]); m = Mesh()
    P = lambda s, w, z: [*(RAIL_P1 + s * t + w * n), z]
    def box(s0, s1, w0, w1, z0, z1):
        cs = [(s0, w0), (s1, w0), (s1, w1), (s0, w1)]
        for z in (z0, z1):
            for i in range(4): m.seg(P(*cs[i], z), P(*cs[(i + 1) % 4], z))
        for q in cs: m.seg(P(*q, z0), P(*q, z1))
    zt, zb = DECK_TOP, DECK_TOP - 2.2
    for s0, s1 in ((BR_S0, LEAF_S - 6.0), (LEAF_S + 6.0, BR_S1)):        # plate-girder approaches
        for w in (-BR_HALF_W, BR_HALF_W):
            m.seg(P(s0, w, zt), P(s1, w, zt)); m.seg(P(s0, w, zb), P(s1, w, zb)); m.seg(P(s0, w, zt + 1.0), P(s1, w, zt + 1.0))
        for s in np.arange(s0, s1 + 0.1, 30.0):                         # piers + cross frames
            m.seg(P(s, -BR_HALF_W, zt), P(s, BR_HALF_W, zt)); m.seg(P(s, -BR_HALF_W, zb), P(s, BR_HALF_W, zb))
            box(s - 1.2, s + 1.2, -BR_HALF_W + 0.5, BR_HALF_W - 0.5, 0.0, zb)
    # trunnion pier + counterweight frame + raised leaf (vertical truss) at LEAF_S
    box(LEAF_S - 6.0, LEAF_S + 6.0, -BR_HALF_W - 1.0, BR_HALF_W + 1.0, 0.0, zt)
    box(LEAF_S - 6.0, LEAF_S - 1.0, -BR_HALF_W, BR_HALF_W, zt, zt + 14.0)                       # counterweight frame
    box(LEAF_S - 1.0, LEAF_S + 4.0, -BR_HALF_W, BR_HALF_W, zt, LEAF_TOP)                       # raised leaf
    for z0 in np.arange(zt, LEAF_TOP - 0.1, 6.5):                                              # leaf truss bracing
        z1 = min(z0 + 6.5, LEAF_TOP)
        for s in (LEAF_S - 1.0, LEAF_S + 4.0):
            m.seg(P(s, -BR_HALF_W, z0), P(s, BR_HALF_W, z1)); m.seg(P(s, BR_HALF_W, z0), P(s, -BR_HALF_W, z1))
        for w in (-BR_HALF_W, BR_HALF_W): m.seg(P(LEAF_S - 1.0, w, z0), P(LEAF_S + 4.0, w, z1))
    note = ('PORT-GELLHORN-V1 2026-10-15 (Alexandre): GTADB L597 "Train Bridge" = IRL FEC Strauss Trunnion Bascule Bridge (Jacksonville), next to Bocamar Bridge. '
            'Axis = the V16 rail line across the bay (bearing 134.8 deg), over water from s %.0f to %.0f m. Raised bascule leaf at s %.0f (%.1f, %.1f): top %.1f m '
            'MEASURED in Port Gellhorn Postcard (X) (seen nearly end-on at 1071 m, 16-20 m wide); plate-girder approaches, deck top %.1f m ESTIMATED '
            '(IRL closed clearance 5 ft), piers every 30 m, 2 tracks (12 m wide). Leaf modelled raised, as in the Postcard.'
            % (BR_S0, BR_S1, LEAF_S, *(RAIL_P1 + LEAF_S * t), LEAF_TOP, DECK_TOP))
    return {'Draper Island Rail Bascule Bridge': ('#7c2d12', m, note, 'FEC Strauss Trunnion Bascule Bridge', 'L597')}


def build():
    F = json.load(open(FOOT))['polygons']; V = Image.open(V16)
    out = {}
    for name, (col, m, note, irl, gid) in {**refinery(F, V), **mill(F), **rail_bridge()}.items():
        out[name] = {'color': col, 'world_edges': m.E, 'name_game': None, 'name_irl': irl, 'gtadb': gid, '_credit': CREDIT, 'note': note}
    return out


def main():
    out = build()
    for k, v in out.items(): print('%-36s %5d edges | %s' % (k, len(v['world_edges']), v['note'][v['note'].find('Plan'):][:110]))
    if '--apply' in sys.argv:
        M = json.load(open(MESHES)); shutil.copy(MESHES, MESHES + '.bak_port_gellhorn'); M.update(out)
        tmp = MESHES + '.tmp'; json.dump(M, open(tmp, 'w'), indent=1, ensure_ascii=True); os.replace(tmp, MESHES); print('applied ->', len(M), 'meshes')


if __name__ == '__main__':
    main()
