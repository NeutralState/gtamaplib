#!/usr/bin/env python3
"""scene_props.py — set dressing for the cinematic camera tour (view3d), scene by scene. [SCENE-PROPS-V1 2026-10-19]

Alexandre (YouTube video of the Trailer 4 tour): when the tour lands on a camera, the 3D view must look like the frame;
the first scene (T4/1 Truck with Jet Ski, US 1 entering Key Lento) had nothing in 3D. Props are simple primitives placed
by BACK-PROJECTING what the frame shows from the camera's pose (pixel measurements listed per scene below), so they land
where the frame has them; their sizes and positions are ESTIMATED (one frame, assumed camera height / sign sizes).
Primitives (tools/threejs/scene_props.json, drawn by view3d [SCENE-PROPS-V1]):
  quad  {p: 4 corners [x,y,z], color}            road surfaces, markings
  box   {c: [x,y,z] (base centre), s: [length, width, height], az (deg, length axis), color}
  cyl   {a: [x,y,z], b: [x,y,z], r, color}       poles, posts, trunks
  line  {pts: [[x,y,z]...], color}               wires
  tex   {p: 4 corners (bl, br, tr, tl), img}     textured panel (image cut from the frame, gitignored like _fac_*.png)
  blob  {c: [x,y,z], r: [rx, ry, rz], color}     bushes / tree crowns
  palm  {a: [x,y,z], h, lean_az, lean}           palm (trunk + fronds)
A scene may also list 'replace': mesh names whose wireframe view3d no longer draws (rebuilt here as solids), and 'clear' polygons [[x,y]...]: view3d does not extrude the V16 massing footprints whose centroid falls
inside (e.g. V16 boxes that land on a modelled road).
Usage: python3 tools/scene_props.py            (writes tools/threejs/scene_props.json and the _prop_*.png textures)
"""
import json, math, os, sys
import numpy as np, cv2
from scipy.spatial.transform import Rotation as Rot

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS)
from horizon_resect import ground as terrain

OUT = os.path.join(THIS, 'threejs', 'scene_props.json')
CAMS = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))


class View:
    """pinhole of a camera of cameras.json (repo convention: R.from_euler('ZXY', ypr), forward = +y)."""
    def __init__(self, name):
        c = CAMS[name]; self.W, self.H = c['size']; self.o = np.array(c['xyz'], float)
        self.R = Rot.from_euler('ZXY', c['ypr'], degrees=True).as_matrix(); self.th = math.tan(math.radians(c['fov'][0]) / 2); self.tv = self.th * self.H / self.W
    def ray(self, u, v):
        return self.R @ np.array([((u + 0.5) / self.W * 2 - 1) * self.th, 1.0, (1 - (v + 0.5) / self.H * 2) * self.tv])
    def on_plane_z(self, u, v, z):
        d = self.ray(u, v); return self.o + d * (z - self.o[2]) / d[2]
    def on_vplane(self, u, v, p0, n):
        """intersection with the vertical plane through p0 (xy) with horizontal normal n."""
        d = self.ray(u, v); n3 = np.array([n[0], n[1], 0.0]); t = ((np.array([p0[0], p0[1], 0.0]) - self.o) @ n3) / (d @ n3); return self.o + d * t


def T(x, y): return float(terrain(np.array([x]), np.array([y]))[0])


