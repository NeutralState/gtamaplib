#!/usr/bin/env python3
"""
patch_phase9_1_1_fix_currentcam_ref.py — fix window.currentCam → currentCam

Phase 9.1's _syncUrlHash() reads window.currentCam, but the actual variable
is just `currentCam` (a script-local let, not attached to window). Same fix
needed wherever window.currentCam was used in Phase 9.1 code.

Idempotent. Builds on Phase 9.1.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_phase9_1_1'

SENTINEL = '/* Phase 9.1.1: fix window.currentCam ref */'
PHASE9_1_SENTINEL = '/* Phase 9.1: URL hash state + landmark sort */'


HUNK_1_OLD = """\
function _syncUrlHash() {
  _writeUrlHash({
    cam: window.currentCam || null,
    view: document.body.classList.contains('view-map') ? 'map' : 'camera',
    sort: lmSort
  });
}"""

HUNK_1_NEW = """\
function _syncUrlHash() {
  // Phase 9.1.1: currentCam is a script-local var, not on window.
  _writeUrlHash({
    cam: (typeof currentCam !== 'undefined' ? currentCam : null) || null,
    view: document.body.classList.contains('view-map') ? 'map' : 'camera',
    sort: lmSort
  });
}"""


HUNKS = [
    ('JS — fix _syncUrlHash currentCam ref',  HUNK_1_OLD, HUNK_1_NEW),
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
            print(f'(dry-run) would restore.')
        return

    with open(CALIB_HTML, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print('✓ Already patched.')
        return
    if PHASE9_1_SENTINEL not in src:
        print('ERROR: Phase 9.1 sentinel not found.')
        sys.exit(1)

    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} (need 1).')
            sys.exit(1)

    new_src = src
    for _label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)
    new_src = new_src.replace(PHASE9_1_SENTINEL,
                              PHASE9_1_SENTINEL + '\n' + SENTINEL, 1)

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
    print('Test: hard reload, select a cam, URL should show #cam=...')


if __name__ == '__main__':
    main()
