#!/usr/bin/env python3
"""
patch_svg_phase6_4_cam_markers.py — distinct cam markers (concentric ring)

Phase 6.3 left the map visually clean, but cam markers (filled circle +
black stroke) read as the same shape as landmark dots — just bigger.
With ~250 cams + ~1500 lm dots eventually visible at once, that's a
visual soup waiting to happen.

This patch turns each cam marker into a "reticle":
  - Outer ring: stroke-only circle, no fill, at the original
    MARKER_RADIUS (35u). Stroke = the cam's type color (LEAK green,
    Trailer blue, screenshots purple), 5u thick.
  - Inner dot: smaller filled circle (radius 14u) at the same center.
    Filled with the cam type color, black stroke 4u thick.

Visually that's a clear "target" / "viewfinder" iconography — distinct
from a plain filled circle dot at first glance. Hover state stays
similar (the existing :hover stroke-width:50 rule on .cam-marker circle
gets bumped down a touch since "50" was tuned for a single fat circle;
applied to the new outer ring it would create a visual blob).

Side effect: this is a small geometry change inside renderCamsOnMap, no
new state, no new event handlers. It only touches the SVG node tree we
build for each cam-group.

Idempotent. Dry-run by default.
Builds on Phase 6.3. Pre-flight verifies its sentinel (which IS literally
in the file thanks to the Phase 6.3 backfill at the end of the CSS block).
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase6_4'

SENTINEL = '/* Phase 6.4: distinct cam markers (concentric ring) */'
PHASE6_3_SENTINEL = '/* // Phase 6.3: visual polish — fix ray colors + reduce noise */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: tune hover stroke-width on the new outer ring so it doesn't
# blob. Adds also a sentinel comment for downstream patches.
#
# The existing rule `#map-overlay .cam-marker:hover circle{stroke-width:50}`
# was tuned for a single thick-stroke filled circle. Now that .cam-marker
# contains TWO circles (outer ring + inner dot), a stroke-width:50 on the
# outer ring's already-thick stroke is too aggressive. We bump it back
# to a sane 12u for the outer ring and add a separate rule for the inner
# dot's hover so the whole reticle visibly reacts to hover.
#
# Anchor: the existing :hover rule.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
#map-overlay .cam-marker{pointer-events:auto;cursor:pointer;transition:opacity .12s}
#map-overlay .cam-marker:hover circle{stroke-width:50}"""

HUNK_1_NEW = """\
#map-overlay .cam-marker{pointer-events:auto;cursor:pointer;transition:opacity .12s}
/* Phase 6.4: hover state for the new two-circle reticle. The outer ring's
   resting stroke is 5u; on hover we bump to 9u for a visible reaction
   without going blob. The inner dot's black stroke 4u → 8u so the dot
   "fills" perceptually under the cursor. */
#map-overlay .cam-marker:hover .cam-ring{stroke-width:9}
#map-overlay .cam-marker:hover .cam-dot{stroke-width:8}
#map-overlay g.cam-group.selected .cam-marker .cam-ring{stroke-width:9}
#map-overlay g.cam-group.selected .cam-marker .cam-dot{stroke-width:8}
/* Phase 6.4 sentinel — for downstream pre-flight checks */"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — JS: replace the apex marker geometry in renderCamsOnMap.
#
# Anchor: the existing single-circle apex marker block. We replace it with
# a two-circle structure: outer ring (.cam-ring) + inner dot (.cam-dot).
#
# We also bump MARKER_STROKE down a hair since it's only used for the
# inner dot's black stroke now; the outer ring uses a separate width
# (5u) inline.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
      // Apex circle (the marker proper) — smaller, cleaner.
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
      camGroup.appendChild(marker);"""

HUNK_2_NEW = """\
      // Phase 6.4: cam marker as a "reticle" — outer ring (color stroke,
      // no fill) + inner filled dot. Visually distinct from landmark
      // dots which are plain filled circles.
      const marker = document.createElementNS(SVG_NS, 'g');
      marker.setAttribute('class', 'cam-marker');
      marker.dataset.camName = c.name;

      // Outer ring: stroke-only, cam-type color, at MARKER_RADIUS.
      const ring = document.createElementNS(SVG_NS, 'circle');
      ring.setAttribute('class', 'cam-ring');
      ring.setAttribute('cx', String(sx));
      ring.setAttribute('cy', String(sy));
      ring.setAttribute('r', String(MARKER_RADIUS));
      ring.setAttribute('fill', 'none');
      ring.setAttribute('stroke', color);
      ring.setAttribute('stroke-width', '5');
      marker.appendChild(ring);

      // Inner dot: small filled circle, color fill + black thin stroke.
      const dot = document.createElementNS(SVG_NS, 'circle');
      dot.setAttribute('class', 'cam-dot');
      dot.setAttribute('cx', String(sx));
      dot.setAttribute('cy', String(sy));
      dot.setAttribute('r', '14');
      dot.setAttribute('fill', color);
      dot.setAttribute('stroke', '#000');
      dot.setAttribute('stroke-width', '4');
      marker.appendChild(dot);

      camGroup.appendChild(marker);"""


HUNKS = [
    ('CSS — reticle hover/selected states + 6.4 sentinel', HUNK_1_OLD, HUNK_1_NEW),
    ('JS — render cam marker as ring + inner dot',         HUNK_2_OLD, HUNK_2_NEW),
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
    print('  - Each cam marker is now a "reticle": outer color ring + inner dot')
    print('  - Color still encodes type (LEAK green, T1/T2 blue, SS purple)')
    print('  - Hover/select: ring stroke thickens, dot stroke thickens')
    print('  - Visually unambiguous vs landmark dots (filled solid circles)')


if __name__ == '__main__':
    main()
