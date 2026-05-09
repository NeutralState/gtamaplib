#!/usr/bin/env python3
"""
patch_svg_phase7a_1_sidebar_preview.py — sidebar preview slot

Moves the bottom-left preview from a floating overlay in .canvas-wrap
into a fixed slot at the bottom of .left-sidebar. Adds a "swap" pattern:
  - Camera view: rotating minimap (CSS-only crop of /yanis.png — no
    server fetch, instant on cam switch).
  - Map view:    cam frame preview (full <img src="/frame/...">,
    object-fit:contain).

Rationale: matches the rlx reference UI shown to Alex. Always-on
context, never overlapping the working area.

Architecture:
  - HTML: new <div id="sb-preview-slot"> inserted at the bottom of
    .left-sidebar. It contains both #minimap-wrap (existing, relocated
    + restyled) and a new #cam-preview-wrap (the cam frame preview).
    The OLD floating #minimap-wrap inside .canvas-wrap is removed.
  - CSS: body.view-map toggles which inner element is visible. The
    slot is fixed-height (240×170-ish) at the bottom of the sidebar,
    above any scroll content (cam list scrolls above it).
  - JS: replaces loadMinimap() (server-side fetch, 5-6s) with a
    synchronous updateMinimap() that computes background-position +
    background-size from the cam's world coords + window.mapTransform
    (which we force-load at init via /api/map_data). Click handler
    on the minimap now navigates to map view (setView('map')) instead
    of toggling visibility off. The 'M' shortcut keeps toggle
    behaviour. Cam preview is just an <img> whose src is updated on
    cam change.

Pre-conditions for the CSS-only minimap:
  - window.mapTransform must be populated. Phase 3+4 only sets it
    when the user visits Map view. Phase 7a.1 fetches /api/map_data
    eagerly at script init so the minimap works from the first cam
    selection.
  - /yanis.png must be cached by the browser. First-cam-selection
    triggers a load; the same response is reused by Map view.

Idempotent. Dry-run by default.
Builds on Phase 6.3 (the Phase 6.4 attempts were reverted).
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase7a_1'

SENTINEL = '/* Phase 7a.1: sidebar preview slot (minimap CSS-only + cam preview) */'
PHASE6_3_SENTINEL = '/* // Phase 6.3: visual polish — fix ray colors + reduce noise */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: sidebar preview slot styles + appended sentinel.
# Anchor: end of the .left-sidebar / .ls-list block (Phase 2 styles).
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
.left-sidebar #cam-dropdown{position:static;display:block;border:none;border-radius:0;max-height:none;margin-top:0;background:transparent}
/* ── end SVG Map Refactor Phase 2 ── */"""

HUNK_1_NEW = """\
.left-sidebar #cam-dropdown{position:static;display:block;border:none;border-radius:0;max-height:none;margin-top:0;background:transparent}
/* ── end SVG Map Refactor Phase 2 ── */

/* ── SVG Map Refactor Phase 7a.1: sidebar preview slot ── */
/* Fixed-size preview slot at the bottom of the left sidebar.
   Hosts the minimap (Camera view) and the cam frame preview (Map view).
   Sized so the cam list scrolls above it without resizing on cam swap. */
.sb-preview-slot{flex-shrink:0;width:240px;height:170px;margin:8px 10px;
  border-radius:8px;overflow:hidden;
  border:1px solid var(--border);
  background:#0d0d12;
  position:relative}
.sb-preview-slot .preview-label{position:absolute;left:8px;top:6px;z-index:11;
  font-family:var(--mono);font-size:9px;color:var(--mid);
  background:rgba(0,0,0,0.55);padding:2px 6px;border-radius:3px;
  letter-spacing:.06em;text-transform:uppercase;pointer-events:none}
/* CSS-only minimap: a positioning container whose inner element holds
   the full /yanis.png as background-image, sized + positioned per cam. */
#minimap-wrap-sb{position:absolute;inset:0;overflow:hidden;cursor:pointer}
#minimap-rotator-sb{position:absolute;width:200%;height:200%;left:-50%;top:-50%;
  transform-origin:50% 50%;transition:transform 120ms ease-out}
#minimap-img-sb{position:absolute;inset:0;
  background-image:url('/yanis.png');
  background-repeat:no-repeat;
  /* JS sets background-position and background-size per cam */
  background-color:#222}
#minimap-pointer-sb{position:absolute;inset:0;pointer-events:none}
/* Cam preview slot — shown only in map view */
#cam-preview-wrap{position:absolute;inset:0;display:none;
  align-items:center;justify-content:center;background:#000}
#cam-preview-img{max-width:100%;max-height:100%;object-fit:contain;
  display:block;user-select:none;-webkit-user-drag:none}
#cam-preview-empty{font-family:var(--mono);font-size:10px;color:var(--dim);
  padding:14px;text-align:center}
body.view-map #minimap-wrap-sb{display:none}
body.view-map #cam-preview-wrap{display:flex}
/* ── end SVG Map Refactor Phase 7a.1 ── */
/* Phase 7a.1: sidebar preview slot (minimap CSS-only + cam preview) */"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — HTML: remove the OLD floating #minimap-wrap from .canvas-wrap.
# Anchor: the entire existing minimap-wrap block (5 lines of HTML).
# Replaces with an HTML comment placeholder so the surrounding markup
# context stays the same.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
    <!-- ── GTA VI-style rotating minimap (bottom-left, rounded rect) ─── -->
    <div id="minimap-wrap" style="position:absolute;bottom:14px;left:14px;
        z-index:10;width:260px;height:180px;border-radius:10px;
        overflow:hidden;border:2px solid rgba(0,0,0,0.8);
        background:rgba(0,0,0,0.4);
        box-shadow:0 4px 14px rgba(0,0,0,0.55);
        display:none;cursor:pointer" title="Click to toggle (M)">
      <!-- Rotator is OVERSIZED so corners are covered when rotated -->
      <div id="minimap-rotator" style="position:absolute;
          width:200%;height:200%;
          left:-50%;top:-50%;
          transform-origin:50% 50%;transition:transform 120ms ease-out">
        <img id="minimap-img" src="" style="position:absolute;width:100%;
          height:100%;left:0;top:0;display:block;background:#222;
          object-fit:cover">
      </div>
      <!-- Fixed view cone (always points up = cam direction) -->
      <svg style="position:absolute;width:100%;height:100%;left:0;top:0;
          pointer-events:none" viewBox="0 0 260 180" preserveAspectRatio="none">
        <path d="M 130,80 L 138,96 L 130,92 L 122,96 Z"
          fill="#ffffff" stroke="#000000"
          stroke-width="1.2" stroke-linejoin="round" stroke-linecap="round"/>
      </svg>
    </div>"""

