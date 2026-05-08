#!/usr/bin/env python3
"""
patch_svg_phase5_5_detach.py — detach map-view DOM when not in use

Phase 5.4 fixed the GPU layer issue but Camera view became slow because
the 600 SVG nodes (cam markers + frustums) we render in the map overlay
make the browser do extra style/layout work on every DOM mutation in
the rest of the page — even though .map-view is display:none.

Measured: 26ms with nodes present, 1ms without (in Camera view, on a
cam switch). 26x slowdown.

Fix: detach the .map-view subtree from the DOM entirely when in Camera
view. Re-attach only when entering Map view. Detached subtrees don't
participate in the browser's style/layout pipeline at all.

Implementation:
  - At setView('camera'): if .map-view is in the DOM, parentNode.removeChild
  - At setView('map'): re-append to .main if it's been detached
  - We keep a reference to the parent (.main) at module level so we know
    where to re-insert.
  - The cam markers stay in the overlay even when detached, so coming
    back to Map view doesn't require a re-render.

Builds on Phase 5.4. Pre-flight verifies its sentinel.
Idempotent. Dry-run by default.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase5_5'

SENTINEL = '// Phase 5.5: detach map-view DOM when in Camera view'
PHASE5_4_SENTINEL = '/* Phase 5.4: separate GPU layers + clean dot styling'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — JS: rewrite setView to detach/reattach the map-view subtree
# instead of just toggling a body class.
#
# Anchor: the existing setView() function from Phase 3+4.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
  function setView(name) {
    if (name !== 'camera' && name !== 'map') return;
    if (window.currentView === name) return;
    window.currentView = name;
    document.body.classList.toggle('view-map', name === 'map');
    viewToggle.querySelectorAll('button[data-view]').forEach(b => {
      b.classList.toggle('active', b.dataset.view === name);
    });
    if (name === 'map') {
      ensureMapLoaded();
    } else {
      // Returning to Camera view: re-fit the overlay since the canvas-wrap
      // size may have been at zero while hidden.
      if (typeof resizeOverlay === 'function') resizeOverlay();
    }
  }
  window.setView = setView;"""

HUNK_1_NEW = """\
  // Phase 5.5: detach map-view DOM when in Camera view
  // Keep references so we can re-attach the .map-view in the right place.
  const _mapViewParent = mapView.parentNode;
  const _mapViewSibling = mapView.nextSibling;  // anchor for re-insert

  function setView(name) {
    if (name !== 'camera' && name !== 'map') return;
    if (window.currentView === name) return;
    window.currentView = name;
    document.body.classList.toggle('view-map', name === 'map');
    viewToggle.querySelectorAll('button[data-view]').forEach(b => {
      b.classList.toggle('active', b.dataset.view === name);
    });
    if (name === 'map') {
      // Re-attach .map-view if previously detached.
      if (!mapView.parentNode && _mapViewParent) {
        _mapViewParent.insertBefore(mapView, _mapViewSibling);
      }
      ensureMapLoaded();
    } else {
      // Detach .map-view entirely so its 600+ overlay nodes don't slow
      // down the browser's style/layout pipeline while in Camera view.
      if (mapView.parentNode) {
        mapView.parentNode.removeChild(mapView);
      }
      // Re-fit the canvas overlay since canvas-wrap size may have been 0.
      if (typeof resizeOverlay === 'function') resizeOverlay();
    }
  }
  window.setView = setView;"""


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

    if PHASE5_4_SENTINEL not in src:
        print('ERROR: Phase 5.4 sentinel not found. Apply Phase 5.4 first.')
        sys.exit(1)

    n = src.count(HUNK_1_OLD)
    if n != 1:
        print(f'ERROR: anchor matches {n} times (need exactly 1).')
        sys.exit(1)

    new_src = src.replace(HUNK_1_OLD, HUNK_1_NEW, 1)
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
    print('Test: hard reload, change cam in Camera view.')
    print('  - Should be back to pre-Phase-5 speed')
    print('  - Switch to Map view and back: instant transitions both ways')


if __name__ == '__main__':
    main()
