"""
OneThousandVenetian — procedural Landmark class for 1000 Venetian Way

Architecture (v5, corrected after triangulation of T-NW, W-Box-NW etc.):
  - Podium au sol (rectangle large, z=0)
  - 2 towers droites côte à côte (z=0 → z=59.5)
  - Escalier 4 paliers W1-W4 sur le côté ouest des towers
  - Murets (2)(3)(4) sur la face est de l'escalier
  - MAIN ROOF principal à z=59.5 (T-NW, T-SW, NW, NE)
  - PENTHOUSE BOX sur le toit (z=59.5 → z=65)
    * Base NW = W-Box-NW (triangulated)
    * Top corners SE/SW (z=65, triangulés — c'était PAS le toit principal)

Z hierarchy:
    z=0    sol/podium
    z=9    W1
    z=21   W2
    z=27   muret E1
    z=32   W3
    z=39   muret E2
    z=44   W4
    z=51   muret E3
    z=59.5 MAIN ROOF (T-NW, T-SW = corners NW/SW; NW, NE = corners NE/SE inferred)
    z=65   PENTHOUSE BOX TOP (SE, SW)

LMs requis dans landmarks.json:
    1000 Venetian Way (T-NW)        z=59.5  toit principal NW
    1000 Venetian Way (NW)          z=59.5  (alternative pour NW si T-NW absent)
    1000 Venetian Way (NE)          z=59.5  toit principal NE
    1000 Venetian Way (Center-NE)   z=59.5  point sur le gap entre towers
    1000 Venetian Way (W-Box-NW)    z=59.5  base NW du penthouse box
    1000 Venetian Way (SE)          z=65    top SE du penthouse box
    1000 Venetian Way (SW)          z=65    top SW du penthouse box
    1000 Venetian Way (2), (3), (4) murets E sur la pyramide
    1000 Venetian Way (B-NW), (B-SW)  podium ground corners
    1000 Venetian Way (W1)-(W4)     paliers de l'escalier W
"""

import math


