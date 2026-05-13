#!/usr/bin/env python3
"""
patch_svg_phase5.py — render cameras on the Map view

Phase 5 of the SVG Map refactor. Adds three things to calib.html:

1. Camera markers (filled circles) and frustum polygons (semi-transparent
   triangles) drawn into the empty SVG overlay (`window.mapOverlay`)
   that Phase 3+4 set up. Color by camera type:
     - LEAK    → green
     - Trailer → blue
     - other   → purple
2. Hover tooltip showing cam name, type, n_pixels, n_independent.
3. "Show all rays" toggle (next to the view-toggle in the header) — when
   ON and a cam is selected, draws a thin line from that cam's apex to
   each landmark it observes. Useful for diagnosing single-cam coverage.

Click on a cam marker = set it as currentCam. We dispatch the same
'change' event on the hidden #cam-sel select that the rest of the app
uses, so the Camera view follows along automatically when the user
switches back.

Builds on Phase 3+4 (PNG). Pre-flight verifies its sentinel.

Idempotent. Dry-run by default. Backup created.

Usage:
  python3 tools/patch_svg_phase5.py            # dry-run
  python3 tools/patch_svg_phase5.py --apply
  python3 tools/patch_svg_phase5.py --revert --apply
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase5'

SENTINEL = '/* ── SVG Map Refactor Phase 5: cams + frustums on map ── */'
PHASE34_SENTINEL = '/* ── SVG Map Refactor Phase 3+4 (PNG): view toggle + map view ── */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: tooltip styling, marker hover effects, show-all-rays button
# Anchor: end of Phase 3+4 CSS block.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
.map-loading{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:var(--mono);font-size:12px;color:var(--dim);pointer-events:none}
/* ── end SVG Map Refactor Phase 3+4 (PNG) ── */"""

HUNK_1_NEW = """\
.map-loading{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:var(--mono);font-size:12px;color:var(--dim);pointer-events:none}
/* ── end SVG Map Refactor Phase 3+4 (PNG) ── */

/* ── SVG Map Refactor Phase 5: cams + frustums on map ── */
/* Cam markers and frustums in #map-overlay. We attach pointer events to
   the markers so they can be hovered and clicked. The frustum polygons
   stay non-interactive — only the apex circle is clickable. */
#map-overlay{pointer-events:none}
#map-overlay .cam-marker{pointer-events:auto;cursor:pointer;transition:opacity .12s}
#map-overlay .cam-marker:hover circle{stroke-width:80}
#map-overlay .cam-frustum{pointer-events:none;opacity:.35;transition:opacity .15s}
#map-overlay .cam-marker.selected circle{stroke:var(--text);stroke-width:120}
#map-overlay .cam-marker.selected ~ .cam-frustum,
#map-overlay g.cam-group.selected .cam-frustum{opacity:.7}
#map-overlay .ray-line{stroke:var(--blue);stroke-width:30;opacity:.4;pointer-events:none}

/* "Show all rays" toggle in the header, next to the view-toggle */
.rays-toggle{font-family:var(--mono);font-size:11px;font-weight:700;padding:5px 10px;background:var(--surface2);color:var(--mid);border:1px solid var(--border);border-radius:5px;cursor:pointer;display:none}
body.view-map .rays-toggle{display:inline-block}
.rays-toggle.active{background:var(--blue);color:#000;border-color:var(--blue)}
.rays-toggle:hover{color:var(--text)}
.rays-toggle.active:hover{color:#000}

/* Map tooltip — same look as the existing .tip but distinct id so it
   doesn't fight with the Camera view's hover tooltip. */
.map-tip{position:fixed;background:var(--surface2);border:1px solid var(--border);border-radius:5px;padding:6px 10px;font-family:var(--mono);font-size:10px;pointer-events:none;display:none;z-index:101;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,.5)}
.map-tip .tip-name{color:var(--text);font-weight:700;margin-bottom:2px}
.map-tip .tip-meta{color:var(--mid);font-size:9px}
/* ── end SVG Map Refactor Phase 5 ── */"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — HTML: add "Show all rays" toggle button + tooltip element
# Anchor: the view-toggle div we added in Phase 3+4.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
  <div class="view-toggle" id="view-toggle">
    <button data-view="camera" class="active" title="Camera view (calibration)">Camera</button>
    <button data-view="map" title="Map view (overview)">Map</button>
  </div>"""

HUNK_2_NEW = """\
  <div class="view-toggle" id="view-toggle">
    <button data-view="camera" class="active" title="Camera view (calibration)">Camera</button>
    <button data-view="map" title="Map view (overview)">Map</button>
  </div>
  <button class="rays-toggle" id="rays-toggle" title="Show all rays from the selected cam to its landmarks">Rays</button>"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — HTML: add tooltip element. We add it just before the existing
# <div class="tip" id="tip"> so it's adjacent and easy to find.
# Anchor: the existing .tip div (used by Camera view).
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
<div class="tip" id="tip"></div>"""

