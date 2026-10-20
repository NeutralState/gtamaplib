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
    of T2/30). Pose fit (tri fit 2026-10-19): the V17 blue-grey footprint shifted (+8.9, -13.1) m and rotated 28.6 deg,
    eave 10.0 / ridge 13.3 m, consistent with the radio tower '102180 Overseas Hwy' and the Key Lento ray to the rooftop
    letters. Props: gable shed, rooftop 'BRIAN'S MARINA' letters keyed out of the frame, the T2/30 gable sign, 5-level
    boat racks with boats, 'RENT A RACK' sign, parking lot, boats on trailers, palms, and the blimp in the sky."""
    V = View("Brian's Marina"); P = []
    XW, XE, YN, YS = -2570.0, -2537.0, -5827.0, -5905.0; xm = (XW + XE) / 2; E, R = 10.02, 13.34
    C0, SH, ROT = np.array([-2553.5, -5866.0]), np.array([8.93, -13.07]), 28.61
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
    rng = np.random.default_rng(2); x0r, x1r = XE + 0.4, XE + 10.0; ys = np.arange(-5832.0, -5910.1, -6.5)
    lv = [g + 0.4 + 2.15 * k for k in range(5)]                          # 5 levels under the 10 m eave
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
    clear = [[list(np.round(F(x_, y_), 1)) for x_, y_ in ((XW - 6, YS - 14), (XE + 16, YS - 14), (XE + 16, YN + 6), (XW - 6, YN + 6))]]
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


SCENES = [keys_entrance, brians_marina, keys_landmarks, keys_bridges]


def main():
    out = dict(_doc=__doc__.split('\n')[0] + ' Generated by tools/scene_props.py; positions ESTIMATED from the frames.', scenes=[f() for f in SCENES])
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    for s in out['scenes']: print(s['scene'], len(s['props']), 'props')


if __name__ == '__main__':
    main()
