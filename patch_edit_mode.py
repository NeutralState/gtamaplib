"""patch_edit_mode.py — EDIT-MODE-V1 (2026-07-03 soir).

Release = REVIEW, not commit. Any marking drag now enters a PENDING state:
  - the original stays visible as a faint dashed ghost with a connector
  - a confirm bar shows the delta BEFORE -> AFTER (the decision data)
  - bare arrows nudge 0.1 px (~0.09 arcmin) — Shift = 1 px — re-drag allowed
  - Enter / ✓ = commit to the API · Esc / ↩ = revert, nothing written
Kills accidental-drag damage and hosts the sub-pixel refinement step.

Also fixes two latent bugs found while testing:
  1. calib.html: liveDelta read `p.proj` but the field is `p.projected` —
     the loupe delta of MARKING-V1 was silently dead since delivery.
  2. server.py: GTAMAP_DIR was HARDCODED to ~/Downloads/gtamaplib-main —
     works on this machine by coincidence, breaks for any collaborator
     (set_pixel/add_pixel FileNotFoundError). Now derived from the file
     location.

Live-tested headless: pending, 0.1px nudge, revert (data untouched),
confirm (data committed, delta bar "0.05' -> 130.20'" live). Zero JS errors.
Requires MARKING-V1 + patch_ui_polish(2). Idempotent. Backups: .bak_editmode.
Restart server + hard refresh after.
"""
import shutil, sys
# ---- server.py ----
P = 'tools/server.py'
s = open(P).read()
if 'EDIT-MODE-V1' in s:
    print('server: deja patche')
else:
    shutil.copy(P, P + '.bak_editmode')
    old = 'GTAMAP_DIR = os.path.expanduser("~/Downloads/gtamaplib-main")'
    assert old in s, 'anchor GTAMAP_DIR'
    s = s.replace(old, 'GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # [EDIT-MODE-V1] portable (was hardcoded ~/Downloads/gtamaplib-main)', 1)
    open(P, 'w').write(s)
    print('tools/server.py: GTAMAP_DIR portable')

# ---- calib.html ----
P = 'tools/calib.html'
s = open(P).read()
if 'EDIT-MODE-V1' in s:
    print('calib: deja patche'); sys.exit(0)
assert 'MARKING-V1' in s and 'POLISH-V3.1' in s, 'prerequis: marking + polish + polish2'
shutil.copy(P, P + '.bak_editmode')

# fix .proj -> .projected (MARKING-V1 liveDelta etait mort)
s = s.replace('if (!p || !p.proj || !camData?.size) return null;',
              'if (!p || !p.projected || !camData?.size) return null;')
s = s.replace('p.proj[0]', 'p.projected[0]').replace('p.proj[1]', 'p.projected[1]')

