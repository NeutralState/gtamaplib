"""
Multi-cam Step 1.0 — minimal split-view layout.

What this adds:
- A "Dual" toggle button in the toolbar (next to Rays/Heat)
- When activated:
  * .canvas-wrap splits horizontally into 2 panes (50/50)
  * Pane 2 has its own <img#frame-img-2> + a #cam-sel-2 dropdown to pick a cam
  * Pane 2 loads /frame/{cam2} just like pane 1
- When deactivated:
  * Pane 2 hidden, layout reverts to single-pane
  * State (currentCam2) preserved so re-toggle restores

What this does NOT add (later steps):
- Overlay canvas for pane 2 (no pixel marker visualization)
- Click handlers / pixel marking on pane 2
- Sync zoom/pan
- Epipolar lines
- Triangulated point projection

Single-cam workflow (current behavior) is completely unaffected when
dual mode is off. Maximum safety.

Idempotent: marker comment '[MULTICAM-STEP1]' makes re-runs no-op.
"""

import os
import sys

CALIB = os.path.expanduser('~/Downloads/gtamaplib-main/tools/calib.html')
BAK = CALIB + '.bak_multicam_step1'

with open(CALIB) as f:
    c = f.read()

if '[MULTICAM-STEP1]' in c:
    print('Already patched — skipping. Use .bak to revert if needed.')
    sys.exit(0)

with open(BAK, 'w') as f:
    f.write(c)
print(f'Backup: {BAK}')

# ───────────────────────────────────────────────────────────────────
# PATCH 1: CSS — add dual-cam layout rules
# ───────────────────────────────────────────────────────────────────
css_anchor = '.canvas-wrap{flex:1;position:relative;background:#000;overflow:hidden}\n#frame-img{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;pointer-events:none;user-select:none}'

css_new = '''.canvas-wrap{flex:1;position:relative;background:#000;overflow:hidden}
#frame-img{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;pointer-events:none;user-select:none}

/* [MULTICAM-STEP1] Dual-pane layout — only active when body.dual-cam is set.
   Splits .canvas-wrap horizontally into 2 equal-width panes. The 2nd pane
   (#pane-2) is hidden by default and only appears when Dual mode is on. */
.cam-pane{position:absolute;top:0;bottom:0;overflow:hidden;background:#000}
#pane-2{display:none}
body.dual-cam .canvas-wrap > #frame-img,
body.dual-cam .canvas-wrap > #overlay,
body.dual-cam .canvas-wrap > #no-img{
  /* Pane 1 (the original frame-img + overlay) constrains to left half */
  right:50%;width:auto
}
body.dual-cam #pane-2{display:block;left:50%;right:0}
#pane-2 > #frame-img-2{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;pointer-events:none;user-select:none}
#pane-2 > #cam-sel-2-wrap{position:absolute;top:8px;left:8px;z-index:11;
  background:rgba(0,0,0,0.7);border:1px solid #555;border-radius:4px;padding:4px 8px}
#pane-2 > #cam-sel-2-wrap select{font-family:JetBrains Mono,monospace;font-size:11px;
  background:transparent;color:#fff;border:none;outline:none;cursor:pointer;max-width:260px}
#pane-2 > #no-img-2{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  color:#666;font-family:JetBrains Mono,monospace;font-size:13px;pointer-events:none}
/* Visual divider between the 2 panes. */
body.dual-cam .canvas-wrap::after{content:'';position:absolute;top:0;bottom:0;left:50%;
  width:1px;background:#333;pointer-events:none;z-index:5}'''

if css_anchor not in c:
    print('ERROR: canvas-wrap CSS anchor not found')
    sys.exit(1)
c = c.replace(css_anchor, css_new, 1)
print('Patch 1/4: CSS added')

# ───────────────────────────────────────────────────────────────────
# PATCH 2: HTML — add #pane-2 inside .canvas-wrap, after #frame-img + #overlay
# ───────────────────────────────────────────────────────────────────
html_anchor = '''  <div class="canvas-wrap" id="canvas-wrap">
    <img id="frame-img" src="" draggable="false">
    <canvas id="overlay"></canvas>
    <div class="no-img" id="no-img">Select a camera to begin</div>'''

html_new = '''  <div class="canvas-wrap" id="canvas-wrap">
    <img id="frame-img" src="" draggable="false">
    <canvas id="overlay"></canvas>
    <div class="no-img" id="no-img">Select a camera to begin</div>
    <!-- [MULTICAM-STEP1] 2nd pane (frame-only, view-only for now) -->
    <div class="cam-pane" id="pane-2">
      <img id="frame-img-2" src="" draggable="false">
      <div id="no-img-2">Select a camera</div>
      <div id="cam-sel-2-wrap">
        <select id="cam-sel-2"><option value="">— Compare with —</option></select>
      </div>
    </div>'''

if html_anchor not in c:
    print('ERROR: HTML canvas-wrap anchor not found')
    sys.exit(1)
c = c.replace(html_anchor, html_new, 1)
print('Patch 2/4: HTML pane-2 inserted')

