#!/usr/bin/env python3
"""
patch_svg_phase7a_1_2_minimap_img.py — minimap: <div bg-image> → <img> + transform

Phase 7a.1 used `background-image: url('/yanis.png')` on a <div> with
JS-set `background-position` and `background-size` to crop. Functional,
but on Safari + macOS the 12000×12000 PNG (~1.4 GB decoded) hits a slow
path: 30-60s before the minimap renders, even though the PNG itself
loads in <50ms (verified with `new Image()` benchmark).

Switching to a real <img> element + CSS transform-based pan/zoom uses
Safari's optimized image rendering pipeline. Net effect: minimap shows
up instantly on first cam selection.

The math is identical to Phase 7a.1's CSS-position approach, just
expressed as `transform: translate(...) scale(...)` instead of
`background-position` + `background-size`. The translate is the
inverse of where we want the cam pixel to land.

Idempotent. Builds on Phase 7a.1.1.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase7a_1_2'

SENTINEL = '/* Phase 7a.1.2: minimap <img>+transform instead of bg-image */'
PHASE7A_1_1_SENTINEL = '/* Phase 7a.1.1: minimap grayscale + cam preview click + PNG preload */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: replace #minimap-img-sb rule. The new rule is for an <img>,
# so it doesn't need background-* properties.
# Anchor: the existing #minimap-img-sb rule with the Phase 7a.1.1 grayscale
# filter line.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
#minimap-img-sb{position:absolute;inset:0;
  background-image:url('/yanis.png');
  background-repeat:no-repeat;
  /* JS sets background-position and background-size per cam */
  background-color:#222;
  /* Phase 7a.1.1: match Map view's grayscale treatment so the
     minimap matches the main map visually. */
  filter:grayscale(1) brightness(1.05) contrast(1.1)}"""

HUNK_1_NEW = """\
/* Phase 7a.1.2: <img>+transform instead of <div> background-image —
   Safari decodes the 12K PNG far faster as an <img> than as a CSS
   background. JS sets transform-origin: 0 0 + translate+scale per cam. */
#minimap-img-sb{position:absolute;left:0;top:0;
  /* Native size of the PNG. JS scales via transform; this is the
     base box that the transform operates on. */
  width:12000px;height:12000px;
  transform-origin:0 0;
  user-select:none;-webkit-user-drag:none;pointer-events:none;
  background:#222;
  /* Match Map view's grayscale treatment. */
  filter:grayscale(1) brightness(1.05) contrast(1.1)}"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — HTML: change the inner #minimap-img-sb from <div> to <img>.
# Anchor: the existing <div id="minimap-img-sb"></div>.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
        <div id="minimap-rotator-sb">
          <div id="minimap-img-sb"></div>
        </div>"""

HUNK_2_NEW = """\
        <div id="minimap-rotator-sb">
          <!-- Phase 7a.1.2: <img> instead of <div> bg-image (Safari perf) -->
          <img id="minimap-img-sb" src="/yanis.png" alt="">
        </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — JS: rewrite updateMinimap() to use transform on the <img>.
# Anchor: the entire current updateMinimap() body.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
function updateMinimap() {
  if (!minimapEnabled) {
    minimapWrap.style.display = 'none';
    return;
  }
  if (!currentCam || !camData?.xyz || !window.mapTransform) {
    minimapWrap.style.display = 'block';
    minimapBg.style.backgroundImage = 'none';  // empty
    return;
  }
  const [pxCx, pxCy] = window.worldToSvg(camData.xyz[0], camData.xyz[1]);
  const sz = window.mapTransform.svg_size;  // [w, h] of the PNG in px
  // Rotator is 480 CSS px wide (200% of 240). We want `2*MINIMAP_RADIUS`
  // map-units to span 480 CSS px ⇒ scale = 480 / (2*MINIMAP_RADIUS).
  const rotW = 480, rotH = 340;
  const scale = rotW / (2 * MINIMAP_RADIUS);
  const bgW = sz[0] * scale;
  const bgH = sz[1] * scale;
  // Background-position: we want the cam pixel to land at the rotator
  // center (rotW/2, rotH/2). Background-position is the offset of the
  // image's TOP-LEFT corner. So image_top_left = center - cam_px.
  const bgX = (rotW / 2) - (pxCx * scale);
  const bgY = (rotH / 2) - (pxCy * scale);
  minimapBg.style.backgroundImage = "url('/yanis.png')";
  minimapBg.style.backgroundSize = `${bgW}px ${bgH}px`;
  minimapBg.style.backgroundPosition = `${bgX}px ${bgY}px`;
  // Rotate so cam direction (yaw) points UP. Yaw 0 = north.
  const yaw = (camData.ypr && camData.ypr.length >= 1) ? camData.ypr[0] : 0;
  minimapRotator.style.transform = `rotate(${-yaw}deg)`;
  minimapWrap.style.display = 'block';
}
window.updateMinimap = updateMinimap;"""

