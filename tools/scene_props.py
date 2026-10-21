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
A scene may also list 'bare_roof' (mesh names whose top gets no generic roof units / parapet in view3d), 'replace': mesh names whose wireframe view3d no longer draws (rebuilt here as solids), and 'clear' polygons [[x,y]...]: view3d does not extrude the V16 massing footprints whose centroid falls
inside (e.g. V16 boxes that land on a modelled road), and 'nolamp' polygons: no generic view3d streetlight inside (where a
SOLVED frame shows none), and 'roadclear' polygons: the V16 road ribbons / markings are not drawn inside (where a scene rebuilt
its own roadway, e.g. the T4/34 Bayside Dr divided deck), and 'cut_solids' {mesh: z}: while the tour shows that scene's camera,
the solid is cut down to z (a tower still under construction in that frame, e.g. Asia Brickell Key in T4/36).
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
            for w in (np.linspace(w0 + m, w1 - m, ncol) if ncol > 1 else [(w0 + w1) / 2]): self.box(s, w, zw, col, col, z - cap - zw)
            self.box(s, (w0 + w1) / 2, z - cap, 1.8, (w1 - w0 - 0.6) if ncol > 1 else 6.0, cap)
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
    WALL = '#d8a9d2'                                                       # walls washed by the pink uplights (frame ~ RGB 205,150,200)
    P.append(dict(k='box', c=r2(at(La / 2, D / 2, zg)), s=[round(La, 1), D, HT], az=round(aza, 1), color='#3a2a37', e=0.25))      # body, dark roof
    P.append(dict(k='box', c=r2(at(La / 2, -0.3, zg + HT)), s=[round(La + 0.6, 1), 0.6, 0.6], az=round(aza, 1), color=WALL, e=0.8))      # front parapet only
    P.append(dict(k='box', c=r2(at(La / 2, -0.6, zg + 3.6)), s=[round(La, 1), 1.6, 0.35], az=round(aza, 1), color=WALL, e=0.8))   # 1st-floor balcony slab
    for j in range(7):
        s_ = La * j / 6; P.append(dict(k='box', c=r2(at(s_, -0.5, zg)), s=[1.1, 1.2, HT - 2.6], az=round(aza, 1), color=WALL, e=1.0))
        P.append(dict(k='glow', pts=[r2(at(s_, -1.2, zg + 0.25))], r=0.35, color='#ffd7f6', i=1.6, ball=True))
        if j < 6:
            m0, m1 = s_ + 0.55, s_ + La / 6 - 0.55
            arc = [at(m0 + (m1 - m0) * (1 - math.cos(t)) / 2, -0.5, zg + HT - 2.6 + 1.6 * math.sin(t)) for t in np.linspace(0, math.pi, 7)]
            for q0, q1 in zip(arc[:-1], arc[1:]): P.append(dict(k='cyl', a=r2(q0), b=r2(q1), r=0.35, color=WALL, e=1.0))
            for zz, col in ((zg + 0.6, '#f2cfa6'), (zg + 4.3, '#f6d9b8')):  # warm-lit glazing behind the arches, both floors
                w0, w1 = s_ + 1.0, s_ + La / 6 - 1.0
                P.append(dict(k='quad', p=[r2(at(w0, 0.05, zz)), r2(at(w1, 0.05, zz)), r2(at(w1, 0.05, zz + 2.6)), r2(at(w0, 0.05, zz + 2.6))], color=col, e=1.1))
    # glass pergola: pale pink-lit frame and glass (as on the frame), soft lamps at the post feet
    Q = [G(3470, 1800, 13.0), G(3840, 1800, 13.0), G(3840, 1610, 13.0), G(3470, 1610, 13.0)]
    for q in Q:
        P.append(dict(k='cyl', a=r2([q[0], q[1], zg]), b=r2([q[0], q[1], 13.0]), r=0.35, color=WALL, e=1.0))
        P.append(dict(k='glow', pts=[r2([q[0], q[1], zg + 0.4])], r=0.5, color='#fff0fb', i=1.8, ball=True))
    for t in np.linspace(0, 1, 7):
        a_, b_ = Q[0] + (Q[1] - Q[0]) * t, Q[3] + (Q[2] - Q[3]) * t; P.append(dict(k='cyl', a=r2(a_), b=r2(b_), r=0.14, color=WALL, e=0.9))
    for t in np.linspace(0, 1, 5):
        a_, b_ = Q[0] + (Q[3] - Q[0]) * t, Q[1] + (Q[2] - Q[1]) * t; P.append(dict(k='cyl', a=r2(a_), b=r2(b_), r=0.14, color=WALL, e=0.9))
    P.append(dict(k='quad', p=[r2(q - [0, 0, 0.1]) for q in Q], color='#7d5a78', e=0.6))
    rng = np.random.default_rng(7)
    # dark plaza ground around the arcade (the night drape there still read pale grey)
    P.append(dict(k='quad', p=[r2(G(2300, 1930, zg + 0.04)), r2(G(3860, 1930, zg + 0.04)), r2(G(3860, 1380, zg + 0.04)), r2(G(2300, 1380, zg + 0.04))], color='#141114', e=0.0))
    # foliage around the arcade (frame: palm rows in front, planters and palms behind, pink-lit trunks)
    for u, v, hgt in ((2560, 1880, 10), (2640, 1860, 11), (2720, 1880, 10), (2800, 1870, 9), (2900, 1900, 10), (3580, 1880, 11), (3700, 1900, 10),
                      (3050, 1560, 12), (3150, 1540, 13), (3390, 1560, 12), (3600, 1500, 12), (3760, 1460, 11)):
        q = G(u, v); P.append(dict(k='palm', a=r2(q), h=hgt, lean_az=200.0, lean=0.06))
        P.append(dict(k='glow', pts=[r2([q[0], q[1], zg + 0.3])], r=0.3, color='#ffc2ee', i=1.4, ball=True))
    for u in np.arange(2520, 3000, 45):
        q = G(u, 1915); r = rng.uniform(2.0, 3.0); P.append(dict(k='blob', c=r2([q[0], q[1], zg + 1.6]), r=[r, r, r * 0.7], color='#1d2a1c'))
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
    clear = [[[1934, 1893], [2024, 1893], [2024, 1966], [1934, 1966]], [[1960, 1950], [2030, 1950], [2030, 1990], [1960, 1990]]]   # + V16 box #1536 (dark slab not on the frame)
    return dict(scene='T4/7 Skyline at Night', camera='Skyline at Night', note=skyline_night.__doc__.split('\n')[0], props=P, clear=clear)


AVI_SKIP = ('Stephen P. Clark Government Center', 'Asia Brickell Key')   # Asia: a construction site (T4/36), its lights are on the cranes


def aviation_lights():
    """Red obstacle lights on the roof corners of every solid taller than 60 m (all night scenes; the T4/7 frame shows
    dozens of them on the skyline). Corners = the 4 extreme vertices of the top layer of tools/mesh_solids.py."""
    import mesh_solids
    P = []
    for name, so in mesh_solids.cached().items():
        if so['zmax'] - so['zmin'] < 60 or not so['layers']: continue
        if name in AVI_SKIP: continue                                        # roofs a tour camera stands on (their own lights: scene props)
        top = so['layers'][-1]; pts = np.array([q for pp in top['polys'] for q in pp['outer']], float)
        if len(pts) < 3: continue
        c = pts.mean(0); idx = {int(np.argmax(pts @ d)) for d in np.array([[1, 1], [1, -1], [-1, 1], [-1, -1]], float)}
        for i in idx:
            q = pts[i] + (c - pts[i]) * 0.04
            P.append(dict(k='glow', pts=[[round(q[0], 2), round(q[1], 2), round(top['z1'] + 1.2, 2)]], r=0.9, color='#ff2020', i=2.4, ball=True))
    return dict(scene='Aviation lights (towers > 60 m)', camera=None, note=aviation_lights.__doc__.split('\\n')[0], props=P)


def brickell_metromover():
    """Brickell Metromover guideway (south leg of the V17 pink loop). Built for T4/9 Iguana, whose Brickell placement was
    REJECTED (the frame shows no towers behind its overpass); kept as a city structure. Guideway on the V17 pink loop (south leg, centre of the two rails), underside 12.1 m and deck
    6.5 m from the fit, deck 1.6 m thick, round piers d 2.2 m with a cap every ~30 m (one at the frame's pier), the station
    (V17 blue strip, 9 m) as a wider deck; the 'roundabout ahead' sign textured from the frame (2.4 m wide -> 80 m away),
    the avenue with the yellow speed-hump bars, utility / lamp poles, the car ahead (1.9 m wide -> 50 m) and trees.
    Sizes are ESTIMATED from the frame (one view)."""
    P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    CL = np.array([[-1340, -1460], [-1335, -1490], [-1300, -1505], [-1250, -1533], [-1200, -1539], [-1150, -1552.5], [-1100, -1565], [-1050, -1562], [-1010, -1540], [-995, -1500]], float)
    t = np.linspace(0, 1, 30); seg = np.vstack([CL[i] + (CL[i + 1] - CL[i]) * t[:, None] for i in range(len(CL) - 1)])
    keep = [0]
    for i in range(1, len(seg)):
        if np.linalg.norm(seg[i] - seg[keep[-1]]) >= 5.0: keep.append(i)
    seg = seg[keep]; HG, WD, TH = 12.08, 6.49, 1.6; CON = '#cfcbc2'
    for a, b in zip(seg[:-1], seg[1:]):
        d = b - a; L = np.linalg.norm(d); az = math.degrees(math.atan2(d[0], d[1])); c = (a + b) / 2
        P.append(dict(k='box', c=r2([c[0], c[1], HG]), s=[round(L + 0.4, 2), WD, TH], az=round(az, 1), color=CON))
        P.append(dict(k='box', c=r2([c[0], c[1], HG + TH]), s=[round(L + 0.4, 2), 0.35, 0.9], az=round(az, 1), color='#b9b5ad'))   # centre guide beam
    cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(seg, axis=0), axis=1))]
    s0 = cum[int(0.5 * (len(cum) - 1))]                                    # the frame's pier (fit tp = 0.5)
    for sp in np.arange(s0 % 30.0, cum[-1], 30.0):
        q = np.array([np.interp(sp, cum, seg[:, 0]), np.interp(sp, cum, seg[:, 1])]); g = T(*q)
        P.append(dict(k='cyl', a=r2([q[0], q[1], g]), b=r2([q[0], q[1], HG - 1.2]), r=1.1, color=CON))
        j = min(int(np.searchsorted(cum, sp)), len(seg) - 1); d = seg[min(j, len(seg) - 1)] - seg[max(j - 1, 0)]
        az = math.degrees(math.atan2(d[0], d[1])) + 90
        P.append(dict(k='box', c=r2([q[0], q[1], HG - 1.4]), s=[WD + 0.6, 2.4, 1.4], az=round(az, 1), color=CON))
    for a, b in (((-1298, -1483), (-1260, -1501)), ((-1245, -1508), (-1205, -1529))):   # station (V17 blue strip)
        a, b = np.array(a, float), np.array(b, float); d = b - a; az = math.degrees(math.atan2(d[0], d[1])); c = (a + b) / 2
        P.append(dict(k='box', c=r2([c[0], c[1], HG - 0.6]), s=[round(np.linalg.norm(d), 1), 10.0, 0.6], az=round(az, 1), color='#bfc4c6'))
        P.append(dict(k='box', c=r2([c[0], c[1], HG + 4.6]), s=[round(np.linalg.norm(d), 1), 11.0, 0.5], az=round(az, 1), color='#9aa3a8'))
    return dict(scene='Brickell Metromover (guideway)', camera=None, note=brickell_metromover.__doc__.split('\n')[0], props=P)


def ferris_marina():
    """T4/10 Skyline with Ferris Wheel — the Watson Island marina in front of downtown at sunset (pose SOLVED on the skyline).
    Foreground placed per frame column: the V17 shoreline distance along each ray (96-137 m), heights from the frame
    (top pixel at that distance): palm rows, the big tree, the steel boat-lift frame, the low marina building with its
    white sign, utility poles and wires, moored boats and the floating dock. Silhouettes against the sun: dark tones."""
    from yanis_markers import crop as _c
    V = View('Skyline with Ferris Wheel'); P = []; r2 = lambda a: [round(float(v), 2) for v in a]; o = V.o
    x0, y0 = o[0] - 700, o[1] - 700; M = cv2.cvtColor(_c(x0, y0, x0 + 1400, y0 + 1400), cv2.COLOR_BGR2HSV).astype(int)
    water = (M[..., 0] >= 88) & (M[..., 0] <= 118) & (M[..., 1] > 70)
    def shore(u):
        d = V.ray(u, 1250); d2 = d[:2] / np.linalg.norm(d[:2])
        for s_ in range(10, 700):
            x, y = o[0] + d2[0] * s_, o[1] + d2[1] * s_
            if not water[int(y0 + 1400 - y), int(x - x0)]: return float(s_)
        return 120.0
    def at(u, v, D): d = V.ray(u, v); return o + d / np.linalg.norm(d[:2]) * D
    def top(u, D, vtop): return float(at(u, vtop, D)[2])
    DARK = ['#2a1d24', '#331f29', '#3a2430', '#24181f']; rng = np.random.default_rng(10)
    # palms (u, top v)
    for u, vt in ((40, 830), (180, 820), (330, 830), (470, 860), (600, 880), (730, 900), (1660, 990), (2430, 990), (2560, 1000),
                  (2980, 950), (3200, 1000), (3330, 1010), (3620, 940), (3760, 920)):
        D = shore(u) + rng.uniform(6, 14); b = at(u, 1250, D); g = max(T(b[0], b[1]), 1.0); h = top(u, D, vt) - g
        P.append(dict(k='palm', a=r2([b[0], b[1], g]), h=round(max(6.0, h - 1.2), 1), lean_az=round(rng.uniform(0, 360), 0), lean=0.07))
    # big tree (u 1750..2350, crown top v 760)
    D = shore(2050) + 25; b = at(2050, 1250, D); g = max(T(b[0], b[1]), 1.0); H = top(2050, D, 760) - g
    P.append(dict(k='cyl', a=r2([b[0], b[1], g]), b=r2([b[0], b[1], g + H * 0.45]), r=0.9, color='#2b1c22'))
    for k in range(26):
        uu = 1760 + 580 * rng.random(); vv = 780 + 320 * rng.random(); q = at(uu, vv, D + rng.normal(0, 4))
        P.append(dict(k='blob', c=r2(q), r=[round(rng.uniform(2.2, 3.8), 1)] * 2 + [round(rng.uniform(1.8, 3.0), 1)], color=DARK[int(rng.integers(4))]))
    # steel boat-lift frame (u 760..1290, top v 1040)
    D = shore(1025) + 2; g = 1.2; Hf = top(1025, D, 1040) - g; cols = np.linspace(760, 1290, 7)
    A = [at(u, 1250, D) for u in cols]
    for q in A: P.append(dict(k='cyl', a=r2([q[0], q[1], g]), b=r2([q[0], q[1], g + Hf]), r=0.25, color='#2e2a2c'))
    for z in (g + Hf, g + Hf - 1.0):
        for q0, q1 in zip(A[:-1], A[1:]): P.append(dict(k='cyl', a=r2([q0[0], q0[1], z]), b=r2([q1[0], q1[1], z]), r=0.18, color='#2e2a2c'))
    back = (A[-1] - A[0])[:2]; nb = np.array([-back[1], back[0]]) / np.linalg.norm(back)
    if nb @ (A[0][:2] - o[:2]) < 0: nb = -nb
    for q in A[::2]: P.append(dict(k='cyl', a=r2([q[0], q[1], g + Hf]), b=r2([q[0] + nb[0] * 8, q[1] + nb[1] * 8, g + Hf]), r=0.15, color='#2e2a2c'))
    # low marina building (u 2150..2950, roof v 1170) + white sign (u 2780..2900, v 1170..1190)
    D = shore(2550) + 30; a0, a1 = at(2150, 1250, D), at(2950, 1250, D); g = max(T(*a0[:2]), 1.0); Hb = top(2550, D, 1170) - g
    d = (a1 - a0)[:2]; L = np.linalg.norm(d); az = math.degrees(math.atan2(d[0], d[1])); c = (a0 + a1)[:2] / 2 + nb * 7
    P.append(dict(k='box', c=r2([c[0], c[1], g]), s=[round(L, 1), 14.0, round(Hb, 1)], az=round(az, 1), color='#2c2026'))
    s0, s1 = at(2780, 1192, D - 0.2), at(2900, 1168, D - 0.2)
    P.append(dict(k='quad', p=[r2([s0[0], s0[1], s0[2]]), r2([s1[0], s1[1], s0[2]]), r2([s1[0], s1[1], s1[2]]), r2([s0[0], s0[1], s1[2]])], color='#d9d4dc', e=0.6))
    # utility poles + wires (u 3100, 3420, tops v 960)
    pts = []
    for u in (2720, 3100, 3420, 3720):
        D = shore(u) + 12; b = at(u, 1250, D); g = max(T(b[0], b[1]), 1.0); h = top(u, D, 960) - g
        P.append(dict(k='cyl', a=r2([b[0], b[1], g]), b=r2([b[0], b[1], g + h]), r=0.16, color='#2a2225')); pts.append(np.r_[b[:2], g + h - 0.6])
    for q0, q1 in zip(pts[:-1], pts[1:]):
        P.append(dict(k='line', pts=[r2(q0 + (q1 - q0) * t - [0, 0, 0.9 * 4 * t * (1 - t)]) for t in np.linspace(0, 1, 9)], color='#1c1418'))
    # dark marina ground (the V17 drape is white there; backlit on the frame)
    for u0 in np.arange(-300, 4100, 100):                                 # draped on the terrain (the island ground is at eye level:
        for d0 in range(-6, 260, 8):                                       # a lifted cover would pass above the view rays)
            Q = [at(u0, 1250, shore(u0) + d0), at(u0 + 100, 1250, shore(u0 + 100) + d0), at(u0 + 100, 1250, shore(u0 + 100) + d0 + 8), at(u0, 1250, shore(u0) + d0 + 8)]
            if max(T(q[0], q[1]) for q in Q) < 0.4: continue
            P.append(dict(k='quad', p=[r2([q[0], q[1], max(T(q[0], q[1]), 0.4) + 0.06]) for q in Q], color='#1e1519', e=0.0))
    # floating dock + moored boats (water side of the shore)
    for u0, u1 in ((0, 1500), (1500, 3840)):
        q0, q1 = at(u0, 1250, shore(u0) - 4), at(u1, 1250, shore(u1) - 4)
        P.append(dict(k='quad', p=[r2([q0[0], q0[1], 0.6]), r2([q1[0], q1[1], 0.6]), r2([q1[0] - nb[0] * 3, q1[1] - nb[1] * 3, 0.6]), r2([q0[0] - nb[0] * 3, q0[1] - nb[1] * 3, 0.6])], color='#3b2c32'))
    for u, L in ((130, 9), (370, 11), (1400, 13), (2000, 9), (2250, 10), (2700, 12), (2920, 9), (3550, 10)):
        q = at(u, 1250, shore(u) - 10); azb = math.degrees(math.atan2(nb[0], nb[1]))
        P.append(dict(k='box', c=r2([q[0], q[1], 0.0]), s=[round(L * 0.75, 1), 2.6, 1.2], az=round(azb, 1), color='#4d3d47'))
        P.append(dict(k='box', c=r2([q[0] - nb[0] * 0.8, q[1] - nb[1] * 0.8, 1.2]), s=[round(L * 0.3, 1), 2.0, 1.0], az=round(azb, 1), color='#5f4d58'))
    clear = [[list(np.round(at(u, 1250, shore(u) + dd)[:2], 1)) for u, dd in ((900, -5), (3600, -5), (3600, 60), (900, 60))], [[455, 145], [485, 145], [485, 172], [455, 172]]]   # V16 boxes #1328, #1327
    return dict(scene='T4/10 Skyline with Ferris Wheel', camera='Skyline with Ferris Wheel', note=ferris_marina.__doc__.split('\n')[0], props=P, clear=clear)


