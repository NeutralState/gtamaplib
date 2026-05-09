#!/usr/bin/env python3
"""
patch_svg_phase6_4_yanis_v_markers.py — Yanis-style V cam markers

Phase 6.4 v3 takes the cam marker iconography directly from yanis_v11
itself: each cam = a small "V" (the two FOV edges) with a colored dot
at the apex. This visually matches the legend embedded in the yanis
source map, gives instant readability ("V" = camera, intuitive), and
auto-encodes the cam's yaw and hFOV in the marker shape.

Geometry (SVG-user units):
  - Apex dot at the cam's world position. r = 18u, filled with the cam
    type color, black stroke 4u.
  - Two FOV-edge lines from the apex outward at angles ±(hfov/2) from
    the cam's forward direction (yaw). Length 60u — long enough to read
    as a V at default zoom, short enough to not clash with the much
    longer Phase 5 frustum which appears on hover/select.
  - Lines colored by cam type (same as the apex dot), 6u stroke,
    rounded linecap.

Yaw / world → SVG mapping reuses the existing
frustumCornersWorld(camXyz, yaw, hfov, dist) helper (Phase 5.1) — the
identical formula used to draw the full frustum, so the V is always
collinear with the frustum that opens on hover. Net effect: hovering
a cam = the V "extends" into the full frustum, which reads as a
zoom-in / focus effect.

Idempotent. Dry-run by default. Builds on Phase 6.3 (clean, no Phase 6.4
v1 or v2 applied).
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase6_4_yanis'

SENTINEL = '/* Phase 6.4 v3: Yanis-style V cam markers (apex dot + FOV edges) */'
PHASE6_3_SENTINEL = '/* // Phase 6.3: visual polish — fix ray colors + reduce noise */'
# Refuse to apply if any earlier 6.4 attempt is still in place.
PHASE6_4_V1_SENTINEL = '/* Phase 6.4 sentinel — for downstream pre-flight checks */'
PHASE6_4_V2_SENTINEL = '/* Phase 6.4 v2 sentinel — for downstream pre-flight checks */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: V hover/selected styling + sentinel.
#
# Anchor: the existing :hover rule from Phase 5. We replace it with a
# V-aware version that tweaks the apex dot stroke + V-edge stroke on
# hover/select. We DON'T add a hover ring this time — the existing
# Phase 5 frustum (which appears on hover) already provides the
# selection feedback by extending the V into a full triangle. Adding a
# ring would compete.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
#map-overlay .cam-marker{pointer-events:auto;cursor:pointer;transition:opacity .12s}
#map-overlay .cam-marker:hover circle{stroke-width:50}"""

HUNK_1_NEW = """\
#map-overlay .cam-marker{pointer-events:auto;cursor:pointer;transition:opacity .12s}
/* Phase 6.4 v3: Yanis-style V cam markers. The marker is a <g> with
   two children: a <path class="cam-v"> (the V's two edges) and a
   <circle class="cam-apex"> (the colored dot at the cam position).
   Hover/selected only thickens the apex stroke — the existing Phase 5
   frustum reveals on hover and provides the spatial feedback. */
#map-overlay .cam-v{stroke-width:6;stroke-linecap:round;fill:none;pointer-events:none;transition:stroke-width .12s}
#map-overlay .cam-apex{stroke:#000;stroke-width:4;transition:stroke-width .12s}
#map-overlay .cam-marker:hover .cam-apex,
#map-overlay g.cam-group.selected .cam-marker .cam-apex{stroke-width:6}
#map-overlay .cam-marker:hover .cam-v,
#map-overlay g.cam-group.selected .cam-marker .cam-v{stroke-width:9}
/* Phase 6.4 v3 sentinel — for downstream pre-flight checks */"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — JS: replace the apex marker geometry with apex dot + FOV-edge V.
#
# Anchor: the same Phase 5 single-circle apex block.
#
# Implementation: we already have `frustumCornersWorld(camXyz, yaw, hfov, dist)`
# from Phase 5.1 which gives the world-space endpoints of the two FOV
# edges. We reuse it with a SHORT distance (60u in world coords ≈ 60
# SVG-user units after worldToSvg, since the y_sign just flips Y, no
# scaling — the SVG viewBox is in world-pixel units).
#
# Wait — actually the world->svg transform is a translate-only thing:
#     [sx, sy] = [wx + ox, y_sign*wy + oy]
# So world 60u distance from cam = 60u distance in SVG. Good.
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
      // Phase 6.4 v3: Yanis-style V cam marker.
      // Two short FOV-edge lines from the apex (the cam position), at
      // angles ±(hfov/2) from forward (yaw). Length picked to be visible
      // at default fit-zoom but much shorter than the full Phase 5
      // frustum which appears on hover/select.
      const V_EDGE_LEN = 60;  // SVG-user units (== world units here)
      const vEdgesWorld = frustumCornersWorld(c.xyz, yaw, hfov, V_EDGE_LEN);
      const vEdgesSvg = vEdgesWorld.map(([wx, wy]) => window.worldToSvg(wx, wy));

      const marker = document.createElementNS(SVG_NS, 'g');
      marker.setAttribute('class', 'cam-marker');
      marker.dataset.camName = c.name;

      // The V (two edges, drawn as one path so a single stroke applies).
      const v = document.createElementNS(SVG_NS, 'path');
      v.setAttribute('class', 'cam-v');
      v.setAttribute('d',
        `M ${vEdgesSvg[0][0]} ${vEdgesSvg[0][1]} ` +
        `L ${sx} ${sy} ` +
        `L ${vEdgesSvg[1][0]} ${vEdgesSvg[1][1]}`);
      v.setAttribute('stroke', color);
      marker.appendChild(v);

      // The apex dot (the cam position itself).
      const apex = document.createElementNS(SVG_NS, 'circle');
      apex.setAttribute('class', 'cam-apex');
      apex.setAttribute('cx', String(sx));
      apex.setAttribute('cy', String(sy));
      apex.setAttribute('r', '18');
      apex.setAttribute('fill', color);
      marker.appendChild(apex);

      camGroup.appendChild(marker);"""


HUNKS = [
    ('CSS — V hover/selected stroke states + sentinel', HUNK_1_OLD, HUNK_1_NEW),
    ('JS — render cam marker as apex dot + V edges',    HUNK_2_OLD, HUNK_2_NEW),
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
        print('ERROR: Phase 6.4 v1 (concentric ring) is still applied. Revert it first.')
        sys.exit(1)
    if PHASE6_4_V2_SENTINEL in src:
        print('ERROR: Phase 6.4 v2 (chevron) is still applied. Revert it first.')
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
    print('Test: hard reload, switch to Map view.')
    print('  - Each cam = small V + apex dot, oriented by yaw, hFOV-aware')
    print('  - Identical iconography to the yanis_v11 legend')
    print('  - Hover: apex stroke + V stroke thicken; full frustum opens')
    print('    "extending" the V into a long triangle')
    print('  - Selected cam: same thicker styling persists')
    print()
    print('Tweak knobs (in HUNK 2):')
    print('  V_EDGE_LEN — length of the V edges (60u default)')
    print('  apex r="18" — size of the apex dot')


if __name__ == '__main__':
    main()