HUNK_2_NEW = """\
    <!-- Phase 7a.1: floating minimap removed — relocated to the
         left sidebar's preview slot (#sb-preview-slot). -->"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — HTML: insert the new #sb-preview-slot at the bottom of
# .left-sidebar (after the .ls-list and the hidden <select>).
# Anchor: the closing </aside> of the left sidebar.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
    <select id="cam-sel" hidden><option value="">— Select camera —</option></select>
  </aside>"""

HUNK_3_NEW = """\
    <select id="cam-sel" hidden><option value="">— Select camera —</option></select>
    <!-- Phase 7a.1: sidebar preview slot. Camera view shows a CSS-only
         minimap; Map view shows the cam frame preview. Toggled by
         body.view-map class. -->
    <div class="sb-preview-slot" id="sb-preview-slot">
      <div id="minimap-wrap-sb" title="Click to open Map view (M to toggle)">
        <div id="minimap-rotator-sb">
          <div id="minimap-img-sb"></div>
        </div>
        <svg id="minimap-pointer-sb" viewBox="0 0 240 170" preserveAspectRatio="none">
          <path d="M 120,75 L 128,91 L 120,87 L 112,91 Z"
            fill="#ffffff" stroke="#000000"
            stroke-width="1.2" stroke-linejoin="round" stroke-linecap="round"/>
        </svg>
      </div>
      <div id="cam-preview-wrap">
        <img id="cam-preview-img" src="" alt="">
        <div id="cam-preview-empty">No camera selected</div>
      </div>
    </div>
  </aside>"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 4 — JS: replace the entire minimap block (loadMinimap + handlers).
# Anchor: the comment header through the last keydown handler.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_4_OLD = """\
// ── GTA-style rotating minimap (bottom-left) ────────────────────────────
const minimapWrap = document.getElementById('minimap-wrap');
const minimapRotator = document.getElementById('minimap-rotator');
const minimapImg = document.getElementById('minimap-img');
let minimapEnabled = true;

async function loadMinimap() {
  if (!currentCam || !minimapEnabled) {
    minimapWrap.style.display = 'none';
    return;
  }
  try {
    const res = await fetch(`/api/minimap?cam=${encodeURIComponent(currentCam)}&radius=350`);
    if (!res.ok) {
      console.warn('minimap status', res.status);
      minimapWrap.style.display = 'none';
      return;
    }
    const data = await res.json();
    if (data.error) {
      console.warn('minimap error', data.error);
      minimapWrap.style.display = 'none';
      return;
    }
    minimapImg.src = 'data:image/png;base64,' + data.image_b64;
    // Rotate so cam direction (yaw) points UP. Yaw 0 = north.
    minimapRotator.style.transform = `rotate(${-data.yaw}deg)`;
    minimapWrap.style.display = 'block';
  } catch (e) {
    console.error('minimap fetch failed', e);
    minimapWrap.style.display = 'none';
  }
}

