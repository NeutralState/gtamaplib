#!/usr/bin/env python3
"""
patch_svg_phase5_4_layers_and_dot.py — final Phase 5 cleanup

Two changes in one patch:

1. SEPARATE GPU LAYERS for the PNG and the SVG overlay.
   Currently both live inside the same .map-svg-wrap. When a CSS class
   toggles on a node inside the overlay (selecting a cam), the browser
   invalidates the entire wrapper's compositing layer, which forces a
   re-upload of the 12000x12000 PNG bitmap to the GPU. Cam switches
   measured at 133ms (42ms JS + ~90ms reflow/paint) — most of that is
   the bitmap re-rasterization.
   Fix: put the <img> and the <svg> overlay in two SIBLING wrappers,
   each with its own CSS transform (kept in sync via applyMapTx).
   Each gets its own GPU layer; toggling a class on the overlay doesn't
   force the PNG layer to re-rasterize. Expected drop: 133ms -> ~25ms.

2. REMOVE THE VISUAL CHANGE on the cam dot when selected.
   Phase 5.3 added a thicker stroke + lighter fill, which produced a
   too-prominent pale circle. The user prefers no visual change on the
   dot — the frustum appearing already signals selection clearly.

Builds on Phase 5.3. Pre-flight verifies its sentinel.
Idempotent. Dry-run by default.

Usage:
  python3 tools/patch_svg_phase5_4_layers_and_dot.py            # dry-run
  python3 tools/patch_svg_phase5_4_layers_and_dot.py --apply
  python3 tools/patch_svg_phase5_4_layers_and_dot.py --revert --apply
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase5_4'

SENTINEL = '/* Phase 5.4: separate GPU layers + clean dot styling'
PHASE5_3_SENTINEL = '/* Phase 5.3 perf: hide frustums for non-selected cams */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: replace the Phase 5.3 block. New rules:
#   - The PNG wrapper and the overlay wrapper each get their own GPU layer
#     via translateZ(0) + will-change. Both sized 0 with overflow visible
#     so child elements bleed out — only the transform matters.
#   - Remove the .selected stroke change on the cam dot.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
/* Phase 5.3 perf: hide frustums for non-selected cams */
/* Apex dots stay visible for all cams. FOV edges + fill render only for
   the selected cam OR the cam currently being hovered. This drops the
   SVG overlay node count from ~600 to ~150 and makes pan/zoom fluid. */
#map-overlay{pointer-events:none}
#map-overlay .cam-marker{pointer-events:auto;cursor:pointer;transition:opacity .12s}
#map-overlay .cam-marker:hover circle{stroke-width:50}
/* Frustum hidden by default. */
#map-overlay .cam-frustum,
#map-overlay .cam-frustum-fill{display:none;pointer-events:none}
/* Show frustum when the cam-group is selected or hovered. */
#map-overlay g.cam-group.selected .cam-frustum,
#map-overlay g.cam-group:hover .cam-frustum{display:block;opacity:1}
#map-overlay g.cam-group.selected .cam-frustum-fill,
#map-overlay g.cam-group:hover .cam-frustum-fill{display:block;opacity:.18}
/* Selected cam stroke — .selected lives on .cam-group (Phase 5.1's
   .cam-marker.selected selector never matched, this fixes that). */
#map-overlay g.cam-group.selected .cam-marker circle{stroke:var(--text);stroke-width:70}
#map-overlay .ray-line{stroke:var(--blue);stroke-width:20;opacity:.45;pointer-events:none}"""

HUNK_1_NEW = """\
/* Phase 5.4: separate GPU layers + clean dot styling
   The bitmap (PNG) and the SVG overlay live in two sibling wrappers,
   each forced into its own GPU compositing layer. Without this, any
   class toggle on an overlay node invalidated the whole layer and
   forced a 12K×12K bitmap re-upload (~90ms cost per cam switch). */
.map-png-wrap,.map-overlay-wrap{position:absolute;left:0;top:0;
  transform-origin:0 0;
  will-change:transform;
  /* Force own compositing layer so they don't share invalidation. */
  transform:translateZ(0)}
.map-png-wrap > img{display:block;
  filter:grayscale(1) brightness(1.05) contrast(1.1);
  user-select:none;-webkit-user-drag:none;pointer-events:none}
.map-overlay-wrap > svg{display:block;pointer-events:none}

/* Overlay interaction (same as Phase 5.3 but no .selected dot styling). */
#map-overlay{pointer-events:none}
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


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — CSS: remove the old single .map-svg-wrap rule (rendered by
# Phase 3+4) since we now have two separate wrappers. We keep the
# class .map-svg-wrap as a no-op (in case any code references it).
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
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
/* Phase 3+4 BW: full grayscale */
.map-svg-wrap > img{display:block;
  filter:grayscale(1) brightness(1.05) contrast(1.1);
  /* Disable browser drag-image and selection on the bitmap */
  user-select:none;-webkit-user-drag:none;pointer-events:none}
.map-svg-wrap > svg{position:absolute;left:0;top:0;
  /* The overlay is transparent except for Phase 5+ markers */
  pointer-events:none}"""

