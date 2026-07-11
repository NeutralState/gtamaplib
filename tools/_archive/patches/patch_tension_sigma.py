#!/usr/bin/env python3
# TENSION-SIGMA-V1 (Phase B, derniere tranche): le tension-audit annote chaque
# bloqueur (sigma pose) et chaque LM charniere (sigma m). Lecture instantanee:
# un bloqueur a petit sigma = objection credible (vraie tension); un bloqueur
# a gros sigma = lui-meme le suspect. Idempotent.
import sys
p = 'tools/audit/tension_audit.py'
src = open(p).read()
if 'TENSION-SIGMA-V1' in src:
    print('ok  deja patche'); sys.exit(0)

old = "from common import cam_rms as _common_cam_rms"
new = "from common import cam_rms as _common_cam_rms\nfrom common import lm_sigma_m, cam_sigma_pos"
assert old in src, 'ancre import introuvable'
src = src.replace(old, new, 1)

old = '''        for b, r in t["blockers"][:4]:
            via = ', '.join(t["med"].get(b, [])[:3]) or '(pose seule)'
            print(f"      bloque par {b}  (+{r:.2f}')  via: {via}")'''
new = '''        for b, r in t["blockers"][:4]:
            # TENSION-SIGMA-V1: contexte d'incertitude — un bloqueur a gros
            # sigma est lui-meme le suspect; une charniere a petit sigma est
            # bien contrainte (son desaccord est significatif).
            sb = cam_sigma_pos(b)
            sb_txt = f", sig {sb:.0f}m" if sb is not None else ""
            via_parts = []
            for l in t["med"].get(b, [])[:3]:
                sl = lm_sigma_m(l)
                via_parts.append(f"{l} (s {sl:.1f}m)" if sl is not None else l)
            via = ', '.join(via_parts) or '(pose seule)'
            print(f"      bloque par {b}  (+{r:.2f}'{sb_txt})  via: {via}")'''
assert old in src, 'ancre blockers introuvable'
src = src.replace(old, new, 1)

old = '''    for cam_name, (n, g) in sorted(blocker_score.items(), key=lambda x: -x[1][1])[:15]:
        print(f"  bloque {n:3d} deltas, {g:8.1f}' de gain en otage   {cam_name}")'''
new = '''    for cam_name, (n, g) in sorted(blocker_score.items(), key=lambda x: -x[1][1])[:15]:
        s = cam_sigma_pos(cam_name)
        s_txt = f"sig {s:6.1f}m" if s is not None else "sig     ?"
        print(f"  bloque {n:3d} deltas, {g:8.1f}' en otage  {s_txt}   {cam_name}")'''
assert old in src, 'ancre leaderboard bloqueurs introuvable'
src = src.replace(old, new, 1)

old = '''    for lm_name, (n, g) in sorted(mediator_score.items(), key=lambda x: -x[1][1])[:15]:
        print(f"  implique dans {n:3d} conflits, ~{g:7.1f}'   {lm_name}")'''
new = '''    for lm_name, (n, g) in sorted(mediator_score.items(), key=lambda x: -x[1][1])[:15]:
        s = lm_sigma_m(lm_name)
        s_txt = f"sig {s:6.1f}m" if s is not None else "sig     ?"
        print(f"  implique dans {n:3d} conflits, ~{g:7.1f}'  {s_txt}   {lm_name}")'''
assert old in src, 'ancre leaderboard mediateurs introuvable'
src = src.replace(old, new, 1)
open(p, 'w').write(src)
print('EDIT tension_audit: TENSION-SIGMA-V1')
