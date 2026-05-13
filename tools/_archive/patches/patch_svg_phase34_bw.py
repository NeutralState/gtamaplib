#!/usr/bin/env python3
"""
patch_svg_phase34_bw.py — make the map view fully black & white

The PNG was being rendered with `filter: grayscale(.4) brightness(.95)`,
which leaves it visibly tinted. Bump grayscale to 1 (full B&W) and adjust
brightness/contrast to keep it readable.

Builds on Phase 3+4 (PNG version). Pre-flight verifies its sentinel.

Idempotent. Dry-run by default. Backup created.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_phase34_bw'

SENTINEL = '/* Phase 3+4 BW: full grayscale */'
PHASE34_SENTINEL = '/* ── SVG Map Refactor Phase 3+4 (PNG): view toggle + map view ── */'


HUNK_OLD = """\
.map-svg-wrap > img{display:block;
  filter:grayscale(.4) brightness(.95);
  /* Disable browser drag-image and selection on the bitmap */
  user-select:none;-webkit-user-drag:none;pointer-events:none}"""

HUNK_NEW = """\
/* Phase 3+4 BW: full grayscale */
.map-svg-wrap > img{display:block;
  filter:grayscale(1) brightness(1.05) contrast(1.1);
  /* Disable browser drag-image and selection on the bitmap */
  user-select:none;-webkit-user-drag:none;pointer-events:none}"""


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
        print('ERROR: Phase 3+4 (PNG) sentinel not found. Apply patch_svg_phase34_html.py first.')
        sys.exit(1)

    n = src.count(HUNK_OLD)
    if n != 1:
        print(f'ERROR: anchor matches {n} times (need exactly 1).')
        sys.exit(1)

    new_src = src.replace(HUNK_OLD, HUNK_NEW, 1)
    delta = new_src.count('\n') - src.count('\n')
    print(f'Will modify {CALIB_HTML} ({delta:+d} lines)')
    print(f'  filter: grayscale(.4) -> grayscale(1) (full B&W)')

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
    print('Reload browser (no server restart needed).')


if __name__ == '__main__':
    main()
