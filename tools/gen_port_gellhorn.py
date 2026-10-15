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
OBSOLETE = ('Draper Island Refinery', 'Draper Island Paper Mill', 'Draper Island Rail Bascule (Deck)')      # V1 names replaced by the split meshes


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
    """WestRock-style kraft mill laid out like the IRL Panama City mill (aerial: long paper-machine hall along the site,
    pulp/recovery band beside it, digesters, tank farm, evaporators, lime kiln, chip pile + inclined conveyor), scaled into
    the V17 lot; the V17 items are kept as anchors (square = recovery boiler, round = tank, rectangle = lime-kiln building,
    small rounds = stacks/vents). Lot frame: u along the lot (0..190 m, NE), v across (0..84 m, towards the SE rail)."""
    D = json.load(open(MILL)); sh = D['v16_shift']                                  # [V3b] placed on the V16 drawing (shown in the app)
    mv = lambda p: [p[0] + sh[0], p[1] + sh[1]]
    for s_ in D['shapes']: s_['ring'] = [mv(q) for q in s_['ring']]; s_['centre'] = mv(s_['centre'])
    D['stacks'] = [[x + sh[0], y + sh[1], r] for x, y, r in D['stacks']]; D['lot'] = {k: (mv(v) if isinstance(v, list) else v) for k, v in D['lot'].items()}
    S = sorted(D['shapes'], key=lambda s: -s['area_m2']); lot = D['lot']
    Lc, Tc, Bc = (np.array(lot[k], float) for k in ('L', 'T', 'B'))
    uh = (Tc - Lc) / np.linalg.norm(Tc - Lc); vh = (Bc - Lc) / np.linalg.norm(Bc - Lc)
    W_ = lambda u, v: list(Lc + u * uh + v * vh)
    rect = lambda u0, u1, v0, v1: [W_(u0, v0), W_(u1, v0), W_(u1, v1), W_(u0, v1)]
    g = float(ground(*W_(95, 42)))
    body, st, steel, racks = Mesh(), Mesh(), Mesh(), Mesh()
    main, annex, ware, tank = S[0], S[3], S[1], S[2]
    # 1) paper machine hall (IRL: the long white building) + raised roof monitor; roll warehouse at its SW end
    body.prism(rect(8, 122, 3, 27), g, g + 22.0); body.prism(rect(12, 118, 12, 18), g + 22.0, g + 26.0)
    body.prism(rect(8, 40, 27, 40), g, g + 14.0)
    # 2) recovery boiler = the V17 square (tallest block) + annex stair tower (the V17 notch); power boiler beside it
    body.prism(main['ring'], g, g + 58.0); body.prism(annex['ring'], g, g + 64.0)
    body.prism(rect(152, 166, 13, 29), g, g + 42.0)
    # 3) digesters (tall cylinders, cone top) with top platforms
    for u, v in ((110, 38), (119, 44)):
        c = W_(u, v); body.cyl(c, 3.6, g, g + 44.0, 20); body.cone(c, 3.6, g + 44.0, g + 47.0, 20)
        racks.ring(body.circle(c, 5.0, 16), g + 44.0); racks.ring(body.circle(c, 5.0, 16), g + 45.1)
    # 4) pulp / liquor tank farm (white tanks) + the V17 round tank
    for u, v in ((156, 44), (168, 44), (180, 44), (162, 57), (174, 57)):
        c = W_(u, v); body.cyl(c, 5.0, g, g + 22.0, 24); body.cone(c, 5.0, g + 22.0, g + 23.6, 24)
    gt = float(ground(*tank['centre'])); body.cyl(tank['centre'], tank['r_m'], gt, gt + 18.0, 28); body.cone(tank['centre'], tank['r_m'], gt + 18.0, gt + 20.5, 28)
    # 5) evaporator train (slender bodies in a row) with their structure
    for k in range(5):
        c = W_(128 + 4.6 * k, 63); body.cyl(c, 2.0, g, g + 30.0, 14)
    process_frame(racks, rect(125, 150, 59, 67), g, 4, fh=7.0, grid=8.0)
    # 6) lime kiln: inclined rotary cylinder on piers + kiln building (the V17 rectangle, gabled)
    c, u, n, L, Wd = obb(ware['ring']); gw = float(ground(*c)); P = lambda a, b, z: [*(c + u * a + n * b), z]
    body.prism(box_ring(c, u, n, L, Wd), gw, gw + 12.0)
    for a in (-L, L): body.seg(P(a, -Wd, gw + 12.0), P(a, 0, gw + 15.0)); body.seg(P(a, 0, gw + 15.0), P(a, Wd, gw + 12.0))
    body.seg(P(-L, 0, gw + 15.0), P(L, 0, gw + 15.0))
    k0, k1 = np.array(W_(42, 71)), np.array(W_(94, 71)); kd = (k1 - k0) / np.linalg.norm(k1 - k0); kn = np.array([-kd[1], kd[0]])
    for k in range(16):                                                      # kiln shell as a 12-sided tube, rising 3 m towards the feed end
        a0, a1 = 2 * math.pi * k / 12, 2 * math.pi * (k + 1) / 12
        if k >= 12: break
        for t0 in (0.0,):
            p0 = lambda a, tt: [*(k0 + kd * tt * 52 + kn * 1.9 * math.cos(a)), g + 6.0 + 3.0 * tt + 1.9 * math.sin(a)]
            steel.seg(p0(a0, 0), p0(a0, 1)); steel.seg(p0(a0, 0), p0(a1, 0)); steel.seg(p0(a0, 1), p0(a1, 1))
    for tt in (0.1, 0.4, 0.7, 0.95):                                         # kiln piers (concrete)
        q = k0 + kd * tt * 52; body.prism([list(q + kd * dd + kn * ww) for dd, ww in ((-1.5, -2.6), (1.5, -2.6), (1.5, 2.6), (-1.5, 2.6))], g, g + 4.0 + 3.0 * tt)
    # 7) chip pile (cone) + inclined belt-conveyor gallery up to the digester tops
    cp = W_(66, 50); body.cone(cp, 12.0, g, g + 11.0, 28)
    a_ = np.array(W_(70, 49)); b_ = np.array(W_(107, 39)); za, zb = g + 10.0, g + 47.0; dd_ = (b_ - a_) / np.linalg.norm(b_ - a_); nn_ = np.array([-dd_[1], dd_[0]])
    for k in range(9):                                                       # gallery: 2 x 3 m box truss, 8 panels, on 2 bents
        t0, t1 = k / 9, (k + 1) / 9
        q = lambda tt, w, h: [*(a_ + (b_ - a_) * tt + nn_ * w), za + (zb - za) * tt + h]
        for w in (-1.2, 1.2):
            steel.seg(q(t0, w, 0), q(t1, w, 0)); steel.seg(q(t0, w, 2.6), q(t1, w, 2.6)); steel.seg(q(t0, w, 0), q(t1, w, 2.6))
        steel.seg(q(t0, -1.2, 0), q(t0, 1.2, 0)); steel.seg(q(t0, -1.2, 2.6), q(t0, 1.2, 2.6))
    for tt in (0.35, 0.7):
        q0 = a_ + (b_ - a_) * tt; zq = za + (zb - za) * tt
        for w in (-1.6, 1.6): steel.seg([*(q0 + nn_ * w), g], [*(q0 + nn_ * w), zq])
    # 8) pipe rack along the process band
    pr = np.array(W_(42, 31)); prb = np.array(W_(104, 31)); pu = (prb - pr) / np.linalg.norm(prb - pr)
    pipe_rack(racks, (pr + prb) / 2, pu, np.array([-pu[1], pu[0]]), np.linalg.norm(prb - pr) / 2, 2.0, g)
    # 9) stacks: the two largest V17 small rounds = recovery / power boiler stacks; the others vents
    for x, y, r in D['stacks']:
        gs = float(ground(x, y))
        if r >= 1.0: st.cyl([x, y], 2.0, gs, gs + 70.0, 16); st.cyl([x, y], 2.4, gs + 67.0, gs + 70.0, 16)
        else: st.cyl([x, y], 0.9, gs, gs + 26.0, 10)
    base = ('PORT-GELLHORN-V3 2026-10-15 (Alexandre: "la papeterie est trop simple, fais-la comme la vraie et place-la environ ou on a draw sur Yanis"): '
            'GTADB L536 / L1201 = IRL WestRock Paper Mill (Panama City; closed 2022). Placed on the V16 drawing (Alexandre: "pas a son emplacement de la map de Yanis"; '
            'V17 moved the same drawing by (-57.5, +71.6) m and the rail to the other side). Layout of the IRL mill (Esri World Imagery: long paper-machine hall along '
            'the site, recovery band beside it, digesters, tank farm, evaporators, lime kiln, chip pile + conveyor) scaled into the V17 lot (190 x 84 m, long axis NE); '
            'drawn items kept as anchors: square = recovery boiler, round = liquor tank, rectangle = lime-kiln building, small rounds = stacks/vents. '
            'NOT on the map (IRL composition, positions in the lot ESTIMATED): ')
    return {'Draper Island Paper Mill (Buildings)': ('#d6d3d1', body, base + 'paper-machine hall 114 x 24 m 22 m + roof monitor, roll warehouse 14 m, power boiler 42 m, 2 digesters 44 m, '
                                                     '5 pulp tanks 22 m, 5 evaporators 30 m, chip pile 12 m, kiln piers. V17-based: recovery boiler 58 m + annex 64 m, tank d 19 m 18 m, kiln building 12 m. '
                                                     'Heights ESTIMATED (IRL practice).'),
            'Draper Island Paper Mill (Stacks)': ('#78716c', st, base + 'stacks 70 m on the two largest V17 small rounds (white steam drawn by view3d), 4 vents 26 m.'),
            'Draper Island Paper Mill (Truss)': ('#9a8f86', steel, base + 'rotary lime kiln (d 3.8 m, 52 m, inclined) and the inclined chip-conveyor gallery to the digester tops; drawn as steel beams.'),
            'Draper Island Paper Mill (Pipe Racks)': ('#9ca3af', racks, base + 'process pipe rack (62 m, 2 tiers), evaporator structure, digester platforms.')}


