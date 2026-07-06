"""Patch EXCL-AWARE-V1: lm_uncertainty.py honore excluded_markings.json.

Meme trou systemique que le bundle avait (fixe le 2026-07-01): une source
dont le marking est exclu participait au Monte-Carlo d'incertitude du LM.
Effet mesure: Wildfire Scooters (S) radius 168m -> 7.0m apres exclusion
du marking Chase (2)(A) empoisonne.

Idempotent. Backup: .bak_excl
"""
import shutil, sys
P = 'tools/audit/lm_uncertainty.py'
s = open(P).read()
if 'EXCL-AWARE-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_excl')
old = """    srcs = [c for c in (d.get('source_cameras') or []) if c in cams]
    if len(srcs) < 2:
        return None"""
assert old in s, 'anchor introuvable'
new = """    # [EXCL-AWARE-V1] honorer excluded_markings.json (meme trou que le
    # bundle avait: une source dont le marking est exclu ne doit pas
    # participer a l'incertitude du LM)
    from common import is_excluded_marking as _iem
    srcs = [c for c in (d.get('source_cameras') or [])
            if c in cams and not _iem(c, lm_name)]
    if len(srcs) < 2:
        return None"""
s = s.replace(old, new, 1)
open(P, 'w').write(s)
print('EXCL-AWARE-V1 applique')
