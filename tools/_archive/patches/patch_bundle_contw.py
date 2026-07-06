"""Patch CONT-W-V1: option --continuous sur bundle_adjust_weighted.py.

Poids LM continus par maximum de vraisemblance: weight = clamp(22/radius_m,
0.1, 15) depuis le Monte-Carlo de lm_uncertainty.py (au lieu des 5 buckets).
K=22 calibre le radius median (~11m) sur le poids "medium" (2.0).

VERDICT A/B (2026-07-02, sandbox): le harvest guarded est INVARIANT au
schema de ponderation sur l'etat actuel — memes deltas, memes gains.
Le guarded gate (residuels bruts, independant des poids) filtre deja ce
que des mauvais poids pourraient corrompre. Option conservee: plus
principielle, zero risque, pourrait compter dans les clusters contestes
(Diner) ou les poids relatifs decident du compromis.

PREREQUIS: tools/generated/lm_uncertainty.json frais (lm_uncertainty.py
--dump apres le patch EXCL-AWARE). Idempotent. Backup: .bak_contw
"""
import shutil, sys
P = 'tools/bundle_adjust_weighted.py'
s = open(P).read()
if 'CONT-W-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_contw')
old = """TIER_WEIGHTS = {"""
assert old in s
new = """# [CONT-W-V1] Poids LM continus par maximum de vraisemblance: weight = K/sigma
# (radius_m Monte-Carlo de lm_uncertainty.py), clamp [0.1, 15] pour rester dans
# la plage des buckets. K=22 calibre le radius median (~11m) sur le poids
# "medium" (2.0). Active par --continuous. Fallback bucket si LM absent du dump.
CONT_K = 22.0
CONT_MIN, CONT_MAX = 0.1, 15.0
CONTINUOUS = '--continuous' in __import__('sys').argv
LM_SIGMA = {}
if CONTINUOUS:
    import os as _os
    _unc_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'generated', 'lm_uncertainty.json')
    with open(_unc_path) as _f:
        _d = __import__('json').load(_f)
    LM_SIGMA = {r['lm']: max(0.5, float(r['radius_m']))
                for r in _d['results'] if r.get('status') == 'ok'}
    print(f"# [CONT-W-V1] poids continus actifs: {len(LM_SIGMA)} LMs avec sigma "
          f"(K={CONT_K}, clamp [{CONT_MIN},{CONT_MAX}])")

TIER_WEIGHTS = {"""
s = s.replace(old, new, 1)
old = """        lm_t = lm_tier.get(lm_name, 'unknown')
        lm_w = TIER_WEIGHTS.get(lm_t, 1.0)"""
assert old in s
new = """        lm_t = lm_tier.get(lm_name, 'unknown')
        if CONTINUOUS and lm_name in LM_SIGMA:
            lm_w = min(CONT_MAX, max(CONT_MIN, CONT_K / LM_SIGMA[lm_name]))  # [CONT-W-V1]
        else:
            lm_w = TIER_WEIGHTS.get(lm_t, 1.0)"""
s = s.replace(old, new, 1)
open(P, 'w').write(s)
print('CONT-W-V1 applique')
