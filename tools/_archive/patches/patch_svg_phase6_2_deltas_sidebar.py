#!/usr/bin/env python3
"""
patch_svg_phase6_2_deltas_sidebar.py — delta-colored dots/rays + landmark sidebar

Phase 6.2 finishes Phase 6:
  1. Replaces the (wrong) Phase 6.1 thresholds (3'/10', 3-tier) with the
     SAME 4-tier dColor() the Camera view uses (1'/3'/8'). The Camera
     view's dColor lives in the script body and is the source of truth for
     delta coloring across the app.
  2. Fetches /api/project?cam=<selected> when a cam is selected in map
     view, caches the per-landmark deltas in window.mapDeltasByLm, then
     re-renders dots so observed dots show their actual residual color.
  3. Recolors rays (the existing #rays-layer used by the "Rays" toggle)
     by delta too, using the same dColor(). Also thins them from
     stroke-width:20 → stroke-width:8 with opacity .5 — Phase 6.1
     observation: the bright thick blue rays were too noisy.
  4. Adds a hover tooltip on landmark dots (event delegation on
     #map-svg-wrap, reuses .map-tip styling from Phase 5).
  5. Adds a right-sidebar landmark list, visible only in map view via
     `body.view-map .map-only` CSS gate. Reuses the existing .sidebar
     container (other sb-sec/lm-list/etc. are already hidden in map
     view by Phase 3+4 CSS), so we just add a new .sb-sec.map-only
     section with our list inside. List is sorted by delta desc, fades
     non-observed lms when a cam is selected, click-to-select wires
     into the existing showLmInfo() mechanism.

Architecture decisions:
  - Single source of truth for color thresholds: we define a NEW global
    function window.deltaColor() at the top of the script, and rewrite
    the Camera view's dColor() to delegate to it. This way both views
    share one function — change the thresholds once, both views update.
  - We REMOVE the Phase 6.1 LM_COLOR_GOOD/MID/BAD/lmColorForDelta()
    constants/fn and replace with calls to window.deltaColor(). The
    LM_COLOR_NEUTRAL and LM_COLOR_LEAK constants stay (they're for
    "no cam selected" / "no delta available" states which are NOT
    delta-driven and shouldn't share thresholds).
  - /api/project fetch is debounced to 80ms to coalesce rapid cam
    flicks (e.g. arrow-key navigation through the cam list). The
    response is shape-compatible with what Camera view already uses —
    we just keep the .name → .delta mapping.
  - Sidebar list rendering reuses the existing .lm-item/.lm-dot/.lm-d
    styles from Camera view. The list is built from window.mapData
    landmarks, filtered to those observed by the selected cam (when a
    cam is selected) or to all triangulated lms (otherwise).

Idempotent. Dry-run by default.

Builds on Phase 6.1. Pre-flight verifies its sentinel.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase6_2'

SENTINEL = '// Phase 6.2: delta-colored dots/rays + landmark sidebar'
PHASE6_1_SENTINEL = '// Phase 6.1: landmark dots on map'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: Phase 6.1 lm-dot rules → broaden to also style rays-by-delta
# and add Phase 6.2 sidebar styles. We REPLACE the Phase 6.1 CSS block
# wholesale (the 6.1 styles stay, plus new 6.2 styles right after).
#
# Anchor: the Phase 6.1 closing comment.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
#map-overlay #lm-layer{pointer-events:none}
#map-overlay .lm-dot{transition:opacity .12s}
#map-overlay .lm-dot.untriangulated{fill:none;stroke:#5a5a7a;stroke-width:8}
#map-overlay .lm-dot.dim{opacity:.18}
/* ── end SVG Map Refactor Phase 6.1 ── */"""

