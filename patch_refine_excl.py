"""patch_refine_excl.py — EXCL-FIX-V1 (2026-07-04).

refine_cam_ypr silently refitted against markings listed in
excluded_markings.json (same class of bug fixed for lm_uncertainty in
e36f64b). Now honored, with a printout of what was skipped. Idempotent.
"""
import shutil, sys
P = 'tools/refine_cam_ypr.py'
s = open(P).read()
if 'EXCL-FIX-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_excl')
old = "    visible_classified = {}\n    for lm_name in cam_pixels:\n        if lm_name not in landmarks:\n            continue\n        if not isinstance(landmarks[lm_name], dict) or not landmarks[lm_name].get('xyz'):\n            continue\n        visible_classified[lm_name] = classify_lm(lm_name, lm_tiers)"
assert old in s, 'anchor introuvable'
s = s.replace(old, '    # [EXCL-FIX-V1] honor excluded_markings.json (same fix as lm_uncertainty\n    # in e36f64b — this tool was silently refitting against excluded markings)\n    import json as _json, os as _os\n    _excl_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),\n                               \'gtamapdata\', \'excluded_markings.json\')\n    try:\n        with open(_excl_path) as _f:\n            _excl = set(_json.load(_f).get(args.cam_name, []))\n    except Exception:\n        _excl = set()\n\n    visible_classified = {}\n    for lm_name in cam_pixels:\n        if lm_name in _excl:\n            continue\n        if lm_name not in landmarks:\n            continue\n        if not isinstance(landmarks[lm_name], dict) or not landmarks[lm_name].get(\'xyz\'):\n            continue\n        visible_classified[lm_name] = classify_lm(lm_name, lm_tiers)\n    if _excl:\n        print(f"Excluded markings honored: {sorted(_excl & set(cam_pixels))}")\n'.rstrip('\n'), 1)
open(P, 'w').write(s)
print('EXCL-FIX-V1 applique')
