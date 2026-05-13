#!/usr/bin/env python3
"""
patch_svg_phase6_3_visual_polish.py — fix ray colors + reduce frustum/ray noise

Phase 6.3 polishes the Map view visuals exposed by Phase 6.2:

  1. FIX BUG: Phase 6.2 set per-ray strokes via setAttribute('stroke', color),
     but the Phase 6.2 CSS rule `#map-overlay .ray-line{stroke:#9090b0;…}`
     overrode it. SVG presentation attributes have lower specificity than
     CSS author rules — a well-known SVG gotcha.
     Fix: drop `stroke` from the CSS rule (keep only stroke-width/opacity/
     pointer-events), and ensure renderRaysForSelectedCam() ALWAYS sets a
     stroke inline (using a neutral grey when delta is null).

  2. Frustum fill opacity .18 → .06. The light-purple wash from selected/
     hovered cam frustums was bleeding over half the map and competing
     with the dots for visual attention. .06 keeps the directional cue
     but lets the underlying map breathe.

  3. Frustum line width 12 → 6 (SVG-user units). Same reasoning — at the
     default fit-zoom, 12u was about as thick as the ray bundle, making
     selection/hover state visually heavy.

  4. Rays default opacity .5 → .15. With 30-50 rays superposed in a tight
     bundle, .5 created a uniform purple wash even when each individual
     ray had its delta color. At .15, individual rays read as faint
     guides; the dots become the primary visual element.

  5. Hover boost. When the user hovers a landmark dot, that landmark's
     ray jumps to opacity .85 + stroke-width 14, isolating it visually.
     When the user hovers a cam marker, ALL its rays go to .55 (still
     legible but not overpowering). Hover state is tracked on the
     <g class="rays-layer"> with classes "lm-hover" + "cam-hover", so the
     individual ray we want to highlight is found via [data-lm-name].

Idempotent. Dry-run by default.

Builds on Phase 6.2. Pre-flight verifies its sentinel.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase6_3'

SENTINEL = '// Phase 6.3: visual polish — fix ray colors + reduce noise'
PHASE6_2_SENTINEL = "/* ── SVG Map Refactor Phase 6.2: delta colors + sidebar ── */"


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: fix specificity bug + reduce frustum opacity + thinner rays.
#
# Anchor: the multiple Phase 5 + Phase 6.2 CSS rules we tweak. We touch
# these as a single anchor block because they sit consecutively and we
# want one stable replacement region. Replacing the .ray-line rule alone
# wouldn't fix frustum fill/line — those live in Phase 5 CSS.
#
# We capture from the beginning of the .map-png-wrap rule (just to give
# enough context) through the end of Phase 5 CSS rule for ray-line.
# Then a separate hunk handles the Phase 6.2 ray-line rule.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
#map-overlay .cam-marker{pointer-events:auto;cursor:pointer;transition:opacity .12s}
#map-overlay .cam-marker:hover circle{stroke-width:50}
#map-overlay .cam-frustum,
#map-overlay .cam-frustum-fill{display:none;pointer-events:none}
#map-overlay g.cam-group.selected .cam-frustum,
#map-overlay g.cam-group:hover .cam-frustum{display:block;opacity:1}
#map-overlay g.cam-group.selected .cam-frustum-fill,
#map-overlay g.cam-group:hover .cam-frustum-fill{display:block;opacity:.18}
/* Phase 5.4: no dot change on select. The cam dot keeps its base style;
   only the frustum reveal signals selection. Cleaner, less prominent. */
#map-overlay .ray-line{stroke:var(--blue);stroke-width:20;opacity:.45;pointer-events:none}"""