# barre + couche JS avant </body>
i = s.rindex('</body>')
s = s[:i] + '<!-- [EDIT-MODE-V1] pending marking confirm bar -->\n<div id="mk-confirm" style="display:none;position:fixed;z-index:402;background:#0a0a10f2;\n  border:1px solid #f59e0b;border-radius:7px;padding:7px 10px;box-shadow:0 6px 22px #000d;\n  font-family:var(--mono,monospace);font-size:11px;color:var(--text,#ddd)">\n  <div id="mk-confirm-title" style="font-weight:700;margin-bottom:2px"></div>\n  <div id="mk-confirm-delta" style="color:var(--mid,#999);margin-bottom:6px"></div>\n  <div style="display:flex;gap:6px;align-items:center">\n    <button id="mk-confirm-ok" style="background:#4ade8022;border:1px solid #4ade80;color:#4ade80;\n      border-radius:5px;padding:3px 10px;cursor:pointer;font-family:inherit;font-size:11px">✓ confirm ⏎</button>\n    <button id="mk-confirm-rv" style="background:#ffffff10;border:1px solid var(--border,#333);color:var(--text,#ddd);\n      border-radius:5px;padding:3px 10px;cursor:pointer;font-family:inherit;font-size:11px">↩ revert esc</button>\n    <span style="color:var(--dim,#666);font-size:9px">arrows = 0.1px · shift = 1px</span>\n  </div>\n</div>\n' + '\n<script>\n// ══ [EDIT-MODE-V1] pending markings: release = review, not commit ══\n// Any drag release enters a PENDING state: the original stays visible as a\n// faint ghost with a connector, the confirm bar shows delta before -> after,\n// bare arrows nudge 0.1px (Shift = 1px), Enter confirms, Esc reverts.\n// Nothing touches the API until you confirm. Kills accidental-drag damage\n// and hosts the sub-pixel refinement step.\n(() => {\n  const mk = window._mk;\n  const bar = document.getElementById(\'mk-confirm\');\n  const barT = document.getElementById(\'mk-confirm-title\');\n  const barD = document.getElementById(\'mk-confirm-delta\');\n\n  function fmtD(v) { return v == null ? \'—\' : v.toFixed(2) + "\'"; }\n\n  function liveDeltaOf(lm, px) {\n    const p = projections.find(x => x.name === lm);\n    if (!p || !p.projected || !camData?.size) return null;\n    const [w, h] = camData.size;\n    const hf = params.hfov;\n    if (!hf) return null;\n    const vf = 2 * Math.atan(Math.tan(hf * Math.PI / 360) * h / w) * 180 / Math.PI;\n    return Math.hypot((p.projected[0] - px[0]) * hf / w * 60, (p.projected[1] - px[1]) * vf / h * 60);\n  }\n\n  window._mkPending = null;\n\n  function paintPendingStatic() {\n    const pd = window._mkPending;\n    if (!pd) return;\n    // original en fantome pale + connecteur\n    if (pd.orig) {\n      const [ox, oy] = toCanvas(pd.orig[0], pd.orig[1]);\n      const [nx, ny] = toCanvas(pd.px[0], pd.px[1]);\n      ctx.save();\n      ctx.globalAlpha = 0.45;\n      ctx.setLineDash([3, 3]);\n      ctx.strokeStyle = \'#8a8a95\'; ctx.lineWidth = 1;\n      ctx.beginPath(); ctx.arc(ox, oy, 5.5, 0, Math.PI * 2); ctx.stroke();\n      ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(nx, ny); ctx.stroke();\n      ctx.restore();\n    }\n    const [nx, ny] = toCanvas(pd.px[0], pd.px[1]);\n    ctx.save();\n    ctx.shadowColor = \'#f59e0b\'; ctx.shadowBlur = 8;\n    ctx.strokeStyle = \'#f59e0b\'; ctx.lineWidth = 1.8;\n    ctx.beginPath(); ctx.arc(nx, ny, 6.5, 0, Math.PI * 2); ctx.stroke();\n    ctx.beginPath(); ctx.arc(nx, ny, 1.6, 0, Math.PI * 2);\n    ctx.fillStyle = \'#f59e0b\'; ctx.fill();\n    ctx.restore();\n  }\n  // repeindre le pending par-dessus chaque draw()\n  const _edDraw = draw;\n  draw = function() { _edDraw(); paintPendingStatic(); };\n\n  function placeBar() {\n    const pd = window._mkPending;\n    if (!pd) return;\n    const [nx, ny] = toCanvas(pd.px[0], pd.px[1]);\n    const r = getMainPaneRect();\n    bar.style.left = Math.min(window.innerWidth - 320, Math.max(8, r.left + nx + 18)) + \'px\';\n    bar.style.top = Math.max(8, r.top + ny - 90) + \'px\';\n  }\n\n  function refreshBar() {\n    const pd = window._mkPending;\n    if (!pd) return;\n    barT.textContent = pd.lm + \'  @ \' + pd.px[0].toFixed(1) + \', \' + pd.px[1].toFixed(1);\n    const before = pd.orig ? liveDeltaOf(pd.lm, pd.orig) : null;\n    const after = liveDeltaOf(pd.lm, pd.px);\n    barD.textContent = pd.orig\n      ? \'d: \' + fmtD(before) + \'  →  \' + fmtD(after)\n      : (after != null ? \'d = \' + fmtD(after) : \'new marking\');\n    placeBar();\n  }\n\n  window._mkEnterPending = function(d) {\n    window._mkPending = { kind: d.kind, lm: d.lm, px: d.px.slice(),\n                          orig: d.orig ? d.orig.slice() : null, isNew: d.isNew };\n    bar.style.display = \'block\';\n    refreshBar();\n    draw();\n  };\n\n  async function confirmPending() {\n    const pd = window._mkPending;\n    if (!pd) return;\n    window._mkPending = null;\n    bar.style.display = \'none\';\n    const nx = Math.round(pd.px[0] * 10) / 10, ny = Math.round(pd.px[1] * 10) / 10;\n    const ep = pd.kind === \'place\' ? \'/api/add_pixel\' : \'/api/set_pixel\';\n    const res = await fetch(ep + \'?cam=\' + encodeURIComponent(currentCam) +\n      \'&lm=\' + encodeURIComponent(pd.lm) + \'&px=\' + nx + \'&py=\' + ny +\n      (pd.isNew ? \'&new=1\' : \'\')).then(r => r.json());\n    if (res.ok) {\n      addPxMode = false;\n      await loadProjections();\n      if (window._refreshGhosts) window._refreshGhosts();\n      const next = (ghostMarkers1 || []).find(g => g.type === \'point\' && g.priority === 1 && g.name !== pd.lm);\n      const t = document.getElementById(\'tri-toast\');\n      if (t) {\n        document.getElementById(\'tri-toast-title\').textContent = pd.lm + \' @ \' + nx + \',\' + ny + \' saved\';\n        document.getElementById(\'tri-toast-meta\').textContent = next ? \'next P1: \' + next.name : \'\';\n        t.style.display = \'block\';\n        setTimeout(() => { t.style.display = \'none\'; }, 2400);\n      }\n    } else { alert(res.error || \'save failed\'); }\n  }\n\n  function revertPending() {\n    window._mkPending = null;\n    bar.style.display = \'none\';\n    addPxMode = false;\n    draw();\n  }\n  window._mkConfirmPending = confirmPending;\n  window._mkRevertPending = revertPending;\n\n  document.getElementById(\'mk-confirm-ok\').addEventListener(\'click\', confirmPending);\n  document.getElementById(\'mk-confirm-rv\').addEventListener(\'click\', revertPending);\n\n  document.addEventListener(\'keydown\', e => {\n    const pd = window._mkPending;\n    if (!pd) return;\n    if (e.target.tagName === \'INPUT\' || e.target.tagName === \'TEXTAREA\') return;\n    if (e.key === \'Enter\') { e.preventDefault(); e.stopImmediatePropagation(); confirmPending(); return; }\n    if (e.key === \'Escape\') { e.preventDefault(); e.stopImmediatePropagation(); revertPending(); return; }\n    const step = e.shiftKey ? 1.0 : 0.1;\n    const map = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };\n    const d = map[e.key];\n    if (!d) return;\n    e.preventDefault(); e.stopImmediatePropagation();\n    pd.px[0] = Math.round((pd.px[0] + d[0]) * 10) / 10;\n    pd.px[1] = Math.round((pd.px[1] + d[1]) * 10) / 10;\n    refreshBar();\n    draw();\n  }, true);\n\n  // re-drag du marker pending\n  canvasWrap.addEventListener(\'mousedown\', e => {\n    const pd = window._mkPending;\n    if (!pd || e.button !== 0) return;\n    const rect = getMainPaneRect();\n    const [cx, cy] = toCanvas(pd.px[0], pd.px[1]);\n    const mx = e.clientX - rect.left, my = e.clientY - rect.top;\n    if ((mx - cx) ** 2 + (my - cy) ** 2 < 144) {\n      bar.style.display = \'none\';\n      mk.drag = { kind: pd.kind, lm: pd.lm, px: pd.px.slice(), isNew: pd.isNew,\n                  orig: pd.orig, line: null, fromPending: true };\n      window._mkPending = null;\n      e.stopImmediatePropagation(); e.preventDefault();\n      mk.swallowClick = true;\n    }\n  }, true);\n\n  console.log(\'[EDIT-MODE-V1] pending confirm layer active\');\n})();\n</script>' + '\n' + s[i:]