HUNK_1_NEW = """\
/* Phase 6.1 lm-layer is interactive in 6.2 — we hover-test dots via
   event delegation on the wrapper, so the layer needs to receive
   pointer events on its children. */
#map-overlay #lm-layer{pointer-events:none}
#map-overlay .lm-dot{transition:opacity .12s;pointer-events:auto;cursor:pointer}
#map-overlay .lm-dot.untriangulated{fill:none;stroke:#5a5a7a;stroke-width:8}
#map-overlay .lm-dot.dim{opacity:.18}
#map-overlay .lm-dot.hovered{stroke:#fff;stroke-width:6}
#map-overlay .lm-dot.selected{stroke:#fff;stroke-width:8}
/* ── end SVG Map Refactor Phase 6.1 ── */

/* ── SVG Map Refactor Phase 6.2: delta colors + sidebar ── */
/* Rays in the #rays-layer (Phase 5 toggle) — Phase 6.2 thins them and
   sets stroke per-element via JS to match each landmark's delta color.
   The CSS rule below is the *fallback* (no delta available); per-line
   inline strokes win when set. */
#map-overlay .ray-line{stroke:#9090b0;stroke-width:8;opacity:.5;pointer-events:none}

/* Map-only sections in the right sidebar — visible ONLY in map view.
   Phase 3+4 already hides .sb-sec/.opt-bar/.lm-hdr/.lm-list/.statusbar
   in map view, so we re-show our map-only ones via this rule. */
body.view-map .sidebar .sb-sec.map-only,
body.view-map .sidebar .lm-hdr.map-only,
body.view-map .sidebar .lm-list.map-only,
body.view-map .sidebar .statusbar.map-only{display:flex}
body.view-map .sidebar .lm-list.map-only{display:block}
body:not(.view-map) .sidebar .sb-sec.map-only,
body:not(.view-map) .sidebar .lm-hdr.map-only,
body:not(.view-map) .sidebar .lm-list.map-only,
body:not(.view-map) .sidebar .statusbar.map-only{display:none}

/* The map sidebar header — slightly different from Camera-view lm-hdr,
   shows the selected cam name + total visible count. */
.map-sb-hdr{padding:9px 13px;border-bottom:1px solid var(--border);font-family:var(--mono);font-size:10px;color:var(--mid)}
.map-sb-hdr .cam-name{color:var(--text);font-weight:700;font-size:11px;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.map-sb-hdr .meta{font-size:9px;color:var(--dim)}
.map-sb-hdr .empty{color:var(--dim);font-style:italic}

/* The list itself reuses .lm-item/.lm-dot/.lm-name/.lm-d from Camera view
   for visual consistency. Add a .map-only modifier so we can target it
   independently if needed. */
.lm-list.map-only{flex:1;overflow-y:auto}
.lm-list.map-only .lm-item.untriangulated .lm-name{color:var(--dim);font-style:italic}
/* ── end SVG Map Refactor Phase 6.2 ── */"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — JS: replace Phase 6.1 LM color constants + lmColorForDelta() with
# a delegation to a NEW window.deltaColor() (defined in HUNK 3 in the
# Camera view's dColor block — single source of truth).
#
# Anchor: the full Phase 6.1 constants block + lmColorForDelta function.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
  // Phase 6.1: landmark dots on map
  // Dot radius in SVG-user units. Smaller than MARKER_RADIUS (35) so cams
  // visually dominate. Tuned for the same default fit-zoom as the cams.
  const LM_DOT_RADIUS = 16;
  // Delta-color thresholds in arcmin, matching the rest of the app
  // (see /api/generate_map and the existing lm-list dColor()).
  const LM_DELTA_GOOD = 3;   // < 3'   → green
  const LM_DELTA_MID  = 10;  // < 10'  → yellow; otherwise red
  // Base palette
  const LM_COLOR_GOOD = '#4ade80';
  const LM_COLOR_MID  = '#f59e0b';
  const LM_COLOR_BAD  = '#f87171';
  const LM_COLOR_LEAK = '#4ade80';   // leak-anchored ground truth (no cam selected)
  const LM_COLOR_NEUTRAL = '#9090b0'; // triangulated, no cam selected, not leak-anchored

  // window.mapDeltasByLm: Map<lm_name, delta_arcmin> for the current
  // mapSelectedCamName. Populated by Phase 6.2 when it fetches /api/project.
  // null when no cam is selected. Phase 6.1 only READS this; Phase 6.2
  // owns the fetch + cache invalidation.
  window.mapDeltasByLm = null;

  function lmColorForDelta(delta) {
    if (delta == null) return null;  // signal "no projection available"
    if (delta < LM_DELTA_GOOD) return LM_COLOR_GOOD;
    if (delta < LM_DELTA_MID)  return LM_COLOR_MID;
    return LM_COLOR_BAD;
  }"""

