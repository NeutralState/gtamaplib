"""
Multicam Step 30 — full pan/zoom for pane 2.

Adds independent pan/zoom on pane 2:
- New state: main2Zoom, main2PanX, main2PanY, main2Dragging, etc.
- New canvas: <canvas id="overlay-2"> inside #pane-2
- New camData2 (fetched via /api/cam?cam=cam2)
- New functions: baseScale2(), toCanvas2(), canvasToImg2(), resetMain2Zoom(), draw2()
- Event handlers on #pane-2 for wheel/mousedown/mouseup/dblclick
- resizeOverlay() also sizes overlay-2
- frame-img-2 gets the same inline-style treatment as frame-img

Pane 1 code is left untouched. We only ADD a parallel system for pane 2.

Idempotent: [MULTICAM-STEP30] marker.
"""

import os
import sys

CALIB = os.path.expanduser('~/Downloads/gtamaplib-main/tools/calib.html')
with open(CALIB) as f:
    c = f.read()

if '[MULTICAM-STEP30]' in c:
    print('Already patched.')
    sys.exit(0)

bak = CALIB + '.bak_multicam_step30'
with open(bak, 'w') as f: f.write(c)
print(f'Backup: {bak}')

# ── PATCH 1: Add overlay-2 canvas inside #pane-2 ──────────────────────
old_pane2 = '''      <img id="frame-img-2" src="" draggable="false">
      <!-- [MULTICAM-STEP23] LM projection overlay for pane 2 -->'''
new_pane2 = '''      <img id="frame-img-2" src="" draggable="false">
      <!-- [MULTICAM-STEP30] pane 2 overlay canvas for pan/zoom rendering -->
      <canvas id="overlay-2"></canvas>
      <!-- [MULTICAM-STEP23] LM projection overlay for pane 2 -->'''

if old_pane2 in c:
    c = c.replace(old_pane2, new_pane2, 1)
    print('Patch 1: overlay-2 canvas added in pane-2')
else:
    print('WARN: pane-2 img anchor not found')

# Add CSS for overlay-2 (mirrors #overlay)
old_css = '''#overlay{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none}'''
new_css = '''#overlay{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none}
/* [MULTICAM-STEP30] pane 2 overlay canvas (same role as #overlay for pane 1) */
#overlay-2{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none}'''

if old_css in c:
    c = c.replace(old_css, new_css, 1)
    print('Patch 2: #overlay-2 CSS added')

# ── PATCH 3: Add state variables for pane 2 ───────────────────────────
old_state = 'let mainZoom = 1, mainPanX = 0, mainPanY = 0, mainDragging = false, mainDragStart = null, mainPanStart = null;'
new_state = '''let mainZoom = 1, mainPanX = 0, mainPanY = 0, mainDragging = false, mainDragStart = null, mainPanStart = null;
// [MULTICAM-STEP30] pane 2 pan/zoom state
let main2Zoom = 1, main2PanX = 0, main2PanY = 0, main2Dragging = false, main2DragStart = null, main2PanStart = null;
let camData2 = null;  // set when cam 2 frame loads
window.camData2 = null;'''

if old_state in c:
    c = c.replace(old_state, new_state, 1)
    print('Patch 3: pane 2 state vars added')

# ── PATCH 4: Add baseScale2, canvasToImg2, resetMain2Zoom functions ──
old_fns_anchor = '''function resetMainZoom() {
  mainZoom = 1; mainPanX = 0; mainPanY = 0;
}'''

