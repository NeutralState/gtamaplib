# CLAUDE_CONTEXT.md

> **À lire en début de chaque session avec Claude.** Colle ce fichier (ou ses
> sections pertinentes) dans le premier message d'un nouveau chat pour
> reprendre où on en était.
>
> **À mettre à jour** à la fin de chaque session productive (Claude génère
> un patch update, tu commit avec le reste).

---

## Quick state

- **Repo** : `~/Downloads/gtamaplib-main` · GitHub : `NeutralState/gtamaplib`
- **Branch active** : `main`
- **Bundle adjust RMS** : 2.26' (commit `a8d5198`)
- **Dashboard global RMS** : 7.71' (broader metric incluant LEAK→FIXED)
- **Last session** : 2026-05-08 — SVG Map Refactor Phases 0-4 done (PNG-based), pushed to `feature-svg-map`
- **Active branch (WIP)** : `feature-svg-map` — Phase 0+1+2+3+4 shipped, Phase 5+ pending

---

## Context : qui je suis, ce que je fais

Je suis **Alex**, Senior Market Events Analyst à Banque Nationale, basé à
Saint-Zotique QC. Je code par "vibe" et j'utilise Claude pour debug/coder.
Le projet `gtamaplib` est un side-project communautaire de cartographie
GTA VI : on calibre des caméras (positions du jeu connues ou inférées) à
partir de pixels marqués sur des screenshots, pour reconstruire la carte
3D avant la sortie du jeu (T3 imminent — flood de screenshots à venir).

`gtamaplib` est la lib originale de **rlx**. Mon code à moi est dans
`tools/`. Je collabore avec rlx via Discord — il review mon travail, me
donne des suggestions, je les implémente.

**Préférences** :
- Commands one-shot dans le terminal que je colle pour voir l'output
- Patches idempotents avec dry-run par défaut, `--apply` pour exécuter
- Backups `.bak_<reason>` avant toute modif destructive
- Solo dev — pas de full collaborative app, focus sur les outils que JE
  vais utiliser, pas sur "et si quelqu'un d'autre…"

---

## Architecture du projet

```
gtamaplib-main/
├── gtamaplib/                  ← rlx canonical lib (DON'T TOUCH)
│   ├── gtamaplib.py            ← Camera, Map, find_camera, find_landmark,
│   │                             intersect_rays(), intersect_ray_and_plane(),
│   │                             intersect_ray_and_ray(), …
│   ├── gtamapdata.py           ← charge cameras.json, landmarks.json,
│   │                             pixels.json, maps.json depuis gtamapdata/
│   └── gtamaputils.py          ← find_aiwe(), find_mary_brickell(), render_all()
├── gtamapdata/                 ← data layer (JSON, source of truth)
│   ├── cameras.json            ← {name: {xyz, ypr, fov, size, source, …}}
│   ├── landmarks.json          ← {name: {xyz, source_cameras, error_m, zone}}
│   ├── pixels.json             ← {cam_name: {lm_name: [px, py]}}
│   ├── maps.json
│   └── map_sections.json
├── tools/                      ← MON code
│   ├── server.py               ← HTTP server localhost:8765 — backend du calib tool
│   ├── calib.html              ← UI de calibration interactive
│   ├── cam_health.html         ← dashboard global de santé des cams
│   ├── bundle_adjust.py        ← solver actuel (TRF two-pass: linear → huber)
│   ├── bundle_adjust_apply.py
│   ├── outliers_report.py
│   ├── regen_index_camdata.py
│   ├── audit/                  ← scripts read-only de diagnostic
│   ├── refine/                 ← scripts qui écrivent dans les JSON
│   ├── _archive/               ← historique (patches déjà appliqués, backups)
│   └── CLAUDE_CONTEXT.md       ← ce fichier
├── docs/                       ← GitHub Pages (visualisation publique)
└── maps/                       ← PNG haute-résolution des maps
```

---

## Concepts clés

### Camera sources

- **LEAK** : caméra extraite directement du jeu (positions exactes,
  ground truth). Source ressemble à `2024-09-26 …`. **Ne jamais les
  optimiser.**
- **TRAILER 1 / 2** : screenshots officiels de Rockstar. Position
  approximative, mais cadrage garanti correct.
- **screenshots** (anciennement "community") : tout le reste — community
  contributions. Position et orientation à inférer.

### Landmarks

- **FIXED** : `source_cameras` ne contient QUE des LEAK cams → triangulé
  depuis le ground truth → on ne le bouge plus.
