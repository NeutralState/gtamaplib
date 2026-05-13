#!/usr/bin/env python3
"""
patch_svg_phase5_2_perf.py — Phase 5 performance optimization

Phase 5.1 introduced lag: the SVG overlay contains ~600 nodes (147 cams ×
4 elements each), and changing the selected cam re-runs an O(N×M) loop
over all landmarks to find which ones the cam observes.

This patch precomputes two indexes ONCE per map load:
  - window.mapCamLandmarks  : Map<cam_name, array<lm_record>>  (used by
                              the rays toggle to draw lines)
  - window.mapCamFrustumDist : Map<cam_name, distance>          (used by
                              the cam render)

Both are filled in one O(N×M) pass when the map first loads, then used
for O(1) lookups on every subsequent interaction. Selecting a different
cam goes from "scan all landmarks" (slow) to "Map.get()" (instant).

Also: the cam markers/frustums now render once at map load and stay in
the DOM. Selection changes update CSS classes only, no DOM rebuild.

Builds on Phase 5.1. Pre-flight verifies its sentinel.

Idempotent. Dry-run by default.

Usage:
  python3 tools/patch_svg_phase5_2_perf.py            # dry-run
  python3 tools/patch_svg_phase5_2_perf.py --apply
  python3 tools/patch_svg_phase5_2_perf.py --revert --apply
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase5_2'

SENTINEL = '// Phase 5.2 perf: precomputed cam->landmarks index'
PHASE5_1_SENTINEL = '// Phase 5.1: yaw fix (-sin) + lighter style'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — replace the O(N×M) frustumDistanceForCam with a Map lookup
# Anchor: the existing function definition.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
  function frustumDistanceForCam(cam) {
    if (!window.mapData || !cam.xyz) return FRUSTUM_DIST_DEFAULT;
    let maxDist = 0;
    const [cx, cy] = cam.xyz;
    for (const lm of (window.mapData.landmarks || [])) {
      if (!lm.xyz) continue;
      const observers = lm.source_cameras || lm.observed_by || [];
      if (!observers.includes(cam.name)) continue;
      const d = Math.hypot(lm.xyz[0] - cx, lm.xyz[1] - cy);
      if (d > maxDist) maxDist = d;
    }
    if (maxDist === 0) return FRUSTUM_DIST_DEFAULT;
    return Math.max(FRUSTUM_DIST_MIN, Math.min(FRUSTUM_DIST_MAX, maxDist));
  }"""

HUNK_1_NEW = """\
  // Phase 5.2 perf: precomputed cam->landmarks index
  // mapCamLandmarks: Map<cam_name, array<lm_record>>  (cached after first build)
  // mapCamFrustumDist: Map<cam_name, distance>         (cached after first build)
  // Both built lazily in buildMapIndexes(), called once when /api/map_data
  // arrives. Subsequent calls are O(1) lookups.
  window.mapCamLandmarks = null;
  window.mapCamFrustumDist = null;

  function buildMapIndexes() {
    if (!window.mapData) return;
    if (window.mapCamLandmarks && window.mapCamFrustumDist) return;  // already built
    const camLm = new Map();
    const camDist = new Map();
    // Init each cam with empty array.
    for (const c of window.mapData.cameras) {
      camLm.set(c.name, []);
    }
    // Single pass over landmarks.
    for (const lm of (window.mapData.landmarks || [])) {
      const observers = lm.source_cameras || lm.observed_by || [];
      for (const camName of observers) {
        const arr = camLm.get(camName);
        if (arr) arr.push(lm);
      }
    }
    // Compute frustum distance per cam.
    for (const c of window.mapData.cameras) {
      if (!c.xyz) { camDist.set(c.name, FRUSTUM_DIST_DEFAULT); continue; }
      const [cx, cy] = c.xyz;
      let maxDist = 0;
      for (const lm of camLm.get(c.name)) {
        if (!lm.xyz) continue;
        const d = Math.hypot(lm.xyz[0] - cx, lm.xyz[1] - cy);
        if (d > maxDist) maxDist = d;
      }
      if (maxDist === 0) maxDist = FRUSTUM_DIST_DEFAULT;
      camDist.set(c.name, Math.max(FRUSTUM_DIST_MIN, Math.min(FRUSTUM_DIST_MAX, maxDist)));
    }
    window.mapCamLandmarks = camLm;
    window.mapCamFrustumDist = camDist;
  }

  function frustumDistanceForCam(cam) {
    if (!window.mapCamFrustumDist) return FRUSTUM_DIST_DEFAULT;
    return window.mapCamFrustumDist.get(cam.name) || FRUSTUM_DIST_DEFAULT;
  }"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — call buildMapIndexes before rendering, and change rays loop
# to use the precomputed cam->landmarks index instead of full scan.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
  function renderRaysForSelectedCam() {
    if (!window.mapOverlay) return;
    const raysLayer = document.getElementById('rays-layer');
    if (!raysLayer) return;
    while (raysLayer.firstChild) raysLayer.removeChild(raysLayer.firstChild);
    if (!raysToggleOn || !mapSelectedCamName || !window.mapData) return;

    // Find the selected cam's xyz (apex).
    const cam = window.mapData.cameras.find(c => c.name === mapSelectedCamName);
    if (!cam || !cam.xyz) return;
    const [ax, ay] = window.worldToSvg(cam.xyz[0], cam.xyz[1]);

    // Find the landmarks observed by this cam. We rely on the lm record
    // having a `source_cameras` array OR `observed_by` OR similar field.
    // /api/map_data's landmarks are dumped from gtamapdata; the field
    // listing observers is `source_cameras` (per the data layer).
    const SVG_NS = 'http://www.w3.org/2000/svg';
    let drawn = 0;
    for (const lm of (window.mapData.landmarks || [])) {
      if (!lm.xyz) continue;  // skip untriangulated for ray draw
      const observers = lm.source_cameras || lm.observed_by || [];
      if (!observers.includes(mapSelectedCamName)) continue;
      const [bx, by] = window.worldToSvg(lm.xyz[0], lm.xyz[1]);
      const line = document.createElementNS(SVG_NS, 'line');
      line.setAttribute('x1', String(ax));
      line.setAttribute('y1', String(ay));
      line.setAttribute('x2', String(bx));
      line.setAttribute('y2', String(by));
      line.setAttribute('class', 'ray-line');
      raysLayer.appendChild(line);
      drawn++;
    }
  }"""

