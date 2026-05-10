#!/usr/bin/env python3
"""
patch_phase9_1_3_fix_sentinel_leak.py — wrap leaking sentinels in HTML comments

Phase 9.1, 9.1.1, and 9.1.2 sentinels were inserted as raw text between
HTML elements, so the browser renders them as visible text at the bottom
of the page. Wrap them in an HTML comment.

Idempotent. Builds on Phase 9.1.2.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_phase9_1_3'


HUNK_1_OLD = """\
/* Phase 9.1: URL hash state + landmark sort */
/* Phase 9.1.1: fix window.currentCam ref */
/* Phase 9.1.2: declutter filter row */
<!-- Phase 8.2: #ray-map-modal removed (replaced by Phase 8.1 Map view tri-rays). -->"""

HUNK_1_NEW = """\
<!-- Phase 9.1: URL hash state + landmark sort -->
<!-- Phase 9.1.1: fix window.currentCam ref -->
<!-- Phase 9.1.2: declutter filter row -->
<!-- Phase 9.1.3: fix sentinel leak -->
<!-- Phase 8.2: #ray-map-modal removed (replaced by Phase 8.1 Map view tri-rays). -->"""


HUNKS = [
    ('HTML — wrap sentinels in HTML comments', HUNK_1_OLD, HUNK_1_NEW),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    if not os.path.exists(CALIB_HTML):
        print(f'ERROR: {CALIB_HTML} not found.')
        sys.exit(1)

    with open(CALIB_HTML, 'r') as f:
        src = f.read()

    if '<!-- Phase 9.1.3: fix sentinel leak -->' in src:
        print('✓ Already patched.')
        return

    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} (need 1).')
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
    print('Test: hard reload. Sentinels should disappear from the visible page.')


if __name__ == '__main__':
    main()
