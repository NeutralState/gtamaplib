#!/usr/bin/env python3
"""
patch_svg_phase34_html.py — Phase 3+4 (PNG version): view toggle + map view

Adds the [Camera | Map] toggle and a Map view that renders the pre-rendered
4K PNG of the yanis map. Pan/zoom is via CSS transform on the wrapper, with
an empty SVG overlay layered on top — Phase 5+ will draw camera markers
and landmark dots into that overlay.

Why PNG instead of SVG: the 85MB vector SVG was too heavy for the browser
to pan/zoom at 60 FPS (re-rasterization on every transform). A 4K PNG
(~4 MB) loads in <500ms and pans/zooms via GPU compositing on any hardware.

Builds on Phase 2 + 2.1 (left sidebar). Pre-flight verifies their sentinels.

Idempotent. Dry-run by default. Backup created.

Usage:
  python3 tools/patch_svg_phase34_html.py            # dry-run
  python3 tools/patch_svg_phase34_html.py --apply
  python3 tools/patch_svg_phase34_html.py --revert --apply
"""

import argparse
import os
import shutil
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase34'

SENTINEL = '/* ── SVG Map Refactor Phase 3+4 (PNG): view toggle + map view ── */'

PHASE2_SENTINEL = '/* ── SVG Map Refactor Phase 2: left sidebar styles ── */'
PHASE2_1_SENTINEL = '// Phase 2.1: also re-size the canvas overlay'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: toggle styling, map-view container, body.view-map mode rules
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
.left-sidebar #cam-dropdown{position:static;display:block;border:none;border-radius:0;max-height:none;margin-top:0;background:transparent}
/* ── end SVG Map Refactor Phase 2 ── */"""

HUNK_1_NEW = """\
.left-sidebar #cam-dropdown{position:static;display:block;border:none;border-radius:0;max-height:none;margin-top:0;background:transparent}
/* ── end SVG Map Refactor Phase 2 ── */