def arsht_night():
    """S2/44 Vice City 08 (Ferris Wheel) — the Arsht Center at night seen from a downtown balcony (pose SOLVED, BA). On the
    frame both halls are UPLIT (pale walls, few windows), which the generic night facades (dark + lit windows) miss:
    relit copies of their solid layers (tools/mesh_solids.py), offset 0.3 m outwards: Galina Ballet Opera House pale
    green with a cyan-lit crown, Knight Concert Hall pale grey with its warm glass foyer."""
    import mesh_solids
    S = mesh_solids.cached(); P = []
    def relit(name, col, e, top=None, offs=0.3, edge='#dff3ea'):
        so = S[name]; n = len(so['layers'])
        for i, L in enumerate(so['layers']):
            for pp in L['polys']:
                q = np.array(pp['outer'], float); c = q.mean(0); d = q - c; r = np.linalg.norm(d, axis=1, keepdims=True); q = c + d * (1 + offs / np.maximum(r, 1))
                cc, ee = (top if (top and i == n - 1) else (col, e))
                P.append(dict(k='prism', poly=[[round(float(x), 2), round(float(y), 2)] for x, y in q], z0=round(L['z0'], 2), z1=round(L['z1'] + 0.05, 2), color=cc, e=ee))
                ring = [[round(float(x), 2), round(float(y), 2), round(L['z1'] - 0.3, 2)] for x, y in np.vstack([q, q[:1]])]
                P.append(dict(k='glow', pts=ring, r=0.12, color=edge, i=1.2))   # lit tier edge (as on the frame)
    relit('Galina Ballet Opera House', '#6f8a80', 0.22, top=('#4f9a90', 0.45))
    relit('Knight Concert Hall', '#7c8682', 0.18, edge='#f0eee4')
    # warm glass foyer of the Knight hall (frame: yellow-lit glazed block on its west side) = its lowest layer, lit
    L0 = S['Knight Concert Hall']['layers'][0]
    for pp in L0['polys']:
        q = np.array(pp['outer'], float); c = q.mean(0); q = c + (q - c) * 1.02
        P.append(dict(k='prism', poly=[[round(float(x), 2), round(float(y), 2)] for x, y in q], z0=round(L0['z0'], 2), z1=round(L0['z0'] + 9.0, 2), color='#c9a64e', e=0.55))
    return dict(scene='S2/44 Vice City 08 (Arsht Center at night)', camera='Vice City 08 (Ferris Wheel)', note=arsht_night.__doc__.split('\n')[0], props=P)


def convertible_bridge():
    """T4/11 Lucia and Jason in a Convertible — westbound on the I-397 bridge, Brickell Key across the water (pose SOLVED on
    the Pegassi Towers). The car fills the lower half of the frame; behind it: the bridge deck at z 6 (V16 has the westbound
    carriageway at z 0.3), its median and south parapets, and the trees of the Brickell Key north shore (crown tops read on
    the frame: v ~930-950 under the far tower at u 2120-2310, v ~660-700 through the windshield at u 2950-3450; between
    them, hidden by Jason, ESTIMATED). Shore distance per column from the V17 water mask."""
    from yanis_markers import crop as _c
    V = View('Lucia and Jason in a Convertible'); P = []; r2 = lambda a: [round(float(v), 2) for v in a]; o = V.o
    # bridge: hwy 99 (westbound) / hwy 100 (eastbound) centrelines of tools/threejs/_v16_roads.json, deck z 6.0
    yw = lambda x: -472.9 - 0.2557 * (x + 43.8); ye = lambda x: -487.8 - 0.2550 * (x + 46.2); ZD = 6.0
    xs = np.arange(-160.0, 81.0, 20.0)
    for x0_, x1_ in zip(xs[:-1], xs[1:]):
        P.append(dict(k='quad', p=[r2([x0_, yw(x0_) + 7.0, ZD]), r2([x1_, yw(x1_) + 7.0, ZD]), r2([x1_, ye(x1_) - 7.0, ZD]), r2([x0_, ye(x0_) - 7.0, ZD])], color='#55585c'))
        for y_ in (yw, ye):                                                  # dashed lane lines (3 lanes each way)
            for off in (-2.0, 2.0):
                P.append(dict(k='quad', p=[r2([x0_, y_(x0_) + off - 0.08, ZD + 0.02]), r2([x0_ + 3, y_(x0_ + 3) + off - 0.08, ZD + 0.02]), r2([x0_ + 3, y_(x0_ + 3) + off + 0.08, ZD + 0.02]), r2([x0_, y_(x0_) + off + 0.08, ZD + 0.02])], color='#e8e6e0'))
    az = math.degrees(math.atan2(1.0, -0.2557)); L = float(np.hypot(240.0, 240.0 * 0.2557))
    for yy in (lambda x: (yw(x) + ye(x)) / 2, lambda x: ye(x) - 6.8):       # median + south parapets (concrete, 0.9 m: the frame sees the sea horizon over them)
        c = np.array([-40.0, yy(-40.0)]); P.append(dict(k='box', c=r2([c[0], c[1], ZD]), s=[round(L, 1), 0.45, 0.9], az=round(az, 1), color='#b9b6ae'))
    # Brickell Key north-shore trees
    x0, y0 = o[0] - 200, o[1] - 900; M = cv2.cvtColor(_c(x0, y0, x0 + 600, y0 + 900), cv2.COLOR_BGR2HSV).astype(int)
    water = (M[..., 0] >= 88) & (M[..., 0] <= 118) & (M[..., 1] > 70)
    def shore(u):
        d = V.ray(u, 1100); d2 = d[:2] / np.linalg.norm(d[:2])
        for s_ in range(120, 880):
            x, y = o[0] + d2[0] * s_, o[1] + d2[1] * s_
            if not water[int(y0 + 900 - y), int(x - x0)]: return float(s_), d2
        return 400.0, d2
    def vtop(u): return np.interp(u, [1800, 2120, 2310, 2950, 3200, 3450, 3700], [950, 935, 940, 700, 665, 690, 700])
    GREEN = ['#5f7048', '#687a4e', '#55663f', '#73835a']; rng = np.random.default_rng(11)
    for u in np.arange(1780, 3720, 55):                                      # broad crowns (shade trees), the trunk mostly hidden
        D, d2 = shore(u); D += rng.uniform(12, 35); b = o[:2] + d2 * D; g = max(T(b[0], b[1]), 2.0)
        ht = float((V.o + V.ray(u, vtop(u)) / np.linalg.norm(V.ray(u, vtop(u))[:2]) * D)[2]) - g
        ht = float(np.clip(ht, 7.0, 14.0)); rr = rng.uniform(4.0, 5.8)
        P.append(dict(k='cyl', a=r2([b[0], b[1], g]), b=r2([b[0], b[1], g + ht - rr]), r=0.4, color='#4a3d33'))
        for k in range(3):
            dc = rng.normal(0, rr * 0.35, 3) * [1, 1, 0.4]
            P.append(dict(k='blob', c=r2([b[0] + dc[0], b[1] + dc[1], g + ht - rr * 0.95 + dc[2]]), r=[round(rr * rng.uniform(0.8, 1.05), 1)] * 2 + [round(rr * 0.75, 1)], color=GREEN[int(rng.integers(4))]))
    return dict(scene='T4/11 Lucia and Jason in a Convertible', camera='Lucia and Jason in a Convertible', note=convertible_bridge.__doc__.split('\n')[0], props=P,
                nolamp=[[[-150, -450], [70, -505], [70, -545], [-150, -490]]])   # bridge in view: no lamp on the frame (u 1700-3000 shows the towers)


def _roundabout_sign(path, W=1360, H=1000):
    """the T4/09 'roundabout ahead' guide sign redrawn sharp (the frame is out of focus; its right half is behind the iguana):
    approach from the east arm; straight = the west arm to the Grassrivers Visitor Center (GTADB L625), left = US 1 South (Key
    Lento, Goose Key with the airport pictogram), right = US 1 North (Hamlet) (Alexandre). The diagram is centred (frame: ring at
    u ~1450, left edge u 1100 -> right edge ~1800). Florida-style green panel, white border, US 1 shields."""
    from PIL import Image, ImageDraw, ImageFont
    GRN, WHT, BLK = (0, 106, 58), (246, 246, 240), (20, 20, 20)
    F = '/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf'
    font = lambda s: ImageFont.truetype(F, s) if os.path.exists(F) else ImageFont.load_default()
    im = Image.new('RGB', (W, H), GRN); d = ImageDraw.Draw(im)
    d.rounded_rectangle([14, 14, W - 15, H - 15], radius=44, outline=WHT, width=14)
    cx, cy, R, w = W // 2, 610, 112, 40                                    # roundabout diagram, centred
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=WHT, width=w)
    d.rectangle([cx - 26, cy + R - 6, cx + 26, H - 60], fill=WHT)          # approach
    def arm(x0, y0, x1, y1, head):
        d.line([x0, y0, x1, y1], fill=WHT, width=w); d.polygon(head, fill=WHT)
    arm(cx, cy - R, cx, 330, [(cx - 52, 342), (cx + 52, 342), (cx, 266)])                       # straight
    arm(cx - R, cy, cx - 196, cy, [(cx - 184, cy - 52), (cx - 184, cy + 52), (cx - 258, cy)])   # left
    arm(cx + R, cy, cx + 196, cy, [(cx + 184, cy - 52), (cx + 184, cy + 52), (cx + 258, cy)])   # right
    def shield(x, y, s, txt):
        pts = [(x, y + 0.18 * s), (x + 0.12 * s, y), (x + 0.32 * s, y + 0.07 * s), (x + 0.5 * s, y), (x + 0.68 * s, y + 0.07 * s),
               (x + 0.88 * s, y), (x + s, y + 0.18 * s), (x + 0.94 * s, y + 0.75 * s), (x + 0.5 * s, y + 1.05 * s), (x + 0.06 * s, y + 0.75 * s)]
        d.polygon(pts, fill=WHT, outline=BLK); f = font(int(0.78 * s)); tw = d.textlength(txt, font=f)
        d.text((x + s / 2 - tw / 2, y + 0.16 * s), txt, fill=BLK, font=f)
    def plane(x, y, s):                                                    # airport pictogram (airplane seen from above, nose up)
        P = lambda pts: [(x + s * a, y + s * b) for a, b in pts]
        d.polygon(P([(0.46, 0.0), (0.54, 0.0), (0.58, 0.12), (0.58, 0.36), (1.0, 0.6), (1.0, 0.7), (0.58, 0.56), (0.57, 0.82),
                     (0.72, 0.94), (0.72, 1.0), (0.5, 0.94), (0.28, 1.0), (0.28, 0.94), (0.43, 0.82), (0.42, 0.56), (0.0, 0.7),
                     (0.0, 0.6), (0.42, 0.36), (0.42, 0.12)]), fill=WHT)
    ctext = lambda x, y, t, s: d.text((x - d.textlength(t, font=font(s)) / 2, y), t, fill=WHT, font=font(s))
    ctext(cx, 50, 'Grassrivers', 100); ctext(cx, 148, 'Visitor Center', 78)                      # straight
    # left: US 1 South
    shield(56, 300, 116, '1'); d.text((186, 316), 'SOUTH', fill=WHT, font=font(84))
    d.text((56, 440), 'Key Lento', fill=WHT, font=font(84))
    d.text((56, 540), 'Goose Key', fill=WHT, font=font(76))
    bb = d.textbbox((56, 540), 'Goose Key', font=font(76)); capc = (bb[1] + d.textbbox((56, 540), 'G', font=font(76))[3]) / 2
    plane(bb[2] + 18, capc - 36, 72)
    # right: US 1 North
    xr = cx + 280
    shield(xr, 300, 116, '1'); d.text((xr + 130, 316), 'NORTH', fill=WHT, font=font(84))
    d.text((xr, 440), 'Hamlet', fill=WHT, font=font(84))
    im.save(path)