HUNK_2_NEW = """\
  function renderRaysForSelectedCam() {
    if (!window.mapOverlay) return;
    const raysLayer = document.getElementById('rays-layer');
    if (!raysLayer) return;
    while (raysLayer.firstChild) raysLayer.removeChild(raysLayer.firstChild);
    if (!raysToggleOn || !mapSelectedCamName || !window.mapData) return;

    const cam = window.mapData.cameras.find(c => c.name === mapSelectedCamName);
    if (!cam || !cam.xyz) return;
    const [ax, ay] = window.worldToSvg(cam.xyz[0], cam.xyz[1]);

    // Phase 5.2 perf: O(K) lookup instead of O(M) scan.
    const observed = window.mapCamLandmarks ? window.mapCamLandmarks.get(mapSelectedCamName) : null;
    if (!observed) return;
    const SVG_NS = 'http://www.w3.org/2000/svg';
    for (const lm of observed) {
      if (!lm.xyz) continue;
      const [bx, by] = window.worldToSvg(lm.xyz[0], lm.xyz[1]);
      const line = document.createElementNS(SVG_NS, 'line');
      line.setAttribute('x1', String(ax));
      line.setAttribute('y1', String(ay));
      line.setAttribute('x2', String(bx));
      line.setAttribute('y2', String(by));
      line.setAttribute('class', 'ray-line');
      raysLayer.appendChild(line);
    }
  }"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — call buildMapIndexes() at the top of renderCamsOnMap()
# Anchor: the function entry.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
  function renderCamsOnMap() {
    if (!window.mapOverlay || !window.mapData) return;
    // Clear any previous render.
    while (window.mapOverlay.firstChild) {
      window.mapOverlay.removeChild(window.mapOverlay.firstChild);
    }"""

HUNK_3_NEW = """\
  function renderCamsOnMap() {
    if (!window.mapOverlay || !window.mapData) return;
    // Phase 5.2 perf: build indexes once on first render.
    buildMapIndexes();
    // Clear any previous render.
    while (window.mapOverlay.firstChild) {
      window.mapOverlay.removeChild(window.mapOverlay.firstChild);
    }"""


HUNKS = [
    ('1 (cache cam->landmarks + cam->distance indexes)', HUNK_1_OLD, HUNK_1_NEW),
    ('2 (renderRaysForSelectedCam: O(K) via index)', HUNK_2_OLD, HUNK_2_NEW),
    ('3 (renderCamsOnMap: build indexes lazily)', HUNK_3_OLD, HUNK_3_NEW),
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

    if PHASE5_1_SENTINEL not in src:
        print('ERROR: Phase 5.1 sentinel not found. Apply Phase 5 + 5.1 first.')
        sys.exit(1)

    failures = []
    for label, old, new in HUNKS:
        n = src.count(old)
        if n != 1:
            failures.append(f'  hunk {label}: anchor matches {n} times (need exactly 1)')

    if failures:
        print('ERROR: hunk pre-flight failed:')
        print('\n'.join(failures))
        sys.exit(1)

    new_src = src
    for label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    delta = new_src.count('\n') - src.count('\n')
    print(f'Will modify {CALIB_HTML}')
    print(f'  hunks applied: {len(HUNKS)}')
    print(f'  net line delta: {delta:+d}')
    print()
    for label, _, _ in HUNKS:
        print(f'  ✓ hunk {label}')

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
    print('  - First map load: ~50ms longer for index build (one-time)')
    print('  - Cam selection changes: should be instant now')
    print('  - Rays toggle: should be instant now')


if __name__ == '__main__':
    main()
