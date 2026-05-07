#!/usr/bin/env python3
"""
patch_item4_hover_preview.py — Adds a preview thumbnail in the bottom-right
of the canvas when hovering over an other-cam frustum.

Run from repo root :
    python3 patch_item4_hover_preview.py             # dry-run
    python3 patch_item4_hover_preview.py --apply
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
    print("✗ Lance ce script depuis la racine de gtamaplib-main/")
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
        shutil.copy(path, path + '.bak_hover_preview')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


# Add preview img element in the canvas-wrap (right next to oc-toggle-btn)
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
    <div id="oc-preview" style="position:absolute;bottom:8px;right:8px;z-index:10;
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


# Update mousemove to show/hide the preview, and reset on mouseleave
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
});'''

CALIB_NEW_MOUSEMOVE = '''const ocPreview = document.getElementById('oc-preview');
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


# ── Apply patches ──
if not args.apply:
    print("═══════════════════════════════════════════════════════════════")
    print("  DRY-RUN — Lance avec --apply pour exécuter")
    print("═══════════════════════════════════════════════════════════════\n")

print("── Patch tools/calib.html ──")
res = patch_file(CALIB_PATH, [
    (CALIB_OLD_BTN, CALIB_NEW_BTN),
    (CALIB_OLD_MOUSEMOVE, CALIB_NEW_MOUSEMOVE),
], marker_already_applied='oc-preview-img')
print(f"  → {res}")

print()
if res.startswith('error'):
    sys.exit(1)
elif args.apply:
    print("✓ Patch appliqué")
    print("\n  Tests :")
    print("    1. Refresh http://localhost:8765/calib.html (Cmd+Shift+R)")
    print("    2. Hover over a frustum → preview thumbnail in bottom-right")
    print("    3. Move out → preview disappears")
else:
    print("Lance avec --apply pour exécuter.")
