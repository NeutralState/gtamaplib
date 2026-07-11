#!/usr/bin/env python3
# PROVENANCE-V2 tranche 1 (2026-07-08): journal append-only events.jsonl.
# 1. common.log_event(tool, action, **payload) -> gtamapdata/events.jsonl
#    (commite). Historique de provenance ET filet de recuperation.
# 2. Cable dans les 3 ecrivains: triangulate_lm --apply (old/new xyz),
#    guarded_apply --apply (resume), collision_scan --apply (war_fix).
# Idempotent.
import sys

p = 'tools/common.py'
src = open(p).read()
if 'def log_event' in src:
    print(f'ok  {p}: deja patche')
else:
    anchor = '_COV_CACHE_CAMS = None'
    block = '''# ── PROVENANCE-V2 (2026-07-08): journal append-only ─────────────────────
# Chaque ecriture outillee loggue dans gtamapdata/events.jsonl (commite).
# Historique de provenance ET filet de recuperation (la quarantaine
# d'orphelins loggue l'ancien xyz -> reversible).

def log_event(tool, action, **payload):
    import os as _os, datetime as _dt
    base = _os.path.dirname(_os.path.abspath(__file__))
    p = _os.path.join(base, '..', 'gtamapdata', 'events.jsonl')
    ev = {'ts': _dt.datetime.now().isoformat(timespec='seconds'),
          'tool': tool, 'action': action}
    ev.update(payload)
    try:
        with open(p, 'a') as f:
            f.write(json.dumps(ev, ensure_ascii=True) + '\\n')
    except Exception:
        pass


'''
    assert anchor in src, 'ancre _COV_CACHE_CAMS introuvable (SIGMA-POOL requis)'
    src = src.replace(anchor, block + anchor, 1)
    open(p, 'w').write(src)
    print(f'EDIT {p}: log_event')

p = 'tools/triangulate_lm.py'
src = open(p).read()
if "log_event('triangulate_lm'" in src:
    print(f'ok  {p}: deja patche')
else:
    old = '    print(f"APPLIED: landmarks.json updated.")'
    new = '''    try:
        from common import log_event
        log_event('triangulate_lm', 'retriangulate', lm=args.lm_name,
                  old_xyz=cur_xyz, new_xyz=[round(v, 4) for v in new_xyz],
                  kept=kept, max_res=round(max_res, 3))
    except Exception:
        pass
    print(f"APPLIED: landmarks.json updated.")'''
    assert old in src, 'ancre APPLIED triangulate introuvable'
    src = src.replace(old, new, 1)
    open(p, 'w').write(src)
    print(f'EDIT {p}: log retriangulate')

p = 'tools/refine/guarded_apply.py'
src = open(p).read()
if "log_event('guarded_apply'" in src:
    print(f'ok  {p}: deja patche')
else:
    old = '''    print(f"\\nAPPLIED: {n_c} cams, {n_l} landmarks written (backups .bak_guarded).")'''
    new = '''    try:
        from common import log_event
        log_event('guarded_apply', 'apply', n_cams=n_c, n_lms=n_l,
                  n_accepted=len(accepted))
    except Exception:
        pass
    print(f"\\nAPPLIED: {n_c} cams, {n_l} landmarks written (backups .bak_guarded).")'''
    assert old in src, 'ancre APPLIED guarded introuvable'
    src = src.replace(old, new, 1)
    open(p, 'w').write(src)
    print(f'EDIT {p}: log apply')

p = 'tools/audit/collision_scan.py'
src = open(p).read()
if "log_event('collision_scan'" in src:
    print(f'ok  {p}: deja patche')
else:
    old = """            print(f"  APPLIED {lm}: excl {f['excl']}, retri {resid:.2f}' / {delta:.1f}m")"""
    new = """            try:
                from common import log_event
                log_event('collision_scan', 'war_fix', lm=lm, excl=f['excl'],
                          resid=round(resid, 3), delta_m=round(delta, 2))
            except Exception:
                pass
            print(f"  APPLIED {lm}: excl {f['excl']}, retri {resid:.2f}' / {delta:.1f}m")"""
    assert old in src, 'ancre APPLIED scan introuvable'
    src = src.replace(old, new, 1)
    open(p, 'w').write(src)
    print(f'EDIT {p}: log war_fix')
print('PROVENANCE-V2 tranche 1 en place.')
