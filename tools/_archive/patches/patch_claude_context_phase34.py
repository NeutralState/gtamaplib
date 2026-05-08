#!/usr/bin/env python3
"""
patch_claude_context_phase34.py — update CLAUDE_CONTEXT.md after Phase 3+4

Updates 4 sections of tools/CLAUDE_CONTEXT.md to reflect completion of
Phase 0+1+2+3+4 of the SVG Map refactor:

1. Quick state — last session date, phases done, current limitation note
2. SVG Map View Refactor section — phase checklist with ✅ marks
3. Last session log — append a new dated block with the session story
4. Insert a "Known limitations" subsection in the SVG refactor section

Idempotent. Dry-run by default.

Usage:
  python3 tools/patch_claude_context_phase34.py            # dry-run
  python3 tools/patch_claude_context_phase34.py --apply
  python3 tools/patch_claude_context_phase34.py --revert --apply
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CTX = os.path.join(THIS_DIR, 'CLAUDE_CONTEXT.md')
BACKUP = CTX + '.bak_phase34_ctx'

# Idempotence sentinel: appears in HUNK_3 (the new last-session log block)
SENTINEL = '### 2026-05-08 — SVG Map Refactor Phases 0-4 (PNG-based)'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — Quick state: update Last session and Active branch lines
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
- **Last session** : 2026-05-07 (evening) — minimap recovered from .bak files, shipped on main; SVG map refactor planned for next session
- **Active branch (WIP)** : `feature-svg-map` — empty so far, ready for SVG refactor Phase 0"""

HUNK_1_NEW = """\
- **Last session** : 2026-05-08 — SVG Map Refactor Phases 0-4 done (PNG-based), pushed to `feature-svg-map`
- **Active branch (WIP)** : `feature-svg-map` — Phase 0+1+2+3+4 shipped, Phase 5+ pending"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — Mark Phases 0-4 done in the SVG refactor section
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
0. Add `tools/assets/yanis_v11.svg` (~10 min)
1. Backend: `GET /yanis.svg` + `GET /api/map_data` (JSON dump) (~20 min)
2. Refactor: move cam picker to collapsible left sidebar (~45 min)
3. View toggle Camera/Map infrastructure (~30 min)
4. SVG map view: inline SVG + native pan/zoom + grayscale CSS (~45 min)
5. Render cams (markers + frustums) on map (~45 min)
6. Render landmarks + right sidebar info panel (~45 min)
7. Per-landmark visibility checkboxes in Camera view (~30 min)
8. Cleanup: remove `/api/ray_map`, `/api/generate_map` + UI (~20 min)

**Total estimate** : ~5h"""

HUNK_2_NEW = """\
0. ✅ Add `tools/assets/yanis_v11.svg` (DONE 2026-05-08)
1. ✅ Backend: `GET /yanis.svg` + `GET /api/map_data` (DONE 2026-05-08)
2. ✅ Refactor: move cam picker to collapsible left sidebar (DONE 2026-05-08)
3. ✅ View toggle Camera/Map infrastructure (DONE 2026-05-08, merged with Phase 4)
4. ✅ Map view rendering — **PNG-based**, NOT inline SVG (DONE 2026-05-08, see notes below)
5. ⏸ Render cams (markers + frustums) on map (~45 min) — **NEXT**
6. ⏸ Render landmarks + right sidebar info panel (~45 min)
7. ⏸ Per-landmark visibility checkboxes in Camera view + minimap CSS-only rebuild (~30 min)
8. ⏸ Cleanup: remove `/api/ray_map`, `/api/generate_map` + UI (~20 min)

**Total estimate** : ~5h (4 phases done, ~3h remaining)

### Phase 4 architectural pivot: SVG → PNG

The original plan was to inline-render the yanis SVG and pan/zoom via
viewBox manipulation. **This was abandoned.** The 85 MB SVG (10 370
paths + 126 embedded base64 PNG vignettes + a 4.5 MB mega-mask) was
unviable in the browser:
- viewBox mutation on every wheel tick triggered re-layout of all paths
  → 1-2 FPS pan/zoom
- CSS `transform: scale()` on the wrapper still required the browser
  to rasterize 85 MB of paths into a GPU texture → multi-second hangs
  and high memory use

**Final solution**: pre-render the SVG to a PNG asset, served as a
static file. Pan/zoom via CSS transform on a `<div>` wrapper containing
both an `<img>` (the PNG) and an empty `<svg>` overlay (where Phase 5+
will draw cam markers and landmark dots). Both layers share the same
transform, so SVG-user coordinates align 1:1 with image pixels.

**Resolution chosen**: 12 000 × 12 000 px (~48 MB). This gives ~1.4×
stretch for a 500 m-radius minimap crop displayed at 260 × 180 px,
close to 1:1 with the current `/api/minimap` endpoint quality. 8K was
tried first (4.3 MB) but at the resolution Phase 7 needs for the
minimap rebuild it would have been visibly blurry.

### Known limitations to revisit

- **PNG resolution** (current 12K, ~48 MB): pan/zoom is fluid but at
  extreme zoom (>5-10× in map view) the bitmap pixelizes. Higher
  resolution attempted (16K/20K) but `rsvg-convert` hits memory limits
  on the cloud sandbox at >5K, and locally the in-browser load time
  starts to lag at 16K+. **Future work**: tile-based loading
  (Leaflet/Mapbox-style 4-level pyramid) or one-shot regen at higher
  res when machine RAM allows.
- **PNG asset size** (48 MB) inflates the repo. Acceptable for now
  since this is a personal/community tool, but worth revisiting if
  the project grows.
- **Filter rendering**: grayscale + brightness/contrast applied via
  CSS filter. Looks OK, but a pre-rendered B&W PNG would be slightly
  faster to composite. Not worth the regen tooling for now."""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — Append a new block to the Last session log section
