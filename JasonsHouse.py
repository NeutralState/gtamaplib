"""
JasonsHouse.py — modele procedural de la maison de Jason (Keys).
Extrait verbatim de rlx upstream/main gtamaplib.py lignes 1838-1977
(doctrine: on ne touche pas notre gtamaplib.py vendore). Ancre sur les
LMs Jason's House importes le 2026-07-13 (gate House (Keys) 1.26').
"""
import numpy as np
import gtamapdata as md
from gtamaplib import Landmark

class JasonsHouse(Landmark):

    def __init__(self, offset=(0, 0)):
        super().__init__("Jason's House")
        self.base_ne = md.landmarks["Jason's House (Main) (BNE)"]
        self.top_se = md.landmarks["Jason's House (Main) (TSE)"]
        self.top_sw = md.landmarks["Jason's House (Main) (TSW)"]
        self.top_ne = md.landmarks["Jason's House (Main) (TNE)"]
        self.roof_se = md.landmarks["Jason's House (Roof) (SE)"]
        self.roof_s = md.landmarks["Jason's House (Roof) (S)"]
        self.roof_sw = md.landmarks["Jason's House (Roof) (SW)"]
        self.roof_ne = md.landmarks["Jason's House (Roof) (NE)"]
        self.stairs_2 = md.landmarks["Jason's House (Front Stairs) (MTNE)"]
        self.stairs_3 = md.landmarks["Jason's House (Front Stairs) (MTSE)"]
        self.stairs_4 = md.landmarks["Jason's House (South Veranda) (TNE)"]
        self.veranda_se = md.landmarks["Jason's House (South Veranda) (TSE)"]
        self.veranda_sw = md.landmarks["Jason's House (South Veranda) (TSW)"]
        self.veranda_ne = md.landmarks["Jason's House (Upper Veranda) (TNE)"]
        self.rear_stairs_1 = md.landmarks["Jason's House (Rear Stairs) (BW)"]
        self.terrace_ne = md.landmarks["Jason's House (North Veranda) (TNE)"]
        self.power_pole_t = md.landmarks["Jason's House (Power Pole) (T)"]
        self.boat_ramp_s = md.landmarks["Jason's House (Boat Ramp) (S)"]
        self.boat_ramp_sw = md.landmarks["Jason's House (Boat Ramp) (SW)"]
        self.boat_ramp_nw = md.landmarks["Jason's House (Boat Ramp) (NW)"]
        self.z = 1.9
        self.ox, self.oy = offset
        self._construct()

    def _construct(self):
        self.base_se = (self.top_se[0], self.top_se[1], self.base_ne[2])
        self.base_sw = (self.top_sw[0], self.top_sw[1], self.base_ne[2])
        self.base_nw = (self.top_sw[0], self.top_ne[1], self.base_ne[2])
        self.ground_se = (self.base_se[0], self.base_se[1], self.z)
        self.ground_sw = (self.base_sw[0], self.base_sw[1], self.z)
        self.ground_nw = (self.base_nw[0], self.base_nw[1], self.z)
        self.ground_ne = (self.base_ne[0], self.base_ne[1], self.z)
        self.top_nw = (self.base_nw[0], self.base_nw[1], (self.top_sw[2] + self.top_ne[2]) / 2)
        self.roof_n = (
            self.roof_ne[0] + self.roof_s[0] - self.roof_se[0],
            self.roof_ne[1] + self.roof_s[1] - self.roof_se[1],
            self.roof_ne[2] + self.roof_s[2] - self.roof_se[2],
        )
        self.roof_nw = (
            self.roof_ne[0] + self.roof_sw[0] - self.roof_se[0],
            self.roof_ne[1] + self.roof_sw[1] - self.roof_se[1],
            self.roof_ne[2] + self.roof_sw[2] - self.roof_se[2],
        )
        self.stairs_1 = (
            self.stairs_2[0] + (self.stairs_3[0] - self.stairs_4[0]) * 1.6,
            self.stairs_2[1] + (self.stairs_3[1] - self.stairs_4[1]) * 1.6,
            self.stairs_2[2] + (self.stairs_3[2] - self.stairs_4[2]) * 1.6,
        )
        self.stairs_0 = (self.stairs_1[0], self.stairs_1[1], self.z)
        self.veranda_nw = (self.veranda_sw[0], self.veranda_ne[1], (self.veranda_sw[2] + self.veranda_ne[2]) / 2)
        self.veranda_e = (self.base_ne[0], self.base_ne[1], self.veranda_ne[2])
        self.rear_stairs_0 = (self.rear_stairs_1[0], self.rear_stairs_1[1], self.z)
        self.rear_stairs_2 = (
            self.rear_stairs_1[0],
            self.rear_stairs_1[1] + self.terrace_ne[2] - self.rear_stairs_1[2] + 1.0,
            self.terrace_ne[2]
        )
        self.terrace_nw = (self.rear_stairs_1[0], self.terrace_ne[1], self.terrace_ne[2])
        self.terrace_e = (self.terrace_ne[0], self.veranda_ne[1], self.terrace_ne[2])
        self.power_pole_b = (self.power_pole_t[0], self.power_pole_t[1], self.z)

    def draw_on_map(self, m, width=1):
        for line in [
            (self.roof_se, self.roof_s),
            (self.roof_s, self.roof_sw),
            (self.roof_sw, self.roof_nw),
            (self.roof_nw, self.roof_n),
            (self.roof_n, self.roof_ne),
            (self.roof_ne, self.roof_se),
            (self.roof_s, self.roof_n),
            (self.stairs_1, self.stairs_2),
            (self.stairs_2, self.stairs_3),
            (self.stairs_3, self.stairs_4),
            (self.stairs_4, self.veranda_se),
            (self.veranda_se, self.veranda_sw),
            (self.veranda_sw, self.veranda_nw),
            (self.veranda_nw, self.veranda_ne),
            (self.veranda_ne, self.veranda_e),
            (self.rear_stairs_0, self.rear_stairs_1),
            (self.rear_stairs_1, self.rear_stairs_2),
            (self.rear_stairs_2, self.terrace_nw),
            (self.terrace_nw, self.terrace_ne),
            (self.terrace_ne, self.terrace_e),
            (self.boat_ramp_s, self.boat_ramp_sw),
            (self.boat_ramp_sw, self.boat_ramp_nw),
        ]:
            m.draw_line(line, self.color, width)
        m.draw_circle(self.power_pole_t, 0.1, self.color, self.color, 1)
        return self

    def render_on_camera(self, cam, width=4):
        for line in [
            (self.ground_se, self.base_se),
            (self.ground_sw, self.base_sw),
            (self.ground_nw, self.base_nw),
            (self.ground_ne, self.base_ne),
            (self.base_se, self.base_sw),
            (self.base_sw, self.base_nw),
            (self.base_nw, self.base_ne),
            (self.base_ne, self.base_se),
            (self.base_se, self.top_se),
            (self.base_sw, self.top_sw),
            (self.base_nw, self.top_nw),
            (self.base_ne, self.top_ne),
            (self.roof_se, self.roof_s),
            (self.roof_s, self.roof_sw),
            (self.roof_sw, self.roof_nw),
            (self.roof_nw, self.roof_n),
            (self.roof_n, self.roof_ne),
            (self.roof_ne, self.roof_se),
            (self.roof_s, self.roof_n),
            (self.stairs_0, self.stairs_1),
            (self.stairs_1, self.stairs_2),
            (self.stairs_2, self.stairs_3),
            (self.stairs_3, self.stairs_4),
            (self.stairs_4, self.veranda_se),
            (self.veranda_se, self.veranda_sw),
            (self.veranda_sw, self.veranda_nw),
            (self.veranda_nw, self.veranda_ne),
            (self.veranda_ne, self.veranda_e),
            (self.rear_stairs_0, self.rear_stairs_1),
            (self.rear_stairs_1, self.rear_stairs_2),
            (self.rear_stairs_2, self.terrace_nw),
            (self.terrace_nw, self.terrace_ne),
            (self.terrace_ne, self.terrace_e),
            (self.power_pole_b, self.power_pole_t),
        ]:
            cam.render_line((
                (line[0][0] + self.ox, line[0][1] + self.oy, line[0][2]),
                (line[1][0] + self.ox, line[1][1] + self.oy, line[1][2]),
            ), self.color, width)
        return self


### AIWE ##########################################################################################

