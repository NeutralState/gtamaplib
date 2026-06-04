#!/usr/bin/env python3
"""
Install PortofinoTower class into gtamaplib.py and update extract_mesh_edges.py.

Run this from ~/Downloads/gtamaplib-main/
"""
import os
import shutil

REPO = os.path.expanduser('~/Downloads/gtamaplib-main')

# ── Patch 1: Add PortofinoTower class to gtamaplib.py ──
GTAMAPLIB = os.path.join(REPO, 'gtamaplib.py')
BACKUP_GTAMAPLIB = GTAMAPLIB + '.bak_portofino_class'
shutil.copy(GTAMAPLIB, BACKUP_GTAMAPLIB)
print(f'Backup: {BACKUP_GTAMAPLIB}')

with open(GTAMAPLIB) as f:
    c = f.read()

# Anchor: end of SunshineSkywayBridge class (look for next ### marker)
anchor = '''### AIWE ##########################################################################################

class AIWE:'''

portofino_class_code = '''### PORTOFINO TOWER ###############################################################################

class PortofinoTower(Landmark):
    """3-branched trifoliate skyscraper (NW, NE, S branches with peak boxes)."""

    Z_PEAK_TOP  = 143.0
    Z_CYL_TOP   = 137.0
    Z_PENT_TOP  = 125.0
    Z_BREAK_TOP = 85.0
    Z_BASE_TOP  = 75.0
    Z_GROUND    = 0.0
    SIDE_FRONT_BASE = 11.2
    R_CYLINDER_BASE = 8.87
    PEAK_BOX_SIDE   = 8.5

    def __init__(
        self,
        nw=(-1106.6, -1543.0, 143.0),
        ne=(-1075.5, -1551.0, 143.0),
        s =(-1085.0, -1583.0, 143.0),
    ):
        super().__init__('Portofino Tower')
        # Try to pull from md.landmarks if available (real calibrated anchors)
        try:
            import gtamapdata as _md
            if 'Portofino Tower (NW)' in _md.landmarks:
                nw = _md.landmarks['Portofino Tower (NW)']
            if 'Portofino Tower (NE)' in _md.landmarks:
                ne = _md.landmarks['Portofino Tower (NE)']
            if 'Portofino Tower (S)' in _md.landmarks:
                s  = _md.landmarks['Portofino Tower (S)']
        except Exception:
            pass
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

    def _which_branch_hidden(self, cam_xy):
        cam_xy = np.array(cam_xy[:2])
        cam_dir = cam_xy - self.centroid_xy
        cam_dist = np.linalg.norm(cam_dir)
        if cam_dist < 1e-6:
            return None
        cam_unit = cam_dir / cam_dist
        best_branch = None
        best_dot = -2.0
        for br_name, peak in self.branch_peaks.items():
            branch_dir = peak[:2] - self.centroid_xy
            branch_unit = branch_dir / np.linalg.norm(branch_dir)
            dot = -np.dot(cam_unit, branch_unit)
            if dot > best_dot:
                best_dot = dot
                best_branch = br_name
        return best_branch

    def render_on_camera(self, cam):
        color = self.color
        thin = 0.5
        bold = 1.0
        hidden_branch = self._which_branch_hidden(cam.xy)

        # Cylinder
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

        # Pentagons
        pent_codes = [code for code, _, _ in self.PENT_LEVELS]
        pent_corners = ['frontL', 'frontR', 'innerR', 'innerL']
        for br_name in ('NW', 'NE', 'S'):
            is_hidden = (br_name == hidden_branch)
            for corner in pent_corners:
                if is_hidden and corner.startswith('front'):
                    continue
                for j in range(len(pent_codes) - 1):
                    p1 = self.pent[(pent_codes[j],     br_name, corner)]
                    p2 = self.pent[(pent_codes[j + 1], br_name, corner)]
                    cam.render_line((p1, p2), color, bold if corner.startswith('front') else thin)
            for code in pent_codes:
                for k in range(4):
                    a = pent_corners[k]
                    b = pent_corners[(k + 1) % 4]
                    if is_hidden and a.startswith('front') and b.startswith('front'):
                        continue
                    p1 = self.pent[(code, br_name, a)]
                    p2 = self.pent[(code, br_name, b)]
                    cam.render_line((p1, p2), color, thin)

        # Peak boxes
        pbox_codes = [code for code, _ in self.PEAK_BOX_LEVELS]
        pbox_corners = ['pbOL', 'pbOR', 'pbIR', 'pbIL']
        for br_name in ('NW', 'NE', 'S'):
            is_hidden = (br_name == hidden_branch)
            for corner in pbox_corners:
                if is_hidden and corner.startswith('pbO'):
                    continue
                p1 = self.pbox[('PB', br_name, corner)]
                p2 = self.pbox[('PT', br_name, corner)]
                cam.render_line((p1, p2), color, bold)
            for code in pbox_codes:
                for k in range(4):
                    a = pbox_corners[k]
                    b = pbox_corners[(k + 1) % 4]
                    if is_hidden and a.startswith('pbO') and b.startswith('pbO'):
                        continue
                    p1 = self.pbox[(code, br_name, a)]
                    p2 = self.pbox[(code, br_name, b)]
                    cam.render_line((p1, p2), color, bold)

        return self


'''

