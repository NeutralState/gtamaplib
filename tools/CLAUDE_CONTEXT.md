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
- **Branch active** : `feature-svg-map`
- **Bundle adjust RMS** : 2.26' (clean state, post-revert of Mount Kalaga experiment)
- **Last session** : 2026-05-09 — Phases 5-8.2 + Phase 9.1 shipped, minimap pre-render script, rlx port investigation (parked)

---

## Context

Je code par "vibe" et j'utilise Claude pour debug/coder. Le projet
`gtamaplib` est un side-project communautaire de cartographie GTA VI :
on calibre des caméras (positions du jeu connues ou inférées) à partir
de pixels marqués sur des screenshots, pour reconstruire la carte 3D
avant la sortie du jeu (T3 imminent — flood de screenshots à venir).

`gtamaplib` est la lib originale de **rlx**. Mon code à moi est dans
`tools/`. Je collabore avec rlx (et martipk, YANIS, autres) via Discord.

**Préférences** :
- Commands one-shot dans le terminal que je colle pour voir l'output
- Patches idempotents avec dry-run par défaut, `--apply` pour exécuter
- Backups `.bak_<reason>` avant toute modif destructive
- Identité du tool : **open-source single-editor**. Moi comme canonical
  maintainer, JSONs dans le repo comme source of truth. Anyone peut
  cloner + run + explorer + PR. Git handle l'isolation, pas de
  preview/commit refactor needed.

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
│   ├── cameras.json            ← {name: {id, player, xyz, ypr, fov, size, source}}
│   ├── landmarks.json          ← {name: {xyz, source_cameras, error_m, zone, author}}
│   ├── pixels.json             ← {cam_name: {lm_name: [px, py]}}
│   ├── maps.json
│   └── map_sections.json
├── tools/                      ← MON code
│   ├── server.py               ← HTTP server localhost:8765 — backend du calib tool
│   ├── calib.html              ← UI de calibration interactive (~3500 lignes)
│   ├── cam_health.html         ← dashboard global de santé des cams
│   ├── bundle_adjust.py        ← solver actuel (TRF two-pass: linear → huber)
│   ├── bundle_adjust_apply.py
│   ├── outliers_report.py
│   ├── prerender_minimaps_fast.py  ← bulk pre-render minimap cache (3s pour 147 cams)
│   ├── audit/                  ← scripts read-only de diagnostic
│   ├── refine/                 ← scripts qui écrivent dans les JSON
│   ├── generated/minimaps/     ← per-cam minimap PNG cache (lazy + bulk)
│   ├── _archive/               ← historique (patches déjà appliqués, abandoned)
│   └── CLAUDE_CONTEXT.md       ← ce fichier
├── docs/                       ← GitHub Pages (visualisation publique)
└── maps/                       ← PNG haute-résolution des maps (yanis,11.png ~56MB)
```

---

## Schema (cameras.json) — IMPORTANT

```json
{
  "L1/1": {
    "id": "L1/1",                    ← format <type><source>/<frame>
    "player": [x, y, z],             ← position du player (LEAK only) ou null
    "xyz": [x, y, z],                ← cam position
    "ypr": [yaw, pitch, roll],       ← roll currently hardcoded = 0
    "fov": [hfov, vfov],             ← un des deux peut être null
    "size": [w, h],
    "source": "..."
  }
}
```

**ID prefixes**:
- `L1`: LEAK source 1 (79 cams)
- `T1`: Trailer 1 (28 cams)
- `T2`: Trailer 2 (16 cams)
- `S2`: Screenshots batch 2 (24 cams)

**Notable**: `roll` (ypr[2]) est systématiquement ignoré dans le pipeline:
- `/api/save`, `/api/optimize`, `/api/update_landmarks` hardcodent `ypr[2] = 0.0`
- `optimize_camera()` n'inclut pas roll dans x0
- `bundle_adjust.py` optimize seulement `[xyz, yaw, pitch, hfov]`

YANIS a confirmé que roll est **needed** pour Jason at sea + Chase 2.
Roll integration = full pipeline refactor (Phase 10 à venir).

---

## Concepts clés

### Camera sources

- **LEAK** : caméra extraite directement du jeu (positions exactes,
  ground truth). Source ressemble à `2024-09-26 …`. **Ne jamais les
  optimiser.**
- **TRAILER 1 / 2** : screenshots officiels de Rockstar. Position
  approximative, mais cadrage garanti correct.
- **screenshots** (S2 etc) : community contributions. Position et
  orientation à inférer.

### Landmarks

- **FIXED** : `source_cameras` ne contient QUE des LEAK cams → triangulé
  depuis le ground truth → on ne le bouge plus.
- **Optimisable** : sourcé depuis au moins une cam non-LEAK → bundle
  adjust peut bouger son xyz.

### Métriques d'erreur

- **Erreur angulaire (arcmin)** : `Δpx · hfov / w · 60` (en arcmin).
  C'est ce que `bundle_adjust` minimise. **Source of truth.**
- **Erreur ground-plane (m)** : trompeur pour les landmarks élevés.

### Triangulation

`gtamaplib.intersect_rays(rays)` (closed-form, ligne 2735) résout le
système linéaire. Préférer à `find_landmark()` (2-rays seulement).

```python
rays = [(cam.xyz, cam.get_landmark_direction(lm_name)) for cam in cams]
xyz, residual_distances = ml.intersect_rays(rays)
```

---

## Conventions

### Scripts dans `tools/refine/`

Toujours dry-run par défaut, `--apply` pour exécuter.

### Backups avant modif

```python
shutil.copy(JSON_PATH, JSON_PATH + ".bak_<reason>")
```

### Patches one-shot sur `server.py` / `calib.html`

Scripts `patch_*.py` qui modifient avec `str.replace()` (idempotent
via sentinel check). Une fois committé, le patch part dans
`tools/_archive/patches/`.

### Persister les changements

**Toujours** passer par `md.update_landmark()` / `md.update_camera()` —
ils gèrent l'écriture atomique (`.tmp` + `os.replace`) et le cache.

---

## Gotchas / leçons apprises

> **Shipping lane pins ne sont PAS coastal** — les landmarks `Pin AXX/BXX/CXX/DXX`
> sont triangulés depuis les 2 cams Keys (LEAK) et flottent à z=2-4m, pas à
> sea level. Source : feedback rlx 2026-05-07.

1. **Le z dans `landmarks.json` est rarement fiable** — pour coastal/pins
   → z=0 est une contrainte plus précise.
2. **`source_cameras` n'est pas immuable** — quand on retriangule, on
   peut élargir le set.
3. **Le ground-plane gap (en mètres) n'est pas l'erreur réelle** — pour
   un panneau à 30m de haut vu à pitch -2°, un décalage de 50m au sol =
   quelques arcmin.
4. **"Update LMs" peut propager des erreurs** — désactivé si loss > 10'.
5. **Pas de classe `Camera` partagée** — chaque appel à `ml.get_camera()`
   peut renvoyer une instance différente. Toujours `set_xyz()` /
   `set_ypr()` / `set_fov()` avant `get_pixel()`.
6. **SVG presentation attributes ont LOWER CSS cascade priority** que
   les author rules. Use inline style or remove conflicting CSS.
7. **Sentinel strings dans patches** doivent être literally embedded
   dans le HUNK_NEW string content, pas juste défini comme constant.
8. **Safari + macOS**: large PNGs (12K+ resolution) hit slow paths en
   CSS background-image AND `<img>` + transform. Native-size `<img>`
   sans transform = fast. Disk-cached small PNGs = fast.
9. **`mapData.cameras` not `mapData.cams`** — verify field names.
10. **zsh quote-stuck issues**: French apostrophes (`l'ancien`) open
    string-quote même dans `#` comments. Quote URLs avec single quotes.