# Anchor: end of the previous "evening" log block (the "How to start the
# next session" instructions are AFTER it in the file, but they belong to
# the SVG refactor section, not the log. We append between the log and
# the refactor section's "How to start" subsection).
#
# Looking at the file structure, the log section ends with:
#   - Bonus: GTA-V style rotating minimap ✅ shipped (lost-then-recovered)
#
# Then there's "---" then the SVG Map View Refactor section. We add the
# new log block right before that "---".
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
- Bonus: GTA-V style rotating minimap ✅ shipped (lost-then-recovered)

---

## SVG Map View Refactor — detailed plan for next session"""

HUNK_3_NEW = """\
- Bonus: GTA-V style rotating minimap ✅ shipped (lost-then-recovered)

### 2026-05-08 — SVG Map Refactor Phases 0-4 (PNG-based)

**TL;DR**: shipped Phases 0+1+2+3+4 of the SVG refactor. Original SVG-
based approach for Phase 4 was abandoned mid-session after extensive
performance debugging — switched to a pre-rendered PNG. Map view now
loads in ~3-5s (one-time per session, then cached), pan/zoom is GPU-
fluid at 60 FPS, and the empty SVG overlay layer is ready for Phase 5+.

**Phases shipped on `feature-svg-map`**:
- **Phase 0**: yanis SVG asset added at `tools/assets/yanis_v11.svg`.
  Filename had spaces in original download (`YANIS V11 Alternative
  Color Scheme.svg`), normalized at copy time.
- **Phase 1**: backend endpoints `GET /yanis.svg` (cache 1h) and
  `GET /api/map_data` (returns transform metadata + cam list with
  xyz + landmark list). Decided y_sign=-1 (verified via
  `gtamaputils.find_aiwe`). Frustum corners computed frontend-side.
  Cams without xyz excluded; landmarks without xyz included with
  xyz=null (so Phase 6 Triangulate can target them).
- **Phase 2**: cam picker moved from header dropdown to collapsible
  left sidebar (260 px, transition 0.18s, burger toggle session-only).
  Hidden `<select id="cam-sel">` retained as source of truth for
  compatibility with existing `dispatchEvent('change')` callsites.
  Phase 2.1 hotfix: `transitionend` listener triggers `resizeOverlay`
  to fix marked-pixel drift on collapse.
- **Phases 3+4 (combined)**: view toggle [Camera | Map] in header,
  `currentView` state, `body.view-map` CSS mode, map-view container.
  Originally tried inline-SVG with viewBox-pan/zoom (1-2 FPS), then
  CSS transform on wrapper containing 85 MB of `<svg>` (still laggy),
  then SVG cleanup (stripped 126 embedded base64 PNGs → 48 MB) — all
  insufficient. **Pivoted to PNG**: rendered yanis_v11_lite.svg via
  `rsvg-convert -w 12000` on cloudconvert.com → 48 MB PNG. Replaced
  endpoint `/yanis.svg` with `/yanis.png`. Front-end now uses `<img>`
  + empty SVG overlay (both pinned to native 20000×20000 dimensions,
  CSS-transformed together). Decided full grayscale + brightness 1.05
  + contrast 1.1 for the B&W look.

**Decisions logbook for this session**:
- y_sign = -1 (validated via `gtamaputils.find_aiwe` showing
  aiwe_top=North → SVG y inverted from world y).
- Frustum corners computed frontend, not backend (Phase 5 scope).
- Map asset stored as PNG, not SVG. Original SVG too heavy. PNG
  re-generation is a one-shot offline step (cloudconvert.com).
- Resolution = 12K. 4K too blurry for minimap rebuild. 16K hits
  rsvg-convert memory limits in sandbox AND in-browser load lag.
- Pan/zoom via CSS transform on wrapper, not viewBox manipulation
  (viewBox forces SVG re-layout per frame).
- `worldToSvg` / `svgToWorld` exposed on `window` (along with
  `mapImg`, `mapOverlay`, `mapTransform`, `mapTx`, `currentView`,
  `setView`, `resetMapView`) so Phase 5+ overlay rendering can plug
  in without smuggling locals through closures.
- Minimap (Phase 7) will be a CSS-only crop of the cached PNG, not
  a server-side render. The 12K resolution was chosen specifically
  to make this work without re-fetching.

**Lessons learned this session**:
- "Sentinel-detected idempotence" patches need their sentinel string
  to actually appear in the inserted text, not just the docstring.
  Got bitten once by a `*/` mismatch between the SENTINEL constant
  and a multi-line CSS comment in HUNK_NEW.
- For interactive web visualization of large vector data, "render
  it once, pan it as a layer" beats "re-render on every interaction"
  by 10× in browser perf, even with all the will-change/translateZ
  hints. If the asset is too big to layer, pre-render to bitmap.
- 85 MB SVG was 44% embedded raster vignettes + 56% real path data.
  Cleanup via regex strip of `<image>` tags reduced to 48 MB without
  visual loss. Useful pattern for any SVG-to-PNG pipeline (the lite
  SVG renders ~2× faster in `rsvg-convert`).

**Roadmap status**:
- Item 1 (z=0 flag) ✅
- Item 2 (precision flag for cams) ⏸ blocked on rlx clarification
- Item 3 (intersect_rays refactor) ✅ shipped
- Item 4 (other cam cones) ✅ shipped
- Bonus: GTA-V style rotating minimap ✅ shipped
- SVG Map Refactor Phases 0-4 ✅ shipped
- SVG Map Refactor Phases 5-8 ⏸ pending

**Next**: Phase 5 — render cam markers + frustums in the empty SVG
overlay (`window.mapOverlay`). All scaffolding in place: `mapData`
has the cam list with xyz, `worldToSvg` converts world→SVG-user
coordinates, Phase 5 just injects `<circle>` and `<polygon>`
elements and wires click/hover handlers.

---

## SVG Map View Refactor — detailed plan for next session"""


