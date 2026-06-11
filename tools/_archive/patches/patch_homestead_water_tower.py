#!/usr/bin/env python3
"""patch_homestead_water_tower.py — Port du mesh HomesteadWaterTower de rlx.

Source: rolux/gtamaplib commit c1d3c4a. Sa classe derive la forme de 6
markings de coins (L1..R3) sur SES pixels Grassrivers 02 — markings qu'on
n'a pas. Les scalaires de forme (referentiel-independants) ont ete calcules
une fois dans son repo et hardcodes: shaft r=6.05m, tank r=8.25m, anneaux a
-16.4/-13.9/-3.3m sous le top. Le CENTRE vient de NOTRE LM 'Homestead Water
Tower' (nos referentiels divergent de ~10m xy / 1.5m z ici, d'ou les offsets
relatifs). Valide en sandbox: apex projete a 4.9px du marking reel sur
Grassrivers 02 (Watson Bay). 192 edges.

Inventaire du diff rlx (2026-06-10): FourSeasons/HanksWaffles/Skyway
identiques a notre vendored lib; WDNAFM existe chez lui en vendored, nous on
a notre port racine WDNAFM.py (pas re-diffe); HomesteadWaterTower = le seul
mesh manquant.

Actions: (1) cree HomesteadWaterTower.py a la racine, (2) patch
tools/extract_mesh_edges.py (import + extraction + output, hunks cibles).
Idempotent. Dry-run par defaut, --apply pour ecrire.
Apres --apply: python3 tools/extract_mesh_edges.py
"""
import os, shutil, sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLS_PATH = os.path.join(PROJ, "HomesteadWaterTower.py")
EXT_PATH = os.path.join(PROJ, "tools", "extract_mesh_edges.py")
APPLY = "--apply" in sys.argv

CLS_CONTENT = "\"\"\"\nHomesteadWaterTower.py \u2014 standalone port of rlx's HomesteadWaterTower\n(rolux/gtamaplib gtamaplib.py, commit c1d3c4a), kept OUT of the vendored lib.\n\nrlx's class derives the tower SHAPE at runtime from 6 corner markings\n(L1..R3) on his Grassrivers 02 (Watson Bay) pixels \u2014 markings we do not\nhave. Shape scalars are referential-independent, so they were computed once\nin his repo (2026-06-10 sandbox session) and hardcoded here with provenance:\n\n    r1 (shaft radius) = 6.0508 m\n    r2 (tank radius)  = 8.2477 m\n    ring offsets below top: d1=16.398, d2=13.934, d3=3.266 m\n    (his absolute z: top 70.083, rings 53.685/56.149/66.817, ground 5.0)\n\nThe tower CENTER comes from OUR landmark 'Homestead Water Tower' (top of\ntower) \u2014 our referential diverges from rlx's by ~10 m xy / 1.5 m z here,\nwhich is exactly why ring heights are stored as offsets from the LM top,\nnot absolute z. Ground elevation (~5 m, grassrivers terrain) stays an\nabsolute tunable.\n\"\"\"\nimport math\n\n\nclass HomesteadWaterTower:\n    color = '#4373a2'  # rlx's RGB (67,115,162)\n\n    R_SHAFT = 6.0508\n    R_TANK = 8.2477\n    # offsets below the LM top (z4): shaft top, tank bottom, tank top\n    D_SHAFT_TOP = 16.398\n    D_TANK_BOT = 13.934\n    D_TANK_TOP = 3.266\n    Z_GROUND = 5.0      # terrain elevation (absolute, grassrivers)\n    STEP_DEG = 15\n\n    def __init__(self, md, ml=None):\n        self.md = md\n        t = md.landmarks['Homestead Water Tower']\n        self.cx, self.cy, self.z_top = float(t[0]), float(t[1]), float(t[2])\n\n    def _ring(self, z, r):\n        pts = []\n        for deg in range(0, 360, self.STEP_DEG):\n            a = math.radians(deg)\n            pts.append((self.cx + r * math.cos(a), self.cy + r * math.sin(a), z))\n        return pts\n\n    def render_on_camera(self, cam, width=0.25):\n        zs = (\n            self.Z_GROUND,                  # z0 ground\n            self.z_top - self.D_SHAFT_TOP,  # z1 shaft top\n            self.z_top - self.D_TANK_BOT,   # z2 tank bottom\n            self.z_top - self.D_TANK_TOP,   # z3 tank top\n            self.z_top,                     # z4 apex\n        )\n        radii = (self.R_SHAFT, self.R_SHAFT, self.R_TANK, self.R_TANK, 0.0)\n        rings = [self._ring(z, r) for z, r in zip(zs, radii)]\n        n = len(rings[0])\n        for level in range(4):\n            ring, nxt = rings[level], rings[level + 1]\n            for i in range(n):\n                # horizontal ring segment\n                cam.render_line((ring[i], ring[(i + 1) % n]), self.color, width)\n                # vertical/slanted connector to next level (apex collapses to center)\n                top = nxt[i] if radii[level + 1] > 0 else (self.cx, self.cy, zs[level + 1])\n                cam.render_line((ring[i], top), self.color, width)\n        return self\n"