11. **`refine_camera.py`** a path bug: `dirname(dirname(__file__))`
    devrait être un niveau de plus. Workaround: prefix avec
    `PYTHONPATH=~/Downloads/gtamaplib-main` quand on run.
12. **Bundle adjust apply requires explicit `yes`** — taper "git status"
    par accident triggers abort. Tape "yes" en majuscules ou minuscules.
13. **rlx schema diffère du nôtre** — voir section "rlx port" plus bas.

---

## Roadmap (Discord feedback rlx + martipk + YANIS, 2026-05-09)

### Items shipped

- ✅ z=0 / known-z flag pour landmarks (2026-05-07)
- ✅ intersect_rays() refactor (2026-05-07)
- ✅ Other cam cones overlay (2026-05-07)
- ✅ GTA-V style rotating minimap (2026-05-07)
- ✅ SVG Map Refactor Phases 0-4 (2026-05-08, PNG-based)
- ✅ Phase 5: cam markers + frustums on map (2026-05-09)
- ✅ Phase 6: landmark dots + delta-colored rays + map sidebar
- ✅ Phase 6.4 abandoned (cam marker styles, all 3 attempts failed)
- ✅ Phase 7a: minimap relocated to sidebar + cam preview swap
- ✅ Phase 8.1: triangulate on Map view (converging rays + toast)
- ✅ Phase 8.2: drop ray-map-modal + /api/ray_map endpoint
- ✅ Phase 9.1: URL hash state + landmark sort + filter row declutter
- ✅ Bulk minimap pre-render (3s pour 147 cams)