if anchor not in c:
    print('ERROR: anchor not found in gtamaplib.py')
    raise SystemExit(1)

c = c.replace(anchor, portofino_class_code + anchor, 1)
with open(GTAMAPLIB, 'w') as f:
    f.write(c)
print('  → class PortofinoTower inserted into gtamaplib.py before AIWE')

# ── Patch 2: Update extract_mesh_edges.py to include PortofinoTower ──
EXTRACT = os.path.join(REPO, 'tools', 'extract_mesh_edges.py')
BACKUP_EXTRACT = EXTRACT + '.bak_portofino'
shutil.copy(EXTRACT, BACKUP_EXTRACT)
print(f'Backup: {BACKUP_EXTRACT}')

with open(EXTRACT) as f:
    e = f.read()

# Insert Portofino extraction before SunshineSkywayBridge section
anchor2 = "print('Extracting Sunshine Skyway Bridge edges...')"

portofino_extract = '''print('Extracting Portofino Tower edges (5 viewpoint passes for pentagonal coverage)...')
pt_edges = []
pt_seen = set()
try:
    for vp_name, vp in [('NE', (99999, 99999)), ('NW', (-99999, 99999)),
                        ('SW', (-99999, -99999)), ('SE', (99999, -99999)),
                        ('N',  (0, 99999))]:
        instance = ml.PortofinoTower()
        fake = FakeCam(xy=vp)
        try:
            instance.render_on_camera(fake)
        except Exception as ex:
            print(f'  pass {vp_name} failed: {ex}')
            continue
        added = 0
        for edge in fake.edges:
            key = tuple(sorted([tuple(edge[0]), tuple(edge[1])]))
            if key not in pt_seen:
                pt_seen.add(key)
                pt_edges.append(edge)
                added += 1
        print(f'  pass {vp_name}: +{added} edges (total {len(pt_edges)})')
except Exception as ex:
    print(f'  FAILED: {ex}')
    import traceback
    traceback.print_exc()
print(f'  → {len(pt_edges)} total unique edges')

'''

if anchor2 in e:
    e = e.replace(anchor2, portofino_extract + anchor2, 1)
    print('  → PortofinoTower extraction added to extract_mesh_edges.py')

# Also add to the result dict at the end
anchor3 = "if fs_edges:\n    result['Four Seasons Hotel Miami'] = {"
portofino_result = """if pt_edges:
    result['Portofino Tower'] = {
        'color': '#ff9d3d',
        'world_edges': pt_edges,
    }
"""

if anchor3 in e:
    e = e.replace(anchor3, portofino_result + anchor3, 1)
    print('  → Portofino added to result dict')

with open(EXTRACT, 'w') as f:
    f.write(e)

print('\\nDone. Now run:')
print('  cd ~/Downloads/gtamaplib-main && python3 tools/extract_mesh_edges.py')