def iguana_roundabout():
    """T4/09 Iguana — east arm of the Keys US 1 roundabout, under the US 1 Hamlet Viaduct (pose SOLVED). Dressing read on the
    frame (golden hour): the green 'roundabout ahead' sign (u 1100-1580, v 540-1060, ~3.6 m wide ->
    55 m), the street-light pole at the left edge (base v 1480 -> 29 m), a second street light (u 750) and a wooden utility pole
    with its cross-arm (u 1010), the white building at the left edge, the car ahead (tyres v 1520), the yellow transverse road
    bars (v 1570..1805), dark trees left of the sign and palms beyond the viaduct on the right. Distances ESTIMATED (one view).
    The sign face is redrawn sharp with the map's directions (_roundabout_sign)."""
    V = View('Iguana'); P = []; r2 = lambda a: [round(float(v), 2) for v in a]; o = V.o
    def ground_at(u, v):
        g = T(o[0], o[1])
        for _ in range(4):
            p = V.on_plane_z(u, v, g); g = T(p[0], p[1])
        return p
    def along(u, D):                                                       # horizontal point D m along the column u, on the ground
        d = V.ray(u, 1300.0); d2 = d[:2] / np.linalg.norm(d[:2]); q = o[:2] + d2 * D; return np.r_[q, T(q[0], q[1])]
    def zat(v, D, u=1920.0):                                               # height of frame row v at horizontal distance D
        d = V.ray(u, v); return float(o[2] + d[2] / np.linalg.norm(d[:2]) * D)
    head = math.radians(-CAMS['Iguana']['ypr'][0]); fwd = np.array([math.sin(head), math.cos(head)]); side = np.array([fwd[1], -fwd[0]])
    AZ = math.degrees(head) % 360
    # the road straight ahead (frame: asphalt from the iguana to the car; the V17 drape has water there): asphalt apron
    RJ = json.load(open(os.path.join(THIS, 'threejs', '_v16_roads.json'))) if os.path.exists(os.path.join(THIS, 'threejs', '_v16_roads.json')) else None
    zr0 = None
    if RJ:                                                                 # height of the drawn V16 road ribbon under the camera
        best = min(((math.hypot(q[0] - o[0], q[1] - o[1]), q[2]) for r in RJ['road'] for q in r['p'] if abs(q[0] - o[0]) < 30 and abs(q[1] - o[1]) < 30), default=None)
        zr0 = best[1] if best else None
    g0 = max(T(o[0], o[1]) + 0.33, (zr0 or -99) + 0.34 + 0.05)             # just above the ribbon (view3d lifts streets 0.34 m)
    for d0 in np.arange(2.0, 70.0, 4.0):
        a0, a1 = o[:2] + fwd * d0, o[:2] + fwd * (d0 + 4.0)
        q = [a0 - side * 7.0, a0 + side * 9.0, a1 + side * 9.0, a1 - side * 7.0]
        P.append(dict(k='quad', p=[r2([*x, g0]) for x in q], color='#3c3d3f', e=0.0))
    # yellow transverse bars across the road (frame rows 1570, 1650, 1730, 1805)
    for v in (1570, 1650, 1730, 1805):
        c = V.on_plane_z(1150, v, g0 + 0.05); a, b = c[:2] - side * 2.2, c[:2] + side * 2.2
        zr = g0 + 0.05                                                    # on the apron
        P.append(dict(k='quad', p=[r2([*(a - fwd * 0.35), zr]), r2([*(b - fwd * 0.35), zr]), r2([*(b + fwd * 0.35), zr]), r2([*(a + fwd * 0.35), zr])], color='#d9a632', e=0.15))
    # the car ahead (rear at the tyre row v 1520, roof v 1130)
    c = ground_at(1080, 1520); D = float(np.linalg.norm(c[:2] - o[:2])); hc = zat(1130, D, 1080) - c[2]
    cc = c[:2] + fwd * 2.2
    P.append(dict(k='box', c=r2([cc[0], cc[1], c[2] + 0.25]), s=[4.6, 2.0, round(max(1.2, hc - 0.25), 2)], az=round(AZ, 1), color='#1d2430'))
    P.append(dict(k='box', c=r2([cc[0], cc[1], c[2]]), s=[3.2, 1.9, 0.35], az=round(AZ, 1), color='#101318'))
    # street-light pole at the left edge (base v 1480, head at v ~400)
    b = ground_at(142, 1480); Db = float(np.linalg.norm(b[:2] - o[:2])); zh = zat(400, Db, 142)
    P.append(dict(k='cyl', a=r2(b), b=r2([b[0], b[1], zh + 1.2]), r=0.14, color='#c9c6bd'))
    arm = b[:2] + side * -1.6
    P.append(dict(k='cyl', a=r2([b[0], b[1], zh]), b=r2([arm[0], arm[1], zh]), r=0.08, color='#c9c6bd'))
    P.append(dict(k='box', c=r2([arm[0], arm[1], zh - 0.15]), s=[0.7, 0.35, 0.15], az=round(AZ, 1), color='#e8e4d8'))
    # second street light (u 750, head v 400) and the wooden utility pole with its cross-arm (u 1010, top v 430, arm v 460)
    for u, D, vt, col, rr in ((750, 62.0, 400, '#b9b6ae', 0.14), (1010, 70.0, 430, '#6b5a45', 0.17)):
        g = along(u, D); zt = zat(vt, D, u)
        P.append(dict(k='cyl', a=r2(g), b=r2([g[0], g[1], zt]), r=rr, color=col))
        if col == '#6b5a45':
            za = zat(460, D, u); P.append(dict(k='cyl', a=r2([*(g[:2] - side * 1.1), za]), b=r2([*(g[:2] + side * 1.1), za]), r=0.09, color=col))
            nxt = along(u - 600, D + 25); P.append(dict(k='line', pts=[r2([g[0], g[1], za]), r2([nxt[0], nxt[1], za - 0.6])], color='#2a2622', opacity=0.6))
        else:
            P.append(dict(k='box', c=r2([g[0], g[1], zt]), s=[0.8, 0.35, 0.18], az=round(AZ, 1), color='#e8e4d8'))
    # green 'roundabout ahead' sign: vertical panel facing the camera at ~55 m; its left edge u 1100 and top/bottom v 540/1060 are on
    # the frame, its right half is behind the iguana; the diagram (u ~1450) is centred -> right edge ~ u 1800
    D = 55.0; n = -fwd; p0 = along(1450, D)
    BL, BR = V.on_vplane(1100, 1060, p0, n), V.on_vplane(1800, 1060, p0, n); TL, TR = V.on_vplane(1100, 540, p0, n), V.on_vplane(1800, 540, p0, n)
    _roundabout_sign(os.path.join(THIS, 'threejs', '_prop_iguana_sign.png'))   # redrawn with the map's directions (Alexandre)
    P.append(dict(k='tex', p=[r2(q) for q in (BL, BR, TR, TL)], img='_prop_iguana_sign.png'))
    P.append(dict(k='box', c=r2(np.r_[(BL[:2] + BR[:2]) / 2 - n * 0.15, BL[2] - 0.1]), s=[float(np.linalg.norm(BR[:2] - BL[:2])) + 0.2, 0.2, float(TL[2] - BL[2]) + 0.2], az=round(AZ + 90, 1), color='#2c3a30'))
    for t in (0.18, 0.82):
        q = BL[:2] + (BR[:2] - BL[:2]) * t - n[:2] * 0.3; g = T(q[0], q[1])
        P.append(dict(k='cyl', a=r2([q[0], q[1], g]), b=r2([q[0], q[1], BL[2]]), r=0.09, color='#9ea3a6'))
    # white building at the left edge (u 0..300, top v 580) ~45 m
    D = 60.0; g = along(90, D); zt = zat(600, D, 90)
    cb = g[:2] - side * 2.5                                                # mostly off the left edge
    P.append(dict(k='box', c=r2([cb[0], cb[1], g[2]]), s=[5.0, 6.0, round(zt - g[2], 2)], az=round(AZ, 1), color='#e6e1d6'))
    # dark trees left of the sign (u 300..1000, crowns v 700..1300) and palms beyond the viaduct (u 2300..3800, tops v 300..500)
    rng = np.random.default_rng(9)
    for u in np.arange(300, 1050, 70):
        D = rng.uniform(85, 120); g = along(u, D); top = zat(rng.uniform(690, 760), D, u); rr = rng.uniform(2.8, 3.8)
        P.append(dict(k='blob', c=r2([g[0], g[1], top - rr * 0.8]), r=[round(rr, 1), round(rr, 1), round(rr * 0.8, 1)], color=['#3b4a2c', '#46552f', '#33422a'][int(rng.integers(3))]))
        P.append(dict(k='cyl', a=r2(g), b=r2([g[0], g[1], top - rr]), r=0.3, color='#3d3126'))
    for u in (2480, 2950, 3420, 3760):
        D = rng.uniform(80, 115); g = along(u, D); top = zat(rng.uniform(300, 480), D, u)
        P.append(dict(k='palm', a=r2(g), h=round(max(7.0, top - g[2]), 1), lean_az=round(rng.uniform(0, 360), 0), lean=0.06))
    for u in np.arange(2250, 3850, 120):
        D = rng.uniform(95, 130); g = along(u, D); top = zat(rng.uniform(560, 720), D, u); rr = rng.uniform(2.8, 3.8)
        P.append(dict(k='blob', c=r2([g[0], g[1], top - rr * 0.8]), r=[round(rr, 1), round(rr, 1), round(rr * 0.75, 1)], color=['#56662f', '#62723a', '#4b5a2c'][int(rng.integers(3))]))
    nolamp = [[[o[0] + 20, o[1] + 45], [o[0] - 180, o[1] + 45], [o[0] - 180, o[1] - 70], [o[0] + 20, o[1] - 70]]]
    return dict(scene='T4/09 Iguana', camera='Iguana', note=iguana_roundabout.__doc__.split('\n')[0], props=P,
                nolamp=[[r2(q)[:2] for q in poly] for poly in nolamp])


# ---- generic wide-body jet (plane frame: origin = main-gear axle centre on the ground, x forward, y left, z up) [T4/20]
JET_D=dict(L_nose=34.0,L_tail=-40.0,R_fus=3.1,z_fus=5.6,                       # fuselage
       wing_root_le=8.0,wing_root_chord=13.0,wing_span=32.0,sweep=31.0,tip_chord=3.2,z_wing=4.3,dihedral=6.0,wing_t=0.9,
       eng_y=11.5,eng_x=5.5,eng_len=6.5,eng_r=1.45,eng_z=2.3,eng2_y=20.5,eng2_x=0.0,
       gear_y=5.6,gear_wheel_r=0.66,gear_wb=1.5,gear_wt=1.5,
       fair=[(7.5,0.55),(12.5,0.5),(17.5,0.45),(22.5,0.4)],
       fin_h=10.0,stab_span=10.0)
def _jet_build(D):
    P=[]   # list of (kind, dict) in plane coords
    # fuselage: cylinder segments (nose taper, tail cone up-swept)
    xs=np.linspace(D['L_tail'],D['L_nose'],30)
    def rad(x):
        if x>D['L_nose']-8: return D['R_fus']*math.sqrt(max(0.02,1-((x-(D['L_nose']-8))/8)**2))
        if x<D['L_tail']+14: return D['R_fus']*max(0.25,(x-D['L_tail'])/14)
        return D['R_fus']
    def zc(x): return D['z_fus']+(max(0,(D['L_tail']+14)-x)/14)*1.8
    for a,b in zip(xs[:-1],xs[1:]):
        m=(a+b)/2; P.append(('cyl',dict(a=(a,0,zc(a)),b=(b,0,zc(b)),r=rad(m),color='#e7e8ea')))
    # wings (each side): quad slab (upper and lower surface) + leading/trailing
    for sg in (1,-1):
        y0=D['R_fus']*0.9; y1=D['wing_span']
        def le(y): return D['wing_root_le']-(y-y0)*math.tan(math.radians(D['sweep']))
        def ch(y): return D['wing_root_chord']+(D['tip_chord']-D['wing_root_chord'])*(y-y0)/(y1-y0)
        def zw(y): return D['z_wing']+(y-y0)*math.tan(math.radians(D['dihedral']))
        ys=np.linspace(y0,y1,7)
        for ya,yb in zip(ys[:-1],ys[1:]):
            for dz,col in ((0,'#cfd2d6'),(D['wing_t'],'#dfe1e4')):
                P.append(('quad',dict(p=[(le(ya),sg*ya,zw(ya)+dz),(le(yb),sg*yb,zw(yb)+dz),(le(yb)-ch(yb),sg*yb,zw(yb)+dz*0.6),(le(ya)-ch(ya),sg*ya,zw(ya)+dz*0.6)],color=col)))
            P.append(('quad',dict(p=[(le(ya),sg*ya,zw(ya)),(le(yb),sg*yb,zw(yb)),(le(yb),sg*yb,zw(yb)+D['wing_t']),(le(ya),sg*ya,zw(ya)+D['wing_t'])],color='#bfc2c6')))
        # engine nacelles + pylons (inboard, outboard)
        for ye,xe in ((D['eng_y'],D['eng_x']),(D.get('eng2_y',0),D.get('eng2_x',0))):
            if not ye: continue
            ze=D.get('eng_z_%d'%int(ye),zw(ye)-D['eng_r']-0.9)
            P.append(('cyl',dict(a=(xe+D['eng_len']/2,sg*ye,ze),b=(xe-D['eng_len']/2,sg*ye,ze),r=D['eng_r'],color='#d9dbde')))
            P.append(('cyl',dict(a=(xe-D['eng_len']/2,sg*ye,ze),b=(xe-D['eng_len']/2-1.6,sg*ye,ze),r=D['eng_r']*0.55,color='#7d8186')))
            P.append(('box',dict(c=(xe-1.0,sg*ye,ze+D['eng_r']*0.7),s=(5.5,0.5,zw(ye)-ze-D['eng_r']*0.7+0.3),color='#c9ccd0')))
        # flap-track fairings (canoes) under the trailing edge
        for yf,rf in D['fair']:
            xt=le(yf)-ch(yf); P.append(('cyl',dict(a=(xt+2.0,sg*yf,zw(yf)-0.2),b=(xt-2.8,sg*yf,zw(yf)-0.5),r=rf*1.4,color='#c3c6ca')))
        # main gear: strut, bogie, 4 wheels
        yg=D['gear_y']; r=D['gear_wheel_r']
        P.append(('cyl',dict(a=(0,sg*yg,r+0.2),b=(0.6,sg*yg,zw(yg)),r=0.28,color='#9a9ea3')))
        P.append(('cyl',dict(a=(0.2,sg*yg,zw(yg)-0.6),b=(-1.6,sg*(yg+1.2),zw(yg)+0.2),r=0.12,color='#8a8e93')))
        P.append(('box',dict(c=(0,sg*yg,r-0.15),s=(D['gear_wb']+0.8,0.35,0.3),color='#6d7176')))
        for dx in (-D['gear_wb']/2,D['gear_wb']/2):
            for dy in (-D['gear_wt']/2,D['gear_wt']/2):
                P.append(('cyl',dict(a=(dx,sg*(yg+dy)-0.22,r),b=(dx,sg*(yg+dy)+0.22,r),r=r,color='#262729')))
    # body gear (747-like): 2 bogies under the fuselage, behind the wing gear
    if D.get('body_gear'):
        for sg in (1,-1):
            yb=D['body_gear_y']; xb=D['body_gear_x']; r=D['gear_wheel_r']
            P.append(('cyl',dict(a=(xb,sg*yb,r+0.2),b=(xb,sg*yb,D['z_fus']-D['R_fus']*0.8),r=0.26,color='#9a9ea3')))
            P.append(('box',dict(c=(xb,sg*yb,r-0.15),s=(D['gear_wb']+0.8,0.35,0.3),color='#6d7176')))
            for dx in (-D['gear_wb']/2,D['gear_wb']/2):
                for dy in (-D['gear_wt']/2,D['gear_wt']/2):
                    P.append(('cyl',dict(a=(xb+dx,sg*(yb+dy)-0.22,r),b=(xb+dx,sg*(yb+dy)+0.22,r),r=r,color='#262729')))
    # tail: fin + stabilisers
    xt=D['L_tail']+6
    P.append(('quad',dict(p=[(xt+8,0,zc(xt+8)+D['R_fus']*0.6),(xt,0,zc(xt)+D['R_fus']*0.5),(xt-3,0,zc(xt)+D['fin_h']),(xt+1.5,0,zc(xt)+D['fin_h'])],color='#d8dadd')))
    for sg in (1,-1):
        P.append(('quad',dict(p=[(xt+6,0,zc(xt)),(xt+0,sg*D['stab_span'],zc(xt)+0.8),(xt-2.5,sg*D['stab_span'],zc(xt)+0.8),(xt-1,0,zc(xt))],color='#d0d3d6')))
    # nose gear
    P.append(('cyl',dict(a=(D['L_nose']-9,0,0.5),b=(D['L_nose']-9,0,D['z_fus']-D['R_fus']),r=0.2,color='#9a9ea3')))
    for dy in (-0.4,0.4): P.append(('cyl',dict(a=(D['L_nose']-9,dy-0.15,0.5),b=(D['L_nose']-9,dy+0.15,0.5),r=0.5,color='#262729')))
    return P
def _jet_world(P,X,Y,G,psi,pitch=0.0):
    h=math.radians(psi); t=math.radians(pitch); f=np.array([math.sin(h),math.cos(h)]); l=np.array([-f[1],f[0]])
    def W(p):
        x,y,z=p; x2=x*math.cos(t)-z*math.sin(t); z2=x*math.sin(t)+z*math.cos(t)
        q=np.array([X,Y])+f*x2+l*y; return [round(float(q[0]),2),round(float(q[1]),2),round(float(G+z2),2)]
    out=[]
    for k,d in P:
        e=dict(d); e['k']=k
        if k=='cyl': e['a']=W(d['a']); e['b']=W(d['b'])
        elif k=='quad': e['p']=[W(p) for p in d['p']]
        elif k=='box':
            c=W(d['c']); e['c']=[c[0],c[1],round(c[2]-d['s'][2]/2,2)]; e['s']=[float(v) for v in d['s']]; e['az']=round(psi,1)
        out.append(e)
    return out


def runway_jet():
    """T4/20 Runway (pose SOLVED): the camera rides low under the right wing of a twin-engine wide-body taking off toward the NW
    (heading 302 = the runway reversed: the pickup racing beside the gear faces the camera), looking aft. Generic jet primitives
    placed on the frame: right main gear at u 3015 (12.5 m), engine at the left edge (u 0..1000), flap-track fairings u 1660..2180 and
    2580..2840, fuselage belly at the right edge. Sizes ESTIMATED (one view)."""
    V = View('Runway'); o = V.o; P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    D = dict(JET_D); D.update(dict(z_wing=3.6, dihedral=5.0, sweep=37.0, wing_root_le=9.0, wing_root_chord=14.0, wing_span=32.0, tip_chord=4.0,
             R_fus=3.2, z_fus=6.6, eng_y=20.0, eng_x=-3.5, eng_r=1.75, eng_len=7.2, eng_z_20=3.1, eng2_y=0, gear_y=5.5, gear_wheel_r=0.62,
             gear_wt=1.3, body_gear=0, fair=[(7.0, 0.55), (11.0, 0.5), (26.0, 0.4)]))
    psi = 302.15; h = math.radians(psi); l = np.array([-math.cos(h), math.sin(h)])
    d = V.ray(3015, 960.0); d2 = d[:2] / np.linalg.norm(d[:2]); gR = o[:2] + d2 * 12.5   # the right main gear
    axle = gR + l * D['gear_y']; G = T(axle[0], axle[1])
    P += _jet_world(_jet_build(D), axle[0], axle[1], G, psi)
    # (no pickup: a box version spoiled the view, Alexandre; the frame shows it during the arrival)
    return dict(scene='T4/20 Runway (jet)', camera='Runway', note=runway_jet.__doc__.split('\n')[0], props=P)


