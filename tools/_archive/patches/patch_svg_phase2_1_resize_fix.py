#!/usr/bin/env python3
"""
patch_svg_phase2_1_resize_fix.py — hotfix for Phase 2

Bug: when the left sidebar collapses/expands, the canvas-wrap container
changes size, but the canvas overlay (which holds the marked-pixel circles
and projection crosses) doesn't get resized. This makes the markers stick
to the old screen positions while the underlying <img> scales correctly,
so they no longer line up with the image features.

Root cause: resizeOverlay() is only called on window resize and image load.
The container width changes (via CSS transition) without either firing.

Fix: hook into the existing burger-toggle handler to call resizeOverlay()
after the CSS transition ends. We use 'transitionend' rather than a fixed
timeout so the resize happens at exactly the right moment, even if the
transition duration changes later.

This patch only modifies the JS handler block introduced by Phase 2.
Idempotent (sentinel-detected). Dry-run by default. Backup created.

Usage:
  python3 tools/patch_svg_phase2_1_resize_fix.py            # dry-run
  python3 tools/patch_svg_phase2_1_resize_fix.py --apply    # apply
  python3 tools/patch_svg_phase2_1_resize_fix.py --revert --apply
"""

import argparse
import os
import shutil
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase2_1'

# Sentinel — present in HUNK_NEW (new comment line).
SENTINEL = '// Phase 2.1: also re-size the canvas overlay'

# Anchor: the entire Phase 2 toggle handler block (matches once).
HUNK_OLD = """\
  // Burger toggle for the left sidebar (session-only, no localStorage)
  const leftSidebar = document.getElementById('left-sidebar');
  const camToggleBtn = document.getElementById('cam-toggle-btn');
  if (camToggleBtn && leftSidebar) {
    camToggleBtn.addEventListener('click', () => {
      leftSidebar.classList.toggle('collapsed');
    });
  }"""

HUNK_NEW = """\
  // Burger toggle for the left sidebar (session-only, no localStorage)
  const leftSidebar = document.getElementById('left-sidebar');
  const camToggleBtn = document.getElementById('cam-toggle-btn');
  if (camToggleBtn && leftSidebar) {
    camToggleBtn.addEventListener('click', () => {
      leftSidebar.classList.toggle('collapsed');
    });
    // Phase 2.1: also re-size the canvas overlay when the sidebar
    // finishes collapsing/expanding. Without this, the canvas keeps
    // its old width/height while the <img> auto-scales (object-fit:
    // contain), so marked pixels and projections drift off the image.
    // We listen for the 'width' transition specifically; the sidebar
    // also sets border-right which transitions but we don't care.
    leftSidebar.addEventListener('transitionend', e => {
      if (e.propertyName !== 'width') return;
      if (typeof resizeOverlay === 'function') resizeOverlay();
    });
  }"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true',
                    help='actually write changes (default: dry-run)')
    ap.add_argument('--revert', action='store_true',
                    help='restore calib.html from .bak_svg_phase2_1 backup')
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
            print(f'(dry-run) would restore {CALIB_HTML} from {BACKUP}.')
            print('Re-run with --revert --apply to actually revert.')
        return

    with open(CALIB_HTML, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print(f'✓ Already patched (sentinel found).')
        print('  No changes needed. Use --revert --apply if you want to undo.')
        return

    n = src.count(HUNK_OLD)
    if n != 1:
        print(f'ERROR: anchor matches {n} times (need exactly 1).')
        print('       This patch expects Phase 2 to be applied first.')
        print('       If Phase 2 was reverted or never applied, this hotfix is not needed.')
        sys.exit(1)

    new_src = src.replace(HUNK_OLD, HUNK_NEW, 1)
    delta_lines = new_src.count('\n') - src.count('\n')
    print(f'Will modify {CALIB_HTML}')
    print(f'  net line delta: {delta_lines:+d}')
    print(f'  fix: trigger resizeOverlay() on sidebar transitionend')

    if not args.apply:
        print('\n(dry-run — re-run with --apply to write changes)')
        return

    shutil.copy(CALIB_HTML, BACKUP)
    print(f'\n✓ Backup: {BACKUP}')
    tmp = CALIB_HTML + '.tmp'
    with open(tmp, 'w') as f:
        f.write(new_src)
    os.replace(tmp, CALIB_HTML)
    print(f'✓ Patched {CALIB_HTML}')
    print()
    print('Test: reload page, click ≡, watch marked pixels stay aligned with image.')


if __name__ == '__main__':
    main()
