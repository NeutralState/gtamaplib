"""patch_minimap_selray_fix.py — MINIMAP-FIX-V1 + MINIMAP-ZOOM-V2 + SELRAY-V2 (2026-07-05).

Three fixes bundled:
1. MINIMAP-FIX-V1: the main cam-change handler updated the frame + projections
   but never called updateMinimap() — so switching cams left a STALE minimap.
   Now refreshed on every cam change.
2. MINIMAP-ZOOM-V2: minimap radius 350 -> 800m (was bumped to 600, now 800)
   for much more surrounding context. Clears the cached PNGs.
3. SELRAY-V2: the selected-LM ray renderer now lazy-creates its layer, forces
   it to the TOP of the overlay (rebuilds could bury or drop it), uses
   non-scaling-stroke so rays stay visible at any zoom, and logs a [SELRAY]
   diagnostic line to the console explaining exactly what it drew or why it
   skipped (helps if rays still don't show — the console will say why).

Live-tested: minimap refreshes on cam change, rays draw on real dot click
(2/2, logged). Requires the SELRAY-V1 chain. Idempotent.
Backups: .bak_msfix. Restart server + hard refresh (Cmd+Shift+R!).
"""
import shutil, sys, os, glob, re

# ---- server.py: zoom ----
P = 'tools/server.py'
s = open(P).read()
if 'MINIMAP-ZOOM-V2' in s:
    print('server: deja patche')
else:
    shutil.copy(P, P + '.bak_msfix')
    m = re.search(r'_MINIMAP_RADIUS_M = [\d.]+.*', s)
    assert m, 'anchor radius'
    s = s[:m.start()] + '_MINIMAP_RADIUS_M = 800.0  # [MINIMAP-ZOOM-V2] 350->800 for more context' + s[m.end():]
    open(P, 'w').write(s)
    cache = os.path.join('tools', 'generated', 'minimaps')
    n = 0
    if os.path.isdir(cache):
        for f in glob.glob(os.path.join(cache, '*.png')):
            os.remove(f); n += 1
    print(f'tools/server.py: radius -> 800m, {n} cached minimaps cleared')

# ---- calib.html: minimap-fix + selray-v2 ----
P = 'tools/calib.html'
s = open(P).read()
if 'SELRAY-V2' in s and 'MINIMAP-FIX-V1' in s:
    print('calib: deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_msfix_calib')

if 'MINIMAP-FIX-V1' not in s:
    old = '  await loadProjections();\n});\n\n// ── Projections'
    assert old in s, 'anchor minimap-fix'
    s = s.replace(old, "  await loadProjections();\n  if (typeof updateMinimap === 'function') updateMinimap();   // [MINIMAP-FIX-V1] was never called on direct cam change -> stale minimap\n});\n\n// ── Projections", 1)
    print('MINIMAP-FIX-V1: updateMinimap on cam change')