HUNKS = [
    ("import",
     "from PortofinoTower import PortofinoTower",
     "from PortofinoTower import PortofinoTower\nfrom HomesteadWaterTower import HomesteadWaterTower"),
    ("extraction",
     """print('Extracting PortofinoTower edges...')
try:
    instance = PortofinoTower(md, ml)
    fake = FakeCam()
    instance.render_on_camera(fake)
    porto_edges = fake.edges
    print(f'  -> {len(porto_edges)} edges')
except Exception as e:
    print(f'  FAILED: {e}')""",
     """print('Extracting PortofinoTower edges...')
try:
    instance = PortofinoTower(md, ml)
    fake = FakeCam()
    instance.render_on_camera(fake)
    porto_edges = fake.edges
    print(f'  -> {len(porto_edges)} edges')
except Exception as e:
    print(f'  FAILED: {e}')

print('Extracting HomesteadWaterTower edges...')
try:
    instance = HomesteadWaterTower(md, ml)
    fake = FakeCam()
    instance.render_on_camera(fake)
    hwt_edges = fake.edges
    print(f'  -> {len(hwt_edges)} edges')
except Exception as e:
    hwt_edges = []
    print(f'  FAILED: {e}')"""),
    ("output",
     """if porto_edges:
    result['Portofino Tower'] = {
        'color': '#a78bfa',
        'world_edges': porto_edges,
    }""",
     """if porto_edges:
    result['Portofino Tower'] = {
        'color': '#a78bfa',
        'world_edges': porto_edges,
    }

if hwt_edges:
    result['Homestead Water Tower'] = {
        'color': HomesteadWaterTower.color,
        'world_edges': hwt_edges,
    }"""),
]

todo = []
if os.path.exists(CLS_PATH):
    print("SKIP: HomesteadWaterTower.py existe deja")
else:
    todo.append("create HomesteadWaterTower.py")
ext = open(EXT_PATH).read()
if "HomesteadWaterTower" in ext:
    print("SKIP: extract_mesh_edges deja patche")
    ext_hunks = []
else:
    ext_hunks = []
    for name, old, new in HUNKS:
        if old not in ext:
            sys.exit(f"ERROR hunk '{name}': introuvable verbatim, target a derive — abort")
        ext_hunks.append((old, new))
        todo.append(f"hunk {name}")

if not todo:
    sys.exit(0)
for t in todo:
    print(("APPLY " if APPLY else "WOULD APPLY ") + t)
if not APPLY:
    print("DRY-RUN: rien ecrit. Relance avec --apply.")
    sys.exit(0)

if not os.path.exists(CLS_PATH):
    open(CLS_PATH, "w").write(CLS_CONTENT)
if ext_hunks:
    shutil.copy(EXT_PATH, EXT_PATH + ".bak_hwt")
    for old, new in ext_hunks:
        ext = ext.replace(old, new, 1)
    open(EXT_PATH, "w").write(ext)
print("DONE. Next: python3 tools/extract_mesh_edges.py")
