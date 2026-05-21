"""
CANVAS-GHOSTS refactor — move ghost projections from SVG to canvas.

Drops the SVG-based projection overlay (STEP23) and re-implements ghost
markers as plain canvas drawing inside draw() and draw2(). This matches
the existing marker style exactly (font, encadré noir, sizes) and lets
ghosts inherit pan/zoom automatically.

Also brings pane 2 up to feature-parity with pane 1: pane 2 now has
its own projections2 list (real markers marked on cam2), its own
hoveredLm2/selectedLm2, hover tracking via mousemove on #pane-2.

What this changes:
1. Remove the two <svg> projection overlays (proj-svg-1 + proj-svg-2)
2. Remove the entire STEP23 IIFE (~150 lines of SVG render code)
3. Add ghostMarkers1[] + ghostMarkers2[] arrays (loaded from /api/lm_projections)
4. Add projections2[] (loaded from /api/project for cam2)
5. Add hoveredLm2 + selectedLm2 state
6. Patch draw() to render ghosts at end (cercle violet outline + label on hover)
7. Patch draw2() to render projections2 + ghosts2 like draw() does for pane 1
8. Add pane 2 mousemove handler for hover hit-test
9. loadGhostsForBoth() called when dual mode toggles or cam changes

Idempotent: marker [CANVAS-GHOSTS].
"""

import os
import sys
import re

CALIB = os.path.expanduser('~/Downloads/gtamaplib-main/tools/calib.html')
with open(CALIB) as f:
    c = f.read()

if '[CANVAS-GHOSTS]' in c:
    print('Already patched.')
    sys.exit(0)

bak = CALIB + '.bak_canvas_ghosts'
with open(bak, 'w') as f: f.write(c)
print(f'Backup: {bak}')

# ── PATCH 1: Remove the SVG proj overlay HTML elements ────────────────
# pane 1 SVG
old_svg1 = '''    <!-- [MULTICAM-STEP23] LM projection overlay for pane 1 -->
    <svg class="lm-proj-svg" id="proj-svg-1" preserveAspectRatio="none"></svg>'''
if old_svg1 in c:
    c = c.replace(old_svg1, '<!-- [CANVAS-GHOSTS] proj-svg-1 removed, ghosts now drawn on #overlay -->', 1)
    print('Patch 1a: proj-svg-1 removed')

# pane 2 SVG
old_svg2 = '''      <!-- [MULTICAM-STEP23] LM projection overlay for pane 2 -->
      <svg class="lm-proj-svg" id="proj-svg-2" preserveAspectRatio="none"></svg>'''
if old_svg2 in c:
    c = c.replace(old_svg2, '<!-- [CANVAS-GHOSTS] proj-svg-2 removed, ghosts now drawn on #overlay-2 -->', 1)
    print('Patch 1b: proj-svg-2 removed')

# ── PATCH 2: Add state vars near other state ──────────────────────────
old_state2 = '''let main2Zoom = 1, main2PanX = 0, main2PanY = 0, main2Dragging = false, main2DragStart = null, main2PanStart = null;
let camData2 = null;  // set when cam 2 frame loads
window.camData2 = null;'''

new_state2 = '''let main2Zoom = 1, main2PanX = 0, main2PanY = 0, main2Dragging = false, main2DragStart = null, main2PanStart = null;
let camData2 = null;  // set when cam 2 frame loads
window.camData2 = null;
// [CANVAS-GHOSTS] Per-pane state: real markers + ghost projections + hover
let projections2 = [];                  // real markers marked on cam2
let ghostMarkers1 = [], ghostMarkers2 = [];  // ghost projections per pane
let hoveredLm2 = null, selectedLm2 = null;
let hoveredGhost1 = null, hoveredGhost2 = null;
window.projections2 = projections2;'''

if old_state2 in c:
    c = c.replace(old_state2, new_state2, 1)
    print('Patch 2: pane 2 + ghosts state vars added')