# rediriger le mouseup de MARKING-V1 vers le pending
old = "  window.addEventListener('mouseup', e => {\n    if (!mk.drag) return;\n    const d = mk.drag;\n    // moved less than 0.5 img px on a 'move' drag = accidental click -> revert\n    if (d.kind === 'move' && d.orig &&\n        Math.hypot(d.px[0] - d.orig[0], d.px[1] - d.orig[1]) < 0.5) {\n      mk.drag = null;\n      loupe.style.display = 'none';\n      canvasWrap.style.cursor = 'crosshair';\n      draw();\n      return;\n    }\n    commit();\n  });"
assert old in s, 'anchor mouseup'
s = s.replace(old, "  window.addEventListener('mouseup', e => {\n    if (!mk.drag) return;\n    const d = mk.drag;\n    // moved less than 0.5 img px on a 'move' drag = accidental click -> revert\n    if (d.kind === 'move' && d.orig && !d.fromPending &&\n        Math.hypot(d.px[0] - d.orig[0], d.px[1] - d.orig[1]) < 0.5) {\n      mk.drag = null;\n      loupe.style.display = 'none';\n      canvasWrap.style.cursor = 'crosshair';\n      draw();\n      return;\n    }\n    // [EDIT-MODE-V1] release = review, not commit\n    mk.drag = null;\n    loupe.style.display = 'none';\n    canvasWrap.style.cursor = 'crosshair';\n    if (window._mkEnterPending) window._mkEnterPending(d);\n    else commit.call(null);\n  });", 1)
open(P, 'w').write(s)
print('tools/calib.html: EDIT-MODE-V1 + fix projected')
print('EDIT-MODE-V1 complet. Redemarre le serveur + hard refresh.')
