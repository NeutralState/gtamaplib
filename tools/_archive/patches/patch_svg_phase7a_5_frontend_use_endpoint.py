#!/usr/bin/env python3
"""
patch_svg_phase7a_5_frontend_use_endpoint.py — rewire minimap to use /api/minimap

Phase 7a.1's CSS-only minimap had to be reverted (Safari decode stall on
12K background-image). Phase 7a.4.1 restored the /api/minimap endpoint
(server-side render, disk cache, lazy on first hit). This patch rewires
the frontend back to that endpoint.

Net change: the minimap <img> is fed a base64 data URL from the server
(small ~50KB PNG, decodes instantly in Safari). The CSS transform-based
position math is gone — server already crops; we just display the result.

What stays:
  - Sidebar slot location (Phase 7a.1)
  - Cam preview swap in Map view (Phase 7a.1)
  - Click minimap → setView('map'), click cam preview → setView('camera')
  - 'M' shortcut for visibility toggle
  - Yaw rotation on the rotator wrapper

Idempotent. Builds on Phase 7a.1.2 (which is the current state).
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase7a_5'

SENTINEL = '/* Phase 7a.5: minimap fetches /api/minimap (revert CSS-only) */'
PHASE7A_1_2_SENTINEL = '/* Phase 7a.1.2: minimap <img>+transform instead of bg-image */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: revert the 12K-sized <img> + transform setup. The new <img>
# is the server-rendered 480×480 PNG, sized to fit the rotator
# (object-fit: cover so the slight aspect ratio diff is hidden).
# Anchor: the existing #minimap-img-sb rule from Phase 7a.1.2.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
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

HUNK_1_NEW = """\
/* Phase 7a.5: minimap is now a server-rendered 480x480 PNG fetched via
   /api/minimap. The <img> fills the rotator at native size; rotation
   is applied to the rotator wrapper (Phase 7a.1 layout). */
#minimap-img-sb{position:absolute;width:100%;height:100%;left:0;top:0;
  display:block;
  user-select:none;-webkit-user-drag:none;pointer-events:none;
  background:#222;object-fit:cover;
  /* Match Map view's grayscale treatment. */
  filter:grayscale(1) brightness(1.05) contrast(1.1)}"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — JS: replace updateMinimap() with a fetch-based version.
# Anchor: the entire current updateMinimap() body from Phase 7a.1.2.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
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

HUNK_2_NEW = """\
// Phase 7a.5: fetch from /api/minimap (server crops + caches on disk).
// Tracks an in-flight token to avoid race conditions when the user
// clicks through cams quickly.
let _minimapFetchToken = 0;
async function updateMinimap() {
  if (!minimapEnabled) {
    minimapWrap.style.display = 'none';
    return;
  }
  if (!currentCam) {
    minimapWrap.style.display = 'block';
    minimapBg.removeAttribute('src');
    return;
  }
  minimapWrap.style.display = 'block';
  const myToken = ++_minimapFetchToken;
  try {
    const res = await fetch('/api/minimap?cam=' + encodeURIComponent(currentCam));
    if (myToken !== _minimapFetchToken) return;  // newer request superseded
    if (!res.ok) {
      console.warn('minimap fetch status', res.status);
      return;
    }
    const data = await res.json();
    if (myToken !== _minimapFetchToken) return;
    if (data.error) {
      console.warn('minimap error', data.error);
      return;
    }
    minimapBg.src = 'data:image/png;base64,' + data.image_b64;
    // Rotate so cam direction (yaw) points UP. Yaw 0 = north.
    minimapRotator.style.transform = `rotate(${-data.yaw}deg)`;
  } catch (e) {
    if (myToken === _minimapFetchToken) {
      console.error('minimap fetch failed', e);
    }
  }
}
window.updateMinimap = updateMinimap;"""


HUNKS = [
    ('CSS — minimap-img-sb back to native-size <img>', HUNK_1_OLD, HUNK_1_NEW),
    ('JS — updateMinimap fetches /api/minimap',         HUNK_2_OLD, HUNK_2_NEW),
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

    if PHASE7A_1_2_SENTINEL not in src:
        print('ERROR: Phase 7a.1.2 sentinel not found.')
        sys.exit(1)

    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} times (need exactly 1).')
            sys.exit(1)

    new_src = src
    for _label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    new_src = new_src.replace(PHASE7A_1_2_SENTINEL,
                              PHASE7A_1_2_SENTINEL + '\n' + SENTINEL,
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
    print('  - First-cam click: ~1-2s while server renders+caches.')
    print('  - Subsequent clicks: instant (PNG already cached on disk).')
    print('  - Yaw rotation works as before; click → setView(map).')


if __name__ == '__main__':
    main()
