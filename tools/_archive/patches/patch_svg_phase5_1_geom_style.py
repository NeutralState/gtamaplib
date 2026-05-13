#!/usr/bin/env python3
"""
patch_svg_phase5_1_geom_style.py — fix Phase 5 yaw direction + restyle

Two issues with the initial Phase 5:

1. Frustums pointed in the wrong direction. The reference code in
   server.py /api/generate_map uses:
     end_x = cam_x - ray_len * sin(yaw)
     end_y = cam_y + ray_len * cos(yaw)
   We had: +sin / +cos. The sin needs to be NEGATED.

2. Style was too heavy: thick filled triangles dominated. The reference
   draws just two thin lines (the FOV edges), no fill. We keep the same
   minimalist approach but add a very light fill (~8% opacity) since
   the user said "une légère opacité ça pourrait être cool".

Also matches the reference's frustum length: extend rays to the distance
of the farthest landmark observed by that cam (clamped to a min/max for
cams with very few landmarks). When a cam has no landmarks, fall back
to a default of 1500 world units.

Builds on Phase 5. Pre-flight verifies its sentinel.

Idempotent. Dry-run by default.

Usage:
  python3 tools/patch_svg_phase5_1_geom_style.py            # dry-run
  python3 tools/patch_svg_phase5_1_geom_style.py --apply
  python3 tools/patch_svg_phase5_1_geom_style.py --revert --apply
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase5_1'

SENTINEL = '// Phase 5.1: yaw fix (-sin) + lighter style'
PHASE5_SENTINEL = '// ── Phase 5: cams + frustums on map ───────────────────────────────────'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: tweak frustum/marker styles to be lighter
#   - frustum opacity: .35 → .08 (very subtle fill)
#   - marker stroke-width when selected: 120 → 60
#   - cam-marker hover: stroke-width 80 → 40
# Also reduce the marker radius default in the JS (HUNK 3 below).
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
#map-overlay{pointer-events:none}
#map-overlay .cam-marker{pointer-events:auto;cursor:pointer;transition:opacity .12s}
#map-overlay .cam-marker:hover circle{stroke-width:80}
#map-overlay .cam-frustum{pointer-events:none;opacity:.35;transition:opacity .15s}
#map-overlay .cam-marker.selected circle{stroke:var(--text);stroke-width:120}
#map-overlay .cam-marker.selected ~ .cam-frustum,
#map-overlay g.cam-group.selected .cam-frustum{opacity:.7}
#map-overlay .ray-line{stroke:var(--blue);stroke-width:30;opacity:.4;pointer-events:none}"""

HUNK_1_NEW = """\
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


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — JS: fix the yaw direction in frustumCornersWorld AND change
# the geometry: instead of fixed FRUSTUM_DIST, compute per-cam max distance
# from observed landmarks. Also restructure the rendering to draw the
# frustum as a fill polygon + two stroke lines (not a single filled
# triangle).
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
  // Frustum geometry: from cam apex (in world coords), the two edge rays
  // open at ±hfov/2 around yaw. In world XY (north-up), yaw=0 points +Y
  // (North) and yaw=90° points +X (East).
  // We extend the rays to a fixed distance D (in world units, ~= 1 GTA-meter
  // per unit on yanis). 1500 units = 1.5 km is enough to be visible at
  // typical map zooms without dominating.
  const FRUSTUM_DIST = 1500;

  function frustumCornersWorld(camXyz, yawDeg, hfovDeg) {
    const [wx, wy] = camXyz;
    const halfFov = hfovDeg / 2;
    const corners = [];
    for (const edgeYawDeg of [yawDeg - halfFov, yawDeg + halfFov]) {
      const r = edgeYawDeg * Math.PI / 180;
      // North-up: yaw 0 → +Y, yaw 90 → +X.
      const ex = wx + FRUSTUM_DIST * Math.sin(r);
      const ey = wy + FRUSTUM_DIST * Math.cos(r);
      corners.push([ex, ey]);
    }
    return corners;
  }"""

HUNK_2_NEW = """\
  // Phase 5.1: yaw fix (-sin) + lighter style
  // Frustum geometry — convention matches server.py /api/generate_map:
  //   end_x = cam_x - ray_len * sin(yaw)
  //   end_y = cam_y + ray_len * cos(yaw)
  // i.e. yaw=0° points +Y (North), yaw=90° points -X (West in world coords).
  // The sin is NEGATED — that's the fix vs Phase 5 v1 which used +sin and
  // produced frustums pointing 180° opposite.
  // Extension distance: the farthest landmark observed by this cam. This
  // makes the frustum length self-consistent with the cam's actual coverage,
  // and matches what /api/generate_map renders. Clamped to [600, 4000].
  const FRUSTUM_DIST_DEFAULT = 1500;
  const FRUSTUM_DIST_MIN = 600;
  const FRUSTUM_DIST_MAX = 4000;

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
  }

  function frustumCornersWorld(camXyz, yawDeg, hfovDeg, dist) {
    const [wx, wy] = camXyz;
    const halfFov = hfovDeg / 2;
    const corners = [];
    for (const edgeYawDeg of [yawDeg - halfFov, yawDeg + halfFov]) {
      const r = edgeYawDeg * Math.PI / 180;
      // Match server.py: -sin for x, +cos for y.
      const ex = wx - dist * Math.sin(r);
      const ey = wy + dist * Math.cos(r);
      corners.push([ex, ey]);
    }
    return corners;
  }"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — JS: rewrite the per-cam DOM building block to match the new
# style (apex circle smaller, FOV as 2 lines + a fill polygon underneath).
#
# Anchor: the existing per-cam DOM block.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
  const MARKER_RADIUS = 60;
  const MARKER_STROKE = 30;"""