/* ── SVG Map Refactor Phase 3+4 (PNG): view toggle + map view ── */
/* Header view toggle (Camera | Map) */
.view-toggle{display:flex;border:1px solid var(--border);border-radius:5px;overflow:hidden}
.view-toggle button{font-family:var(--mono);font-size:11px;font-weight:700;padding:5px 12px;background:var(--surface2);color:var(--mid);border:none;cursor:pointer;transition:all .12s}
.view-toggle button:hover{color:var(--text)}
.view-toggle button.active{background:var(--green);color:#000}
.view-toggle button + button{border-left:1px solid var(--border)}

/* Map view container — fills the canvas-wrap slot when active. Toggled via
   body.view-map class (set by setView() in JS). Camera-view-only sections
   in the right sidebar are hidden in Map view. */
.map-view{flex:1;position:relative;background:#0a0a0c;overflow:hidden;display:none;cursor:grab}
.map-view.dragging{cursor:grabbing}
body.view-map .canvas-wrap{display:none}
body.view-map .map-view{display:block}
body.view-map .sidebar .sb-sec,
body.view-map .sidebar .opt-bar,
body.view-map .sidebar .opt-result,
body.view-map .sidebar .lm-hdr,
body.view-map .sidebar .lm-list,
body.view-map .sidebar .statusbar{display:none}

/* The map renders as a stacked pair: a <img> for the rasterized yanis at
   the bottom, and an <svg> overlay on top into which Phase 5+ draws camera
   markers and landmark dots. Both share the same wrapper, so a single
   CSS transform pans/zooms them together. The <svg> overlay's coordinate
   system uses the SVG's native viewBox (0 0 svg_size_x svg_size_y), and
   so does the <img> via explicit width/height on it — this means a
   marker drawn at SVG x=12345 lines up perfectly with the same pixel in
   the image, regardless of zoom. */
.map-svg-wrap{position:absolute;left:0;top:0;
  transform-origin:0 0;
  will-change:transform}
.map-svg-wrap > img{display:block;
  filter:grayscale(.4) brightness(.95);
  /* Disable browser drag-image and selection on the bitmap */
  user-select:none;-webkit-user-drag:none;pointer-events:none}
.map-svg-wrap > svg{position:absolute;left:0;top:0;
  /* The overlay is transparent except for Phase 5+ markers */
  pointer-events:none}

.map-loading{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:var(--mono);font-size:12px;color:var(--dim);pointer-events:none}
/* ── end SVG Map Refactor Phase 3+4 (PNG) ── */"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — HTML: add view toggle to header
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
<header>
  <button class="cam-toggle-btn" id="cam-toggle-btn" title="Toggle camera list">≡</button>
  <div class="logo">gtamaplib</div>
<a href="/cam_health.html" class="nav-link">→ Dashboard</a>"""

HUNK_2_NEW = """\
<header>
  <button class="cam-toggle-btn" id="cam-toggle-btn" title="Toggle camera list">≡</button>
  <div class="logo">gtamaplib</div>
<a href="/cam_health.html" class="nav-link">→ Dashboard</a>
  <div class="view-toggle" id="view-toggle">
    <button data-view="camera" class="active" title="Camera view (calibration)">Camera</button>
    <button data-view="map" title="Map view (overview)">Map</button>
  </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — HTML: add .map-view container in .main
# Anchor: the line right before <div class="sidebar"> (the right sidebar).
# We use the unique combination of "sidebar" opening + btn-genmap to anchor.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
  <div class="sidebar">
<button id="btn-genmap" disabled>🗺 Generate Map</button>"""

HUNK_3_NEW = """\
  <div class="map-view" id="map-view">
    <div class="map-svg-wrap" id="map-svg-wrap"></div>
    <div class="map-loading" id="map-loading">Loading yanis map…</div>
  </div>
  <div class="sidebar">
<button id="btn-genmap" disabled>🗺 Generate Map</button>"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 4 — JS: state + view toggle + image load + pan/zoom
# Inserted right after the Phase 2.1 transitionend handler block.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_4_OLD = """\
    leftSidebar.addEventListener('transitionend', e => {
      if (e.propertyName !== 'width') return;
      if (typeof resizeOverlay === 'function') resizeOverlay();
    });
  }"""

HUNK_4_NEW = """\
    leftSidebar.addEventListener('transitionend', e => {
      if (e.propertyName !== 'width') return;
      if (typeof resizeOverlay === 'function') resizeOverlay();
    });
  }

  // ── Phase 3+4 (PNG): view toggle + map view ───────────────────────────
  // Globals exposed on window so Phase 5+ overlays can access them cleanly.
  window.currentView = 'camera';
  window.mapData = null;        // populated on first switch to Map view
  window.mapImg = null;         // the <img> element once loaded
  window.mapOverlay = null;     // empty <svg> overlay where Phase 5+ draws
  window.mapTransform = null;   // {world_offset, y_sign, scale, svg_size}

  // World <-> map-pixel coord helpers, used by Phase 5+ to place markers.
  // The PNG is rendered from the SVG at viewBox 0 0 svg_size, so SVG-user
  // coords and image pixel coords are 1:1 (we set the <img>'s explicit
  // width/height to match svg_size).
  window.worldToSvg = function(wx, wy) {
    const t = window.mapTransform;
    if (!t) return [0, 0];
    return [wx + t.world_offset[0], (t.y_sign * wy) + t.world_offset[1]];
  };
  window.svgToWorld = function(sx, sy) {
    const t = window.mapTransform;
    if (!t) return [0, 0];
    return [sx - t.world_offset[0], (sy - t.world_offset[1]) / t.y_sign];
  };

  const viewToggle = document.getElementById('view-toggle');
  const mapView = document.getElementById('map-view');
  const mapSvgWrap = document.getElementById('map-svg-wrap');
  const mapLoading = document.getElementById('map-loading');

  async function ensureMapLoaded() {
    if (window.mapImg && window.mapData) return;
    mapLoading.style.display = 'flex';
    mapLoading.textContent = 'Loading yanis map…';
    try {
      // Fetch metadata + image in parallel.
      const [dataRes, imgEl] = await Promise.all([
        fetch('/api/map_data').then(r => r.json()),
        new Promise((resolve, reject) => {
          const img = new Image();
          img.onload = () => resolve(img);
          img.onerror = () => reject(new Error('failed to load /yanis.png'));
          img.src = '/yanis.png';
        }),
      ]);
      window.mapData = dataRes;
      window.mapTransform = dataRes.transform;
      const sz = dataRes.transform.svg_size;
      // Pin the image to the SVG's native viewBox dimensions (in CSS pixels)
      // so SVG-user coords == image pixel coords. The wrapper transform then
      // scales both <img> and overlay <svg> together.
      imgEl.setAttribute('width', String(sz[0]));
      imgEl.setAttribute('height', String(sz[1]));
      // Build the empty overlay SVG that Phase 5+ will draw into.
      const overlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      overlay.setAttribute('viewBox', `0 0 ${sz[0]} ${sz[1]}`);
      overlay.setAttribute('width', String(sz[0]));
      overlay.setAttribute('height', String(sz[1]));
      overlay.id = 'map-overlay';
      // Insert: <img> first (bottom layer), <svg> second (top layer).
      mapSvgWrap.innerHTML = '';
      mapSvgWrap.appendChild(imgEl);
      mapSvgWrap.appendChild(overlay);
      window.mapImg = imgEl;
      window.mapOverlay = overlay;
      mapLoading.style.display = 'none';
    } catch (e) {
      console.error('map load failed:', e);
      mapLoading.textContent = 'Failed to load map: ' + (e.message || e);
    }
  }

  function setView(name) {
    if (name !== 'camera' && name !== 'map') return;
    if (window.currentView === name) return;
    window.currentView = name;
    document.body.classList.toggle('view-map', name === 'map');
    viewToggle.querySelectorAll('button[data-view]').forEach(b => {
      b.classList.toggle('active', b.dataset.view === name);
    });
    if (name === 'map') {
      ensureMapLoaded();
    } else {
      // Returning to Camera view: re-fit the overlay since the canvas-wrap
      // size may have been at zero while hidden.
      if (typeof resizeOverlay === 'function') resizeOverlay();
    }
  }
  window.setView = setView;

  viewToggle.addEventListener('click', e => {
    const btn = e.target.closest('button[data-view]');
    if (!btn) return;
    setView(btn.dataset.view);
  });

  // Pan/zoom via CSS transform on the wrapper (GPU-composited, fluid).
  // window.mapTx holds the current transform: { scale, tx, ty }
  // Screen coord = wrapper origin + (svg_x * scale, svg_y * scale) + (tx, ty)
  window.mapTx = null;
  let mapDragging = false, mapDragStart = null, mapTxStart = null;

  function applyMapTx() {
    if (!mapSvgWrap || !window.mapTx) return;
    const { scale, tx, ty } = window.mapTx;
    mapSvgWrap.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
  }

  function resetMapView() {
    if (!window.mapData) return;
    const sz = window.mapData.transform.svg_size;
    const rect = mapView.getBoundingClientRect();
    const scale = Math.min(rect.width / sz[0], rect.height / sz[1]);
    const tx = (rect.width  - sz[0] * scale) / 2;
    const ty = (rect.height - sz[1] * scale) / 2;
    window.mapTx = { scale, tx, ty };
    applyMapTx();
  }
  window.resetMapView = resetMapView;

  mapView.addEventListener('wheel', e => {
    if (window.currentView !== 'map' || !window.mapImg) return;
    e.preventDefault();
    if (!window.mapTx) resetMapView();
    const { scale: s, tx, ty } = window.mapTx;
    const rect = mapView.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.2 : 1 / 1.2;
    const sz = window.mapData.transform.svg_size;
    const minScale = Math.min(rect.width / sz[0], rect.height / sz[1]) * 0.5;
    const maxScale = 50;
    let ns = Math.max(minScale, Math.min(maxScale, s * factor));
    // Adjust translate so the cursor stays over the same map point.
    const ntx = mx - (mx - tx) * (ns / s);
    const nty = my - (my - ty) * (ns / s);
    window.mapTx = { scale: ns, tx: ntx, ty: nty };
    applyMapTx();
  }, { passive: false });

  mapView.addEventListener('mousedown', e => {
    if (window.currentView !== 'map' || !window.mapImg) return;
    if (!window.mapTx) resetMapView();
    mapDragging = true;
    mapDragStart = [e.clientX, e.clientY];
    mapTxStart = { ...window.mapTx };
    mapView.classList.add('dragging');
  });
  window.addEventListener('mousemove', e => {
    if (!mapDragging) return;
    const dx = e.clientX - mapDragStart[0];
    const dy = e.clientY - mapDragStart[1];
    window.mapTx = { scale: mapTxStart.scale, tx: mapTxStart.tx + dx, ty: mapTxStart.ty + dy };
    applyMapTx();
  });
  window.addEventListener('mouseup', () => {
    if (mapDragging) { mapDragging = false; mapView.classList.remove('dragging'); }
  });
  mapView.addEventListener('dblclick', () => { resetMapView(); });

  // Initial fit once both image and metadata are loaded.
  const _vbInit = setInterval(() => {
    if (window.mapImg && !window.mapTx) {
      resetMapView();
      clearInterval(_vbInit);
    }
  }, 100);
  // ── end Phase 3+4 (PNG) ───────────────────────────────────────────────"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 5 — JS: resizeOverlay() no-op when in Map view
