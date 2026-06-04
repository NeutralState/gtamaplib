"""
Multi-cam Step 1.5 — top/bottom layout + sidebar-list pane 2 selection.

Changes:
1. CSS: dual-cam layout switches from left/right (50/50 horizontal split)
   to top/bottom (50/50 vertical split). Frames are 3840x2160 so vertical
   split preserves much more horizontal detail per pane.
2. HTML/CSS: remove the in-pane dropdown for pane 2. Cam 2 is now picked
   from the same sidebar list as cam 1 — shift-click an item in the list
   to assign it to pane 2.
3. JS: shift-click hook on the cam dropdown items. Visual indicators
   "→1" / "→2" badges on the currently-loaded cams.

Idempotent: marker [MULTICAM-STEP15] makes re-runs no-op.
"""

import os
import sys

CALIB = os.path.expanduser('~/Downloads/gtamaplib-main/tools/calib.html')

with open(CALIB) as f:
    c = f.read()

if '[MULTICAM-STEP15]' in c:
    print('Already patched — skipping.')
    sys.exit(0)

bak = CALIB + '.bak_multicam_step15'
with open(bak, 'w') as f: f.write(c)
print(f'Backup: {bak}')

# ── PATCH 1: CSS — switch layout from L/R to T/B ──────────────────────
# Find the existing dual-cam CSS block and replace the layout rules.
old_css = '''body.dual-cam .canvas-wrap > #frame-img,
body.dual-cam .canvas-wrap > #overlay,
body.dual-cam .canvas-wrap > #no-img{right:50%;width:auto}
body.dual-cam #pane-2{display:block;left:50%;right:0}
#pane-2 > #frame-img-2{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;pointer-events:none;user-select:none}
#pane-2 > #cam-sel-2-wrap{position:absolute;top:8px;left:8px;z-index:11;background:rgba(0,0,0,0.7);border:1px solid #555;border-radius:4px;padding:4px 8px}
#pane-2 > #cam-sel-2-wrap select{font-family:JetBrains Mono,monospace;font-size:11px;background:transparent;color:#fff;border:none;outline:none;cursor:pointer;max-width:260px}
#pane-2 > #no-img-2{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#666;font-family:JetBrains Mono,monospace;font-size:13px;pointer-events:none}
body.dual-cam .canvas-wrap::after{content:'';position:absolute;top:0;bottom:0;left:50%;width:1px;background:#333;pointer-events:none;z-index:5}'''

new_css = '''/* [MULTICAM-STEP15] Top/bottom split (was left/right).
   Pane 1 occupies the top 50%, pane 2 the bottom 50%. */
body.dual-cam .canvas-wrap > #frame-img,
body.dual-cam .canvas-wrap > #overlay,
body.dual-cam .canvas-wrap > #no-img{bottom:50%;height:auto}
body.dual-cam #pane-2{display:block;top:50%;bottom:0;left:0;right:0}
#pane-2 > #frame-img-2{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;pointer-events:none;user-select:none}
/* [MULTICAM-STEP15] in-pane dropdown removed — pane 2 cam is picked from
   the main sidebar via shift-click. */
#pane-2 > #cam-sel-2-wrap{display:none}
#pane-2 > #no-img-2{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#666;font-family:JetBrains Mono,monospace;font-size:13px;pointer-events:none}
/* Horizontal divider (was vertical at left:50%) */
body.dual-cam .canvas-wrap::after{content:'';position:absolute;left:0;right:0;top:50%;height:1px;background:#333;pointer-events:none;z-index:5}

/* [MULTICAM-STEP15] Sidebar cam item badges showing pane assignment. */
.cam-dropdown-item .pane-badge{display:inline-block;margin-left:6px;padding:0 5px;
  font-size:9px;font-weight:700;border-radius:3px;font-family:JetBrains Mono,monospace}
.cam-dropdown-item .pane-badge.p1{background:var(--green);color:#000}
.cam-dropdown-item .pane-badge.p2{background:var(--blue);color:#000}
body:not(.dual-cam) .cam-dropdown-item .pane-badge.p2{display:none}'''

if old_css in c:
    c = c.replace(old_css, new_css, 1)
    print('Patch 1/3: CSS swapped to top/bottom + badge styles')
else:
    print('WARN: dual-cam CSS anchor not found exactly')

# ── PATCH 2: JS — shift-click hook on the sidebar cam dropdown ────────
# Find where cam-dropdown items are clicked. We use event delegation on
# document.body so we don't need to know exact item DOM structure.
# Inject a shift-click handler near the existing MULTICAM-STEP1 block.