HUNK_2_NEW = """\
  // Phase 6.1: landmark dots on map
  // Phase 6.2: aligned with Camera view's dColor() — single source of
  // truth is window.deltaColor(), defined later alongside dColor.
  // Dot radius in SVG-user units. Smaller than MARKER_RADIUS (35) so cams
  // visually dominate. Tuned for the same default fit-zoom as the cams.
  const LM_DOT_RADIUS = 16;
  const LM_COLOR_LEAK = '#4ade80';    // leak-anchored ground truth (no cam selected)
  const LM_COLOR_NEUTRAL = '#9090b0'; // triangulated, no cam selected, not leak-anchored

  // window.mapDeltasByLm: Map<lm_name, delta_arcmin> for the current
  // mapSelectedCamName. Populated by Phase 6.2 when it fetches /api/project.
  // null when no cam is selected.
  window.mapDeltasByLm = null;

  // Bridge: Phase 6.2 wants delta colors but the canonical dColor() is
  // defined later in the script (inside the Camera view block). We expose
  // window.deltaColor in a shim here that calls it lazily — by the time
  // any landmark is rendered, the Camera view block has run and
  // window.deltaColor is wired up.
  function lmColorForDelta(delta) {
    return window.deltaColor ? window.deltaColor(delta) : null;
  }"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — JS: rewrite the Camera view's dColor() to delegate to
# window.deltaColor(), and define window.deltaColor() with the existing
# 4-tier thresholds. This makes Camera + Map share one function.
#
# Anchor: the existing dColor function. We keep the same return values
# so Camera view rendering is byte-identical post-patch.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
// ── Landmark list ──────────────────────────────────────────────────────────
function dColor(d) {
  if (d == null) return '#333';
  if (d < 1) return '#4ade80';
  if (d < 3) return '#a3e635';
  if (d < 8) return '#f59e0b';
  return '#f87171';
}"""