def keys_entrance():
    """T4/1 Truck with Jet Ski — US 1 southbound entering Key Lento: 3-lane carriageway, jersey barriers, the
    'Welcome to The Keys' billboard, utility poles and wires, an overhead sign gantry, mangrove bushes and palms.
    Frame measurements (3840 x 1920): vanishing point of the road (299, 1149); right barrier base (1960,1330) (2800,1410)
    (3680,1520); lane line (2300,1480) (3800,1730); left yellow edge (120,1530) (380,1460) -> with the camera 1.6 m above
    the road they give: left edge 0 m, lane line 8.3 m, barrier 12.6 m to the right, parallel to the road (az 160)."""
    V = View('Truck with Jet Ski'); P = []; AZ = 160.0
    dv = np.array([math.sin(math.radians(AZ)), math.cos(math.radians(AZ))]); rv = np.array([math.sin(math.radians(AZ + 90)), math.cos(math.radians(AZ + 90))])
    O = V.o[:2]; zr = V.o[2] - 1.6
    at = lambda s, l: O + dv * s + rv * l                                 # road frame: s along (m), l to the right (m)
    zg = lambda s, l: max(T(*at(s, l)), 0.3)
    def strip(l0, l1, s0, s1, col, step=10.0, dz=0.04):
        for s in np.arange(s0, s1, step):
            q = [at(s, l0), at(s, l1), at(s + step, l1), at(s + step, l0)]
            z = [zroad(s), zroad(s), zroad(s + step), zroad(s + step)]
            P.append(dict(k='quad', p=[[round(a[0], 2), round(a[1], 2), round(zz + dz, 2)] for a, zz in zip(q, z)], color=col))
    # the road surface follows a smoothed profile: the camera's road height here, the terrain further on
    def zroad(s):                                                          # the road deck is never under the (12 m) heightmap
        z = zr if s < 15 else zr - 0.012 * (s - 15)
        return max(z, max(zg(s, l) for l in (-1.0, 3.0, 6.0, 9.0, 13.4)) + 0.25)
    S0, S1 = -40.0, 260.0
    strip(-1.0, 13.4, S0, S1, '#3b3c3f')                                  # asphalt, 3 lanes + shoulders
    strip(0.05, 0.25, S0, S1, '#d9b23a', dz=0.06)                         # yellow left edge line (Florida)
    for l in (4.0, 7.7):                                                   # dashed lane lines (3 m dash / 9 m gap)
        for s in np.arange(S0, S1, 12.0): strip(l, l + 0.15, s, s + 3.0, '#e8e8e2', step=3.0, dz=0.06)
    strip(11.4, 11.55, S0, S1, '#e8e8e2', dz=0.06)                        # right edge line
    for l0, name in ((12.6, 'right'), (-1.6, 'median')):                  # jersey barriers (0.85 m)
        for s in np.arange(S0, 180.0, 6.0):
            c = at(s + 3, l0 + 0.3); P.append(dict(k='box', c=[round(c[0], 2), round(c[1], 2), round(zroad(s + 3), 2)], s=[6.0, 0.6, 0.85], az=AZ, color='#a9aea4'))
    # billboard 'Welcome to The Keys': panel u 1585..2215, v 643..1104 (frame px); it faces the oncoming (southbound)
    # traffic: vertical plane perpendicular to the road, at the distance where its centre sits 4.5 m behind the barrier
    def board_at(sb):
        n = -dv; p0 = at(sb, 0.0); return n, p0, V.on_vplane(1900, 873, p0, n)
    sb = min(np.arange(10, 120, 0.25), key=lambda q: abs(((board_at(q)[2][:2] - O) @ rv) - 17.1))
    n, p0, _ = board_at(sb)
    BL, BR = V.on_vplane(1585, 1104, p0, n), V.on_vplane(2215, 1104, p0, n); TL, TR = V.on_vplane(1585, 643, p0, n), V.on_vplane(2215, 643, p0, n)
    img = cv2.imread(os.path.join(REPO, 'frames', 'Truck with Jet Ski.png'))
    if img is not None:
        cv2.imwrite(os.path.join(THIS, 'threejs', '_prop_keys_billboard.png'), img[643:1105, 1585:2216])
    P.append(dict(k='tex', p=[list(np.round(q, 2)) for q in (BL, BR, TR, TL)], img='_prop_keys_billboard.png'))
    back = -n * 0.3                                                        # the frame box sits BEHIND the printed face
    P.append(dict(k='box', c=list(np.round(np.r_[(BL[:2] + BR[:2]) / 2 + back[:2], BL[2] - 0.2], 2)), s=[0.4, float(np.linalg.norm(BR[:2] - BL[:2])) + 0.4, float(TL[2] - BL[2]) + 0.4],
                  az=AZ, color='#30343a'))
    for u in (1680, 2030):
        top = V.on_vplane(u, 1104, p0, n) + np.r_[back[:2], 0]; g = zg(*((top[:2] - O) @ np.c_[dv, rv]))
        P.append(dict(k='cyl', a=[round(top[0], 2), round(top[1], 2), round(g - 0.2, 2)], b=list(np.round(top + [0, 0, 0.5], 2)), r=0.22, color='#5a5f66'))
    # utility poles (concrete, ~13 m) on a line 7 m behind the barrier; frame u of the poles: 2990 (near), 1825, 1440, 1380
    pl = at(0, 19.6); tops = []
    for u in (2990, 1825, 1440, 1385):
        q = V.on_vplane(u, 900, pl, rv); g = zg(*((q[:2] - O) @ np.c_[dv, rv])); a = [q[0], q[1], g]; b = [q[0], q[1], g + 13.0]
        P.append(dict(k='cyl', a=list(np.round(a, 2)), b=list(np.round(b, 2)), r=0.28, color='#c9c6bd'))
        for zz in (12.2, 11.0):
            e1 = q[:2] + rv * 1.6; e2 = q[:2] - rv * 1.6
            P.append(dict(k='cyl', a=[round(e1[0], 2), round(e1[1], 2), round(g + zz, 2)], b=[round(e2[0], 2), round(e2[1], 2), round(g + zz, 2)], r=0.09, color='#8a8578'))
        tops.append((q[:2], g))
    tops.sort(key=lambda t: (t[0] - O) @ dv)
    for (qa, ga), (qb, gb) in zip(tops[:-1], tops[1:]):                    # 3 wires per span, sagging 0.8 m
        for off, zz in ((1.4, 12.2), (-1.4, 12.2), (0.0, 11.0)):
            pts = []
            for t in np.linspace(0, 1, 13):
                xy = qa + (qb - qa) * t + rv * off; z = ga + zz + (gb - ga) * t - 0.8 * 4 * t * (1 - t)
                pts.append([round(xy[0], 2), round(xy[1], 2), round(z, 2)])
            P.append(dict(k='line', pts=pts, color='#2b2b2b'))
    # overhead sign gantry ~48 m ahead (panel centre 7.5 m above the road, frame u 150..530 of 1600 -> 360..1270)
    sg = 85.0; zz = zroad(sg)
    for l in (-2.0, 13.8):
        a = at(sg, l); P.append(dict(k='cyl', a=[round(a[0], 2), round(a[1], 2), round(zz, 2)], b=[round(a[0], 2), round(a[1], 2), round(zz + 8.6, 2)], r=0.3, color='#9aa0a6'))
    a, b = at(sg, -2.0), at(sg, 13.8)
    for dz_ in (8.1, 8.9):
        P.append(dict(k='cyl', a=[round(a[0], 2), round(a[1], 2), round(zz + dz_, 2)], b=[round(b[0], 2), round(b[1], 2), round(zz + dz_, 2)], r=0.16, color='#9aa0a6'))
    for l0, l1 in ((1.0, 5.4), (6.4, 10.4)):                               # two green guide signs
        c = at(sg - 0.4, (l0 + l1) / 2); P.append(dict(k='box', c=[round(c[0], 2), round(c[1], 2), round(zz + 6.3, 2)], s=[0.25, l1 - l0, 2.3], az=AZ, color='#1f6b3a'))
    # mangroves / bushes behind the right barrier and on the median, a few palms near the billboard
    rng = np.random.default_rng(41)
    tones = ['#2f4a24', '#3e5f2c', '#4d6b31', '#2a3d1e', '#56743a']
    for _ in range(90):                                                    # mangrove clumps: 3-6 overlapping crowns each
        s0 = rng.uniform(-30, 200); l0 = rng.uniform(14.0, 48.0)
        if abs(s0 - sb) < 10 and l0 < 21: continue                         # keep the billboard face clear
        tall = 2.5 if l0 < 17 else rng.uniform(4.0, 8.0)                   # low scrub along the barrier, taller mangroves behind
        if abs(s0 - sb) < 25 and l0 / max(s0, 1) < 0.84: tall = min(tall, 4.0)   # sky stays clear above the billboard
        for _ in range(int(rng.integers(3, 7))):
            s = s0 + rng.normal(0, 3.0); l = l0 + rng.normal(0, 2.5); r = rng.uniform(1.0, 2.2); c = at(s, l); g = zg(s, l)
            hz = rng.uniform(0.6, 1.0) * tall
            P.append(dict(k='blob', c=[round(c[0], 2), round(c[1], 2), round(g + hz, 2)], r=[round(r * 1.25, 2), round(r * 1.25, 2), round(r, 2)], color=tones[int(rng.integers(len(tones)))]))
    for s, l, hgt in ((3, 14.2, 9.5), (6, 15.8, 11.0), (9.5, 14.6, 10.0), (12, 17.5, 12.0), (5, 19.5, 12.5), (15, 20, 11.0), (1, 17, 10.5)):   # frame right edge: > 40 deg right of the road
        c = at(s, l); g = zg(s, l)                                         # tall broadleaf trees close on the right (frame top-right)
        P.append(dict(k='cyl', a=[round(c[0], 2), round(c[1], 2), round(g, 2)], b=[round(c[0], 2), round(c[1], 2), round(g + hgt * 0.6, 2)], r=0.35, color='#5b4a38'))
        for _ in range(4):
            q = c + rng.normal(0, 1.6, 2)
            P.append(dict(k='blob', c=[round(q[0], 2), round(q[1], 2), round(g + hgt * rng.uniform(0.72, 0.95), 2)], r=[3.2, 3.2, 2.6], color=tones[int(rng.integers(len(tones)))]))
    for s, l, hgt in ((22, 21, 10.5), (30, 25, 12.0), (12, 27, 11.0), (55, 23, 9.5), (70, 30, 12.5), (-6, 24, 10.0)):
        c = at(s, l); P.append(dict(k='palm', a=[round(c[0], 2), round(c[1], 2), round(zg(s, l), 2)], h=hgt, lean_az=round(AZ + 60, 1), lean=0.12))
    clear = [[list(np.round(at(s_, l_), 1)) for s_, l_ in ((-40, -4), (260, -4), (260, 16), (-40, 16))]]   # road corridor: no V16 massing box on it
    return dict(scene='T4/1 Truck with Jet Ski', camera='Truck with Jet Ski', note=keys_entrance.__doc__.split('\n')[0], props=P, clear=clear)


def _key_letters(crop):
    """alpha mask of the salmon/red sign letters (frame crop): red clearly above green and blue."""
    b, g, r = [crop[..., i].astype(int) for i in range(3)]
    a = ((r - g > 45) & (r - b > 35) & (r > 120)).astype(np.uint8) * 255
    a = cv2.morphologyEx(a, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)); a = cv2.GaussianBlur(a, (3, 3), 0)
    return np.dstack([crop, a])