new_fns = '''function resetMainZoom() {
  mainZoom = 1; mainPanX = 0; mainPanY = 0;
}

// [MULTICAM-STEP30] Pane 2 equivalents of baseScale/toCanvas/canvasToImg/resetMainZoom
function baseScale2() {
  const overlay2 = document.getElementById('overlay-2');
  if (!camData2 || !camData2.size || !overlay2) return {scale:1, ox:0, oy:0};
  const [iw, ih] = camData2.size;
  const scale = Math.min(overlay2.width / iw, overlay2.height / ih);
  const ox = (overlay2.width  - iw * scale) / 2;
  const oy = (overlay2.height - ih * scale) / 2;
  return {scale, ox, oy};
}
function toCanvas2(px, py) {
  const {scale, ox, oy} = baseScale2();
  const bx = ox + px * scale;
  const by = oy + py * scale;
  return [main2PanX + bx * main2Zoom, main2PanY + by * main2Zoom];
}
function canvasToImg2(cx, cy) {
  const {scale, ox, oy} = baseScale2();
  const bx = (cx - main2PanX) / main2Zoom;
  const by = (cy - main2PanY) / main2Zoom;
  return [(bx - ox) / scale, (by - oy) / scale];
}
function resetMain2Zoom() {
  main2Zoom = 1; main2PanX = 0; main2PanY = 0;
}
window.baseScale2 = baseScale2;
window.resetMain2Zoom = resetMain2Zoom;'''

if old_fns_anchor in c:
    c = c.replace(old_fns_anchor, new_fns, 1)
    print('Patch 4: pane 2 helper functions added')

# ── PATCH 5: Add draw2() — apply pan/zoom to frame-img-2 ─────────────
# We inject draw2 right before the existing draw() function.
old_draw = 'function draw() {'
new_draw = '''// [MULTICAM-STEP30] Apply current pan/zoom to frame-img-2 by setting inline style.
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
window.draw2 = draw2;

function draw() {'''

if old_draw in c:
    c = c.replace(old_draw, new_draw, 1)
    print('Patch 5: draw2() function added')

# ── PATCH 6: Pane 2 event handlers (wheel + mousedown + dblclick) ────
# Inject right after the existing pane 1 dblclick handler
old_pane1_dblclick = "canvasWrap.addEventListener('dblclick', () => { resetMainZoom(); draw(); });"
new_handlers = old_pane1_dblclick + '''

// [MULTICAM-STEP30] Pane 2 wheel/pan/dblclick handlers (mirror of pane 1)
(() => {
  const pane2 = document.getElementById('pane-2');
  if (!pane2) return;

  pane2.addEventListener('wheel', e => {
    e.preventDefault();
    const rect = pane2.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const bx = (mx - main2PanX) / main2Zoom;
    const by = (my - main2PanY) / main2Zoom;
    const factor = e.deltaY < 0 ? 1.15 : 0.87;
    main2Zoom = Math.max(0.3, Math.min(32, main2Zoom * factor));
    main2PanX = mx - bx * main2Zoom;
    main2PanY = my - by * main2Zoom;
    draw2();
  }, {passive: false});

  pane2.addEventListener('mousedown', e => {
    // Allow shift-click + dropdown clicks to fall through to the cam list logic
    if (e.shiftKey) return;
    // Don't drag if clicking on the (legacy hidden) cam select wrap
    if (e.target.closest('#cam-sel-2-wrap')) return;
    main2Dragging = true;
    main2DragStart = [e.clientX, e.clientY];
    main2PanStart = [main2PanX, main2PanY];
    pane2.style.cursor = 'grabbing';
  });
  window.addEventListener('mousemove', e => {
    if (!main2Dragging) return;
    main2PanX = main2PanStart[0] + e.clientX - main2DragStart[0];
    main2PanY = main2PanStart[1] + e.clientY - main2DragStart[1];
    draw2();
  });
  window.addEventListener('mouseup', () => {
    if (main2Dragging) { main2Dragging = false; pane2.style.cursor = ''; }
  });
  pane2.addEventListener('dblclick', () => { resetMain2Zoom(); draw2(); });
  console.log('[MULTICAM-STEP30] pane 2 pan/zoom wired up');
})();'''

if old_pane1_dblclick in c:
    c = c.replace(old_pane1_dblclick, new_handlers, 1)
    print('Patch 6: pane 2 event handlers added')