def red_car_terminal():
    """T4/21 Jason and Lucia by the Red Car — NW corner of the M21 container terminal, looking SW at the elevated I-297 (pose:
    Yanis's heading, moved 35 m into the yard; checked: the sun sits at the right edge, the berm behind Lucia, ~74 m, 14 m above the eye, tops at
    v ~600, and the overhead guide signs over the I-297 ramp ~135 m away at u 1470-1760, v 480-540). Dressing read on the frame:
    the container stacks on the right (3 high, rows ~280 px -> ~18-21 m), smaller stacks far left in the yard, the sign gantry.
    Close-up: the tour shows the full frame on arrival. Distances ESTIMATED."""
    V = View('Jason and Lucia by the Red Car'); o = V.o; P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    g0 = T(o[0], o[1])
    def along(u, D):
        d = V.ray(u, 960.0); d2 = d[:2] / np.linalg.norm(d[:2]); q = o[:2] + d2 * D; return q, d2
    COLS = ['#c9cbcc', '#bfc2c4', '#8a4b3c', '#9c5a46', '#d2d3d1', '#7b4335']; rng = np.random.default_rng(21)
    def stack(u, D, n_hi, n_wide, az):
        q, d2 = along(u, D); side = np.array([d2[1], -d2[0]])
        for i in range(n_wide):
            c = q + side * (i - (n_wide - 1) / 2) * 2.5
            for k in range(n_hi):
                P.append(dict(k='box', c=r2([c[0], c[1], g0 + k * 2.6]), s=[12.2, 2.44, 2.55], az=round(az, 1), color=COLS[int(rng.integers(len(COLS)))]))
    head = (-CAMS['Jason and Lucia by the Red Car']['ypr'][0]) % 360
    for u, D, hi, wide in ((2950, 21.0, 3, 3), (3350, 19.0, 3, 3), (3750, 18.0, 3, 3)):    # right: 3 high (tops v ~260-320 at ~19 m)
        stack(u, D, hi, wide, (head + 90) % 360)
    for u, D, hi, wide in ((520, 60.0, 2, 4), (650, 62.0, 2, 3)):                          # far left, in the yard
        stack(u, D, hi, wide, head)
    # overhead sign gantry over the I-297 ramp (V16 hwy 302, deck z ~21) at ~135 m, signs u 1470-1760, v 480-540
    q, d2 = along(1610, 135.0); side = np.array([d2[1], -d2[0]]); zd = 21.0
    for sx in (-9.0, 9.0):
        a = q + side * sx; P.append(dict(k='cyl', a=r2([a[0], a[1], zd]), b=r2([a[0], a[1], zd + 8.0]), r=0.3, color='#8f949a'))
    a, b = q - side * 9.0, q + side * 9.0
    P.append(dict(k='cyl', a=r2([a[0], a[1], zd + 7.6]), b=r2([b[0], b[1], zd + 7.6]), r=0.25, color='#8f949a'))
    for sx, col in ((-4.2, '#1f6b3f'), (0.6, '#1f6b3f'), (5.0, '#c9a227')):
        c = q + side * sx; n = -d2
        A, B = c - side * 2.1, c + side * 2.1
        P.append(dict(k='quad', p=[r2([A[0] - n[0] * 0.3, A[1] - n[1] * 0.3, zd + 5.4]), r2([B[0] - n[0] * 0.3, B[1] - n[1] * 0.3, zd + 5.4]),
                                   r2([B[0] - n[0] * 0.3, B[1] - n[1] * 0.3, zd + 8.2]), r2([A[0] - n[0] * 0.3, A[1] - n[1] * 0.3, zd + 8.2])], color=col, e=0.1))
    return dict(scene='T4/21 Jason and Lucia by the Red Car', camera='Jason and Lucia by the Red Car', note=red_car_terminal.__doc__.split('\n')[0], props=P)


def green_car_edison():
    """T4/25 Green Sports Car on Ocean Drive — NE corner of the Grape St / Shore Dr intersection, looking WSW at the north facade
    of the Edison Hotel (Alexandre; its neighbour the Breakwater is south of it). Pose: the Edison's NE corner (V17) pinned at u 1060
    (Alexandre) and its base. The facade is a texture cut from the frame and put on the plane of the Edison's north facade (the yellow arcade, the white
    tower), plus the asphalt of Grape St with its crosswalk and the near curb, the green trash can (the palms are in the facade
    texture). ESTIMATED."""
    V = View('Green Sports Car on Ocean Drive'); o = V.o; P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    NE, NW = np.array([1963.0, 602.0]), np.array([1939.0, 602.0]); n = np.array([NW[1] - NE[1], -(NW[0] - NE[0])]); n /= np.linalg.norm(n)
    if n @ (o[:2] - NE) < 0: n = -n
    p0 = NE + n * 0.3                                                       # the Edison's north facade (Grape St)
    # (no frame texture pasted on the facades: Alexandre, 'une fausse image par dessus' makes no sense; to be rebuilt as geometry)
    zr = o[2] - 0.8                                                       # road level under the eye
    Z = lambda q, dz=0.0: r2([q[0], q[1], max(zr, T(q[0], q[1]) + 0.06) + dz])   # never under the terrain
    fwd = np.array([math.sin(math.radians(-CAMS['Green Sports Car on Ocean Drive']['ypr'][0])), math.cos(math.radians(-CAMS['Green Sports Car on Ocean Drive']['ypr'][0]))])
    side = np.array([fwd[1], -fwd[0]])
    zg = max(zr, T(o[0], o[1]) + 0.06)
    def G(u, v, dz=0.0):                                                   # frame pixel -> road plane, kept above the terrain
        q = V.on_plane_z(u, v, zg); return r2([q[0], q[1], max(zg, T(q[0], q[1]) + 0.08) + dz])
    for v0, v1 in ((1920, 1300), (1300, 1080), (1080, 960), (960, 905)):           # asphalt (frame rows), up to the far sidewalk
        P.append(dict(k='quad', p=[G(-400, v0), G(4240, v0), G(4240, v1), G(-400, v1)], color='#4a4a4f'))
    P.append(dict(k='quad', p=[G(-400, 1700, 0.15), G(1700, 1500, 0.15), G(1700, 1920, 0.15), G(-400, 1920, 0.15)], color='#7a6668'))   # near sidewalk
    for i in range(9):                                                     # crosswalk across Grape St (frame u 640-1700, v 915-1010)
        u0 = 640 + i * 120
        P.append(dict(k='quad', p=[G(u0, 1010, 0.03), G(u0 + 60, 1010, 0.03), G(u0 + 60, 915, 0.03), G(u0, 915, 0.03)], color='#d8d8d2'))
    q = o[:2] + fwd * 3.0 - side * 3.2                                    # trash can (left)
    P.append(dict(k='cyl', a=r2([q[0], q[1], zr]), b=r2([q[0], q[1], zr + 1.1]), r=0.35, color='#1f4a32'))
    return dict(scene='T4/25 Green Sports Car (Edison Hotel, Grape St)', camera='Green Sports Car on Ocean Drive', note=green_car_edison.__doc__.split('\n')[0], props=P,
                clear=[[[1945, 598], [1985, 598], [1985, 625], [1945, 625]]],   # V16 boxes between the camera and the Edison (Grape St; #1422 = the V16 Edison box)
                nolamp=[[[1915, 596], [1985, 596], [1985, 630], [1915, 630]]])


def bike_viaduct():
    """T4/26 Dirt Bike on the Overpass — telephoto from the north bank of the Miami River (pose: Yanis's position, heading on Infinity
    at Brickell, Alexandre) at the elevated rail viaduct ~100 m away (V17 double pink line, bottom of its curve at (-1000, -748)):
    the deck (top from the railing row v ~1090), the near railing, the box girder and two piers, two trains (one per track, their
    ends at u 1050 / 2900 where the bike rides between them), ESTIMATED sizes (the out-of-focus palm in the
    foreground is not modelled)."""
    V = View('Dirt Bike on the Overpass'); o = V.o; P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    CL = np.array([(-1120, -706), (-1100, -715), (-1080, -724), (-1060, -733), (-1040, -742), (-1020, -747.5), (-1000, -748),
                   (-980, -745), (-960, -736), (-940, -721), (-920, -706)], float)
    S_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(CL, axis=0), axis=1))]
    def at(s, w):
        i = int(np.clip(np.searchsorted(S_, s), 1, len(S_) - 1)); a, b = CL[i - 1], CL[i]; u = (b - a) / np.linalg.norm(b - a)
        nrm = np.array([-u[1], u[0]]); return a + (b - a) * (s - S_[i - 1]) / (S_[i] - S_[i - 1]) + nrm * w, u, nrm
    # the near (camera-side) edge: sign of the normal toward the camera
    _, u0, n0 = at(S_[-1] / 2, 0); near = 1.0 if n0 @ (o[:2] - at(S_[-1] / 2, 0)[0]) > 0 else -1.0
    HW = 5.2                                                                # half width of the double-track deck
    sc = float(S_[np.argmin(np.linalg.norm(CL - (o[:2] + (CL[6] - o[:2])), axis=1))])
    pe, ue, ne_ = at(S_[6], near * HW); q = V.on_vplane(1920, 1090, pe, ne_ * near)   # railing top row at the centre column
    ZT = float(q[2]) - 1.1                                                  # deck top
    G = lambda x, y: max(T(x, y), 0.0)
    for s0 in np.arange(0, S_[-1] - 4, 4.0):
        a0, ua, na = at(s0, 0); a1, ub, nb = at(s0 + 4, 0)
        L = lambda p, w, z: r2([*(p[0] + p[2] * w), z])
        A, B = at(s0, -HW), at(s0, HW); C, D = at(s0 + 4, HW), at(s0 + 4, -HW)
        P.append(dict(k='quad', p=[r2([*A[0], ZT]), r2([*B[0], ZT]), r2([*C[0], ZT]), r2([*D[0], ZT])], color='#5a5650'))     # deck top
        P.append(dict(k='quad', p=[r2([*A[0], ZT - 0.45]), r2([*B[0], ZT - 0.45]), r2([*C[0], ZT - 0.45]), r2([*D[0], ZT - 0.45])], color='#4a4238'))   # slab soffit
        for w in (-HW, HW):                                                 # slab edge (thin) + steel edge girder
            E0, E1 = at(s0, w)[0], at(s0 + 4, w)[0]
            P.append(dict(k='quad', p=[r2([*E0, ZT - 0.45]), r2([*E1, ZT - 0.45]), r2([*E1, ZT + 0.15]), r2([*E0, ZT + 0.15])], color='#6a5e4e'))
            P.append(dict(k='quad', p=[r2([*E0, ZT - 1.6]), r2([*E1, ZT - 1.6]), r2([*E1, ZT - 0.45]), r2([*E0, ZT - 0.45])], color='#2f2923'))
        for ds in (0.0, 2.0):                                               # transverse floor beams under the slab (seen from below)
            c0 = at(s0 + ds, 0)[0]; uu = at(s0 + ds, 0)[1]; az = math.degrees(math.atan2(uu[0], uu[1]))
            P.append(dict(k='box', c=r2([c0[0], c0[1], ZT - 1.45]), s=[0.35, 2 * HW - 0.4, 1.0], az=round(az, 1), color='#3a332b'))
        for w in (-3.4, -1.2, 1.2, 3.4):                                    # longitudinal stringers
            E0, E1 = at(s0, w)[0], at(s0 + 4, w)[0]
            P.append(dict(k='cyl', a=r2([*E0, ZT - 0.9]), b=r2([*E1, ZT - 0.9]), r=0.25, color='#332d26'))
        for w in (near * (HW - 0.2),):                                      # railing: top rail, mid rail, posts
            E0, E1 = at(s0, w)[0], at(s0 + 4, w)[0]
            for zz in (ZT + 1.1, ZT + 0.55): P.append(dict(k='cyl', a=r2([*E0, zz]), b=r2([*E1, zz]), r=0.05, color='#3b3833'))
            P.append(dict(k='cyl', a=r2([*E0, ZT]), b=r2([*E0, ZT + 1.1]), r=0.05, color='#3b3833'))
        for w in (-2.4, 2.4):                                               # rails
            for dw in (-0.72, 0.72):
                E0, E1 = at(s0, w + dw)[0], at(s0 + 4, w + dw)[0]
                P.append(dict(k='cyl', a=r2([*E0, ZT + 0.2]), b=r2([*E1, ZT + 0.2]), r=0.06, color='#8a8478'))
    for s0 in np.arange(10, S_[-1], 34.0):                                  # piers
        c = at(s0, 0)[0]; g = G(*c)
        P.append(dict(k='box', c=r2([c[0], c[1], g]), s=[2.4, 3.2, round(ZT - 1.9 - g, 2)], az=0.0, color='#5e564b'))
    # trains: left on the near track ending at the frame column u 1050, right on the far track starting at u 2900
    def s_at(u):
        best = min(np.arange(0, S_[-1], 0.5), key=lambda s: abs(((at(s, 0)[0] - o[:2]) @ np.array([V.R[0, 0], V.R[1, 0]])) / max(1e-6, (at(s, 0)[0] - o[:2]) @ np.array([V.R[0, 1], V.R[1, 1]])) - ((u + 0.5) / V.W * 2 - 1) * V.th))
        return float(best)
    sl, sr = s_at(640), s_at(2900)                                      # left end: the near corner sits ~400 px right of the s point
    dirL = -1.0 if sl > sr else 1.0                                        # the left train extends away from the gap
    for (s_end, w, sgn) in ((sl, near * 2.4, -dirL), (sr, -near * 2.4, dirL)):
        for k in range(3):
            sa, sb = s_end + sgn * (k * 23.5 + 0.5), s_end + sgn * (k * 23.5 + 23.0)
            c = at((sa + sb) / 2, w)[0]; u = at((sa + sb) / 2, 0)[1]; az = math.degrees(math.atan2(u[0], u[1]))
            P.append(dict(k='box', c=r2([c[0], c[1], ZT + 0.35]), s=[22.5, 3.1, 3.5], az=round(az, 1), color='#b9b8b0'))        # stainless body
            P.append(dict(k='box', c=r2([c[0], c[1], ZT + 1.25]), s=[22.4, 3.14, 0.18], az=round(az, 1), color='#3d6fa0'))      # blue stripe
            for wx in np.arange(-9.5, 10.0, 2.4):                                                                                    # windows
                wq = c + u * wx; P.append(dict(k='box', c=r2([wq[0], wq[1], ZT + 2.05]), s=[1.5, 3.16, 0.85], az=round(az, 1), color='#2b333b'))
            P.append(dict(k='box', c=r2([c[0], c[1], ZT + 0.0]), s=[18.0, 2.6, 0.4], az=round(az, 1), color='#2a2724'))        # bogies / skirt
    # Infinity at Brickell's round north drum with its balcony rings (frame: drum u 1272..2508, aimed 100 px left to match the render; the mesh solid is a plain shaft)
    def hit_y(u, y):
        d = V.ray(u, 960.0); t = (y - o[1]) / d[1]; return o[:2] + d[:2] * t
    A, B_ = hit_y(1172, -1368.0), hit_y(2408, -1368.0); rad = float(np.linalg.norm(B_ - A)) / 2
    cc = (A + B_) / 2 + np.array([0.0, -rad])                               # the drum's north face just in front of the mesh shaft
    cc = cc + np.array([V.R[0, 0], V.R[1, 0]]) * 8.0                        # measured on the render: 8 m to the camera's right
    for z in np.arange(30.0, 172.0, 3.4):
        P.append(dict(k='cyl', a=r2([cc[0], cc[1], z]), b=r2([cc[0], cc[1], z + 2.6]), r=round(rad - 0.9, 2), color='#55606a'))    # glass
        P.append(dict(k='cyl', a=r2([cc[0], cc[1], z + 2.6]), b=r2([cc[0], cc[1], z + 3.4]), r=round(rad + 0.3, 2), color='#f2ede2'))  # balcony slab
    P.append(dict(k='cyl', a=r2([cc[0], cc[1], 172.0]), b=r2([cc[0], cc[1], 175.6]), r=round(rad + 0.8, 2), color='#e8e2d6'))
    for k in range(24):                                                     # helipad railing posts
        t = 2 * math.pi * k / 24; q = cc + rad * 0.9 * np.array([math.cos(t), math.sin(t)])
        P.append(dict(k='cyl', a=r2([q[0], q[1], 175.6]), b=r2([q[0], q[1], 176.8]), r=0.08, color='#6b6b6b'))
    return dict(scene='T4/26 Dirt Bike on the Overpass (rail viaduct)', camera='Dirt Bike on the Overpass', note=bike_viaduct.__doc__.split('\n')[0], props=P,
                nolamp=[[[-1130, -690], [-910, -690], [-910, -770], [-1130, -770]]])


