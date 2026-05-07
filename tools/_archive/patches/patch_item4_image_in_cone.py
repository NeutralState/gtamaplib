#!/usr/bin/env python3
"""
patch_item4_image_in_cone.py — Render the other cam's image inside its
projected frustum quadrilateral (rlx's suggestion). Permanent display at
35% opacity, full opacity on hover. Auto-flip if the quad is inverted.

Removes the bottom-right preview panel (replaced by in-cone rendering).

Run from repo root :
    python3 patch_item4_image_in_cone.py             # dry-run
    python3 patch_item4_image_in_cone.py --apply
"""
import argparse
import os
import shutil
import sys

REPO_ROOT  = os.path.dirname(os.path.abspath(__file__))
CALIB_PATH = os.path.join(REPO_ROOT, 'tools', 'calib.html')

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

if not os.path.isfile(CALIB_PATH):
    print("✗ Lance depuis la racine de gtamaplib-main/")
    sys.exit(1)


def patch_file(path, replacements, marker_already_applied=None):
    with open(path) as f:
        content = f.read()
    if marker_already_applied and marker_already_applied in content:
        return 'already_patched'
    new_content = content
    for old, new in replacements:
        if old not in new_content:
            return f"error: pattern not found:\n{old[:200]}..."
        if new_content.count(old) > 1:
            return f"error: pattern found multiple times: {old[:100]}..."
        new_content = new_content.replace(old, new)
    if args.apply:
        shutil.copy(path, path + '.bak_image_in_cone')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


# ── 1. Remove the bottom-right preview panel (no longer needed) ─────────────

CALIB_OLD_PREVIEW_PANEL = '''    <div id="oc-preview" style="position:absolute;bottom:8px;right:8px;z-index:10;
        width:320px;background:rgba(0,0,0,0.85);border:1px solid #666;
        border-radius:6px;padding:6px;display:none;
        font-family:JetBrains Mono,monospace;color:#fff;font-size:11px">
      <div id="oc-preview-name" style="margin-bottom:4px;font-weight:bold;
        white-space:nowrap;overflow:hidden;text-overflow:ellipsis"></div>
      <img id="oc-preview-img" src="" style="width:100%;display:block;
        border-radius:3px;background:#222">
      <div id="oc-preview-meta" style="margin-top:4px;color:#aaa"></div>
    </div>
  </div>'''

CALIB_NEW_PREVIEW_PANEL = '''  </div>'''


# ── 2. Replace the draw() override with image-in-cone version ───────────────

CALIB_OLD_DRAW = '''// Hook into draw() to render cones on the canvas overlay.
const _origDraw = draw;
draw = function() {
  _origDraw();
  if (!otherCones.length) return;
  for (let i = 0; i < otherCones.length; i++) {
    const cone = otherCones[i];
    const isHover = hoveredCone === i;
    const [r, g, b] = cone.color;
    const stroke = `rgb(${r},${g},${b})`;
    ctx.strokeStyle = stroke;
    ctx.lineWidth = isHover ? 3 : 1.5;

    const [ax, ay] = toCanvas(cone.apex[0], cone.apex[1]);
    const corners = cone.corners.map(c => toCanvas(c[0], c[1]));

    // 4 lines apex → corners
    for (const [cx, cy] of corners) {
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(cx, cy);
      ctx.stroke();
    }
    // Rectangle of corners
    ctx.beginPath();
    for (let j = 0; j < 4; j++) {
      const [x1, y1] = corners[j];
      if (j === 0) ctx.moveTo(x1, y1);
      else ctx.lineTo(x1, y1);
    }
    ctx.closePath();
    ctx.stroke();

    // Label at apex on hover
    if (isHover) {
      ctx.font = 'bold 11px JetBrains Mono, monospace';
      const label = `${cone.name} · ${cone.dist_m}m`;
      const w = ctx.measureText(label).width;
      ctx.fillStyle = stroke;
      ctx.fillRect(ax + 6, ay - 14, w + 8, 16);
      ctx.fillStyle = '#fff';
      ctx.fillText(label, ax + 10, ay - 2);
    }
  }
};'''

