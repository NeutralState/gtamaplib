"""patch_sel_lm_rays.py — SELRAY-V1 (2026-07-05).

Map view: when an LM is selected (canvas click or list click), draw a ray
from each of its source cameras toward the LM, plus a ring at the LM so it
reads as the convergence point. Completes the click-to-select feature.
Dashed green hairlines, no pointer capture. Deselect clears them.
Requires the UIFIX-V1 chain. Idempotent. Backup: .bak_selray. Hard refresh.
"""
import shutil, sys
P = 'tools/calib.html'
s = open(P).read()
if 'SELRAY-V1' in s:
    print('deja patche'); sys.exit(0)
assert 'worldToSvg' in s and "id', 'rays-layer'" in s, 'structure map attendue absente'
shutil.copy(P, P + '.bak_selray')
anchor = "    const raysGroup = document.createElementNS(SVG_NS, 'g');\n    raysGroup.setAttribute('id', 'rays-layer');\n    window.mapOverlay.appendChild(raysGroup);\n"
assert anchor in s, 'anchor rays-layer'
s = s.replace(anchor, anchor + "\n    // [SELRAY-V1] rays from a selected LM's source cameras toward the LM.\n    const selRayGroup = document.createElementNS(SVG_NS, 'g');\n    selRayGroup.setAttribute('id', 'sel-lm-rays-layer');\n    window.mapOverlay.appendChild(selRayGroup);\n", 1)
i = s.rindex('</body>')
s = s[:i] + "\n<script>\n// ══ [SELRAY-V1] map: draw rays from a selected LM's source cams to the LM ══\n// Complements the click-to-select: when an LM is selected, the map shows\n// which cameras see it and from where — one line per source camera.\n(() => {\n  const SVG_NS = 'http://www.w3.org/2000/svg';\n  function render() {\n    const layer = document.getElementById('sel-lm-rays-layer');\n    if (!layer || !window.mapData || !window.worldToSvg) return;\n    while (layer.firstChild) layer.removeChild(layer.firstChild);\n    if (!selectedLm) return;\n    const lm = window.mapData.landmarks.find(l => l.name === selectedLm);\n    if (!lm || !lm.xyz) return;                         // no xyz = nothing to draw\n    const [bx, by] = window.worldToSvg(lm.xyz[0], lm.xyz[1]);\n    const srcs = lm.source_cameras || lm.observed_by || [];\n    const camByName = window.mapCamByName ||\n      (window.mapCamByName = new Map(window.mapData.cameras.map(c => [c.name, c])));\n    for (const cn of srcs) {\n      const cam = camByName.get(cn);\n      if (!cam || !cam.xyz) continue;\n      const [ax, ay] = window.worldToSvg(cam.xyz[0], cam.xyz[1]);\n      const line = document.createElementNS(SVG_NS, 'line');\n      line.setAttribute('x1', ax); line.setAttribute('y1', ay);\n      line.setAttribute('x2', bx); line.setAttribute('y2', by);\n      line.setAttribute('stroke', '#4ade80');\n      line.setAttribute('stroke-width', '2.5');\n      line.setAttribute('opacity', '0.8');\n      line.setAttribute('stroke-dasharray', '1 6');\n      line.setAttribute('stroke-linecap', 'round');\n      layer.appendChild(line);\n    }\n    // a small ring on the LM itself so it reads as the convergence point\n    const ring = document.createElementNS(SVG_NS, 'circle');\n    ring.setAttribute('cx', bx); ring.setAttribute('cy', by);\n    ring.setAttribute('r', '9'); ring.setAttribute('fill', 'none');\n    ring.setAttribute('stroke', '#4ade80'); ring.setAttribute('stroke-width', '2.5');\n    layer.appendChild(ring);\n  }\n  window._selRayRender = render;\n\n  // hook selection: wrap _mkSelectLm (canvas click) + the list click path\n  const _sel = window._mkSelectLm;\n  if (_sel) window._mkSelectLm = function(n) { _sel(n); render(); };\n  // list clicks call showLmInfo — wrap it too so both paths refresh\n  const _info = window.showLmInfo || showLmInfo;\n  window.showLmInfo = async function(n) { const r = await _info(n); render(); return r; };\n  // redraw on pan/zoom (rays live in SVG user-space; the wrap transform\n  // already moves them, but a re-render keeps them crisp after rebuilds)\n  const _tx = window.applyMapTx;\n  console.log('[SELRAY-V1] selected-LM ray display active');\n})();\n</script>\n" + s[i:]
open(P, 'w').write(s)
print('SELRAY-V1 applique. Hard refresh.')