def _xform(P, F, rot):
    """move props built in a local (V17 footprint) frame into the world: F(x, y) -> world xy, boxes turn by -rot (compass)."""
    m3 = lambda q: [round(float(v), 2) for v in (*F(q[0], q[1]), q[2])]
    for p in P:
        if p['k'] in ('quad', 'tex'): p['p'] = [m3(q) for q in p['p']]
        elif p['k'] == 'box': p['c'] = m3(p['c']); p['az'] = round((p['az'] - rot) % 360, 2)
        elif p['k'] == 'cyl': p['a'], p['b'] = m3(p['a']), m3(p['b'])
        elif p['k'] == 'blob': p['c'] = m3(p['c'])
        elif p['k'] == 'palm': p['a'] = m3(p['a'])
    return P


def brians_marina():
    """T4/2 Brian's Marina — the dry-stack shed of Key Lento (its north gable is the 'Brian's Boat Works & Marina' door
    of T2/30). Pose fit (T4-VIDEO-FIT-3 2026-10-19): the V17 blue-grey footprint shifted (+26.0, -57.1) m and turned 8.1 deg,
    50 m long, eave 11.8 / ridge 15.6 m, with the radio tower '102180 Overseas Hwy' and the blimp landmarks (horizon). Props: gable shed, rooftop 'BRIAN'S MARINA' letters keyed out of the frame, the T2/30 gable sign, 5-level
    boat racks with boats, 'RENT A RACK' sign, parking lot, boats on trailers, palms, and the blimp in the sky."""
    V = View("Brian's Marina"); P = []
    XW, XE, YN, YS = -2570.0, -2537.0, -5827.0, -5877.0; xm = (XW + XE) / 2; E, R = 11.81, 15.59
    C0, SH, ROT = np.array([-2553.5, -5866.0]), np.array([25.99, -57.11]), 8.10
    ca, sa = math.cos(math.radians(ROT)), math.sin(math.radians(ROT))
    F = lambda x, y: C0 + np.array([[ca, -sa], [sa, ca]]) @ (np.array([x, y], float) - C0) + SH
    g = T(*F(xm, (YN + YS) / 2))
    L = []                                                                  # ---- shed + racks in the footprint frame
    L.append(dict(k='box', c=[xm, (YN + YS) / 2, g], s=[YN - YS, XE - XW, E], az=0.0, color='#78aca6'))
    o = 0.6
    L.append(dict(k='quad', p=[[XW - o, YN + o, g + E - 0.3], [XW - o, YS - o, g + E - 0.3], [xm, YS - o, g + R], [xm, YN + o, g + R]], color='#cfd0cb'))
    L.append(dict(k='quad', p=[[XE + o, YN + o, g + E - 0.3], [XE + o, YS - o, g + E - 0.3], [xm, YS - o, g + R], [xm, YN + o, g + R]], color='#d6d6d1'))
    for yy in (YN, YS):
        L.append(dict(k='quad', p=[[XW, yy, g + E], [XE, yy, g + E], [xm, yy, g + R - 0.2], [xm, yy, g + R - 0.2]], color='#78aca6'))
    L.append(dict(k='quad', p=[[xm - 6, YN + 0.08, g], [xm + 6, YN + 0.08, g], [xm + 6, YN + 0.08, g + 7.6], [xm - 6, YN + 0.08, g + 7.6]], color='#1b1f22'))
    bw = cv2.imread(os.path.join(REPO, 'frames', "Brian's Boat Works.png"))
    if bw is not None: cv2.imwrite(os.path.join(THIS, 'threejs', '_prop_brians_gable.png'), bw[12:349, 1836:2497])
    L.append(dict(k='tex', p=[[xm + 3.4, YN + 0.12, g + 8.0], [xm - 3.4, YN + 0.12, g + 8.0], [xm - 3.4, YN + 0.12, g + 11.5], [xm + 3.4, YN + 0.12, g + 11.5]], img='_prop_brians_gable.png'))
    rng = np.random.default_rng(2); x0r, x1r = XE + 0.4, XE + 17.0; ys = np.arange(-5832.0, -5877.1, -6.5)
    lv = [g + 0.4 + 2.5 * k for k in range(5)]                           # 5 levels under the 11.8 m eave
    for x_ in (x0r, x1r):
        for y_ in ys: L.append(dict(k='cyl', a=[x_, y_, g], b=[x_, y_, lv[-1] + 2.0], r=0.15, color='#3d4043'))
        for z_ in lv + [lv[-1] + 2.0]: L.append(dict(k='cyl', a=[x_, ys[0], z_], b=[x_, ys[-1], z_], r=0.1, color='#3d4043'))
    for y_ in ys:
        for z_ in lv: L.append(dict(k='cyl', a=[x0r, y_, z_], b=[x1r, y_, z_], r=0.08, color='#3d4043'))
    hulls = ['#ecece8', '#e6e3dc', '#d9d4c7', '#b9ab8f', '#a8977a', '#5a5a58', '#f0f0ee']
    for ya, yb in zip(ys[:-1], ys[1:]):
        for z_ in lv:
            for yc in (ya - 1.65, yb + 1.65):
                if rng.random() < 0.12: continue
                Lb = rng.uniform(6.0, 8.0); col = hulls[int(rng.integers(len(hulls)))]
                L.append(dict(k='box', c=[x1r - Lb / 2 + 0.6, yc, z_ + 0.12], s=[Lb, 2.2, 1.0], az=90.0, color=col))
                if rng.random() < 0.5: L.append(dict(k='box', c=[x1r - Lb / 2 - 0.4, yc, z_ + 1.12], s=[Lb * 0.45, 1.7, 0.65], az=90.0, color='#f2f2f0' if col not in ('#b9ab8f', '#a8977a') else col))
    L.append(dict(k='quad', p=[[XE + 10.5, YN - 25, g + 0.06], [XE + 38, YN - 25, g + 0.06], [XE + 38, YN + 32, g + 0.06], [XE + 10.5, YN + 32, g + 0.06]], color='#2e3032'))
    L.append(dict(k='quad', p=[[XW - 6, YN, g + 0.05], [XE + 10.5, YN, g + 0.05], [XE + 10.5, YN + 32, g + 0.05], [XW - 6, YN + 32, g + 0.05]], color='#34363a'))
    P += _xform(L, F, ROT)
    rotv = lambda v: np.array([[ca, -sa], [sa, ca]]) @ np.array(v, float)
    r2 = lambda a: [round(float(v), 2) for v in a]
    # ---- frame-derived props (world): rooftop letters, RENT A RACK, trailers, palms
    fr = cv2.imread(os.path.join(REPO, 'frames', "Brian's Marina.png"))
    if fr is not None:
        cv2.imwrite(os.path.join(THIS, 'threejs', '_prop_brians_letters.png'), _key_letters(fr[581:763, 994:1982]))
        cv2.imwrite(os.path.join(THIS, 'threejs', '_prop_brians_rentarack.png'), fr[1452:1657, 996:1530])
    n = rotv((1.0, 0.0)); p0 = F(xm + 4.0, YN)
    BL, BR, TR, TL = (V.on_vplane(u, v, p0, n) for u, v in ((994, 762), (1981, 762), (1981, 581), (994, 581)))
    P.append(dict(k='tex', p=[r2(q) for q in (BL, BR, TR, TL)], img='_prop_brians_letters.png', alpha=True))
    for t in np.linspace(0.04, 0.96, 6):
        q = BL + (BR - BL) * t - np.r_[n * 0.3, 0]; P.append(dict(k='cyl', a=r2([q[0], q[1], g + R - 1.2]), b=r2([q[0], q[1], TL[2]]), r=0.1, color='#4a4d50'))
    q = [V.on_vplane(u, v, F(x1r + 0.35, YN), n) for u, v in ((996, 1656), (1529, 1656), (1529, 1452), (996, 1452))]
    P.append(dict(k='tex', p=[r2(a) for a in q], img='_prop_brians_rentarack.png'))
    for u, v, az in ((2700, 1480, 40.0), (2560, 1540, 45.0)):
        q = V.on_plane_z(u, v, g + 0.6); P.append(dict(k='box', c=r2([q[0], q[1], g + 0.6]), s=[8.0, 2.6, 1.5], az=az, color='#efefec'))
        P.append(dict(k='box', c=r2([q[0], q[1], g + 2.1]), s=[3.4, 2.1, 1.0], az=az, color='#e5ded0'))
    for u, v, hgt in ((2050, 1360, 11.0), (2900, 1260, 13.0), (3100, 1230, 12.0), (3330, 1250, 13.5), (3580, 1230, 12.0), (560, 930, 10.0), (2860, 1460, 9.0)):
        q = V.on_plane_z(u, v, g); P.append(dict(k='palm', a=r2(q), h=hgt, lean_az=300.0, lean=0.08))
    # ---- the blimp (frame u 2664..2808, v 96..168): ~2 km out on its ray, side view -> axis across the view
    d = V.ray(2736, 132); d2 = d[:2] / np.linalg.norm(d[:2]); bc = V.o + d / np.linalg.norm(d[:2]) * 2000.0
    ax = math.degrees(math.atan2(d2[0], d2[1])) + 90.0; Lb = 2000.0 * (2808 - 2664) / (V.W / 2 / V.th); rb = Lb * 0.13
    P.append(dict(k='blob', c=r2(bc), r=[round(Lb / 2, 1), round(rb, 1), round(rb, 1)], az=round(ax % 360, 1), color='#c9ccd1', smooth=True))
    u_ = np.array([math.sin(math.radians(ax)), math.cos(math.radians(ax))]); tail = bc[:2] - u_ * Lb * 0.42
    for dz_, side in ((rb * 0.9, 0), (-rb * 0.9, 0), (0, rb * 0.9), (0, -rb * 0.9)):
        w = np.array([-u_[1], u_[0]]) * side; P.append(dict(k='box', c=r2([tail[0] + w[0], tail[1] + w[1], bc[2] + dz_ - (0.3 * rb if dz_ > 0 else 0)]), s=[Lb * 0.12, 0.6 if side == 0 else rb * 0.7, rb * 0.7 if side == 0 else 0.6], az=round(ax % 360, 1), color='#9da2a8'))
    P.append(dict(k='box', c=r2([bc[0], bc[1], bc[2] - rb * 1.05]), s=[Lb * 0.14, rb * 0.35, rb * 0.3], az=round(ax % 360, 1), color='#6d7278'))
    # foreground: the frame's bottom edge is tree crowns (the camera looks over them), mid-ground a dark asphalt yard
    rng2 = np.random.default_rng(22); tones = ['#2b3d22', '#344a27', '#3d552c', '#26361e']
    for u in list(np.linspace(1750, 3950, 16)) + list(np.linspace(-150, 350, 4)):     # crowns whose tops just enter the bottom edge
        for v in (2010, 2120):
            q = V.on_plane_z(u, v, g); r = rng2.uniform(2.6, 3.6)
            P.append(dict(k='blob', c=r2([q[0], q[1], g + rng2.uniform(3.0, 4.5)]), r=[r, r, r * 0.8], color=tones[int(rng2.integers(4))]))
    # tree mass BEHIND the shed (frame: dense crowns between the roof and the houses, u 300..2900, v 380..700)
    dsh = float(np.linalg.norm(F(xm, (YN + YS) / 2) - V.o[:2]))
    for u in np.arange(250, 3000, 110):
        for v in (430, 520, 610, 690):
            d = V.ray(u, v); d = d / np.linalg.norm(d[:2])
            for _ in range(2):
                D = dsh + rng2.uniform(22, 75); q = V.o + d * D; r = rng2.uniform(4.0, 6.5)
                zc = max(g + r * 0.8, q[2] - r * 0.4)
                if zc - g > 13: continue                                       # not taller than ~16 m trees
                P.append(dict(k='blob', c=r2([q[0], q[1], zc]), r=[r, r, r * 0.85], color=tones[int(rng2.integers(4))]))
    L2 = [dict(k='quad', p=[[XE + 17.5, YS - 10, g + 0.07], [XE + 90, YS - 10, g + 0.07], [XE + 90, YN + 40, g + 0.07], [XE + 17.5, YN + 40, g + 0.07]], color='#2a2c2e')]
    P += _xform(L2, F, ROT)
    clear = [[list(np.round(F(x_, y_), 1)) for x_, y_ in ((XW - 6, YS - 14), (XE + 95, YS - 14), (XE + 95, YN + 45), (XW - 6, YN + 45))]]
    clear.append([[-2672, -5919], [-2632, -5919], [-2632, -5879], [-2672, -5879]])   # V16 box #88: water on the frame (Alexandre: 'un building dans l'eau')
    return dict(scene='T4/2 Brian\'s Marina', camera="Brian's Marina", note=brians_marina.__doc__.split('\n')[0], props=P, clear=clear)


