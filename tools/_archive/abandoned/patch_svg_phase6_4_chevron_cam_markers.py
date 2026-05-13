#!/usr/bin/env python3
"""
patch_svg_phase6_4_chevron_cam_markers.py — chevron-shaped cam markers

Phase 6.4 v1 (concentric ring) didn't land — the ring + inner dot read as
two separate objects, and the inner dot was still vocabulary-overlapping
with landmark dots.

This v2 takes a different tack: cam markers become small **chevron**
shapes oriented by the cam's yaw. Reasoning:

  - Different shape vocabulary (triangle/chevron vs filled circle dots)
    makes cams unambiguously distinguishable from landmarks at any zoom.
  - The yaw is encoded directly in the shape orientation, so you can
    read each cam's direction at a glance without hovering to reveal
    the frustum. This matches the GTA-style minimap (bottom-left in
    cam view) where a small triangle indicates cam heading.
  - Sharper visual character — angled shapes contrast with the rounded
    landmark dots and rounded map elements, giving the map a
    surveying-tool feel.

Geometry (in SVG-user units, world coords NOT transformed):
  - Chevron is a path "M 0 -tip  L base/2 base  L 0 base/3  L -base/2 base  Z"
    forming a stylized arrowhead with a slight inner notch (the L 0 base/3
    pulls the bottom edge inward, making it read as a chevron not a flat
    triangle).
  - tip = 32u (forward extent from center), base = 24u (rear extent).
    Net length 56u, width 48u.
  - Center at the cam's world position, then rotated by yaw so the tip
    points in the cam's forward direction.
  - Filled with the cam type color, black stroke 3u for crispness.

Yaw → SVG rotation:
  - Phase 5 frustum geometry: forward direction in world = (-sin(yaw), cos(yaw)).
  - SVG y-axis is flipped vs world (window.mapTransform.y_sign = -1).
  - With the chevron's local "tip up" direction = (0, -1) in SVG-user space,
    we want to rotate it so its tip points in the SVG-projected forward
    direction.
  - Forward in world = (-sin(yaw), cos(yaw)).
    Forward in SVG  = (-sin(yaw), -cos(yaw))   (y flipped).
    SVG rotation angle θ such that (sin θ, -cos θ) = forward_svg
      → sin θ = -sin(yaw)  and  -cos θ = -cos(yaw)
      → θ = -yaw  (mod 360)
  - So the SVG rotation is `rotate(-yaw, sx, sy)` applied to the chevron.

Hover/selected: outer thin ring appears (radius matching the chevron's
bounding circle) to confirm interaction without changing the chevron
itself. This keeps the chevron crisp and replaces Phase 6.4 v1's
"thicken stroke" hover, which made small chevrons blob.

Idempotent. Dry-run by default. Builds on Phase 6.3 (the working state
after reverting Phase 6.4 v1).

PRE-FLIGHT: requires Phase 6.3 sentinel AND requires that Phase 6.4 v1
NOT be applied (we're a clean replacement, not a stacked patch).
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase6_4_chevron'

SENTINEL = '/* Phase 6.4 v2: chevron cam markers oriented by yaw */'
PHASE6_3_SENTINEL = '/* // Phase 6.3: visual polish — fix ray colors + reduce noise */'
# If this is in the file, the OLD Phase 6.4 v1 was applied — must revert it first.
PHASE6_4_V1_SENTINEL = '/* Phase 6.4 sentinel — for downstream pre-flight checks */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: chevron hover/selected ring + sentinel.
#
# Anchor: the existing :hover rule from Phase 5. We replace it with a
# chevron-aware version. The selected/hover state shows a thin ring
# around the chevron (drawn as a separate <circle> we'll add in HUNK 2).
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
#map-overlay .cam-marker{pointer-events:auto;cursor:pointer;transition:opacity .12s}
#map-overlay .cam-marker:hover circle{stroke-width:50}"""

HUNK_1_NEW = """\
#map-overlay .cam-marker{pointer-events:auto;cursor:pointer;transition:opacity .12s}
/* Phase 6.4 v2: chevron cam markers — hover/selected shows a thin
   indicator ring around the chevron. The chevron itself doesn't change
   on hover (no fill/stroke flicker) — we just reveal the ring. */
#map-overlay .cam-hover-ring{display:none;fill:none;stroke:#fff;stroke-width:3;opacity:.85;pointer-events:none}
#map-overlay .cam-marker:hover .cam-hover-ring{display:block}
#map-overlay g.cam-group.selected .cam-marker .cam-hover-ring{display:block;stroke:#fff;stroke-width:4}
/* Phase 6.4 v2: chevron path crispness */
#map-overlay .cam-chevron{stroke:#000;stroke-width:3;stroke-linejoin:round;paint-order:stroke fill}
/* Phase 6.4 v2 sentinel — for downstream pre-flight checks */"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — JS: replace the apex marker geometry in renderCamsOnMap with
# a chevron path + hover ring.
#
# Anchor: the Phase 5 single-circle apex block (this is the same anchor
# Phase 6.4 v1 used; once we revert v1, this block is back to its Phase 5
# original).
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
      // Phase 6.4 v2: chevron cam marker oriented by yaw.
      // Local-space chevron path (tip up at y=-32, base at y+24, side x=±24,
      // with a notch at y+8 making it read as a chevron not a flat triangle).
      // Then translate to (sx,sy) and rotate by -yaw (see patch comment).
      const marker = document.createElementNS(SVG_NS, 'g');
      marker.setAttribute('class', 'cam-marker');
      marker.dataset.camName = c.name;
      // The transform applies to all children: position + heading.
      marker.setAttribute('transform', `translate(${sx}, ${sy}) rotate(${-yaw})`);

      // Hover/selected ring — drawn underneath the chevron, hidden by
      // default (CSS controls the show/hide).
      const hoverRing = document.createElementNS(SVG_NS, 'circle');
      hoverRing.setAttribute('class', 'cam-hover-ring');
      hoverRing.setAttribute('cx', '0');
      hoverRing.setAttribute('cy', '0');
      hoverRing.setAttribute('r', '40');
      marker.appendChild(hoverRing);

      // The chevron itself.
      const chevron = document.createElementNS(SVG_NS, 'path');
      chevron.setAttribute('class', 'cam-chevron');
      // M tip   L right-base   L center-notch   L left-base   Z
      chevron.setAttribute('d', 'M 0 -32 L 24 24 L 0 8 L -24 24 Z');
      chevron.setAttribute('fill', color);
      marker.appendChild(chevron);

      camGroup.appendChild(marker);"""


HUNKS = [
    ('CSS — chevron + hover ring rules + sentinel', HUNK_1_OLD, HUNK_1_NEW),
    ('JS — render cam marker as chevron path',      HUNK_2_OLD, HUNK_2_NEW),
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

    if PHASE6_4_V1_SENTINEL in src:
        print('ERROR: Phase 6.4 v1 (concentric ring) is still applied.')
        print('       Run: python3 tools/patch_svg_phase6_4_cam_markers.py --revert --apply')
        print('       Then re-run this patch.')
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
    print('  - Each cam is now a small chevron pointing in its yaw direction')
    print('  - Color encodes type (LEAK green, T1/T2 blue, SS purple)')
    print('  - Hover/select: thin white ring appears around the chevron')
    print('  - Visually distinct from the round landmark dots')
    print()
    print('Geometry can be tweaked in HUNK 2 (chevron path "M 0 -32 L 24 24 L 0 8 L -24 24 Z")')
    print('and in CSS (hover ring radius=40, stroke-width).')


if __name__ == '__main__':
    main()
