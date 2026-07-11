#!/usr/bin/env python3
"""GUARD-DUAL-V1 + tolerance baseline plancher (Phase B tranche 2, 2026-07-08).

(a) ci_healthcheck: la mediane metres sur 119 cams bouge par pas discrets —
    fail seulement au-dela de max(10%, 0.03m absolu) (lecon du switch 0708).
(b) guarded_apply: un blocage n'est legitime que si la regression est reelle
    en METRES (l'arcmin explose a courte portee). Par cam bloquante:
    arcmin_reg > tol ET (median_m_reg > 0.05m OU max_m_reg > 3m).
    Cams sans donnees metres: regle arcmin pure (conservateur).

Validation sandbox: 24 -> 26 deltas acceptes (Vice City 05 -0.83', 1500 Ocean
Dr -1.09' liberes), mediane 1.889' -> 1.835' (RECORD), metres 0.187m stables,
CI vert. Idempotent."""
import sys

# (a)
p = 'tools/ci_healthcheck.py'
src = open(p).read()
if 'tol_abs' in src:
    print(f'ok  {p}: deja patche')
else:
    old = """            if bm_m > 0 and (cm_m - bm_m) / bm_m * 100 > TOL_MEDIAN_PCT:
                fails.append(f'RMS-M: mediane metres degradee {bm_m}m -> {cm_m}m '
                             f'(> {TOL_MEDIAN_PCT}% tolere)')"""
    new = """            # tolerance plancher (lecon 0708): la mediane sur 119 cams bouge
            # par pas discrets — un switch de point median de 0.02m = 12% a
            # 0.17m sans vraie regression. Fail seulement au-dela de
            # max(TOL%, 0.03m absolu).
            tol_abs = max(bm_m * TOL_MEDIAN_PCT / 100.0, 0.03)
            if bm_m > 0 and (cm_m - bm_m) > tol_abs:
                fails.append(f'RMS-M: mediane metres degradee {bm_m}m -> {cm_m}m '
                             f'(> max({TOL_MEDIAN_PCT}%, 0.03m) tolere)')"""
    assert old in src, 'ancre CI introuvable'
    src = src.replace(old, new, 1)
    open(p, 'w').write(src)
    print(f'EDIT {p}: tolerance plancher')

# (b)
p = 'tools/refine/guarded_apply.py'
src = open(p).read()
if 'GUARD-DUAL-V1' in src:
    print(f'ok  {p}: deja patche')
    sys.exit(0)

old = "from common import cam_rms as _common_cam_rms"
new = "from common import cam_rms as _common_cam_rms\nfrom common import cam_rms_dual as _common_cam_rms_dual"
assert old in src, 'ancre import introuvable'
src = src.replace(old, new, 1)

old = """def cam_rms(cam_name, cams, lms):
    return _common_cam_rms(cam_name, cam_state=cams.get(cam_name), lms=lms)"""
new = """def cam_rms(cam_name, cams, lms):
    return _common_cam_rms(cam_name, cam_state=cams.get(cam_name), lms=lms)


def cam_m(cam_name, cams, lms):
    \\"\\"\\"(median_m, max_m) — contexte metres pour le guard dual [GUARD-DUAL-V1].\\"\\"\\"
    d = _common_cam_rms_dual(cam_name, cam_state=cams.get(cam_name), lms=lms)
    return (None, None) if d is None else (d['median_m'], d['max_m'])"""
assert old in src, 'ancre cam_rms introuvable'
src = src.replace(old, new, 1)

old = "    baseline0 = {c: cam_rms(c, cams, lms) for c in md.pixels if c in cams}"
new = """    baseline0 = {c: cam_rms(c, cams, lms) for c in md.pixels if c in cams}
    baseline0_m = {c: cam_m(c, cams, lms) for c in md.pixels if c in cams}"""
assert old in src, 'ancre baseline0 introuvable'
src = src.replace(old, new, 1)

old = """        # cumulative guard: regression measured against the session baseline
        worst = max((after[a] - (baseline0.get(a) if baseline0.get(a) is not None else before[a])) for a in valid)
        net = sum((after[a] - before[a]) for a in valid)
        if worst <= args.tol and net < -1e-6:"""
new = """        # cumulative guard: regression measured against the session baseline
        # GUARD-DUAL-V1 (2026-07-08): un blocage n'est legitime que si la
        # regression est reelle en METRES aussi (l'arcmin explose a courte
        # portee: 0.3' sur une cam de rue = millimetres). Par cam: bloque si
        # arcmin_reg > tol ET (median_m_reg > 0.05m OU max_m_reg > 3m) — le OU
        # couvre une obs lointaine unique wreckee que la mediane cacherait.
        # Cams sans donnees metres: regle arcmin pure (conservateur).
        worst = max((after[a] - (baseline0.get(a) if baseline0.get(a) is not None else before[a])) for a in valid)
        net = sum((after[a] - before[a]) for a in valid)
        blocked = False
        for a in valid:
            reg = after[a] - (baseline0.get(a) if baseline0.get(a) is not None else before[a])
            if reg <= args.tol:
                continue
            bm, bx = baseline0_m.get(a, (None, None))
            am, ax = cam_m(a, cams, lms)
            if bm is None or am is None:
                blocked = True
                break
            med_reg = am - bm
            max_reg = (ax - bx) if (ax is not None and bx is not None) else None
            if med_reg > 0.05 or (max_reg is not None and max_reg > 3.0):
                blocked = True
                break
        if not blocked and net < -1e-6:"""
assert old in src, 'ancre worst/net introuvable'
src = src.replace(old, new, 1)
open(p, 'w').write(src)
print(f'EDIT {p}: GUARD-DUAL-V1')
print('\\nPhase B tranche 2 en place.')