def keys_landmarks():
    """Key Lento landmarks seen from several tour scenes: the rectangular concrete radio tower '102180 Overseas Hwy'
    (top triangulated from 4 cameras, z 40.3; seen in Key Lento, T4/2 ...) with its antenna mast. Footprint 3.8 x 3.8 m (width on the T4/2 frame) and the
    floor bands are ESTIMATED from the Key Lento frame."""
    P = []; x, y, ztop = -2633.6, -6018.4, 40.3; g = T(x, y)
    P.append(dict(k='box', c=[x, y, round(g, 2)], s=[3.8, 3.8, round(ztop - g, 2)], az=0.0, color='#aaa59c'))
    for zz in np.arange(g + 6, ztop - 2, 4.5):                            # darker window bands
        P.append(dict(k='box', c=[x, y, round(float(zz), 2)], s=[3.9, 3.9, 0.7], az=0.0, color='#8a8c8d'))
    P.append(dict(k='box', c=[x, y, round(ztop, 2)], s=[2.6, 2.6, 1.8], az=0.0, color='#8e8a82'))
    P.append(dict(k='cyl', a=[x, y, round(ztop + 2.2, 2)], b=[x, y, round(ztop + 12.0, 2)], r=0.25, color='#cfcfcf'))
    return dict(scene='Key Lento landmarks', camera=None, note=keys_landmarks.__doc__.split('\n')[0], props=P)