# ───────────────────────────────────────────────────────────────────
# PATCH 3: Button "Dual" in the toolbar (next to Tiles toggle area)
# ───────────────────────────────────────────────────────────────────
# We insert next to the Heat button using its anchor.
btn_anchor = '<button class="heat-toggle" id="heat-toggle" title="Show loss landscape for the selected cam (heat map)">Heat</button>'
btn_new = btn_anchor + '''
  <!-- [MULTICAM-STEP1] Toggle dual-pane comparison view (Camera view only) -->
  <button class="rays-toggle" id="dual-toggle" title="Compare two cams side-by-side (D)" style="display:inline-block">Dual</button>'''

# Note: .rays-toggle CSS already has display rules — for the Dual button we
# want it visible in Camera view (not Map view). Override via inline style.
# Actually rays-toggle is `display:none` by default and only shown in Map view.
# So we need our own visibility CSS. Let me do it via class.

if btn_anchor not in c:
    print('ERROR: Heat button anchor not found')
    sys.exit(1)
c = c.replace(btn_anchor, btn_new, 1)
print('Patch 3/4: Dual button inserted')

# Patch CSS so .dual-toggle is visible in Camera view (not Map view)
# Find the .rays-toggle CSS and add a sibling rule for #dual-toggle.
dual_css_anchor = '/* "Show all rays" toggle in the header, next to the view-toggle */'
dual_css_addition = dual_css_anchor + '''
/* [MULTICAM-STEP1] Dual toggle is visible in CAMERA view (opposite of Rays). */
#dual-toggle{display:none}
body:not(.view-map) #dual-toggle{display:inline-block}
body.dual-cam #dual-toggle{background:var(--blue);color:#000;border-color:var(--blue)}
'''
if dual_css_anchor in c:
    c = c.replace(dual_css_anchor, dual_css_addition, 1)
    print('       (dual button visibility CSS added)')

# ───────────────────────────────────────────────────────────────────
# PATCH 4: JS — wire up the toggle + 2nd cam selector
# ───────────────────────────────────────────────────────────────────
# We add a new JS block at the very end of the existing script, before </script>.
# Pick a unique anchor near the end.
js_anchor = '</script>\n</body>\n</html>'

js_new = '''
// ── [MULTICAM-STEP1] Dual-pane comparison view ────────────────────────
// Adds a 2nd cam preview pane alongside the main one. View-only for now:
// no overlay, no click handlers, no pixel marking. Next steps will add
// the overlay canvas, epipolar lines, and triangulated point projection.
(() => {
  const btnDual = document.getElementById('dual-toggle');
  const sel2    = document.getElementById('cam-sel-2');
  const img2    = document.getElementById('frame-img-2');
  const noImg2  = document.getElementById('no-img-2');
  if (!btnDual || !sel2 || !img2) {
    console.warn('[MULTICAM-STEP1] DOM not found — patch may need re-check');
    return;
  }
  window.currentCam2 = null;

  // Populate cam dropdown with the same list as #cam-sel.
  function populateCam2Dropdown() {
    const mainSel = document.getElementById('cam-sel');
    if (!mainSel) return;
    // Reset + rebuild
    sel2.innerHTML = '<option value="">— Compare with —</option>';
    for (const opt of mainSel.options) {
      if (!opt.value) continue;
      const clone = document.createElement('option');
      clone.value = opt.value;
      clone.textContent = opt.value;
      sel2.appendChild(clone);
    }
  }

  function loadCam2Frame(camName) {
    window.currentCam2 = camName || null;
    if (!camName) {
      img2.removeAttribute('src');
      noImg2.style.display = 'flex';
      noImg2.textContent = 'Select a camera';
      return;
    }
    noImg2.style.display = 'flex';
    noImg2.textContent = 'Loading…';
    img2.src = `/frame/${encodeURIComponent(camName)}`;
    img2.onload = () => { noImg2.style.display = 'none'; };
    img2.onerror = () => { noImg2.textContent = 'No image'; };
  }

  sel2.addEventListener('change', () => {
    loadCam2Frame(sel2.value);
  });

  btnDual.addEventListener('click', () => {
    const on = !document.body.classList.contains('dual-cam');
    document.body.classList.toggle('dual-cam', on);
    btnDual.classList.toggle('active', on);
    if (on) {
      populateCam2Dropdown();
      // If a cam was previously selected, reload its frame.
      if (window.currentCam2) loadCam2Frame(window.currentCam2);
    }
    console.log('[MULTICAM-STEP1] dual mode:', on);
  });

  // Re-populate dropdown when the main cam list changes (e.g. filter chips).
  const mainSel = document.getElementById('cam-sel');
  if (mainSel) {
    // Listen for option changes — use MutationObserver since the dropdown
    // is rebuilt by other code, not via .options API.
    const obs = new MutationObserver(() => {
      if (document.body.classList.contains('dual-cam')) populateCam2Dropdown();
    });
    obs.observe(mainSel, { childList: true });
  }

  // Keyboard shortcut: D toggles dual mode.
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
    if (e.key === 'd' || e.key === 'D') {
      btnDual.click();
    }
  });

  console.log('[MULTICAM-STEP1] dual-pane wired up');
})();
// ── end [MULTICAM-STEP1] ──────────────────────────────────────────────
</script>
</body>
</html>'''

if js_anchor not in c:
    print('ERROR: end-of-script anchor not found')
    sys.exit(1)
c = c.replace(js_anchor, js_new, 1)
print('Patch 4/4: JS wiring added')

with open(CALIB, 'w') as f:
    f.write(c)
print('\nAll patches applied. Hard refresh the browser and click Dual or press D.')