def rooftop_explosion():
    """T4/28 Explosion behind Jason — the helipad deck on top of the Stephen P. Clark Government Center at night (pose SOLVED on
    Marina Blue + Vizcayne South). Read on the frame and back-projected on the deck plane (z 155.35): the deck edge ~8-11 m ahead with
    its red perimeter lights (u 261 / 979 / 1633 / 2856), the steel grating walkway one level below beyond the edge, its red handrail
    and the stair going down at the right. ESTIMATED (one view)."""
    V = View('Explosion behind Jason'); o = V.o; P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    ZD = 155.35                                                            # roof top (landmark 'Government Center (NW)')
    L = [V.on_plane_z(u, v, ZD) for u, v in ((261, 1095), (979, 1145), (1633, 1107), (2856, 1225), (3300, 1280), (3840, 1330))]
    ex = np.mean([q[0] for q in L])                                        # the deck's east edge (x ~ -902.5)
    for y0 in np.arange(48.0, 90.0, 2.0):                                  # dark concrete deck, camera side of the edge
        P.append(dict(k='quad', p=[r2([-905.4, y0, ZD + 0.03]), r2([ex, y0, ZD + 0.03]), r2([ex, y0 + 2, ZD + 0.03]), r2([-905.4, y0 + 2, ZD + 0.03])], color='#2b2b34', e=0.0))
    P.append(dict(k='quad', p=[r2([ex, 60, ZD - 0.9]), r2([ex, 86, ZD - 0.9]), r2([ex, 86, ZD + 0.03]), r2([ex, 60, ZD + 0.03])], color='#24242c'))   # deck edge face
    for q in L[:4]:                                                        # red perimeter lights
        P.append(dict(k='glow', pts=[r2([ex - 0.2, q[1], ZD + 0.25])], r=0.07, color='#ff2030', i=2.2, ball=True))
    for y0 in np.arange(60.0, 86.0, 2.0):                                  # grating walkway, one level below
        P.append(dict(k='quad', p=[r2([ex, y0, ZD - 1.0]), r2([ex + 6, y0, ZD - 1.0]), r2([ex + 6, y0 + 2, ZD - 1.0]), r2([ex, y0 + 2, ZD - 1.0])], color='#3b3d44'))
    for zz in (ZD + 0.1, ZD - 0.4):                                        # red handrail on the far side of the walkway (frame: right part only)
        P.append(dict(k='cyl', a=r2([ex + 6, 44, zz]), b=r2([ex + 6, 60, zz]), r=0.04, color='#c2262e'))
    for y0 in np.arange(44.0, 61.0, 1.5):
        P.append(dict(k='cyl', a=r2([ex + 6, y0, ZD - 1.0]), b=r2([ex + 6, y0, ZD + 0.1]), r=0.03, color='#c2262e'))
    for k in range(6):                                                     # stair going down at the right (frame u 3200-3500)
        P.append(dict(k='box', c=r2([ex + 1.0 + k * 0.6, 72.0, ZD - 1.0 - k * 0.45]), s=[0.6, 1.4, 0.06], az=90.0, color='#55585f'))
    return dict(scene='T4/28 Explosion behind Jason (Government Center roof)', camera='Explosion behind Jason', note=rooftop_explosion.__doc__.split('\n')[0], props=P,
                nolamp=[[[-930, 40], [-830, 40], [-830, 100], [-930, 100]]], bare_roof=['Stephen P. Clark Government Center'])


def beach_biplane():
    """T4/30 Biplane over the Beach — South Beach seen from ~32 m up, looking S (pose SOLVED). Beach furniture back-projected on the
    sand from the frame (half-res pixel lists x2): rows of blue-white umbrellas on the right, red-white umbrellas mid-beach, the
    lifeguard tower (yellow roof) and the pink-roof kiosk. Sizes ESTIMATED (umbrella 2.4 m, tower 4.5 m)."""
    V = View('Biplane over the Beach'); o = V.o; P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    def sand(u, v):
        g = T(o[0], o[1])
        for _ in range(4):
            q = V.on_plane_z(u, v, g); g = max(T(q[0], q[1]), 0.6)
        return q
    BLUE = [(1270, 655), (1330, 645), (1390, 660), (1470, 645), (1550, 690), (1520, 740), (1610, 720), (1660, 690), (1720, 720), (1780, 650),
            (1840, 660), (1870, 735), (1880, 775), (1640, 795), (1550, 760), (1480, 735), (1260, 715), (1330, 685), (1600, 625), (1820, 750),
            (1700, 760), (1760, 780), (1420, 700), (1500, 680)]
    RED = [(830, 520), (870, 540), (900, 530), (940, 550), (980, 535), (1000, 560), (860, 560), (1110, 525), (1150, 540), (1220, 540)]
    for pts, col in ((BLUE, '#d8e1e6'), (RED, '#d9585a')):
        for i, (uh, vh) in enumerate(pts):
            q = sand(2 * uh, 2 * vh + 14)                                  # the pole foot is a little below the canopy centre
            P.append(dict(k='cyl', a=r2(q), b=r2([q[0], q[1], q[2] + 2.3]), r=0.04, color='#e8e8e2'))
            c2 = col if (col != '#d8e1e6' or i % 2) else '#3d6f8f'
            P.append(dict(k='blob', c=r2([q[0], q[1], q[2] + 2.25]), r=[1.2, 1.2, 0.35], color=c2))
    # wooden lifeguard tower (yellow roof); the pink-roof station further S is V16 tower #1542, built by beach_lifeguards()
    for (uh, vh), roof, body in (((1060, 600), '#e9c84a', '#6c8ea8'),):
        q = sand(2 * uh, 2 * vh)
        for dx, dy in ((-1.1, -1.1), (1.1, -1.1), (1.1, 1.1), (-1.1, 1.1)):
            P.append(dict(k='cyl', a=r2([q[0] + dx, q[1] + dy, q[2]]), b=r2([q[0] + dx, q[1] + dy, q[2] + 2.2]), r=0.09, color='#9aa3a8'))
        P.append(dict(k='box', c=r2([q[0], q[1], q[2] + 2.2]), s=[3.0, 3.0, 2.2], az=0.0, color=body))
        P.append(dict(k='box', c=r2([q[0], q[1], q[2] + 4.4]), s=[3.6, 3.6, 0.35], az=0.0, color=roof))
    P += _biplane(V)
    # the two tower cranes of the Fisher Island skyline (frame, half-res: mast u 310 / top row 228 / jib row 249 from u 248 to 345 over
    # the 7634 Fisher Island Dr site; mast u 527 / top 228 / short jib row 245 over the Palazzo del Sol lot), back-projected on the
    # vertical planes through those lots; ground from the heightmap. ESTIMATED depth (= the lot).
    for (mx, my), g, ztop, zj, (ax, ay), (bx, by) in (((1959.0, -1361.8), 13.0, 43.7, 31.1, (1994.7, -1367.3), (1938.9, -1358.7)),
                                                      ((1898.5, -1037.7), 4.8, 44.9, 36.2, (1904.5, -1039.0), (1892.1, -1036.3))):
        for dx, dy in ((-0.8, -0.8), (0.8, -0.8), (0.8, 0.8), (-0.8, 0.8)):
            P.append(dict(k='cyl', a=[mx + dx, my + dy, g], b=[mx + dx, my + dy, zj], r=0.12, color='#8a7f6a'))
        P.append(dict(k='box', c=[mx, my, round(zj - 2.0, 2)], s=[2.2, 2.2, 2.0], az=0.0, color='#7a7062'))      # slewing unit + cab
        P.append(dict(k='cyl', a=[ax, ay, zj], b=[bx, by, zj], r=0.45, color='#8a7f6a'))                      # jib + counter-jib
        P.append(dict(k='cyl', a=[mx, my, zj], b=[mx, my, ztop], r=0.35, color='#8a7f6a'))                    # tower peak
        P.append(dict(k='box', c=[bx + (mx - bx) * 0.15, by + (my - by) * 0.15, zj - 1.6], s=[3.0, 2.0, 1.6], az=0.0, color='#5e5850'))   # counterweight
        P.append(dict(k='line', pts=[[ax, ay, zj], [mx, my, ztop], [bx, by, zj]], color='#8a7f6a'))         # pendant ties
    # 101 Ocean Dr (the yellow-banded block left of the Royal Atlantic, Alexandre: « ce building est manquant »): the mesh was
    # there but white; its facade is now the ochre grid of the frame, plus the cantilevered floor slabs of its east end
    for k in range(9):
        z = 15.0 + 3.6 * k
        if z > 44.0: break
        P.append(dict(k='box', c=[2031.6, 32.0, round(z - 0.3, 2)], s=[11.0, 1.8, 0.3], az=0.0, color='#d9cfb4'))
    return dict(scene='T4/30 Biplane over the Beach (South Beach)', camera='Biplane over the Beach', note=beach_biplane.__doc__.split('\n')[0], props=P)


def napping_room():
    """T4/32 Napping in the Chair — the living room of Jason's House (Keys), rebuilt around the camera (Alexandre: « reconstruire
    la piece »). Nothing outside is measurable (blown-out window), so the pose is ESTIMATED (cameras.json INTERIOR-ROOM-V1): the
    frame's back wall with the window = the house's E exterior wall (x -2342), eye 0.9 m above the slab (2.0). Everything is
    BACK-PROJECTED from the frame (display px x 1.92) onto three planes: the panelled back wall (x -2342.25), the table top
    (z 2.75) and the floor: dark wood panelling with grooves, the bright window (jambs u 2477 / 3696, mullion 2790, sill row 518),
    the door / cabinet edge on the left (u 307, 960), the white cane leaning on the wall, the wicker armchair under the window,
    the table with the red cup, burger, fries, paper box and game controller, a desk fan. The sleeper and the snake are not
    modelled. Sizes ESTIMATED."""
    V = View('Napping in the Chair'); P = []; r2 = lambda a: [round(float(v), 3) for v in a]; S = 1.92
    XW, ZF, ZT, ZC = -2342.25, 2.0, 2.75, 4.6         # table top 0.15 m below the eye: the cup's width (~9 cm, 160 px) fixes it
    wall = lambda u, v: V.on_vplane(u * S, v * S, (XW, 0.0), (1.0, 0.0))
    tab = lambda u, v: V.on_plane_z(u * S, v * S, ZT)
    yL, yR = float(wall(-200, 500)[1]), float(wall(2200, 500)[1])               # back wall beyond the frame edges
    WOOD, GROOVE, TRIM = '#4a3524', '#2f2116', '#d8cc98'
    quad = lambda p, col, e=None: P.append(dict(k='quad', p=[r2(q) for q in p], color=col, **({'e': e} if e is not None else {})))
    quad([[XW, yL, ZF], [XW, yR, ZF], [XW, yR, ZC], [XW, yL, ZC]], WOOD, 0.22)                                # back wall
    quad([[XW - 4.4, yL, ZF + 0.01], [XW, yL, ZF + 0.01], [XW, yR, ZF + 0.01], [XW - 4.4, yR, ZF + 0.01]], '#3b2d22', 0.1)   # floor
    quad([[XW - 4.4, yL, ZC], [XW, yL, ZC], [XW, yR, ZC], [XW - 4.4, yR, ZC]], '#2c2119', 0.08)               # ceiling
    for y in (yL, yR): quad([[XW - 4.4, y, ZF], [XW, y, ZF], [XW, y, ZC], [XW - 4.4, y, ZC]], WOOD, 0.16)     # side walls
    # window: glass glowing (bloom), painted trim, mullion
    wa, wb = wall(1290, 300), wall(1925, 300); zs = float(wall(1600, 270)[2]); zt = ZC - 0.15
    ya, yb = float(wa[1]), float(wb[1])
    quad([[XW - 0.02, ya, zs], [XW - 0.02, yb, zs], [XW - 0.02, yb, zt], [XW - 0.02, ya, zt]], '#fbf6ea', 2.6)
    for y in (ya, yb, float(wall(1452, 300)[1])):
        P.append(dict(k='box', c=r2([XW - 0.06, y, zs]), s=[0.09, 0.12, round(zt - zs, 2)], az=0.0, color=TRIM))
    P.append(dict(k='box', c=r2([XW - 0.06, (ya + yb) / 2, zs - 0.08]), s=[abs(yb - ya) + 0.2, 0.16, 0.08], az=0.0, color=TRIM))   # sill
    # panel grooves every 0.22 m (not across the window)
    y = yL
    while y > yR:
        if not (yb - 0.05 < y < ya + 0.05):
            P.append(dict(k='box', c=r2([XW - 0.02, y, ZF]), s=[0.02, 0.018, ZC - ZF], az=0.0, color=GROOVE))
        y -= 0.22
    # door / cabinet on the left: lighter frame strip and the panel junction
    for u in (140, 500):
        q = wall(u, 400); P.append(dict(k='box', c=r2([XW - 0.05, q[1], ZF]), s=[0.08, 0.07 if u == 500 else 0.12, ZC - ZF - 0.2], az=0.0, color='#7a5c3c' if u == 140 else '#3a2a1c'))
    # white cane leaning on the wall (top at display (275, 230), shaft toward (205, 640))
    top = wall(275, 230); low = wall(205, 640); d = low - top; t = (ZF - top[2]) / d[2]; foot = top + d * t
    P.append(dict(k='cyl', a=r2([foot[0] - 0.05, foot[1], ZF]), b=r2(top - [0.03, 0, 0]), r=0.012, color='#eeeeea'))
    # wicker armchair under the window (seat centre ~2.4 m ahead, 0.8 m right), back against the wall
    cx, cy = XW - 0.55, float(V.o[1]) - 0.8
    WK = '#6a4a2c'
    P.append(dict(k='box', c=[cx, cy, ZF], s=[0.95, 0.85, 0.45], az=90.0, color=WK, e=0.12))
    P.append(dict(k='box', c=[XW - 0.12, cy, ZF + 0.45], s=[0.95, 0.14, 0.6], az=90.0, color=WK, e=0.12))   # back under the sill
    for s in (-1, 1): P.append(dict(k='box', c=[cx, cy + s * 0.44, ZF + 0.45], s=[0.1, 0.85, 0.32], az=90.0, color='#5c3f25', e=0.12))
    P.append(dict(k='box', c=[cx - 0.05, cy, ZF + 0.45], s=[0.8, 0.72, 0.1], az=90.0, color='#3f3a2c', e=0.1))        # cushion
    # table (front edge on display row 790, right end u 980), top z 2.78, 0.8 m deep
    e0, e1 = tab(-100, 790), tab(980, 790)
    tc = (e0 + e1) / 2 + np.array([0.4, 0, 0]); L = float(abs(e1[1] - e0[1]))
    P.append(dict(k='box', c=r2([tc[0], tc[1], ZF]), s=[L, 0.8, ZT - ZF], az=0.0, color='#6e5139', e=0.42))
    # on the table: back-projected contact points
    cup = tab(490, 765); P.append(dict(k='cyl', a=r2(cup), b=r2(cup + [0, 0, 0.10]), r=0.045, color='#b2262a'))
    P.append(dict(k='cyl', a=r2(cup + [0, 0, 0.10]), b=r2(cup + [0, 0, 0.11]), r=0.047, color='#efe9df'))
    P.append(dict(k='cyl', a=r2(cup + [0, 0, 0.11]), b=r2(cup + [0.0, 0.0, 0.21]), r=0.004, color='#d8b860'))
    bun = tab(430, 772); P.append(dict(k='blob', c=r2(bun + [0, 0, 0.035]), r=[0.06, 0.06, 0.035], color='#a8743c', smooth=True))
    P.append(dict(k='blob', c=r2(bun + [0, 0, 0.02]), r=[0.063, 0.063, 0.012], color='#5a3a22', smooth=True))
    pad = tab(720, 785); P.append(dict(k='blob', c=r2(pad + [0, 0, 0.022]), r=[0.07, 0.045, 0.022], color='#2a2a2d', smooth=True))
    for s in (-1, 1): P.append(dict(k='blob', c=r2(pad + [0.03, s * 0.05, 0.02]), r=[0.035, 0.03, 0.02], color='#c9c9c9', smooth=True))
    box = tab(645, 700); P.append(dict(k='box', c=r2(box), s=[0.2, 0.16, 0.07], az=0.0, color='#ece6da'))
    fr = tab(300, 705); P.append(dict(k='blob', c=r2(fr + [0, 0, 0.03]), r=[0.1, 0.08, 0.035], color='#c4883a'))
    bag = tab(60, 735); P.append(dict(k='blob', c=r2(bag + [0, 0, 0.06]), r=[0.1, 0.08, 0.07], color='#cdb48a'))
    # desk fan at the far left (display (60, 580))
    d = V.ray(60 * S, 580 * S); fc = V.o + d * (2.75 / d[0])                     # its small size puts it ~2.75 m ahead, by the wall
    P.append(dict(k='box', c=r2([fc[0], fc[1], ZF]), s=[0.5, 0.45, round(fc[2] - 0.2 - ZF, 2)], az=0.0, color='#5b4431', e=0.18))   # cabinet under it
    P.append(dict(k='cyl', a=r2(fc - [0, 0, 0.2]), b=r2(fc), r=0.012, color='#7d7f76'))
    P.append(dict(k='cyl', a=r2(fc + [0.02, 0, 0]), b=r2(fc - [0.02, 0, 0]), r=0.12, color='#8a8d84'))
    return dict(scene='T4/32 Napping in the Chair (Jason\'s House, Keys)', camera='Napping in the Chair', note=napping_room.__doc__.split('\n')[0], props=P)