CALIB_NEW_DRAW = '''// ── Image preload cache for in-cone rendering ─────────────────────────────
const _ocImgCache = new Map();    // cam_name → HTMLImageElement (loaded)
const _ocImgPending = new Map();  // cam_name → true (loading)

function _ocPreloadImg(camName) {
  if (_ocImgCache.has(camName) || _ocImgPending.has(camName)) return;
  _ocImgPending.set(camName, true);
  const img = new Image();
  img.onload = () => {
    _ocImgCache.set(camName, img);
    _ocImgPending.delete(camName);
    draw();  // re-draw now that image is ready
  };
  img.onerror = () => {
    _ocImgPending.delete(camName);
    _ocImgCache.set(camName, null);  // mark as failed (no image)
  };
  img.src = `/frame/${encodeURIComponent(camName)}`;
}

// Sign of the quadrilateral (positive = counter-clockwise = "front-facing")
function _ocQuadSign(corners) {
  // Shoelace formula on first 3 points is enough to detect flip
  const [a, b, c] = corners;
  return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
}

// Draw an image into a quadrilateral by splitting into 2 triangles.
// quad = [[x,y]x4] in canvas coords, in order TL, TR, BR, BL of the source img.
function _ocDrawImageInQuad(img, quad, alpha) {
  if (!img || !img.width) return;
  const w = img.width, h = img.height;
  const [tl, tr, br, bl] = quad;
  ctx.save();
  ctx.globalAlpha = alpha;

  // Triangle 1: TL, TR, BR  (source: 0,0 / w,0 / w,h)
  _ocDrawTriangle(img, [0, 0, w, 0, w, h], [...tl, ...tr, ...br]);
  // Triangle 2: TL, BR, BL  (source: 0,0 / w,h / 0,h)
  _ocDrawTriangle(img, [0, 0, w, h, 0, h], [...tl, ...br, ...bl]);

  ctx.restore();
}

function _ocDrawTriangle(img, src, dst) {
  // src = [sx0,sy0,sx1,sy1,sx2,sy2], dst = [dx0,dy0,dx1,dy1,dx2,dy2]
  const [sx0, sy0, sx1, sy1, sx2, sy2] = src;
  const [dx0, dy0, dx1, dy1, dx2, dy2] = dst;

  // Solve affine transform that maps (sx,sy) → (dx,dy) for the 3 vertices.
  // Returns matrix [a, b, c, d, e, f] for ctx.transform(a,b,c,d,e,f) which means
  //   x' = a*x + c*y + e
  //   y' = b*x + d*y + f
  const denom = sx0 * (sy2 - sy1) + sx1 * (sy0 - sy2) + sx2 * (sy1 - sy0);
  if (Math.abs(denom) < 1e-9) return;
  const a = (dx0 * (sy2 - sy1) + dx1 * (sy0 - sy2) + dx2 * (sy1 - sy0)) / denom;
  const b = (dy0 * (sy2 - sy1) + dy1 * (sy0 - sy2) + dy2 * (sy1 - sy0)) / denom;
  const c = -(dx0 * (sx2 - sx1) + dx1 * (sx0 - sx2) + dx2 * (sx1 - sx0)) / denom;
  const d = -(dy0 * (sx2 - sx1) + dy1 * (sx0 - sx2) + dy2 * (sx1 - sx0)) / denom;
  const e = (dx0 * (sx1 * sy2 - sx2 * sy1) + dx1 * (sx2 * sy0 - sx0 * sy2) + dx2 * (sx0 * sy1 - sx1 * sy0)) / denom;
  const f = (dy0 * (sx1 * sy2 - sx2 * sy1) + dy1 * (sx2 * sy0 - sx0 * sy2) + dy2 * (sx0 * sy1 - sx1 * sy0)) / denom;

  ctx.save();
  // Clip to triangle
  ctx.beginPath();
  ctx.moveTo(dx0, dy0);
  ctx.lineTo(dx1, dy1);
  ctx.lineTo(dx2, dy2);
  ctx.closePath();
  ctx.clip();
  // Apply transform and draw the full image (clipped to triangle)
  ctx.transform(a, b, c, d, e, f);
  ctx.drawImage(img, 0, 0);
  ctx.restore();
}

// Hook into draw() to render cones with image in the quad.
const _origDraw = draw;
draw = function() {
  _origDraw();
  if (!otherCones.length) return;

  // Preload images for all visible cones
  for (const cone of otherCones) _ocPreloadImg(cone.name);

  for (let i = 0; i < otherCones.length; i++) {
    const cone = otherCones[i];
    const isHover = hoveredCone === i;
    const [r, g, b] = cone.color;
    const stroke = `rgb(${r},${g},${b})`;

    const [ax, ay] = toCanvas(cone.apex[0], cone.apex[1]);
    let corners = cone.corners.map(c => toCanvas(c[0], c[1]));

    // Detect flipped (mirrored) quad and reorder if needed.
    // Corners come from server in order TL, TR, BR, BL of the source image.
    // If the projected quad has negative signed area, reverse it so the
    // image draws right-side-up (rlx's "flipped if needed").
    if (_ocQuadSign(corners) < 0) {
      corners = [corners[1], corners[0], corners[3], corners[2]];
    }

    // Draw the image inside the quad (if loaded), faded normally, full on hover
    const img = _ocImgCache.get(cone.name);
    if (img) {
      _ocDrawImageInQuad(img, corners, isHover ? 1.0 : 0.35);
    }

    // Draw frustum lines on top of the image
    ctx.strokeStyle = stroke;
    ctx.lineWidth = isHover ? 3 : 1.5;
    for (const [cx, cy] of corners) {
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(cx, cy);
      ctx.stroke();
    }
    ctx.beginPath();
    for (let j = 0; j < 4; j++) {
      const [x1, y1] = corners[j];
      if (j === 0) ctx.moveTo(x1, y1);
      else ctx.lineTo(x1, y1);
    }
    ctx.closePath();
    ctx.stroke();

    // Label at apex on hover
    if (isHover) {
      ctx.font = 'bold 11px JetBrains Mono, monospace';
      const label = `${cone.name} · ${cone.dist_m}m`;
      const w = ctx.measureText(label).width;
      ctx.fillStyle = stroke;
      ctx.fillRect(ax + 6, ay - 14, w + 8, 16);
      ctx.fillStyle = '#fff';
      ctx.fillText(label, ax + 10, ay - 2);
    }
  }
};'''


