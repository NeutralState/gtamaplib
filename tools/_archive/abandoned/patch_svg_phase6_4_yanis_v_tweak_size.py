#!/usr/bin/env python3
"""
patch_svg_phase6_4_yanis_v_tweak_size.py — bump V cam marker dimensions

Phase 6.4 v3 rendered the Yanis-style V markers correctly but at
ridiculously small dimensions for a 20000-unit-wide map (V_EDGE_LEN=60,
apex r=18, V stroke=6). This tweak triples-to-quintuples those values
to match the existing MARKER_RADIUS=35 / FRUSTUM_LINE_WIDTH=6 conventions
already established by Phase 5.

Changes:
  - V_EDGE_LEN: 60 → 300 (long enough to read as a clear V shape)
  - apex dot r: 18 → 35 (matches old MARKER_RADIUS for visual weight,
    same size as the original Phase 5 cam circle)
  - V stroke-width: 6 → 20 (proportional to length, won't look like
    spider legs)
  - Hover/selected V stroke-width: 9 → 28 (proportional bump)
  - Apex stroke-width unchanged (4u resting, 6u hover) — black outline
    at 4u still reads well around a r=35 dot.

Idempotent. Builds on Phase 6.4 v3.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase6_4_v_size'

SENTINEL = '/* Phase 6.4 v3.1: V marker size bump */'
PHASE6_4_V3_SENTINEL = '/* Phase 6.4 v3 sentinel — for downstream pre-flight checks */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: bump V stroke-widths.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
#map-overlay .cam-v{stroke-width:6;stroke-linecap:round;fill:none;pointer-events:none;transition:stroke-width .12s}
#map-overlay .cam-apex{stroke:#000;stroke-width:4;transition:stroke-width .12s}
#map-overlay .cam-marker:hover .cam-apex,
#map-overlay g.cam-group.selected .cam-marker .cam-apex{stroke-width:6}
#map-overlay .cam-marker:hover .cam-v,
#map-overlay g.cam-group.selected .cam-marker .cam-v{stroke-width:9}
/* Phase 6.4 v3 sentinel — for downstream pre-flight checks */"""

HUNK_1_NEW = """\
/* Phase 6.4 v3.1: V stroke-widths bumped to match the new V_EDGE_LEN=300
   and apex r=35 dimensions. Old values (6/9) looked like spider legs. */
#map-overlay .cam-v{stroke-width:20;stroke-linecap:round;fill:none;pointer-events:none;transition:stroke-width .12s}
#map-overlay .cam-apex{stroke:#000;stroke-width:8;transition:stroke-width .12s}
#map-overlay .cam-marker:hover .cam-apex,
#map-overlay g.cam-group.selected .cam-marker .cam-apex{stroke-width:14}
#map-overlay .cam-marker:hover .cam-v,
#map-overlay g.cam-group.selected .cam-marker .cam-v{stroke-width:28}
/* Phase 6.4 v3 sentinel — for downstream pre-flight checks */
/* Phase 6.4 v3.1: V marker size bump */"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — JS: bump V_EDGE_LEN from 60 to 300.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
      // Phase 6.4 v3: Yanis-style V cam marker.
      // Two short FOV-edge lines from the apex (the cam position), at
      // angles ±(hfov/2) from forward (yaw). Length picked to be visible
      // at default fit-zoom but much shorter than the full Phase 5
      // frustum which appears on hover/select.
      const V_EDGE_LEN = 60;  // SVG-user units (== world units here)"""

HUNK_2_NEW = """\
      // Phase 6.4 v3: Yanis-style V cam marker.
      // Two short FOV-edge lines from the apex (the cam position), at
      // angles ±(hfov/2) from forward (yaw). Length picked to be visible
      // at default fit-zoom but much shorter than the full Phase 5
      // frustum which appears on hover/select.
      // Phase 6.4 v3.1: bumped from 60 → 300 — was way too small at
      // default zoom on a 20000u-wide map.
      const V_EDGE_LEN = 300;  // SVG-user units (== world units here)"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — JS: bump apex dot radius from 18 to 35 (matching MARKER_RADIUS).
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
      apex.setAttribute('cx', String(sx));
      apex.setAttribute('cy', String(sy));
      apex.setAttribute('r', '18');"""

HUNK_3_NEW = """\
      apex.setAttribute('cx', String(sx));
      apex.setAttribute('cy', String(sy));
      apex.setAttribute('r', '35');"""


HUNKS = [
    ('CSS — V/apex stroke-widths bumped',  HUNK_1_OLD, HUNK_1_NEW),
    ('JS — V_EDGE_LEN 60 → 300',           HUNK_2_OLD, HUNK_2_NEW),
    ('JS — apex r 18 → 35',                HUNK_3_OLD, HUNK_3_NEW),
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

    if PHASE6_4_V3_SENTINEL not in src:
        print('ERROR: Phase 6.4 v3 sentinel not found. Apply Phase 6.4 v3 first.')
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
    print('  - V markers should now be CLEARLY visible at default zoom')
    print('  - 5x bigger V edges, ~2x bigger apex dot, proportionally thicker strokes')


if __name__ == '__main__':
    main()