HUNK_1_NEW = """\
#map-overlay .cam-marker{pointer-events:auto;cursor:pointer;transition:opacity .12s}
#map-overlay .cam-marker:hover circle{stroke-width:50}
#map-overlay .cam-frustum,
#map-overlay .cam-frustum-fill{display:none;pointer-events:none}
#map-overlay g.cam-group.selected .cam-frustum,
#map-overlay g.cam-group:hover .cam-frustum{display:block;opacity:1}
/* Phase 6.3: frustum fill drops from .18 → .06 so the selected/hovered
   triangle no longer washes out the underlying map and dots. */
#map-overlay g.cam-group.selected .cam-frustum-fill,
#map-overlay g.cam-group:hover .cam-frustum-fill{display:block;opacity:.06}
/* Phase 5.4: no dot change on select. The cam dot keeps its base style;
   only the frustum reveal signals selection. Cleaner, less prominent.
   Phase 6.3: ray-line CSS rule no longer sets `stroke` (was overriding
   per-ray inline strokes due to SVG presentation-attr specificity).
   stroke-width also lowered (8 → 4) and opacity (.5 → .15) so the
   ray bundle reads as faint context, not a wall of color. */
#map-overlay .ray-line{stroke-width:4;opacity:.15;pointer-events:none;transition:opacity .1s,stroke-width .1s}
#map-overlay #rays-layer.lm-hover .ray-line{opacity:.08}
#map-overlay #rays-layer.lm-hover .ray-line.lm-hovered{opacity:.85;stroke-width:14}
#map-overlay #rays-layer.cam-hover .ray-line{opacity:.55}"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — CSS: remove the Phase 6.2 ray-line rule (now redundant + wrong).
#
# Phase 6.2 introduced a ray-line CSS rule with `stroke:#9090b0` that's
# the source of the specificity bug. We delete this rule entirely; the
# Phase 5 ray-line rule (which we just fixed in HUNK 1) is now correct.
#
# Anchor: the exact Phase 6.2 ray-line CSS line + its surrounding comment.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
/* Rays in the #rays-layer (Phase 5 toggle) — Phase 6.2 thins them and
   sets stroke per-element via JS to match each landmark's delta color.
   The CSS rule below is the *fallback* (no delta available); per-line
   inline strokes win when set. */
#map-overlay .ray-line{stroke:#9090b0;stroke-width:8;opacity:.5;pointer-events:none}

"""

HUNK_2_NEW = """\
/* Phase 6.3: the duplicate ray-line rule that Phase 6.2 added here has
   been removed — its `stroke:#9090b0` was overriding per-line inline
   strokes due to SVG presentation-attribute specificity (presentation
   attrs sit BELOW author CSS in the cascade). The Phase 5 ray-line CSS
   rule has been updated in-place to no longer set stroke at all; per-ray
   strokes are set inline by renderRaysForSelectedCam() and never lose
   the cascade fight. */

"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — JS: reduce FRUSTUM_LINE_WIDTH from 12 to 6.
#
# Anchor: the constant declaration block in the Phase 5 section.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
  // Phase 5.1: smaller markers, thinner outlines
  const MARKER_RADIUS = 35;
  const MARKER_STROKE = 12;
  const FRUSTUM_LINE_WIDTH = 12;"""

HUNK_3_NEW = """\
  // Phase 5.1: smaller markers, thinner outlines
  // Phase 6.3: FRUSTUM_LINE_WIDTH 12 → 6 (less visual weight on hover/select)
  const MARKER_RADIUS = 35;
  const MARKER_STROKE = 12;
  const FRUSTUM_LINE_WIDTH = 6;"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 4 — JS: rewrite renderRaysForSelectedCam to ALWAYS set inline stroke
# (with grey fallback for null deltas) AND tag each ray with data-lm-name
# so the hover boost can target the specific ray for the hovered landmark.
#
# Anchor: the Phase 6.2 version of renderRaysForSelectedCam.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_4_OLD = """\
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

