"""patch_delete_btn.py — DELETE-BTN-V1 (2026-07-03 soir).

The missing verb: a 🗑 button in the pending confirm bar, shown only when
editing an EXISTING marking (hidden for new placements). confirm() guard,
calls the existing /api/delete_pixel, refreshes projections + ghosts.
Live-tested: delete removes the pixel (42 -> 41), hidden on 'place',
zero JS errors. Requires patch_edit_mode.py. Idempotent. Hard refresh.
"""
import shutil, sys
P = 'tools/calib.html'
s = open(P).read()
if 'DELETE-BTN-V1' in s:
    print('deja patche'); sys.exit(0)
assert 'EDIT-MODE-V1' in s, 'prerequis: patch_edit_mode.py'
shutil.copy(P, P + '.bak_delbtn')
old = '    <button id="mk-confirm-rv" style="background:#ffffff10;border:1px solid var(--border,#333);color:var(--text,#ddd);\n      border-radius:5px;padding:3px 10px;cursor:pointer;font-family:inherit;font-size:11px">↩ revert esc</button>'
assert old in s, 'anchor bouton rv'
s = s.replace(old, old + '\n    <button id="mk-confirm-del" title="delete this marking (removes the pixel from pixels.json)" style="background:#f8717118;border:1px solid #f87171;color:#f87171;\n      border-radius:5px;padding:3px 9px;cursor:pointer;font-family:inherit;font-size:11px">🗑</button><!-- [DELETE-BTN-V1] -->', 1)
old = "  window._mkEnterPending = function(d) {\n    window._mkPending = { kind: d.kind, lm: d.lm, px: d.px.slice(),\n                          orig: d.orig ? d.orig.slice() : null, isNew: d.isNew };\n    bar.style.display = 'block';"
assert old in s, 'anchor enterPending'
s = s.replace(old, old + "\n    document.getElementById('mk-confirm-del').style.display = d.kind === 'move' ? '' : 'none';  // [DELETE-BTN-V1]", 1)
old = "  document.getElementById('mk-confirm-ok').addEventListener('click', confirmPending);\n  document.getElementById('mk-confirm-rv').addEventListener('click', revertPending);"
assert old in s, 'anchor handlers'
s = s.replace(old, old + '\n  document.getElementById(\'mk-confirm-del\').addEventListener(\'click\', async () => {   // [DELETE-BTN-V1]\n    const pd = window._mkPending;\n    if (!pd) return;\n    if (!confirm(\'Delete the marking "\' + pd.lm + \'" on this cam? (pixel removed from pixels.json)\')) return;\n    window._mkPending = null;\n    bar.style.display = \'none\';\n    const res = await fetch(\'/api/delete_pixel?cam=\' + encodeURIComponent(currentCam) +\n      \'&lm=\' + encodeURIComponent(pd.lm)).then(r => r.json());\n    if (res.ok) {\n      await loadProjections();\n      if (window._refreshGhosts) window._refreshGhosts();\n      const t = document.getElementById(\'tri-toast\');\n      if (t) {\n        document.getElementById(\'tri-toast-title\').textContent = pd.lm + \' marking deleted\';\n        document.getElementById(\'tri-toast-meta\').textContent = \'\';\n        t.style.display = \'block\';\n        setTimeout(() => { t.style.display = \'none\'; }, 2200);\n      }\n    } else { alert(res.error || \'delete failed\'); }\n  });', 1)
open(P, 'w').write(s)
print('DELETE-BTN-V1 applique. Hard refresh.')