def bayside_bridge():
    """T4/34 Explosion on the Highway — Lucia leaning out of a helicopter over the Bayside Dr bridge at night (pose fitted on the
    road lines, cameras.json BAYSIDE-HELI-V1). The bridge was only a V16 road stroke at 6 m: rebuilt as a divided deck on the V17
    road axis (az 274.7, centre y -1085 at x -520, shores x -622 / -414; past the W shore a smooth curve joins the V16 Bayside Dr
    road (Alexandre: « la route lead dans un building », « fit parfaitement avec la route plus loin »)): concrete deck (top 6.8, ESTIMATED), Jersey median
    0.61 m (fitted), yellow edge lines 2.18 m each side of it (fitted), dashed lane lines, white edge lines, parapets, piers every
    26 m. 22 m wide, not the 12.5 m V17 band: the wreck and the police cars back-project 8-10 m either side of the median (measured beats map).
    Back-projected from the frame (half-res px x 2) on the deck plane: the wreck (no explosion, Alexandre: « met pas l'explosion »), the police cars with their light bars on the right carriageway, the trees and blue-lit palms of the W shore (palms on the
    Four Ambassadors pool-deck podium, V16 box #626). Sizes ESTIMATED; Lucia and the helicopter are not modelled."""
    V = View('Explosion on the Highway'); P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    ZD = 6.8; A = np.array([-520.0, -1085.0]); az = math.radians(274.7)      # deck top 6.8: the V16 road ribbons render at 6.3-6.7 here
    d = np.array([math.sin(az), math.cos(az)]); n = np.array([d[1], -d[0]])                    # d: W along the bridge, n: right (N)
    at = lambda s, l, z: [A[0] + d[0] * s + n[0] * l, A[1] + d[1] * s + n[1] * l, z]
    s0, s1 = (-414.0 - A[0]) / d[0], (-622.0 - A[0]) / d[0]                                  # E and W shores
    AZ = round(math.degrees(az), 1); L = s1 - s0; sm = (s0 + s1) / 2
    quad = lambda p, col, e=None: P.append(dict(k='quad', p=[r2(q) for q in p], color=col, **({'e': e} if e is not None else {})))
    def lines(at_, sa, sb, z):                                                       # asphalt, yellow / white edge lines, dashes
        quad([at_(sa, -10.7, z + 0.02), at_(sb, -10.7, z + 0.02), at_(sb, 10.7, z + 0.02), at_(sa, 10.7, z + 0.02)], '#232427', 0.05)
        for l, col, w in ((-2.18, '#d6ad2c', 0.15), (2.18, '#d6ad2c', 0.15), (-10.2, '#d8d8d2', 0.13), (10.2, '#d8d8d2', 0.13)):
            quad([at_(sa, l - w / 2, z + 0.04), at_(sb, l - w / 2, z + 0.04), at_(sb, l + w / 2, z + 0.04), at_(sa, l + w / 2, z + 0.04)], col, 0.45)
    # 1) the bridge: one straight deck on the V17 axis between the shores
    P.append(dict(k='box', c=r2(at(sm, 0, ZD - 1.3)), s=[round(L, 1), 22.4, 1.3], az=AZ, color='#7d7b76'))                       # deck
    lines(at, s0, s1, ZD)
    P.append(dict(k='box', c=r2(at(sm, 0, ZD)), s=[round(L, 1), 0.6, 0.32], az=AZ, color='#9a978f'))                              # Jersey median
    P.append(dict(k='box', c=r2(at(sm, 0, ZD + 0.32)), s=[round(L, 1), 0.22, 0.29], az=AZ, color='#9a978f'))
    for l in (-5.9, 5.9):                                                                                     # dashed lane lines
        t = s0 + 2.0
        while t < s1 - 3.0:
            quad([at(t, l - 0.065, ZD + 0.04), at(t + 3.0, l - 0.065, ZD + 0.04), at(t + 3.0, l + 0.065, ZD + 0.04), at(t, l + 0.065, ZD + 0.04)], '#d8d8d2', 0.45); t += 12.0
    for l in (-10.95, 10.95):
        P.append(dict(k='box', c=r2(at(sm, l, ZD)), s=[round(L, 1), 0.35, 0.95], az=AZ, color='#8f8c85'))                         # parapets
    s = s0 + 13.0
    while s < s1 - 6:
        P.append(dict(k='box', c=r2(at(s, 0, -2.0)), s=[1.4, 18.0, ZD - 1.3 + 2.0], az=AZ, color='#6e6c68')); s += 26.0      # piers
    # 2) past the W shore the divided road joins the V16 Bayside Dr ribbon (14 m, drawn 0.34 above its points) that carries on to
    # the N-S avenue: a cubic Hermite curve tangent to the bridge axis at the W shore and to the V16 road at its point (-683.9,
    # -1050.5) (az 286), narrowing 22 -> 14 m, the median ending in a nose before the join, the level easing from the deck (6.8) to
    # the V16 ribbon (3.2 + 0.34); continuous quad strips (Alexandre: « que la route curve smoothly et fit parfaitement »)
    P0 = np.array(at(s1, 0, 0)[:2]); P1 = np.array([-683.9, -1050.5]); t1 = np.array([-11.5, 3.3]); t1 /= np.linalg.norm(t1)
    Lc = float(np.linalg.norm(P1 - P0)); M0, M1 = d * Lc, t1 * Lc; ZJ = 3.2 + 0.34 + 0.01
    TT = np.linspace(0, 1, 61)
    def hermite(t):
        h00, h10, h01, h11 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t, -2 * t**3 + 3 * t**2, t**3 - t**2
        dh = (6 * t**2 - 6 * t), (3 * t**2 - 4 * t + 1), (-6 * t**2 + 6 * t), (3 * t**2 - 2 * t)
        c = h00 * P0 + h10 * M0 + h01 * P1 + h11 * M1; tg = dh[0] * P0 + dh[1] * M0 + dh[2] * P1 + dh[3] * M1
        return c, tg / np.linalg.norm(tg)
    CC, NN = [], []
    for t in TT: c, tg = hermite(t); CC.append(c); NN.append(np.array([tg[1], -tg[0]]))
    ease = lambda t: 0.5 - 0.5 * math.cos(math.pi * t)
    ZC = [ZD + (ZJ - ZD) * ease(t) for t in TT]; HW = [10.7 + (7.0 - 10.7) * ease(t) for t in TT]
    pt = lambda i, l, dz=0.0: [CC[i][0] + NN[i][0] * l, CC[i][1] + NN[i][1] * l, ZC[i] + dz]
    def strip(lf, col, dz, e=None, i0=0, i1=len(TT) - 1):                     # lf(i) -> (l_left, l_right)
        for i in range(i0, i1):
            (a0, b0), (a1, b1) = lf(i), lf(i + 1)
            quad([pt(i, a0, dz), pt(i + 1, a1, dz), pt(i + 1, b1, dz), pt(i, b0, dz)], col, e)
    strip(lambda i: (-HW[i], HW[i]), '#232427', 0.02, 0.05)                                                     # asphalt
    IM = int(0.8 * (len(TT) - 1))                                                                                # median ends here
    for sg in (-1, 1):
        strip(lambda i: (sg * 2.18 - 0.075, sg * 2.18 + 0.075), '#d6ad2c', 0.04, 0.45, 0, IM)                  # yellow
        strip(lambda i: (sg * (HW[i] - 0.5) - 0.065, sg * (HW[i] - 0.5) + 0.065), '#d8d8d2', 0.04, 0.45)       # white edges
        for i in range(0, len(TT) - 1, 3):                                                                       # dashes
            l = lambda k: sg * (2.18 + HW[k] - 0.5) / 2
            quad([pt(i, l(i) - 0.065, 0.04), pt(i + 1, l(i + 1) - 0.065, 0.04), pt(i + 1, l(i + 1) + 0.065, 0.04), pt(i, l(i) + 0.065, 0.04)], '#d8d8d2', 0.45)
    for i in range(IM):                                                                                          # Jersey median: 2 faces + top
        for sg in (-1, 1):
            quad([pt(i, sg * 0.3, 0.0), pt(i + 1, sg * 0.3, 0.0), pt(i + 1, sg * 0.11, 0.61), pt(i, sg * 0.11, 0.61)], '#9a978f')
        quad([pt(i, -0.11, 0.61), pt(i + 1, -0.11, 0.61), pt(i + 1, 0.11, 0.61), pt(i, 0.11, 0.61)], '#a29f97')
    quad([pt(IM, -0.3, 0.0), pt(IM, 0.3, 0.0), pt(IM, 0.11, 0.61), pt(IM, -0.11, 0.61)], '#9a978f')              # nose
    for i in range(len(TT) - 1):                                                                                 # deck flanks while raised
        for sg in (-1, 1):
            g0, g1 = T(*pt(i, sg * HW[i])[:2]), T(*pt(i + 1, sg * HW[i + 1])[:2])
            if ZC[i] - g0 > 0.4 or ZC[i + 1] - g1 > 0.4:
                quad([pt(i, sg * HW[i], 0.02), pt(i + 1, sg * HW[i + 1], 0.02), [*pt(i + 1, sg * HW[i + 1])[:2], g1 - 0.5], [*pt(i, sg * HW[i])[:2], g0 - 0.5]], '#7d7b76')
    S2 = None
    # stops short of the join (curve sample 54 of 60): the V16 ribbon resumes under the curve's end (overlap, no gap)
    roadclear = [[r2(at(s0 - 4, -12.5, 0)[:2]), r2(at(s1, -12.5, 0)[:2])] + [r2(np.array(pt(i, -HW[i] - 1.5)[:2])) for i in range(0, 55, 6)] +
                 [r2(np.array(pt(i, HW[i] + 1.5)[:2])) for i in range(54, -1, -6)] + [r2(at(s1, 12.5, 0)[:2]), r2(at(s0 - 4, 12.5, 0)[:2])]]
    deck = lambda u, v, z=ZD: V.on_plane_z(u * 2, v * 2, z)
    w = deck(1000, 410); P.append(dict(k='box', c=r2(w), s=[4.4, 1.9, 1.2], az=AZ + 25, color='#1d1d1f'))                       # wreck
    # police cars on the right carriageway: body, white door panel, red / blue light bar
    for (u, v), a in (((1590, 362), 0), ((1730, 332), -8), ((1445, 252), 4)):
        q = deck(u, v)
        P.append(dict(k='box', c=r2(q), s=[4.9, 1.95, 1.05], az=AZ + 180 + a, color='#141416'))
        P.append(dict(k='box', c=r2(q + [0, 0, 1.05]), s=[2.4, 1.7, 0.42], az=AZ + 180 + a, color='#1a1a1c'))
        for sgn, col in ((-1, '#ff2a2a'), (1, '#2a5cff')):
            P.append(dict(k='glow', pts=[r2(q + [n[0] * sgn * 0.4, n[1] * sgn * 0.4, 1.55])], r=0.22, color=col, i=4.0, ball=True))
    # W shore left of the road: broadleaf trees back-projected from their trunk bases on the ground (z 4; the one at u 560 held
    # just N of the Four Ambassadors (N) tower, y -1096), crowns from their extents; two palms with the blue trunk uplights of the
    # frame (u 265 / 360) standing on the tower's pool-deck podium (V16 box #626, top 9.8: on the ground their rays end inside the tower)
    for (u, v), h, cr in (((560, 455), 10.0, 4.2), ((890, 335), 8.5, 3.6), ((1010, 310), 8.5, 3.4)):
        q = V.on_plane_z(u * 2, v * 2, 4.0)
        if u == 560: q = V.on_vplane(u * 2, v * 2, (0, -1096.0), (0, 1)); q[2] = T(q[0], q[1])
        P.append(dict(k='cyl', a=r2(q), b=r2(q + [0, 0, h * 0.6]), r=0.25, color='#4a3a2a'))
        for dx, dy, dz, k in ((0, 0, 0.72, 1.0), (1.2, 0.8, 0.62, 0.7), (-1.0, -0.9, 0.66, 0.75)):
            P.append(dict(k='blob', c=r2(q + [dx, dy, h * dz]), r=[round(cr * k, 2), round(cr * k, 2), round(cr * k * 0.65, 2)], color='#3d6a2c'))
    for u, v in ((265, 365), (360, 360)):
        q = V.on_plane_z(u * 2, v * 2, 9.8)
        P.append(dict(k='palm', a=r2(q), h=7.0, lean_az=0.0, lean=0.03))
        P.append(dict(k='glow', pts=[r2(q + [0.25, 0, 0.3]), r2(q + [0.25, 0, 3.8])], r=0.09, color='#3a5cff', i=2.5))
    return dict(scene='T4/34 Explosion on the Highway (Bayside Dr bridge)', camera='Explosion on the Highway', note=bayside_bridge.__doc__.split('\n')[0], props=P, roadclear=roadclear)


def _race_signs(prefix):
    """the three T4/37 overhead guide signs redrawn sharp (Florida green, white border): 'Shoreline / Amphitheater / Marina' with
    a left arrow; 'EAST TO' + I-397 shield + toll 1A shield + 'Port VC/Keys' + down arrow; 'West' + I-397 and I-97 shields (the junction
    with I-97) + down arrow, butted against the East panel (Alexandre, from a sharper view of the gantry)."""
    from PIL import Image, ImageDraw, ImageFont
    GRN, WHT, BLU, RED = (0, 106, 58), (246, 246, 240), (24, 52, 140), (190, 30, 40)
    F = '/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf'
    font = lambda s: ImageFont.truetype(F, s) if os.path.exists(F) else ImageFont.load_default()
    def panel(W, H):
        im = Image.new('RGB', (W, H), GRN); d = ImageDraw.Draw(im); d.rounded_rectangle([8, 8, W - 9, H - 9], radius=26, outline=WHT, width=8); return im, d
    def ctext(d, W, y, s, sz):
        f = font(sz); w = d.textlength(s, font=f); d.text(((W - w) / 2, y), s, font=f, fill=WHT)
    def interstate(d, x, y, s, num):
        d.rounded_rectangle([x, y + 0.18 * s, x + s, y + s], radius=int(0.25 * s), fill=BLU, outline=WHT, width=4)
        d.rectangle([x + 4, y + 0.18 * s + 4, x + s - 4, y + 0.36 * s], fill=RED)
        f = font(int(0.5 * s)); w = d.textlength(num, font=f); d.text((x + (s - w) / 2, y + 0.38 * s), num, font=f, fill=WHT)
    def down(d, cx, y, s):
        d.rectangle([cx - 0.09 * s, y, cx + 0.09 * s, y + 0.55 * s], fill=WHT); d.polygon([(cx - 0.32 * s, y + 0.5 * s), (cx + 0.32 * s, y + 0.5 * s), (cx, y + s)], fill=WHT)
    im, d = panel(700, 420)                                                   # Shoreline / Amphitheater / Marina, left arrow
    for k, s in enumerate(('Shoreline', 'Amphitheater', 'Marina')): ctext(d, 700, 30 + 92 * k, s, 92)
    d.rectangle([300, 330, 470, 352], fill=WHT); d.polygon([(230, 341), (310, 300), (310, 382)], fill=WHT)
    im.save(prefix + '_shoreline.png')
    im, d = panel(560, 560)                                                   # EAST TO I-397 / toll 1A / Port VC/Keys, down arrow
    f = font(80); d.text((40, 24), 'EAST', font=f, fill=WHT); d.text((380, 24), 'TO', font=f, fill=WHT)
    interstate(d, 60, 120, 150, '397')
    d.polygon([(380, 140), (470, 140), (490, 175), (470, 280), (425, 300), (380, 280), (360, 175)], fill=WHT)
    f2 = font(46); d.text((392, 178), 'TOLL', font=font(30), fill=GRN); d.text((400, 210), '1A', font=f2, fill=GRN)
    ctext(d, 560, 320, 'Port VC/Keys', 86); down(d, 280, 420, 120)
    im.save(prefix + '_east397.png')
    im, d = panel(620, 560)                                                   # West: I-397 + I-97 shields (junction), down arrow under 397
    d.text((40, 24), 'West', font=font(80), fill=WHT)
    interstate(d, 70, 130, 170, '397'); interstate(d, 330, 130, 170, '97'); down(d, 155, 360, 160)
    im.save(prefix + '_west397.png')