### Items pending

#### High priority (T3 critical path)

- ⏸ **Roll slider integration (Phase 10)** — full pipeline refactor.
  YANIS confirmed needed for Jason at sea + Chase 2. Touche save +
  optimize + bundle_adjust. ~2-3h focused work.
- ⏸ **Vanishing points + verticals UX** — rlx + martipk both push.
  Single biggest T3 unlock. Replace landmarks for fresh cam bootstrap.
  Multi-session feature.
- ⏸ **Port rlx upstream cams** — 24 new cams chez rlx pas chez nous
  (Auto Shop SE/SW, Police Chase B-I, Yacht 1/2, Tennis Court E/N/SW,
  Jason Duval 03 Boat, etc). Requires schema mapping (rlx vs ours,
  voir section dédiée plus bas).

#### Medium

- ⏸ **Roll slider** — slider only (no pipeline integration), live
  preview mode. Could be done before Phase 10.
- ⏸ Search and sort landmarks (sort done in Phase 9.1, search exists)

#### Parked

- Optimized vs unoptimized dataset toggle
- Rainbow blob uncertainty viz (computationally expensive per rlx)
- Step-through animation of bundle adjust
- Chain triangulation + reoptimize (research project, not feature)
- Identity question / preview-vs-commit refactor (resolved: open-source
  single-editor, git handles isolation)

---

## Workflow de session avec Claude

1. **Début** : coller ce fichier (ou ses sections pertinentes)
2. **Préciser le focus** : "let's start with X"
3. **Plan** : Claude propose une approche avant de coder
4. **Patch** : Claude génère un script `patch_*.py` idempotent
5. **Test** : dry-run, review, `--apply`
6. **Fin** : update ce fichier + commit

---

## rlx port — schema mapping needed

**Issue identifiée 2026-05-09**: rlx maintient son repo upstream
(`rolux/gtamaplib`). 190 commits divergence. Son `gtamapdata.py` utilise
un schema différent du nôtre.

**Son schema**:
```python
"[L1/1] Diner": (
    (px, py, pz),                  # player
    (cx, cy, cz),                  # xyz
    (yaw, pitch, roll),            # ypr
    (hfov, vfov),                  # fov tuple
    (w, h),                        # size
    "2021-03-23 09-58-52 [1]"      # source
)
```

**Notre schema** (cameras.json):
```json
{
  "id": "L1/1",
  "player": [...] or null,
  "xyz": [...],
  "ypr": [...],
  "fov": [hfov, vfov] or [null, vfov] or [hfov, null],
  "size": [w, h],
  "source": "..."
}
```

**Mapping nécessaire**:
- rlx `(player, xyz, ypr, fov_tuple, size, source)` →
  notre `{id, player, xyz, ypr, fov, size, source}`
- ID extracted depuis le key `[L1/1] Name` chez rlx, séparé en clé chez nous

**À faire pour le port**:
1. Re-écrire `port_rlx_new_cams.py` avec ce mapping correct
2. Tester sur 1 cam d'abord
3. Pour landmarks, schema simple: rlx a `lm_name: (x, y, z)` tuple,
   nous on a un dict avec metadata

**Sample landmarks (notre schema)**:
```json
{
  "112 NE 41st St": {
    "xyz": [...],
    "source_cameras": ["Glitch (A)", "Highway (NE)"],
    "error_m": 0.604,
    "zone": "vice_city",
    "author": "rlx"
  }
}
```

rlx n'a pas `source_cameras`/`error_m`/`zone`/`author`. Pour porter ses
landmarks, on devrait soit set des defaults soit générer ces fields.

---

## Last session log

### 2026-05-09 — Big day: Phases 6-8.2 + 9.1 + cleanup + rlx port investigation

**Phases shipped**:
- Phase 6 (landmark dots + delta colored rays + map sidebar)
- Phase 6.4 abandoned (3 cam marker styles all failed, reverted)
- Phase 7a (minimap to sidebar, cam preview swap, drop Generate Map)
- Phase 8.1 (Triangulate on Map view with converging color-coded rays
  + toast)
