"""patch_sel_lm_rays.py — SELRAY-V1 (2026-07-05, in-scope fix).

Map view: selecting an LM (click its dot) draws a ray from each source
camera to the LM + a convergence ring. Deselect clears.

FIX vs first attempt: the map has its OWN selection var `mapSelectedLm`
inside a closed IIFE scope — the earlier version hooked Camera view's
`selectedLm` from an external <script> and never fired. The render fn now
lives INSIDE the map scope, called directly by setMapSelectedLm, and again
at the end of renderCamsOnMap so it survives overlay rebuilds.

Live-tested with a real dot click: 2 sources -> 2 rays, survives rebuild,
reclick clears. Idempotent. Backup: .bak_selray2. Hard refresh.
"""
import shutil, sys
P = 'tools/calib.html'
s = open(P).read()

# if the old external-hook version is present, strip it first
if 'selected-LM ray display active' in s and 'function renderSelLmRays' not in s:
    import re
    i = s.index('<script>\n// ══ [SELRAY-V1]')
    j = s.index('</script>', i) + len('</script>')
    st = s.rfind('\n', 0, i)
    s = s[:st] + s[j:]
    print('ancien bloc externe retire')

if 'function renderSelLmRays' in s:
    print('deja patche (in-scope)'); sys.exit(0)
shutil.copy(P, P + '.bak_selray2')

# 1. layer (si absent)
if "id', 'sel-lm-rays-layer'" not in s:
    anchor = "    const raysGroup = document.createElementNS(SVG_NS, 'g');\n    raysGroup.setAttribute('id', 'rays-layer');\n    window.mapOverlay.appendChild(raysGroup);\n"
    assert anchor in s, 'anchor rays-layer'
    s = s.replace(anchor, anchor + "\n    // [SELRAY-V1] rays from a selected LM's source cameras toward the LM.\n    const selRayGroup = document.createElementNS(SVG_NS, 'g');\n    selRayGroup.setAttribute('id', 'sel-lm-rays-layer');\n    window.mapOverlay.appendChild(selRayGroup);\n", 1)

# 2. render fn in-scope
anchor = '  function setMapSelectedLm(name) {'
assert anchor in s, 'anchor setMapSelectedLm'
s = s.replace(anchor, "  // [SELRAY-V1] draw rays from the selected LM's source cams to the LM.\n  function renderSelLmRays() {\n    const layer = document.getElementById('sel-lm-rays-layer');\n    if (!layer || !window.mapData || !window.worldToSvg) return;\n    while (layer.firstChild) layer.removeChild(layer.firstChild);\n    if (!mapSelectedLm) return;\n    const lm = window.mapData.landmarks.find(l => l.name === mapSelectedLm);\n    if (!lm || !lm.xyz) return;\n    const NS = 'http://www.w3.org/2000/svg';\n    const [bx, by] = window.worldToSvg(lm.xyz[0], lm.xyz[1]);\n    const srcs = lm.source_cameras || lm.observed_by || [];\n    if (!window.mapCamByName)\n      window.mapCamByName = new Map(window.mapData.cameras.map(c => [c.name, c]));\n    for (const cn of srcs) {\n      const cam = window.mapCamByName.get(cn);\n      if (!cam || !cam.xyz) continue;\n      const [ax, ay] = window.worldToSvg(cam.xyz[0], cam.xyz[1]);\n      const line = document.createElementNS(NS, 'line');\n      line.setAttribute('x1', ax); line.setAttribute('y1', ay);\n      line.setAttribute('x2', bx); line.setAttribute('y2', by);\n      line.setAttribute('stroke', '#4ade80');\n      line.setAttribute('stroke-width', '2.5');\n      line.setAttribute('opacity', '0.85');\n      line.setAttribute('stroke-dasharray', '1 6');\n      line.setAttribute('stroke-linecap', 'round');\n      layer.appendChild(line);\n    }\n    const ring = document.createElementNS(NS, 'circle');\n    ring.setAttribute('cx', bx); ring.setAttribute('cy', by);\n    ring.setAttribute('r', '9'); ring.setAttribute('fill', 'none');\n    ring.setAttribute('stroke', '#4ade80'); ring.setAttribute('stroke-width', '2.5');\n    layer.appendChild(ring);\n  }\n" + '\n' + anchor, 1)

# 3. call from setMapSelectedLm
old = '    mapSelectedLm = name;\n    // Re-render sidebar so the .sel class lands on the right item.\n    renderMapSidebar();'
assert old in s, 'anchor call'
s = s.replace(old, '    mapSelectedLm = name;\n    renderSelLmRays();   // [SELRAY-V1]\n    // Re-render sidebar so the .sel class lands on the right item.\n    renderMapSidebar();', 1)

# 4. survive rebuilds
ctx = 'renderLandmarksOnMap();\n    renderSelLmRays();   // [SELRAY-V1] survive overlay rebuilds'
assert ctx.split(chr(10))[0] in s, 'anchor survive'
import re
idx = s.index('function renderCamsOnMap')
rl = s.index('renderLandmarksOnMap();', idx)
end = s.index(chr(10), rl)
s = s[:end] + '\n    renderSelLmRays();   // [SELRAY-V1] survive overlay rebuilds' + s[end:]

open(P, 'w').write(s)
print('SELRAY-V1 applique (in-scope). Hard refresh.')