- **Optimisable** : sourcé depuis au moins une cam non-LEAK → bundle
  adjust peut bouger son xyz.

### Métriques d'erreur

- **Erreur angulaire (arcmin)** : `Δpx · hfov / w · 60` (en arcmin).
  C'est ce que `bundle_adjust` minimise. **Source of truth.**
- **Erreur ground-plane (m)** : projeter le pixel marqué à z=0 et mesurer
  la distance au xyz courant. **Trompeur** pour les landmarks élevés vus
  à pitch faible (le gap peut être énorme alors que l'erreur angulaire
  est minuscule).

### Triangulation

`gtamaplib.intersect_rays(rays)` (closed-form, ligne 2735 de gtamaplib.py)
résout le système linéaire des plans perpendiculaires aux rays. C'est la
primitive moderne — préférer à `find_landmark()` (2-rays seulement) et
aux Nelder-Mead manuels.

```python
# Pattern standard pour triangulation multi-cam :
rays = [(cam.xyz, cam.get_landmark_direction(lm_name)) for cam in cams]
xyz, residual_distances = ml.intersect_rays(rays)
```

---

## Conventions

### Scripts dans `tools/refine/`

Toujours dry-run par défaut, `--apply` pour exécuter :

```python
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
# ... compute proposed changes ...
if not args.apply:
    print("(dry run — re-run with --apply to write changes)")
    sys.exit(0)
# ... write to landmarks.json / cameras.json ...
```

### Backups avant modif

```python
import shutil
shutil.copy(JSON_PATH, JSON_PATH + ".bak_<reason>")
```

Les `.bak*` sont gitignorés et stockés dans `tools/_archive/backups/`.

### Patches one-shot sur `server.py` / `calib.html`

Quand on ajoute une feature, on écrit un script `patch_*.py` qui modifie
le fichier en place avec `str.replace()` (idempotent grâce à un check
"already patched"). Une fois testé et committé, le patch part dans
`tools/_archive/patches/`.

### Persister les changements

**Toujours** passer par `md.update_landmark()` / `md.update_camera()` —
ils gèrent l'écriture atomique (`.tmp` + `os.replace`) et l'update du
cache en mémoire.

---

## Gotchas / leçons apprises

> **Shipping lane pins ne sont PAS coastal** — les landmarks `Pin AXX/BXX/CXX/DXX`
> sont triangulés depuis les 2 cams Keys (LEAK) et flottent à z=2-4m, pas à
> sea level. Le scan `find_z_candidates.py` exclut explicitement `Pin` du
> regex. Source : feedback rlx 2026-05-07.


1. **Le z dans `landmarks.json` est rarement fiable** — la plupart des
   cams sont à pitch faible, donc la composante z est sous-déterminée.
   Pour les coastal points / pins → z=0 est une contrainte plus précise
   que ce qu'on triangule (item 1 de la todo rlx).

2. **`source_cameras` n'est pas immuable** — quand on retriangule un
   landmark FIXED avec un nouvel observer, on peut élargir le set.
   Voir `batch_retriangulate_aiwe_fixed.py` pour le pattern.

3. **Le ground-plane gap (en mètres) n'est pas l'erreur réelle** —
   pour un panneau d'enseigne à 30m de haut vu à pitch -2°, un
   décalage de 50m au sol = quelques arcmin. `investigate_landmark.py`
   affiche les deux maintenant pour éviter cette confusion.

4. **"Update LMs" peut propager des erreurs** — si la cam est dans un
   bad local minimum (loss > 10'), le bouton est grayed-out (patch
   `patch_update_lms_safety.py`).

5. **Pas de classe `Camera` partagée** — chaque appel à `ml.get_camera()`
   peut renvoyer une instance différente. Toujours `set_xyz()` /
   `set_ypr()` / `set_fov()` avant `get_pixel()`. Voir `compute_projections`
   dans `server.py` pour le pattern.

---

## Roadmap actuelle (Discord feedback de rlx, 2026-05-06)

### Items prioritaires

