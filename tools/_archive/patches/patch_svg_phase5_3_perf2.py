#!/usr/bin/env python3
"""
patch_svg_phase5_3_perf2.py — Phase 5 second perf pass

Phase 5.2 cached the cam->landmarks indexes but the lag remained because
the bottleneck is GPU compositing of ~600 SVG nodes (147 cams × 4 elements:
fill polygon + 2 lines + circle) on top of the transformed PNG layer.

This patch hides frustums for non-selected cams via CSS. Only the selected
cam (and the one being hovered) shows its FOV edges + fill; all other cams
are reduced to a single small apex circle. Total visible node count drops
from ~600 to ~150, and pan/zoom becomes fluid.

Also fixes a latent bug: the .selected class is on the .cam-group parent
(set by updateMapSelectionStyle), but Phase 5's CSS used
`.cam-marker.selected` which never matched. The new selector traverses
through the parent group: `g.cam-group.selected .cam-marker circle`.

Builds on Phase 5.2. Pre-flight verifies its sentinel.
Idempotent. Dry-run by default.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase5_3'

SENTINEL = '/* Phase 5.3 perf: hide frustums for non-selected cams */'
PHASE5_2_SENTINEL = '// Phase 5.2 perf: precomputed cam->landmarks index'


# Single combined hunk — replace the entire CSS block from Phase 5.1
# with the new "hide frustums by default, show on selected/hover" version.
HUNK_OLD = """\
/* Phase 5.1: lighter cam style — apex dot + 2 thin FOV edge lines (matches
   /api/generate_map look), with very light fill between the edges. */
#map-overlay{pointer-events:none}
#map-overlay .cam-marker{pointer-events:auto;cursor:pointer;transition:opacity .12s}
#map-overlay .cam-marker:hover circle{stroke-width:50}
#map-overlay .cam-frustum{pointer-events:none;opacity:.5;transition:opacity .15s}
#map-overlay .cam-frustum-fill{pointer-events:none;opacity:.08;transition:opacity .15s}
#map-overlay .cam-marker.selected circle{stroke:var(--text);stroke-width:70}
#map-overlay g.cam-group.selected .cam-frustum{opacity:1}
#map-overlay g.cam-group.selected .cam-frustum-fill{opacity:.18}
#map-overlay .ray-line{stroke:var(--blue);stroke-width:20;opacity:.45;pointer-events:none}"""

HUNK_NEW = """\
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

    if PHASE5_2_SENTINEL not in src:
        print('ERROR: Phase 5.2 sentinel not found. Apply Phase 5+5.1+5.2 first.')
        sys.exit(1)

    n = src.count(HUNK_OLD)
    if n != 1:
        print(f'ERROR: anchor matches {n} times (need exactly 1).')
        sys.exit(1)

    new_src = src.replace(HUNK_OLD, HUNK_NEW, 1)
    delta = new_src.count('\n') - src.count('\n')
    print(f'Will modify {CALIB_HTML} ({delta:+d} lines)')

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
    print('  - Pan/zoom should be MUCH more fluid')
    print('  - Selected cam: shows frustum + white-stroked apex')
    print('  - Hovered cam: shows frustum on hover')
    print('  - Other cams: just a colored dot')


if __name__ == '__main__':
    main()