def keys_bridges():
    """The 5 Keys bridges of tools/gen_keys_bridges.py as SOLIDS (Alexandre: the bridge behind scene 2 'looked exploded':
    it was only drawn as wireframe + the flat V16 road ribbon on the water). Same geometry (axes, deck profiles, piers) as
    the meshes, rebuilt with a Bridge subclass that emits slabs, parapets, columns, caps and footings; the meshes' own
    wireframes are hidden in view3d ('replace')."""
    import gen_keys_bridges as GB
    P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    class SB(GB.Bridge):
        col = '#c9ccce'
        def az(self, s): _, u, _ = self.frame(s); return math.degrees(math.atan2(u[0], u[1])) % 360
        def box(self, s, w, z0, along, across, hgt, col=None):
            q = self.P(s, w, z0); P.append(dict(k='box', c=r2(q), s=[round(along, 2), round(across, 2), round(hgt, 2)], az=round(self.az(s), 2), color=col or self.col))
        def L(self, a, b):                                                  # leftover edges (trusses, arches): thin members
            if abs(a[0] - b[0]) < 0.05 and abs(a[1] - b[1]) < 0.05 and min(a[2], b[2]) <= 0.1:
                P.append(dict(k='box', c=r2([a[0], a[1], -0.5]), s=[1.4, 1.4, round(max(a[2], b[2]) + 0.5, 2)], az=0.0, color='#b8b4ac'))
            else: P.append(dict(k='cyl', a=r2(a), b=r2(b), r=0.18, color='#8f8a82'))
        def deck(self, s0, s1, zb, w0, w1, depth=1.8, parapet=1.0, step=10.0, frame=20.0):
            ss = list(np.arange(s0, s1, step)) + [s1]
            for a, b in zip(ss[:-1], ss[1:]):
                za, zb_ = zb(a), zb(b)
                A = lambda w, dz, s_=a, z=za: self.P(s_, w, z + dz); B_ = lambda w, dz, s_=b, z=zb_: self.P(s_, w, z + dz)
                P.append(dict(k='quad', p=[A(w0, depth), B_(w0, depth), B_(w1, depth), A(w1, depth)], color='#5d6064'))   # road surface
                P.append(dict(k='quad', p=[A(w0, 0), B_(w0, 0), B_(w1, 0), A(w1, 0)], color='#a9a8a3'))                   # soffit
                for w in (w0, w1):
                    P.append(dict(k='quad', p=[A(w, 0), B_(w, 0), B_(w, depth + parapet), A(w, depth + parapet)], color=self.col))   # fascia + parapet
        def bent(self, s, zb, w0, w1, ncol=2, col=1.2, zw=0.0, cap=1.4, tie=12.0, footing=1.5):
            z = zb(s); m = 0.18 * (w1 - w0)
            for w in np.linspace(w0 + m, w1 - m, ncol): self.box(s, w, zw, col, col, z - cap - zw)
            self.box(s, (w0 + w1) / 2, z - cap, 1.8, w1 - w0 - 0.6, cap)
            self.box(s, (w0 + w1) / 2, zw - 0.5, 4.4, w1 - w0 - 2 * m + 3.6, footing + 0.5, '#b0aca4')
        def abutment(self, s, zb, w0, w1, back):
            z = zb(s) + 1.8; self.box(s + back / 2, (w0 + w1) / 2, 0.0, abs(back), w1 - w0, max(z - 1.0, 1.0), '#b8b4ac')
    def pier_wall(br, s, zb, w, along=3.0, across=7.0, footing=1.5, zw=0.0):
        z = zb(s) - 1.2; br.box(s, w, zw, along, across, z - zw); br.box(s, w, z, 3.2, 17.0, 1.2); br.box(s, w, zw - 0.5, 7.0, 12.0, footing + 0.5, '#b0aca4')
    Bridge0, pw0 = GB.Bridge, GB.pier_wall
    GB.Bridge, GB.pier_wall = SB, pier_wall
    try:
        L = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
        for f in GB.BUILDERS.values(): f(L)
    finally: GB.Bridge, GB.pier_wall = Bridge0, pw0
    return dict(scene='Keys bridges (solids)', camera=None, note=keys_bridges.__doc__.split('\n')[0], props=P, replace=list(GB.BUILDERS))