# ── PATCH 3: Replace draw2() with a full version that mirrors draw() ──
old_draw2 = '''// [MULTICAM-STEP30] Apply current pan/zoom to frame-img-2 by setting inline style.
function draw2() {
  const img2 = document.getElementById('frame-img-2');
  const overlay2 = document.getElementById('overlay-2');
  if (!img2 || !overlay2) return;
  if (!camData2 || !camData2.size) return;
  const {scale, ox, oy} = baseScale2();
  const left = main2PanX + ox * main2Zoom;
  const top  = main2PanY + oy * main2Zoom;
  const w    = camData2.size[0] * scale * main2Zoom;
  const h    = camData2.size[1] * scale * main2Zoom;
  img2.style.cssText = `position:absolute;left:${left}px;top:${top}px;width:${w}px;height:${h}px;object-fit:fill;pointer-events:none`;
  // Trigger projection re-render so ghost markers follow
  if (typeof window._refreshProjections === 'function') {
    requestAnimationFrame(window._refreshProjections);
  }
}
window.draw2 = draw2;'''

new_draw2 = '''// [CANVAS-GHOSTS] draw2() = full mirror of draw() but on pane 2.
// Renders frame-img-2, real markers (projections2), and ghosts (ghostMarkers2).
function toCanvas2v(px, py) {
  // Same as toCanvas2 but exists in this scope. Use the existing toCanvas2 helper.
  return toCanvas2(px, py);
}
function draw2() {
  const img2 = document.getElementById('frame-img-2');
  const overlay2 = document.getElementById('overlay-2');
  if (!img2 || !overlay2) return;
  const ctx2 = overlay2.getContext('2d');
  ctx2.clearRect(0, 0, overlay2.width, overlay2.height);
  if (!camData2 || !camData2.size) return;

  // Sync frame image with zoom/pan
  const {scale, ox, oy} = baseScale2();
  const left = main2PanX + ox * main2Zoom;
  const top  = main2PanY + oy * main2Zoom;
  const w    = camData2.size[0] * scale * main2Zoom;
  const h    = camData2.size[1] * scale * main2Zoom;
  img2.style.cssText = `position:absolute;left:${left}px;top:${top}px;width:${w}px;height:${h}px;object-fit:fill;pointer-events:none`;

  // Real markers on pane 2 (those marked on currentCam2)
  for (const lm of projections2) {
    if (!lm.marked_pixel) continue;
    const hi = hoveredLm2 === lm.name || selectedLm2 === lm.name;
    const color = dColor(lm.delta);
    const visible = lmFilter === 'all'   ? true
                  : lmFilter === 'indep' ? !lm.is_circular
                  : (lm.delta != null && lm.delta > 5);
    ctx2.globalAlpha = visible ? 1 : 0.12;
    const [mx, my] = toCanvas2(lm.marked_pixel[0], lm.marked_pixel[1]);
    const r = hi ? 8 : (lm.is_circular ? 3 : 5);
    ctx2.beginPath(); ctx2.arc(mx, my, r, 0, Math.PI * 2);
    ctx2.fillStyle = color + '44'; ctx2.fill();
    ctx2.strokeStyle = color; ctx2.lineWidth = hi ? 2.5 : 1.5; ctx2.stroke();
    if (hi) {
      ctx2.font = '11px JetBrains Mono, monospace';
      ctx2.fillStyle = '#fff';
      ctx2.fillText(lm.name, mx + 10, my - 8);
      if (lm.delta != null) {
        ctx2.fillStyle = color;
        ctx2.fillText(`d=${lm.delta.toFixed(3)} arcmin`, mx + 10, my + 6);
      }
    }
    ctx2.globalAlpha = 1;
  }

  // Ghost markers on pane 2 (LMs marked on currentCam, projected here)
  drawGhostsOnCtx(ctx2, ghostMarkers2, toCanvas2, hoveredGhost2);
}
window.draw2 = draw2;

// [CANVAS-GHOSTS] Shared helper: draw ghost markers on any ctx with any toCanvas mapper.
function drawGhostsOnCtx(ctxLocal, ghosts, mapper, hoveredName) {
  if (!ghosts || !ghosts.length) return;
  const VIOLET = '#c084fc';
  for (const g of ghosts) {
    if (g.type === 'point') {
      const hi = hoveredName === g.name;
      const [mx, my] = mapper(g.pixel[0], g.pixel[1]);
      const r = hi ? 8 : 5;
      ctxLocal.beginPath(); ctxLocal.arc(mx, my, r, 0, Math.PI * 2);
      ctxLocal.fillStyle = VIOLET + '44';  // 27% alpha fill — matches existing markers
      ctxLocal.fill();
      ctxLocal.strokeStyle = VIOLET; ctxLocal.lineWidth = hi ? 2.5 : 1.5; ctxLocal.stroke();
      if (hi) {
        ctxLocal.font = '11px JetBrains Mono, monospace';
        const labelText = g.name;
        const labelW = ctxLocal.measureText(labelText).width;
        // Black background rect (matches the cone-label style — see line ~3991)
        ctxLocal.fillStyle = '#000';
        ctxLocal.fillRect(mx + 6, my - 14, labelW + 8, 16);
        ctxLocal.fillStyle = '#fff';
        ctxLocal.fillText(labelText, mx + 10, my - 2);
      }
    } else if (g.type === 'epipolar') {
      // Epipolar line in violet, dashed
      const [x1, y1] = mapper(g.line[0][0], g.line[0][1]);
      const [x2, y2] = mapper(g.line[1][0], g.line[1][1]);
      ctxLocal.beginPath();
      ctxLocal.moveTo(x1, y1); ctxLocal.lineTo(x2, y2);
      ctxLocal.strokeStyle = VIOLET;
      ctxLocal.lineWidth = 1.5;
      ctxLocal.setLineDash([6, 4]);
      ctxLocal.stroke();
      ctxLocal.setLineDash([]);
    }
  }
}
window.drawGhostsOnCtx = drawGhostsOnCtx;'''