if 'SELRAY-V2' not in s:
    old = "  function renderSelLmRays() {\n    const layer = document.getElementById('sel-lm-rays-layer');\n    if (!layer || !window.mapData || !window.worldToSvg) return;\n    while (layer.firstChild) layer.removeChild(layer.firstChild);\n    if (!mapSelectedLm) return;\n    const lm = window.mapData.landmarks.find(l => l.name === mapSelectedLm);\n    if (!lm || !lm.xyz) return;\n    const NS = 'http://www.w3.org/2000/svg';\n    const [bx, by] = window.worldToSvg(lm.xyz[0], lm.xyz[1]);\n    const srcs = lm.source_cameras || lm.observed_by || [];\n    if (!window.mapCamByName)\n      window.mapCamByName = new Map(window.mapData.cameras.map(c => [c.name, c]));\n    for (const cn of srcs) {\n      const cam = window.mapCamByName.get(cn);\n      if (!cam || !cam.xyz) continue;\n      const [ax, ay] = window.worldToSvg(cam.xyz[0], cam.xyz[1]);\n      const line = document.createElementNS(NS, 'line');\n      line.setAttribute('x1', ax); line.setAttribute('y1', ay);\n      line.setAttribute('x2', bx); line.setAttribute('y2', by);\n      line.setAttribute('stroke', '#4ade80');\n      line.setAttribute('stroke-width', '2.5');\n      line.setAttribute('opacity', '0.85');\n      line.setAttribute('stroke-dasharray', '1 6');\n      line.setAttribute('stroke-linecap', 'round');\n      layer.appendChild(line);\n    }\n    const ring = document.createElementNS(NS, 'circle');\n    ring.setAttribute('cx', bx); ring.setAttribute('cy', by);\n    ring.setAttribute('r', '9'); ring.setAttribute('fill', 'none');\n    ring.setAttribute('stroke', '#4ade80'); ring.setAttribute('stroke-width', '2.5');\n    layer.appendChild(ring);\n  }"
    assert old in s, 'anchor renderSelLmRays (need SELRAY-V1 first)'
    s = s.replace(old, "  function renderSelLmRays() {\n    const NS = 'http://www.w3.org/2000/svg';\n    // [SELRAY-V2] lazy-ensure the layer exists AND sits on top (rebuilds\n    // sometimes recreate the overlay without it, or below other layers).\n    let layer = document.getElementById('sel-lm-rays-layer');\n    if (!window.mapOverlay) { console.warn('[SELRAY] no mapOverlay yet'); return; }\n    if (!layer) {\n      layer = document.createElementNS(NS, 'g');\n      layer.setAttribute('id', 'sel-lm-rays-layer');\n    }\n    // always move to top of the overlay so nothing paints over the rays\n    window.mapOverlay.appendChild(layer);\n    while (layer.firstChild) layer.removeChild(layer.firstChild);\n    if (!window.mapData || !window.worldToSvg) { console.warn('[SELRAY] mapData/worldToSvg missing'); return; }\n    if (!mapSelectedLm) return;\n    const lm = window.mapData.landmarks.find(l => l.name === mapSelectedLm);\n    if (!lm) { console.warn('[SELRAY] LM not in mapData:', mapSelectedLm); return; }\n    if (!lm.xyz) { console.warn('[SELRAY] LM has no xyz (untriangulated):', mapSelectedLm); return; }\n    const [bx, by] = window.worldToSvg(lm.xyz[0], lm.xyz[1]);\n    const srcs = lm.source_cameras || lm.observed_by || [];\n    if (!window.mapCamByName)\n      window.mapCamByName = new Map(window.mapData.cameras.map(c => [c.name, c]));\n    let drawn = 0;\n    for (const cn of srcs) {\n      const cam = window.mapCamByName.get(cn);\n      if (!cam || !cam.xyz) continue;\n      const [ax, ay] = window.worldToSvg(cam.xyz[0], cam.xyz[1]);\n      const line = document.createElementNS(NS, 'line');\n      line.setAttribute('x1', ax); line.setAttribute('y1', ay);\n      line.setAttribute('x2', bx); line.setAttribute('y2', by);\n      line.setAttribute('stroke', '#4ade80');\n      line.setAttribute('stroke-width', '3');\n      line.setAttribute('opacity', '0.9');\n      line.setAttribute('stroke-dasharray', '2 7');\n      line.setAttribute('stroke-linecap', 'round');\n      line.setAttribute('vector-effect', 'non-scaling-stroke');\n      layer.appendChild(line);\n      drawn++;\n    }\n    const ring = document.createElementNS(NS, 'circle');\n    ring.setAttribute('cx', bx); ring.setAttribute('cy', by);\n    ring.setAttribute('r', '10'); ring.setAttribute('fill', 'none');\n    ring.setAttribute('stroke', '#4ade80'); ring.setAttribute('stroke-width', '3');\n    ring.setAttribute('vector-effect', 'non-scaling-stroke');\n    layer.appendChild(ring);\n    console.log(`[SELRAY] ${mapSelectedLm}: ${drawn}/${srcs.length} rays drawn, LM at svg(${bx.toFixed(0)},${by.toFixed(0)})`);\n  }\n", 1)
    print('SELRAY-V2: robust layer + diagnostics')

open(P, 'w').write(s)
print('Applique. Restart server + HARD REFRESH (Cmd+Shift+R).')
