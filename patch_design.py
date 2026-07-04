"""Patch CALIB-DESIGN-V1: passe visuelle du header/toolbar de calib.html.

- Tokens raffines (fond plus profond, bordures plus subtiles, radius 6px commun)
- Camera/Map/3D en segmented control (conteneur pilule, actif vert plein)
- Tous les controles du header a 28px uniformes
- Export/Suspicious/Triage en ghost buttons (sobres au repos, teinte au hover)
- Save garde son statut d'unique action pleine (lueur verte subtile)
- Nettoyage: styles morts du bouton Optimize decommissionne

PREREQUIS: patch decom applique. Idempotent. Backup: tools/calib.html.bak_design
Revert: supprimer le bloc [CALIB-DESIGN-V1] du <style> + restaurer les 3 boutons.
"""
import shutil, sys

P = 'tools/calib.html'
s = open(P).read()
if 'CALIB-DESIGN-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_design')

old = '<button class="btn" id="btn-export" style="background:#0e7490;color:#fff">\u2b07 Export</button>'
assert old in s, 'bouton export introuvable'
s = s.replace(old, '<button class="btn btn-ghost" id="btn-export">\u2b07 Export</button>', 1)
old = '<button class="btn" id="btn-suspicious" style="background:#1c1c26;color:#f59e0b;border:1px solid #f59e0b">\u26a0 Suspicious</button>'
assert old in s, 'bouton suspicious introuvable'
s = s.replace(old, '<button class="btn btn-ghost btn-ghost-amber" id="btn-suspicious">\u26a0 Suspicious</button>', 1)
old = '<button class="btn" id="triage-btn" style="background:#1c1c26;color:#e74c3c;border:1px solid #e74c3c" title="Triage: cams categorisees avec action recommandee">Triage</button>'
assert old in s, 'bouton triage introuvable'
s = s.replace(old, '<button class="btn btn-ghost btn-ghost-red" id="triage-btn" title="Triage: cams categorisees avec action recommandee">Triage</button>', 1)

css = "/* ══ [CALIB-DESIGN-V1] passe visuelle 2026-07-02 — couche d'override, revert = supprimer ce bloc ══ */\n:root{ --bg:#0b0b10; --surface:#10101a; --surface2:#171722; --border:#222236; --radius:6px; }\nheader{ padding:0 16px; height:46px; gap:8px;\n  background:linear-gradient(180deg,#13131e 0%,#0e0e16 100%);\n  border-bottom:1px solid #1c1c2c; }\nheader .view-toggle{height:28px; display:inline-flex; align-items:stretch;\n  border-radius:var(--radius); overflow:hidden; border:1px solid var(--border); background:var(--surface2)}\nheader .view-toggle button[data-view]{\n  font-family:var(--mono); font-size:11px; font-weight:600;\n  height:100%; padding:0 14px; border:none; border-radius:0; cursor:pointer;\n  background:transparent; color:var(--mid);\n  border-right:1px solid var(--border); transition:color .12s, background .12s; }\nheader .view-toggle button[data-view]:last-of-type{border-right:none}\nheader .view-toggle button[data-view]:hover{color:var(--text)}\nheader .view-toggle button[data-view].active{background:var(--green); color:#08120a; font-weight:700}\nheader .btn, header .rays-toggle, header .nav-link, .cam-toggle-btn{\n  height:28px !important; display:inline-flex; align-items:center;\n  border-radius:var(--radius); font-weight:600; letter-spacing:.2px;\n  padding:0 12px; box-sizing:border-box; }\nheader .rays-toggle{background:transparent; border:1px solid var(--border)}\nheader .rays-toggle:hover{border-color:var(--mid); color:var(--text)}\nheader .rays-toggle.active{background:var(--blue); border-color:var(--blue); color:#04101f}\nbody.assist-on #proj-toggle{background:#f59e0b !important; border-color:#f59e0b !important; color:#1a1002 !important}\n.btn-ghost{background:transparent !important; color:var(--mid) !important; border:1px solid var(--border) !important}\n.btn-ghost:hover{color:var(--text) !important; border-color:var(--mid) !important; background:var(--surface2) !important}\n.btn-ghost-amber:hover{color:#f59e0b !important; border-color:#f59e0b88 !important}\n.btn-ghost-red:hover{color:#f87171 !important; border-color:#f8717188 !important}\n.btn-save:not(:disabled){box-shadow:0 1px 8px -2px #4ade8055}\n.btn-reset{background:transparent}\n.chip{height:28px; display:inline-flex; align-items:center; gap:5px;\n  padding:0 11px; border-radius:var(--radius);\n  background:var(--surface2); border:1px solid var(--border)}\n.ls-header #cam-search{border-radius:var(--radius); height:28px; box-sizing:border-box}\n.ls-list::-webkit-scrollbar{width:4px}\n.btn-opt{display:none}\n\n"
assert '</style>' in s
s = s.replace('</style>', '\n' + css + '</style>', 1)
open(P, 'w').write(s)
print('CALIB-DESIGN-V1 applique. Backup: .bak_design')
