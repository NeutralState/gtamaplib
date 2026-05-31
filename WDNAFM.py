"""
WDNAFM.py — standalone WDNA FM radio tower mesh generator.
Ported from rlx upstream (gtamaplib.py class WDNAFM). Separate file like
OneThousandVenetian.py so the vendored gtamaplib.py stays untouched.
Triangular lattice mast: 3 verticals (N/SE/SW) from z=5 up through 5 levels
to z~396, then converging to tip t (z~402).
"""

class WDNAFM:
    color = '#f87171'

    def __init__(self, md, ml=None):
        self.md = md
        self.ml = ml
        L = md.landmarks
        self.t = L["WDNA FM"]
        self.n0 = L["WDNA FM (N0)"];  self.se0 = L["WDNA FM (SE0)"];  self.sw0 = L["WDNA FM (SW0)"]
        self.n1 = L["WDNA FM (N1)"];  self.se1 = L["WDNA FM (SE1)"];  self.sw1 = L["WDNA FM (SW1)"]
        self.n2 = L["WDNA FM (N2)"];  self.se2 = L["WDNA FM (SE2)"];  self.sw2 = L["WDNA FM (SW2)"]
        self.n3 = L["WDNA FM (N3)"];  self.se3 = L["WDNA FM (SE3)"];  self.sw3 = L["WDNA FM (SW3)"]
        self.n4 = L["WDNA FM (N4)"];  self.se4 = L["WDNA FM (SE4)"];  self.sw4 = L["WDNA FM (SW4)"]

    def render_on_camera(self, cam, width=1):
        for line in [
            (self.n0, self.n4), (self.se0, self.se4), (self.sw0, self.sw4),
            (self.n4, self.t), (self.se4, self.t), (self.sw4, self.t),
            (self.n0, self.se0), (self.se0, self.sw0), (self.sw0, self.n0),
            (self.n1, self.se1), (self.se1, self.sw1), (self.sw1, self.n1),
            (self.n2, self.se2), (self.se2, self.sw2), (self.sw2, self.n2),
            (self.n3, self.se3), (self.se3, self.sw3), (self.sw3, self.n3),
            (self.n4, self.se4), (self.se4, self.sw4), (self.sw4, self.n4),
        ]:
            cam.render_line(line, self.color, width)
        return self
