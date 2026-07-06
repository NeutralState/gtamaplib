"""patch_adjust_fix.py — ADJFIX-V1 (2026-07-04).

The adjust panel visually did NOTHING: draw() rewrites frameImg.style.cssText
on every repaint, erasing the inline filter within milliseconds of any mouse
move. The filter now lives in a CSS class (classes survive cssText rewrites).
Verified headless: filter persists across forced draw() calls, auto-reset on
close intact. Requires patch_ui_fixes.py chain. Idempotent. Hard refresh.
"""
import shutil, sys
P = 'tools/calib.html'
s = open(P).read()
if 'ADJFIX-V1' in s:
    print('deja patche'); sys.exit(0)
assert 'UIFIX-V1' in s, 'prerequis: patch_ui_fixes.py'
shutil.copy(P, P + '.bak_adjfix')
anchor = """
/* [PANEL-V3] pose = read-only display, terminal-first."""
assert anchor in s
s = s.replace(anchor, '\n/* [ADJFIX-V1] filter via class: draw() rewrites frameImg.style.cssText\n   every frame, wiping inline filters — a class survives */\n#frame-img.mkadj-on, img.mkadj-on { filter: url(#mkadj) !important; }\n\n' + anchor, 1)
old = "    const active = PARAMS.some(p => st[p[0]] !== p[3]);\n    frameImg.style.filter = active ? 'url(#mkadj)' : '';\n    window._mkAdjActive = active;"
assert old in s, 'anchor applyAdj'
s = s.replace(old, "    const active = PARAMS.some(p => st[p[0]] !== p[3]);\n    frameImg.classList.toggle('mkadj-on', active);   // [ADJFIX-V1]\n    window._mkAdjActive = active;", 1)
open(P, 'w').write(s)
print('ADJFIX-V1 applique. Hard refresh.')