def rail_bridge():
    """FEC Strauss-type crossing, as in the IRL Jacksonville bridge (aerial + photos): low plate-girder trestle, a run of
    through Pratt truss spans next to the channel, single-leaf heel-trunnion bascule with a fixed steel tower at the heel,
    overhead counterweight on a frame pivoting at the tower top, timber fenders along the channel."""
    R = json.load(open(RAIL)); A = np.array(R['A']); t = np.array(R['t']); n = np.array([-t[1], t[0]]); s0, s1 = R['runs'][0][0], float(R['south_shore_s'])
    m, tr, cw, cb = Mesh(), Mesh(), Mesh(), Mesh(); zt = 4.5; half = 5.2
    decks = [Mesh(), Mesh(), Mesh()]                                          # 3 deck meshes (mesh_solids skips meshes > 450 m)
    class _DK:
        def prism(self, R_, z0, z1):
            s_ = (np.mean(R_, 0) - A) @ t; decks[0 if s_ < 470 else (1 if s_ < 705 else 2)].prism(R_, z0, z1)
    dk = _DK()
    P = lambda s, w, z: [*(A + s * t + w * n), z]
    quad = lambda sa, sb, wa, wb: [list(A + sa * t + n * wa), list(A + sb * t + n * wa), list(A + sb * t + n * wb), list(A + sa * t + n * wb)]
    S_TIP = 497.0; LEAF = 50.0; S_HEEL = S_TIP - LEAF; TRUSS0, NTR, LTR = S_HEEL - 4 * 55.0 - 8.0, 4, 55.0
    def pier(s, d=1.0, z1=zt - 1.8, w=half + 0.8): m.prism(quad(s - d, s + d, -w, w), max(0.0, float(ground(*(A + s * t)))), z1)
    def trestle(sa, sb, span=20.0):                                           # plate-girder deck (1.8 m) on bents
        ss = list(np.arange(sa, sb, span)) + [sb]
        for a, b in zip(ss[:-1], ss[1:]):
            dk.prism(quad(a + 0.2, b - 0.2, -half, half), zt - 1.8, zt)
            for w in (-half, half): m.seg(P(a, w, zt + 1.1), P(b, w, zt + 1.1))
        for s in ss: pier(s, 0.7)
    def through_truss(sa, sb, h=10.0, panels=8):                              # Pratt through truss, portal + top/bottom laterals
        ss = np.linspace(sa, sb, panels + 1)
        for w in (-half, half):
            tr.seg(P(sa, w, zt), P(sb, w, zt))
            tr.seg(P(sa, w, zt), P(ss[1], w, zt + h)); tr.seg(P(sb, w, zt), P(ss[-2], w, zt + h))          # inclined end posts
            tr.seg(P(ss[1], w, zt + h), P(ss[-2], w, zt + h))                                                   # top chord
            for k in range(1, panels):
                tr.seg(P(ss[k], w, zt), P(ss[k], w, zt + h))                                                     # verticals
                mid = panels // 2
                if k < mid: tr.seg(P(ss[k], w, zt + h), P(ss[k + 1], w, zt))                                      # Pratt diagonals (towards the centre)
                elif k > mid: tr.seg(P(ss[k], w, zt + h), P(ss[k - 1], w, zt))
        for k in range(1, panels):
            tr.seg(P(ss[k], -half, zt + h), P(ss[k], half, zt + h))                                             # top struts
            tr.seg(P(ss[k], -half, zt), P(ss[k], half, zt))                                                     # floor beams
        for k in range(1, panels - 1): tr.seg(P(ss[k], -half, zt + h), P(ss[k + 1], half, zt + h))             # top lateral bracing
        dk.prism(quad(sa + 0.3, sb - 0.3, -half + 0.4, half - 0.4), zt - 1.2, zt)                                 # deck floor
        pier(sa, 2.0, zt - 1.2, half + 1.5); pier(sb, 2.0, zt - 1.2, half + 1.5)                                   # river piers
    isl0, isl1 = R['islet_s']
    def truss_run(sa, sb):                                                    # equal through-truss spans of ~55 m over the water
        k = max(1, int(round((sb - sa) / LTR))); e = np.linspace(sa, sb, k + 1)
        for a, b in zip(e[:-1], e[1:]): through_truss(a, b)
        return k
    trestle(s0, s0 + 20.0)                                                    # short trestles at the shores and over the islet
    NT = truss_run(s0 + 20.0, S_HEEL - 12.0); trestle(S_HEEL - 12.0, S_HEEL - 2.0, 10.0)
    NT += truss_run(S_TIP + 3.0, isl0); trestle(isl0, isl1, 20.0)
    NT += truss_run(isl1, s1 - 20.0); trestle(s1 - 20.0, s1)
    # heel: trunnion pier + fixed steel tower (4 legs, braced), counterweight frame pivoting at its top, counterweight block
    cw.prism(quad(S_HEEL - 16.0, S_HEEL + 3.0, -half - 3.0, half + 3.0), 0.0, zt)
    TH = 34.0; s_a, s_b = S_HEEL - 9.0, S_HEEL + 1.0; zz = [zt, zt + 11.0, zt + 22.0, zt + TH]
    for w in (-half - 1.0, half + 1.0):
        for s in (s_a, s_b): tr.seg(P(s, w, zt), P(s, w, zt + TH))
        for z0, z1 in zip(zz[:-1], zz[1:]): tr.seg(P(s_a, w, z0), P(s_b, w, z1)); tr.seg(P(s_b, w, z0), P(s_a, w, z1))
        for z in zz[1:]: tr.seg(P(s_a, w, z), P(s_b, w, z))
    for s in (s_a, s_b):
        for z in zz[1:]: tr.seg(P(s, -half - 1.0, z), P(s, half + 1.0, z))
        tr.seg(P(s, -half - 1.0, zt + 22.0), P(s, half + 1.0, zt + TH)); tr.seg(P(s, half + 1.0, zt + 22.0), P(s, -half - 1.0, zt + TH))
    # counterweight frame (raised leaf -> frame swung down behind the tower): pivot at the tower top, block 15 x 11 x 8 m
    piv = (S_HEEL - 4.0, zt + TH); cwt0, cwt1 = S_HEEL - 26.0, S_HEEL - 11.0; czb = zt + 14.0
    cb.prism(quad(cwt0, cwt1, -half - 0.5, half + 0.5), czb, czb + 8.0)
    for w in (-half - 0.5, half + 0.5):
        tr.seg(P(piv[0], w, piv[1]), P(cwt1, w, czb + 8.0)); tr.seg(P(piv[0], w, piv[1]), P(cwt0, w, czb + 8.0))   # counterweight frame
        tr.seg(P(cwt1, w, czb + 8.0), P(S_HEEL + 2.0, w, zt + 8.0))                                                 # link to the leaf heel
    # raised leaf: through Pratt truss 50 m, 10 -> 6 m deep, raised 80 deg about the trunnion at the heel
    th = math.radians(80.0); zp = zt + 1.0
    def Q(a, h, w): return P(S_HEEL + a * math.cos(th) - h * math.sin(th), w, zp + a * math.sin(th) + h * math.cos(th))
    depth = lambda a: 10.0 - 4.0 * a / LEAF; panels = np.linspace(0, LEAF, 9)
    for w in (-half, half):
        for a0, a1 in zip(panels[:-1], panels[1:]):
            tr.seg(Q(a0, 0, w), Q(a1, 0, w)); tr.seg(Q(a0, depth(a0), w), Q(a1, depth(a1), w)); tr.seg(Q(a0, 0, w), Q(a1, depth(a1), w))
        for a in panels: tr.seg(Q(a, 0, w), Q(a, depth(a), w))
    for a in panels: tr.seg(Q(a, 0, -half), Q(a, 0, half)); tr.seg(Q(a, depth(a), -half), Q(a, depth(a), half))
    for a0, a1 in zip(panels[:-1], panels[1:]): tr.seg(Q(a0, depth(a0), -half), Q(a1, depth(a1), half))
    tip_z = zp + LEAF * math.sin(th) + depth(LEAF) * math.cos(th)
    # rest pier at the tip + timber fenders along the channel (both sides, 70 m)
    cw.prism(quad(S_TIP - 1.0, S_TIP + 3.0, -half - 2.0, half + 2.0), 0.0, zt)
    for w0 in (-half - 9.0, half + 7.5): cw.prism(quad(S_HEEL - 10.0, S_TIP + 15.0, w0, w0 + 1.2), 0.0, 1.6)
    note = ('PORT-GELLHORN-V3 2026-10-15 (Alexandre: "le bridge est encore pas bon"): GTADB L597 "Train Bridge" = IRL FEC Strauss Trunnion Bascule Bridge (Jacksonville), '
            'next to Bocamar Bridge. Built like the IRL bridge (Esri aerial + photos): low plate-girder trestle, %d through Pratt truss spans of %.0f m (10 m high) next '
            'to the channel, single-leaf heel-trunnion bascule 50 m (through truss 10 -> 6 m) RAISED 80 deg (as in Port Gellhorn Postcard (X)), tip %.1f m; fixed braced '
            'steel tower 34 m at the heel, counterweight frame pivoting at its top with a 15 x 11 x 8 m concrete block (swung down behind the tower when open), link to the '
            'heel, rest pier, timber fenders along the channel. Axis = the V17 rail line (bearing 135.0 deg) = the V16 one, from the Draper Island shore to the Port Gellhorn beach '
            '(s %.0f..%.0f m, over an islet at s 665-705; V3b: extended to the south shore, the PORT GELLHORN label had cut the water test at s 575); opening at the deepest water = '
            'the GTADB point (s 470). Deck top %.1f m. Sizes ESTIMATED (IRL: plate girder approaches, simple truss, bascule, 2 tracks).' % (LTR, NT, tip_z, s0, s1, zt))
    return {'Draper Island Rail Bascule Bridge': ('#7c2d12', m, note),
            'Draper Island Rail Bascule (Truss)': ('#7c2d12', tr, 'Steel of the Draper Island Rail Bascule Bridge (fixed through trusses, raised leaf, heel tower, counterweight frame), drawn as steel beams. ' + note),
            **{'Draper Island Rail Bascule (Deck %s)' % k: ('#8b8178', decks[i], 'Decks of the Draper Island Rail Bascule Bridge (%s part): trestle girders 1.8 m and truss-span floors 1.2 m, deck top 4.5 m ESTIMATED. ' % k + note)
               for i, k in enumerate(('N', 'S', 'SE'))},
            'Draper Island Rail Bascule (Counterweight)': ('#a8a29e', cw, 'Concrete of the Draper Island Rail Bascule Bridge: trunnion pier, rest pier, timber fenders (ESTIMATED sizes). ' + note),
            'Draper Island Rail Bascule (Counterweight Block)': ('#b8b2a8', cb, 'Concrete counterweight block 15 x 11 x 8 m of the Draper Island Rail Bascule Bridge, hanging from its frame (drawn by view3d as a block, not a height field). ' + note)}


def build():
    F = json.load(open(FOOT))['polygons']; V = Image.open(V16); out = {}
    for name, (col, m, note) in {**refinery(F, V), **mill(), **rail_bridge()}.items():
        irl, gid = (('Vertex Energy Mobile Refinery', 'L535') if 'Refinery' in name else (('WestRock Paper Mill', 'L536') if 'Mill' in name else ('FEC Strauss Trunnion Bascule Bridge', 'L597')))
        out[name] = {'color': col, 'world_edges': m.E, 'name_game': None, 'name_irl': irl, 'gtadb': gid, '_credit': CREDIT, 'note': note}
        if 'Bascule (' in name: out[name]['facade'] = {'kind': 'none', 'color': [0.66, 0.64, 0.6]}          # concrete, no windows
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