HUNK_3_NEW = """\
<div class="tip" id="tip"></div>
<div class="map-tip" id="map-tip">
  <div class="tip-name" id="map-tip-name"></div>
  <div class="tip-meta" id="map-tip-meta"></div>
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 4 — JS: insert the rendering + interaction code. We anchor on the
# closing comment of Phase 3+4's JS block.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_4_OLD = """\
  // ── end Phase 3+4 (PNG) ───────────────────────────────────────────────"""

HUNK_4_NEW = """\
  // ── end Phase 3+4 (PNG) ───────────────────────────────────────────────

  // ── Phase 5: cams + frustums on map ───────────────────────────────────
  // Camera type → color. We pull from the same color palette as the rest
  // of the app for consistency (greens for LEAK ground-truth, blue for
  // Trailers, purple for other community sources).
  const CAM_COLORS = {
    'LEAK':      '#4ade80',  // green — ground truth
    'Trailer 1': '#60a5fa',  // blue
    'Trailer 2': '#60a5fa',
    'screenshots': '#a78bfa', // purple
  };

  function getCamTypeForMap(c) {
    // Match the existing getCamType() logic in the cam-picker. We can't
    // call that one directly because it's defined later in the file as a
    // top-level function — order is fine at runtime but we want this code
    // to be self-contained for clarity.
    const src = c.source || '';
    if (/^\\d{4}-\\d{2}-\\d{2}/.test(src)) return 'LEAK';
    if (src.startsWith('Trailer 1')) return 'Trailer 1';
    if (src.startsWith('Trailer 2') || src === 'Trailer 2') return 'Trailer 2';
    if (src.startsWith('Trailer')) return 'Trailer 2';
    return 'screenshots';
  }

  // Frustum geometry: from cam apex (in world coords), the two edge rays
  // open at ±hfov/2 around yaw. In world XY (north-up), yaw=0 points +Y
  // (North) and yaw=90° points +X (East).
  // We extend the rays to a fixed distance D (in world units, ~= 1 GTA-meter
  // per unit on yanis). 1500 units = 1.5 km is enough to be visible at
  // typical map zooms without dominating.
  const FRUSTUM_DIST = 1500;

  function frustumCornersWorld(camXyz, yawDeg, hfovDeg) {
    const [wx, wy] = camXyz;
    const halfFov = hfovDeg / 2;
    const corners = [];
    for (const edgeYawDeg of [yawDeg - halfFov, yawDeg + halfFov]) {
      const r = edgeYawDeg * Math.PI / 180;
      // North-up: yaw 0 → +Y, yaw 90 → +X.
      const ex = wx + FRUSTUM_DIST * Math.sin(r);
      const ey = wy + FRUSTUM_DIST * Math.cos(r);
      corners.push([ex, ey]);
    }
    return corners;
  }

  // The marker circle radius and stroke widths are in SVG-user units, NOT
  // CSS pixels. The wrapper transform scales them with zoom (no fixed-pixel
  // markers — that would require counter-scaling, doable later if wanted).
  // Tuned for visibility at the default fit-zoom on a 12000-px-wide PNG.
  const MARKER_RADIUS = 60;
  const MARKER_STROKE = 30;

  // Selected cam tracking. We listen to the existing #cam-sel change event
  // (the source of truth across the whole app) to update marker styling.
  let mapSelectedCamName = null;

  function renderCamsOnMap() {
    if (!window.mapOverlay || !window.mapData) return;
    // Clear any previous render.
    while (window.mapOverlay.firstChild) {
      window.mapOverlay.removeChild(window.mapOverlay.firstChild);
    }
    const SVG_NS = 'http://www.w3.org/2000/svg';

    // Cams group — append all <g class="cam-group"> children.
    const camsGroup = document.createElementNS(SVG_NS, 'g');
    camsGroup.setAttribute('id', 'cams-layer');
    window.mapOverlay.appendChild(camsGroup);

    // Rays group (Phase 5 toggle) — empty by default, populated by
    // renderRaysForSelectedCam() when the toggle is on.
    const raysGroup = document.createElementNS(SVG_NS, 'g');
    raysGroup.setAttribute('id', 'rays-layer');
    window.mapOverlay.appendChild(raysGroup);

    for (const c of window.mapData.cameras) {
      if (!c.xyz) continue;  // shouldn't happen since /api/map_data filters
      const type = getCamTypeForMap(c);
      const color = CAM_COLORS[type] || '#a78bfa';
      const [sx, sy] = window.worldToSvg(c.xyz[0], c.xyz[1]);

      // Frustum triangle. We need yaw and hfov from the cam record.
      // ypr is [yaw, pitch, roll] in degrees per the existing API.
      const yaw = (c.ypr && c.ypr.length >= 1) ? c.ypr[0] : 0;
      const hfov = c.hfov || 60;
      const fcWorld = frustumCornersWorld(c.xyz, yaw, hfov);
      const fcSvg = fcWorld.map(([wx, wy]) => window.worldToSvg(wx, wy));

      const camGroup = document.createElementNS(SVG_NS, 'g');
      camGroup.setAttribute('class', 'cam-group');
      camGroup.dataset.camName = c.name;

      // Frustum polygon: apex + two edge corners.
      const frustum = document.createElementNS(SVG_NS, 'polygon');
      frustum.setAttribute('class', 'cam-frustum');
      frustum.setAttribute('points',
        `${sx},${sy} ${fcSvg[0][0]},${fcSvg[0][1]} ${fcSvg[1][0]},${fcSvg[1][1]}`);
      frustum.setAttribute('fill', color);
      camGroup.appendChild(frustum);

      // Apex circle (the marker proper).
      const marker = document.createElementNS(SVG_NS, 'g');
      marker.setAttribute('class', 'cam-marker');
      marker.dataset.camName = c.name;
      const circle = document.createElementNS(SVG_NS, 'circle');
      circle.setAttribute('cx', String(sx));
      circle.setAttribute('cy', String(sy));
      circle.setAttribute('r', String(MARKER_RADIUS));
      circle.setAttribute('fill', color);
      circle.setAttribute('stroke', '#000');
      circle.setAttribute('stroke-width', String(MARKER_STROKE));
      marker.appendChild(circle);
      camGroup.appendChild(marker);

      camsGroup.appendChild(camGroup);
    }

    // Apply current selection styling (in case we re-render after a select).
    updateMapSelectionStyle();
  }

  function updateMapSelectionStyle() {
    if (!window.mapOverlay) return;
    window.mapOverlay.querySelectorAll('g.cam-group').forEach(g => {
      g.classList.toggle('selected', g.dataset.camName === mapSelectedCamName);
    });
  }

  // Rays from the selected cam to all its observed landmarks.
  // Toggle-controlled. Rebuilt on every cam change while toggle is on.
  let raysToggleOn = false;

  function renderRaysForSelectedCam() {
    if (!window.mapOverlay) return;
    const raysLayer = document.getElementById('rays-layer');
    if (!raysLayer) return;
    while (raysLayer.firstChild) raysLayer.removeChild(raysLayer.firstChild);
    if (!raysToggleOn || !mapSelectedCamName || !window.mapData) return;

    // Find the selected cam's xyz (apex).
    const cam = window.mapData.cameras.find(c => c.name === mapSelectedCamName);
    if (!cam || !cam.xyz) return;
    const [ax, ay] = window.worldToSvg(cam.xyz[0], cam.xyz[1]);

    // Find the landmarks observed by this cam. We rely on the lm record
    // having a `source_cameras` array OR `observed_by` OR similar field.
    // /api/map_data's landmarks are dumped from gtamapdata; the field
    // listing observers is `source_cameras` (per the data layer).
    const SVG_NS = 'http://www.w3.org/2000/svg';
    let drawn = 0;
    for (const lm of (window.mapData.landmarks || [])) {
      if (!lm.xyz) continue;  // skip untriangulated for ray draw
      const observers = lm.source_cameras || lm.observed_by || [];
      if (!observers.includes(mapSelectedCamName)) continue;
      const [bx, by] = window.worldToSvg(lm.xyz[0], lm.xyz[1]);
      const line = document.createElementNS(SVG_NS, 'line');
      line.setAttribute('x1', String(ax));
      line.setAttribute('y1', String(ay));
      line.setAttribute('x2', String(bx));
      line.setAttribute('y2', String(by));
      line.setAttribute('class', 'ray-line');
      raysLayer.appendChild(line);
      drawn++;
    }
  }

  // Hook the rendering into ensureMapLoaded by re-running it when the map
  // is ready. We call it from setView('map') after ensureMapLoaded resolves.
  // Also expose globally for Phase 6+ to trigger a re-render after data
  // changes (e.g. after triangulating a landmark).
  window.renderCamsOnMap = renderCamsOnMap;
  window.renderRaysForSelectedCam = renderRaysForSelectedCam;

  // Wire in: when the map first loads, render the cams; when the cam
  // selection changes, update styling and rays.
  const _origEnsureMapLoaded = ensureMapLoaded;
  ensureMapLoaded = async function() {
    await _origEnsureMapLoaded.apply(this, arguments);
    if (window.mapData && window.mapOverlay) {
      // Sync selected cam from the global #cam-sel.
      const sel = document.getElementById('cam-sel');
      mapSelectedCamName = sel && sel.value ? sel.value : null;
      renderCamsOnMap();
      renderRaysForSelectedCam();
    }
  };

  // Listen to cam-sel changes to update selection styling on the map.
  document.getElementById('cam-sel').addEventListener('change', () => {
    mapSelectedCamName = document.getElementById('cam-sel').value || null;
    if (window.currentView === 'map') {
      updateMapSelectionStyle();
      renderRaysForSelectedCam();
    }
  });

  // Click on a cam marker = navigate to it (sync with Camera view).
  // Use event delegation on the overlay since markers are dynamic.
  if (window.mapOverlay) {
    // mapOverlay isn't created yet at script-load time (it's created in
    // ensureMapLoaded). We attach listeners on the wrapper instead, which
    // exists from page load.
  }
  mapSvgWrap.addEventListener('click', e => {
    if (window.currentView !== 'map') return;
    // Walk up to find a .cam-marker
    let node = e.target;
    while (node && node !== mapSvgWrap) {
      if (node.classList && node.classList.contains('cam-marker')) {
        const camName = node.dataset.camName;
        if (camName) {
          const sel = document.getElementById('cam-sel');
          if (sel && sel.value !== camName) {
            sel.value = camName;
            sel.dispatchEvent(new Event('change'));
            // Also sync the visible search input so the cam-picker UI
            // reflects the choice.
            const camSearch = document.getElementById('cam-search');
            if (camSearch) camSearch.value = camName;
          }
          // Stop the click from triggering the pan/drag handler.
          e.stopPropagation();
        }
        return;
      }
      node = node.parentNode;
    }
  });

  // Hover tooltip on cam markers.
  const mapTip = document.getElementById('map-tip');
  const mapTipName = document.getElementById('map-tip-name');
  const mapTipMeta = document.getElementById('map-tip-meta');

  mapSvgWrap.addEventListener('mousemove', e => {
    if (window.currentView !== 'map') { mapTip.style.display = 'none'; return; }
    let node = e.target;
    let camName = null;
    while (node && node !== mapSvgWrap) {
      if (node.classList && node.classList.contains('cam-marker')) {
        camName = node.dataset.camName;
        break;
      }
      node = node.parentNode;
    }
    if (!camName) { mapTip.style.display = 'none'; return; }
    const cam = window.mapData?.cameras.find(c => c.name === camName);
    if (!cam) { mapTip.style.display = 'none'; return; }
    mapTipName.textContent = cam.name;
    const type = getCamTypeForMap(cam);
    const bits = [type];
    if (cam.n_pixels != null) bits.push(`${cam.n_pixels}px`);
    if (cam.n_independent != null) bits.push(`${cam.n_independent} indep`);
    if (cam.source) bits.push(cam.source);
    mapTipMeta.textContent = bits.join(' · ');
    mapTip.style.display = 'block';
    mapTip.style.left = (e.clientX + 14) + 'px';
    mapTip.style.top = (e.clientY - 10) + 'px';
  });
  mapSvgWrap.addEventListener('mouseleave', () => { mapTip.style.display = 'none'; });

  // "Show all rays" toggle in the header.
  const raysToggleBtn = document.getElementById('rays-toggle');
  raysToggleBtn.addEventListener('click', () => {
    raysToggleOn = !raysToggleOn;
    raysToggleBtn.classList.toggle('active', raysToggleOn);
    renderRaysForSelectedCam();
  });
  // ── end Phase 5 ───────────────────────────────────────────────────────"""