HUNK_3_NEW = """\
// ── Landmark list ──────────────────────────────────────────────────────────
// Phase 6.2: dColor delegates to window.deltaColor — the Map view uses
// the same thresholds. Single source of truth for delta coloring.
window.deltaColor = function(d) {
  if (d == null) return '#333';
  if (d < 1) return '#4ade80';
  if (d < 3) return '#a3e635';
  if (d < 8) return '#f59e0b';
  return '#f87171';
};
function dColor(d) { return window.deltaColor(d); }"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 4 — JS: rewrite renderLandmarksOnMap to use window.deltaColor() and
# track which dots match selected/hovered for the new hover/click feature.
#
# Anchor: the existing renderLandmarksOnMap function body.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_4_OLD = """\
  function renderLandmarksOnMap() {
    if (!window.mapOverlay || !window.mapData) return;
    const lmLayer = document.getElementById('lm-layer');
    if (!lmLayer) return;
    // Clear previous dots.
    while (lmLayer.firstChild) lmLayer.removeChild(lmLayer.firstChild);
    const SVG_NS = 'http://www.w3.org/2000/svg';

    // When a cam is selected, the set of landmarks observed by it tells
    // us which dots to fully color vs dim. Use the precomputed index.
    const observedSet = (mapSelectedCamName && window.mapCamLandmarks)
      ? new Set((window.mapCamLandmarks.get(mapSelectedCamName) || []).map(l => l.name))
      : null;

    for (const lm of window.mapData.landmarks) {
      // Untriangulated → hollow outline at expected position. /api/map_data
      // gives null xyz for these, so we have nowhere to place them. Skip
      // entirely (Phase 7 will surface them via the sidebar).
      if (!lm.xyz) continue;

      const [sx, sy] = window.worldToSvg(lm.xyz[0], lm.xyz[1]);
      const dot = document.createElementNS(SVG_NS, 'circle');
      dot.setAttribute('class', 'lm-dot');
      dot.setAttribute('cx', String(sx));
      dot.setAttribute('cy', String(sy));
      dot.setAttribute('r',  String(LM_DOT_RADIUS));
      dot.dataset.lmName = lm.name;

      // Color logic
      let fill = LM_COLOR_NEUTRAL;
      let dim = false;
      if (observedSet) {
        if (observedSet.has(lm.name)) {
          // Cam-observed: color by delta if available.
          const delta = window.mapDeltasByLm
            ? window.mapDeltasByLm.get(lm.name)
            : undefined;
          const deltaColor = lmColorForDelta(delta);
          if (deltaColor) {
            fill = deltaColor;
          } else {
            // delta is null (untriangulatable for this cam) — keep neutral
            // but don't dim, since this cam DOES observe it.
            fill = LM_COLOR_NEUTRAL;
          }
        } else {
          // Not observed by selected cam → dim grey.
          fill = LM_COLOR_NEUTRAL;
          dim = true;
        }
      } else {
        // No cam selected → leak-anchored gets the green tint, others neutral.
        fill = lm.is_leak_anchored ? LM_COLOR_LEAK : LM_COLOR_NEUTRAL;
      }

      dot.setAttribute('fill', fill);
      if (dim) dot.classList.add('dim');
      lmLayer.appendChild(dot);
    }
  }
  window.renderLandmarksOnMap = renderLandmarksOnMap;"""

HUNK_4_NEW = """\
  function renderLandmarksOnMap() {
    if (!window.mapOverlay || !window.mapData) return;
    const lmLayer = document.getElementById('lm-layer');
    if (!lmLayer) return;
    // Clear previous dots.
    while (lmLayer.firstChild) lmLayer.removeChild(lmLayer.firstChild);
    const SVG_NS = 'http://www.w3.org/2000/svg';

    // When a cam is selected, the set of landmarks observed by it tells
    // us which dots to fully color vs dim. Use the precomputed index.
    const observedSet = (mapSelectedCamName && window.mapCamLandmarks)
      ? new Set((window.mapCamLandmarks.get(mapSelectedCamName) || []).map(l => l.name))
      : null;

    for (const lm of window.mapData.landmarks) {
      // Untriangulated → no xyz, can't place on map. Phase 6.2 sidebar
      // surfaces these even without map placement.
      if (!lm.xyz) continue;

      const [sx, sy] = window.worldToSvg(lm.xyz[0], lm.xyz[1]);
      const dot = document.createElementNS(SVG_NS, 'circle');
      dot.setAttribute('class', 'lm-dot');
      dot.setAttribute('cx', String(sx));
      dot.setAttribute('cy', String(sy));
      dot.setAttribute('r',  String(LM_DOT_RADIUS));
      dot.dataset.lmName = lm.name;

      // Color logic
      let fill = LM_COLOR_NEUTRAL;
      let dim = false;
      if (observedSet) {
        if (observedSet.has(lm.name)) {
          // Cam-observed: color by delta if available (Phase 6.2 fetches
          // /api/project on cam change to populate window.mapDeltasByLm).
          const delta = window.mapDeltasByLm
            ? window.mapDeltasByLm.get(lm.name)
            : undefined;
          if (delta != null) {
            fill = window.deltaColor(delta);
          } else {
            // Either deltas not yet fetched OR the projection failed for
            // this lm (e.g. behind cam). Use neutral; not dimmed since
            // this cam DOES observe it.
            fill = LM_COLOR_NEUTRAL;
          }
        } else {
          // Not observed by selected cam → dim grey.
          fill = LM_COLOR_NEUTRAL;
          dim = true;
        }
      } else {
        // No cam selected → leak-anchored gets the green tint, others neutral.
        fill = lm.is_leak_anchored ? LM_COLOR_LEAK : LM_COLOR_NEUTRAL;
      }

      dot.setAttribute('fill', fill);
      if (dim) dot.classList.add('dim');
      // Re-apply hover/select markers if they survived a re-render.
      if (mapHoveredLm === lm.name)  dot.classList.add('hovered');
      if (mapSelectedLm === lm.name) dot.classList.add('selected');
      lmLayer.appendChild(dot);
    }
  }
  window.renderLandmarksOnMap = renderLandmarksOnMap;"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 5 — JS: rewrite renderRaysForSelectedCam so each ray is colored by