js_anchor = "// ── end [MULTICAM-STEP1] ──────────────────────────────────────────────"
js_new = '''// ── end [MULTICAM-STEP1] ──────────────────────────────────────────────

// ── [MULTICAM-STEP15] Sidebar pane-2 selection via shift-click ────────
// Pattern: normal click on a cam-dropdown item = set cam 1 (existing
// behavior). Shift-click = set cam 2 (new). Renders "→1" / "→2" badges
// on the currently-loaded cams so the assignment is visible at a glance.
(() => {
  // The cam-dropdown contains items with data-cam-name. We intercept the
  // shift-click before the default handler fires.
  // Use capture phase so we run BEFORE the existing cam1 click handler.
  document.addEventListener('click', (e) => {
    if (!e.shiftKey) return;  // Only handle shift-clicks
    const item = e.target.closest('.cam-dropdown-item, [data-cam-name]');
    if (!item) return;
    const camName = item.getAttribute('data-cam-name') || item.dataset.camName;
    if (!camName) return;
    // Block default selection (which would set cam 1).
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    // Ensure dual mode is on so pane 2 is visible.
    if (!document.body.classList.contains('dual-cam')) {
      const btnDual = document.getElementById('dual-toggle');
      if (btnDual) btnDual.click();
    }
    // Load the cam into pane 2.
    const img2 = document.getElementById('frame-img-2');
    const noImg2 = document.getElementById('no-img-2');
    if (img2 && noImg2) {
      window.currentCam2 = camName;
      noImg2.style.display = 'flex';
      noImg2.textContent = 'Loading…';
      img2.src = `/frame/${encodeURIComponent(camName)}`;
      img2.onload = () => { noImg2.style.display = 'none'; };
      img2.onerror = () => { noImg2.textContent = 'No image'; };
    }
    // Refresh badges and projections.
    setTimeout(updateCamBadges, 50);
    if (typeof window.tilesRender === 'function') window.tilesRender();
    console.log('[MULTICAM-STEP15] cam2 set to', camName);
  }, true);  // capture phase

  // Render "→1" / "→2" badges on the currently-loaded cams in the dropdown.
  function updateCamBadges() {
    const cam1 = window.currentCam;
    const cam2 = window.currentCam2;
    document.querySelectorAll('.cam-dropdown-item, [data-cam-name]').forEach(item => {
      // Clean existing badges
      item.querySelectorAll('.pane-badge').forEach(b => b.remove());
      const name = item.getAttribute('data-cam-name') || item.dataset.camName;
      if (!name) return;
      if (name === cam1) {
        const b = document.createElement('span');
        b.className = 'pane-badge p1';
        b.textContent = '→1';
        item.appendChild(b);
      }
      if (name === cam2 && document.body.classList.contains('dual-cam')) {
        const b = document.createElement('span');
        b.className = 'pane-badge p2';
        b.textContent = '→2';
        item.appendChild(b);
      }
    });
  }
  window.updateCamBadges = updateCamBadges;

  // Refresh badges when cam1 changes (other code already wires up #cam-sel change)
  const sel1 = document.getElementById('cam-sel');
  if (sel1) sel1.addEventListener('change', () => setTimeout(updateCamBadges, 100));

  // Refresh on dual toggle
  const btnDual = document.getElementById('dual-toggle');
  if (btnDual) btnDual.addEventListener('click', () => setTimeout(updateCamBadges, 100));

  // Initial render after the dropdown is populated. The dropdown is
  // populated in the existing init code; observe mutations to refresh.
  const dd = document.querySelector('.cam-dropdown') || document.body;
  const obs = new MutationObserver(() => updateCamBadges());
  obs.observe(dd, { childList: true, subtree: true });

  console.log('[MULTICAM-STEP15] shift-click pane-2 selection wired up');
})();
// ── end [MULTICAM-STEP15] ─────────────────────────────────────────────'''

if js_anchor in c:
    c = c.replace(js_anchor, js_new, 1)
    print('Patch 2/3: JS shift-click hook + badges injected')
else:
    print('WARN: STEP1 end anchor not found')

# ── PATCH 3: hide existing pane-2 dropdown (legacy fallback, kept in DOM) ─
# The CSS rule #pane-2 > #cam-sel-2-wrap{display:none} already hides it.
# Also disable the dropdown's change handler so it doesn't fire stale events.
# (For now, leaving the JS wiring intact — the element just isn't visible.)

with open(CALIB, 'w') as f:
    f.write(c)
print('\nAll patches applied. Hard refresh browser to test.')
print('Workflow:')
print('  1. Open Camera view')
print('  2. Click any cam in the sidebar list -> sets pane 1 (cam 1)')
print('  3. Click Dual (or press D) to enable dual mode')
print('  4. Shift-click any other cam in the sidebar list -> sets pane 2')
print('  5. Both frames stack vertically (top/bottom).')
print('  6. Projections (ghost LMs) render on both panes.')