HUNKS = [
    ('1 (CSS: marker styles + tooltip + rays-toggle)', HUNK_1_OLD, HUNK_1_NEW),
    ('2 (HTML: rays-toggle button in header)', HUNK_2_OLD, HUNK_2_NEW),
    ('3 (HTML: map-tip element)', HUNK_3_OLD, HUNK_3_NEW),
    ('4 (JS: render cams + frustums + tooltip + rays + click)', HUNK_4_OLD, HUNK_4_NEW),
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

    if PHASE34_SENTINEL not in src:
        print('ERROR: Phase 3+4 (PNG) sentinel not found. Apply Phase 3+4 patches first.')
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
    print('  1. Reload localhost:8765 (no server restart needed)')
    print('  2. Switch to Map view')
    print('  3. Cameras appear as colored circles with frustum triangles')
    print('  4. Hover a cam = tooltip with name/type/pixel count')
    print('  5. Click a cam = it becomes currentCam (sync with Camera view)')
    print('  6. "Rays" button in header = toggle rays from selected cam')
    print()
    print('If geometry looks wrong (frustums backwards, north flipped):')
    print('  python3 tools/patch_svg_phase5.py --revert --apply')
    print('  Open an issue and tell me which way they''re wrong.')


if __name__ == '__main__':
    main()