HUNK_3_NEW = """\
function updateMinimap() {
  if (!minimapEnabled) {
    minimapWrap.style.display = 'none';
    return;
  }
  if (!currentCam || !camData?.xyz || !window.mapTransform) {
    minimapWrap.style.display = 'block';
    // Park the image off-screen so we don't show a misplaced map.
    minimapBg.style.transform = 'translate(-99999px, -99999px)';
    return;
  }
  // Phase 7a.1.2: transform-based crop on a real <img>. Same math as
  // the prior background-position approach, expressed as transform.
  const [pxCx, pxCy] = window.worldToSvg(camData.xyz[0], camData.xyz[1]);
  // Rotator is 480 CSS px wide (200% of the 240px slot). We want
  // `2*MINIMAP_RADIUS` map-units to span 480 CSS px ⇒
  // scale = 480 / (2*MINIMAP_RADIUS).
  const rotW = 480, rotH = 340;
  const scale = rotW / (2 * MINIMAP_RADIUS);
  // The <img> has its native size in CSS (12000×12000) and
  // transform-origin: 0 0. We want the cam pixel to land at
  // (rotW/2, rotH/2) of the rotator. Translate first, then scale,
  // so order of operations: scale around (0,0), then translate.
  // CSS transforms apply right-to-left, so write: translate(...) scale(...).
  const tx = (rotW / 2) - (pxCx * scale);
  const ty = (rotH / 2) - (pxCy * scale);
  minimapBg.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
  // Rotate so cam direction (yaw) points UP. Yaw 0 = north.
  const yaw = (camData.ypr && camData.ypr.length >= 1) ? camData.ypr[0] : 0;
  minimapRotator.style.transform = `rotate(${-yaw}deg)`;
  minimapWrap.style.display = 'block';
}
window.updateMinimap = updateMinimap;"""


HUNKS = [
    ('CSS — minimap-img-sb as <img> styling',          HUNK_1_OLD, HUNK_1_NEW),
    ('HTML — <div id="minimap-img-sb"> → <img>',       HUNK_2_OLD, HUNK_2_NEW),
    ('JS — updateMinimap uses transform on <img>',      HUNK_3_OLD, HUNK_3_NEW),
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

    if PHASE7A_1_1_SENTINEL not in src:
        print('ERROR: Phase 7a.1.1 sentinel not found.')
        sys.exit(1)

    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} times (need exactly 1).')
            sys.exit(1)

    new_src = src
    for _label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    new_src = new_src.replace(PHASE7A_1_1_SENTINEL,
                              PHASE7A_1_1_SENTINEL + '\n' + SENTINEL,
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
    print('Test: hard reload (Cmd+Shift+R), select a cam.')
    print('  - Minimap should appear within 100ms (vs 30-60s before).')
    print('  - Same crop, same yaw rotation, same grayscale.')


if __name__ == '__main__':
    main()