# the per-landmark delta, and add inline stroke (overrides the CSS
# fallback). The line CSS already sets stroke-width:8 + opacity:.5 in
# Phase 6.2 hunk 1.
#
# Anchor: the existing renderRaysForSelectedCam function body.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_5_OLD = """\
  function renderRaysForSelectedCam() {
    if (!window.mapOverlay) return;
    const raysLayer = document.getElementById('rays-layer');
    if (!raysLayer) return;
    while (raysLayer.firstChild) raysLayer.removeChild(raysLayer.firstChild);
    if (!raysToggleOn || !mapSelectedCamName || !window.mapData) return;

    const cam = window.mapData.cameras.find(c => c.name === mapSelectedCamName);
    if (!cam || !cam.xyz) return;
    const [ax, ay] = window.worldToSvg(cam.xyz[0], cam.xyz[1]);

    // Phase 5.2 perf: O(K) lookup instead of O(M) scan.
    const observed = window.mapCamLandmarks ? window.mapCamLandmarks.get(mapSelectedCamName) : null;
    if (!observed) return;
    const SVG_NS = 'http://www.w3.org/2000/svg';
    for (const lm of observed) {
      if (!lm.xyz) continue;
      const [bx, by] = window.worldToSvg(lm.xyz[0], lm.xyz[1]);
      const line = document.createElementNS(SVG_NS, 'line');
      line.setAttribute('x1', String(ax));
      line.setAttribute('y1', String(ay));
      line.setAttribute('x2', String(bx));
      line.setAttribute('y2', String(by));
      line.setAttribute('class', 'ray-line');
      raysLayer.appendChild(line);
    }
  }"""

HUNK_5_NEW = """\
  function renderRaysForSelectedCam() {
    if (!window.mapOverlay) return;
    const raysLayer = document.getElementById('rays-layer');
    if (!raysLayer) return;
    while (raysLayer.firstChild) raysLayer.removeChild(raysLayer.firstChild);
    if (!raysToggleOn || !mapSelectedCamName || !window.mapData) return;

    const cam = window.mapData.cameras.find(c => c.name === mapSelectedCamName);
    if (!cam || !cam.xyz) return;
    const [ax, ay] = window.worldToSvg(cam.xyz[0], cam.xyz[1]);

    // Phase 5.2 perf: O(K) lookup instead of O(M) scan.
    const observed = window.mapCamLandmarks ? window.mapCamLandmarks.get(mapSelectedCamName) : null;
    if (!observed) return;
    const SVG_NS = 'http://www.w3.org/2000/svg';
    for (const lm of observed) {
      if (!lm.xyz) continue;
      const [bx, by] = window.worldToSvg(lm.xyz[0], lm.xyz[1]);
      const line = document.createElementNS(SVG_NS, 'line');
      line.setAttribute('x1', String(ax));
      line.setAttribute('y1', String(ay));
      line.setAttribute('x2', String(bx));
      line.setAttribute('y2', String(by));
      line.setAttribute('class', 'ray-line');
      // Phase 6.2: per-ray color matches the dot's delta color.
      const delta = window.mapDeltasByLm ? window.mapDeltasByLm.get(lm.name) : undefined;
      if (delta != null) {
        line.setAttribute('stroke', window.deltaColor(delta));
      }
      raysLayer.appendChild(line);
    }
  }"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 6 — JS: Phase 6.2 fetch + sidebar + hover/click wiring.
#
# Inserted right before the "Click on a cam marker" delegation block, so
# all map-related logic stays grouped. We use the sentinel string here.
#
# Anchor: the existing comment block "Click on a cam marker = navigate to it"
# ─────────────────────────────────────────────────────────────────────────────

HUNK_6_OLD = """\
  // Click on a cam marker = navigate to it (sync with Camera view).
  // Use event delegation on the overlay since markers are dynamic."""

