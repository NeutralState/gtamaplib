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
A scene may also list 'clear' polygons [[x,y]...]: view3d does not extrude the V16 massing footprints whose centroid falls
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


SCENES = [keys_entrance]


def main():
    out = dict(_doc=__doc__.split('\n')[0] + ' Generated by tools/scene_props.py; positions ESTIMATED from the frames.', scenes=[f() for f in SCENES])
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    for s in out['scenes']: print(s['scene'], len(s['props']), 'props')


if __name__ == '__main__':
    main()
