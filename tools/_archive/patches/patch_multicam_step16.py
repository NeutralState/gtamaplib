"""
Multicam Step 1.6 — fix pane 1 resize + smarter pane assignment.

P1: When toggling Dual mode, pane 1's frame img + overlay + no-img need
    to adapt to the new half-height. The CSS rule was bottom:50%;height:auto
    which should work but the #overlay canvas has explicit width/height
    attributes set by resizeOverlay() that were computed pre-dual. Force
    a resize tick on dual toggle.

P2: Click on sidebar cam = goes to the "non-last-used" pane. So after
    setting cam 1, the next normal click goes to cam 2 (no shift needed).
    Then next normal click goes back to cam 1 (the older one). Tracks
    "last touched pane" to decide.

P3 (projections) handled separately after these two.

Idempotent: [MULTICAM-STEP16] marker.
"""

import os
import sys

CALIB = os.path.expanduser('~/Downloads/gtamaplib-main/tools/calib.html')
with open(CALIB) as f:
    c = f.read()

if '[MULTICAM-STEP16]' in c:
    print('Already patched.')
    sys.exit(0)

bak = CALIB + '.bak_multicam_step16'
with open(bak, 'w') as f: f.write(c)
print(f'Backup: {bak}')

# ── PATCH 1: P2 — replace the shift-click logic with last-touched toggle ──
# We replace the entire [MULTICAM-STEP15] JS block.
old_marker_start = '// ── [MULTICAM-STEP15] Sidebar pane-2 selection via shift-click ────────'
old_marker_end   = '// ── end [MULTICAM-STEP15] ─────────────────────────────────────────────'

start = c.find(old_marker_start)
end = c.find(old_marker_end)
if start < 0 or end < 0:
    print('ERROR: STEP15 block markers not found')
    sys.exit(1)
end += len(old_marker_end)

