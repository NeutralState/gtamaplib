#!/usr/bin/env python3
"""
patch_item4_cursor_preview.py — Revert the image-in-cone rendering and
replace it with a preview thumbnail that follows the cursor on hover.

Changes :
  - Remove the in-cone image draw (was laggy + visually busy)
  - Remove _ocDrawImageInQuad / _ocDrawTriangle helpers (no longer needed)
  - Restore the simple cone outline (lines only) for all visible cones
  - On hover: show a 240px preview thumbnail next to the cursor (adaptive
    side so it doesn't go off-screen)

Run from repo root :
    python3 patch_item4_cursor_preview.py             # dry-run
    python3 patch_item4_cursor_preview.py --apply
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
        shutil.copy(path, path + '.bak_cursor_preview')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


# ── Patch 1: remove the in-cone image draw block (replace with nothing) ────

CALIB_OLD_INCONE = '''    // Draw the image in the bounding box of the quad (simple, robust).
    const img = _ocImgCache.get(cone.name);
    if (img && img.naturalWidth > 0) {
      const xs = corners.map(c => c[0]);
      const ys = corners.map(c => c[1]);
      const bx = Math.min(...xs);
      const by = Math.min(...ys);
      const bw = Math.max(...xs) - bx;
      const bh = Math.max(...ys) - by;
      if (bw > 4 && bh > 4) {
        ctx.save();
        // Clip to quad shape so image stays inside the cone outline
        ctx.beginPath();
        ctx.moveTo(corners[0][0], corners[0][1]);
        for (let j = 1; j < 4; j++) ctx.lineTo(corners[j][0], corners[j][1]);
        ctx.closePath();
        ctx.clip();
        ctx.drawImage(img, bx, by, bw, bh);
        ctx.restore();
      }
    }

    // Draw frustum lines on top of the image
    ctx.strokeStyle = stroke;
    ctx.lineWidth = isHover ? 3 : 1.5;'''

CALIB_NEW_INCONE = '''    // Draw frustum lines (image preview now shown next to cursor on hover)
    ctx.strokeStyle = stroke;
    ctx.lineWidth = isHover ? 3 : 1.5;'''


# ── Patch 2: simplify the image cache — only loaded on hover, not preloaded ──

CALIB_OLD_PRELOAD = '''  // Preload images for all visible cones
  for (const cone of otherCones) _ocPreloadImg(cone.name);

  for (let i = 0; i < otherCones.length; i++) {'''

CALIB_NEW_PRELOAD = '''  for (let i = 0; i < otherCones.length; i++) {'''


# ── Patch 3: add cursor-following preview element + handlers ──

# Find the canvas-wrap close tag (we already added oc-toggle-btn there)
CALIB_OLD_BTN = '''    <button id="oc-toggle-btn" title="Toggle other cams overlay (O)"
      style="position:absolute;top:8px;right:8px;z-index:10;
             background:rgba(0,0,0,0.6);color:#fff;border:1px solid #555;
             border-radius:4px;padding:4px 8px;font-size:11px;cursor:pointer;
             font-family:JetBrains Mono,monospace">⊕ cams</button>
  </div>'''

CALIB_NEW_BTN = '''    <button id="oc-toggle-btn" title="Toggle other cams overlay (O)"
      style="position:absolute;top:8px;right:8px;z-index:10;
             background:rgba(0,0,0,0.6);color:#fff;border:1px solid #555;
             border-radius:4px;padding:4px 8px;font-size:11px;cursor:pointer;
             font-family:JetBrains Mono,monospace">⊕ cams</button>
    <div id="oc-cursor-preview" style="position:fixed;display:none;z-index:100;
        width:240px;background:rgba(0,0,0,0.92);border:1px solid #888;
        border-radius:6px;padding:6px;pointer-events:none;
        font-family:JetBrains Mono,monospace;color:#fff;font-size:11px;
        box-shadow:0 4px 16px rgba(0,0,0,0.6)">
      <div id="oc-cursor-name" style="margin-bottom:4px;font-weight:bold;
        white-space:nowrap;overflow:hidden;text-overflow:ellipsis"></div>
      <img id="oc-cursor-img" src="" style="width:100%;display:block;
        border-radius:3px;background:#222;min-height:60px">
      <div id="oc-cursor-meta" style="margin-top:4px;color:#aaa"></div>
    </div>
  </div>'''


# ── Patch 4: replace mousemove handler to position the cursor preview ──

CALIB_OLD_MOUSEMOVE = '''canvasWrap.addEventListener('mousemove', e => {
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

CALIB_NEW_MOUSEMOVE = '''const ocCursorPreview = document.getElementById('oc-cursor-preview');
const ocCursorName = document.getElementById('oc-cursor-name');
const ocCursorImg = document.getElementById('oc-cursor-img');
const ocCursorMeta = document.getElementById('oc-cursor-meta');
let _ocCursorLastCam = null;

function _ocPositionPreview(clientX, clientY) {
  // Adaptive placement: pick the side of the cursor that doesn't overflow.
  const PREVIEW_W = 240;
  const PREVIEW_H = ocCursorPreview.offsetHeight || 200;
  const PAD = 14;
  const winW = window.innerWidth;
  const winH = window.innerHeight;

  let left = clientX + PAD;
  let top = clientY + PAD;
  if (left + PREVIEW_W > winW - 8) left = clientX - PREVIEW_W - PAD;
  if (top + PREVIEW_H > winH - 8) top = clientY - PREVIEW_H - PAD;
  if (left < 8) left = 8;
  if (top < 8) top = 8;

  ocCursorPreview.style.left = left + 'px';
  ocCursorPreview.style.top = top + 'px';
}

function _ocShowCursorPreview(coneIdx, clientX, clientY) {
  if (coneIdx === null) {
    ocCursorPreview.style.display = 'none';
    _ocCursorLastCam = null;
    return;
  }
  const cone = otherCones[coneIdx];
  if (_ocCursorLastCam !== cone.name) {
    _ocCursorLastCam = cone.name;
    ocCursorName.textContent = cone.name;
    ocCursorMeta.textContent = `${cone.type} · ${cone.dist_m}m`;
    ocCursorImg.style.display = 'block';
    ocCursorImg.src = `/frame/${encodeURIComponent(cone.name)}`;
    ocCursorImg.onerror = () => {
      ocCursorImg.style.display = 'none';
      ocCursorMeta.textContent = `${cone.type} · ${cone.dist_m}m · (no image)`;
    };
  }
  ocCursorPreview.style.display = 'block';
  _ocPositionPreview(clientX, clientY);
}

canvasWrap.addEventListener('mousemove', e => {
  if (!otherCones.length) {
    if (hoveredCone !== null) {
      hoveredCone = null;
      _ocShowCursorPreview(null);
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
    _ocShowCursorPreview(hit, e.clientX, e.clientY);
    draw();
  } else if (hit !== null) {
    // Update position even when hovering same cone (smooth tracking)
    _ocPositionPreview(e.clientX, e.clientY);
  }
});

canvasWrap.addEventListener('mouseleave', () => {
  if (hoveredCone !== null) {
    hoveredCone = null;
    _ocShowCursorPreview(null);
    draw();
  }
});'''


if not args.apply:
    print("═══════════════════════════════════════════════════════════════")
    print("  DRY-RUN")
    print("═══════════════════════════════════════════════════════════════\n")

print("── Patch tools/calib.html ──")
res = patch_file(CALIB_PATH, [
    (CALIB_OLD_INCONE,    CALIB_NEW_INCONE),
    (CALIB_OLD_PRELOAD,   CALIB_NEW_PRELOAD),
    (CALIB_OLD_BTN,       CALIB_NEW_BTN),
    (CALIB_OLD_MOUSEMOVE, CALIB_NEW_MOUSEMOVE),
], marker_already_applied='oc-cursor-preview')
print(f"  → {res}")

print()
if res.startswith('error'):
    sys.exit(1)
elif args.apply:
    print("✓ Patch appliqué")
    print("\n  Hard refresh http://localhost:8765/calib.html (Cmd+Shift+R)")
    print("  Pas besoin de restart server.")
else:
    print("Lance avec --apply pour exécuter.")
