#!/usr/bin/env python3
# MAP-TRUTH-V1 (2026-07-13): la capacite "decouvertes terrain" de rlx dans
# NOTRE pipeline. Principe: un feature au sol identifie a la fois dans un
# frame ET sur la map yanis (routes, chemins, rives, ponts, pylones) devient
# un LM ancre — xyz = verite-map (x,y du hover de la vue Map, z du sol) —
# et chaque marking dessus est une contrainte courte-portee qui verrouille
# les poses la ou les tours lointaines sont molles (les vallees N-S).
# (1) tools/add_ground_lm.py: creation en une commande.
# (2) compute_confidence_tiers: map_anchored=true => tier anchor (le bundle
#     verrouille x,y par tier; z_constraint fixed epingle z — machinerie
#     existante, zero changement au BA).
import sys, os

TOOL = '''#!/usr/bin/env python3
# add_ground_lm.py -- cree un LM map-ancre (verite yanis,13). MAP-TRUTH-V1.
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
               "notes": "map-evidence yanis,13 (MAP-TRUTH-V1)"}
with open(p, "w") as f:
    json.dump(lms, f, indent=2, ensure_ascii=True); f.write("\\n")
log_event("map_truth", "ground_lm_created", lm=a.name,
          reason=f"map-ancre ({a.x}, {a.y}, {a.z})")
print(f"LM map-ancre cree: {a.name} @ ({a.x}, {a.y}, {a.z})")
print("Marque-le maintenant dans les cams qui le voient.")
'''
if not os.path.exists('tools/add_ground_lm.py'):
    open('tools/add_ground_lm.py', 'w').write(TOOL)
    print('CREE tools/add_ground_lm.py')
else:
    print('ok  add_ground_lm.py existe')

p = 'tools/compute_confidence_tiers.py'
src = open(p).read()
if 'map_anchored' in src:
    print('ok  tiers deja patches')
else:
    # ancre: la ou le tier anchor est attribue — adapte selon la structure
    import re
    m = re.search(r"def classify_lm\w*\(.*\):", src)
    assert m, 'structure tiers inattendue — colle-moi compute_confidence_tiers.py autour de la classification LM'
    a = m.group(0)
    add = a + '''
    # [MAP-TRUTH-V1] LM map-ancre = verite yanis => tier anchor direct
    if (_lm_meta(name) or {}).get("map_anchored"):
        return "anchor"'''
    src = src.replace(a, add, 1)
    helper = '''
def _lm_meta(name):
    import json as _j
    global _LM_META_CACHE
    try:
        _LM_META_CACHE
    except NameError:
        _LM_META_CACHE = _j.load(open("gtamapdata/landmarks.json"))
    return _LM_META_CACHE.get(name)
'''
    src = helper + src
    open(p, 'w').write(src)
    print('EDIT compute_confidence_tiers.py: map_anchored -> anchor')