HUNK_4_NEW = """\
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
    // Phase 6.3: neutral grey fallback color when delta is unavailable.
    // window.deltaColor(null) already returns '#333' (very dark) — that
    // disappears against the dim map. Use the LM_COLOR_NEUTRAL we already
    // defined in 6.1 (#9090b0) for visual consistency with neutral dots.
    const NULL_DELTA_COLOR = '#9090b0';
    for (const lm of observed) {
      if (!lm.xyz) continue;
      const [bx, by] = window.worldToSvg(lm.xyz[0], lm.xyz[1]);
      const line = document.createElementNS(SVG_NS, 'line');
      line.setAttribute('x1', String(ax));
      line.setAttribute('y1', String(ay));
      line.setAttribute('x2', String(bx));
      line.setAttribute('y2', String(by));
      line.setAttribute('class', 'ray-line');
      // Phase 6.3: tag with data-lm-name so the hover boost CSS can
      // target this specific ray when its landmark is hovered.
      line.dataset.lmName = lm.name;
      // Phase 6.2/6.3: per-ray color matches the dot's delta color.
      // ALWAYS set stroke inline — Phase 5's CSS rule no longer sets
      // stroke (Phase 6.3 hunk 1), so inline always wins. Fallback
      // grey for null deltas (delta hasn't loaded, or projection
      // failed, or cam can't see this landmark).
      const delta = window.mapDeltasByLm ? window.mapDeltasByLm.get(lm.name) : undefined;
      const color = (delta != null) ? window.deltaColor(delta) : NULL_DELTA_COLOR;
      line.setAttribute('stroke', color);
      raysLayer.appendChild(line);
    }
  }"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 5 — JS: extend setMapHoveredLm() and add a cam-hover handler so the
# rays-layer gets the right CSS classes for the boost effect.
#
# Anchor: the Phase 6.2 setMapHoveredLm function.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_5_OLD = """\
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
  }"""

HUNK_5_NEW = """\
  // Map dots: hover tooltip + click select via delegation on the wrapper.
  // Phase 6.3: also boost the matching ray via .lm-hovered class on the
  // specific <line>, gated by a .lm-hover class on #rays-layer (so we
  // don't have to selector-target every other ray to dim it).
  function setMapHoveredLm(name) {
    if (mapHoveredLm === name) return;
    if (window.mapOverlay) {
      // Dot
      const prev = window.mapOverlay.querySelector(`.lm-dot.hovered`);
      if (prev) prev.classList.remove('hovered');
      if (name) {
        const cur = window.mapOverlay.querySelector(`.lm-dot[data-lm-name="${CSS.escape(name)}"]`);
        if (cur) cur.classList.add('hovered');
      }
      // Phase 6.3: matching ray boost
      const raysLayer = document.getElementById('rays-layer');
      if (raysLayer) {
        const prevRay = raysLayer.querySelector('.ray-line.lm-hovered');
        if (prevRay) prevRay.classList.remove('lm-hovered');
        if (name) {
          raysLayer.classList.add('lm-hover');
          const ray = raysLayer.querySelector(`.ray-line[data-lm-name="${CSS.escape(name)}"]`);
          if (ray) ray.classList.add('lm-hovered');
        } else {
          raysLayer.classList.remove('lm-hover');
        }
      }
    }
    mapHoveredLm = name;
  }
  // Phase 6.3: cam-hover sets a class on #rays-layer to bump ALL rays
  // for the currently selected cam. Tied to the existing cam-marker
  // hover via :hover in CSS would have been cleanest, but the rays
  // and cams live in different SVG groups so we drive it from JS.
  function setMapCamHovered(isHovered) {
    const raysLayer = document.getElementById('rays-layer');
    if (!raysLayer) return;
    raysLayer.classList.toggle('cam-hover', !!isHovered);
  }
  window.setMapCamHovered = setMapCamHovered;"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 6 — JS: wire the cam-hover boost into the existing mousemove/leave