# Same as the old Phase 3+4 — without this, switching views triggers
# overlay resize with clientWidth=0 (because canvas-wrap is display:none).
# ─────────────────────────────────────────────────────────────────────────────

HUNK_5_OLD = """\
function resizeOverlay() {
  overlay.width  = canvasWrap.clientWidth;
  overlay.height = canvasWrap.clientHeight;
  draw();
}"""

HUNK_5_NEW = """\
function resizeOverlay() {
  // Phase 3+4: skip if Camera view is hidden — clientWidth/Height would be 0
  // and we'd zero out the overlay, breaking marked-pixel layout on switch back.
  if (window.currentView === 'map') return;
  overlay.width  = canvasWrap.clientWidth;
  overlay.height = canvasWrap.clientHeight;
  draw();
}"""


HUNKS = [
    ('1 (CSS: view toggle + map-view + image+overlay layers)', HUNK_1_OLD, HUNK_1_NEW),
    ('2 (header: view toggle buttons)', HUNK_2_OLD, HUNK_2_NEW),
    ('3 (main: insert .map-view container)', HUNK_3_OLD, HUNK_3_NEW),
    ('4 (JS: state + setView + map load + pan/zoom)', HUNK_4_OLD, HUNK_4_NEW),
    ('5 (JS: resizeOverlay no-op in Map view)', HUNK_5_OLD, HUNK_5_NEW),
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
            print('Re-run with --revert --apply.')
        return

    with open(CALIB_HTML, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print('✓ Already patched.')
        print('  Use --revert --apply to undo.')
        return

    if PHASE2_SENTINEL not in src:
        print('ERROR: Phase 2 sentinel not found.')
        sys.exit(1)
    if PHASE2_1_SENTINEL not in src:
        print('ERROR: Phase 2.1 sentinel not found.')
        sys.exit(1)

    failures = []
    for label, old, new in HUNKS:
        n = src.count(old)
        if n != 1:
            failures.append(f'  hunk {label}: anchor matches {n} times (need exactly 1)')

    if failures:
        print('ERROR: hunk pre-flight failed:')
        print('\n'.join(failures))
        sys.exit(1)

    new_src = src
    for label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    delta = new_src.count('\n') - src.count('\n')
    print(f'Will modify {CALIB_HTML}')
    print(f'  hunks applied: {len(HUNKS)}')
    print(f'  net line delta: {delta:+d}')
    print()
    for label, _, _ in HUNKS:
        print(f'  ✓ hunk {label}')

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
    print('Test:')
    print('  1. Restart server.py (the server endpoint changed too)')
    print('  2. Reload localhost:8765')
    print('  3. [Camera | Map] toggle in header')
    print('  4. Click Map: yanis PNG loads (~500ms), pan/zoom should be 60fps')
    print('  5. Click Camera: returns to calibration view, no glitches')


if __name__ == '__main__':
    main()