- Phase 8.2 (drop ray-map-modal HTML + showRayMap callsites + /api/ray_map)
- Phase 9.1 (URL hash state for cam/view/sort, sort dropdown for lm-list,
  drop "Bad" filter, move "+Add" to header)

**Mount Kalaga experiment** (reverted, kept uncommitted state clean):
- martipk asked about Delights billboard visible from Mount Kalaga 04
- Added pixel `(2594.1, 362.6)` for "Billboard (Delights)" on this cam
- Bundle adjust showed 266.8' residual on this observation [FIXED LM]
- Ran `refine_camera.py --refine-xyz --xyz-radius 5000 --no-hfov`:
  cam was off by **1.3km**, RMS converged at 4.10' on consensus landmarks
- Apply + bundle adjust: **global RMS dropped 6.27' → 2.32'** (-64%)
- BUT decided not to commit — uncertainty about whether it's truly the
  same billboard. Reverted via Python script that removes the pixel and
  uses git checkout for cameras.json + landmarks.json.

**Dark map experiment** (tested, didn't like, reverted):
- Generated yanis_v11_dark.png + yanis,11_dark.png via PIL invert
- Visual not preferred, reverted

**Bulk minimap pre-render**:
- Wrote `tools/prerender_minimaps_fast.py` (commits to repo)
- Loads source PNG once, batch-renders 131 minimaps in **3.1 seconds**
  (42 cams/sec). Replaces lazy on-demand rendering for first-time use.

**rlx port investigation**:
- Added `upstream` remote pointing to `rolux/gtamaplib`
- 190 commits divergence, 226 files modified by rlx
- 24 new cams chez rlx pas chez nous (mostly action shots, Police Chase
  series, Yacht, Tennis Court angles)
- 5 new landmarks (3 with xyz: Squalo Billboard TN/TS, Stephen P. Clark
  Center NW; 2 without xyz: Stephen P. Clark Center W, Unknown Building
  North Vice Beach)
- 21 pixels to port (21 Minimap UI refs to skip)
- **Port script first attempt FAILED** because rlx schema differs from
  ours (no `id`, no `player`, `hfov` scalar vs `fov` tuple). Reverted.
- **Schema mapping required** before next attempt.

**Discord context**:
- rlx considers gtamaplib our "real thing", his repo a "toy prototype"
- Confirmed identity: open-source single-editor, JSONs in repo as truth
- Vanishing points + verticals UX = highest priority T3 unlock
- Roll integration confirmed needed (YANIS: Jason at sea + Chase 2)

**Files cleanup**:
- 19 backup files in tools/ deleted (post Phase 9.1)
- Patch Phase 7a.1.2 archived
- bundle_adjust_result.json untracked (gitignore'd)
- `.gitignore` deduped

**Next session priorities**:
1. **Roll slider** (Phase 10 if full integration, or just live preview
   slider if we want quick win)
2. **rlx port v2** (with correct schema mapping)
3. **Vanishing points + verticals UX** (T3 critical path)


---

## Session: 2026-05-18 Day 2 — Portofino mesh refinement (final)

**Final state**: commit `82cbe03` — sym 120° mesh with proven global optimum

### Key discoveries

1. **AI World Editor Map (4K) is OUR construction, not external leak**. The B-front* landmarks derived from it (centroid 1741.58, -200.89, R=30m wing front) are not ground truth — they are noise from our own data.

2. **3 distinct peaks visible on Amphi** at pixels ~547/556/577 (separated by ~10px). User confirmed visually + Discord validation.

3. **Correct Amphi pixel assignments** (left-to-right ordering on Amphi due to building rotation and cam angle):
   - NE = (555, 53) — leftmost peak
   - NW = (565, 52) — middle peak (the central one with antenna)
   - S  = (577.4, 53.7) — rightmost peak
   - Earlier confusion: thought "NE" pixel at (556, 52) was actually NW projection (~0.1px match)

4. **Sidewalk (Jason) (E) is also a leak cam** (L1/6). 3 leak cams total: Port (L1/7), Amphi (L1/3), Sidewalk (L1/6). Rooftop is screenshot (T1/20), not leak.

5. **Leak cams constraint**: xyz + fov are FIXED. yaw/pitch/roll can be adjusted.

### Mathematical proof of global optimum

Used Differential Evolution + Basin Hopping + fine grid LSQ — all converge to same minimum under sym 120° constraint:

- Centroid: (1732.81, -206.87)
- R_PEAK: 18.04m
- Z: 142.77m
- Rotation: +5.44° vs canonical base bearings NW=279.19°, NE=39.41°, S=159.37°
- RMS: 2.67 px on 7 leak cam observations

GTA bearings final: NW=284.63°, NE=44.85°, S=164.81°.

### Leak cam yaw/pitch optimization (applied)

Joint optimization with all leak cam landmarks (not just Portofino):
- Port:     yaw 302.5 → 302.3392 (Δ-0.1608°)
- Amphi:    yaw 256.6083 → 256.6445 (Δ+0.0362°)
- Sidewalk: yaw 244.8 → 244.7533 (Δ-0.0467°)
- pitch deltas: all <0.02°

Result: initial RMS 1.91 → 1.58 (-17%) on all leak observations including non-Portofino LMs.

### Body dimensions (90% scale — sweet spot)

After leak-cams-only fit shrunk mesh, body proportionally tuned for visual match:
- BODY_OUTER: 27.0m (was 30 original, tested 25.5 at 85%)
- BODY_HALF_W: 11.7m (was 13)
- BODY_INNER: 6.3m (was 7)
- CYL_RADIUS: 8.1m (was 9)
- PEAK_BOX: 4×4m, rotated +45° from radial (corner-facing not face-facing)

85% was slightly too narrow on Port. 100% would be too wide on Amphi. 90% is compromise.

### Persistent residuals (irreducible)

- Amphi NW: 6.43 px
- Sidewalk NE: 5.39 px

RANSAC dropping Port gave RMS 0.84 on Amphi+Sidewalk only — but Port itself matches all its other LMs (Murano 2.3px, Portofino 0.9-3px). Port is reliable; the Amphi+Sidewalk outliers are pixel marking imprecision at 1.9-2.6km distance (resolution limit).

### Commits this session

- `161f43c` Portofino sym 120° fit without Amphi NW outlier (initial RMS 1.9)
- Final relabeled state with 3 Amphi peaks correctly identified
- `82cbe03` Body bumped to 90% (final compromise)

### Lessons learned

- Naive ordering assumption (left=NW, right=S on Amphi) is WRONG. Pinwheel buildings project peaks in non-intuitive orders depending on cam bearing.
- Test permutations of label assignments when pixel ordering is ambiguous.
- Global optimization (DE + Basin Hopping) is essential when fit has multiple local minima.
- B-front leak landmarks should be treated as constructed, not ground truth.
- For leak cams: xyz/fov fixed but yaw/pitch can have small calibration errors (~0.1-0.2°).
- Pixel marking at >2km distance has ~5px irreducible error from human perception limits.


## Session: 2026-05-21 — Building meshes (procedural rendering) + Portofino densify

### Major wins

Procedural building wireframes rendering live in calib UI. Each cam projects
the building mesh into pixel space via the server `/api/building_meshes_procedural`
endpoint. Buildings supported:

- **Four Seasons Hotel Miami**: 1003 edges
- **Sunshine Skyway Bridge**: 242 edges (includes the suspension cables)
- **HanksWaffles**: 65 edges
- **Portofino Tower**: 256 edges (densified from 135 to 256, includes pyramidal apex)

### Architecture

Pipeline:
1. `gtamaplib.py` has Landmark subclasses (`FourSeasons`, `SunshineSkywayBridge`,
   `HanksWaffles`) with `render_on_camera(cam)` methods that draw via
   `cam.render_line((xyz1, xyz2), ...)` calls.
2. `tools/extract_mesh_edges.py` uses a `FakeCam` proxy to hijack render_line
   calls — collects (xyz1, xyz2) pairs into a list instead of drawing.
3. Multi-pass extraction (4 viewpoints for FourSeasons) to capture all faces
   despite hidden-face logic in render_on_camera.
4. Output: `gtamapdata/building_meshes_procedural.json` with `{building_name:
   {color, world_edges: [[xyz1, xyz2], ...]}}`.
5. Server endpoint `/api/building_meshes_procedural?cam=X` projects each edge
   to pixel space via `cam.get_pixel(xyz)`, skips out-of-frame edges, returns
   `{meshes: {bld_name: {color, pixel_edges: [[[x,y], [x,y]], ...]}}}`.
6. Frontend `loadProceduralMeshes()` fetches per-cam projected edges, stored
   in `BUILDING_PROCEDURAL_PIXEL_EDGES`. `drawBuildingWireframes()` handles
   both legacy LM-name format (Portofino) and procedural pixel format.

### Portofino: densified hardcoded edges (not a procedural class)

Portofino has 135 LMs in landmarks.json (Alexandre's calibrated mesh from
`gen_portofino_v4.py`). Tried refactoring as a `PortofinoTower(Landmark)` class
but failed — the simplistic translation didn't match the real building's
break/topology and looked worse than the hardcoded version.

Final approach: `tools/densify_portofino_edges.py` auto-generates a complete
edge array from the 135 existing LMs. Walks the pent/cyl/peak-box structure
and outputs all vertical + horizontal edges. Pyramidal apex edges connect
peak box PT corners to branch anchors (NW/NE/S act as turret pyramid apex).

Re-run anytime LMs change:
    python3 tools/densify_portofino_edges.py

The script discovers structure on-the-fly:
- Pentagons: levels B(-15) / L(14) / K(83) / M(91) / P(125), 3 branches, 4 corners
- Cylinder: levels B/L/K/M/P/CT(137), 8 segments
- Peak box: levels PB(125) / PT(138.77), 3 branches, 4 corners

### Tools inventory (NEW)

`tools/TOOLS_INVENTORY.md` is auto-generated from `tools/generate_inventory.py`.
Scans repo and produces markdown docs for:
- 21 CLI scripts (with docstring summaries + usage)
- 22 server endpoints
- 30 UI buttons (with tooltips)
- 13 keyboard shortcuts

Re-run after adding new tools: `python3 tools/generate_inventory.py`

Helped surface forgotten existing scripts (intake_camera, calibration_order,
compute_confidence_tiers, bundle_adjust, etc.).

### Multicam dual-pane (committed earlier)

Side-by-side cam comparison view (`d` to toggle). Top/bottom split. Each pane
has independent pan/zoom. Ghost LM projections render on opposite pane
(`/api/lm_projections?cam=X&filter_cam=Y`). Smart pane assignment on click.

Canvas-ghosts refactor: ghost markers drawn on canvas (not SVG) for consistent
visual style with main markers.

### Tile migration complete

`yanis.jpg` (13MB) + `map_view_v2.html/js` removed. Map view + sidebar/cam
minimaps all use rlx tile pyramid via `vendor/gtadb.org/maps/tiles/6/yanis,12/`.

### Failed experiments (reverted)

- **Strategic dashboard** for cam_health.html (ROI scoring). Built it, found
  the recommendations weren't useful (top picks were Diner E, Gas Station,
  Mount Kalaga). Reverted.
- **PortofinoTower class** refactor. Topology I coded didn't match real
  building. Backups still exist:
  - `gtamaplib.py.bak_portofino_class`
  - `tools/extract_mesh_edges.py.bak_portofino`

### Commits this session

```
d919577 tools: auto-generated inventory of CLI scripts, endpoints, buttons, shortcuts
96d733e WIP: multicam dual-pane comparison (pre-pan/zoom-pane2-refactor)
a89bd58 canvas-ghosts refactor
1097c88 tiles: cleanup yanis.jpg + map_view_v2 test pages (Phase 4)
[mesh work commits]
52425bc portofino: pyramidal apex roofs on 3 turrets
```

16 commits ahead of origin/feature-svg-map — needs `git push` for backup.

### TODO next session

1. `git push origin feature-svg-map` (16 commits not backed up)
2. Portofino top floor refinements:
   - Maybe tiered balconies (need real measurements, not invented)
   - Maybe atrium ring open at CT level
3. Validate procedural meshes on multiple cams (check Sunshine Skyway from
   beach cams, HanksWaffles from Sandy Shores cams)
4. Apply mesh approach to other major buildings (AIWE class exists too?)

### Files / patches added this session

- `tools/TOOLS_INVENTORY.md` (auto-generated, ~1000 lines)
- `tools/generate_inventory.py`
- `tools/extract_mesh_edges.py` (FakeCam multi-pass)
- `tools/densify_portofino_edges.py`
- `gtamapdata/building_meshes_procedural.json` (1502 edges total)
- `gtamapdata/building_meshes.json` (handwritten LM-name edges, mostly superseded)
- Server endpoint `/api/building_meshes_procedural?cam=X`
- Frontend `[MESH-FRONTEND-V2]` markers in calib.html

### Patches still in repo root (cleanup needed)

```
patch_canvas_ghosts.py
patch_mesh_v1.py
patch_multicam_step15.py through step30.py
patch_strategic_v1.py  (reverted)
... (etc)
```
Should be deleted or moved to tools/patches_archive/ in next cleanup pass.
