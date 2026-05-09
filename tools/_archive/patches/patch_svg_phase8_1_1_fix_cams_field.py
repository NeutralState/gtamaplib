#!/usr/bin/env python3
"""
patch_svg_phase8_1_1_fix_cams_field.py — fix mapData.cams → mapData.cameras

Phase 8.1's showTriangulationOnMap() reads window.mapData.cams, but the
actual field name is window.mapData.cameras (per the /api/map_data response
shape: keys are transform, cameras, landmarks, counts).

Result: the source-cam lookup `(window.mapData?.cams || []).find(...)`
returned undefined for every cam → tri-rays loop drew nothing → and
likely something else threw silently before the pulse render.

Fix: rename `cams` → `cameras` in the two access sites inside
showTriangulationOnMap. Plus add a defensive console.error if the
lookup still finds zero cams, so future debugging is faster.

Idempotent. Builds on Phase 8.1.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase8_1_1'

SENTINEL = '/* Phase 8.1.1: fix mapData.cams → mapData.cameras */'
PHASE8_1_SENTINEL = '/* Phase 8.1: triangulate on Map view + drop showRayMap callsites */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — fix the camColor lookup.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
  function camColor(camName) {
    const cam = (window.mapData?.cams || []).find(c => c.name === camName);
    if (!cam) return '#9090b0';"""

HUNK_1_NEW = """\
  function camColor(camName) {
    // Phase 8.1.1: window.mapData.cameras (not .cams)
    const cam = (window.mapData?.cameras || []).find(c => c.name === camName);
    if (!cam) return '#9090b0';"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — fix the per-source-cam lookup in the rays loop.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
  // Render one ray per source cam.
  for (const camName of sourceCams) {
    const cam = (window.mapData?.cams || []).find(c => c.name === camName);
    if (!cam || !cam.xyz) continue;"""

HUNK_2_NEW = """\
  // Render one ray per source cam.
  // Phase 8.1.1: window.mapData.cameras (not .cams)
  let _triRaysDrawn = 0;
  for (const camName of sourceCams) {
    const cam = (window.mapData?.cameras || []).find(c => c.name === camName);
    if (!cam || !cam.xyz) continue;
    _triRaysDrawn++;"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — add defensive log after the rays loop, before the pulse.
# Anchor: the pulse circle creation block.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
  // Pulse ring around the landmark.
  const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');"""

HUNK_3_NEW = """\
  // Phase 8.1.1: defensive log — if 0 rays drawn, something is wrong.
  if (_triRaysDrawn === 0) {
    console.warn('[tri-rays] drew 0 rays for', lmName,
      '— sourceCams:', sourceCams,
      '· mapData.cameras count:', window.mapData?.cameras?.length);
  }
  // Pulse ring around the landmark.
  const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');"""


HUNKS = [
    ('JS — camColor lookup uses .cameras',          HUNK_1_OLD, HUNK_1_NEW),
    ('JS — per-source-cam lookup uses .cameras',    HUNK_2_OLD, HUNK_2_NEW),
    ('JS — defensive log if 0 rays drawn',          HUNK_3_OLD, HUNK_3_NEW),
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

    if PHASE8_1_SENTINEL not in src:
        print('ERROR: Phase 8.1 sentinel not found.')
        sys.exit(1)

    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} times (need exactly 1).')
            sys.exit(1)

    new_src = src
    for _label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    new_src = new_src.replace(PHASE8_1_SENTINEL,
                              PHASE8_1_SENTINEL + '\n' + SENTINEL,
                              1)

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
    print('Test: hard reload, click ⊕ on a non-triangulated landmark.')
    print('Tri-rays should now actually render.')


if __name__ == '__main__':
    main()