def catalan_race():
    """T4/37 Night Street Race — racing south on Catalan Blvd under the I-397 guide-sign gantry (pose ESTIMATED from Citigroup Center /
    100 Biscayne Blvd / Pegassi Towers, cameras.json CATALAN-RACE-V2). Dressing back-projected from the frame:
    the gantry ~42 m ahead (sign bottoms at 5.5 m clearance, ESTIMATED) with the three redrawn guide signs on it, the signal heads
    of the next intersection (~75 m), the street lights on the left kerb and lane dashes. No cars and no people (Alexandre). Sizes ESTIMATED."""
    V = View('Night Street Race'); P = []; r2 = lambda a: [round(float(v), 2) for v in a]; k = 1.92
    ZR = 3.34                                                              # V16 ribbon level (3.0 + 0.34) at the marker
    A = V.o[:2].copy(); az = math.radians(167.5); d = np.array([math.sin(az), math.cos(az)]); n = np.array([d[1], -d[0]])   # road frame on the camera, along Catalan Blvd
    at = lambda s, l, z: [A[0] + d[0] * s + n[0] * l, A[1] + d[1] * s + n[1] * l, z]
    d3, n3 = np.r_[d, 0.0], np.r_[n, 0.0]
    pre = os.path.join(THIS, 'threejs', '_prop_t437'); _race_signs(pre)
    SG = 42.0; G0 = np.array(at(SG, 0, 0)[:2])
    on_g = lambda u, v: V.on_vplane(u * k, v * k, G0, d)                     # the gantry plane (normal = road direction)
    for (u0, v0, u1, v1), img in (((1025, 250, 1200, 355), 'shoreline'), ((1215, 228, 1340, 362), 'east397'), ((1340, 228, 1488, 362), 'west397')):
        BL, BR, TR, TL = on_g(u0, v1), on_g(u1, v1), on_g(u1, v0), on_g(u0, v0)
        P.append(dict(k='tex', p=[r2(q) for q in (BL, BR, TR, TL)], img='_prop_t437_%s.png' % img))
        P.append(dict(k='box', c=r2((BL + BR) / 2 + d3 * 0.08), s=[round(float(np.linalg.norm(BR - BL)) + 0.2, 2), 0.12, round(float(TL[2] - BL[2]) + 0.2, 2)],
                      az=round(math.degrees(az) + 90, 1), color='#5d6468'))                                 # panel back
    zt = float(on_g(1215, 228)[2]) + 0.4
    for l in (-11.5, 12.5): P.append(dict(k='cyl', a=r2(at(SG + 0.5, l, ZR)), b=r2(at(SG + 0.5, l, zt + 0.6)), r=0.35, color='#8a9094'))   # posts
    for dz in (0.0, 0.9): P.append(dict(k='cyl', a=r2(at(SG + 0.5, -11.5, zt + dz)), b=r2(at(SG + 0.5, 12.5, zt + dz)), r=0.18, color='#8a9094'))   # truss chords
    # signal heads of the next intersection (green), back-projected on the plane 75 m ahead
    S2 = np.array(at(75.0, 0, 0)[:2])
    for u, v in ((1040, 470), (1160, 470), (1280, 470), (1205, 555)):
        q = V.on_vplane(u * k, v * k, S2, d)
        P.append(dict(k='box', c=r2(q - [0, 0, 0.55]), s=[0.4, 0.4, 1.1], az=round(math.degrees(az), 1), color='#1a1c1e'))
        P.append(dict(k='glow', pts=[r2(q - d3 * 0.25)], r=0.16, color='#36ff7a', i=3.0, ball=True))
    for s in (40.0, 75.0): P.append(dict(k='cyl', a=r2(at(s, -11.0, ZR + 5.6)), b=r2(at(s, 6.0, ZR + 5.6)), r=0.12, color='#2a2c2e'))   # mast arms
    # street lights on the left kerb (lamp heads at display (860, 150) / (1045, 150))
    for u in (860, 1045):
        q = V.on_vplane(u * k, 150 * k, at(0, -10.5, 0), n)
        P.append(dict(k='cyl', a=r2([q[0], q[1], ZR]), b=r2(q), r=0.14, color='#3a3d40'))
        P.append(dict(k='glow', pts=[r2(q)], r=0.35, color='#fff4d6', i=3.2, ball=True))
    for l in (-3.6, 3.6):                                                                                     # lane dashes
        for s in np.arange(4.0, 120.0, 12.0):
            P.append(dict(k='quad', p=[r2(at(s, l - 0.07, ZR + 0.03)), r2(at(s + 3, l - 0.07, ZR + 0.03)), r2(at(s + 3, l + 0.07, ZR + 0.03)), r2(at(s, l + 0.07, ZR + 0.03))], color='#d8d8d2', e=0.4))
    # no cars (Alexandre: « pas de voiture »)
    return dict(scene='T4/37 Night Street Race (Catalan Blvd)', camera='Night Street Race', note=catalan_race.__doc__.split('\n')[0], props=P)


def sea_balcony():
    """T4/39 Balcony at Sunset — a balcony of W South Beach over the sea (pose ESTIMATED, cameras.json SEA-BALCONY-V1c). The balcony
    is back-projected from the frame: its wooden handrail (rows 955 at the left, 2.7 m away, to 695 at the right, 8.6 m: it runs
    along the view, sea side on the left) on the plane 0.45 m below the eye, the glass railing under it, the floor slab, the
    white partition wall closing it on the right (u 1770), the translucent glass panels and the balcony above seen only in
    the top-right corner; below it the dark tree canopy and the palms of the frame, and the yacht / boats on the sea (Alexandre:
    « design plus comme la scene »). Lucia and Jason are not modelled. Sizes ESTIMATED."""
    V = View('Balcony at Sunset'); P = []; r2 = lambda a: [round(float(v), 2) for v in a]; k = 1.92
    ZE = float(V.o[2]); ZF = ZE - 1.6; ZR = ZE - 0.45
    R = np.array([V.on_plane_z(u * k, v * k, ZR)[:2] for u, v in ((50, 955), (300, 925), (600, 895), (880, 868), (1500, 748), (1700, 722), (1900, 695))])
    t = R[-1] - R[0]; t /= np.linalg.norm(t); a0 = R[0] - t * 4.0; a1 = V.on_plane_z(1770 * k, 960 * k, ZF)[:2]   # rail from the tower face to the wall
    a1 = a0 + t * float((a1 - a0) @ t); RL = [a0 + (a1 - a0) * s for s in np.linspace(0, 1, 12)]
    w = np.array([t[1], -t[0]]);  w = w if (V.o[:2] - a0) @ w > 0 else -w                                 # towards the inside of the balcony
    slab = [a0, a1, a1 + w * 4.2, a0 + w * 4.2]
    P.append(dict(k='prism', poly=[r2(q) for q in slab], z0=round(ZF - 0.3, 2), z1=round(ZF, 2), color='#d8cfc2', e=0.2))      # floor
    for i in range(len(RL) - 1):
        p, q = RL[i], RL[i + 1]
        P.append(dict(k='cyl', a=r2([*p, ZR]), b=r2([*q, ZR]), r=0.055, color='#8a623e'))                                         # wooden handrail
        P.append(dict(k='cyl', a=r2([*p, ZF + 0.06]), b=r2([*q, ZF + 0.06]), r=0.03, color='#9a9690'))
        P.append(dict(k='cyl', a=r2([*p, ZF]), b=r2([*p, ZR]), r=0.03, color='#9a9690'))
        P.append(dict(k='line', pts=[r2([*p, ZR - 0.08]), r2([*q, ZR - 0.08])], color='#e8e2da', opacity=0.5))
    wc = (a1 + a1 + w * 4.2) / 2 + t * 0.15
    P.append(dict(k='box', c=r2([wc[0], wc[1], ZF]), s=[4.4, 0.3, 3.0], az=round(math.degrees(math.atan2(w[0], w[1])), 1), color='#ece8e2'))   # partition (right)
    for i in range(len(RL) - 1):                                                                          # glass panels (translucent)
        p, q = RL[i], RL[i + 1]
        P.append(dict(k='quad', p=[r2([*p, ZF + 0.1]), r2([*q, ZF + 0.1]), r2([*q, ZR - 0.05]), r2([*p, ZR - 0.05])], color='#7f979c', e=0.15, opacity=0.35))
    # tree canopy just under the balcony (frame: a dense mass of palms and dark broadleaf trees up to rows ~690-800 on the left, tall
    # palms behind the rail on the right; Alexandre: « a plein de palms sur la vraie frame »)
    rng = np.random.default_rng(39)
    for u0, u1, v0, v1, n in ((0, 820, 700, 900, 34), (1440, 1800, 610, 700, 12)):
        for _ in range(n):
            u, v = rng.uniform(u0, u1), rng.uniform(v0, v1); zt = rng.uniform(10.5, 14.5)
            q = V.on_plane_z(u * k, v * k, zt)
            if np.hypot(*(q[:2] - V.o[:2])) > 250: continue
            if rng.random() < 0.6:
                P.append(dict(k='palm', a=r2([q[0], q[1], 2.0]), h=round(zt - 2.0, 1), lean_az=round(rng.uniform(0, 360), 0), lean=round(rng.uniform(0.03, 0.1), 2)))
            else:
                rr = rng.uniform(2.5, 3.8)
                P.append(dict(k='blob', c=r2(q - [0, 0, rr * 0.5]), r=[rr, rr * 0.9, rr * 0.65], color='#26321e'))
                P.append(dict(k='cyl', a=r2([q[0], q[1], 2.0]), b=r2(q - [0, 0, rr * 0.8]), r=0.3, color='#3b2f24'))
    # boats on the sea (yacht at display (380, 630), small boats)
    for (u, v), L, Wb in (((380, 632), 22.0, 6.0), ((300, 603), 8.0, 2.5), ((1560, 592), 10.0, 3.0), ((1765, 566), 14.0, 4.0)):
        q = V.on_plane_z(u * k, v * k, 0.3)
        P.append(dict(k='box', c=r2(q), s=[L, Wb, 2.2], az=60.0, color='#ece9e3'))
        P.append(dict(k='box', c=r2(q + [0, 0, 2.2]), s=[L * 0.45, Wb * 0.8, 1.6], az=60.0, color='#d8d4cc'))
    up = [a1 - t * 3.5, a1, a1 + w * 4.2, a1 - t * 3.5 + w * 4.2]                                         # balcony above, over the right part
    P.append(dict(k='prism', poly=[r2(q) for q in up], z0=round(ZF + 2.9, 2), z1=round(ZF + 3.2, 2), color='#5a5652'))
    return dict(scene='T4/39 Balcony at Sunset (W South Beach)', camera='Balcony at Sunset', note=sea_balcony.__doc__.split('\n')[0], props=P)


def _lattice_mast(P, x, y, z0, z1, w, col='#3b302c', az=0.0):
    """tower-crane mast: 4 chords, a tie ring every 4 m, X bracing (lines)."""
    a = math.radians(az); ex, ey = np.array([math.cos(a), -math.sin(a)]) * w / 2, np.array([math.sin(a), math.cos(a)]) * w / 2
    C = [np.array([x, y]) + sx * ex + sy * ey for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    r2 = lambda v: [round(float(t), 2) for t in v]
    for c in C: P.append(dict(k='cyl', a=r2([c[0], c[1], z0]), b=r2([c[0], c[1], z1]), r=0.16, color=col))
    z = z0
    while z < z1 - 0.1:
        zb = min(z + 4.0, z1)
        P.append(dict(k='line', pts=[r2([*C[i % 4], z]) for i in range(5)], color=col))
        for i in range(4):
            P.append(dict(k='line', pts=[r2([*C[i], z]), r2([*C[(i + 1) % 4], zb])], color=col))
            P.append(dict(k='line', pts=[r2([*C[(i + 1) % 4], z]), r2([*C[i], zb])], color=col))
        z = zb


def pegassi_terrace():
    """T4/36 Lucia on the Rooftop at Sunset — a terrace of 3 Tequesta Point (our 'Pegassi Towers', Alexandre) at 179.3 m, looking
    WNW over Brickell (pose fitted on the Southeast Financial Center, the Asia crane CC2 and the skyline, cameras.json
    PEGASSI-TERRACE-V1). Asia Brickell Key is still a construction site below the terrace in this frame: the tour cuts its solid at
    150 m for this scene (cut_solids) and its two tower cranes are built (right = landmark CC2, top 224.5, 4 m mast with the blue LED
    strip of the frame on its face; left = back-projected on the site at u 283, ~110 m, top 213.5). The curved terrace edge and glass
    railing are back-projected from the frame (rail top / floor edge rows), the planters on the left. Lucia is not modelled. ESTIMATED."""
    V = View('Lucia on the Rooftop at Sunset'); P = []; r2 = lambda a: [round(float(v), 2) for v in a]; k = 1.92
    ZF = float(V.o[2]) - 1.6
    # terrace edge: rail-top / floor-edge pixels back-projected, smoothed by a quadratic y(x)
    pts = [V.on_plane_z(u * k, v * k, ZF + 1.1)[:2] for u, v in ((0, 505), (460, 515), (900, 545), (1370, 592), (1700, 640), (2000, 700))]
    pts += [V.on_plane_z(u * k, v * k, ZF)[:2] for u, v in ((0, 690), (300, 705), (600, 735), (870, 760))]
    pts = np.array(pts); cf = np.polyfit(pts[:, 0], pts[:, 1], 2)
    XS = np.linspace(-48.0, -16.0, 24); EDGE = np.c_[XS, np.polyval(cf, XS)]
    floor = [r2(q) for q in EDGE] + [[-16.0, -918.0], [-48.0, -918.0]]
    P.append(dict(k='prism', poly=floor, z0=round(ZF - 0.45, 2), z1=round(ZF, 2), color='#5e4f4e', e=0.18))   # polished stone slab
    for i in range(len(EDGE) - 1):                                                                        # glass railing: rails + posts
        a, b = EDGE[i], EDGE[i + 1]
        P.append(dict(k='cyl', a=r2([*a, ZF + 1.1]), b=r2([*b, ZF + 1.1]), r=0.035, color='#c9c2bb'))
        P.append(dict(k='cyl', a=r2([*a, ZF + 0.08]), b=r2([*b, ZF + 0.08]), r=0.03, color='#8f8984'))
        P.append(dict(k='cyl', a=r2([*a, ZF]), b=r2([*a, ZF + 1.1]), r=0.025, color='#8f8984'))
        P.append(dict(k='line', pts=[r2([*a, ZF + 1.05]), r2([*b, ZF + 1.05])], color='#e9d8d0', opacity=0.5))
    for (u, v), rr in (((25, 420), 0.16), ((60, 600), 0.2), ((110, 780), 0.24), ((30, 880), 0.22), ((150, 920), 0.2)):   # planter leaves, left edge
        d = V.ray(u * k, v * k); q = V.o + d / np.linalg.norm(d) * 2.4
        P.append(dict(k='blob', c=r2(q), r=[rr * 1.4, rr, rr * 0.8], color='#22301c'))
    # the two tower cranes of the Asia Brickell Key site
    d = V.ray(283 * 2, 300 * 2); d = d / np.linalg.norm(d[:2]); L = V.o[:2] + d[:2] * 110.0
    for (x, y), top, w, led in (((-144.6, -855.8), 224.5, 4.0, True), ((float(L[0]), float(L[1])), 213.5, 3.2, False)):
        _lattice_mast(P, x, y, 4.4, top, w, az=24.0)
        P.append(dict(k='box', c=[x, y, top], s=[w + 0.6, w + 0.6, 3.0], az=24.0, color='#4a3c36'))      # slewing unit + cab
        jb = np.array([math.sin(math.radians(60)), math.cos(math.radians(60))])
        P.append(dict(k='cyl', a=r2([x - jb[0] * 18, y - jb[1] * 18, top + 3.5]), b=r2([x + jb[0] * 55, y + jb[1] * 55, top + 3.5]), r=0.6, color='#3b302c'))
        if led:                                                                                                   # blue LED strip facing the camera
            t = V.o[:2] - np.array([x, y]); t = t / np.linalg.norm(t)
            P.append(dict(k='glow', pts=[r2([x + t[0] * (w / 2 + 0.2), y + t[1] * (w / 2 + 0.2), 164.5]), r2([x + t[0] * (w / 2 + 0.2), y + t[1] * (w / 2 + 0.2), 196.0])], r=0.18, color='#4a54ff', i=3.0))
    return dict(scene='T4/36 Lucia on the Rooftop at Sunset (Pegassi Towers terrace)', camera='Lucia on the Rooftop at Sunset', note=pegassi_terrace.__doc__.split('\n')[0],
                props=P, cut_solids={'Asia Brickell Key': 150.0}, bare_roof=['Asia Brickell Key'])


def _obox(c, f, r, u, L, W, H, color):
    """oriented box (any attitude) as 6 quads: centre c, unit axes f / r / u, sizes L / W / H along them."""
    c, f, r, u = (np.asarray(a, float) for a in (c, f, r, u))
    q = lambda i, j, k: c + f * (i * L / 2) + r * (j * W / 2) + u * (k * H / 2)
    F = [((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)), ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)),
         ((-1, 1, -1), (-1, 1, 1), (1, 1, 1), (1, 1, -1)), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)),
         ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)), ((-1, -1, -1), (-1, 1, -1), (1, 1, -1), (1, -1, -1))]
    return [dict(k='quad', p=[[round(float(v), 2) for v in q(*ijk)] for ijk in face], color=color) for face in F]


