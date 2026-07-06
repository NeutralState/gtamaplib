"""patch_ui_polish.py — PANEL-V3 + MARKERS-V2 (2026-07-03).

Feedback-driven redo of the pose panel + a visual pass on the markers.

PANEL-V3 (replaces PANEL-V2, auto-reverted if present): pose editing lives
in the TERMINAL — the UI displays it beautifully instead. Sliders and raw
inputs hidden; clean formatted rows (2 decimals + unit); CLICK a value =
copy it at full precision; "⧉ copy pose" = the whole pose ready to paste
into a terminal command or a chat message.

MARKERS-V2: markers stop being flat blobs. Marked pixel = precision reticle
(center dot + open ring + ticks and glow on hover; dashed ring = circular
provenance). Ghosts = diamonds (instantly distinct from real markers),
priority colors kept. Labels = rounded chips with the delta on line 2.
Epipolar lines thinner with a subtle glow.

Live-tested headless: formatted display, click-copy full precision,
copy-pose string, MARKING-V1 drag coexistence. Zero JS errors.
Idempotent. Requires MARKING-V1. Restart server + hard refresh after.
"""
import shutil, sys, os
P = 'tools/calib.html'
s = open(P).read()

# 0. revert PANEL-V2 if present
if 'PANEL-V2' in s:
    bak = P + '.bak_panel'
    assert os.path.exists(bak), 'PANEL-V2 present mais .bak_panel introuvable'
    shutil.copy(bak, P)
    s = open(P).read()
    print('PANEL-V2 reverte (restore .bak_panel)')
assert 'MARKING-V1' in s, 'prerequis: patch_marking_v1.py d abord'
if 'PANEL-V3' in s and 'MARKERS-V2' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_polish')

# 1. PANEL-V3
if 'PANEL-V3' not in s:
    assert '</style>' in s
    s = s.replace('</style>', '\n/* [PANEL-V3] pose = read-only display, terminal-first. Sliders and inputs\n   hidden; clean value rows, click = copy. */\n.sl-row input[type=range],.sl-row .num{display:none}\n.pv3-val{flex:1;text-align:right;font-family:var(--mono,monospace);font-size:13.5px;\n  color:var(--text,#e8e8ee);padding:5px 8px;border-radius:5px;cursor:copy;\n  letter-spacing:.2px;transition:background .12s}\n.pv3-val:hover{background:#ffffff0d}\n.pv3-val .pv3-unit{color:var(--dim,#555);font-size:10px;margin-left:4px}\n.pv3-val.pv3-flash{background:#4ade8022;color:var(--green,#4ade80)}\n#pv3-copy-pose{width:100%;margin-top:8px;font-family:var(--mono,monospace);font-size:10px;\n  padding:5px 8px;background:transparent;border:1px solid var(--border,#2a2a33);\n  color:var(--mid,#999);border-radius:5px;cursor:pointer;transition:all .12s}\n#pv3-copy-pose:hover{border-color:var(--green,#4ade80);color:var(--green,#4ade80)}\n' + '</style>', 1)
    hfov_row = '      <div class="sl-row"><span class="sl-lbl">hFOV</span><input type="range" id="sl-hfov" min="10" max="130" step="0.01"><input class="num" id="num-hfov" type="number" step="0.01"></div>'
    assert hfov_row in s, 'anchor hfov'
    s = s.replace(hfov_row, hfov_row + '\n      <!-- [PANEL-V3] -->\n      <button id="pv3-copy-pose" title="copy the full pose, ready to paste in a terminal command">⧉ copy pose</button>', 1)
    i = s.rindex('</body>')
    s = s[:i] + '\n<script>\n// ══ [PANEL-V3] pose display: read-only, formatted, click-to-copy ══\n// Editing lives in the terminal (fit_minimal & co). The UI shows the pose\n// beautifully and hands it to the clipboard: click a value = copy it (full\n// precision), "copy pose" = the whole thing ready to paste.\n(() => {\n  const UNITS = { x: \'m\', y: \'m\', z: \'m\', yaw: \'°\', pitch: \'°\', roll: \'°\', hfov: \'°\' };\n  const spans = {};\n  Object.keys(NUM_IDS).forEach(key => {\n    const row = document.getElementById(NUM_IDS[key]).parentElement;\n    const v = document.createElement(\'span\');\n    v.className = \'pv3-val\';\n    v.title = \'click = copy exact value\';\n    v.addEventListener(\'click\', async () => {\n      try { await navigator.clipboard.writeText(String(params[key])); } catch (_) {}\n      v.classList.add(\'pv3-flash\');\n      setTimeout(() => v.classList.remove(\'pv3-flash\'), 350);\n    });\n    row.appendChild(v);\n    spans[key] = v;\n  });\n  function fmt(key) {\n    const val = params[key];\n    if (val == null || isNaN(val)) return \'—\';\n    return Number(val).toFixed(2);\n  }\n  function refresh() {\n    for (const key of Object.keys(spans)) {\n      spans[key].innerHTML = fmt(key) + \'<span class="pv3-unit">\' + UNITS[key] + \'</span>\';\n    }\n  }\n  setInterval(refresh, 200);\n  refresh();\n  document.getElementById(\'pv3-copy-pose\').addEventListener(\'click\', async e => {\n    const r3 = v => Math.round(v * 1000) / 1000;\n    const txt = `xyz=[${r3(params.x)}, ${r3(params.y)}, ${r3(params.z)}] ` +\n                `ypr=[${r3(params.yaw)}, ${r3(params.pitch)}, ${r3(params.roll)}] hfov=${r3(params.hfov)}`;\n    try { await navigator.clipboard.writeText(txt); } catch (_) {}\n    e.target.textContent = \'✓ copied\';\n    setTimeout(() => { e.target.textContent = \'⧉ copy pose\'; }, 900);\n  });\n  console.log(\'[PANEL-V3] read-only pose display active\');\n})();\n</script>\n' + s[i:]
    print('PANEL-V3 applique')