if old_draw2 in c:
    c = c.replace(old_draw2, new_draw2, 1)
    print('Patch 3: draw2() rewritten + drawGhostsOnCtx helper')

# ── PATCH 4: Patch draw() to call drawGhostsOnCtx at the end ──────────
# Find the closing brace of draw() — but it's complex. Easier: insert
# our ghost call right before the closing logic. The function ends with
# `})` for the forEach + closing brace for the function.
# Let's just find the last reference inside the projections.forEach loop
# and append a call OUTSIDE the loop, before the function closes.
# We search for the unique end pattern of draw().

# Looking at the code, after `projections.forEach(lm => { ... });` the
# draw() function should end. Let's find the right anchor.

# Method: insert ghost draw call right after projections.forEach closes.
old_proj_loop_end = '''    ctx.globalAlpha = 1;
  });
}

// ── Mouse'''

new_proj_loop_end = '''    ctx.globalAlpha = 1;
  });
  // [CANVAS-GHOSTS] Draw ghost markers (LMs marked on cam2, projected onto cam1)
  drawGhostsOnCtx(ctx, ghostMarkers1, toCanvas, hoveredGhost1);
}

// ── Mouse'''

if old_proj_loop_end in c:
    c = c.replace(old_proj_loop_end, new_proj_loop_end, 1)
    print('Patch 4: draw() now calls drawGhostsOnCtx at end')
else:
    print('WARN: draw() end anchor not found — ghosts won\'t render on pane 1')

# ── PATCH 5: Replace STEP23 IIFE with a simpler ghost loader ──────────
# Find the STEP23 IIFE start/end and replace its body.
step23_start = '// ── [MULTICAM-STEP23] LM projection overlay rendering ─────────────────'
step23_end = '// ── end [MULTICAM-STEP23] ─────────────────────────────────────────────'

