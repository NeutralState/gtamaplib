#!/usr/bin/env python3
# CYCLE-DETECT-FIX (2026-07-09): les LM demotees par TIERS-SIGMA comptent
# encore comme anchor/high pour les ARETES de circular_deps — la demotion
# retire leur poids BA, pas la realite de la dependance. Sans ca, une demotion
# (dependante des covariances du dernier solve) peut MASQUER un cycle pur
# (vecu: Delights<->Postcard invisible quand Train Signal E/W flottait au
# seuil 20m -> CI vert par accident, commit bd1eba1 au message errone).
# Post-fix: 2 cycles purs STABLES (trio Ambrosia + Delights<->Postcard).
# Idempotent.
import sys
p = 'tools/audit/circular_deps.py'
src = open(p).read()
if 'CYCLE-DETECT-FIX' in src:
    print('ok  deja patche'); sys.exit(0)
old = "    cameras, landmarks, pixels, lm_tiers = L.load_data()"
new = """    cameras, landmarks, pixels, lm_tiers = L.load_data()
    # CYCLE-DETECT-FIX (2026-07-09): les LM demotees par TIERS-SIGMA comptent
    # encore comme anchor/high pour les ARETES de dependance — la demotion
    # retire leur poids BA, pas la realite de la dependance. Sans ca, une
    # demotion (qui depend des covariances du dernier solve) peut MASQUER un
    # cycle pur du detecteur. Deterministe donne les data.
    try:
        import json as _json
        _full = _json.load(open('tools/generated/confidence_tiers.json'))
        _lmrec = _full.get('landmarks', _full.get('lms', {}))
        for _n, _r in _lmrec.items():
            if str(_r.get('reason', '')).startswith('TIERS-SIGMA demotion'):
                lm_tiers[_n] = 'high'
    except Exception:
        pass"""
assert old in src, 'ancre load_data introuvable'
src = src.replace(old, new, 1)
open(p, 'w').write(src)
print('EDIT circular_deps: CYCLE-DETECT-FIX')
