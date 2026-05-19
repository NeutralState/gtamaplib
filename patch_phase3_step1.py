"""
Phase 3 Step 1 — Add tile canvas renderer to calib.html.

Approach (conservative, dual-rendering):
- Keeps existing <img src="/yanis.jpg"> intact (still visible by default)
- Adds <canvas id="map-tile-canvas"> as a sibling of .map-svg-wrap inside .map-view
- Canvas is viewport-sized (CSS inset:0), gets its own pan/zoom view derived from window.mapTx
- A keyboard shortcut 'T' toggles canvas visibility (for visual comparison vs. <img>)
- A 'Tiles' button in the controls area (next to Rays/Heat) lets the user switch render mode

If validation passes (canvas matches img position 1:1 on cams/LMs), we'll
remove the <img> layer in Phase 4.

Idempotent: re-running this script is safe (uses unique markers, exits if already applied).
"""

import os
import sys

CALIB_PATH = os.path.expanduser('~/Downloads/gtamaplib-main/tools/calib.html')
BAK_PATH = CALIB_PATH + '.bak_phase3_step1'

with open(CALIB_PATH) as f:
    c = f.read()

if '[TILES-V1-CANVAS]' in c:
    print('Already patched — skipping. Use the .bak file to revert if needed.')
    sys.exit(0)

# Backup
with open(BAK_PATH, 'w') as f:
    f.write(c)
print(f'Backup written: {BAK_PATH}')

# ─── PATCH 1: CSS for the new canvas ──────────────────────────────────────
# Add CSS for #map-tile-canvas right after the existing .map-png-wrap rules
css_anchor = '.map-png-wrap > img{display:block;\n  filter:grayscale(1) brightness(1.05) contrast(1.1);\n  user-select:none;-webkit-user-drag:none;pointer-events:none}'

css_addition = '''.map-png-wrap > img{display:block;
  filter:grayscale(1) brightness(1.05) contrast(1.1);
  user-select:none;-webkit-user-drag:none;pointer-events:none}

/* [TILES-V1-CANVAS] tile renderer canvas — sibling of .map-svg-wrap.
   Sits BEHIND the SVG overlay, fills the .map-view viewport directly.
   No CSS transform applied — pan/zoom is rendered internally via view state. */
.map-tile-canvas{position:absolute;inset:0;width:100%;height:100%;
  pointer-events:none;
  filter:grayscale(1) brightness(1.05) contrast(1.1);
  display:none}  /* hidden by default until user enables it via Tiles button */
body.tiles-on .map-tile-canvas{display:block}
body.tiles-on .map-png-wrap{display:none}  /* hide the legacy <img> when tiles on */'''

if css_anchor not in c:
    print('ERROR: CSS anchor not found')
    sys.exit(1)
c = c.replace(css_anchor, css_addition, 1)
print('Patch 1/4: CSS added')

# ─── PATCH 2: HTML — add <canvas> element inside .map-view ────────────────
html_anchor = '<div class="map-svg-wrap" id="map-svg-wrap"></div>'
html_addition = '''<!-- [TILES-V1-CANVAS] tile renderer behind the SVG overlay -->
    <canvas class="map-tile-canvas" id="map-tile-canvas"></canvas>
    <div class="map-svg-wrap" id="map-svg-wrap"></div>'''

if html_anchor not in c:
    print('ERROR: HTML anchor not found')
    sys.exit(1)
c = c.replace(html_anchor, html_addition, 1)
print('Patch 2/4: <canvas> element inserted')

# ─── PATCH 3: button in the toolbar (next to Rays/Heat) ───────────────────
btn_anchor = '<button class="heat-toggle" id="heat-toggle" title="Show loss landscape for the selected cam (heat map)">Heat</button>'
btn_addition = btn_anchor + '''
  <!-- [TILES-V1-CANVAS] Toggle between legacy yanis.jpg and tile renderer -->
  <button class="heat-toggle" id="tiles-toggle" title="Use tile renderer (canvas) instead of the legacy yanis.jpg">Tiles</button>'''

if btn_anchor not in c:
    print('ERROR: Heat button anchor not found')
    sys.exit(1)
c = c.replace(btn_anchor, btn_addition, 1)
print('Patch 3/4: Tiles button added')

# ─── PATCH 4: JS — tile renderer init + sync with mapTx ───────────────────
# Inject after applyMapTx() definition. We hook into it so every pan/zoom
# re-renders the canvas.

js_anchor = '''  function applyMapTx() {
    if (!window.mapTx) return;
    const { scale, tx, ty } = window.mapTx;
    const t = `translate(${tx}px, ${ty}px) scale(${scale})`;
    // Phase 5.4: set transform on each layer wrapper independently. Each
    // is its own GPU compositing layer (see CSS), so they stay in sync
    // visually but never invalidate each other on overlay class toggles.
    if (window.mapPngWrap)     window.mapPngWrap.style.transform = t;
    if (window.mapOverlayWrap) window.mapOverlayWrap.style.transform = t;
    updateDotSizes();
  }'''