start_idx = c.find(step23_start)
end_idx = c.find(step23_end)
if start_idx >= 0 and end_idx >= 0:
    end_idx += len(step23_end)
    new_block = '''// ── [CANVAS-GHOSTS] Ghost projection loader (replaces SVG STEP23) ─────
// Fetches /api/lm_projections for each pane and stores results in
// ghostMarkers1/ghostMarkers2. Then triggers draw()/draw2() to render.
(() => {
  const cache = new Map();

  async function fetchProjections(camName, filterCam) {
    if (!camName) return null;
    const cacheKey = camName + '|' + (filterCam || '');
    if (cache.has(cacheKey)) return cache.get(cacheKey);
    try {
      let url = '/api/lm_projections?cam=' + encodeURIComponent(camName);
      if (filterCam) url += '&filter_cam=' + encodeURIComponent(filterCam);
      const r = await fetch(url);
      const d = await r.json();
      if (d.error) {
        console.warn('[CANVAS-GHOSTS] error for', camName, d.error);
        return null;
      }
      cache.set(cacheKey, d);
      return d;
    } catch (e) {
      console.warn('[CANVAS-GHOSTS] fetch failed for', camName, e);
      return null;
    }
  }

  async function refresh() {
    const cam1 = window.currentCam;
    const cam2 = window.currentCam2;
    if (document.body.classList.contains('dual-cam') && cam1 && cam2 &&
        !document.body.classList.contains('proj-off')) {
      const d1 = await fetchProjections(cam1, cam2);
      ghostMarkers1 = (d1 && d1.projections) || [];
      const d2 = await fetchProjections(cam2, cam1);
      ghostMarkers2 = (d2 && d2.projections) || [];
    } else {
      ghostMarkers1 = [];
      ghostMarkers2 = [];
    }
    if (typeof draw === 'function') draw();
    if (typeof draw2 === 'function') draw2();
  }
  window._refreshGhosts = refresh;
  // Backward-compat alias used by draw2 raF call
  window._refreshProjections = refresh;

  // Refresh hooks
  const btnDual = document.getElementById('dual-toggle');
  if (btnDual) btnDual.addEventListener('click', () => setTimeout(refresh, 50));
  const sel1 = document.getElementById('cam-sel');
  if (sel1) sel1.addEventListener('change', () => setTimeout(refresh, 200));
  const sel2 = document.getElementById('cam-sel-2');
  if (sel2) sel2.addEventListener('change', () => setTimeout(refresh, 200));

  // Projections toggle
  const btnProj = document.getElementById('proj-toggle');
  if (btnProj) {
    btnProj.addEventListener('click', () => {
      const off = document.body.classList.toggle('proj-off');
      btnProj.classList.toggle('active', !off);
      refresh();
    });
    btnProj.classList.add('active');
  }

  console.log('[CANVAS-GHOSTS] ghost loader wired up');
})();'''
    c = c[:start_idx] + new_block + c[end_idx:]
    print('Patch 5: STEP23 SVG IIFE replaced by canvas ghost loader')
else:
    print('WARN: STEP23 markers not found, leaving as-is')

# ── PATCH 6: Hook ghost refresh into draw2's request-animation-frame chain
# (already done above with _refreshProjections alias)

# ── PATCH 7: Fetch projections2 when cam2 loads ───────────────────────
# Patch loadCam2 (in MULTICAM-STEP16) - both occurrences for safety.
old_load = '''        .then(d => {
          if (d && d.camera && d.camera.size) {
            camData2 = d.camera;
            window.camData2 = d.camera;
            resetMain2Zoom();
            if (typeof window.resizeOverlay === 'function') window.resizeOverlay();
            if (typeof window.draw2 === 'function') window.draw2();
          }
        })'''

