#!/usr/bin/env python3
"""
patch_svg_phase6_1_dots.py — landmark dots on map view

Phase 6.1 adds a landmarks layer to the SVG map overlay:
  - One small dot per landmark with xyz, placed via window.worldToSvg().
  - Untriangulated landmarks (xyz == null) are drawn as hollow grey
    outlines so they remain visible context but are visually de-emphasized.
  - When no cam is selected, dots are colored by their "is_leak_anchored"
    status (green for leak-anchored ground truth, neutral mid grey
    otherwise).
  - When a cam IS selected, every dot observed by that cam (i.e. the cam
    has a pixel for that landmark) is recolored by its angular residual
    delta, fetched from /api/project:
      delta < 3'   → green
      delta < 10'  → yellow
      delta >= 10' → red
      delta == null (landmark has_xyz=false, can't project) → grey outline
    Non-observed landmarks become very dim grey so the selected cam's
    coverage stands out.

Architecture decisions:
  - We add a NEW SVG group #lm-layer INSIDE window.mapOverlay, inserted
    BEFORE the existing #cams-layer so that cam markers/frustums stay on
    top (cams are the primary interaction target, dots are reference).
    renderCamsOnMap() clears window.mapOverlay before each render, so we
    hook into renderCamsOnMap by patching it to also create + populate
    #lm-layer between #rays-layer and #cams-layer.
  - Per-cam delta data is NOT in /api/map_data (that endpoint only knows
    about the landmark.xyz, not per-cam projection residuals). On cam
    select in map view, we fetch /api/project?cam=<name> and cache the
    result in window.mapDeltasByLm = Map<lm_name, delta>. The fetch is
    skipped if the user is just hovering — we only fetch on actual cam
    change.
  - Dot styling is done via SVG <circle> elements with a "fill" attribute
    set inline (we already have ~600 cam nodes; landmark count adds
    another ~1500-2500). To keep node count manageable, dots have NO
    interactive listeners attached — hover tooltips will be added in
    Phase 6.2 via event delegation on #map-svg-wrap.

Idempotent. Dry-run by default.

Builds on Phase 5.5. Pre-flight verifies its sentinel.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase6_1'

SENTINEL = '// Phase 6.1: landmark dots on map'
PHASE5_5_SENTINEL = '// Phase 5.5: detach map-view DOM when in Camera view'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: landmark dot styles
#
# Anchor: end of Phase 5 CSS section. We append a new "Phase 6.1" CSS block
# right after the closing `/* ── end SVG Map Refactor Phase 5 ── */` comment.
# The map-tip CSS rule comes immediately before that comment, so we anchor
# on a unique, stable string: the exact end-of-section comment line.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
.map-tip .tip-meta{color:var(--mid);font-size:9px}
/* ── end SVG Map Refactor Phase 5 ── */"""

HUNK_1_NEW = """\
.map-tip .tip-meta{color:var(--mid);font-size:9px}
/* ── end SVG Map Refactor Phase 5 ── */

/* ── SVG Map Refactor Phase 6.1: landmark dots on map ── */
/* Landmark dots are drawn as <circle class="lm-dot"> nodes inside
   #lm-layer. Sizing is in SVG-user units (matches the cam-marker
   convention). Untriangulated landmarks get a hollow outline. Per-cam
   delta-driven coloring is applied via inline `fill`/`stroke` attrs in
   JS; the rules below provide the *base* style and the dim/leak states.
   We deliberately do NOT add hover styles here — Phase 6.2 will do hover
   via event delegation, not :hover, to keep node count low. */
#map-overlay #lm-layer{pointer-events:none}
#map-overlay .lm-dot{transition:opacity .12s}
#map-overlay .lm-dot.untriangulated{fill:none;stroke:#5a5a7a;stroke-width:8}
#map-overlay .lm-dot.dim{opacity:.18}
/* ── end SVG Map Refactor Phase 6.1 ── */"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — JS: extend renderCamsOnMap to also build the #lm-layer.
#
# Anchor: the existing block that creates #cams-layer + #rays-layer at the
# top of renderCamsOnMap. We insert the lm-layer creation BEFORE cams-layer
# so it ends up below cams visually (SVG paint order = document order).
#
# We also need:
#   - new constants for dot radius + color thresholds
#   - a renderLandmarksOnMap() function that does the actual rendering,
#     reading window.mapDeltasByLm if present
#   - exposing renderLandmarksOnMap globally for Phase 6.2 to call after
#     a delta refresh
#
# To keep the diff small we put the new function + constants right BEFORE
# renderCamsOnMap, then add a call to it inside renderCamsOnMap.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
  // Selected cam tracking. We listen to the existing #cam-sel change event
  // (the source of truth across the whole app) to update marker styling.
  let mapSelectedCamName = null;

  function renderCamsOnMap() {
    if (!window.mapOverlay || !window.mapData) return;
    // Phase 5.2 perf: build indexes once on first render.
    buildMapIndexes();
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
    window.mapOverlay.appendChild(raysGroup);"""

