#!/usr/bin/env python3
"""gen_port_gellhorn.py — Draper Island (Port Gellhorn): refinery, paper mill, rail bascule bridge. [PORT-GELLHORN-V2 2026-10-15]

Alexandre: "Vertex Energy's Mobile Alabama Refinery, WestRock Paper Mill in Panama City, et le pont next to le Sunshine
Skyway bridge (FEC Strauss Trunnion Bascule Bridge de Jacksonville)", then "tu peux faire tellement mieux que ca".
Identification = GTADB: L535 "Refinery?" = Vertex Energy Mobile Refinery (Saraland AL); L536/L1201 "Factory?" = WestRock
Paper Mill (Panama City); L597 "Train Bridge" = FEC Strauss Trunnion Bascule Bridge (Jacksonville), next to Bocamar
Bridge (= Sunshine Skyway). The port cranes are in gen_port_cranes.py.

Plans. V17 (gtadb tiles yanis,17 z6, 0.5 m/px, fetched 2026-10-15; tile frame -> ours +9.0 m E +8.0 m N, water NCC
0.997, the same offset as at Pier Sixty-Six):
- refinery: the V17 drawing equals the V16 one (overlay checked), so the V16 footprints are used: grey strips = pipe
  racks, rectangles = process units with their columns/vessels (small circles), small squares = pump/compressor houses;
  from the V16 raster: 6 crude tanks (d 23 m) and the red pipe corridors (incl. the tank-farm dike) + red blocks.
- paper mill: MOVED in V17 (~60 m W, ~75 m N of the V16 footprints): main building 402 m2 + annex, warehouse 332 m2,
  round tank d 19 m, 6 small round items (tools/data/draper_v17_mill.json).
- rail bridge: the V17 rail line across the bay (bearing 135.0 deg, tools/data/draper_v17_rail.json), over water for
  490 m; the bascule span is at the deepest water, which is also the GTADB L597 point (s 470 m).
Heights: no published height for any of these. Port Gellhorn Postcard (X) sees all three but its pose is poor (39' RMS;
its triangulated cranes miss their clicks by 60-70 px), so it only bounds the tallest items (~60-70 m above ground):
stacks and the raised leaf are set in that range; everything else is ESTIMATED from IRL plant practice, per element:
pipe racks 2 tiers (5.5 / 8.0 m), process structures 3-4 floors of 6 m, distillation columns 42 m (d 3-4 m), vessels
24 m (d 4.5-6.5 m), drums 14 m (d 6.5-12 m), crude tanks 16 m + cone roof, flare 60 m; mill boiler house 34 m + annex 42 m, warehouse 12 m (gable),
tank 26 m + cone; bridge: plate-girder approaches, deck top 4.5 m (IRL closed clearance 5 ft), single-leaf through-truss
bascule ~50 m (raised, as in the Postcard) with overhead counterweight tower, 2 tracks.
Open steel structures are named "(Pipe Racks)" / "(Process Frames)" so mesh_solids keeps them as wireframes.
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
MILL = os.path.join(THIS, 'data', 'draper_v17_mill.json')
RAIL = os.path.join(THIS, 'data', 'draper_v17_rail.json')
CREDIT = 'identification: GTA VI Landmarks Data (CC BY 4.0) https://map.gtadb.org; plan: V16/V17 (yanis); heights: estimated (IRL practice), tallest items bounded by Port Gellhorn Postcard (X)'
REF_BOX = (-7700, -7300, 5080, 5420)
OBSOLETE = ('Draper Island Refinery', 'Draper Island Paper Mill')      # V1 names replaced by the split meshes


class Mesh:
    def __init__(self): self.E = []
    def seg(self, a, b): self.E.append([[round(float(v), 2) for v in a], [round(float(v), 2) for v in b]])
    def ring(self, R, z):
        for k in range(len(R)): self.seg([*R[k], z], [*R[(k + 1) % len(R)], z])
    def prism(self, R, z0, z1):
        self.ring(R, z0); self.ring(R, z1)
        for p in R: self.seg([*p, z0], [*p, z1])
    def circle(self, c, r, n=24): return [[c[0] + r * math.cos(2 * math.pi * k / n), c[1] + r * math.sin(2 * math.pi * k / n)] for k in range(n)]
    def cyl(self, c, r, z0, z1, n=24): self.prism(self.circle(c, r, n), z0, z1)
    def cone(self, c, r, z0, z1, n=24):
        R = self.circle(c, r, n)
        for p in R: self.seg([*p, z0], [c[0], c[1], z1])


def obb(R):
    """oriented box of a polygon: centre, unit long axis u, normal n, half-lengths (L, W)."""
    (cx, cy), (a, b), ang = cv2.minAreaRect(np.array(R, np.float32))
    u = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))]); n = np.array([-u[1], u[0]])
    if b > a: u, n, a, b = n, -u, b, a
    return np.array([cx, cy]), u, n, a / 2, b / 2


def box_ring(c, u, n, L, W): return [list(c + u * su * L + n * sw * W) for su, sw in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def classify(f):
    R = np.array(f['ring'], np.float32); a = f['area']; (w, h) = sorted(cv2.minAreaRect(R)[1]); per = cv2.arcLength(R, True)
    circ = 4 * math.pi * a / per ** 2 if per else 0
    if w < 6.0 and h / max(w, 1e-6) > 5: return 'rack'
    if circ > 0.76 and abs(w - h) < 0.6:
        if w <= 2.5: return 'stack'
        if w <= 4.2: return 'column'
        if w <= 6.5: return 'house' if a > 30 and abs(a - w * w) < 3 else 'vessel'
        if w <= 12.0: return 'drum'                                    # wider round items: low storage vessels / spheres
    return 'unit'


def pipe_rack(m, c, u, n, L, W, g, tiers=(5.5, 8.0), bay=6.0, pipes=3):
    """2-tier steel pipe rack along u: bents every `bay` m (2 posts + tier beams + knee braces), longitudinal struts, pipes."""
    W = max(W, 1.6); ss = list(np.arange(-L, L, bay)) + [L]
    P = lambda s, w, z: [*(c + u * s + n * w), z]
    for s in ss:
        for w in (-W, W): m.seg(P(s, w, g), P(s, w, g + tiers[-1]))
        for zt in tiers: m.seg(P(s, -W, g + zt), P(s, W, g + zt))
        m.seg(P(s, -W, g + tiers[0] - 1.2), P(s, -W + 1.0, g + tiers[0])); m.seg(P(s, W, g + tiers[0] - 1.2), P(s, W - 1.0, g + tiers[0]))
    for zt in tiers:
        for w in (-W, W): m.seg(P(-L, w, g + zt), P(L, w, g + zt))
        for k in range(pipes):                                            # pipes resting on the tier
            w = -W + (k + 1) * 2 * W / (pipes + 1); m.seg(P(-L, w, g + zt + 0.4), P(L, w, g + zt + 0.4))


def process_frame(m, R, g, floors, fh=6.0, grid=6.0):
    """open steel process structure on the unit footprint: columns on a grid, beams + floor at each level, X-bracing on the ends."""
    c, u, n, L, W = obb(R); nu = max(1, int(round(2 * L / grid))); nw = max(1, int(round(2 * W / grid)))
    us = np.linspace(-L, L, nu + 1); ws = np.linspace(-W, W, nw + 1); P = lambda a, b, z: [*(c + u * a + n * b), z]
    zs = [g + fh * k for k in range(1, floors + 1)]
    for a in us:
        for b in ws: m.seg(P(a, b, g), P(a, b, zs[-1]))
    for z in zs:
        for a in us: m.seg(P(a, -W, z), P(a, W, z))
        for b in ws: m.seg(P(-L, b, z), P(L, b, z))
    for a in (-L, L):                                                    # end bracing
        for z0, z1 in zip([g] + zs[:-1], zs): m.seg(P(a, -W, z0), P(a, W, z1)); m.seg(P(a, W, z0), P(a, -W, z1))
    m.prism(box_ring(c, u, n, L + 0.6, W + 0.6), g, g + 0.6)                                       # concrete slab
    return c, u, n, L, W


def column(m, c, r, g, h):
    m.cyl(c, r, g, g + h, 20); m.cone(c, r, g + h, g + h + r * 0.6, 20)           # shell + top head
    m.cyl(c, r * 1.15, g, g + 2.5, 20)                                             # skirt


def platforms(m, c, r, g, h, step=7.0):
    for z in np.arange(g + step, g + h - 1, step):                                  # access platforms + handrails (wireframe mesh)
        R = m.circle(c, r + 1.2, 16); m.ring(R, z); m.ring(R, z + 1.1)


def refinery(F, V):
    X0, X1, Y0, Y1 = REF_BOX
    racks, frames, cols, houses, tanks, stacks = Mesh(), Mesh(), Mesh(), Mesh(), Mesh(), Mesh(); cnt = {}
    sel = [f for f in F if X0 < f['centroid'][0] < X1 and Y0 < f['centroid'][1] < Y1]
    units = []; stack_fp = []
    for f in sel:
        k = classify(f); cnt[k] = cnt.get(k, 0) + 1; g = float(ground(*f['centroid'])); R = f['ring']
        if k == 'rack':
            c, u, n, L, W = obb(R); pipe_rack(racks, c, u, n, L, W, g)
        elif k == 'unit':
            floors = 4 if f['area'] > 420 else 3; units.append(process_frame(frames, R, g, floors))
        elif k == 'column':
            r = math.sqrt(f['area'] / math.pi); column(cols, f['centroid'], r, g, 42.0); platforms(frames, f['centroid'], r, g, 42.0)
        elif k == 'vessel':
            r = math.sqrt(f['area'] / math.pi); column(cols, f['centroid'], r, g, 24.0); platforms(frames, f['centroid'], r, g, 24.0, 8.0)
        elif k == 'drum':
            r = math.sqrt(f['area'] / math.pi); cols.cyl(f['centroid'], r, g, g + 14.0, 24); cols.cone(f['centroid'], r, g + 14.0, g + 15.5, 24)
        elif k == 'house':
            houses.prism(R, g, g + 6.0)
        elif k == 'stack':
            stack_fp.append((f, g))
    # stacks: the one farthest from the process units is the FLARE (separate mesh, flame drawn by view3d); the others smoke
    flare = Mesh(); uc = np.mean([u[0] for u in units], 0) if units else np.zeros(2)
    far = max(stack_fp, key=lambda fg: np.hypot(*(np.array(fg[0]['centroid']) - uc)))[0]['id'] if stack_fp else None
    for f, g in stack_fp:
        r = max(1.2, math.sqrt(f['area'] / math.pi))
        if f['id'] == far:
            flare.cyl(f['centroid'], 1.0, g, g + 62.0, 12); flare.cyl(f['centroid'], 1.6, g + 62.0, g + 64.0, 12)      # flare stack + tip
            for z in (g + 20.0, g + 40.0):                                                                          # guy-wire levels
                for k in range(3):
                    a = 2 * math.pi * k / 3; flare.seg([f['centroid'][0], f['centroid'][1], z], [f['centroid'][0] + 18 * math.cos(a), f['centroid'][1] + 18 * math.sin(a), g])
        else:
            stacks.cyl(f['centroid'], r, g, g + 58.0, 12); stacks.cyl(f['centroid'], r * 1.25, g + 56.0, g + 58.0, 12)  # stack + cap band
    # V16 raster: tanks (circles), red blocks, red pipe corridors
    a = np.asarray(V.crop((X0 + 16991, 11008 - Y1, X1 + 16991, 11008 - Y0)).convert('RGB')).astype(int)
    red = ((a[..., 0] > 190) & (a[..., 1] < 120) & (a[..., 2] < 120)).astype(np.uint8)
    n_, lab, st, cen = cv2.connectedComponentsWithStats(red, 8); corridor = np.zeros_like(red)
    for l in range(1, n_):
        A, w, hh = st[l, cv2.CC_STAT_AREA], st[l, cv2.CC_STAT_WIDTH], st[l, cv2.CC_STAT_HEIGHT]; c = [X0 + cen[l][0], Y1 - cen[l][1]]; g = float(ground(*c))
        if abs(w - hh) <= 2 and 0.72 < A / (w * hh) < 0.86:                        # crude tank: shell, cone roof, wind girder, stair
            r = math.sqrt(A / math.pi); tanks.cyl(c, r, g, g + 16.0, 32); tanks.cone(c, r, g + 16.0, g + 18.2, 32); tanks.ring(tanks.circle(c, r + 0.4, 32), g + 14.5)
            for k in range(8):
                t0, t1 = 2 * math.pi * k / 8 * 0.35, 2 * math.pi * (k + 1) / 8 * 0.35
                tanks.seg([c[0] + (r + 0.8) * math.cos(t0), c[1] + (r + 0.8) * math.sin(t0), g + 2 * k], [c[0] + (r + 0.8) * math.cos(t1), c[1] + (r + 0.8) * math.sin(t1), g + 2 * (k + 1)])
            cnt['tank'] = cnt.get('tank', 0) + 1
        elif A < 600 and max(w, hh) < 30:
            cs, _ = cv2.findContours((lab == l).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            R = [[X0 + p[0], Y1 - p[1]] for p in cv2.boxPoints(cv2.minAreaRect(cs[0]))]; houses.prism(R, g, g + 8.0); cnt['red block'] = cnt.get('red block', 0) + 1
        else:
            corridor |= (lab == l).astype(np.uint8)
    # red corridors -> centrelines -> low pipeways on sleepers (1.2 m) + the tank-farm dike
    sk = cv2.ximgproc.thinning(corridor * 255) if hasattr(cv2, 'ximgproc') else cv2.erode(corridor * 255, np.ones((3, 3), np.uint8), iterations=2)
    L_ = cv2.HoughLinesP(sk, 1, np.pi / 360, 18, minLineLength=18, maxLineGap=6)
    nseg = 0
    for x1, y1, x2, y2 in ([] if L_ is None else L_[:, 0]):
        p, q = np.array([X0 + x1, Y1 - y1], float), np.array([X0 + x2, Y1 - y2], float); u = (q - p) / max(np.linalg.norm(q - p), 1e-6)
        c, Lh = (p + q) / 2, np.linalg.norm(q - p) / 2; g = float(ground(*c))
        pipe_rack(racks, c, u, np.array([-u[1], u[0]]), Lh, 1.6, g, tiers=(1.2,), bay=8.0, pipes=3); nseg += 1
    cnt['pipeway'] = nseg
    def note(what, extra=''):
        return ('PORT-GELLHORN-V2 2026-10-15 (Alexandre): GTADB L535 "Refinery?" = IRL Vertex Energy Mobile Refinery (Saraland AL). %s Plan = V16 (= V17 there). %s'
                'Heights ESTIMATED from IRL practice (no published height; Port Gellhorn Postcard (X) pose too poor to measure). Ground = heightmap.' % (what, extra))
    return {
        'Draper Island Refinery (Pipe Racks)': ('#9ca3af', racks, note('Pipe racks: %d V16 strips as 2-tier racks (5.5 / 8.0 m, bents every 6 m) and %d red corridor segments as low pipeways (1.2 m).' % (cnt.get('rack', 0), nseg))),
        'Draper Island Refinery (Process Frames)': ('#a1a1aa', frames, note('Open steel process structures on the %d unit footprints (3 floors of 6 m, 4 for the largest), plus column platforms.' % cnt.get('unit', 0))),
        'Draper Island Refinery (Columns)': ('#e5e7eb', cols, note('%d distillation columns (d 3-4 m) 42 m, %d vessels (d 4.5-6.5 m) 24 m, with skirt and top head; %d drums (d 6.5-12 m) 14 m.' % (cnt.get('column', 0), cnt.get('vessel', 0), cnt.get('drum', 0)))),
        'Draper Island Refinery (Tanks)': ('#f1f5f9', tanks, note('%d crude tanks (d 23 m, red on V16) 16 m + cone roof, wind girder, stair.' % cnt.get('tank', 0))),
        'Draper Island Refinery (Buildings)': ('#cbd5e1', houses, note('Pump/compressor houses (V16 small squares) 6 m and %d red blocks 8 m.' % cnt.get('red block', 0))),
        'Draper Island Refinery (Stacks)': ('#6b7280', stacks, note('%d smoking stacks (d <= 2.5 m) 58 m with cap band: within the ~60-70 m the Postcard bounds (dark smoke drawn by view3d).' % (cnt.get('stack', 0) - 1))),
        'Draper Island Refinery (Flare Stack)': ('#57534e', flare, note('Flare: the V16 stack farthest from the process units, 64 m with tip and guy wires (flame drawn by view3d).')),
    }


def mill():
    D = json.load(open(MILL)); S = sorted(D['shapes'], key=lambda s: -s['area_m2'])
    main, annex, ware, tank = S[0], S[3], S[1], S[2]
    body, st = Mesh(), Mesh()
    g = float(ground(*main['centre'])); body.prism(main['ring'], g, g + 34.0)                  # boiler house
    body.prism(annex['ring'], g, g + 42.0)                                                       # stair / boiler annex tower
    c, u, n, L, W = obb(ware['ring']); gw = float(ground(*c)); P = lambda a, b, z: [*(c + u * a + n * b), z]
    body.prism(box_ring(c, u, n, L, W), gw, gw + 12.0)                                         # warehouse walls
    for a in (-L, L): body.seg(P(a, -W, gw + 12.0), P(a, 0, gw + 15.0)); body.seg(P(a, 0, gw + 15.0), P(a, W, gw + 12.0))
    body.seg(P(-L, 0, gw + 15.0), P(L, 0, gw + 15.0))                                           # gable ridge
    gt = float(ground(*tank['centre'])); body.cyl(tank['centre'], tank['r_m'], gt, gt + 26.0, 28); body.cone(tank['centre'], tank['r_m'], gt + 26.0, gt + 29.0, 28)
    for x, y, r in D['stacks']:
        gs = float(ground(x, y))
        if r >= 1.0: st.cyl([x, y], 1.6, gs, gs + 68.0, 14); st.cyl([x, y], 2.0, gs + 66.0, gs + 68.0, 14)   # stacks, cap band
        else: st.cyl([x, y], 0.9, gs, gs + 24.0, 10)                                                       # vents
    base = ('PORT-GELLHORN-V2 2026-10-15 (Alexandre): GTADB L536 / L1201 "Factory?" = IRL WestRock Paper Mill (Panama City; closed 2022). '
            'Plan = V17 (moved ~60 m W / 75 m N from the V16 footprints): ')
    return {'Draper Island Paper Mill (Buildings)': ('#d6d3d1', body, base + 'boiler house 402 m2 34 m + annex tower 42 m, warehouse 332 m2 12 m with a 3 m gable, round tank d 19 m 26 m + cone; heights ESTIMATED.'),
            'Draper Island Paper Mill (Stacks)': ('#78716c', st, base + 'the two largest small round items as stacks 68 m (within the ~60-70 m the Postcard bounds), the 4 others as 24 m vents; ESTIMATED.')}


def rail_bridge():
    R = json.load(open(RAIL)); A = np.array(R['A']); t = np.array(R['t']); n = np.array([-t[1], t[0]]); (s0, s1) = R['runs'][0]
    m = Mesh(); tr = Mesh(); cw = Mesh(); zt = 4.5; zg = zt - 2.6; half = 5.2
    P = lambda s, w, z: [*(A + s * t + w * n), z]
    S_TIP = 470.0 + 25.0; LEAF = 50.0; S_HEEL = S_TIP - LEAF                 # opening centred on the deepest water (s 470)
    dk = Mesh()
    def girders(sa, sb):                                                      # plate-girder span = solid deck box (2.6 m) + handrails
        dk.prism([list(A + (sa + 0.3) * t - n * half), list(A + (sb - 0.3) * t - n * half), list(A + (sb - 0.3) * t + n * half), list(A + (sa + 0.3) * t + n * half)], zg, zt)
        for w in (-half, half): m.seg(P(sa, w, zt + 1.1), P(sb, w, zt + 1.1))
    def pier(s, wide=1.0):
        R_ = [list(A + s * t + n * w + t * d) for d, w in ((-1.0 * wide, -half - 0.8), (1.0 * wide, -half - 0.8), (1.0 * wide, half + 0.8), (-1.0 * wide, half + 0.8))]
        m.prism(R_, 0.0, zg)
    spans = list(np.arange(s0, S_HEEL - 12.0, 25.0)) + [S_HEEL - 12.0]
    for a, b in zip(spans[:-1], spans[1:]): girders(a, b); pier(b)
    pier(s0); spans2 = list(np.arange(S_TIP + 2.0, s1, 25.0)) + [s1]
    for a, b in zip(spans2[:-1], spans2[1:]): girders(a, b); pier(b)
    pier(S_TIP + 2.0, 2.0)                                                   # rest pier at the leaf tip
    # trunnion pier + counterweight tower (A-frames) over the heel
    cw.prism([list(A + (S_HEEL + d) * t + n * w) for d, w in ((-12, -8), (2, -8), (2, 8), (-12, 8))], 0.0, zt)
    for w in (-half - 0.5, half + 0.5):
        tr.seg(P(S_HEEL - 11.0, w, zt), P(S_HEEL - 5.0, w, zt + 26.0)); tr.seg(P(S_HEEL + 1.0, w, zt), P(S_HEEL - 5.0, w, zt + 26.0))
        tr.seg(P(S_HEEL - 8.0, w, zt + 13.0), P(S_HEEL - 2.0, w, zt + 13.0))
    tr.seg(P(S_HEEL - 5.0, -half - 0.5, zt + 26.0), P(S_HEEL - 5.0, half + 0.5, zt + 26.0))
    # counterweight (raised leaf -> counterweight down near the deck, behind the heel)
    cw.prism([list(A + (S_HEEL + d) * t + n * w) for d, w in ((-17, -half), (-6, -half), (-6, half), (-17, half))], zt + 3.0, zt + 11.0)
    tr.seg(P(S_HEEL - 5.0, 0, zt + 26.0), P(S_HEEL - 11.5, 0, zt + 11.0))                     # link
    # raised leaf: through Pratt truss, depth 9 m at the heel -> 5 m at the tip, panels of 6.25 m, rotated 80 deg about the trunnion
    th = math.radians(80.0); zp = zt + 2.0
    def Q(a, h, w):  # leaf local (a along the closed leaf from the heel, h above its floor) -> world
        return P(S_HEEL + a * math.cos(th) - h * math.sin(th), w, zp + a * math.sin(th) + h * math.cos(th))
    depth = lambda a: 9.0 - 4.0 * a / LEAF; panels = np.linspace(0, LEAF, 9)
    for w in (-half, half):
        for a0, a1 in zip(panels[:-1], panels[1:]):
            tr.seg(Q(a0, 0, w), Q(a1, 0, w)); tr.seg(Q(a0, depth(a0), w), Q(a1, depth(a1), w))       # chords
            tr.seg(Q(a0, 0, w), Q(a1, depth(a1), w))                                                 # diagonal
        for a in panels: tr.seg(Q(a, 0, w), Q(a, depth(a), w))                                       # verticals
    for a in panels:
        tr.seg(Q(a, 0, -half), Q(a, 0, half)); tr.seg(Q(a, depth(a), -half), Q(a, depth(a), half))   # floor beams + top struts
    for a0, a1 in zip(panels[:-1], panels[1:]): tr.seg(Q(a0, depth(a0), -half), Q(a1, depth(a1), half))   # top lateral bracing
    tip_z = zp + LEAF * math.sin(th) + depth(LEAF) * math.cos(th)
    note = ('PORT-GELLHORN-V2 2026-10-15 (Alexandre): GTADB L597 "Train Bridge" = IRL FEC Strauss Trunnion Bascule Bridge (Jacksonville), next to Bocamar Bridge. '
            'Axis = the V17 rail line across the bay (bearing 135.0 deg), over water from s %.0f to %.0f m (490 m). Bascule opening at the deepest water = the GTADB point '
            '(s 470): single-leaf through Pratt truss 50 m (depth 9 -> 5 m), RAISED 80 deg as in Port Gellhorn Postcard (X), tip %.1f m; trunnion pier, A-frame counterweight '
            'tower 26 m and counterweight block over the heel (Strauss overhead-counterweight type). Approaches: 4 plate girders (2 tracks), deck top %.1f m, piers every 25 m. '
            'All ESTIMATED (IRL: plate girder approaches, 2 tracks, 5 ft closed clearance; Postcard pose too poor to fix the leaf along the rail).' % (s0, s1, tip_z, zt))
    return {'Draper Island Rail Bascule Bridge': ('#7c2d12', m, note),
            'Draper Island Rail Bascule (Truss)': ('#7c2d12', tr, 'PORT-GELLHORN-V2 2026-10-15: steel of the Draper Island Rail Bascule Bridge: raised through-truss leaf (50 m, 80 deg) and A-frame counterweight tower; drawn as steel beams. ' + note),
            'Draper Island Rail Bascule (Deck)': ('#8b8178', dk, 'PORT-GELLHORN-V2 2026-10-15: plate-girder approach spans of the Draper Island Rail Bascule Bridge as solid deck boxes (2.6 m deep, 10.4 m wide, deck top 4.5 m ESTIMATED), 25 m spans.'),
            'Draper Island Rail Bascule (Counterweight)': ('#a8a29e', cw, 'PORT-GELLHORN-V2 2026-10-15: concrete trunnion pier and counterweight block of the Draper Island Rail Bascule Bridge (ESTIMATED sizes).')}


def build():
    F = json.load(open(FOOT))['polygons']; V = Image.open(V16); out = {}
    for name, (col, m, note) in {**refinery(F, V), **mill(), **rail_bridge()}.items():
        irl, gid = (('Vertex Energy Mobile Refinery', 'L535') if 'Refinery' in name else (('WestRock Paper Mill', 'L536') if 'Mill' in name else ('FEC Strauss Trunnion Bascule Bridge', 'L597')))
        out[name] = {'color': col, 'world_edges': m.E, 'name_game': None, 'name_irl': irl, 'gtadb': gid, '_credit': CREDIT, 'note': note}
    return out


def main():
    out = build()
    for k, v in out.items(): print('%-42s %5d edges' % (k, len(v['world_edges'])))
    if '--apply' in sys.argv:
        M = json.load(open(MESHES)); shutil.copy(MESHES, MESHES + '.bak_port_gellhorn')
        for k in OBSOLETE: M.pop(k, None)
        M.update(out); tmp = MESHES + '.tmp'; json.dump(M, open(tmp, 'w'), indent=1, ensure_ascii=True); os.replace(tmp, MESHES); print('applied ->', len(M), 'meshes')


if __name__ == '__main__':
    main()
