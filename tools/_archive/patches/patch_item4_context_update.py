#!/usr/bin/env python3
"""
patch_item4_context_update.py — Updates CLAUDE_CONTEXT.md to reflect:
  - Item 4 ✅ done (cone outlines + cursor preview)
  - Image-in-cone alternative kept in tools/_archive/patches/
    (in case we want to bring it back as an option later)
  - New session log entry
"""
import argparse
import os
import shutil
import sys

REPO_ROOT  = os.path.dirname(os.path.abspath(__file__))
CONTEXT_PATH = os.path.join(REPO_ROOT, 'tools', 'CLAUDE_CONTEXT.md')

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()


def read_file(path):
    with open(path) as f: return f.read()
def write_file(path, content):
    if args.apply:
        shutil.copy(path, path + '.bak_context_update')
        with open(path, 'w') as f: f.write(content)


# Find the item 4 line and mark it done
src = read_file(CONTEXT_PATH)

# ── Find item 4 line and mark done ──────────────────────────────────────────
# We look for several possible anchors (since the file has been edited a few times)
ITEM4_VARIANTS = [
    "4. **Display other cam cones on screenshot**",
    "4. Display other cam cones on screenshot",
    "**Display other cam cones on screenshot**",
    "Display other cam cones on screenshot",
    "Display other cams on screenshot",
    "display other cams",
    "render_camera",  # related landmark
]

found_anchor = None
for v in ITEM4_VARIANTS:
    if v in src:
        found_anchor = v
        break

if not found_anchor:
    print("⚠  No item 4 anchor found in CLAUDE_CONTEXT.md")
    print("    Will append a new session log entry only.")

# ── Compose the session log entry ──────────────────────────────────────────
SESSION_LOG = """
### 2026-05-07 (afternoon) — Item 4: other cam cones on screenshot

Implemented overlay of other cameras' projected frustums on the canvas
of calib.html, with click-to-navigate.

**Final design (shipped) :**
- `server.py` : endpoint `/api/other_cams_overlay` returns `apex` and 4
  `corners` pixel coords for each visible cam. Filters by type
  (leak/trailer/screenshot), max distance (5 km default), and excludes
  cones whose quad doesn't overlap the visible image.
- `calib.html` :
  - Cone outlines drawn on canvas overlay (lines only, no image fill)
  - Toggle button `⊕ cams` top-right of canvas + keyboard shortcut `O`
  - Hover shows 240 px preview thumbnail next to cursor (adaptive
    placement so it stays on-screen)
  - Click on cone navigates to that cam (via cam-picker dropdown)
  - Hooks into existing `draw()` and `toCanvas()` for zoom/pan compat

**Image-in-cone alternative :**
Tried rendering the actual image of each other cam *inside* its
projected quad (rlx's original suggestion). Worked technically but :
- Visually confusing on busy/dark scenes
- Significantly laggy with 20+ cams visible (20× perspective warps
  per draw, including on every mousemove)

Code preserved at `tools/_archive/patches/patch_item4_image_in_cone.py`
+ matrix-warp helpers `_ocDrawImageInQuad` / `_ocDrawTriangle`.
Could be reactivated as an opt-in mode (e.g. shift-click toggle) later.

Other archived experiments :
- `patch_item4_other_cams.py` : original v1, server-side image rendering
  (way too heavy)
- `patch_item4_v2_canvas_overlay.py` : v2 with sidebar panel (too cluttered)
- `patch_item4_v3_auto.py` : v3 auto-on without sidebar (kept the toggle btn)
- `patch_item4_hover_preview.py` : bottom-right preview panel (replaced
  by cursor preview in final version)
- `patch_item4_opacity_fix.py`, `patch_item4_skip_offscreen.py`,
  `patch_item4_tighten_filter.py`, `patch_item4_simple_bbox.py` :
  iterative fixes during the image-in-cone phase
- `patch_item4_cursor_preview.py` : final patch (rolled back image-in-cone,
  added cursor-following preview)

**Roadmap status :**
- Item 1 (z=0 flag) ✅
- Item 2 (precision flag for cams) ⏸ blocked on rlx clarification
- Item 3 (intersect_rays refactor) ⏸ pending
- Item 4 (other cam cones) ✅ shipped this session

**Next** : item 3 (intersect_rays) — function already exists in
gtamaplib.py line 2735, just needs wiring into `/api/triangulate`,
`retriangulate_landmark.py`, `batch_retriangulate_aiwe_fixed.py`.
"""

# ── Append to end of file ──────────────────────────────────────────────────
if "Item 4: other cam cones on screenshot" in src:
    print("Already updated — skipping.")
    sys.exit(0)

new_src = src.rstrip() + "\n" + SESSION_LOG

# ── Optionally mark item 4 done in roadmap if found ────────────────────────
if found_anchor:
    # Replace "4. Display..." with "4. ✅ Display..." (or similar based on variant found)
    if found_anchor.startswith("4. "):
        replacement = found_anchor.replace("4. ", "4. ✅ ", 1)
        new_src = new_src.replace(found_anchor, replacement, 1)
        print(f"  Marked anchor '{found_anchor}' as done")

print("── Patch CLAUDE_CONTEXT.md ──")
if not args.apply:
    print("  → would patch (dry-run)")
    print(f"\n    Anchor found: {found_anchor!r}")
    print(f"    New content size: {len(new_src)} chars (+{len(new_src) - len(src)})")
else:
    write_file(CONTEXT_PATH, new_src)
    print("  → patched ✓")
