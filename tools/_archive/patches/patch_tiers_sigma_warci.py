#!/usr/bin/env python3
# TIERS-SIGMA-V1 + WAR-CI-V1 (2026-07-08, fin du backlog programmatique).
# 1. compute_confidence_tiers: DEMOTION anchor/high -> medium si sigma_m > 20m
#    (geometrie molle: sources d'accord angulairement, parallaxe faible —
#    confiance non meritee, ne doit ni peser au BA ni cascader des promotions).
#    Symetrique de la promotion DUAL-METRIC-V2. 7 LM demotes (la liste exacte
#    des surprises du sigma_report: Radio Tower #1 28m, Train Signal S, etc.)
# 2. ci_healthcheck: WAR-SCAN light (warning only) — compte les LM avec >=1
#    observer en outlier dual (ang>15' ET gap>3m), ~1s.
# Validation sandbox: tiers anchor 85->79/high->133/medium->237, cycle vert,
# mediane 1.831'/0.187m INTOUCHEE (re-poids propre), CI 2.4s. Idempotent.
import sys

p = 'tools/compute_confidence_tiers.py'
src = open(p).read()
if 'TIERS-SIGMA-V1' in src:
    print(f'ok  {p}: deja patche')
else:
    old = "def apply_dual_promotions(cam_tiers):"
    new = '''# ── TIERS-SIGMA-V1 (2026-07-08): demotion des LM a confiance non meritee ──
# Un LM anchor/high avec sigma_m > 20m (COVARIANCE-V1) a des sources qui
# s'accordent angulairement mais une geometrie molle (parallaxe faible):
# sa confiance de tier n'est pas meritee — il ne doit ni peser fort au BA
# ni cascader des promotions de cams. Symetrique de la promotion V2.
LM_DEMOTE_SIGMA_M = 20.0

def apply_sigma_demotions(lm_tiers):
    demoted = []
    try:
        from common import lm_sigma_m
    except Exception:
        return demoted
    for lm_name, rec in lm_tiers.items():
        if rec.get('tier') not in ('anchor', 'high'):
            continue
        s = lm_sigma_m(lm_name)
        if s is not None and s > LM_DEMOTE_SIGMA_M:
            old_tier = rec['tier']
            rec['tier'] = 'medium'
            rec['reason'] = (f'TIERS-SIGMA demotion: sigma {s:.1f}m > '
                             f'{LM_DEMOTE_SIGMA_M}m (geometrie molle) — etait '
                             f'{old_tier}: ' + str(rec.get('reason', '?')))
            demoted.append((s, lm_name, old_tier))
    return demoted


def apply_dual_promotions(cam_tiers):'''
    assert old in src, 'ancre apply_dual_promotions introuvable'
    src = src.replace(old, new, 1)

    old = "    lm_tiers = classify_landmarks(source_only_cam_tier)"
    new = "    lm_tiers = classify_landmarks(source_only_cam_tier)\n    apply_sigma_demotions(lm_tiers)  # TIERS-SIGMA-V1"
    assert old in src, 'ancre pass1 LM introuvable'
    src = src.replace(old, new, 1)

    old = "            new_tiers = classify_landmarks(cam_tier_lookup)"
    new = "            new_tiers = classify_landmarks(cam_tier_lookup)\n            apply_sigma_demotions(new_tiers)  # TIERS-SIGMA-V1"
    assert old in src, 'ancre convergence LM introuvable'
    src = src.replace(old, new, 1)

    old = '''    if promoted:
        promoted.sort()'''
    new = '''    lm_demoted = [(None, n) for n, r in lm_tiers.items()
                  if str(r.get('reason', '')).startswith('TIERS-SIGMA demotion')]
    try:
        from common import lm_sigma_m as _lsm
        lm_demoted = sorted((_lsm(n) or 0, n) for _s, n in lm_demoted)
    except Exception:
        pass
    if lm_demoted:
        print(f"\\n⚑ TIERS-SIGMA-V1: {len(lm_demoted)} LM anchor/high DEMOTES "
              f"medium (sigma > {LM_DEMOTE_SIGMA_M}m, geometrie molle):")
        for s, n in lm_demoted:
            print(f"    {s:6.1f}m  {n}")
    if promoted:
        promoted.sort()'''
    assert old in src, 'ancre report promotions introuvable'
    src = src.replace(old, new, 1)
    open(p, 'w').write(src)
    print(f'EDIT {p}: TIERS-SIGMA-V1')

p = 'tools/ci_healthcheck.py'
src = open(p).read()
if 'WAR-CI-V1' in src:
    print(f'ok  {p}: deja patche')
    sys.exit(0)
old = """        else:
            print('✓ fossils: none')"""
new = """        else:
            print('✓ fossils: none')
        # ── WAR-SCAN light (WARNING only) [WAR-CI-V1, 2026-07-08] ──────
        # Compte les LM avec >=1 observer en outlier DUAL (ang>15' ET
        # gap>3m) — version legere du collision_scan pour le CI.
        try:
            from common import get_cam, residual_dual, is_excluded_marking
            import gtamapdata as _md
            war_lms = set()
            for _c, _obs in _md.pixels.items():
                _cam = get_cam(_c)
                if _cam is None:
                    continue
                for _l, _px in _obs.items():
                    if _px is None or is_excluded_marking(_c, _l):
                        continue
                    _xyz = _md.landmarks.get(_l)
                    if _xyz is None:
                        continue
                    _a, _g, _d = residual_dual(_cam, _px, _xyz)
                    if _a is not None and _a > 15 and (_g is None or _g > 3.0):
                        war_lms.add(_l)
            if war_lms:
                print(f'⚠ wars: {len(war_lms)} LM avec outlier dual '
                      f'(collision_scan pour le detail)')
            else:
                print('✓ wars: aucun outlier dual')
        except Exception as _e:
            print(f'  (war-scan light indisponible: {_e})')"""
assert old in src, 'ancre fossils introuvable'
src = src.replace(old, new, 1)
open(p, 'w').write(src)
print(f'EDIT {p}: WAR-CI-V1')