# ── PATCH 7: Size overlay-2 in resizeOverlay() ───────────────────────
old_resize = '''  // [MULTICAM-STEP20] In dual mode, the overlay covers only pane 1 (top half).
  const _r = getMainPaneRect();
  overlay.width  = _r.width;
  overlay.height = _r.height;'''

new_resize = '''  // [MULTICAM-STEP20] In dual mode, the overlay covers only pane 1 (top half).
  const _r = getMainPaneRect();
  overlay.width  = _r.width;
  overlay.height = _r.height;
  // [MULTICAM-STEP30] Also size overlay-2 to match pane 2.
  const overlay2 = document.getElementById('overlay-2');
  const pane2 = document.getElementById('pane-2');
  if (overlay2 && pane2 && document.body.classList.contains('dual-cam')) {
    const p2r = pane2.getBoundingClientRect();
    overlay2.width = p2r.width;
    overlay2.height = p2r.height;
    draw2();
  }'''

if old_resize in c:
    c = c.replace(old_resize, new_resize, 1)
    print('Patch 7: resizeOverlay also handles overlay-2')

# ── PATCH 8: When cam 2 frame loads, fetch camData2 and trigger draw2 ──
# Find the loadCam2Frame function in MULTICAM-STEP16 and patch it.
old_load = '''    if (img2 && noImg2) {
      window.currentCam2 = camName;
      noImg2.style.display = 'flex';
      noImg2.textContent = 'Loading…';
      img2.src = `/frame/${encodeURIComponent(camName)}`;
      img2.onload = () => { noImg2.style.display = 'none'; };
      img2.onerror = () => { noImg2.textContent = 'No image'; };
    }'''

new_load = '''    if (img2 && noImg2) {
      window.currentCam2 = camName;
      noImg2.style.display = 'flex';
      noImg2.textContent = 'Loading…';
      img2.src = `/frame/${encodeURIComponent(camName)}`;
      img2.onload = () => {
        noImg2.style.display = 'none';
        // [MULTICAM-STEP30] Fetch camData2 and trigger draw2 on frame load.
        fetch('/api/cam?cam=' + encodeURIComponent(camName))
          .then(r => r.json())
          .then(d => {
            if (d && d.size) {
              camData2 = d;
              window.camData2 = d;
              resetMain2Zoom();
              if (typeof window.resizeOverlay === 'function') window.resizeOverlay();
              if (typeof window.draw2 === 'function') window.draw2();
            }
          })
          .catch(e => console.warn('[MULTICAM-STEP30] cam2 data fetch failed', e));
      };
      img2.onerror = () => { noImg2.textContent = 'No image'; };
    }'''

if old_load in c:
    c = c.replace(old_load, new_load, 1)
    print('Patch 8: cam2 frame load fetches camData2 + triggers draw2')

# ── PATCH 9: Expose refresh() of projection module on window for draw2 ───
old_refresh_export = '''  console.log('[MULTICAM-STEP23] projection overlays wired up');
})();'''

new_refresh_export = '''  window._refreshProjections = refresh;  // [MULTICAM-STEP30] for draw2 sync
  console.log('[MULTICAM-STEP23] projection overlays wired up');
})();'''

if old_refresh_export in c:
    c = c.replace(old_refresh_export, new_refresh_export, 1)
    print('Patch 9: refresh() exposed for draw2 sync')

with open(CALIB, 'w') as f:
    f.write(c)
print('\nAll patches applied.')
print('Test:')
print('  1. Hard refresh browser')
print('  2. Dual mode + cam1 + cam2')
print('  3. Wheel on pane 1 = zoom pane 1 (as before)')
print('  4. Wheel on pane 2 = zoom pane 2 (NEW!)')
print('  5. Drag pane 2 = pan pane 2 (NEW!)')
print('  6. Double-click pane 2 = reset zoom (NEW!)')