def seaplane_dock():
    """T4/3 Seaplane at the Dock — the seawall of Brian's Marina looking north up Key Lento's bay at the Lake Surprise
    Viaduct (pose solved on the viaduct skyline): concrete seawall + cleats, the 'Brian's' floatplane (DHC-2 Beaver-like,
    9.5 m long / 14.6 m span), the wooden boardwalk and gazebo on the right, the palm trunk on the left, mangrove crowns
    on the V17 islands in view. Positions back-projected from the frame (dock 1.9 m, floats 0.4 m above the water)."""
    V = View('Seaplane at the Dock'); P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    ZD = 1.9                                                                # dock top: camera 2.4 m above the dock (man 1.85 m at ~7 m on the frame)
    A, B = V.on_plane_z(580, 1484, ZD), V.on_plane_z(3800, 1780, ZD)                       # seawall edge (frame)
    e = (B - A)[:2] / np.linalg.norm((B - A)[:2]); nb = np.array([-e[1], e[0]])          # nb: towards the camera (land)
    if (V.o[:2] - A[:2]) @ nb < 0: nb = -nb
    A2, B2 = A[:2] - e * 30, B[:2] + e * 30
    P.append(dict(k='quad', p=[r2([*A2, ZD]), r2([*B2, ZD]), r2([*(B2 + nb * 14), ZD]), r2([*(A2 + nb * 14), ZD])], color='#9c9a93'))     # dock top
    P.append(dict(k='quad', p=[r2([*A2, -1.0]), r2([*B2, -1.0]), r2([*B2, ZD]), r2([*A2, ZD])], color='#7d7b74'))                         # seawall face
    P.append(dict(k='quad', p=[r2([*(A2 + nb * 0.0), ZD + 0.02]), r2([*(B2 + nb * 0.0), ZD + 0.02]), r2([*(B2 + nb * 0.45), ZD + 0.02]), r2([*(A2 + nb * 0.45), ZD + 0.02])], color='#b3b1a9'))   # cap stone
    az_e = math.degrees(math.atan2(e[0], e[1]))
    for u, v in ((1740, 1560), (3740, 1770)):                                             # cleats
        q = V.on_plane_z(u, v, ZD); P.append(dict(k='box', c=r2([*(q[:2] + nb * 0.3), ZD]), s=[0.9, 0.22, 0.25], az=round(az_e, 1), color='#3a3b3c'))
    # floatplane: tail (2300,1050) and nose (3040,1085) over the water at float height
    # pose of the plane fitted on 5 frame points: wing tips (1970,830)/(3300,710) at 3.65 m, spinner (3030,890) 2.4 m,
    # fin top (2300,660) 4.4 m, right float front tip (3200,1100) 0.5 m (Beaver: span 14.6, length 9.5)
    from scipy.optimize import least_squares
    obs = np.array([[1970, 830], [3300, 710], [3030, 890], [2300, 660], [3200, 1100]], float)
    def pts(q):
        cx, cy, a_ = q; dd = np.array([math.sin(math.radians(a_)), math.cos(math.radians(a_))]); ww = np.array([-dd[1], dd[0]]); c_ = np.array([cx, cy])
        return np.array([[*(c_ + dd * 1.4 - ww * 7.3), 3.65], [*(c_ + dd * 1.4 + ww * 7.3), 3.65], [*(c_ + dd * 4.9), 2.4], [*(c_ - dd * 4.6), 4.4], [*(c_ + dd * 3.8 + ww * 1.3), 0.5]])
    def proj(Q):
        D = (Q - V.o) @ V.R; return np.c_[(D[:, 0] / D[:, 1] / V.th + 1) * 0.5 * V.W, (1 - (D[:, 2] / D[:, 1] / V.tv + 1) * 0.5) * V.H]
    c0 = V.on_plane_z(2650, 1080, 0.4)[:2]
    best = min((least_squares(lambda q: (proj(pts(q)) - obs).ravel() / 10, [c0[0], c0[1], a0]) for a0 in range(0, 360, 45)), key=lambda r: r.cost)
    C = best.x[:2]; az = best.x[2] % 360; d = np.array([math.sin(math.radians(az)), math.cos(math.radians(az))]); w = np.array([-d[1], d[0]])
    for side in (-1.3, 1.3):                                                              # floats
        q = C + w * side; P.append(dict(k='blob', c=r2([*q, 0.45]), r=[4.6, 0.42, 0.42], az=round(az, 1), color='#f4f2ec', smooth=True))
        for t in (-1.2, 1.4): P.append(dict(k='cyl', a=r2([*(q + d * t), 0.8]), b=r2([*(C + d * t), 2.1]), r=0.06, color='#9a9a96'))
    P.append(dict(k='blob', c=r2([*(C + d * 0.4), 2.6]), r=[4.8, 0.75, 0.85], az=round(az, 1), color='#f1f0ec', smooth=True))           # fuselage
    P.append(dict(k='box', c=r2([*(C + d * 1.6), 2.4]), s=[2.4, 1.5, 1.4], az=round(az, 1), color='#e8e7e2'))                            # cabin
    P.append(dict(k='box', c=r2([*(C + d * 1.4), 3.65]), s=[1.7, 14.6, 0.16], az=round(az, 1), color='#f4f3ef'))                         # wing
    P.append(dict(k='box', c=r2([*(C - d * 4.2), 2.9]), s=[1.3, 0.12, 1.9], az=round(az, 1), color='#1e3a5f'))                           # fin (dark blue)
    P.append(dict(k='box', c=r2([*(C - d * 4.3), 2.85]), s=[1.0, 4.6, 0.1], az=round(az, 1), color='#f1f0ec'))                           # tailplane
    P.append(dict(k='box', c=r2([*(C + d * 4.85), 2.0]), s=[0.12, 0.25, 1.9], az=round(az, 1), color='#2b2b2b'))                         # propeller
    P.append(dict(k='quad', p=[r2([*(C + d * 3.4 + w * 0.77), 2.15]), r2([*(C - d * 2.8 + w * 0.77), 2.15]), r2([*(C - d * 2.8 + w * 0.77), 2.45]), r2([*(C + d * 3.4 + w * 0.77), 2.45])], color='#1e3a5f'))   # cheat line
    # boardwalk + gazebo on the right (front edge (3100,700)-(3840,760))
    Q0, Q1 = V.on_plane_z(3100, 700, 1.2), V.on_plane_z(3840, 760, 1.2); eb = (Q1 - Q0)[:2]; Lb = np.linalg.norm(eb); eb /= Lb; nbb = np.array([eb[1], -eb[0]])
    if (nbb @ ((Q0[:2] - V.o[:2]))) < 0: nbb = -nbb                                      # away from the camera
    Q1x = Q1[:2] + eb * 25
    P.append(dict(k='quad', p=[r2([*Q0[:2], 1.2]), r2([*Q1x, 1.2]), r2([*(Q1x + nbb * 9), 1.2]), r2([*(Q0[:2] + nbb * 9), 1.2])], color='#6b5642'))
    for t in np.arange(0, Lb + 25, 3.0):
        q = Q0[:2] + eb * t; P.append(dict(k='cyl', a=r2([*q, -0.5]), b=r2([*q, 2.2]), r=0.13, color='#4e3f31'))
    gz = V.on_plane_z(3700, 650, 1.2)[:2]                                     # gazebo base (frame)
    for a_ in range(0, 360, 90):
        q = gz + 2.6 * np.array([math.sin(math.radians(a_ + 45)), math.cos(math.radians(a_ + 45))]); P.append(dict(k='cyl', a=r2([*q, 1.2]), b=r2([*q, 3.9]), r=0.12, color='#e9e4da'))
    P.append(dict(k='box', c=r2([*gz, 3.9]), s=[6.2, 6.2, 0.35], az=0.0, color='#2c3e57'))
    P.append(dict(k='blob', c=r2([*gz, 4.3]), r=[3.2, 3.2, 1.3], color='#2c3e57'))
    # palm trunk on the left, ~3.5 m from the camera (frame u 160..560)
    q = V.o + V.ray(380, 1400) / np.linalg.norm(V.ray(380, 1400)[:2]) * 3.5
    P.append(dict(k='cyl', a=r2([q[0], q[1], ZD]), b=r2([q[0] - 0.3, q[1], ZD + 11]), r=0.22, color='#6d5c48'))
    # mangrove crowns on the V17 islands within 900 m in the view
    from yanis_markers import crop as _c
    R0 = 900; x0, y0 = V.o[0] - R0, V.o[1] - R0
    M = cv2.cvtColor(_c(x0, y0, x0 + 2 * R0, y0 + 2 * R0), cv2.COLOR_BGR2HSV).astype(int)
    isl = ((M[..., 0] >= 18) & (M[..., 0] <= 45) & (M[..., 1] > 50) & (M[..., 2] > 150))
    rng = np.random.default_rng(3); tones = ['#2d4524', '#36532b', '#3f5f31', '#2a3e21']
    for j in range(0, 2 * R0, 9):
        for i in range(0, 2 * R0, 9):
            if not isl[i, j]: continue
            x, y = x0 + j + 0.5, y0 + 2 * R0 - i - 0.5; vv = np.array([x, y]) - V.o[:2]
            if np.linalg.norm(vv) < 40: continue
            fw = V.R @ np.array([0, 1, 0.0]); cosang = (vv @ fw[:2]) / np.linalg.norm(vv) / np.linalg.norm(fw[:2])
            if cosang < math.cos(math.radians(40)): continue
            r = rng.uniform(4.0, 6.5); P.append(dict(k='blob', c=r2([x + rng.normal(0, 2), y + rng.normal(0, 2), r * 0.7]), r=[r, r, r * 0.75], color=tones[int(rng.integers(4))]))
    clear = [[[-2600, -5800], [-2480, -5800], [-2480, -5660], [-2600, -5660]]]          # V16 boxes #145/#146 (camera stood inside #145)
    return dict(scene='T4/3 Seaplane at the Dock', camera='Seaplane at the Dock', note=seaplane_dock.__doc__.split('\n')[0], props=P, clear=clear)


