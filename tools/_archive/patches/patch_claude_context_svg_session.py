#!/usr/bin/env python3
"""
patch_claude_context_svg_session.py

Updates CLAUDE_CONTEXT.md with:
- Roadmap status update (minimap recovered + shipped)
- New "Last session log" entry for the minimap recovery saga
- Detailed SVG map refactor plan for the next session

Idempotent — safe to re-run.
"""

import os
import shutil
import sys

CTX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'CLAUDE_CONTEXT.md')

# Marker phrase to detect if already patched
ALREADY_MARKER = "### 2026-05-07 (evening) — Minimap recovery + SVG refactor plan"

# We replace the "Quick state" block to update timestamps and the
# "Last session log" by appending a new dated entry.

QUICK_STATE_OLD = """- **Last session** : 2026-05-07 — cleanup repo (audit/refine/_archive split)"""
QUICK_STATE_NEW = """- **Last session** : 2026-05-07 (evening) — minimap recovered from .bak files, shipped on main; SVG map refactor planned for next session
- **Active branch (WIP)** : `feature-svg-map` — empty so far, ready for SVG refactor Phase 0"""

# Append marker for the session log — we add the new entry just before
# this anchor so it shows up at the bottom of the existing log.
LOG_ANCHOR = """**Next** : item 3 (intersect_rays) — function already exists in
gtamaplib.py line 2735, just needs wiring into `/api/triangulate`,
`retriangulate_landmark.py`, `batch_retriangulate_aiwe_fixed.py`."""

NEW_LOG_ENTRY = """**Next** : item 3 (intersect_rays) — function already exists in
gtamaplib.py line 2735, just needs wiring into `/api/triangulate`,
`retriangulate_landmark.py`, `batch_retriangulate_aiwe_fixed.py`.

### 2026-05-07 (evening) — Minimap recovery + SVG refactor plan

**TL;DR** : Item 3 + GTA-V style minimap had been shipped earlier but lost
during a botched `git restore`. Recovered everything from `.bak_*` files,
shipped on main as PR #4. Planned the SVG map refactor in detail.

**Lesson learned** : ALWAYS commit (even as wip) before any `git restore`
or `git checkout` with uncommitted changes. The `.bak_*` system saved us
this time, but only because the convention is rigorous. Don't rely on it.

**Recovery saga** :
- The minimap work lived only as uncommitted changes on a deleted branch
  (`feature-rotating-minimap`). After `git restore` + `rm patch_minimap_*.py`,
  the working files were gone and Time Machine / Cursor history were both
  empty.
- BUT — `.bak_*` files in `tools/` had captured the state before each
  patch. Identified the most complete pair:
  - `calib.html.bak_arrow_zoom` (1907 lines, has rectangular rounded
    minimap 260x180, oversized rotator for corner coverage)
  - `server.py.bak_polish` (has `/api/minimap` endpoint with native-scale
    crop + LANCZOS resize — avoids 24000x24000 memory blowup)
- Recovered via `cp tools/X.bak_Y tools/X` on a `recover-minimap` branch.
- Iteratively fixed the pointer to match the original GTA V style:
  small white-filled chevron (16px tall) with thin black stroke, no
  center dot. Final geometry: tip(130,80) wings(122,96)(138,96)
  notch(130,92) in viewBox 260x180.
- Shipped via PR #4, merged into main as commit `7bae4bb`.

**Repo cleanup** :
- All `.bak_*` files moved to `tools/_archive/backups/` (gitignored).
- Applied minimap patches archived in `tools/_archive/patches/`:
  `patch_minimap_pointer_fix.py`, `patch_minimap_pointer_smaller.py`,
  and the obsolete `patch_minimap_final_tweaks.py`.

**Roadmap status** :
- Item 1 (z=0 flag) ✅
- Item 2 (precision flag for cams) ⏸ blocked on rlx clarification
- Item 3 (intersect_rays refactor) ✅ shipped (lost-then-recovered)
- Item 4 (other cam cones) ✅ shipped
- Bonus: GTA-V style rotating minimap ✅ shipped (lost-then-recovered)

---

## SVG Map View Refactor — detailed plan for next session

**Branch** : `feature-svg-map` (already created, currently empty — base
is post-recovery main with minimap shipped).

**Why** : the current `/api/generate_map` and `/api/ray_map` endpoints
re-render PNGs server-side on every interaction → laggy. With T3 release
imminent (1-2 weeks), we need a fluid map view that scales to many cams
and lots of marked pixels.

**Key insight** : Alex has the yanis v11 map as a real vector SVG
(`YANIS_V11_Alternative_Color_Scheme.svg`, viewBox 0 0 20000 20000,
~MB-scale, pure path data — no embedded raster). World-to-SVG transform
is a simple offset: `svg_xy = (world_x + 16500, world_y + 12000)` (based
on `gtamapdata/maps.json` yanis entry: scale=1.0, zero=[16500, 12000],
size=20000x20000). Y-sign to verify on first render.

**The yanis Map object** has `.get_world_xy(pixel)` available (used in
`gtamaputils.py` for AIWE) — so the conversion math is already known.

### Architecture

Two full-screen views, toggle in header `[Camera | Map]`:

**Camera view** (refactored):
- Canvas image at center (current behavior)
- LEFT sidebar (collapsible): cam list + search + filter chips. Replaces
  the current header dropdown. Click cam = sets `currentCam`.
  Checkbox = toggle visibility on map.
- RIGHT sidebar: existing controls (sliders, landmarks list, optimize,
  update LMs, etc.)
- Per-landmark visibility checkboxes in the landmark list (session-only,
  not persisted)
- Minimap stays in bottom-left of canvas (unchanged)

**Map view** (new):
- SVG yanis at center, full-screen, native pan/zoom (viewBox manipulation)
- LEFT sidebar (same as Camera view — shared component)
- RIGHT sidebar: adaptive info panel (cam info on cam click, landmark
  info on landmark click, hover preview)
- Cams render as colored circles + frustum polygons
- Landmarks render as small colored circles (color by error_m)
- "Show all rays" toggle for the selected cam (default off — just
  frustum — to avoid clutter with 50+ cams visible)
- Click landmark → hover preview of triangulation rays + Triangulate
  button (calls existing `/api/triangulate`)

**Shared state** : `currentCam` is global across both views. Switch
between views = `display: none` toggle, no reload, instant.

### Phases (commits on `feature-svg-map`)

0. Add `tools/assets/yanis_v11.svg` (~10 min)
1. Backend: `GET /yanis.svg` + `GET /api/map_data` (JSON dump) (~20 min)
2. Refactor: move cam picker to collapsible left sidebar (~45 min)
3. View toggle Camera/Map infrastructure (~30 min)
4. SVG map view: inline SVG + native pan/zoom + grayscale CSS (~45 min)
5. Render cams (markers + frustums) on map (~45 min)
6. Render landmarks + right sidebar info panel (~45 min)
7. Per-landmark visibility checkboxes in Camera view (~30 min)
8. Cleanup: remove `/api/ray_map`, `/api/generate_map` + UI (~20 min)

**Total estimate** : ~5h

### Design decisions confirmed

- Q1: Use existing SVG asset directly (not PNG-as-bg). CSS
  `filter: grayscale(1)` for the B&W look.
- Q2: Full-screen toggle Camera↔Map (not split, not Map-primary).
- Q3: Remove BOTH `/api/ray_map` AND `/api/generate_map` (the new map
  view replaces both — cleaner than keeping Generate Map for export).
- Q4: Hover preview + click confirm for triangulation (not auto-modify).
- Left sidebar: collapsible.
- Rays in map view: frustum-only by default, toggle "show all rays"
  for the selected cam.
- Landmark visibility checkboxes: session-only via JS Set (no localStorage,
  no server persistence).

### Files in scope

- `tools/server.py` (new endpoints, drop old ones)
- `tools/calib.html` (major restructure)
- `tools/assets/yanis_v11.svg` (new file)
- `gtamaplib/` and `gtamapdata/`: read-only — DON'T TOUCH

### How to start the next session

Paste `tools/CLAUDE_CONTEXT.md` (this file) at the start.
Then say: "let's start Phase 0 of the SVG refactor". Claude should:
1. Confirm we're on `feature-svg-map` branch (clean)
2. Ask Alex to provide the path to his local
   `YANIS_V11_Alternative_Color_Scheme.svg` file
3. Generate the `mkdir tools/assets && cp ...` commands
4. Move to Phase 1 (backend endpoints) once asset is in place
"""


