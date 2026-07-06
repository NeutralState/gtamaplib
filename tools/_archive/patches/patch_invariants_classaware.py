"""Patch CLASS-AWARE-V1: invariants.py compare seulement les DOF verrouillees
par classe V2 a la reference leaks. Une classe C qui refine son ypr (sanctionne)
ne declenche plus de faux positif LEAK.
Idempotent. Backup: .bak_classaware
"""
import shutil, sys
P = 'tools/audit/invariants.py'
s = open(P).read()
if 'CLASS-AWARE-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_classaware')
old = "from leak_cam_audit import is_triangulation_trusted"
assert old in s
s = s.replace(old, "from leak_cam_audit import is_triangulation_trusted, get_class\n\n# [CLASS-AWARE-V1] DOF verrouillees par classe V2 — seules celles-la sont\n# comparees a la reference gelee. C laisse ypr libre, Cm laisse ypr+fov.\n_LOCKED_KEYS = {\n    'A': ('xyz', 'ypr', 'fov'),\n    'B': ('xyz', 'ypr', 'fov'),\n    'C': ('xyz', 'fov'),\n    'Cm': ('xyz',),\n}\ndef _locked_keys(cam_name):\n    cls = (get_class(cam_name, cameras=md.cameras) or '')\n    for pref in ('Cm', 'A', 'B', 'C'):\n        if cls.startswith(pref):\n            return _LOCKED_KEYS[pref]\n    return ('xyz', 'ypr', 'fov')", 1)
old = '''            c = md.cameras[n]
            for k in ("xyz", "ypr", "fov"):'''
assert old in s
s = s.replace(old, '''            c = md.cameras[n]
            for k in _locked_keys(n):  # [CLASS-AWARE-V1]''', 1)
open(P, 'w').write(s)
print('invariants class-aware. Backup: .bak_classaware')