// Auto-update on cam change
let _minimapLastCam = null;
setInterval(() => {
  if (currentCam !== _minimapLastCam) {
    _minimapLastCam = currentCam;
    loadMinimap();
  }
}, 250);

// Live yaw update from slider (instant, no fetch)
const _slYaw = document.getElementById('sl-yaw');
if (_slYaw) {
  _slYaw.addEventListener('input', () => {
    const yaw = parseFloat(_slYaw.value);
    if (!isNaN(yaw)) minimapRotator.style.transform = `rotate(${-yaw}deg)`;
  });
}

// Toggle on click + 'M' shortcut
minimapWrap.addEventListener('click', () => {
  minimapEnabled = false;
  minimapWrap.style.display = 'none';
});
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'm' || e.key === 'M') {
    minimapEnabled = !minimapEnabled;
    if (minimapEnabled) loadMinimap();
    else minimapWrap.style.display = 'none';
  }
});"""

HUNK_4_NEW = """\
// ── Phase 7a.1: CSS-only minimap (sidebar) + cam preview ──────────────────
// The minimap is a CSS background-image crop of /yanis.png — no fetch.
// In Map view, the same slot shows the cam's frame as a static <img>.
// Both elements live in #sb-preview-slot (bottom of the left sidebar).
//
// CSS-only minimap math:
//   We want to display a `radius`-meter window around the cam, scaled to
//   fit the slot width. Given window.mapTransform (the same metadata
//   used by Map view), the cam center in PNG-pixel space is:
//     [px_cx, px_cy] = window.worldToSvg(cam.xyz[0], cam.xyz[1])
//   (The PNG is rendered at viewBox 0 0 svg_size, so SVG-user coords
//   are 1:1 with pixel coords.)
//   The PNG is 12000 px wide in our build; window.mapTransform.svg_size
//   gives the exact dimensions.
//   We size the inner #minimap-img-sb so that `radius` map-units fit
//   inside half the slot width (slot is 240 CSS px wide; we use the
//   inner #minimap-rotator-sb which is 480×340 — 200% — so radius maps
//   to 240 CSS px in rotator space). Then we offset so [px_cx, px_cy]
//   lands at the rotator center.
const minimapWrap   = document.getElementById('minimap-wrap-sb');
const minimapRotator = document.getElementById('minimap-rotator-sb');
const minimapBg     = document.getElementById('minimap-img-sb');
const camPreviewImg = document.getElementById('cam-preview-img');
const camPreviewEmpty = document.getElementById('cam-preview-empty');
let minimapEnabled = true;
const MINIMAP_RADIUS = 350;  // map-units around the cam to show

async function ensureMapTransform() {
  // Phase 3+4 lazy-loads /api/map_data only on first Map view visit.
  // Phase 7a.1 needs window.mapTransform up-front for the minimap.
  if (window.mapTransform) return;
  try {
    const data = await fetch('/api/map_data').then(r => r.json());
    window.mapData = window.mapData || data;
    window.mapTransform = data.transform;
  } catch (e) {
    console.warn('Phase 7a.1: failed to preload /api/map_data', e);
  }
}

function updateMinimap() {
  if (!minimapEnabled) {
    minimapWrap.style.display = 'none';
    return;
  }
  if (!currentCam || !camData?.xyz || !window.mapTransform) {
    minimapWrap.style.display = 'block';
    minimapBg.style.backgroundImage = 'none';  // empty
    return;
  }
  const [pxCx, pxCy] = window.worldToSvg(camData.xyz[0], camData.xyz[1]);
  const sz = window.mapTransform.svg_size;  // [w, h] of the PNG in px
  // Rotator is 480 CSS px wide (200% of 240). We want `2*MINIMAP_RADIUS`
  // map-units to span 480 CSS px ⇒ scale = 480 / (2*MINIMAP_RADIUS).
  const rotW = 480, rotH = 340;
  const scale = rotW / (2 * MINIMAP_RADIUS);
  const bgW = sz[0] * scale;
  const bgH = sz[1] * scale;
  // Background-position: we want the cam pixel to land at the rotator
  // center (rotW/2, rotH/2). Background-position is the offset of the
  // image's TOP-LEFT corner. So image_top_left = center - cam_px.
  const bgX = (rotW / 2) - (pxCx * scale);
  const bgY = (rotH / 2) - (pxCy * scale);
  minimapBg.style.backgroundImage = "url('/yanis.png')";
  minimapBg.style.backgroundSize = `${bgW}px ${bgH}px`;
  minimapBg.style.backgroundPosition = `${bgX}px ${bgY}px`;
  // Rotate so cam direction (yaw) points UP. Yaw 0 = north.
  const yaw = (camData.ypr && camData.ypr.length >= 1) ? camData.ypr[0] : 0;
  minimapRotator.style.transform = `rotate(${-yaw}deg)`;
  minimapWrap.style.display = 'block';
}
window.updateMinimap = updateMinimap;

