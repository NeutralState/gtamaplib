"""Patch CALIB-DESIGN-V1.1: feedback d'Alexandre sur la passe design.

- Bouton Suspicious RETIRE (redondant avec le Triage board; /api/suspicious
  reste dispo cote serveur). Refs JS stubbees, y compris le .click()
  programmatique du pixel editor.
- Chip "indep" -> rangee de stat pleine largeur integree au panneau de sliders
  (fini la pilule orpheline)
- Visibilite des toggles par mode: Rays = Map seulement, Dual = Camera
  seulement, Assist = Camera seulement, rien en 3D

PREREQUIS: patch_design.py applique. Idempotent. Backup: .bak_design11
"""
import shutil, sys

P = 'tools/calib.html'
s = open(P).read()
if 'CALIB-DESIGN-V1.1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_design11')

old = '<button class="btn btn-ghost btn-ghost-amber" id="btn-suspicious">\u26a0 Suspicious</button>'
assert old in s, 'bouton suspicious introuvable'
s = s.replace(old, '<!-- [CALIB-DESIGN-V1.1] Suspicious retire: la detection vit dans le Triage board (/api/suspicious reste dispo) -->', 1)
old = "const btnSuspicious = document.getElementById('btn-suspicious');"
assert old in s
s = s.replace(old, "const btnSuspicious = {disabled:true, classList:{add(){},remove(){}}, style:{}, addEventListener(){}, click(){}};  // [CALIB-DESIGN-V1.1] stub", 1)

old = '.indep-chip{font-family:var(--mono);font-size:11px;padding:5px 10px;border-radius:5px;background:#0f1a2e;border:1px solid var(--blue);color:var(--blue);text-align:center;white-space:nowrap}'
assert old in s, 'css indep-chip introuvable'
s = s.replace(old, "/* [CALIB-DESIGN-V1.1] indep = rangee de stat pleine largeur, alignee au panneau */\n.indep-chip{font-family:var(--mono);font-size:11px;display:flex;align-items:center;justify-content:space-between;\n  width:100%;box-sizing:border-box;padding:8px 12px;border-radius:var(--radius,6px);\n  background:var(--surface2);border:1px solid var(--border);color:var(--blue);white-space:nowrap}\n.indep-chip::before{content:'LOSS INDEPENDANT';font-size:9px;letter-spacing:1px;color:var(--dim)}", 1)
old = '<div class="indep-chip"><span style="font-size:9px;color:var(--dim)">indep </span><span class="v" id="loss-indep">\u2014</span></div>'
assert old in s, 'markup indep introuvable'
s = s.replace(old, '<div class="indep-chip"><span class="v" id="loss-indep">\u2014</span></div>', 1)

css = '/* ══ [CALIB-DESIGN-V1.1] visibilite des toggles par mode + retrait Suspicious ══ */\n#rays-toggle{display:none !important}\nbody.view-map #rays-toggle{display:inline-flex !important}\n#dual-toggle{display:none !important}\nbody:not(.view-map):not(.view-view3d) #dual-toggle{display:inline-flex !important}\n#proj-toggle{display:none !important}\nbody:not(.view-map):not(.view-view3d) #proj-toggle{display:inline-flex !important}\n'
assert '</style>' in s
s = s.replace('</style>', '\n' + css + '</style>', 1)
open(P, 'w').write(s)
print('CALIB-DESIGN-V1.1 applique. Backup: .bak_design11')