HUNKS = [
    ('1 (Quick state — last session + branch status)', HUNK_1_OLD, HUNK_1_NEW),
    ('2 (SVG section — phase checklist + pivot notes + limitations)', HUNK_2_OLD, HUNK_2_NEW),
    ('3 (Last session log — append 2026-05-08 block)', HUNK_3_OLD, HUNK_3_NEW),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--revert', action='store_true')
    args = ap.parse_args()

    if not os.path.exists(CTX):
        print(f'ERROR: {CTX} not found.')
        sys.exit(1)

    if args.revert:
        if not os.path.exists(BACKUP):
            print(f'ERROR: no backup at {BACKUP}.')
            sys.exit(1)
        if args.apply:
            shutil.copy(BACKUP, CTX)
            print(f'✓ Restored {CTX} from {BACKUP}.')
        else:
            print(f'(dry-run) would restore from {BACKUP}.')
        return

    with open(CTX, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print('✓ Already patched.')
        return

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
    print(f'Will modify {CTX}')
    print(f'  hunks applied: {len(HUNKS)}')
    print(f'  net line delta: {delta:+d}')
    print()
    for label, _, _ in HUNKS:
        print(f'  ✓ hunk {label}')

    if not args.apply:
        print('\n(dry-run — re-run with --apply)')
        return

    shutil.copy(CTX, BACKUP)
    print(f'\n✓ Backup: {BACKUP}')
    tmp = CTX + '.tmp'
    with open(tmp, 'w') as f:
        f.write(new_src)
    os.replace(tmp, CTX)
    print(f'✓ Patched {CTX}')


if __name__ == '__main__':
    main()
