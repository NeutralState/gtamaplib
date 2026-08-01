#!/usr/bin/env python3
# MAP-TRUTH-V1 partie 2 (2026-07-13): tiers pour les LM map-ancres.
# Le module gtamapdata WHITELISTE les champs meta (source_cameras/error_m/
# zone/z_constraint) — map_anchored serait jete au chargement. Doctrine: on
# ne touche pas le module -> compute_confidence_tiers lit le JSON brut.
# Valide sandbox: LM test -> tier anchor, reason 'verite-map yanis'.
import sys
p = 'tools/compute_confidence_tiers.py'
src = open(p).read()
if 'MAP-TRUTH-V1' in src:
    print('ok  deja patche'); sys.exit(0)
o = "def classify_landmarks(cam_tier_fn):"
n = '''_RAW_LMS_CACHE = None
def _raw_lms():
    # [MAP-TRUTH-V1] le module gtamapdata whiteliste les champs meta —
    # map_anchored se lit dans le JSON brut (doctrine: ne pas toucher le module)
    global _RAW_LMS_CACHE
    if _RAW_LMS_CACHE is None:
        import json as _j
        _RAW_LMS_CACHE = _j.load(open('gtamapdata/landmarks.json'))
    return _RAW_LMS_CACHE

def classify_landmarks(cam_tier_fn):'''
assert o in src, 'ancre classify introuvable'
src = src.replace(o, n, 1)
o = """        meta = md.landmarks_meta.get(lm_name, {})
        sources = meta.get('source_cameras', [])
        z_const = meta.get('z_constraint')"""
n = """        meta = md.landmarks_meta.get(lm_name, {})
        sources = meta.get('source_cameras', [])
        z_const = meta.get('z_constraint')

        # [MAP-TRUTH-V1] LM map-ancre (xyz = verite yanis,13) => anchor direct
        if xyz is not None and _raw_lms().get(lm_name, {}).get('map_anchored'):
            out[lm_name] = {
                'tier': 'anchor', 'n_sources': len(sources),
                'n_leak_sources': 0, 'median_res': None, 'max_res': None,
                'reason': 'map_anchored: verite-map yanis (MAP-TRUTH-V1)',
            }
            continue"""
assert o in src, 'ancre meta introuvable'
src = src.replace(o, n, 1)
open(p, 'w').write(src)
print('EDIT compute_confidence_tiers.py: map_anchored -> anchor (JSON brut)')
