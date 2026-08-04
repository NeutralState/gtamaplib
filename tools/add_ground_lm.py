#!/usr/bin/env python3
# add_ground_lm.py -- cree un LM map-ancre (verite yanis,14). MAP-TRUTH-V1.
# Usage: python3 tools/add_ground_lm.py "Nom (Zone) (A)" X Y [Z] [--zone nom]
# X/Y = coords monde lues au hover de la vue Map. Z defaut 0.5 (sol).
# Ensuite: marque-le dans les cams (verdict toast actif des le 1er marking).
import argparse, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import log_event

ap = argparse.ArgumentParser()
ap.add_argument("name"); ap.add_argument("x", type=float)
ap.add_argument("y", type=float)
ap.add_argument("z", type=float, nargs="?", default=0.5)
ap.add_argument("--zone", default="map_truth")
a = ap.parse_args()
p = "gtamapdata/landmarks.json"
lms = json.load(open(p))
if a.name in lms and (lms[a.name] or {}).get("xyz"):
    sys.exit(f"existe deja avec xyz: {a.name}")
lms[a.name] = {"xyz": [a.x, a.y, a.z], "source_cameras": [],
               "error_m": None, "zone": a.zone, "map_anchored": True,
               "z_constraint": {"type": "fixed", "value": a.z},
               "notes": "map-evidence yanis,14 (MAP-TRUTH-V1)"}
with open(p, "w") as f:
    json.dump(lms, f, indent=2, ensure_ascii=True); f.write("\n")
log_event("map_truth", "ground_lm_created", lm=a.name,
          reason=f"map-ancre ({a.x}, {a.y}, {a.z})")
print(f"LM map-ancre cree: {a.name} @ ({a.x}, {a.y}, {a.z})")
print("Marque-le maintenant dans les cams qui le voient.")