js_addition = '''  function applyMapTx() {
    if (!window.mapTx) return;
    const { scale, tx, ty } = window.mapTx;
    const t = `translate(${tx}px, ${ty}px) scale(${scale})`;
    // Phase 5.4: set transform on each layer wrapper independently. Each
    // is its own GPU compositing layer (see CSS), so they stay in sync
    // visually but never invalidate each other on overlay class toggles.
    if (window.mapPngWrap)     window.mapPngWrap.style.transform = t;
    if (window.mapOverlayWrap) window.mapOverlayWrap.style.transform = t;
    updateDotSizes();
    // [TILES-V1-CANVAS] also re-render the tile canvas if active
    if (window.tilesRender) window.tilesRender();
  }

  // [TILES-V1-CANVAS] Tile renderer state & functions ─────────────────────
  //
  // Renders the rlx gtadb.org tile pyramid into a canvas that sits behind
  // the SVG overlay. The canvas is viewport-sized; pan/zoom is rendered
  // internally via a derived view state (centerX, centerY, zoom in world coords).
  //
  // Coord conversion:
  //   - .map-overlay-wrap has CSS transform: translate(tx,ty) scale(s)
  //     where (tx,ty) is in screen px and s is the SVG-to-screen scale.
  //   - SVG point (x,y) renders at screen (tx + x*s, ty + y*s).
  //   - Screen center is (rect.w/2, rect.h/2), so SVG center =
  //       ((rect.w/2 - tx)/s, (rect.h/2 - ty)/s)
  //   - SVG → world: see svgToWorld(). With y_sign=-1:
  //       world_x = svg_x - world_offset[0]
  //       world_y = -(svg_y - world_offset[1]) = world_offset[1] - svg_y
  //   - Tile zoom level: 1 SVG unit ≈ 1 meter (no world_scale). So
  //     meters per screen pixel = 1/s, and rlx formula gives:
  //       zoom = log2(MAP_W / (1024 * (1/s))) = log2(32 * s)
  //   - At s=1 (no zoom), zoom = log2(32) = 5.
  //
  // Tile coord constants (verbatim from rlx ui/map.js).
  const TILES_MAP_W = 32768;
  const TILES_ZERO_X = 16384;
  const TILES_ZERO_Y = 16384;
  const TILES_SIZE = 256;
  const TILES_MIN_Z = 0;
  const TILES_MAX_Z = 6;
  const TILES_RANGES = {
    0: [[0, 0], [2, 2]],
    1: [[0, 1], [4, 5]],
    2: [[0, 2], [9, 11]],
    3: [[0, 4], [19, 23]],
    4: [[0, 8], [38, 47]],
    5: [[0, 17], [77, 95]],
    6: [[0, 34], [155, 190]],
  };
  window.tilesCache = new Map();
  window.tilesPending = new Map();
  let tilesCanvas = null, tilesCtx = null;

  function tilesUrl(z, x, y)   { return `/tiles/${z}/${z},${y},${x}.jpg`; }
  function tilesKey(z, x, y)   { return `${z}/${y}/${x}`; }
  function tilesGet(z, x, y) {
    const k = tilesKey(z, x, y);
    if (window.tilesCache.has(k)) return window.tilesCache.get(k);
    const img = new Image();
    window.tilesCache.set(k, img);
    return img;
  }
  function tilesLoad(z, x, y) {
    const img = tilesGet(z, x, y);
    if (img.src) return img;
    const k = tilesKey(z, x, y);
    if (window.tilesPending.has(k)) return img;
    window.tilesPending.set(k, true);
    img.addEventListener('load',  () => { window.tilesPending.delete(k); requestAnimationFrame(window.tilesRender); }, { once: true });
    img.addEventListener('error', () => { window.tilesPending.delete(k); }, { once: true });
    img.src = tilesUrl(z, x, y);
    return img;
  }
  function tilesDrawParent(ctx, zInt, x, y, tx, ty, drawSize) {
    for (let pz = zInt - 1; pz >= Math.max(TILES_MIN_Z, zInt - 2); pz--) {
      const scale = Math.pow(2, zInt - pz);
      const px = Math.floor(x / scale);
      const py = Math.floor(y / scale);
      const [[x0, y0], [x1, y1]] = TILES_RANGES[pz];
      if (px < x0 || px > x1 || py < y0 || py > y1) continue;
      const img = tilesGet(pz, px, py);
      if (!img.complete || img.naturalWidth === 0) { tilesLoad(pz, px, py); continue; }
      const sSize = TILES_SIZE / scale;
      const sx = (x - px * scale) * sSize;
      const sy = (y - py * scale) * sSize;
      ctx.drawImage(img, sx, sy, sSize, sSize, Math.floor(tx), Math.floor(ty),
                    Math.ceil(tx + drawSize) - Math.floor(tx),
                    Math.ceil(ty + drawSize) - Math.floor(ty));
      return true;
    }
    return false;
  }

  // Render tiles for the current view derived from window.mapTx.
  window.tilesRender = function () {
    if (!document.body.classList.contains('tiles-on')) return;
    if (!tilesCanvas || !window.mapTx || !window.mapTransform) return;
    const rect = document.getElementById('map-view').getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const cssW = rect.width;
    const cssH = rect.height;
    // Match canvas resolution to screen.
    if (tilesCanvas.width !== Math.floor(cssW * dpr) || tilesCanvas.height !== Math.floor(cssH * dpr)) {
      tilesCanvas.width = Math.floor(cssW * dpr);
      tilesCanvas.height = Math.floor(cssH * dpr);
    }
    tilesCtx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Derive world center + tile zoom from window.mapTx.
    const { scale: s, tx, ty } = window.mapTx;
    // SVG point at screen center.
    const svgCx = (cssW / 2 - tx) / s;
    const svgCy = (cssH / 2 - ty) / s;
    // SVG → world via existing inverse transform.
    const t = window.mapTransform;
    const centerX = svgCx - t.world_offset[0];                  // world x
    const centerY = (svgCy - t.world_offset[1]) / t.y_sign;     // world y (y_sign=-1)

    // Tile zoom: 1 SVG unit ≈ 1 m (we confirmed in Phase 2), so m/screen-px = 1/s.
    // rlx: mppx = MAP_W / (1024 * 2^zoom)  ⇔  zoom = log2(MAP_W / 1024 / mppx) = log2(32 * s)
    const zoomReal = Math.log2(32 * s);
    const zoom = Math.min(TILES_MAX_Z, Math.max(TILES_MIN_Z, zoomReal));
    const zInt = Math.min(TILES_MAX_Z, Math.max(TILES_MIN_Z, Math.ceil(zoom)));
    const tileWorldPxFactor = (1024 * Math.pow(2, zoom)) / TILES_MAP_W;  // tile-pixels per world meter
    const cxPix = (centerX + TILES_ZERO_X) * tileWorldPxFactor;
    const cyPix = (TILES_ZERO_Y - centerY) * tileWorldPxFactor;
    const offX = cssW / 2 - cxPix;
    const offY = cssH / 2 - cyPix;
    const drawSize = TILES_SIZE * Math.pow(2, zoom - zInt);

    tilesCtx.fillStyle = '#0a0a0c';
    tilesCtx.fillRect(0, 0, cssW, cssH);

    const [[x0, y0], [x1, y1]] = TILES_RANGES[zInt];
    const minTx = Math.floor(-offX / drawSize);
    const maxTx = Math.ceil((cssW - offX) / drawSize);
    const minTy = Math.floor(-offY / drawSize);
    const maxTy = Math.ceil((cssH - offY) / drawSize);

    for (let yy = minTy; yy <= maxTy; yy++) {
      for (let xx = minTx; xx <= maxTx; xx++) {
        const dx = offX + xx * drawSize;
        const dy = offY + yy * drawSize;
        if (xx < x0 || xx > x1 || yy < y0 || yy > y1) continue;
        const img = tilesLoad(zInt, xx, yy);
        if (img.complete && img.naturalWidth > 0) {
          tilesCtx.drawImage(img, 0, 0, TILES_SIZE, TILES_SIZE,
                             Math.floor(dx), Math.floor(dy),
                             Math.ceil(dx + drawSize) - Math.floor(dx),
                             Math.ceil(dy + drawSize) - Math.floor(dy));
        } else {
          tilesDrawParent(tilesCtx, zInt, xx, yy, dx, dy, drawSize);
        }
      }
    }
  };

  // Toggle handler — wired up at end of script (where other toggles are wired).
  // Init canvas reference when DOM is ready (the canvas is in the static HTML).
  document.addEventListener('DOMContentLoaded', () => {
    tilesCanvas = document.getElementById('map-tile-canvas');
    if (tilesCanvas) tilesCtx = tilesCanvas.getContext('2d');
    const tilesBtn = document.getElementById('tiles-toggle');
    if (tilesBtn) {
      tilesBtn.addEventListener('click', () => {
        const on = !document.body.classList.contains('tiles-on');
        document.body.classList.toggle('tiles-on', on);
        tilesBtn.classList.toggle('active', on);
        if (on) window.tilesRender();
      });
    }
    // Re-render on window resize.
    window.addEventListener('resize', () => {
      if (document.body.classList.contains('tiles-on')) window.tilesRender();
    });
  });
  // ── end [TILES-V1-CANVAS] ─────────────────────────────────────────────'''

if js_anchor not in c:
    print('ERROR: applyMapTx anchor not found')
    sys.exit(1)
c = c.replace(js_anchor, js_addition, 1)
print('Patch 4/4: tile renderer JS injected')

with open(CALIB_PATH, 'w') as f:
    f.write(c)
print('\nAll patches applied successfully.')
print('Reload http://localhost:8765/ and click the new "Tiles" button in Map view.')