HUNK_6_NEW = """\
  // ── Phase 6.2: delta-colored dots/rays + landmark sidebar ──────────────

  // Hover/select state for landmark dots on the map.
  let mapHoveredLm = null;
  let mapSelectedLm = null;

  // Fetch /api/project for the currently selected cam, populate
  // window.mapDeltasByLm, then re-render dots + rays + sidebar.
  // Debounced to coalesce rapid cam flicks.
  let _deltasFetchTimer = null;
  let _deltasFetchToken = 0;
  async function fetchDeltasForSelectedCam() {
    if (!mapSelectedCamName) {
      window.mapDeltasByLm = null;
      renderLandmarksOnMap();
      renderRaysForSelectedCam();
      renderMapSidebar();
      return;
    }
    const myToken = ++_deltasFetchToken;
    try {
      const url = '/api/project?cam=' + encodeURIComponent(mapSelectedCamName);
      const data = await fetch(url).then(r => r.json());
      // Bail if the user changed cams while we were waiting.
      if (myToken !== _deltasFetchToken) return;
      const m = new Map();
      for (const p of (data.projections || [])) {
        if (p.delta != null) m.set(p.name, p.delta);
      }
      window.mapDeltasByLm = m;
      renderLandmarksOnMap();
      renderRaysForSelectedCam();
      renderMapSidebar();
    } catch (e) {
      console.error('Phase 6.2 delta fetch failed:', e);
    }
  }
  function scheduleDeltasFetch() {
    clearTimeout(_deltasFetchTimer);
    _deltasFetchTimer = setTimeout(fetchDeltasForSelectedCam, 80);
  }
  window.scheduleMapDeltasFetch = scheduleDeltasFetch;

  // Sidebar — populated by renderMapSidebar.
  // Structure:
  //   <div class="map-sb-hdr map-only">…</div>
  //   <div class="lm-list map-only">…</div>
  // Inserted into .sidebar so it shares the right-side container with
  // Camera view content (which is hidden in map view via Phase 3+4 CSS).
  const _mapSidebarHdr = document.createElement('div');
  _mapSidebarHdr.className = 'map-sb-hdr map-only sb-sec';
  _mapSidebarHdr.id = 'map-sb-hdr';
  const _mapSidebarList = document.createElement('div');
  _mapSidebarList.className = 'lm-list map-only';
  _mapSidebarList.id = 'map-lm-list';
  // Insert right after the Generate Map button so the sidebar reads
  // top-to-bottom: genmap btn → map header → map list.
  const _rightSidebar = document.querySelector('.sidebar');
  if (_rightSidebar) {
    const genmapBtn = document.getElementById('btn-genmap');
    if (genmapBtn && genmapBtn.parentNode === _rightSidebar) {
      _rightSidebar.insertBefore(_mapSidebarHdr, genmapBtn.nextSibling);
      _rightSidebar.insertBefore(_mapSidebarList, _mapSidebarHdr.nextSibling);
    } else {
      _rightSidebar.insertBefore(_mapSidebarHdr, _rightSidebar.firstChild);
      _rightSidebar.insertBefore(_mapSidebarList, _mapSidebarHdr.nextSibling);
    }
  }

  function renderMapSidebar() {
    if (!window.mapData) return;
    // Header
    if (!mapSelectedCamName) {
      _mapSidebarHdr.innerHTML = '<div class="empty">No camera selected</div>'
        + '<div class="meta" style="margin-top:4px">Click a cam on the map to see its landmarks</div>';
      _mapSidebarList.innerHTML = '';
      return;
    }

    const observed = (window.mapCamLandmarks && window.mapCamLandmarks.get(mapSelectedCamName)) || [];
    // Sort by delta desc (worst first), nulls/missing at the bottom.
    const decorated = observed.map(lm => {
      const delta = window.mapDeltasByLm ? window.mapDeltasByLm.get(lm.name) : undefined;
      return { lm, delta: (delta == null) ? null : delta };
    });
    decorated.sort((a, b) => {
      if (a.delta == null && b.delta == null) return a.lm.name.localeCompare(b.lm.name);
      if (a.delta == null) return 1;
      if (b.delta == null) return -1;
      return b.delta - a.delta;
    });

    // Counts
    const n = decorated.length;
    const nWith = decorated.filter(d => d.delta != null).length;
    const fetching = window.mapDeltasByLm == null;
    const meta = fetching
      ? `${n} observed · loading deltas…`
      : `${n} observed · ${nWith} with delta`;
    _mapSidebarHdr.innerHTML =
      `<div class="cam-name">${escapeHtml(mapSelectedCamName)}</div>` +
      `<div class="meta">${meta}</div>`;

    // List
    if (n === 0) {
      _mapSidebarList.innerHTML = '<div style="padding:10px 13px;font-family:var(--mono);font-size:10px;color:var(--dim)">No observed landmarks</div>';
      return;
    }
    const html = decorated.map(({ lm, delta }) => {
      const color = window.deltaColor(delta);
      const deltaStr = delta != null ? delta.toFixed(2) : '—';
      const cls = 'lm-item' + (mapSelectedLm === lm.name ? ' sel' : '')
                            + (!lm.xyz ? ' untriangulated' : '');
      const safeName = escapeHtml(lm.name);
      return `<div class="${cls}" data-lm-name="${safeName}">
        <div class="lm-dot" style="background:${color}"></div>
        <span class="lm-name">${safeName}</span>
        <span class="lm-d" style="color:${color}">${deltaStr}</span>
      </div>`;
    }).join('');
    _mapSidebarList.innerHTML = html;
  }
  window.renderMapSidebar = renderMapSidebar;

  // Tiny html escape — we already use escapeHtml in cam_health but it's
  // not in calib.html scope. Define a small one here.
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => (
      { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]
    ));
  }

  // Sidebar: hover/click delegation
  _mapSidebarList.addEventListener('mouseover', e => {
    const item = e.target.closest('.lm-item[data-lm-name]');
    if (!item) return;
    setMapHoveredLm(item.dataset.lmName);
  });
  _mapSidebarList.addEventListener('mouseleave', () => {
    setMapHoveredLm(null);
  });
  _mapSidebarList.addEventListener('click', e => {
    const item = e.target.closest('.lm-item[data-lm-name]');
    if (!item) return;
    const name = item.dataset.lmName;
    setMapSelectedLm(mapSelectedLm === name ? null : name);
  });

  // Map dots: hover tooltip + click select via delegation on the wrapper.
  function setMapHoveredLm(name) {
    if (mapHoveredLm === name) return;
    if (window.mapOverlay) {
      const prev = window.mapOverlay.querySelector(`.lm-dot.hovered`);
      if (prev) prev.classList.remove('hovered');
      if (name) {
        const cur = window.mapOverlay.querySelector(`.lm-dot[data-lm-name="${CSS.escape(name)}"]`);
        if (cur) cur.classList.add('hovered');
      }
    }
    mapHoveredLm = name;
  }
  function setMapSelectedLm(name) {
    if (window.mapOverlay) {
      const prev = window.mapOverlay.querySelector(`.lm-dot.selected`);
      if (prev) prev.classList.remove('selected');
      if (name) {
        const cur = window.mapOverlay.querySelector(`.lm-dot[data-lm-name="${CSS.escape(name)}"]`);
        if (cur) cur.classList.add('selected');
      }
    }
    mapSelectedLm = name;
    // Re-render sidebar so the .sel class lands on the right item.
    renderMapSidebar();
    // Sync with Camera view's lm-info-panel so picking on the map opens
    // the same landmark info as picking from the Camera-view list.
    if (typeof showLmInfo === 'function') showLmInfo(name);
  }

  // Hover tooltip on dots — reuses .map-tip from Phase 5 to stay
  // visually consistent with cam-marker tooltips.
  mapSvgWrap.addEventListener('mousemove', e => {
    if (window.currentView !== 'map') return;
    // Only react to landmark dots (cam markers have their own tooltip
    // logic earlier in the file that's wired to the same wrapper).
    let node = e.target;
    let dotEl = null;
    while (node && node !== mapSvgWrap) {
      if (node.classList && node.classList.contains('lm-dot')) {
        dotEl = node;
        break;
      }
      node = node.parentNode;
    }
    if (!dotEl) {
      // Don't fight cam-marker tooltips — those clear .map-tip elsewhere.
      // We only set when we actually hovered a dot.
      if (mapHoveredLm) setMapHoveredLm(null);
      return;
    }
    const name = dotEl.dataset.lmName;
    setMapHoveredLm(name);
    const delta = window.mapDeltasByLm ? window.mapDeltasByLm.get(name) : undefined;
    const lm = window.mapData.landmarks.find(l => l.name === name);
    mapTipName.textContent = name;
    const bits = [];
    if (delta != null) {
      bits.push(`Δ ${delta.toFixed(2)}'`);
    } else if (mapSelectedCamName) {
      bits.push('not observed');
    }
    if (lm && lm.is_leak_anchored) bits.push('★ leak-anchored');
    if (lm && lm.error_m != null) bits.push(`err ${lm.error_m.toFixed(1)}m`);
    mapTipMeta.textContent = bits.join(' · ');
    mapTip.style.display = 'block';
    mapTip.style.left = (e.clientX + 14) + 'px';
    mapTip.style.top = (e.clientY - 10) + 'px';
  });

  // Click on a dot → select it (also handled by the cam-marker click
  // delegation which stop-propagates, so a click on a dot that's behind
  // a cam still goes to the cam — desirable since cams are smaller and
  // intentional clicks).
  mapSvgWrap.addEventListener('click', e => {
    if (window.currentView !== 'map') return;
    let node = e.target;
    while (node && node !== mapSvgWrap) {
      if (node.classList && node.classList.contains('lm-dot')) {
        const name = node.dataset.lmName;
        if (name) {
          setMapSelectedLm(mapSelectedLm === name ? null : name);
          e.stopPropagation();
        }
        return;
      }
      node = node.parentNode;
    }
  });

  // Trigger a deltas fetch on every cam change (debounced inside).
  // Phase 6.1 already wired the cam-sel listener to call
  // renderLandmarksOnMap(); we extend it via a separate listener so the
  // fetch runs in parallel with the Phase 6.1 dim re-render.
  document.getElementById('cam-sel').addEventListener('change', () => {
    if (window.currentView === 'map') {
      mapSelectedLm = null;  // clear lm selection on cam change
      scheduleDeltasFetch();
      // renderMapSidebar() runs immediately to show "loading deltas…"
      renderMapSidebar();
    }
  });

  // Also kick the sidebar render when the map first loads + initial fetch
  // if a cam was already selected (e.g. via ?cam= URL param).
  const _origEnsureMapLoadedForPhase62 = ensureMapLoaded;
  ensureMapLoaded = async function() {
    await _origEnsureMapLoadedForPhase62.apply(this, arguments);
    renderMapSidebar();
    if (mapSelectedCamName) scheduleDeltasFetch();
  };

  // ── end Phase 6.2 ──────────────────────────────────────────────────────

  // Click on a cam marker = navigate to it (sync with Camera view).
  // Use event delegation on the overlay since markers are dynamic."""