function updateCamPreview() {
  if (!currentCam) {
    camPreviewImg.style.display = 'none';
    camPreviewImg.src = '';
    camPreviewEmpty.style.display = 'block';
    return;
  }
  camPreviewEmpty.style.display = 'none';
  camPreviewImg.style.display = 'block';
  // Re-use the /frame/ endpoint (cached by browser).
  camPreviewImg.src = '/frame/' + encodeURIComponent(currentCam);
}
window.updateCamPreview = updateCamPreview;

// Auto-update on cam change. Both updaters are cheap (no fetch in
// minimap; cam preview is browser-cached after first load).
let _previewLastCam = null;
setInterval(() => {
  if (currentCam !== _previewLastCam) {
    _previewLastCam = currentCam;
    updateMinimap();
    updateCamPreview();
  }
}, 250);

// Live yaw update from slider (instant, no fetch)
const _slYaw = document.getElementById('sl-yaw');
if (_slYaw) {
  _slYaw.addEventListener('input', () => {
    const yaw = parseFloat(_slYaw.value);
    if (!isNaN(yaw)) minimapRotator.style.transform = `rotate(${-yaw}deg)`;
  });
}

// Click on the minimap → switch to Map view (matches rlx reference UI).
minimapWrap.addEventListener('click', () => {
  if (typeof window.setView === 'function') window.setView('map');
});

// 'M' shortcut: toggle minimap visibility (kept for parity with old behaviour).
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'm' || e.key === 'M') {
    minimapEnabled = !minimapEnabled;
    if (minimapEnabled) updateMinimap();
    else minimapWrap.style.display = 'none';
  }
});

// Eagerly prefetch map metadata so the minimap works on first cam selection.
ensureMapTransform().then(() => {
  if (currentCam) updateMinimap();
});"""


HUNKS = [
    ('CSS — sidebar preview slot styles + sentinel', HUNK_1_OLD, HUNK_1_NEW),
    ('HTML — remove floating minimap from canvas-wrap', HUNK_2_OLD, HUNK_2_NEW),
    ('HTML — add #sb-preview-slot to left sidebar',  HUNK_3_OLD, HUNK_3_NEW),
    ('JS — replace loadMinimap with CSS-only updateMinimap + cam preview', HUNK_4_OLD, HUNK_4_NEW),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--revert', action='store_true')
    args = ap.parse_args()

    if not os.path.exists(CALIB_HTML):
        print(f'ERROR: {CALIB_HTML} not found.')
        sys.exit(1)

    if args.revert:
        if not os.path.exists(BACKUP):
            print(f'ERROR: no backup at {BACKUP}.')
            sys.exit(1)
        if args.apply:
            shutil.copy(BACKUP, CALIB_HTML)
            print(f'✓ Restored {CALIB_HTML} from {BACKUP}.')
        else:
            print(f'(dry-run) would restore from {BACKUP}.')
        return

    with open(CALIB_HTML, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print('✓ Already patched.')
        return

    if PHASE6_3_SENTINEL not in src:
        print('ERROR: Phase 6.3 sentinel not found. Apply Phase 6.3 first.')
        sys.exit(1)

    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} times (need exactly 1).')
            sys.exit(1)

    new_src = src
    for _label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    delta = new_src.count('\n') - src.count('\n')
    print(f'Will modify {CALIB_HTML} ({delta:+d} lines)')
    print(f'  hunks applied: {len(HUNKS)}')

    if not args.apply:
        print('\n(dry-run — re-run with --apply)')
        return

    shutil.copy(CALIB_HTML, BACKUP)
    print(f'\n✓ Backup: {BACKUP}')
    tmp = CALIB_HTML + '.tmp'
    with open(tmp, 'w') as f:
        f.write(new_src)
    os.replace(tmp, CALIB_HTML)
    print(f'✓ Patched {CALIB_HTML}')
    print()
    print('Test: hard reload, select a cam.')
    print('  - Camera view: minimap appears at bottom of left sidebar')
    print('    (rotates with yaw, no server fetch, instant)')
    print('  - Click minimap → switches to Map view')
    print('  - Map view: the same slot shows the cam frame preview')
    print('  - Switch cams: minimap re-positions instantly, preview swaps')
    print('  - "M" key still toggles minimap visibility (legacy)')
    print()
    print('After this works: apply phase7a_2 to drop /api/minimap server-side.')


if __name__ == '__main__':
    main()