new_load = '''        .then(d => {
          if (d && d.camera && d.camera.size) {
            camData2 = d.camera;
            window.camData2 = d.camera;
            // [CANVAS-GHOSTS] also store the real projections for pane 2 drawing
            projections2 = d.projections || [];
            window.projections2 = projections2;
            resetMain2Zoom();
            if (typeof window.resizeOverlay === 'function') window.resizeOverlay();
            if (typeof window.draw2 === 'function') window.draw2();
            if (typeof window._refreshGhosts === 'function') window._refreshGhosts();
          }
        })'''

n = c.count(old_load)
if n > 0:
    c = c.replace(old_load, new_load)
    print(f'Patch 7: {n}x loadCam2 patched to fetch projections2 + refresh ghosts')

# ── PATCH 8: Pane 2 mousemove for hover hit-test ─────────────────────
# Right after the pane 2 wheel/mousedown handlers (in STEP30 IIFE), add mousemove.
old_p2_md = '''  pane2.addEventListener('dblclick', () => { resetMain2Zoom(); draw2(); });
  console.log('[MULTICAM-STEP30] pane 2 pan/zoom wired up');'''

new_p2_md = '''  pane2.addEventListener('dblclick', () => { resetMain2Zoom(); draw2(); });

  // [CANVAS-GHOSTS] hover hit-test on pane 2
  pane2.addEventListener('mousemove', e => {
    const rect = pane2.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    // Test against real projections2 (marked pixels)
    let found = null;
    for (const lm of projections2) {
      if (!lm.marked_pixel) continue;
      const [cx, cy] = toCanvas2(lm.marked_pixel[0], lm.marked_pixel[1]);
      const dx = mx - cx, dy = my - cy;
      if (dx*dx + dy*dy < 64) { found = lm.name; break; }  // 8px radius
    }
    if (found !== hoveredLm2) { hoveredLm2 = found; draw2(); }
    // Test against ghosts
    let foundGhost = null;
    for (const g of ghostMarkers2) {
      if (g.type !== 'point') continue;
      const [cx, cy] = toCanvas2(g.pixel[0], g.pixel[1]);
      const dx = mx - cx, dy = my - cy;
      if (dx*dx + dy*dy < 64) { foundGhost = g.name; break; }
    }
    if (foundGhost !== hoveredGhost2) { hoveredGhost2 = foundGhost; draw2(); }
  });
  pane2.addEventListener('mouseleave', () => {
    if (hoveredLm2 !== null || hoveredGhost2 !== null) {
      hoveredLm2 = null; hoveredGhost2 = null; draw2();
    }
  });

  console.log('[MULTICAM-STEP30] pane 2 pan/zoom wired up');'''

if old_p2_md in c:
    c = c.replace(old_p2_md, new_p2_md, 1)
    print('Patch 8: pane 2 mousemove hover hit-test added')

# ── PATCH 9: Add ghost hover hit-test to pane 1 mousemove ────────────
# Find the existing mousemove handler in pane 1 and append ghost hit-test
old_p1_mm_end = '''  if (found !== hoveredLm) { hoveredLm = found; draw(); }'''
new_p1_mm_end = '''  if (found !== hoveredLm) { hoveredLm = found; draw(); }
  // [CANVAS-GHOSTS] Ghost hover hit-test on pane 1
  let foundGhost = null;
  for (const g of ghostMarkers1) {
    if (g.type !== 'point') continue;
    const [cx, cy] = toCanvas(g.pixel[0], g.pixel[1]);
    const dx = mx - cx, dy = my - cy;
    if (dx*dx + dy*dy < 64) { foundGhost = g.name; break; }
  }
  if (foundGhost !== hoveredGhost1) { hoveredGhost1 = foundGhost; draw(); }'''

if old_p1_mm_end in c:
    c = c.replace(old_p1_mm_end, new_p1_mm_end, 1)
    print('Patch 9: pane 1 mousemove ghost hit-test added')

with open(CALIB, 'w') as f:
    f.write(c)
print('\nAll canvas-ghost patches applied. Hard refresh.')