HUNK_2_NEW = """\
/* Phase 5.4: .map-svg-wrap kept as a positioning container only.
   The PNG and SVG overlay are now siblings in their OWN wrappers
   (.map-png-wrap and .map-overlay-wrap) — see the dedicated CSS rules
   later in this file. The original Phase 3+4 single-wrapper approach
   forced the bitmap to re-rasterize on every overlay class toggle. */
.map-svg-wrap{position:absolute;inset:0}"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — JS: ensureMapLoaded restructure. Build two siblings instead of
# stacking img+svg in the same wrapper. Update applyMapTx to set the
# transform on BOTH wrappers in sync.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
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
      window.mapOverlay = overlay;"""

HUNK_3_NEW = """\
      // Phase 5.4: separate the bitmap and overlay into sibling wrappers.
      // Each gets its own GPU layer (via CSS translateZ(0) + will-change),
      // so toggling a class on a node inside the overlay no longer
      // invalidates the bitmap layer.
      imgEl.setAttribute('width', String(sz[0]));
      imgEl.setAttribute('height', String(sz[1]));
      const overlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      overlay.setAttribute('viewBox', `0 0 ${sz[0]} ${sz[1]}`);
      overlay.setAttribute('width', String(sz[0]));
      overlay.setAttribute('height', String(sz[1]));
      overlay.id = 'map-overlay';

      // Build two sibling wrappers, side by side, both at (0,0).
      mapSvgWrap.innerHTML = '';
      const pngWrap = document.createElement('div');
      pngWrap.className = 'map-png-wrap';
      pngWrap.id = 'map-png-wrap';
      pngWrap.appendChild(imgEl);
      const overlayWrap = document.createElement('div');
      overlayWrap.className = 'map-overlay-wrap';
      overlayWrap.id = 'map-overlay-wrap';
      overlayWrap.appendChild(overlay);
      mapSvgWrap.appendChild(pngWrap);
      mapSvgWrap.appendChild(overlayWrap);

      window.mapImg = imgEl;
      window.mapOverlay = overlay;
      window.mapPngWrap = pngWrap;
      window.mapOverlayWrap = overlayWrap;"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 4 — JS: applyMapTx now applies the transform to BOTH wrappers.
# We keep the same mapTx state. The single mapSvgWrap.style.transform
# call is replaced with two calls (one per child wrapper).
# ─────────────────────────────────────────────────────────────────────────────

HUNK_4_OLD = """\
  function applyMapTx() {
    if (!mapSvgWrap || !window.mapTx) return;
    const { scale, tx, ty } = window.mapTx;
    mapSvgWrap.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
  }"""

HUNK_4_NEW = """\
  function applyMapTx() {
    if (!window.mapTx) return;
    const { scale, tx, ty } = window.mapTx;
    const t = `translate(${tx}px, ${ty}px) scale(${scale})`;
    // Phase 5.4: set transform on each layer wrapper independently. Each
    // is its own GPU compositing layer (see CSS), so they stay in sync
    // visually but never invalidate each other on overlay class toggles.
    if (window.mapPngWrap)     window.mapPngWrap.style.transform = t;
    if (window.mapOverlayWrap) window.mapOverlayWrap.style.transform = t;
  }"""


HUNKS = [
    ('1 (CSS: layer wrappers + remove dot styling)', HUNK_1_OLD, HUNK_1_NEW),
    ('2 (CSS: collapse old .map-svg-wrap to no-op container)', HUNK_2_OLD, HUNK_2_NEW),
    ('3 (JS: build sibling pngWrap + overlayWrap)', HUNK_3_OLD, HUNK_3_NEW),
    ('4 (JS: applyMapTx writes to both wrappers)', HUNK_4_OLD, HUNK_4_NEW),
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

    if PHASE5_3_SENTINEL not in src:
        print('ERROR: Phase 5.3 sentinel not found. Apply Phase 5.3 first.')
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
    print('  1. Hard reload localhost:8765')
    print('  2. Switch to Map view')
    print('  3. Cam switch should drop from ~133ms to ~25-50ms')
    print('  4. Selected cam: only frustum visible, no dot change')


if __name__ == '__main__':
    main()