new_block = '''// ── [MULTICAM-STEP16] Smart pane assignment (replaces STEP15) ────────
// Behavior:
//   - Single mode: click sidebar cam = goes to cam 1 (default behavior).
//   - Dual mode: click sidebar cam = goes to the OPPOSITE of last-touched.
//     First click after enabling dual: pane 1 (no change in default flow).
//     Second click: pane 2. Third: pane 1 again. Etc.
//   - Visual badges "→1" / "→2" show which cams are loaded in which pane.
(() => {
  // Track which pane was last assigned to. Default to 2 so the FIRST click
  // after enabling dual mode goes to pane 1 (the natural default).
  window._lastAssignedPane = 2;

  function loadCam2(camName) {
    const img2 = document.getElementById('frame-img-2');
    const noImg2 = document.getElementById('no-img-2');
    if (!img2 || !noImg2) return;
    window.currentCam2 = camName;
    noImg2.style.display = 'flex';
    noImg2.textContent = 'Loading…';
    img2.src = `/frame/${encodeURIComponent(camName)}`;
    img2.onload = () => { noImg2.style.display = 'none'; };
    img2.onerror = () => { noImg2.textContent = 'No image'; };
  }

  // Capture-phase click handler: intercepts before the existing cam1 handler.
  document.addEventListener('click', (e) => {
    // Only act in dual mode.
    if (!document.body.classList.contains('dual-cam')) return;
    const item = e.target.closest('.cam-dropdown-item, [data-cam-name]');
    if (!item) return;
    const camName = item.getAttribute('data-cam-name') || item.dataset.camName;
    if (!camName) return;

    const nextPane = window._lastAssignedPane === 1 ? 2 : 1;

    if (nextPane === 2) {
      // Block the default (which would set cam 1) and assign cam 2 instead.
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      loadCam2(camName);
      window._lastAssignedPane = 2;
      setTimeout(updateCamBadges, 50);
      console.log('[MULTICAM-STEP16] cam2 set to', camName);
    } else {
      // Let the default handler run (it sets cam 1).
      // We just mark last-assigned as 1 so the next click flips to 2.
      window._lastAssignedPane = 1;
      setTimeout(updateCamBadges, 100);
      console.log('[MULTICAM-STEP16] cam1 set to', camName);
    }
  }, true);  // capture phase

  // Shift+click as explicit pane 2 override (kept from STEP15 for power users).
  document.addEventListener('click', (e) => {
    if (!e.shiftKey) return;
    if (!document.body.classList.contains('dual-cam')) return;
    const item = e.target.closest('.cam-dropdown-item, [data-cam-name]');
    if (!item) return;
    const camName = item.getAttribute('data-cam-name') || item.dataset.camName;
    if (!camName) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    loadCam2(camName);
    window._lastAssignedPane = 2;
    setTimeout(updateCamBadges, 50);
  }, true);

  function updateCamBadges() {
    const cam1 = window.currentCam;
    const cam2 = window.currentCam2;
    document.querySelectorAll('.cam-dropdown-item, [data-cam-name]').forEach(item => {
      item.querySelectorAll('.pane-badge').forEach(b => b.remove());
      const name = item.getAttribute('data-cam-name') || item.dataset.camName;
      if (!name) return;
      if (name === cam1) {
        const b = document.createElement('span');
        b.className = 'pane-badge p1';
        b.textContent = '\u21921';
        item.appendChild(b);
      }
      if (name === cam2 && document.body.classList.contains('dual-cam')) {
        const b = document.createElement('span');
        b.className = 'pane-badge p2';
        b.textContent = '\u21922';
        item.appendChild(b);
      }
    });
  }
  window.updateCamBadges = updateCamBadges;

  // [MULTICAM-STEP16] On dual toggle: reset last-assigned to 2, force resize
  // of the overlay canvas so pane 1's overlay re-fits the new half-height.
  const btnDual = document.getElementById('dual-toggle');
  if (btnDual) {
    btnDual.addEventListener('click', () => {
      window._lastAssignedPane = 2;  // Next click goes to pane 1 by default
      setTimeout(() => {
        // Force overlay canvas to recompute its size after layout shift.
        if (typeof window.resizeOverlay === 'function') {
          try { window.resizeOverlay(); } catch (e) { /* ignore */ }
        }
        // Also dispatch a synthetic resize event for any other listeners
        // (the tile renderer, the projection overlay, etc.).
        window.dispatchEvent(new Event('resize'));
        updateCamBadges();
      }, 100);
    });
  }

  const sel1 = document.getElementById('cam-sel');
  if (sel1) sel1.addEventListener('change', () => setTimeout(updateCamBadges, 100));

  // Refresh badges whenever the cam list is rebuilt.
  const dd = document.querySelector('.cam-dropdown') || document.body;
  const obs = new MutationObserver(() => updateCamBadges());
  obs.observe(dd, { childList: true, subtree: true });

  console.log('[MULTICAM-STEP16] smart pane assignment wired up');
})();
// ── end [MULTICAM-STEP16] ─────────────────────────────────────────────'''

c = c[:start] + new_block + c[end:]
print('Patch 1/2: STEP15 block replaced with STEP16 (smart pane assignment)')

# ── PATCH 2: P1 — also expose resizeOverlay as window.* so we can call it ─
# The function `resizeOverlay()` exists in the main code; we need it on window.
# Find the function definition and add a window assignment after.
rs_anchor = 'function resizeOverlay()'
if rs_anchor in c and 'window.resizeOverlay = resizeOverlay' not in c:
    # Insert right after the function declaration line — find the matching {
    # but easier: just add `window.resizeOverlay = resizeOverlay;` somewhere
    # that executes after the function is defined.
    # The simplest reliable place: right after the first occurrence + closing brace.
    # We use a different approach: inject the assignment after a unique line
    # that we know exists in the resizeOverlay area.

    # Look for the resize-overlay call inside the frame img onload:
    onload_anchor = "frameImg.onload  = () => { noImg.style.display = 'none'; resizeOverlay(); };"
    if onload_anchor in c:
        replacement = onload_anchor + '\n  window.resizeOverlay = resizeOverlay;  // [MULTICAM-STEP16] expose for dual-mode resize trigger'
        c = c.replace(onload_anchor, replacement, 1)
        print('Patch 2/2: resizeOverlay exposed on window')
    else:
        print('WARN: frameImg.onload anchor not found, resizeOverlay not exposed')
else:
    print('       (resizeOverlay already exposed or function missing)')

with open(CALIB, 'w') as f: f.write(c)
print('\nDone. Hard refresh browser to test.')
print('  - Click a cam = pane 1 (as before)')
print('  - Click Dual (D) = enables split, pane 1 frame shrinks to top half')
print('  - Click another cam = goes to pane 2 (since last was pane 1)')
print('  - Click another cam = goes back to pane 1 (toggles)')
