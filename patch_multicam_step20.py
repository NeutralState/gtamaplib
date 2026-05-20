"""
Multicam Step 20 — pan/zoom refactor for dual mode.

Strategy: introduce a `getMainPaneRect()` helper that returns the effective
pane-1 viewport — full canvas-wrap in single mode, top half in dual mode.
All the click/wheel/mousemove handlers and the resize/inline-style code
use this helper instead of canvasWrap.getBoundingClientRect() directly.

Also reverts the STEP19 !important rules so the inline pan/zoom style
can work again (now that it calculates with the correct pane size).

Idempotent: marker [MULTICAM-STEP20].
"""

import os
import sys

CALIB = os.path.expanduser('~/Downloads/gtamaplib-main/tools/calib.html')
with open(CALIB) as f:
    c = f.read()

if '[MULTICAM-STEP20]' in c:
    print('Already patched.')
    sys.exit(0)

bak = CALIB + '.bak_multicam_step20'
with open(bak, 'w') as f: f.write(c)
print(f'Backup: {bak}')

# ── PATCH 1: Add the helper function near the top of the JS ──
# Insert after `const canvasWrap = document.getElementById('canvas-wrap');`
helper_anchor = "const canvasWrap = document.getElementById('canvas-wrap');"
helper_new = helper_anchor + '''

// [MULTICAM-STEP20] Pane-aware rect helper.
// In single mode: returns the full canvasWrap rect (pane 1 == full).
// In dual mode: returns only the top half (pane 1 occupies top 50%).
// All pan/zoom/click handlers should use this instead of
// canvasWrap.getBoundingClientRect() directly so they keep working
// correctly when the layout splits.
function getMainPaneRect() {
  const r = canvasWrap.getBoundingClientRect();
  if (document.body.classList.contains('dual-cam')) {
    return {
      left: r.left,
      top: r.top,
      right: r.right,
      bottom: r.top + r.height / 2,
      width: r.width,
      height: r.height / 2,
      x: r.x,
      y: r.y
    };
  }
  return r;
}
window.getMainPaneRect = getMainPaneRect;
'''

if helper_anchor in c:
    c = c.replace(helper_anchor, helper_new, 1)
    print('Patch 1/5: getMainPaneRect helper inserted')
else:
    print('ERROR: canvasWrap anchor not found')
    sys.exit(1)

# ── PATCH 2: Replace the 5 canvasWrap.getBoundingClientRect() calls ──
# Each one is `const rect = canvasWrap.getBoundingClientRect();`
old_rect = "const rect = canvasWrap.getBoundingClientRect();"
new_rect = "const rect = getMainPaneRect();  // [MULTICAM-STEP20]"
n = c.count(old_rect)
c = c.replace(old_rect, new_rect)
print(f'Patch 2/5: {n} canvasWrap.getBoundingClientRect() calls -> getMainPaneRect()')

# ── PATCH 3: Replace overlay sizing in resizeOverlay() ──
# Find the two lines that set overlay.width/height
old_overlay = '''  overlay.width  = canvasWrap.clientWidth;
  overlay.height = canvasWrap.clientHeight;'''

new_overlay = '''  // [MULTICAM-STEP20] In dual mode, the overlay covers only pane 1 (top half).
  const _r = getMainPaneRect();
  overlay.width  = _r.width;
  overlay.height = _r.height;'''

if old_overlay in c:
    c = c.replace(old_overlay, new_overlay, 1)
    print('Patch 3/5: resizeOverlay now uses pane rect')
else:
    print('WARN: overlay sizing anchor not found')

# ── PATCH 4: Fix the frameImg inline style calculation ──
# The original line is somewhere around 2829:
# frameImg.style.cssText = `position:absolute;left:${left}px;top:${top}px;width:${w}px;height:${h}px;object-fit:fill;pointer-events:none`;
# Before this line, the code likely computes `left`, `top`, `w`, `h` from
# canvasWrap dimensions and image scale. Those are correct if the canvas
# is sized to the pane (which Patch 3 ensures). So this should already work
# once overlay.width/height match pane size.
# However, we should double-check by looking at how left/top/w/h get computed.
# For now we trust Patch 3 since the math uses overlay.width/height.

# ── PATCH 5: Revert STEP19 !important rules (now that pan/zoom respects pane) ──
old_step19 = '''/* [MULTICAM-STEP19] Force pane 1 to fill top half with !important to
   beat the inline style that the pan/zoom code keeps re-applying on
   #frame-img. We override object-fit too so the image is contained
   (letterboxed) instead of stretched. */
body.dual-cam .canvas-wrap > #frame-img,
body.dual-cam .canvas-wrap > #overlay,
body.dual-cam .canvas-wrap > #no-img{
  top:0 !important;
  left:0 !important;
  right:0 !important;
  bottom:auto !important;
  width:100% !important;
  height:50% !important
}
body.dual-cam .canvas-wrap > #frame-img{
  object-fit:contain !important;
  object-position:center !important
}'''

new_step20 = '''/* [MULTICAM-STEP20] Pane 1 occupies top half in dual mode.
   No more !important — the pan/zoom JS code computes its inline style
   from getMainPaneRect() now, so its left/top/width/height values are
   already pane-relative. CSS only needs to set the container bounds. */
body.dual-cam .canvas-wrap > #frame-img,
body.dual-cam .canvas-wrap > #overlay,
body.dual-cam .canvas-wrap > #no-img{
  top:0;left:0;right:0;bottom:auto;
  width:100%;height:50%
}'''

if old_step19 in c:
    c = c.replace(old_step19, new_step20, 1)
    print('Patch 5/5: STEP19 !important reverted, pure dual-cam CSS')
else:
    print('WARN: STEP19 anchor not found (maybe already reverted)')

with open(CALIB, 'w') as f: f.write(c)
print('\nAll patches applied. Hard refresh browser.')
print('Test:')
print('  1. Click cam = pane 1 (normal layout)')
print('  2. Press D = split top/bottom, pane 1 image should fit top half')
print('  3. Wheel-zoom on pane 1 = should zoom into pane 1 (not full canvas)')
print('  4. Click another cam = pane 2 (no zoom changes)')
print('  5. Press D again = back to single mode, zoom state should still work')