def _biplane(V):
    """the T4/30 crop-duster biplane (Stearman type), back-projected from the frame: upper-wing span 1260 px -> ~49 m from the
    camera (9.8 m span, 15 deg of yaw); engine centre (1465, 915), upper wing row 745, lower wing 950, wheels 1095; the fuselage runs
    to the image left -> heading 0.5 (N up the beach), bank 0.9 deg left wing down (tips back-projected). The wing-walker and the
    pink smoke are left out (Alexandre: « enleve la fumee rouge et la personne sur l'aile »). Shapes and sizes ESTIMATED."""
    d = V.ray(1465, 915); d /= np.linalg.norm(d); P0 = V.o + d * 49.0
    az = math.radians(0.5); ph = math.radians(0.9)
    f = np.array([math.sin(az), math.cos(az), 0.0]); r = np.array([math.cos(az), -math.sin(az), 0.0]); z = np.array([0, 0, 1.0])
    r, z = r * math.cos(ph) + z * math.sin(ph), z * math.cos(ph) - r * math.sin(ph)
    W = lambda x, y, h: P0 + f * x + r * y + z * h; r2 = lambda a: [round(float(v), 2) for v in a]
    MAR, RED, SIL, DK = '#5a1c22', '#8a2630', '#c8c4bc', '#1d1a19'; B = []
    cyl = lambda a, b, rr, col: B.append(dict(k='cyl', a=r2(a), b=r2(b), r=rr, color=col))
    cyl(W(0.05, 0, 0), W(-0.75, 0, 0), 0.6, DK)                                    # cowl + radial engine
    cyl(W(0.12, 0, 0), W(0.0, 0, 0), 0.16, '#9a9a96')                              # hub
    cyl(W(-0.75, 0, 0), W(-4.6, 0, 0.12), 0.56, SIL)                               # forward fuselage (bare metal)
    cyl(W(-4.6, 0, 0.12), W(-7.0, 0, 0.35), 0.3, MAR)                              # tail cone
    B += _obox(W(-0.95, 0, 1.23), f, r, z, 1.55, 9.8, 0.16, MAR)                  # upper wing
    B += _obox(W(-1.05, 0, -0.25), f, r, z, 1.5, 9.4, 0.15, MAR)                  # lower wing
    for s in (-1, 1):
        B += _obox(W(-0.3, s * 4.85, 1.23), f, r, z, 0.35, 0.12, 0.17, RED)       # red wing-tip edges
        for x in (-0.55, -1.45): cyl(W(x, s * 3.7, -0.2), W(x, s * 3.7, 1.16), 0.045, DK)            # interplane struts
        cyl(W(-0.6, s * 0.35, 0.5), W(-0.7, s * 0.55, 1.16), 0.04, DK); cyl(W(-1.3, s * 0.35, 0.5), W(-1.2, s * 0.55, 1.16), 0.04, DK)   # cabane
        cyl(W(-0.7, s * 0.3, -0.45), W(-0.55, s * 1.05, -1.35), 0.07, MAR)       # gear legs
        B.append(dict(k='blob', c=r2(W(-0.55, s * 1.1, -1.35)), r=[0.13, 0.4, 0.4], az=round(math.degrees(math.atan2(r[0], r[1])), 1), color=DK, smooth=True))
    B += _obox(W(-6.55, 0, 0.38), f, r, z, 0.95, 3.3, 0.07, MAR)                  # tailplane
    B += _obox(W(-6.75, 0, 0.95), f, r, z, 1.05, 0.08, 1.15, MAR)                 # fin
    B.append(dict(k='blob', c=r2(W(-2.3, 0, 0.62)), r=[0.5, 0.45, 0.28], color='#2a2422', smooth=True))   # front cockpit + pilot
    cyl(W(-0.95, 0, 1.31), W(-0.95, 0, 2.7), 0.03, DK)                             # mast above the centre section
    return B


def beach_lifeguards():
    """Vice Beach lifeguard towers — V16 draws them as 30 m2 octagons every ~110 m along the sand (x 2110-2217); view3d
    extruded them as grey windowed boxes (Alexandre on T4/30: « les lifeguard tower c'est pas des buildings »). Rebuilt in
    the Miami Beach style: pastel cabin on four stilts, glass band, hipped roof in a second colour, deck with railing,
    ramp down to the sand on the land side, flag pole. #1542 = the white / pink-roof station of the T4/30 frame. Sizes ESTIMATED."""
    MS = json.load(open(os.path.join(THIS, 'threejs', '_v16_massing.json')))
    T8 = []
    for i, m in enumerate(MS):
        p = np.array(m['o'], float)
        A = 0.5 * abs(p[:, 0] @ np.roll(p[:, 1], 1) - p[:, 1] @ np.roll(p[:, 0], 1))
        if len(p) == 8 and 27 <= A <= 33 and m['z'] < 6: T8.append((i + 1, p.mean(0), m['z']))
    T8.sort(key=lambda t: t[1][1])
    PAL = [('#f6a9bd', '#5fc4d6'), ('#ffd166', '#ef6f8f'), ('#80d4c8', '#f7905f'), ('#c7aaf0', '#ffd166'),
           ('#a6e36f', '#f6a9bd'), ('#f7905f', '#80d4c8'), ('#7fb8f0', '#ffe08a')]
    P = []; clear = []; r2 = lambda a: [round(float(v), 2) for v in a]
    for j, (k, c, z0) in enumerate(T8):
        a, b = T8[max(0, j - 1)][1], T8[min(len(T8) - 1, j + 1)][1]
        t = (b - a) / max(1e-6, np.linalg.norm(b - a)); s = np.array([t[1], -t[0]])
        if s[0] < 0: s = -s                                              # seaward = east
        az = math.degrees(math.atan2(t[0], t[1]))
        body, roof = ('#f4f1ea', '#e88fa0') if k == 1542 else PAL[k % len(PAL)]
        L = lambda dt, ds, z: [c[0] + t[0] * dt + s[0] * ds, c[1] + t[1] * dt + s[1] * ds, z]
        zd = z0 + 2.1; zc = zd + 0.25; zr = zc + 2.6
        clear.append([r2(L(-5, -5, 0)[:2]), r2(L(5, -5, 0)[:2]), r2(L(5, 5, 0)[:2]), r2(L(-5, 5, 0)[:2])])
        for dt, ds in ((-1.7, -1.7), (1.7, -1.7), (1.7, 1.7), (-1.7, 1.7)):
            P.append(dict(k='cyl', a=r2(L(dt, ds, z0)), b=r2(L(dt, ds, zd)), r=0.12, color='#e6e1d6'))
        P.append(dict(k='box', c=r2(L(0, 0.4, zd)), s=[4.4, 5.2, 0.25], az=az, color='#d8cfbd'))          # deck (wider on the sea side)
        P.append(dict(k='box', c=r2(L(0, 0, zc)), s=[3.2, 3.2, 2.6], az=az, color=body))                    # cabin
        P.append(dict(k='box', c=r2(L(0, 0, zc + 1.05)), s=[3.26, 3.26, 0.85], az=az, color='#2c3a46'))     # glass band
        P.append(dict(k='box', c=r2(L(0, 0, zr)), s=[4.1, 4.1, 0.16], az=az, color=roof))                   # eave
        ap = L(0, 0, zr + 1.15); E4 = [L(-2.05, -2.05, zr + 0.16), L(2.05, -2.05, zr + 0.16), L(2.05, 2.05, zr + 0.16), L(-2.05, 2.05, zr + 0.16)]
        for q in range(4): P.append(dict(k='quad', p=[r2(E4[q]), r2(E4[(q + 1) % 4]), r2(ap), r2(ap)], color=roof))
        for q in range(4):                                                                                  # deck railing
            e0, e1 = [L(-2.2, -2.2, zd), L(2.2, -2.2, zd), L(2.2, 3.0, zd), L(-2.2, 3.0, zd)][q], [L(2.2, -2.2, zd), L(2.2, 3.0, zd), L(-2.2, 3.0, zd), L(-2.2, -2.2, zd)][q]
            if q == 0: e0 = L(-1.0, -2.2, zd)                                                               # gap for the ramp
            P.append(dict(k='cyl', a=r2([e0[0], e0[1], zd + 1.0]), b=r2([e1[0], e1[1], zd + 1.0]), r=0.04, color='#f4f2ee'))
            P.append(dict(k='cyl', a=r2([e0[0], e0[1], zd]), b=r2([e0[0], e0[1], zd + 1.0]), r=0.05, color='#f4f2ee'))
        bot0, bot1 = L(-2.2, -9.0, z0 + 0.05), L(-1.0, -9.0, z0 + 0.05); top0, top1 = L(-2.2, -2.2, zd + 0.12), L(-1.0, -2.2, zd + 0.12)
        P.append(dict(k='quad', p=[r2(bot0), r2(bot1), r2(top1), r2(top0)], color='#d8cfbd'))                  # ramp to the land side
        for e in (bot0, bot1):
            tp = top0 if e is bot0 else top1
            P.append(dict(k='cyl', a=r2([e[0], e[1], e[2] + 0.9]), b=r2([tp[0], tp[1], tp[2] + 0.9]), r=0.04, color='#f4f2ee'))
        P.append(dict(k='cyl', a=r2(ap), b=r2([ap[0], ap[1], ap[2] + 2.4]), r=0.04, color='#d8d8d8'))         # flag pole + flag
        P.append(dict(k='box', c=r2([ap[0] + t[0] * 0.5, ap[1] + t[1] * 0.5, ap[2] + 1.8]), s=[0.9, 0.04, 0.55], az=az, color='#e8c040' if j % 2 else '#d84040'))
    return dict(scene='Vice Beach lifeguard towers', camera='Biplane over the Beach', note=beach_lifeguards.__doc__.split('\n')[0], props=P, clear=clear)


def _offset(P, d):
    """polygon P (n x 2) offset outward by d (miter, clamped)."""
    P = np.asarray(P, float); n = len(P); A = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]); sg = 1 if A > 0 else -1
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        e0 = (b - a) / max(1e-9, np.linalg.norm(b - a)); e1 = (c - b) / max(1e-9, np.linalg.norm(c - b))
        n0 = sg * np.array([e0[1], -e0[0]]); n1 = sg * np.array([e1[1], -e1[0]]); m = n0 + n1
        k = d / max(0.35, (m @ n0) / max(1e-9, np.linalg.norm(m))) if np.linalg.norm(m) > 1e-9 else d
        out.append(b + (m / max(1e-9, np.linalg.norm(m))) * min(k, 3 * d))
    return np.array(out)


def portofino_detail():
    """Portofino Tower — Alexandre's favourite building (« portofino 0 comme irl... je veux plus de detail »). Detail on the
    measured Y solid (tools/mesh_solids.py, PORTOFINO-V2), after the IRL tower and the T4/30 frame: a white balcony slab every
    floor (3.2 m) wrapping the facade with its railing line, terracotta pilasters on the corners of the Y, terracotta cornice bands
    at the shoulder (126 m) and the roof (141.6 m), and the BREAK (Alexandre: « manque le break dans la tour »): two open floors
    z 86.5-93.7 MEASURED on T4/30 (frame rows 165 / 118 on the facade plane), dark recess behind terracotta piers, no balconies,
    a cornice above and below. The facade shader does the blue-grey glass ribbons. Slab depth ESTIMATED 1.4 m."""
    import mesh_solids
    so = mesh_solids.cached()['Portofino Tower']; P = []; r2 = lambda a: [round(float(v), 2) for v in a]
    main = [L for L in so['layers'] if L['z1'] - L['z0'] > 50][0]; crown = [L for L in so['layers'] if 10 < L['z1'] - L['z0'] < 50][0]
    O = np.array(main['polys'][0]['outer'], float)[:, :2]; OC = np.array(crown['polys'][0]['outer'], float)[:, :2]
    if np.allclose(O[0], O[-1]): O = O[:-1]
    if np.allclose(OC[0], OC[-1]): OC = OC[:-1]
    S1 = _offset(O, 1.4); RL = _offset(O, 1.32)
    B0, B1 = 86.5, 93.7                         # the break: 2 open terracotta floors (T4/30 rows 165 / 118 on the facade plane)
    z = main['z0'] + 3.2 * 2
    while z < main['z1'] - 1.0:
        if not (B0 - 0.5 < z < B1 + 0.5):
            P.append(dict(k='prism', poly=[r2(q) for q in S1], z0=round(z - 0.22, 2), z1=round(z, 2), color='#eeeae2'))
            P.append(dict(k='line', pts=[r2([q[0], q[1], z + 1.05]) for q in list(RL) + [RL[0]]], color='#f6f4f0'))
        z += 3.2
    P.append(dict(k='prism', poly=[r2(q) for q in _offset(O, 0.12)], z0=B0, z1=B1, color='#3a2a26'))      # dark recess behind the piers
    for zz in (B0, B1):                                                                                     # cornices of the break
        P.append(dict(k='prism', poly=[r2(q) for q in _offset(O, 1.1)], z0=round(zz - 0.55, 2), z1=round(zz + 0.15, 2), color='#b8664f'))
    PO = _offset(O, 0.6); acc = 0.0
    for i in range(len(PO)):                                                                                # terracotta piers every ~5.5 m
        a, b = PO[i], PO[(i + 1) % len(PO)]; L = float(np.linalg.norm(b - a)); az = math.degrees(math.atan2(*(b - a)))
        s = (5.5 - acc) % 5.5
        while s < L:
            q = a + (b - a) * s / L; P.append(dict(k='box', c=r2([q[0], q[1], B0]), s=[1.5, 1.0, round(B1 - B0, 2)], az=round(az, 1), color='#b8664f')); s += 5.5
        acc = (acc + L) % 5.5
    for Ls, zz, d in ((O, main['z1'], 1.9), (OC, crown['z1'], 1.6)):                                       # cornice bands
        P.append(dict(k='prism', poly=[r2(q) for q in _offset(Ls, d)], z0=round(zz - 1.6, 2), z1=round(zz + 0.2, 2), color='#b8664f'))
    # the terracotta diagonal down the central wing (T4/30 frame, full-res pixels: (3365, 165) -> (3300, 400), ~26 px wide),
    # back-projected on the facade: 2D ray / footprint intersection, 1.7 m proud (in front of the balcony slabs)
    V = View('Biplane over the Beach')
    def on_face(u, v):
        d = V.ray(u, v); best = None
        for i in range(len(O)):
            a, b = O[i], O[(i + 1) % len(O)]; M2 = np.array([[d[0], a[0] - b[0]], [d[1], a[1] - b[1]]])
            if abs(np.linalg.det(M2)) < 1e-9: continue
            t, s = np.linalg.solve(M2, a - V.o[:2])
            if t > 0 and 0 <= s <= 1 and (best is None or t < best): best = t
        return V.o + d * (best - 1.7 / np.linalg.norm(d[:2]))
    for (ua, va), (ub, vb) in (((3365, 165), (3300, 400)), ((3462, 232), (3478, 300))):
        Q = [on_face(ua - 13, va), on_face(ua + 13, va), on_face(ub + 13, vb), on_face(ub - 13, vb)]
        P.append(dict(k='quad', p=[r2(q) for q in Q], color='#b25a45'))
    n = len(O)
    for i in range(n):                                                                                       # pilasters on the sharp corners
        a, b, c = O[i - 1], O[i], O[(i + 1) % n]
        e0, e1 = (b - a) / np.linalg.norm(b - a), (c - b) / np.linalg.norm(c - b)
        if math.degrees(math.acos(np.clip(e0 @ e1, -1, 1))) < 35: continue
        q = _offset(O, 0.5)[i]; az = math.degrees(math.atan2(*(e0 + e1)[::1]))
        P.append(dict(k='box', c=r2([q[0], q[1], main['z0']]), s=[1.8, 1.8, round(main['z1'] - main['z0'] - 0.4, 2)], az=round(az, 1), color='#b8664f'))
    return dict(scene='Portofino Tower detail', camera='Biplane over the Beach', note=portofino_detail.__doc__.split('\n')[0], props=P)


SCENES = [keys_entrance, brians_marina, keys_landmarks, keys_bridges, seaplane_dock, radio_towers, skyline_night, aviation_lights, brickell_metromover, ferris_marina, arsht_night, convertible_bridge, iguana_roundabout, runway_jet, red_car_terminal, green_car_edison, bike_viaduct, rooftop_explosion, beach_biplane, beach_lifeguards, portofino_detail, napping_room, bayside_bridge, pegassi_terrace, catalan_race, sea_balcony]


def main():
    out = dict(_doc=__doc__.split('\n')[0] + ' Generated by tools/scene_props.py; positions ESTIMATED from the frames.', scenes=[f() for f in SCENES])
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    for s in out['scenes']: print(s['scene'], len(s['props']), 'props')


if __name__ == '__main__':
    main()