def main():
    if not os.path.exists(CTX_PATH):
        print(f"ERROR: {CTX_PATH} not found", file=sys.stderr)
        sys.exit(1)

    with open(CTX_PATH, 'r') as f:
        content = f.read()

    if ALREADY_MARKER in content:
        print("✓ Already patched — no changes needed.")
        return

    if QUICK_STATE_OLD not in content:
        print(f"ERROR: could not find Quick state line to update.\n"
              f"Looked for: {QUICK_STATE_OLD!r}", file=sys.stderr)
        sys.exit(2)
    if LOG_ANCHOR not in content:
        print(f"ERROR: could not find log anchor (last 'Next' line).\n"
              f"Has the file structure changed?", file=sys.stderr)
        sys.exit(3)

    backup = CTX_PATH + ".bak_svg_session"
    if not os.path.exists(backup):
        shutil.copy(CTX_PATH, backup)
        print(f"  backup created: {backup}")

    new_content = content.replace(QUICK_STATE_OLD, QUICK_STATE_NEW, 1)
    new_content = new_content.replace(LOG_ANCHOR, NEW_LOG_ENTRY, 1)

    tmp = CTX_PATH + ".tmp"
    with open(tmp, 'w') as f:
        f.write(new_content)
    os.replace(tmp, CTX_PATH)
    print("  ✓ Quick state updated")
    print("  ✓ New session log entry appended")
    print("  ✓ SVG refactor plan documented")
    print("✓ Done.")


if __name__ == '__main__':
    main()