# ── 3. Simplify mousemove — no more preview panel to show/hide ──────────────

CALIB_OLD_MOUSEMOVE = '''const ocPreview = document.getElementById('oc-preview');
const ocPreviewName = document.getElementById('oc-preview-name');
const ocPreviewImg = document.getElementById('oc-preview-img');
const ocPreviewMeta = document.getElementById('oc-preview-meta');
let _ocPreviewLast = null;

function _ocShowPreview(coneIdx) {
  if (coneIdx === null) {
    ocPreview.style.display = 'none';
    _ocPreviewLast = null;
    return;
  }
  const cone = otherCones[coneIdx];
  if (_ocPreviewLast === cone.name) {
    ocPreview.style.display = 'block';
    return;
  }
  _ocPreviewLast = cone.name;
  ocPreviewName.textContent = cone.name;
  ocPreviewMeta.textContent = `${cone.type} · ${cone.dist_m}m`;
  ocPreviewImg.src = `/frame/${encodeURIComponent(cone.name)}`;
  ocPreviewImg.onerror = () => {
    ocPreviewImg.style.display = 'none';
    ocPreviewMeta.textContent = `${cone.type} · ${cone.dist_m}m · (no image)`;
  };
  ocPreviewImg.onload = () => { ocPreviewImg.style.display = 'block'; };
  ocPreview.style.display = 'block';
}

canvasWrap.addEventListener('mousemove', e => {
  if (!otherCones.length) {
    if (hoveredCone !== null) {
      hoveredCone = null;
      _ocShowPreview(null);
      draw();
    }
    return;
  }
  const rect = canvasWrap.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  const hit = _conesHitTest(mx, my);
  if (hit !== hoveredCone) {
    hoveredCone = hit;
    canvasWrap.style.cursor = (hit !== null) ? 'pointer' : '';
    _ocShowPreview(hit);
    draw();
  }
});

canvasWrap.addEventListener('mouseleave', () => {
  if (hoveredCone !== null) {
    hoveredCone = null;
    _ocShowPreview(null);
    draw();
  }
});'''

CALIB_NEW_MOUSEMOVE = '''canvasWrap.addEventListener('mousemove', e => {
  if (!otherCones.length) {
    if (hoveredCone !== null) { hoveredCone = null; draw(); }
    return;
  }
  const rect = canvasWrap.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  const hit = _conesHitTest(mx, my);
  if (hit !== hoveredCone) {
    hoveredCone = hit;
    canvasWrap.style.cursor = (hit !== null) ? 'pointer' : '';
    draw();
  }
});

canvasWrap.addEventListener('mouseleave', () => {
  if (hoveredCone !== null) { hoveredCone = null; draw(); }
});'''


# ── Apply ──
if not args.apply:
    print("═══════════════════════════════════════════════════════════════")
    print("  DRY-RUN — Lance avec --apply pour exécuter")
    print("═══════════════════════════════════════════════════════════════\n")

print("── Patch tools/calib.html ──")
res = patch_file(CALIB_PATH, [
    (CALIB_OLD_PREVIEW_PANEL, CALIB_NEW_PREVIEW_PANEL),
    (CALIB_OLD_DRAW,          CALIB_NEW_DRAW),
    (CALIB_OLD_MOUSEMOVE,     CALIB_NEW_MOUSEMOVE),
], marker_already_applied='_ocDrawImageInQuad')
print(f"  → {res}")

print()
if res.startswith('error'):
    sys.exit(1)
elif args.apply:
    print("✓ Patch appliqué")
    print("\n  Tests :")
    print("    1. Refresh hard http://localhost:8765/calib.html (Cmd+Shift+R)")
    print("    2. Pick a cam → frustums + image-in-cone at 35% opacity")
    print("    3. Hover → image becomes 100% opacity + label")
    print("    4. Click → navigate")
else:
    print("Lance avec --apply pour exécuter.")
