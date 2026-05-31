"""
PortofinoTower.py — standalone trifoliate tower mesh (cylinder + 3 radial wings).
Adapted from install_portofino_class.py but kept OUT of the vendored gtamaplib.py.
Anchored on real LMs Portofino Tower (NW)/(NE)/(S). Scale calibrated to measured
geometry: dist centroid->wing-peak = 18m, cylinder box ~485px ~= 36m diam (R~18m),
height z_top ~= 142.
"""
import math
import numpy as np


class PortofinoTower:
    color = '#a78bfa'  # violet, distinct from other meshes

    # Heights (m) — z_top matches real peaks (~142)
    Z_PEAK_TOP  = 142.0
    Z_CYL_TOP   = 137.0
    Z_PENT_TOP  = 125.0
    Z_BREAK_TOP = 85.0
    Z_BASE_TOP  = 75.0
    Z_GROUND    = 0.0

    # Scale (m) — calibrated to satellite reference (1px ~= 0.074m)
    R_CYLINDER_BASE = 18.0    # cylinder radius (485px box -> ~36m diam -> R~18)
    SIDE_FRONT_BASE = 9.7     # outer (yellow) square side: 131px*0.074
    PEAK_BOX_SIDE   = 8.6     # inner (green) square side: 116px*0.074

    def __init__(self, md, ml=None):
        self.md = md
        self.ml = ml
        nw = md.landmarks['Portofino Tower (NW)']
        ne = md.landmarks['Portofino Tower (NE)']
        s  = md.landmarks['Portofino Tower (S)']
        self.nw = np.array(nw, dtype=float)
        self.ne = np.array(ne, dtype=float)
        self.s  = np.array(s,  dtype=float)
        self.centroid_xy = (self.nw[:2] + self.ne[:2] + self.s[:2]) / 3
        self.branch_peaks = {'NW': self.nw, 'NE': self.ne, 'S': self.s}

        self.PENT_LEVELS = [
            ('B', self.Z_GROUND,    1.7),
            ('K', self.Z_BASE_TOP,  1.6),
            ('L', self.Z_BREAK_TOP, 1.0),
            ('P', self.Z_PENT_TOP,  1.0),
        ]
        self.CYL_LEVELS = [
            ('B',  self.Z_GROUND,    1.7),
            ('K',  self.Z_BASE_TOP,  1.6),
            ('L',  self.Z_BREAK_TOP, 1.0),
            ('P',  self.Z_PENT_TOP,  1.0),
            ('CT', self.Z_CYL_TOP,   1.0),
        ]
        self.PEAK_BOX_LEVELS = [('PB', self.Z_PENT_TOP), ('PT', self.Z_PEAK_TOP)]

        self.pent = {}
        self.cyl  = {}
        self.pbox = {}
        self._build_geometry()

    def _pentagon(self, peak_xyz, z, scale=1.0):
        peak_xy = peak_xyz[:2]
        radial = peak_xy - self.centroid_xy
        radial_len = np.linalg.norm(radial)
        radial_unit = radial / radial_len
        perp = np.array([-radial_unit[1], radial_unit[0]])
        radial_outward = (scale - 1.0) * radial_len * 0.3
        side_front = self.SIDE_FRONT_BASE * scale
        inner_radius = self.R_CYLINDER_BASE * scale
        inner_half = side_front * 0.75
        peak_pos_xy = self.centroid_xy + radial_unit * (radial_len + radial_outward)
        front_half = side_front / 2
        front_L = peak_pos_xy + perp * front_half
        front_R = peak_pos_xy - perp * front_half
        inner_pos = self.centroid_xy + radial_unit * inner_radius
        inner_L = inner_pos + perp * inner_half
        inner_R = inner_pos - perp * inner_half
        return {
            'frontL': (front_L[0], front_L[1], z),
            'frontR': (front_R[0], front_R[1], z),
            'innerL': (inner_L[0], inner_L[1], z),
            'innerR': (inner_R[0], inner_R[1], z),
        }

    def _peak_box(self, peak_xyz, z):
        peak_xy = peak_xyz[:2]
        radial = peak_xy - self.centroid_xy
        radial_unit = radial / np.linalg.norm(radial)
        perp = np.array([-radial_unit[1], radial_unit[0]])
        half = self.PEAK_BOX_SIDE / 2
        outer = peak_xy + radial_unit * half
        inner = peak_xy - radial_unit * half
        return {
            'pbOL': (outer[0] + perp[0]*half, outer[1] + perp[1]*half, z),
            'pbOR': (outer[0] - perp[0]*half, outer[1] - perp[1]*half, z),
            'pbIL': (inner[0] + perp[0]*half, inner[1] + perp[1]*half, z),
            'pbIR': (inner[0] - perp[0]*half, inner[1] - perp[1]*half, z),
        }

    def _cylinder(self, z, scale=1.0):
        R = self.R_CYLINDER_BASE * scale
        pts = {}
        for i in range(8):
            a = i * math.pi / 4
            x = self.centroid_xy[0] + R * math.cos(a)
            y = self.centroid_xy[1] + R * math.sin(a)
            pts[f'cyl{i}'] = (x, y, z)
        return pts

    def _build_geometry(self):
        for code, z, scale in self.PENT_LEVELS:
            for br_name, peak in self.branch_peaks.items():
                for c_name, xyz in self._pentagon(peak, z, scale).items():
                    self.pent[(code, br_name, c_name)] = xyz
        for code, z, scale in self.CYL_LEVELS:
            for c_name, xyz in self._cylinder(z, scale).items():
                self.cyl[(code, c_name)] = xyz
        for code, z in self.PEAK_BOX_LEVELS:
            for br_name, peak in self.branch_peaks.items():
                for c_name, xyz in self._peak_box(peak, z).items():
                    self.pbox[(code, br_name, c_name)] = xyz

    def render_on_camera(self, cam):
        color = self.color
        thin = 0.5
        bold = 1.0

        cyl_codes = [code for code, _, _ in self.CYL_LEVELS]
        for i in range(8):
            for j in range(len(cyl_codes) - 1):
                c1 = self.cyl[(cyl_codes[j],     f'cyl{i}')]
                c2 = self.cyl[(cyl_codes[j + 1], f'cyl{i}')]
                cam.render_line((c1, c2), color, thin)
        for code in cyl_codes:
            for i in range(8):
                c1 = self.cyl[(code, f'cyl{i}')]
                c2 = self.cyl[(code, f'cyl{(i + 1) % 8}')]
                cam.render_line((c1, c2), color, thin)

        pent_codes = [code for code, _, _ in self.PENT_LEVELS]
        pent_corners = ['frontL', 'frontR', 'innerR', 'innerL']
        for br_name in ('NW', 'NE', 'S'):
            for corner in pent_corners:
                for j in range(len(pent_codes) - 1):
                    p1 = self.pent[(pent_codes[j],     br_name, corner)]
                    p2 = self.pent[(pent_codes[j + 1], br_name, corner)]
                    cam.render_line((p1, p2), color, bold if corner.startswith('front') else thin)
            for code in pent_codes:
                for k in range(4):
                    a = pent_corners[k]; b = pent_corners[(k + 1) % 4]
                    p1 = self.pent[(code, br_name, a)]
                    p2 = self.pent[(code, br_name, b)]
                    cam.render_line((p1, p2), color, thin)

        pbox_corners = ['pbOL', 'pbOR', 'pbIR', 'pbIL']
        for br_name in ('NW', 'NE', 'S'):
            for corner in pbox_corners:
                p1 = self.pbox[('PB', br_name, corner)]
                p2 = self.pbox[('PT', br_name, corner)]
                cam.render_line((p1, p2), color, bold)
            for code in [c for c, _ in self.PEAK_BOX_LEVELS]:
                for k in range(4):
                    a = pbox_corners[k]; b = pbox_corners[(k + 1) % 4]
                    p1 = self.pbox[(code, br_name, a)]
                    p2 = self.pbox[(code, br_name, b)]
                    cam.render_line((p1, p2), color, bold)
        return self