def radio_towers():
    """The two radio towers north of Key Lento seen in T4/3 (Alexandre: 'modelise les deux radio tower surtout WDNA'):
    - WDNA FM: guyed mast on the mesh / landmark geometry (triangular lattice, legs ~5 m apart, 396 m + antenna to 409 m),
      guy attachment levels of the mesh (215, 380, 390 m) + 100 / 300 m, 3 guy directions; anchor radii and the
      orange/white paint bands are ESTIMATED (FAA practice);
    - the self-supporting lattice tower left of it (T4/3 frame u 958, top v 365 -> bearing 357.1 deg, elevation +3.5 deg):
      NOT in our data, distance unknown: placed at 2.2 km on that bearing (Hamlet), height 136 m to match the elevation
      (ESTIMATED; a second view would fix it)."""
    P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    ORG, WHT = '#e0592b', '#efeeea'
    # ---- WDNA FM
    L3 = np.array([[-2522.5, -2299.0], [-2520.7, -2303.7], [-2525.7, -2302.7]]); C = L3.mean(0); z0, zt = 5.0, 396.3
    band = lambda z: ORG if int((z - z0) / ((zt - z0) / 7)) % 2 == 0 else WHT
    for k in range(3): P.append(dict(k='cyl', a=r2([*L3[k], z0]), b=r2([*L3[k], zt]), r=0.22, color='#c9c9c4'))
    for z in np.arange(z0, zt, 6.0):
        col = band(z)
        for k in range(3):
            a, b = L3[k], L3[(k + 1) % 3]
            P.append(dict(k='cyl', a=r2([*a, z]), b=r2([*b, z]), r=0.12, color=col))
            P.append(dict(k='cyl', a=r2([*a, z]), b=r2([*b, min(z + 6, zt)]), r=0.08, color=col))
    P.append(dict(k='cyl', a=r2([*C, zt]), b=r2([-2527.2, -2301.8, 409.4]), r=0.35, color=WHT))      # top antenna
    for z in (100, 200, 300, 396):
        P.append(dict(k='box', c=r2([*C, z]), s=[1.2, 1.2, 0.8], az=0.0, color='#ff2a2a'))
    zg = T(*C)
    for i, a in enumerate((20.0, 140.0, 260.0)):
        dd = np.array([math.sin(math.radians(a)), math.cos(math.radians(a))])
        for z, R in ((100, 170), (215, 170), (300, 300), (390, 300)):
            an = C + dd * R; P.append(dict(k='line', pts=[r2([*C, z]), r2([*an, max(T(*an), 0.0) + 1.0])], color='#b0b0b0', opacity=0.18))
        for R in (170, 300):
            an = C + dd * R; P.append(dict(k='box', c=r2([*an, max(T(*an), 0.0)]), s=[3, 3, 1.2], az=a, color='#a8a39a'))
    # ---- lattice tower (ESTIMATED distance)
    cam = np.array([-2571.03, -5754.92]); az = math.radians(357.07); D = 2200.0
    B0 = cam + D * np.array([math.sin(az), math.cos(az)]); g = T(*B0); H = 4.25 + D * math.tan(math.radians(3.52)) - g
    hw = lambda z: 5.0 + (0.75 - 5.0) * (z / H)
    corners = lambda z: [B0 + np.array(v) * hw(z) for v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    lv = list(np.arange(0, H, 8.0)) + [H]
    for za, zb in zip(lv[:-1], lv[1:]):
        A_, B_ = corners(za), corners(zb); col = ORG if int(za / (H / 7)) % 2 == 0 else WHT
        for k in range(4):
            P.append(dict(k='cyl', a=r2([*A_[k], g + za]), b=r2([*B_[k], g + zb]), r=0.18, color=col))                       # legs
            P.append(dict(k='cyl', a=r2([*A_[k], g + za]), b=r2([*B_[(k + 1) % 4], g + zb]), r=0.07, color=col))             # X bracing
            P.append(dict(k='cyl', a=r2([*A_[(k + 1) % 4], g + za]), b=r2([*B_[k], g + zb]), r=0.07, color=col))
            P.append(dict(k='cyl', a=r2([*B_[k], g + zb]), b=r2([*B_[(k + 1) % 4], g + zb]), r=0.07, color=col))             # horizontals
    P.append(dict(k='cyl', a=r2([*B0, g + H]), b=r2([*B0, g + H + 8]), r=0.25, color=WHT))
    P.append(dict(k='box', c=r2([*B0, g + H + 8]), s=[1, 1, 0.8], az=0.0, color='#ff2a2a'))
    return dict(scene='Radio towers (WDNA FM + lattice)', camera=None, note=radio_towers.__doc__.split('\n')[0], props=P, replace=['WDNA FM'])


def _key_bright(crop, thr=150):
    """alpha mask of a bright neon glyph (frame crop)."""
    g = crop.max(axis=2).astype(int); a = (np.clip((g - thr) * 4, 0, 255)).astype(np.uint8)
    return np.dstack([crop, cv2.GaussianBlur(a, (3, 3), 0)])


def skyline_night():
    """T4/7 Skyline at Night — Mid-Beach at night, drone 97 m above the sand spit looking SW at downtown (pose SOLVED on
    the far field). The near hotel = the V17 lot of 'Sorrento Tower' (re-fitted by tools/fit_fontainebleau.py, roof 64 m);
    its neon (4 teal vertical strips on the east face, teal crown arch, two cyan glyph signs), the magenta-lit beach
    pavilion north of it, the pool deck and the dark tree canopy of the foreground, all back-projected from the frame
    (planes: east face x 2020, north face y 1962, ground)."""
    V = View('Skyline at Night'); P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    E = lambda u, v: V.on_vplane(u, v, (2020.3, 1930), (1, 0)); N = lambda u, v: V.on_vplane(u, v, (1980, 1962.3), (0, 1))
    TEAL, CYAN, MAG = '#3ef2d0', '#9fe8ff', '#ff4fd8'
    for u in (1810, 1862, 1918, 1978):                                     # vertical neon strips (east face, roof down ~45 m)
        P.append(dict(k='glow', pts=[r2(E(u, 748)), r2(E(u, 965))], r=0.35, color=TEAL, i=2.2))
    arch = [(2210, 756), (2282, 724), (2400, 694), (2500, 674), (2620, 660)]   # crown arch top edge
    A = [E(u, v) if u <= 2282 else N(u, v) for u, v in arch]
    P.append(dict(k='glow', pts=[r2(q) for q in A], r=0.45, color=TEAL, i=2.4))
    for q0, q1 in zip(A[:-1], A[1:]):                                      # crown screen wall (roof -> arch)
        P.append(dict(k='quad', p=[r2([q0[0], q0[1], 64.0]), r2([q1[0], q1[1], 64.0]), r2(q1), r2(q0)], color='#1e2a2c'))
    fr = cv2.imread(os.path.join(REPO, 'frames', 'Skyline at Night.png'))
    for nm, (u0, v0, u1, v1) in (('_prop_fb_sign1.png', (2668, 590, 2720, 710)), ('_prop_fb_sign2.png', (2480, 776, 2532, 916))):
        if fr is not None: cv2.imwrite(os.path.join(THIS, 'threejs', nm), _key_bright(fr[v0:v1, u0:u1]))
        P.append(dict(k='tex', p=[r2(N(u0, v1)), r2(N(u1, v1)), r2(N(u1, v0)), r2(N(u0, v0))], img=nm, alpha=True, glow=1.8))
    # balcony slabs on the hotel's east and north faces (one per 3.2 m floor, as on the frame)
    for z in np.arange(8.4, 63.0, 3.2):
        P.append(dict(k='box', c=[2020.6, 1929.5, round(float(z), 2)], s=[65.0, 1.4, 0.28], az=0.0, color='#6d6f73'))
        P.append(dict(k='box', c=[1979.0, 1962.6, round(float(z), 2)], s=[82.0, 1.4, 0.28], az=90.0, color='#6d6f73'))
    # pink-lit arcade (2-storey, 6 arches) + glass pergola north of the hotel (frame u 2950..3840, v 1600..1910):
    # front base on the ground at v 1905, arch tops / roof back-projected on that vertical plane (16.6 / 18.7 m)
    zg = 4.5
    G = lambda u, v, z=zg: V.on_plane_z(u, v, z)
    A0, A1 = G(2990, 1905), G(3480, 1905); ea = (A1 - A0)[:2]; La = np.linalg.norm(ea); ea /= La; na = np.array([-ea[1], ea[0]])
    if (V.o[:2] - A0[:2]) @ na < 0: na = -na                               # na: towards the camera (front)
    aza = math.degrees(math.atan2(ea[0], ea[1])); D = 12.0; HT = 12.0
    at = lambda s_, w_, z: [*(A0[:2] + ea * s_ - na * w_), z]
    P.append(dict(k='box', c=r2(at(La / 2, D / 2, zg)), s=[round(La, 1), D, HT], az=round(aza, 1), color='#5e4459'))      # body (soft pink wash)
    P.append(dict(k='box', c=r2(at(La / 2, D / 2, zg + HT)), s=[round(La + 0.6, 1), D + 0.6, 0.7], az=round(aza, 1), color='#8d6c86'))   # parapet
    for j in range(7):                                                     # piers, softly uplit (no neon: the frame shows a wash)
        s_ = La * j / 6; P.append(dict(k='box', c=r2(at(s_, -0.4, zg)), s=[1.1, 1.0, HT], az=round(aza, 1), color='#9c7894'))
        P.append(dict(k='glow', pts=[r2(at(s_, -1.0, zg + 0.3))], r=0.35, color='#f3c6ea', i=1.3, ball=True))
        if j < 6:
            for zz in (zg + 1.5, zg + 4.6):                                # windows behind the arches (2 floors), mostly dark
                w0, w1 = s_ + 1.2, s_ + La / 6 - 1.2
                P.append(dict(k='quad', p=[r2(at(w0, -0.05, zz)), r2(at(w1, -0.05, zz)), r2(at(w1, -0.05, zz + 2.2)), r2(at(w0, -0.05, zz + 2.2))], color=['#c9a98a', '#2a1e28', '#2a1e28'][(j + int(zz)) % 3]))
    # glass pergola: thin dark steel, faintly lit glass, soft lamps at the post feet
    Q = [G(3470, 1800, 13.0), G(3840, 1800, 13.0), G(3840, 1610, 13.0), G(3470, 1610, 13.0)]
    for q in Q:
        P.append(dict(k='cyl', a=r2([q[0], q[1], zg]), b=r2([q[0], q[1], 13.0]), r=0.3, color='#7b6476'))
        P.append(dict(k='glow', pts=[r2([q[0], q[1], zg + 0.4])], r=0.45, color='#f6d6ef', i=1.4, ball=True))
    for t in np.linspace(0, 1, 7):
        a_, b_ = Q[0] + (Q[1] - Q[0]) * t, Q[3] + (Q[2] - Q[3]) * t; P.append(dict(k='cyl', a=r2(a_), b=r2(b_), r=0.1, color='#6e5a6a'))
    for t in np.linspace(0, 1, 5):
        a_, b_ = Q[0] + (Q[3] - Q[0]) * t, Q[1] + (Q[2] - Q[1]) * t; P.append(dict(k='cyl', a=r2(a_), b=r2(b_), r=0.1, color='#6e5a6a'))
    P.append(dict(k='quad', p=[r2(q + [0, 0, 0.1]) for q in Q], color='#57434f'))
    # forecourt: dark drive, lit roundabout planter, pool cabanas, palms in front
    rb = G(3250, 1560); P.append(dict(k='blob', c=r2([rb[0], rb[1], zg + 1.0]), r=[5, 5, 1.2], color='#2b3a24'))
    P.append(dict(k='glow', pts=[r2([rb[0] + 6 * math.cos(t), rb[1] + 6 * math.sin(t), zg + 0.3]) for t in np.linspace(0, 2 * math.pi, 17)], r=0.12, color='#ffd9a0', i=1.6))
    for u in (3020, 3110, 3200):
        q = G(u, 1905, zg); P.append(dict(k='box', c=r2([*(q[:2] + na * 6), zg]), s=[3.2, 3.2, 2.6], az=round(aza, 1), color='#5b4436'))
    for u, v in ((2600, 1890), (2700, 1870), (2820, 1880), (2560, 1800)):
        q = G(u, v); P.append(dict(k='palm', a=r2(q), h=11.0, lean_az=200.0, lean=0.06))
    # pool deck (frame u 1500..1700, v 1810..1920) + warm path lights
    pa, pb, pc, pd = G(1510, 1915, 4.6), G(1700, 1915, 4.6), G(1700, 1815, 4.6), G(1510, 1815, 4.6)
    P.append(dict(k='quad', p=[r2(pa), r2(pb), r2(pc), r2(pd)], color='#1f9bd9'))
    P.append(dict(k='glow', pts=[r2(pa), r2(pb), r2(pc), r2(pd), r2(pa)], r=0.2, color='#6fd3ff', i=1.6))
    rng = np.random.default_rng(4); tones = ['#16221a', '#1b2a1d', '#213222', '#121c15']
    for _ in range(260):                                                   # dark canopy of the foreground (frame bottom-left)
        u = rng.uniform(-200, 1900); v = rng.uniform(1230, 2000)
        if u > 1450 and v < 1500: continue
        q = G(u, v); r = rng.uniform(3.5, 6.5)
        P.append(dict(k='blob', c=r2([q[0], q[1], zg + rng.uniform(5, 11)]), r=[r, r, r * 0.8], color=tones[int(rng.integers(4))]))
    for _ in range(60):                                                    # warm garden / path lights under the trees
        u = rng.uniform(100, 1800); v = rng.uniform(1250, 1950); q = G(u, v, zg + 0.6)
        P.append(dict(k='glow', pts=[r2(q)], r=0.6, color=['#ffd27a', '#ffb85c', '#fff1c4'][int(rng.integers(3))], i=2.2, ball=True))
    clear = [[[1934, 1893], [2024, 1893], [2024, 1966], [1934, 1966]]]
    return dict(scene='T4/7 Skyline at Night', camera='Skyline at Night', note=skyline_night.__doc__.split('\n')[0], props=P, clear=clear)


def aviation_lights():
    """Red obstacle lights on the roof corners of every solid taller than 60 m (all night scenes; the T4/7 frame shows
    dozens of them on the skyline). Corners = the 4 extreme vertices of the top layer of tools/mesh_solids.py."""
    import mesh_solids
    P = []
    for name, so in mesh_solids.cached().items():
        if so['zmax'] - so['zmin'] < 60 or not so['layers']: continue
        top = so['layers'][-1]; pts = np.array([q for pp in top['polys'] for q in pp['outer']], float)
        if len(pts) < 3: continue
        c = pts.mean(0); idx = {int(np.argmax(pts @ d)) for d in np.array([[1, 1], [1, -1], [-1, 1], [-1, -1]], float)}
        for i in idx:
            q = pts[i] + (c - pts[i]) * 0.04
            P.append(dict(k='glow', pts=[[round(q[0], 2), round(q[1], 2), round(top['z1'] + 1.2, 2)]], r=0.9, color='#ff2020', i=2.4, ball=True))
    return dict(scene='Aviation lights (towers > 60 m)', camera=None, note=aviation_lights.__doc__.split('\\n')[0], props=P)


SCENES = [keys_entrance, brians_marina, keys_landmarks, keys_bridges, seaplane_dock, radio_towers, skyline_night, aviation_lights]


def main():
    out = dict(_doc=__doc__.split('\n')[0] + ' Generated by tools/scene_props.py; positions ESTIMATED from the frames.', scenes=[f() for f in SCENES])
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    for s in out['scenes']: print(s['scene'], len(s['props']), 'props')


if __name__ == '__main__':
    main()
