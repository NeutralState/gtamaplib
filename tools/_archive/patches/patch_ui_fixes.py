"""patch_ui_fixes.py — UIFIX-V1 (2026-07-04 pm).

1. Click a marker on the canvas = select it + smooth-scroll its row into
   view in the LM list (wired into the sub-0.5px "accidental click" branch
   of the drag machinery — a click IS a selection). Empty-area clicks near
   a marker (12px) also select.
2. ◐ adjust button aligned with mesh/verts/cams (top 8, same padding/font,
   slot right:248).
3. Adjust panel PERF: the two feGaussianBlur ran even when texture/clarity
   were 0 — that was the whole delay. stdDeviation forced to 0 when unused:
   tone-only adjustments are now instant.
(Map-view ray display for a selected LM: deferred to next session.)
Requires patch_marking_qol.py. Idempotent. Backup: .bak_uifix. Hard refresh.
"""
import shutil, sys
P = 'tools/calib.html'
s = open(P).read()
if 'UIFIX-V1' in s:
    print('deja patche'); sys.exit(0)
assert 'QOL-V1' in s, 'prerequis: patch_marking_qol.py'
shutil.copy(P, P + '.bak_uifix')
old = '    <button id="btn-mkadj" onclick="window._mkAdjToggle()" style="position:absolute;top:12px;right:270px;z-index:30;\n             background:#1a1a22cc;border:1px solid #333;color:#999;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:12px;\n             font-family:JetBrains Mono,monospace">◐ adjust</button>'
assert old in s, 'anchor bouton'
s = s.replace(old, '    <button id="btn-mkadj" onclick="window._mkAdjToggle()" style="position:absolute;top:8px;right:248px;z-index:30;\n             background:#1a1a22cc;border:1px solid #333;color:#999;padding:4px 8px;border-radius:6px;cursor:pointer;font-size:11px;\n             font-family:JetBrains Mono,monospace">◐ adjust</button><!-- [UIFIX-V1] aligned with mesh/verts/cams -->', 1)
old = "    const kt = st.texture / 130, kc = st.clarity / 160;\n    const tex = document.getElementById('mkadj-tex');\n    tex.setAttribute('k2', (1 + kt).toFixed(3)); tex.setAttribute('k3', (-kt).toFixed(3));\n    const cla = document.getElementById('mkadj-cla');\n    cla.setAttribute('k2', (1 + kc).toFixed(3)); cla.setAttribute('k3', (-kc).toFixed(3));"
assert old in s, 'anchor perf'
s = s.replace(old, '    const kt = st.texture / 130, kc = st.clarity / 160;\n    const tex = document.getElementById(\'mkadj-tex\');\n    tex.setAttribute(\'k2\', (1 + kt).toFixed(3)); tex.setAttribute(\'k3\', (-kt).toFixed(3));\n    const cla = document.getElementById(\'mkadj-cla\');\n    cla.setAttribute(\'k2\', (1 + kc).toFixed(3)); cla.setAttribute(\'k3\', (-kc).toFixed(3));\n    // [UIFIX-V1] the two feGaussianBlur are the whole GPU cost — kill them\n    // when their sharpen stage is unused (tone-only = instant)\n    document.querySelector(\'#mkadj feGaussianBlur[result="btex"]\').setAttribute(\'stdDeviation\', kt > 0 ? \'1.5\' : \'0\');\n    document.querySelector(\'#mkadj feGaussianBlur[result="bcla"]\').setAttribute(\'stdDeviation\', kc > 0 ? \'10\' : \'0\');', 1)
old = "    if (d.kind === 'move' && d.orig && !d.fromPending &&\n        Math.hypot(d.px[0] - d.orig[0], d.px[1] - d.orig[1]) < 0.5) {\n      mk.drag = null;\n      loupe.style.display = 'none';\n      canvasWrap.style.cursor = 'crosshair';\n      draw();\n      return;\n    }"
assert old in s, 'anchor revert'
s = s.replace(old, "    if (d.kind === 'move' && d.orig && !d.fromPending &&\n        Math.hypot(d.px[0] - d.orig[0], d.px[1] - d.orig[1]) < 0.5) {\n      mk.drag = null;\n      loupe.style.display = 'none';\n      canvasWrap.style.cursor = 'crosshair';\n      if (window._mkSelectLm) window._mkSelectLm(d.lm);   // [UIFIX-V1] click = select\n      draw();\n      return;\n    }", 1)
i = s.rindex('</body>')
s = s[:i] + "\n<script>\n// ══ [UIFIX-V1] click a marker on canvas -> select + scroll in the LM list ══\n(() => {\n  window._mkSelectLm = function(name) {\n    selectedLm = selectedLm === name ? null : name;\n    renderLmList(); draw(); showLmInfo(selectedLm);\n    if (selectedLm) {\n      for (const row of lmList.children) {\n        const n = row.querySelector && row.querySelector('.lm-name');\n        if (n && n.textContent === selectedLm) {\n          row.scrollIntoView({ block: 'center', behavior: 'smooth' });\n          break;\n        }\n      }\n    }\n  };\n  canvasWrap.addEventListener('click', e => {\n    if (addPxMode || (window._mk && window._mk.drag) || window._mkPending) return;\n    if (window._assistHoverGhost) return;   // ghost click = arming, not select\n    const rect = getMainPaneRect();\n    const mx = e.clientX - rect.left, my = e.clientY - rect.top;\n    let best = null, bd = 144;\n    for (const lm of projections) {\n      if (!lm.marked_pixel) continue;\n      const [cx, cy] = toCanvas(lm.marked_pixel[0], lm.marked_pixel[1]);\n      const d = (cx - mx) ** 2 + (cy - my) ** 2;\n      if (d < bd) { bd = d; best = lm.name; }\n    }\n    if (!best) return;\n    window._mkSelectLm(best);\n  });\n  console.log('[UIFIX-V1] canvas marker click-to-list active');\n})();\n</script>\n" + s[i:]
open(P, 'w').write(s)
print('UIFIX-V1 applique. Hard refresh.')