HUNK_2_NEW = """\
  // Selected cam tracking. We listen to the existing #cam-sel change event
  // (the source of truth across the whole app) to update marker styling.
  let mapSelectedCamName = null;

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
  }

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
  window.renderLandmarksOnMap = renderLandmarksOnMap;

  function renderCamsOnMap() {
    if (!window.mapOverlay || !window.mapData) return;
    // Phase 5.2 perf: build indexes once on first render.
    buildMapIndexes();
    // Clear any previous render.
    while (window.mapOverlay.firstChild) {
      window.mapOverlay.removeChild(window.mapOverlay.firstChild);
    }
    const SVG_NS = 'http://www.w3.org/2000/svg';

    // Phase 6.1: landmark dots layer — created FIRST so it sits below
    // cams + rays in document order (and thus in paint order). Populated
    // by renderLandmarksOnMap() which is called at the end of this fn.
    const lmGroup = document.createElementNS(SVG_NS, 'g');
    lmGroup.setAttribute('id', 'lm-layer');
    window.mapOverlay.appendChild(lmGroup);

    // Cams group — append all <g class="cam-group"> children.
    const camsGroup = document.createElementNS(SVG_NS, 'g');
    camsGroup.setAttribute('id', 'cams-layer');
    window.mapOverlay.appendChild(camsGroup);

    // Rays group (Phase 5 toggle) — empty by default, populated by
    // renderRaysForSelectedCam() when the toggle is on.
    const raysGroup = document.createElementNS(SVG_NS, 'g');
    raysGroup.setAttribute('id', 'rays-layer');
    window.mapOverlay.appendChild(raysGroup);"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — JS: call renderLandmarksOnMap() at the END of renderCamsOnMap.
#
# Anchor: the existing closing block that calls updateMapSelectionStyle().
# We add the lm render call just before it, so dot styling exists before
# any selection-driven re-style runs. The lm dots themselves don't have
# selection styling in 6.1 (that's hover/click in 6.2), but ordering is
# still consistent with the pattern.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
      camsGroup.appendChild(camGroup);
    }

    // Apply current selection styling (in case we re-render after a select).
    updateMapSelectionStyle();
  }"""

HUNK_3_NEW = """\
      camsGroup.appendChild(camGroup);
    }

    // Phase 6.1: render landmark dots. Done after cams so any future
    // shared state (e.g. dim-on-cam-hover) flows in the right direction.
    renderLandmarksOnMap();

    // Apply current selection styling (in case we re-render after a select).
    updateMapSelectionStyle();
  }"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 4 — JS: re-render landmarks on cam-sel change in map view.
#
# Anchor: the existing cam-sel change handler that calls
# updateMapSelectionStyle() + renderRaysForSelectedCam(). We add a call to
# renderLandmarksOnMap() so the dots recolor when the selected cam changes.
# Note: window.mapDeltasByLm stays null in Phase 6.1 — the dots will only
# show "observed vs not observed" coloring (full color vs dim grey).
# Phase 6.2 will populate mapDeltasByLm via /api/project + trigger another
# render when deltas arrive.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_4_OLD = """\
  // Listen to cam-sel changes to update selection styling on the map.
  document.getElementById('cam-sel').addEventListener('change', () => {
    mapSelectedCamName = document.getElementById('cam-sel').value || null;
    if (window.currentView === 'map') {
      updateMapSelectionStyle();
      renderRaysForSelectedCam();
    }
  });"""

HUNK_4_NEW = """\
  // Listen to cam-sel changes to update selection styling on the map.
  document.getElementById('cam-sel').addEventListener('change', () => {
    mapSelectedCamName = document.getElementById('cam-sel').value || null;
    if (window.currentView === 'map') {
      updateMapSelectionStyle();
      renderRaysForSelectedCam();
      // Phase 6.1: invalidate per-cam delta cache and re-render dots in
      // their new "observed vs dim" coloring. Phase 6.2 will async-fetch
      // /api/project and call renderLandmarksOnMap() again with deltas.
      window.mapDeltasByLm = null;
      renderLandmarksOnMap();
    }
  });"""


HUNKS = [
    ('CSS — landmark dot styles',          HUNK_1_OLD, HUNK_1_NEW),
    ('JS — renderLandmarksOnMap + lm-layer', HUNK_2_OLD, HUNK_2_NEW),
    ('JS — call render in renderCamsOnMap', HUNK_3_OLD, HUNK_3_NEW),
    ('JS — re-render dots on cam change',   HUNK_4_OLD, HUNK_4_NEW),
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

    if PHASE5_5_SENTINEL not in src:
        print('ERROR: Phase 5.5 sentinel not found. Apply Phase 5.5 first.')
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
    print('  - Landmark dots should appear under the cam markers')
    print('  - Leak-anchored landmarks (Prison-DD, etc.) tinted green')
    print('  - Other triangulated landmarks neutral grey')
    print('  - Select a cam: its observed dots stay neutral, others dim')
    print('  - (Delta-colored dots come in Phase 6.2)')
    print()
    print('Next: patch_svg_phase6_2_sidebar.py — fetch /api/project for')
    print('  delta-based coloring + add the right-sidebar landmark list.')


if __name__ == '__main__':
    main()