1. ✅ **z=0 / known-z flag pour landmarks** (DONE 2026-05-07)
   - Schema : `landmarks_meta[name]["z_constraint"] = {"type": "fixed", "value": <float>}`
     ou `None` (default).
   - `bundle_adjust.py` force z à la valeur fixée à chaque eval du résidu
     pour les landmarks contraints (x et y restent libres).
   - `update_landmark()` snap `xyz[2]` à la valeur fixée → JSON xyz toujours
     en sync avec le constraint (single source of truth).
   - Workflow d'application :
     1. `python3 tools/audit/find_z_candidates.py` → propose les coastal/pin
     2. Review `/tmp/z_candidates.json`, enlever les faux positifs
     3. `python3 tools/refine/apply_z_constraints.py --apply` → écrit le constraint
     4. `python3 tools/bundle_adjust.py` → re-run avec les contraintes actives

2. **Precision flag pour cams** (Tennis Court etc.)
   - Certaines cams ont des params connus à très haute précision
     (±0.0005 sur ypr au lieu de ±10°)
   - Ajouter une bound personnalisée dans `bundle_adjust`

3. **`intersect_rays()` better triangulation**
   - Remplacer `find_landmark()` 2-rays dans `/api/triangulate` (server.py
     ligne 886) par `ml.intersect_rays(all_rays)`
   - Mettre à jour `retriangulate_landmark.py` et
     `batch_retriangulate_aiwe_fixed.py` pour l'utiliser aussi
   - Bénéfice : closed-form (pas de Nelder-Mead), plus rapide, plus stable

4. **Display other cam cones sur screenshot**
   - Quand on regarde une cam dans calib.html, overlay les frustums des
     autres cams qui voient les mêmes landmarks
   - Backend : nouveau endpoint `/api/observers_for_cam`
   - Frontend : draw les wedges sur le canvas par-dessus l'image

### Stretch (one-shot si possible)

- Dual-pane UI : liste screenshots à gauche + landmarks à droite, filtre
  bidirectionnel
- SVG map overlay au lieu de PNG generation (`/api/generate_map`)

### Concerns

- T3 sort dans 1-2 semaines max → flood de screenshots arrive
- Garder le data layer (JSON files) compatible avec bundle adjust à
  chaque change

---

## Workflow de session avec Claude

1. **Début** : coller ce fichier (ou ses sections pertinentes) au premier
   message
2. **Préciser le focus** : "let's start with item 1: z=0 flag for
   landmarks"
3. **Claude lit le code concerné** dans `/mnt/user-data/uploads/` ou via
   les fichiers que je colle
4. **Plan** : Claude propose une approche avant de toucher au code
5. **Patch** : Claude génère un script `patch_*.py` idempotent
6. **Test** : je lance le dry-run, je review, je `--apply`
7. **Fin** : Claude génère un patch update pour ce fichier
   (`CLAUDE_CONTEXT.md`) que je commit avec le reste

---

## Last session log

### 2026-05-07 — Cleanup repo

- Reorganisé `tools/` en `audit/` (read-only) + `refine/` (write data) +
  `_archive/` (patches déjà appliqués, backups, rlx_originals)
- Ajouté `.gitignore` pour `.bak*` et `bundle_adjust_result.json`
- Créé ce fichier `CLAUDE_CONTEXT.md`
- Commits sur branche `tools-cleanup`, mergé via PR
- **Découverte clé** : `ml.intersect_rays()` existe déjà dans
  `gtamaplib.py` (ligne 2735, closed-form). L'item 3 de rlx = "utilise-la
  partout au lieu des Nelder-Mead manuels".

**Next** : item 1 (z=0 flag for landmarks).

### 2026-05-07 — Consolidate bundle adjust + Item 1 z=0 flag

- Drop `bundle_adjust_v2.py` (archived). `bundle_adjust_v3_twopass.py`
  renommé `bundle_adjust.py` (canonical).
- **Item 1 implémenté** :
  - `gtamapdata.py` : charge `z_constraint` dans `landmarks_meta`.
    `update_landmark()` accepte `z_constraint=None`, préserve les
    fields non-touchés (au passage : fixe le bug qui détruisait le champ
    `author` à chaque write).
  - `bundle_adjust.py` : pré-calcule `_z_constraints`, force z dans le
    résidu, snap z au write-out.
  - `server.py` : `/api/triangulate` snap z, `/api/lm_info` expose
    `z_constraint` au frontend.
  - `tools/audit/find_z_candidates.py` (nouveau) : scan des coastal/pin.
  - `tools/refine/apply_z_constraints.py` (nouveau) : applique le constraint
    en batch depuis une liste.
- Pas de regression : landmarks sans `z_constraint` restent inchangés.

**Next** : item 2 (precision flag pour cams Tennis Court etc).

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
  faster to composite. Not worth the regen tooling for now.

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