HUNKS = [
    ('CSS — dot interactivity + sidebar styles + thin rays', HUNK_1_OLD, HUNK_1_NEW),
    ('JS — replace Phase 6.1 color constants with delegation', HUNK_2_OLD, HUNK_2_NEW),
    ('JS — dColor → window.deltaColor (single source of truth)', HUNK_3_OLD, HUNK_3_NEW),
    ('JS — renderLandmarksOnMap uses deltaColor + hover/sel state', HUNK_4_OLD, HUNK_4_NEW),
    ('JS — color rays per delta',                             HUNK_5_OLD, HUNK_5_NEW),
    ('JS — fetch deltas + sidebar + hover tooltip + dot click', HUNK_6_OLD, HUNK_6_NEW),
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

    if PHASE6_1_SENTINEL not in src:
        print('ERROR: Phase 6.1 sentinel not found. Apply Phase 6.1 first.')
        sys.exit(1)

    # Pre-flight: every hunk must match exactly once.
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
    print('Test: hard reload, switch to Map view.')
    print('  - Without cam selected: dots in neutral grey, leak-anchored green')
    print('  - Click a cam: observed dots recolor by delta (1\'/3\'/8\' thresholds)')
    print('    matching Camera view exactly. Non-observed go dim.')
    print('  - Right sidebar shows ranked list of observed landmarks (worst first)')
    print('  - Hover a dot: tooltip shows name + delta arcmin')
    print('  - Hover/click sidebar items: dot highlights, lm-info-panel opens')
    print('  - Toggle Rays: rays now thin (8) + colored per delta, not bright blue')
    print()
    print('If clean: commit, archive both Phase 6 patches:')
    print('  git add tools/calib.html')
    print('  git commit -m "Phase 6: landmark dots colored by delta + map sidebar"')
    print('  mkdir -p tools/_archive/patches')
    print('  mv tools/patch_svg_phase6_*.py tools/_archive/patches/')
    print('  git add tools/_archive/patches/')
    print('  git commit -m "Archive Phase 6 patches"')


if __name__ == '__main__':
    main()
