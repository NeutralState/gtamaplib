"""
HomesteadWaterTower.py — standalone port of rlx's HomesteadWaterTower
(rolux/gtamaplib gtamaplib.py, commit c1d3c4a), kept OUT of the vendored lib.

rlx's class derives the tower SHAPE at runtime from 6 corner markings
(L1..R3) on his Grassrivers 02 (Watson Bay) pixels — markings we do not
have. Shape scalars are referential-independent, so they were computed once
in his repo (2026-06-10 sandbox session) and hardcoded here with provenance:

    r1 (shaft radius) = 6.0508 m
    r2 (tank radius)  = 8.2477 m
    ring offsets below top: d1=16.398, d2=13.934, d3=3.266 m
    (his absolute z: top 70.083, rings 53.685/56.149/66.817, ground 5.0)

The tower CENTER comes from OUR landmark 'Homestead Water Tower' (top of
tower) — our referential diverges from rlx's by ~10 m xy / 1.5 m z here,
which is exactly why ring heights are stored as offsets from the LM top,
not absolute z. Ground elevation (~5 m, grassrivers terrain) stays an
absolute tunable.
"""
import math


class HomesteadWaterTower:
    color = '#4373a2'  # rlx's RGB (67,115,162)

    R_SHAFT = 6.0508
    R_TANK = 8.2477
    # offsets below the LM top (z4): shaft top, tank bottom, tank top
    D_SHAFT_TOP = 16.398
    D_TANK_BOT = 13.934
    D_TANK_TOP = 3.266
    Z_GROUND = 5.0      # terrain elevation (absolute, grassrivers)
    STEP_DEG = 15

    def __init__(self, md, ml=None):
        self.md = md
        t = md.landmarks['Homestead Water Tower']
        self.cx, self.cy, self.z_top = float(t[0]), float(t[1]), float(t[2])

    def _ring(self, z, r):
        pts = []
        for deg in range(0, 360, self.STEP_DEG):
            a = math.radians(deg)
            pts.append((self.cx + r * math.cos(a), self.cy + r * math.sin(a), z))
        return pts

    def render_on_camera(self, cam, width=0.25):
        zs = (
            self.Z_GROUND,                  # z0 ground
            self.z_top - self.D_SHAFT_TOP,  # z1 shaft top
            self.z_top - self.D_TANK_BOT,   # z2 tank bottom
            self.z_top - self.D_TANK_TOP,   # z3 tank top
            self.z_top,                     # z4 apex
        )
        radii = (self.R_SHAFT, self.R_SHAFT, self.R_TANK, self.R_TANK, 0.0)
        rings = [self._ring(z, r) for z, r in zip(zs, radii)]
        n = len(rings[0])
        for level in range(4):
            ring, nxt = rings[level], rings[level + 1]
            for i in range(n):
                # horizontal ring segment
                cam.render_line((ring[i], ring[(i + 1) % n]), self.color, width)
                # vertical/slanted connector to next level (apex collapses to center)
                top = nxt[i] if radii[level + 1] > 0 else (self.cx, self.cy, zs[level + 1])
                cam.render_line((ring[i], top), self.color, width)
        return self