# handlers on mapSvgWrap. The existing mousemove handler walks up to find
# .cam-marker for the tooltip — we piggyback there.
#
# Anchor: the Phase 5 cam-marker hover tooltip block. We add the boost
# call in two places: when found a cam marker (turn ON), and when not
# (turn OFF). The mouseleave handler also needs to turn it off.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_6_OLD = """\
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
  mapSvgWrap.addEventListener('mouseleave', () => { mapTip.style.display = 'none'; });"""

HUNK_6_NEW = """\
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
    if (!camName) {
      mapTip.style.display = 'none';
      // Phase 6.3: clear cam-hover ray boost if we left the cam marker.
      if (typeof setMapCamHovered === 'function') setMapCamHovered(false);
      return;
    }
    // Phase 6.3: only boost rays for the SELECTED cam (rays are only
    // rendered for the selected cam), so hovering a non-selected cam
    // shouldn't tint other rays.
    if (typeof setMapCamHovered === 'function') {
      setMapCamHovered(camName === mapSelectedCamName);
    }
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
  mapSvgWrap.addEventListener('mouseleave', () => {
    mapTip.style.display = 'none';
    // Phase 6.3: clear ray boost states on leave.
    if (typeof setMapCamHovered === 'function') setMapCamHovered(false);
    if (typeof setMapHoveredLm === 'function') setMapHoveredLm(null);
  });"""


HUNKS = [
    ('CSS — frustum opacity + ray hover boost rules',         HUNK_1_OLD, HUNK_1_NEW),
    ('CSS — remove Phase 6.2 conflicting ray-line rule',      HUNK_2_OLD, HUNK_2_NEW),
    ('JS — FRUSTUM_LINE_WIDTH 12 → 6',                        HUNK_3_OLD, HUNK_3_NEW),
    ('JS — render rays with always-inline stroke + lm-name', HUNK_4_OLD, HUNK_4_NEW),
    ('JS — setMapHoveredLm boosts matching ray + cam helper', HUNK_5_OLD, HUNK_5_NEW),
    ('JS — wire cam-hover ray boost into cam-marker handlers', HUNK_6_OLD, HUNK_6_NEW),
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

    if PHASE6_2_SENTINEL not in src:
        print('ERROR: Phase 6.2 sentinel not found. Apply Phase 6.2 first.')
        sys.exit(1)

    # Pre-flight: every hunk must match exactly once.
    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} times (need exactly 1).')
            sys.exit(1)

    # Embed the sentinel into the new src so future patches can pre-flight on it.
    new_src = src
    for _label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    # Add a sentinel marker so subsequent patches can verify Phase 6.3.
    # We append it as a CSS comment at the end of the Phase 6.2 sidebar
    # CSS block — that block already exists in the file from Phase 6.2.
    SENTINEL_LINE = '/* ── end SVG Map Refactor Phase 6.2 ── */'
    SENTINEL_REPLACE = (
        '/* ── end SVG Map Refactor Phase 6.2 ── */\n'
        f'/* {SENTINEL} */'
    )
    if SENTINEL_LINE in new_src:
        new_src = new_src.replace(SENTINEL_LINE, SENTINEL_REPLACE, 1)

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
    print('Test: hard reload, switch to Map view, click a cam, toggle Rays.')
    print('  - Rays now properly colored by delta (lime, green, yellow, red)')
    print('  - At rest: rays very faint (.15 opacity) — context, not noise')
    print('  - Hover a dot: that landmark\'s ray pops to .85 opacity + thicker')
    print('  - Hover the selected cam marker: all rays bump to .55')
    print('  - Frustum fill is now barely-there (.06 opacity)')
    print('  - Frustum lines are thinner (6 user-units instead of 12)')
    print()
    print('If clean: archive Phase 6 patches together.')
    print('  git add tools/calib.html')
    print('  git commit -m "Phase 6: landmark dots + delta-colored rays + map sidebar"')
    print('  mkdir -p tools/_archive/patches')
    print('  mv tools/patch_svg_phase6_*.py tools/_archive/patches/')
    print('  git add tools/_archive/patches/')
    print('  git commit -m "Archive Phase 6 patches"')


if __name__ == '__main__':
    main()