HUNK_3_NEW = """\
  // Phase 5.1: smaller markers, thinner outlines
  const MARKER_RADIUS = 35;
  const MARKER_STROKE = 12;
  const FRUSTUM_LINE_WIDTH = 12;"""


HUNK_4_OLD = """\
    for (const c of window.mapData.cameras) {
      if (!c.xyz) continue;  // shouldn't happen since /api/map_data filters
      const type = getCamTypeForMap(c);
      const color = CAM_COLORS[type] || '#a78bfa';
      const [sx, sy] = window.worldToSvg(c.xyz[0], c.xyz[1]);

      // Frustum triangle. We need yaw and hfov from the cam record.
      // ypr is [yaw, pitch, roll] in degrees per the existing API.
      const yaw = (c.ypr && c.ypr.length >= 1) ? c.ypr[0] : 0;
      const hfov = c.hfov || 60;
      const fcWorld = frustumCornersWorld(c.xyz, yaw, hfov);
      const fcSvg = fcWorld.map(([wx, wy]) => window.worldToSvg(wx, wy));

      const camGroup = document.createElementNS(SVG_NS, 'g');
      camGroup.setAttribute('class', 'cam-group');
      camGroup.dataset.camName = c.name;

      // Frustum polygon: apex + two edge corners.
      const frustum = document.createElementNS(SVG_NS, 'polygon');
      frustum.setAttribute('class', 'cam-frustum');
      frustum.setAttribute('points',
        `${sx},${sy} ${fcSvg[0][0]},${fcSvg[0][1]} ${fcSvg[1][0]},${fcSvg[1][1]}`);
      frustum.setAttribute('fill', color);
      camGroup.appendChild(frustum);

      // Apex circle (the marker proper).
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
      camGroup.appendChild(marker);

      camsGroup.appendChild(camGroup);
    }"""

HUNK_4_NEW = """\
    for (const c of window.mapData.cameras) {
      if (!c.xyz) continue;  // shouldn't happen since /api/map_data filters
      const type = getCamTypeForMap(c);
      const color = CAM_COLORS[type] || '#a78bfa';
      const [sx, sy] = window.worldToSvg(c.xyz[0], c.xyz[1]);

      // Phase 5.1: per-cam frustum length = farthest observed landmark.
      const yaw = (c.ypr && c.ypr.length >= 1) ? c.ypr[0] : 0;
      const hfov = c.hfov || 60;
      const dist = frustumDistanceForCam(c);
      const fcWorld = frustumCornersWorld(c.xyz, yaw, hfov, dist);
      const fcSvg = fcWorld.map(([wx, wy]) => window.worldToSvg(wx, wy));

      const camGroup = document.createElementNS(SVG_NS, 'g');
      camGroup.setAttribute('class', 'cam-group');
      camGroup.dataset.camName = c.name;

      // Frustum fill (very light triangle between apex and the two edges).
      const fill = document.createElementNS(SVG_NS, 'polygon');
      fill.setAttribute('class', 'cam-frustum-fill');
      fill.setAttribute('points',
        `${sx},${sy} ${fcSvg[0][0]},${fcSvg[0][1]} ${fcSvg[1][0]},${fcSvg[1][1]}`);
      fill.setAttribute('fill', color);
      camGroup.appendChild(fill);

      // Two FOV edge lines (the "frustum" proper, like generate_map).
      for (let i = 0; i < 2; i++) {
        const line = document.createElementNS(SVG_NS, 'line');
        line.setAttribute('class', 'cam-frustum');
        line.setAttribute('x1', String(sx));
        line.setAttribute('y1', String(sy));
        line.setAttribute('x2', String(fcSvg[i][0]));
        line.setAttribute('y2', String(fcSvg[i][1]));
        line.setAttribute('stroke', color);
        line.setAttribute('stroke-width', String(FRUSTUM_LINE_WIDTH));
        line.setAttribute('stroke-linecap', 'round');
        camGroup.appendChild(line);
      }

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
      camGroup.appendChild(marker);

      camsGroup.appendChild(camGroup);
    }"""


HUNKS = [
    ('1 (CSS: lighter frustum + smaller selected stroke + fill class)', HUNK_1_OLD, HUNK_1_NEW),
    ('2 (JS: yaw -sin fix + per-cam frustum length)', HUNK_2_OLD, HUNK_2_NEW),
    ('3 (JS: smaller marker constants)', HUNK_3_OLD, HUNK_3_NEW),
    ('4 (JS: rewrite per-cam DOM with fill + edge lines + apex)', HUNK_4_OLD, HUNK_4_NEW),
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

    if PHASE5_SENTINEL not in src:
        print('ERROR: Phase 5 sentinel not found. Apply patch_svg_phase5.py first.')
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
    print('  - Frustums should now point in the correct direction.')
    print('  - Style: smaller apex dot + 2 thin FOV edge lines + very light fill')
    print('  - Per-cam frustum length = farthest observed landmark')


if __name__ == '__main__':
    main()