# 2. MARKERS-V2
if 'MARKERS-V2' not in s:
    anchor = '// [CANVAS-GHOSTS] Shared helper: draw ghost markers on any ctx with any toCanvas mapper.\nfunction drawGhostsOnCtx('
    assert anchor in s, 'anchor ghosts'
    s = s.replace(anchor, "// ══ [MARKERS-V2] shared drawing helpers: precision-instrument look ══\n// Reticle = center dot + open ring (+ticks when highlighted). Circular\n// provenance = dashed ring. Labels = rounded chips, not raw text.\nfunction _mv2Reticle(c, x, y, r, color, opts) {\n  const hi = opts && opts.hi, dash = opts && opts.dash;\n  c.save();\n  if (hi) { c.shadowColor = color; c.shadowBlur = 9; }\n  c.beginPath(); c.arc(x, y, 1.6, 0, Math.PI * 2);\n  c.fillStyle = color; c.fill();\n  c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2);\n  if (dash) c.setLineDash([3.5, 3]);\n  c.strokeStyle = color; c.lineWidth = hi ? 1.8 : 1.25; c.stroke();\n  c.setLineDash([]);\n  if (hi) {\n    c.beginPath();\n    c.moveTo(x - r - 6, y); c.lineTo(x - r - 1, y);\n    c.moveTo(x + r + 1, y); c.lineTo(x + r + 6, y);\n    c.moveTo(x, y - r - 6); c.lineTo(x, y - r - 1);\n    c.moveTo(x, y + r + 1); c.lineTo(x, y + r + 6);\n    c.stroke();\n  }\n  c.restore();\n}\nfunction _mv2Diamond(c, x, y, r, color, opts) {\n  const hi = opts && opts.hi;\n  c.save();\n  if (hi) { c.shadowColor = color; c.shadowBlur = 9; }\n  c.beginPath();\n  c.moveTo(x, y - r); c.lineTo(x + r, y); c.lineTo(x, y + r); c.lineTo(x - r, y);\n  c.closePath();\n  if (hi) { c.fillStyle = color + '33'; c.fill(); }\n  c.strokeStyle = color; c.lineWidth = hi ? 1.8 : 1.25; c.stroke();\n  c.restore();\n}\nfunction _mv2Chip(c, x, y, lines) {\n  c.save();\n  c.font = '11px JetBrains Mono, monospace';\n  const pad = 7, lh = 14;\n  const w = Math.max(...lines.map(l => c.measureText(l[0]).width)) + pad * 2;\n  const h = lines.length * lh + pad;\n  let bx = x + 12, by = y - h - 8;\n  if (by < 4) by = y + 12;\n  c.beginPath();\n  const rr = 5;\n  c.moveTo(bx + rr, by);\n  c.arcTo(bx + w, by, bx + w, by + h, rr);\n  c.arcTo(bx + w, by + h, bx, by + h, rr);\n  c.arcTo(bx, by + h, bx, by, rr);\n  c.arcTo(bx, by, bx + w, by, rr);\n  c.fillStyle = '#0a0a10e6'; c.fill();\n  c.strokeStyle = lines[0][1] + '66'; c.lineWidth = 1; c.stroke();\n  lines.forEach((l, i) => {\n    c.fillStyle = l[1];\n    c.fillText(l[0], bx + pad, by + pad / 2 + (i + 1) * lh - 4);\n  });\n  c.restore();\n}\n\n" + anchor, 1)
    for old, new, tag in [("    // Marked pixel circle\n    if (lm.marked_pixel) {\n      const [mx, my] = toCanvas(lm.marked_pixel[0], lm.marked_pixel[1]);\n      const r = hi ? 8 : (lm.is_circular ? 3 : 5);\n      ctx.beginPath(); ctx.arc(mx, my, r, 0, Math.PI * 2);\n      ctx.fillStyle = color + '44'; ctx.fill();\n      ctx.strokeStyle = color; ctx.lineWidth = hi ? 2.5 : 1.5; ctx.stroke();\n\n      if (hi) {\n        ctx.font = '11px JetBrains Mono, monospace';\n        ctx.fillStyle = '#fff';\n        ctx.fillText(lm.name, mx + 10, my - 8);\n        if (lm.delta != null) {\n          ctx.fillStyle = color;\n          ctx.fillText(`d=${lm.delta.toFixed(3)} arcmin`, mx + 10, my + 6);\n        }\n      }\n    }", '    // [MARKERS-V2] marked pixel = precision reticle\n    if (lm.marked_pixel) {\n      const [mx, my] = toCanvas(lm.marked_pixel[0], lm.marked_pixel[1]);\n      const r = hi ? 8 : (lm.is_circular ? 4.5 : 5.5);\n      _mv2Reticle(ctx, mx, my, r, color, { hi, dash: lm.is_circular });\n      if (hi) {\n        const lines = [[lm.name + (lm.is_circular ? \'  ↻\' : \'  ★\'), \'#e8e8ee\']];\n        if (lm.delta != null) lines.push(["d = " + lm.delta.toFixed(2) + "\'", color]);\n        _mv2Chip(ctx, mx, my, lines);\n      }\n    }\n', 'pane1'), ("    const [mx, my] = toCanvas2(lm.marked_pixel[0], lm.marked_pixel[1]);\n    const r = hi ? 8 : (lm.is_circular ? 3 : 5);\n    ctx2.beginPath(); ctx2.arc(mx, my, r, 0, Math.PI * 2);\n    ctx2.fillStyle = color + '44'; ctx2.fill();\n    ctx2.strokeStyle = color; ctx2.lineWidth = hi ? 2.5 : 1.5; ctx2.stroke();\n    if (hi) {\n      ctx2.font = '11px JetBrains Mono, monospace';\n      ctx2.fillStyle = '#fff';\n      ctx2.fillText(lm.name, mx + 10, my - 8);\n      if (lm.delta != null) {\n        ctx2.fillStyle = color;\n        ctx2.fillText(`d=${lm.delta.toFixed(3)} arcmin`, mx + 10, my + 6);\n      }\n    }", '    const [mx, my] = toCanvas2(lm.marked_pixel[0], lm.marked_pixel[1]);\n    const r = hi ? 8 : (lm.is_circular ? 4.5 : 5.5);\n    _mv2Reticle(ctx2, mx, my, r, color, { hi, dash: lm.is_circular });   // [MARKERS-V2]\n    if (hi) {\n      const lines = [[lm.name + (lm.is_circular ? \'  ↻\' : \'  ★\'), \'#e8e8ee\']];\n      if (lm.delta != null) lines.push(["d = " + lm.delta.toFixed(2) + "\'", color]);\n      _mv2Chip(ctx2, mx, my, lines);\n    }', 'pane2'),
                          ("    if (g.type === 'point') {\n      const hi = hoveredName === g.name;\n      const COL = gcol(g);\n      const [mx, my] = mapper(g.pixel[0], g.pixel[1]);\n      const r = hi ? 8 : (g.priority === 1 ? 6 : 5);\n      ctxLocal.beginPath(); ctxLocal.arc(mx, my, r, 0, Math.PI * 2);\n      ctxLocal.fillStyle = COL + '44';\n      ctxLocal.fill();\n      ctxLocal.strokeStyle = COL; ctxLocal.lineWidth = hi ? 2.5 : 1.5; ctxLocal.stroke();\n      if (hi) {\n        ctxLocal.font = '11px JetBrains Mono, monospace';\n        const labelText = g.name;\n        const labelW = ctxLocal.measureText(labelText).width;\n        // Black background rect (matches the cone-label style — see line ~3991)\n        ctxLocal.fillStyle = '#000';\n        ctxLocal.fillRect(mx + 6, my - 14, labelW + 8, 16);\n        ctxLocal.fillStyle = '#fff';\n        ctxLocal.fillText(labelText, mx + 10, my - 2);\n      }\n    } else if (g.type === 'epipolar') {", "    if (g.type === 'point') {\n      const hi = hoveredName === g.name;\n      const COL = gcol(g);\n      const [mx, my] = mapper(g.pixel[0], g.pixel[1]);\n      const r = hi ? 9 : (g.priority === 1 ? 7 : 5.5);\n      _mv2Diamond(ctxLocal, mx, my, r, COL, { hi });   // [MARKERS-V2] ghost = diamond\n      if (hi) {\n        const pr = g.priority ? 'P' + g.priority + ' · ' : '';\n        _mv2Chip(ctxLocal, mx, my, [[pr + g.name, COL], ['ghost — press & drag to mark', '#8a8a95']]);\n      }\n    } else if (g.type === 'epipolar') {", 'ghosts'), ('      ctxLocal.strokeStyle = gcol(g);\n      ctxLocal.lineWidth = 1.5;\n      ctxLocal.setLineDash([6, 4]);\n      ctxLocal.stroke();\n      ctxLocal.setLineDash([]);', '      ctxLocal.save();                                 // [MARKERS-V2]\n      ctxLocal.shadowColor = gcol(g); ctxLocal.shadowBlur = 4;\n      ctxLocal.strokeStyle = gcol(g);\n      ctxLocal.lineWidth = 1.1;\n      ctxLocal.setLineDash([7, 5]);\n      ctxLocal.stroke();\n      ctxLocal.setLineDash([]);\n      ctxLocal.restore();', 'epipolar')]:
        assert old in s, 'anchor ' + tag
        s = s.replace(old, new, 1)
    print('MARKERS-V2 applique')

open(P, 'w').write(s)
print('UI polish complet. Redemarre le serveur + hard refresh.')