class OneThousandVenetian:
    Z_GROUND = 0.0
    Z_W1 = 9.0
    Z_W2 = 21.0
    Z_PE1 = 27.0
    Z_W3 = 32.0
    Z_PE2 = 39.0
    Z_W4 = 44.0
    Z_PE3 = 51.0
    Z_ROOF = 62.75     # main roof of the building (where T-NW/T-SW sit)
    Z_PHTOP = 68.2    # top of the penthouse box (where SE/SW sit)

    def __init__(self, md, ml):
        self.md = md
        self.ml = ml

        # Triangulated anchors
        # Note: SE and SW are at z=65 = PENTHOUSE TOP, not the main roof
        self.ph_top_se = self._get_lm("1000 Venetian Way (SE)")
        self.ph_top_sw = self._get_lm("1000 Venetian Way (SW)")

        # Main roof corners (triangulated multi-cam)
        self.t_nw = self._get_lm_optional("1000 Venetian Way (T-NW)")  # NW corner of main roof
        self.nw_roof = None  # was: triangulated at z=64.5 but main roof is z=59.5, disabled
        self.ne_roof = None  # disabled (see nw_roof comment)
        self.center_ne = self._get_lm_optional("1000 Venetian Way (Center-NE)")

        # Penthouse base
        self.w_box_nw = self._get_lm_optional("1000 Venetian Way (W-Box-NW)")

        # Murets E
        self.pe1 = self._get_lm("1000 Venetian Way (2)")
        self.pe2 = self._get_lm("1000 Venetian Way (3)")
        self.pe3 = self._get_lm("1000 Venetian Way (4)")

        # Podium
        self.b_nw = self._get_lm("1000 Venetian Way (B-NW)")
        self.b_sw = self._get_lm("1000 Venetian Way (B-SW)")

        # Paliers W
        self.w1 = self._get_lm("1000 Venetian Way (W1)")
        self.w2 = self._get_lm("1000 Venetian Way (W2)")
        self.w3 = self._get_lm("1000 Venetian Way (W3)")
        self.w4 = self._get_lm("1000 Venetian Way (W4)")

        # [V6 2026-07-20] niveaux z DERIVES des LMs courants (les constantes
        # de classe etaient perimees apres retriangulations/BA: W1 9->10.8,
        # toit 62.75->62.5, penthouse 68.2->68.0). Le mesh suit les LMs.
        self.Z_GROUND = self.b_nw[2]
        self.Z_W1 = self.w1[2]
        self.Z_W2 = self.w2[2]
        self.Z_W3 = self.w3[2]
        self.Z_W4 = self.w4[2]
        self.Z_PE1 = self.pe1[2]
        self.Z_PE2 = self.pe2[2]
        self.Z_PE3 = self.pe3[2]
        if self.t_nw is not None:
            self.Z_ROOF = self.t_nw[2]
        self.Z_PHTOP = (self.ph_top_se[2] + self.ph_top_sw[2]) / 2
        # rythme mesure: paliers W espaces de ~12.15m = 4 etages
        self.FLOOR_H = (self.Z_W2 - self.Z_W1) / 4.0

        self._compute_axes()
        self._compute_inferred_corners()

    def _get_lm(self, name):
        xyz = self.md.landmarks.get(name)
        if xyz is None or len(xyz) < 3:
            raise ValueError(f"Missing required LM: {name}")
        return tuple(xyz)

    def _get_lm_optional(self, name):
        """Return LM if available, else None."""
        xyz = self.md.landmarks.get(name)
        if xyz is None or len(xyz) < 3:
            return None
        return tuple(xyz)

    def _compute_axes(self):
        """
        Build axes from the penthouse top corners (SE/SW), as before.
        NW/NE main roof corners are used only for the BACK face depth.
        """
        # Always use penthouse top SE/SW for orientation - that was the stable
        # baseline that put the front face at v=0
        dx = self.ph_top_se[0] - self.ph_top_sw[0]
        dy = self.ph_top_se[1] - self.ph_top_sw[1]
        self.roof_mid = (
            (self.ph_top_se[0] + self.ph_top_sw[0]) / 2,
            (self.ph_top_se[1] + self.ph_top_sw[1]) / 2,
        )
        self.roof_back_corners = (self.nw_roof, self.ne_roof) if (
            self.nw_roof is not None and self.ne_roof is not None) else None
        length = math.hypot(dx, dy)
        self.axis_main = (dx / length, dy / length, 0.0)
        self.width_roof = length

        # axis_depth perpendicular, pointing toward the paliers
        perp = (-self.axis_main[1], self.axis_main[0], 0.0)
        test_dx = self.w4[0] - self.roof_mid[0]
        test_dy = self.w4[1] - self.roof_mid[1]
        proj = test_dx * perp[0] + test_dy * perp[1]
        if proj < 0:
            perp = (-perp[0], -perp[1], 0.0)
        self.axis_depth = perp

        # Depths
        self.depth_tower = self._proj_depth(self.nw_roof) if self.nw_roof is not None else abs(self._proj_depth(self.w4))
        self.depth_podium = self._proj_depth(self.b_nw)
        self.depth_w1 = self._proj_depth(self.w1)
        self.depth_w2 = self._proj_depth(self.w2)
        self.depth_w3 = self._proj_depth(self.w3)
        self.depth_w4 = self._proj_depth(self.w4)

        # u-positions
        self.u_b_nw = self._proj_main(self.b_nw)
        self.u_b_sw = self._proj_main(self.b_sw)
        self.u_w1 = self._proj_main(self.w1)
        self.u_w2 = self._proj_main(self.w2)
        self.u_w3 = self._proj_main(self.w3)
        self.u_w4 = self._proj_main(self.w4)
        # Tower west/east edges
        # Building's east/west extent at main roof level (z=Z_ROOF):
        # Use T-NW if available (it's the actual NW corner of the main roof,
        # which extends further west than the penthouse top).
        # Mirror to get east edge.
        if self.t_nw is not None:
            self.u_west = self._proj_main(self.t_nw)
            self.u_east = -self.u_west  # mirror across axis_main center
        else:
            self.u_west = self._proj_main(self.ph_top_sw)
            self.u_east = self._proj_main(self.ph_top_se)

    def _proj_main(self, point):
        rx = point[0] - self.roof_mid[0]
        ry = point[1] - self.roof_mid[1]
        return rx * self.axis_main[0] + ry * self.axis_main[1]

    def _proj_depth(self, point):
        rx = point[0] - self.roof_mid[0]
        ry = point[1] - self.roof_mid[1]
        return rx * self.axis_depth[0] + ry * self.axis_depth[1]

    def _from_axes(self, u, v, z):
        x = self.roof_mid[0] + u * self.axis_main[0] + v * self.axis_depth[0]
        y = self.roof_mid[1] + u * self.axis_main[1] + v * self.axis_depth[1]
        return (x, y, z)

    def _compute_inferred_corners(self):
        """Compute corners not directly triangulated."""
        # Main roof corners (z=Z_ROOF=59.5)
        # If NW/NE not triangulated, use ph_top mirror at z=Z_ROOF
        if self.nw_roof is None:
            self.nw_roof = self._from_axes(self.u_west, self.depth_tower, self.Z_ROOF)
        if self.ne_roof is None:
            self.ne_roof = self._from_axes(self.u_east, self.depth_tower, self.Z_ROOF)
        # Front roof corners (at v=0, z=Z_ROOF) - inferred from ph_top corners
        # ph_top_sw is at SOMEWHERE on the penthouse top. Its u/v gives us
        # information about where the penthouse is, but the main roof front
        # corners are at u=u_west/u_east, v=0, z=Z_ROOF.
        self.sw_roof = self._from_axes(self.u_west, 0.0, self.Z_ROOF)
        self.se_roof = self._from_axes(self.u_east, 0.0, self.Z_ROOF)

        # Podium NE/SE corners
        self.b_ne = self._from_axes(self.u_east, self.depth_podium, self.Z_GROUND)
        self.b_se = self._from_axes(self.u_east, 0.0, self.Z_GROUND)

        # Penthouse box: 4 base corners at z=Z_ROOF + 4 top corners at z=Z_PHTOP.
        # Footprint = same rectangle for base and top (so verticals are straight).
        # Anchors:
        #   W-Box-NW: NW corner of the box base (z=Z_ROOF)
        #   ph_top_sw / ph_top_se: SW and SE corners of the box TOP (z=Z_PHTOP)
        # We use w_box_nw's u as the west edge, and ph_top_se's u as the east edge.
        # For depth: use w_box_nw's v as back, and ph_top_sw/se's v as front.
        if self.w_box_nw is not None:
            u_west = self._proj_main(self.w_box_nw)
            u_east = self._proj_main(self.ph_top_se)
            v_back = self._proj_depth(self.w_box_nw)
            v_front = (self._proj_depth(self.ph_top_sw)
                       + self._proj_depth(self.ph_top_se)) / 2
            # Build all 8 corners with the SAME footprint (u_west/u_east, v_front/v_back)
            self.box_base_nw = self._from_axes(u_west, v_back, self.Z_ROOF)
            self.box_base_ne = self._from_axes(u_east, v_back, self.Z_ROOF)
            self.box_base_sw = self._from_axes(u_west, v_front, self.Z_ROOF)
            self.box_base_se = self._from_axes(u_east, v_front, self.Z_ROOF)
            self.box_top_nw = self._from_axes(u_west, v_back, self.Z_PHTOP)
            self.box_top_ne = self._from_axes(u_east, v_back, self.Z_PHTOP)
            self.box_top_sw = self._from_axes(u_west, v_front, self.Z_PHTOP)
            self.box_top_se = self._from_axes(u_east, v_front, self.Z_PHTOP)
        else:
            self.box_base_nw = None

    def render_on_camera(self, cam):
        self._render_podium(cam)
        self._render_towers(cam)
        self._render_pyramid_w(cam)
        self._render_murets_e(cam)
        self._render_penthouse(cam)

    def _ring(self, cam, u0, u1, v0, v1, z):
        """[V6] anneau horizontal rectangulaire dans le repere (u, v) a la hauteur z."""
        a = self._from_axes(u0, v0, z)
        b = self._from_axes(u1, v0, z)
        c = self._from_axes(u1, v1, z)
        d = self._from_axes(u0, v1, z)
        cam.render_line((a, b))
        cam.render_line((b, c))
        cam.render_line((c, d))
        cam.render_line((d, a))

    def _render_podium(self, cam):
        cam.render_line((self.b_nw, self.b_ne))
        cam.render_line((self.b_ne, self.b_se))
        cam.render_line((self.b_se, self.b_sw))
        cam.render_line((self.b_sw, self.b_nw))

    def _render_towers(self, cam):
        # Tower bottom corners at ground level
        t_se_base = self._from_axes(self.u_east, 0.0, self.Z_GROUND)
        t_sw_base = self._from_axes(self.u_west, 0.0, self.Z_GROUND)
        t_ne_base = self._from_axes(self.u_east, self.depth_tower, self.Z_GROUND)
        t_nw_base = self._from_axes(self.u_west, self.depth_tower, self.Z_GROUND)

        # Main roof rectangle (at z=Z_ROOF, NOT Z_PHTOP)
        cam.render_line((self.sw_roof, self.se_roof))
        cam.render_line((self.se_roof, self.ne_roof))
        cam.render_line((self.ne_roof, self.nw_roof))
        cam.render_line((self.nw_roof, self.sw_roof))

        # 4 vertical edges (corners of the towers)
        cam.render_line((t_se_base, self.se_roof))
        cam.render_line((t_ne_base, self.ne_roof))
        cam.render_line((t_sw_base, self.sw_roof))
        cam.render_line((t_nw_base, self.nw_roof))

        # Tower base rectangle
        cam.render_line((t_sw_base, t_se_base))
        cam.render_line((t_se_base, t_ne_base))
        cam.render_line((t_ne_base, t_nw_base))
        cam.render_line((t_nw_base, t_sw_base))

        # [V6] dalles de balcon: la signature visuelle du batiment — un
        # anneau complet par etage (FLOOR_H derive des paliers W)
        z = self.Z_GROUND + self.FLOOR_H
        while z < self.Z_ROOF - 0.5:
            self._ring(cam, self.u_west, self.u_east, 0.0, self.depth_tower, z)
            z += self.FLOOR_H

        # Gap between the 2 towers (if we have Center-NE)
        if self.center_ne is not None:
            u_center = self._proj_main(self.center_ne)
            # Vertical edge marking the split between East/West towers
            # at the back face (v=depth_tower) and front face (v=0)
            split_back_top = self._from_axes(u_center, self.depth_tower, self.Z_ROOF)
            split_back_bot = self._from_axes(u_center, self.depth_tower, self.Z_GROUND)
            split_front_top = self._from_axes(u_center, 0.0, self.Z_ROOF)
            split_front_bot = self._from_axes(u_center, 0.0, self.Z_GROUND)
            cam.render_line((split_back_top, split_back_bot))
            cam.render_line((split_front_top, split_front_bot))

    def _render_pyramid_w(self, cam):
        # Top tier of pyramid is now at Z_ROOF (not Z_PHTOP)
        tiers = [
            (self.u_b_nw,    self.depth_podium, self.Z_GROUND),
            (self.u_w1,      self.depth_w1,     self.Z_W1),
            (self.u_w2,      self.depth_w2,     self.Z_W2),
            (self.u_w3,      self.depth_w3,     self.Z_W3),
            (self.u_w4,      self.depth_w4,     self.Z_W4),
            (self.u_west,    self.depth_tower,  self.Z_ROOF),
        ]
        u_east_palier = self.u_west  # paliers meet the tower's west face

        for i, (u_west, depth, z) in enumerate(tiers):
            front_w = self._from_axes(u_west, 0.0, z)
            front_e = self._from_axes(u_east_palier, 0.0, z)
            back_w = self._from_axes(u_west, depth, z)
            back_e = self._from_axes(u_east_palier, depth, z)
            cam.render_line((front_w, front_e))
            cam.render_line((back_w, back_e))
            cam.render_line((front_w, back_w))
            cam.render_line((front_e, back_e))

            if i + 1 < len(tiers):
                _, depth_next, z_next = tiers[i + 1]
                front_w_up = (front_w[0], front_w[1], z_next)
                back_w_up_full = (back_w[0], back_w[1], z_next)
                cam.render_line((front_w, front_w_up))
                cam.render_line((back_w, back_w_up_full))
                cam.render_line((front_w_up, back_w_up_full))

            # [V6] balcons du bloc sous CE palier: anneaux aux etages
            # intermediaires entre le palier precedent et celui-ci
            if i > 0:
                z_prev = tiers[i - 1][2]
                zb = z_prev + self.FLOOR_H
                while zb < z - 0.5:
                    self._ring(cam, u_west, u_east_palier, 0.0, depth, zb)
                    zb += self.FLOOR_H

    def _render_murets_e(self, cam):
        for muret_xyz, z in [(self.pe1, self.Z_PE1),
                             (self.pe2, self.Z_PE2),
                             (self.pe3, self.Z_PE3)]:
            stub = 2.0
            pt_top = muret_xyz
            pt_bot = (muret_xyz[0], muret_xyz[1], z - stub)
            cam.render_line((pt_top, pt_bot))

    def _render_penthouse(self, cam):
        """Draw the penthouse box if we have its base anchor."""
        if self.box_base_nw is None:
            return
        # Base rectangle (at z=Z_ROOF, on top of main roof)
        cam.render_line((self.box_base_nw, self.box_base_ne))
        cam.render_line((self.box_base_ne, self.box_base_se))
        cam.render_line((self.box_base_se, self.box_base_sw))
        cam.render_line((self.box_base_sw, self.box_base_nw))
        # Top rectangle (at z=Z_PHTOP)
        cam.render_line((self.box_top_nw, self.box_top_ne))
        cam.render_line((self.box_top_ne, self.box_top_se))
        cam.render_line((self.box_top_se, self.box_top_sw))
        cam.render_line((self.box_top_sw, self.box_top_nw))
        # 4 verticals
        cam.render_line((self.box_base_nw, self.box_top_nw))
        cam.render_line((self.box_base_ne, self.box_top_ne))
        cam.render_line((self.box_base_se, self.box_top_se))
        cam.render_line((self.box_base_sw, self.box_top_sw))
