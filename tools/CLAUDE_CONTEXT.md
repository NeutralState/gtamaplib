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
- **Bundle adjust RMS** : 2.95' (recovered from 5.78' via data fixes; baseline pre-port was 2.28')
- **Phase 12 workflow tools** : calibrate_cam.py + calibration_order.py + calibrate_session.py — the narrative method for new cam calibration
- **171 cams** (148 base + 23 rlx ported), **680 landmarks**
- **Last session** : 2026-05-14 (afternoon) — Two new audit tools commited (b24bc26): (1) `audit_leak_marker_quality.py` flagged 15 CASE A reprojection outliers on LEAK markings (top: Gas Station (Jason) → 4937 E Hwy 98 at 92.8'). (2) `audit_leak_influence_tree.py` BFS dependency tree from each LEAK cam — reveals 4 macro-clusters; AIWE/Diner cluster dominates (14 LEAK cams sharing reach to 22 calibrated cams + 186 LMs, depth 11). Metro/Tennis Stadium surprisingly low rank (22-23) — their sourced LMs are rarely marked anchor+high downstream. 65 of 92 LEAK cams have zero downstream reach. Earlier same day: ancestry discovery (87% of non-LEAK cams have zero all_leak markings) + calibrate_cam.py ANCESTRY-V1 tagging + audit_all_leak_opportunities.py tool. No data changes.

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

**2026-05-10 (Phase A + B + Phase 10 day):**
- ✅ **Phase A — confidence tiering** (`compute_confidence_tiers.py`).
  Classifies cams and landmarks into anchor/high/medium/low/unverified.
  Output `tools/generated/confidence_tiers.json` is the truth source
  for downstream tooling. Iterated v1 → v2 → v3 to get sensible tier
  distribution on real data: 79 anchor cams (LEAK), 156 anchor LMs.
- ✅ **Phase B — intake gate** (`intake_camera.py`). Read-only validator
  that solves a cam's params against the trustworthy LM skeleton
  (anchor+high tier), with a medium-LM fallback for sparse-anchor
  regions. Reports verdict (commit/review/reject) without modifying
  cameras.json. JSON audit record at `tools/generated/intake/<cam>.json`.
  Discovered Pylon (3) LM bug in first test (see Items pending).
- ✅ **Phase 10 — roll end-to-end**. Roll is now a real optimizable
  parameter across the entire pipeline. Five files patched, single
  atomic commit. Backward-compatible (cams without roll default to 0).
- ✅ **Bug fixes** committed: `tools/refine/refine_camera.py` path
  was off-by-one (dirname depth), and intake_camera's recommendation
  prose pointed at `tools/refine_camera.py` (doesn't exist).

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

- ✅ **Roll slider integration (Phase 10) — DONE 2026-05-10.** Full
  end-to-end: refine_camera, intake_camera, bundle_adjust, server.py
  /api/{project,optimize,save,update_landmarks}, calib.html slider.
  Ocean near Keys (N) validated 2.21' → 1.64' (26% improvement).
- ⏸ **Vanishing points + verticals UX** — rlx + martipk both push.
  Single biggest T3 unlock. Replace landmarks for fresh cam bootstrap.
  Multi-session feature.
- ⏸ **Port rlx upstream cams** — 24 new cams chez rlx pas chez nous.
  **UNBLOCKED 2026-05-10** by Phase 10 + intake_camera. Schema reality
  check: rlx's data is in `gtamapdata.py` (Python dicts, not JSON like
  ours). Format:
  ```python
  "[L1/N] Name": ((px,py,pz), (cx,cy,cz), (yaw,pitch,roll),
                  (hfov,vfov), (w,h), "source string")
  ```
  Roll is the 3rd ypr component (we now handle it).
- ⏸ **Pylon (3) landmark — bad pixels** (discovered 2026-05-10).
  Affects Chase (2) (A) calibration. The LM was triangulated with
  some bad pixel observations, polluting its xyz position. Causes
  ~6-8' residuals on cams that look at it. Manual fix needed:
  identify and remove/correct the bad source-cam pixels.

#### Medium

- ⏸ Search and sort landmarks (sort done in Phase 9.1, search exists)
- ⏸ **intake_camera v2 refinements** (post-T3 if needed). v1 works
  but verdict logic doesn't surface "solve made things worse" cases
  (Chase 2 A: anchor+high improved but medium-LM residuals exploded
  20×). Could add suspect-LM surfacing when sanity-residuals degrade
  significantly. Defer until T3 batch experience reveals if needed.

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

---

## ⚠ CRITICAL T3 PROBLEM (discovered 2026-05-09 late-night)

**The current bundle_adjust workflow does not handle batches of new cams.**

When the system has converged to RMS 2.32' on the existing 147 cams + their
landmarks, adding 24 new cams from rlx upstream:
- Initial RMS jumps to 15.42' (6.6× worse)
- Bundle adjust can only improve to 11.87' (23% improvement)
- The optimizer is **trapped near the old local optimum**
- Many existing cams that worked fine now show >100' outliers
  (e.g. Convertible 170', Port Gellhorn 01 123', Gas Station Chase 63')

**Root cause analysis**:
- Old optimum was tightly fitted to a specific set of cam params + landmark
  positions. New cams come with their OWN optimization (rlx's params), and
  those params point toward landmarks at OUR positions, which differ from
  rlx's positions by a median ~3m (max 948m for some entries).
- The optimizer cannot escape the old basin without large perturbations,
  which it doesn't try (xtol termination after 2 nfev when stuck).

**Schema divergence with rlx**:
- 447 of 685 landmarks (65%) differ by >0.5m between our state and rlx's
- 66 differ by >50m
- Our 69 unique landmarks not in rlx + rlx's 5 newer landmarks not in us
- This is 7 months of divergent optimization between two forks

**Why this matters for T3**:
T3 will bring 50-100+ new cams from leaks/trailers/screenshots simultaneously.
Each will come with pixel observations against landmarks. Our current
workflow cannot absorb this gracefully — the same dynamic we hit tonight
with 24 cams will be much worse with T3's volume.

**Possible solutions to explore (NEXT SESSION priority)**:

1. **Incremental workflow** — each new cam passes through `refine_camera.py`
   solo (with wide search radius) BEFORE being added to bundle_adjust pool.
   Validates each cam against the current system before introducing it.

2. **Cold-start mode in bundle_adjust** — flag to re-initialize all cam
   params from approximate values, allowing the optimizer to find a new
   global optimum instead of staying near the old one.

3. **Multi-seed bundle_adjust** — multiple random restarts of the
   optimizer with perturbations, keep the best result. Computationally
   expensive but escapes local optima.

4. **Confidence scoring + auto-refine** — after bundle_adjust, auto-detect
   cams with residuals >threshold and force a refine on them, then re-run.

5. **Sync strategy with rlx** — workflow to pull rlx's landmark updates
   regularly without breaking the local state. This is upstream of all
   the above — if our landmarks stay in sync with rlx, the new cams
   from any source will fit cleanly.

6. **Confidence-based bundle_adjust** — give different weight to
   constraints based on how trusted each cam/landmark is. New unverified
   cams get low weight initially, high-confidence LEAK cams get high weight.

**Workflow attempted tonight (FAILED — reverted)**:
- v1 port: copied rlx schema directly → server crashed (schema mismatch)
- v2 port: correct schema mapping, ported 24 cams + 5 landmarks +
  21 pixels → bundle adjust regressed to 11.87' RMS
- Full sync to rlx: replaced all landmarks with rlx's positions →
  Suspicious flag on LEAK cams (broken)

**Final state of session 2026-05-09**:
- Reverted to clean state (RMS 2.32', 147 cams)
- All session artifacts cleaned up
- This problem documented for next session

<!-- PATCH-2026-05-10-MULTISEED-LESSONS -->

**2026-05-10 update — multi-seed bundle_adjust ruled out**:

Tested option (3) "multi-seed bundle_adjust" from the strategy list above.
Two patches written and applied (multi-seed wrapper + budget tuning), both
technically correct; both confirmed the approach **does not fit the problem**.

What we observed:
- σ_xyz=5m, σ_angle=1°, σ_lm=2m perturbations produce initial RMS in the
  80-400' range. The TRF solver cannot recover from those magnitudes
  regardless of `xtol` (tested 1e-7 and 1e-4) or `max_nfev` (tested 200
  and 2000). Pass 1 quits at 2 nfev because the cost surface is too
  non-convex at that scale; the linear approximation TRF uses is wildly
  off, every trial step looks worse, trust region collapses.
- The bit-for-bit identical seed results between the v1 (tight) and v2
  (loose) tolerance runs proved the issue isn't tolerances — it's that
  perturbations large enough to escape basins create starting points the
  solver simply cannot traverse.

What this taught us about the actual problem:
- The 24-cam rlx-port trap (RMS 11.87') was NOT a local-optimum problem.
- It was a **data inconsistency** problem: rlx's cams point at where rlx's
  landmarks are, our landmarks differ from his by meters (447/685 LMs
  differ by >0.5m, 66 by >50m), so the optimizer faces literally
  contradictory constraints. No restart strategy fixes that.

**Strategies still on the table for T3**:
- (1) **Incremental refine-before-add** — each new cam validated solo
  against current LMs via `refine_camera.py` BEFORE entering the bundle.
  This forces new cams to fit OUR positions before they can affect
  anything else. Most aligned with the actual root cause.
- (5) **Sync with rlx landmarks** — periodically pull rlx's landmark
  deltas, accept whichever side has higher confidence per LM. Reduces
  divergence at the source.
- (6) **Confidence-based weighting** — new cams arrive with low weight,
  ramp up as residuals validate.

**Strategies removed from consideration**:
- (3) Multi-seed bundle_adjust (this session)
- (2) Cold-start mode (would have the same large-perturbation problem)
- (4) Auto-refine outliers (refine also fails from bad starting points)

## Last session log

<!-- PATCH-2026-05-10-PM-FULL-SESSION -->

### 2026-05-12 — Phase 11 verticals + bounds + tier weights + batch_optimize  <!-- ── SESSION-2026-05-12 ── -->

**13 commits today** (435e87d→c281ad1 spans 2 sessions, hashes for today's
commits: 5cd8765, b269dbf, 558b9c9, bbf3af7, 8b35f6c, a9aa09c, b93209d, c281ad1).

**Phase 11 verticals end-to-end**:
- Backend `/api/verticals?cam=NAME&xyz=...&ypr=...&hfov=...` — projects world-vertical
  lines (yaw-60° to yaw+60° step 0.5°, 20m tall at distance 10) through the cam,
  returns pixel pairs. Replicates rlx's `render_vertical_lines()` algo (gtamaplib L719).
- Frontend toggle button "⊕ verts" in calib.html, keyboard shortcut V. Yellow lines
  overlay the screenshot. Auto-updates when sliders move.
- **Visually validated** on Ocean near Keys (N): lines align perfectly with Seven Mile
  Bridge pillars. Calibration locked.
- Sentinels: `# ── VERTICALS-V1 ──`, `<!-- ── VERTICALS-FE-V1 ── -->`

**Phase 11.A — Physical z bounds**:
Server.py `optimize_camera()` had relative bounds (±50m on z from initial value).
This meant Yacht (2) with z=5 initial could solve to z=-45 (under sea level).
Fix: `lb[2] = max(xyz[2]-50, -5.0)` and `ub[2] = min(xyz[2]+50, 500.0)`.
Absolute floor at -5m prevents submarine solutions.

**Phase 11.B — Tier-weighted optimize**:
`optimize_camera()` was using binary weights (0.3 self-source, 1.0 indep). Now uses
tier weights: anchor=1.0, high=0.8, medium=0.4, low=0.1, unverified=0.0 (skipped),
multiplied by 0.3 if self-source (preserves anti-circular safeguard).
Loads `tools/generated/confidence_tiers.json` with graceful fallback.
Effect on bundle_adjust: 6.17' → 5.78' (~6% improvement, no regression).

**Phase 11.C — batch_optimize.py + safety**:
Calls server API per cam: Optimize → Save (optionally Update LMs if loss < threshold).
Supports `--tier`, `--cams`, `--apply`, `--update-lms`, `--save-threshold`,
`--regression-tolerance`, `--polish` (chains into bundle_adjust).
**Safety checks** added in same session: refuses save if loss_after > 10' (catastrophic)
or > loss_before * 1.05 (regression). First run revealed U-Turn (NE) at 866' loss
(garbage params) — correctly refused to persist.
Of 58 unverified cams: 9 successfully batch-optimized, 1 refused (U-Turn NE), 48
failed (<3 anchor+high obs each — these need manual marking in UI).

**rlx port v2 — done**:
- `port_rlx_inventory.py`: 24 cams unique-to-rlx with source, 27 unique LMs.
- `port_rlx_one_cam.py`: ports single cam with pixels (filters by our LMs).
  Pilot: Yacht (2) — 3 pixels, all to LMs we have. Optimized via UI with --refine-xyz
  initially gave z=-24m (sub-sea); Phase 11.A bound prevents this now.
- `port_rlx_batch.py`: ports the 23 sourced cams. Filters Minimap/Player/AIWE
  pixels (rlx skips these in his own solver — see gtamaplib L683, L1056). Result:
  9 portable with ≥3 usable pixels, 14 with 0 usable. Tier=anchor for most because
  source field matches LEAK pattern.
- **Cams ported are visualization-only**: most have few visible landmarks. They'll
  need manual marking via UI to be properly calibrated. RMS impact: 2.28' → 5.78'
  reflects this pollution.

**Four Seasons (BW) — circular dependency lesson**:
Originally triangulated from 1 cam (Handlebar SW), 8 cams mark the LM but only one
is source. Tried to re-triangulate from all 8 (best pair: Ocean near Keys N +
Rooftop Party, error 0.021m, xyz shifted ~17m). **rlx flagged this as circular**:
the 7 other cams' calibrations depend on Four Seasons (BW) being where it is, so
re-triangulating from them creates a feedback loop. Reverted via `git checkout`.
**Lesson**: anchor LMs stay anchored. Only retriangulate LMs that are genuinely
new or unanchored.

**Marti / Discord update**:
- Got **mapper+** from martipk (unilaterally — "haven't asked the others, inb4
  former staff", but "you definitely deserve it").
- Marti's note on Jason at Sea / Ocean near Keys (N) used as triangulation
  constraint: addressed by Phase 11 verticals (visual validation) + multi-cam
  triangulation already in `/api/update_landmarks` (with the source-cameras
  gate). Reply sent.
- rlx feedback on auto-triangulation: "too much work, the manual narration
  along the chain is more practical". Heeded. Don't try to fully automate the
  chain — narrate manually with tier system + verticals as guardrails.
- rlx confirms angular delta (arcmin) is the right metric — already what we
  use in `optimize_camera` and `bundle_adjust`.
- rlx's classification scheme (PLAYER / AIWE / MINIMAP / GIZMO / dir: prefix /
  high_precision overlay) is tribal knowledge, not stored in his code. Detectable
  via pixel markers ("Player", "AIWE", "Minimap (TL/N/BR)") but no urgent need
  to encode this until T3 arrives.

**Next session priorities** (updated 2026-05-12 — superseded by PM section below):
1. ~~Pylon (3) LM bug~~ — deferred (Alex said "men fous pour now")
2. ~~C — Verticals as solver constraints~~ — **ATTEMPTED, abandoned** (see PM section)
3. D — Multi-step relaxation — still on deck for next session
4. Update LMs in batch with whitelist — still on deck
5. Manual marking session — still relevant for the 48 sous-contraintes

<!-- ── SESSION-2026-05-12-PM ── -->
### 2026-05-12 (PM) — Data fixes, narrative workflow, RMS recovery

**More commits today** (c281ad1..d8296cb): 8 additional commits in PM session.

**C — Verticals as solver constraints — ATTEMPTED AND ABANDONED**:
- Patched server.py to accept marked vertical lines in optimize_camera, with
  residuals comparing observed vs predicted pixel direction (angle in arcmin).
- Math validated: reproj test on Yacht (2) showed cam.get_pixel(cam.get_pixel_direction(p)*D + cam.xyz) == p exactly.
- BUT: weight tuning was wrong. On Yacht (2) (3 LM constraints) the vertical
  line dominated and shifted xyz Y by 9m. On Leonida Keys 01 (Airplane) (X) (12
  constraints, loss 2'), adding a single vertical line caused loss to BLOW UP
  to 16' (-694%). The vertical-line residual was at a different scale than the
  LM residuals.
- **Reverted** the patch. C is harder than it looks — needs experimental weight
  tuning and probably soft-cap on the residual. Deferred.

**Data fixes (RMS 5.78' → 2.95', recovered 95% of pollution from 23 rlx-ports)**:

1. **BA filter `min_obs >= 3`** (commit 3453507 also includes this) — `bundle_adjust.py`
   now excludes cams with fewer than 3 observations. 15 cams dropped (all
   unverified, 1-2 pixels). Modest RMS impact (5.78' → 5.72') because most
   were also under-constrained, not pulling.

2. **Removed bad pixels on Police Chase (B) and (C) for White Billboard (Hamlet)**.
   Both had loss > 100 arcmin (vs ~10' for siblings E-I). Investigation: 10 Police
   Chase LEAK cams march along a road (Y -3566→-3272, same yaw ~190°). The pixels
   on B and C pointed to a different building (mismatch). Removed via direct
   pixels.json edit. RMS 5.72' → 5.48'.

3. **Reverted Motorboats (A) drift** — biggest single win. batch_optimize.py
   had shifted xyz Y by 15m (1518 → 1503), which made the 8 LMs that Motorboats (A)
   was solo-source for (C TNE/TSE/BNE/BSE/TSW/BSW, Container Crane (3), CC (3)
   (BB2), all z=24-77m) outliers at 60-90 arcmin. Reverting to pre-port params
   brought RMS 5.48' → **2.95'**.

**Self-source divergence — lesson learned**:
   When a cam is solo-source for several LMs, batch_optimize can pull the cam
   away from those LMs by privileging the anchor+high LMs (with weight 1.0 / 0.8)
   over self-source LMs (×0.3 weight). Cam moves, self-source LMs stay put,
   residuals explode.

   **Defense**: after any batch_optimize, check max self-source error. If >10',
   either revert the cam or re-triangulate those LMs (if z-elevation compatible).
   This check is now built into `calibrate_cam.py`.

   Other batch-optimized cams checked clean (Convertible, Highway Peacock A/B,
   Jason Duval 05, Leonida Keys 05 Boats, Motorboats B, Raul Bautista 03,
   Yacht 2). Only Motorboats (A) had the bug.

**Ocean near Keys (N) — LEAK ground truth from game debug overlay**:
   Alex screenshot'd Ocean near Keys (N) in the leak debug overlay, exposing
   the **true** params: xyz=(-3442.897, -7191.001, 0.501), ypr=(358.539, -2.172,
   -1.245), fov=(81.924, 52.054). Our previously refined params were within
   0.1° of all angles. Updated cameras.json to match exact LEAK values.
   Slight RMS uptick (2.95→2.97) because LM positions are noisy, the math
   optimum != ground truth.
   **Implication**: LEAK cams should never be optimized. Their game-engine
   params are ground truth, our solver only adds noise.

**White Billboard (Hamlet) re-triangulation attempt — abandoned**:
   Tried to retriangulate from 7 rays (6 Police Chase LEAK + Leonida Keys 01).
   Convergence poor (max residual 40' after solve). Reason: Police Chase cams
   stretch 243-537m from the LM along a road with yaw varying ±14° — rays
   diverge too much. The LM is too far for these cams to converge sharply.
   Some pixels may also be on different billboards (visual inspection needed).
   Lesson: 6 LEAK cams marching down a road != 6 independent observation angles.

**calibrate_cam.py — workflow narratif livré** (commit d8296cb):
   For a given cam, prints:
   - State (tier, source, marked LMs broken down by tier with per-LM errors)
   - Trusted loss (RMS over anchor+high)
   - **Self-source divergence check** (alert if any > 10' — the Motorboats A bug)
   - Suggested action:
     * `>=3 anchor+high`: "Run `batch_optimize.py --cams 'NAME'`"
     * `<3 anchor+high but some marked`: "Mark more anchor+high in UI"
     * `0 marked`: "Fresh start, open in UI, mark these likely-visible"
   - Likely-visible LMs (projected in-frame, sorted by distance)
   - Post-action checklist (when to Update LMs, when to bundle_adjust)

   Tested on 4 cases (Vice Beach A, Yacht 2, Yacht 1, Leonida Keys 02 Sidewalk).
   All produced sensible narrative output. Use it as `python3 tools/calibrate_cam.py "CAM NAME"`.

**Next session priorities** (updated 2026-05-12 PM):
1. **Test calibrate_cam.py on real new cam intake** — when a new cam arrives
   (T3 or otherwise), run the script and see if its suggestions actually lead
   to good calibration. The workflow is now coded but unproven on a fresh case.
2. **D — Multi-step relaxation** — still on deck (~1.5-2h).
3. **Phase 12 — LEAK ground truth dump tool** — Alex can see exact LEAK cam
   params via the game's debug overlay. Could be huge if he can dump all 87
   LEAK cams' true params and we replace ours. Would establish a hard floor
   on RMS that no solver can improve. Need to find if dump is possible vs
   screenshot-only.
4. **C — Verticals as solver constraints**, take 2 — requires weight tuning,
   probably soft-cap on residual, OR a different math formulation (compare
   projected top position vs observed, not directions).

<!-- ── PHASE-12-WORKFLOW ── -->
### 2026-05-12 (late PM) — Phase 12: Workflow tools

**3 new tools livrés** for narrative calibration of new cams.

**`tools/calibrate_cam.py "CAM_NAME"`** — per-cam state + action assistant:
- Tier, source, marked LMs broken down by tier with per-LM error in arcmin
- Trusted loss (RMS over anchor+high)
- Self-source divergence check (alerts on >10' — the Motorboats A bug)
- Suggested action based on what's marked:
  * ≥3 anchor+high → "Run batch_optimize"
  * <3 anchor+high but some marked → "Mark more anchor+high in UI"
  * 0 marked → "Fresh start in UI"
- Likely-visible LMs (projected in-frame, sorted by distance)
- Limitation: projection-based suggestions assume current params are roughly
  correct. For very-off cams, suggestions won't match the actual frame.

**`tools/calibration_order.py --tier unverified`** — greedy calibration order:
- Algorithm: score each cam by # anchor+high marked, pick highest, "promote"
  its self-source LMs (assume they become anchor-quality post-calibration),
  re-score remaining cams, repeat.
- Flags:
  * ✓ AUTO-OPTIMIZE READY (if ≥3 anchor+high AND loss < 10')
  * ⚠ BROKEN (≥3 anchor+high but loss > 10' — case U-Turn NE)
  * ◐ NEEDS MORE marking
  * ⭐ GOLDMINE (≥20 LMs total but ≤2 anchor+high — high-value targets)
  * ○ FRESH START (0 marked)
- Reveals goldmines: cams like Keys (56 LMs), Motorboats (A) (49), Mount Kalaga
  National Park 02 (Helicopter) (X) (38) — lots of obs but no anchor link.
- Limitation: loss check uses only anchor+high (not all LMs), so a cam with
  loss=0 on its single anchor+high but 866' on a medium LM (U-Turn NE) still
  flags as ✓. Worth refining in future.

**`tools/calibrate_session.py --cams "A,B,C"`** — interactive session:
- For each cam in list, shows the calibrate_cam.py report + prompt
- Commands:
  * [Enter] re-check after marking in UI
  * o  → run batch_optimize
  * u  → call Update LMs API (with server-side safety)
  * s  → skip to next
  * b  → run bundle_adjust (global polish)
  * q  → quit
- Server must be running on http://localhost:8765
- Use `--from-order` to drive session from calibration_order output
- Use `--limit N` to cap the session length

**Lessons discovered while building these**:

1. **Self-source divergence is a real bug class**: Motorboats (A) batch-optimized
   ended up 15m off from its own 8 self-source LMs (z=24-77m containers).
   Reverted via git. calibrate_cam.py now has built-in detection (>10' on any
   self-source LM → warning). Defense against future batch_optimize misuse.

2. **Goldmine cams are common in ported data**: when rlx ports a cam from his
   triangulate.py runs, it brings ~50 LMs all sourced from that cam (e.g. Keys
   has 56 LMs all self-source). These don't have anchor validation but the LMs
   are internally consistent (sub-5' max error to the source cam). Promoting
   such LMs to "high" requires independent validation from another cam, which
   often doesn't exist in our system.

3. **Tools' projection-based suggestions need anchor coverage**: when calibrate_cam.py
   tries to find "likely visible" anchors, it projects all anchor LMs and filters
   to in-frame. For cams with rough params (Leonida Keys 02 Sidewalk: 0 marked),
   nothing projects in-frame so the tool can't help. Reality requires user to
   visually identify what's in the scene first.

4. **calibrate_session.py's "from-order" mode** parses the output of
   calibration_order.py — a fragile coupling. If the latter's output format
   changes, parser breaks. Should refactor to JSON output mode for both later.

**The full narrative workflow now**:
```
# 1. See the optimal order to attack a batch of cams
python3 tools/calibration_order.py --tier unverified --limit 20

# 2. Open interactive session on those cams
python3 tools/calibrate_session.py --from-order --limit 20

# 3. For each cam, the session shows state + waits for user to mark in UI,
#    then offers Optimize / Update LMs / next / bundle_adjust / quit
```

This is the **method** for T3 intake. Replaces ad-hoc UI work with a guided
loop. Not yet stress-tested on a real fresh batch (T3 hasn't arrived) but
the pieces are in place.

**Next session priorities** (updated 2026-05-12 late PM):
1. **Run on real cams** — when T3 arrives or to attack one of the 3 goldmines
   (Keys / Motorboats A / Mount Kalaga 02), use the session tool. See what
   breaks in practice.
2. **JSON mode for the workflow tools** — refactor calibration_order to emit
   JSON so calibrate_session doesn't have to parse text.
3. **Address the projection limitation** — for cams with rough params, the
   "likely visible" suggestions don't match reality. Could add a tolerance
   mode (search wider than frame) or reverse-lookup (user types what they see).
4. **C — Verticals as solver constraints**, take 2 — still on deck if needed.
5. **D — Multi-step relaxation** — still on deck.

---



---



---

### 2026-05-10 (afternoon) — Phase A + B + Phase 10: confidence tiering, intake gate, roll end-to-end

**Goal**: build the T3 intake pipeline foundation. Establish a confidence
tier system, then a per-cam intake validator, then finally complete the
roll integration that yesterday's multi-seed detour distracted from.

**Phase A — confidence tiering (`compute_confidence_tiers.py`)**:
Classifies cams and LMs into 5 tiers. Started with strict criteria;
iterated through v1 → v2 → v3 to match the reality of the dataset.
Key finding: 244 single-source non-LEAK LMs were initially flagged
"low" (= problematic) but semantically belong in "unverified" (= can't
cross-validate yet). v3 split fixes this — `low` is now just the
genuinely-bad LMs (high residuals), `unverified` is single-source.

Final distribution on clean state:
```
anchor    79 cams  156 LMs
high       1 cam    2 LMs
medium    19 cams  273 LMs
low        1 cam    6 LMs    ← actually problematic (Starlet Motel Sign,
unverified 47 cams  243 LMs    ←   Oval Yellow, Radio Tower #1, Flamingo SRSW,
                              ←   Red Billboard, 1111 Lincoln Rd)
```

**Phase B — intake gate (`intake_camera.py`)**:
Per-cam read-only validator. Takes a cam name, filters its pixel
observations to anchor+high LMs (with medium fallback), runs scipy
optimization, reports verdict + audit JSON. Three verdicts: commit,
review, reject. Doesn't modify cameras.json — that step is still
`refine_camera.py --apply`.

First diagnostic test: Chase (2) (A) revealed that the cam fits
medium LMs (Juice Fruit Signs) at 0.9' but anchor+high LMs
(Pylon 3, Wildfire Scooters) at 6.86'. Two interpretations: bad cam,
or mis-positioned anchor LMs. User confirmed: Pylon (3) has known
bad pixels never fixed. **The intake tool diagnosed a real data bug
on its first non-trivial use.**

**Phase 10 — roll end-to-end** (the actual goal that yesterday's
multi-seed detour pushed):
- `tools/refine/refine_camera.py`: roll as 7th param, --no-roll flag
- `tools/intake_camera.py`: same, with audit JSON including roll
- `tools/bundle_adjust.py`: CAM_BLOCK 6→7, jacobian sparsity, output JSON
- `tools/server.py`: 4 query-string parsers, optimize_camera function
- `tools/calib.html`: Roll slider in UI between Pitch and hFOV

Critical test: bundle_adjust on the clean state (all rolls=0) gives
**identical RMS 2.2842'**, confirming the patch doesn't destabilize
the converged state. Vice Beach (A) refine: roll converges to 0.001°
(no spurious roll). Chase (2) (A): roll converges to -0.004° (not
the bug). Ocean near Keys (N): existing roll=-1.300° from manual
adjustment is now preserved + refined to -1.342°, **RMS 2.21' → 1.64'**
(26% improvement). This is the first concrete payoff of Phase 10.

**Pylon (3) bug surfaced**: medium LMs (Juice Fruit Sign group)
disagree with anchor+high LMs (Pylon (3), Wildfire Scooters) on
where Chase (2) (A) is pointed. Root cause: Pylon (3) has bad
source-cam pixels never fixed. Affects all cams looking at Pylon.
Filed under Items pending for next session.

**Things ruled out today**:
- Aggressive roll prior (option C from yesterday's A/B/C debate) —
  not needed. v1 of roll integration doesn't show micro-roll
  absorption on the clean state, confirming rlx's concern was
  hypothetical for our dataset.
- Investigating Pylon today — chosen to keep momentum on Phase 10.

**Final state**:
- 4 commits: Phase A (`435e87d`), Phase B (`7afd06d`), path fixes
  (`c9bae29`), Phase 10 atomic (`1844f23`)
- Ocean near Keys (N) refined and applied (cameras.json modified)
- All tooling now roll-aware end-to-end
- Next session is unblocked for rlx port v2

**Next session priorities** (updated 2026-05-10 PM):
1. **rlx port v2** — finally do it. Schema is now understood
   (`gtamapdata.py` Python dicts, roll in 3rd ypr position). 24
   cams unique to rlx, 5 new landmarks, 21 new pixels. Each ported
   cam → run intake_camera to validate against our skeleton →
   commit or defer.
2. **Pylon (3) LM bug** — investigate + fix the bad source pixels.
   Concrete, ~30-45 min, autonomous.
3. **Vanishing points + verticals UX** — biggest T3 unlock per
   Discord feedback. Multi-session.

### 2026-05-10 (morning) — Multi-seed bundle_adjust experiment (ruled out)

**Goal**: address T3 batch-absorption problem (option 3 from strategy list).
Approach: wrap bundle_adjust in a multi-seed driver that runs N optimizations
from perturbed starting points, keeps the best result. Hypothesis: random
restarts let the solver escape local optima the 24-cam port got trapped in.

**Patches written (both reverted at end of session)**:
- `patch_bundle_adjust_multiseed.py` — adds `--multi-seed N`, `--seed S`,
  `--sigma-xyz/angle/lm` flags. Wraps optimization in `run_optimization()`,
  outer loop runs seeds 0..N-1 (seed 0 = current values, others perturbed),
  picks lowest-RMS winner. Idempotent via sentinel V1.
- `patch_bundle_adjust_seed_budget.py` — diagnostic follow-up after seed 0
  results showed perturbed seeds quitting at 2 nfev. Adds
  `--max-nfev-perturbed 2000`, `--xtol-perturbed 1e-4`, separate solver
  budgets for seed 0 (tight) vs perturbed seeds (loose). Sentinel V2.

**Results on clean state (RMS 2.28')**:
- All 8 seeds: seed 0 won at 2.2842' (correctly — clean state already converged)
- Perturbed seeds (1-7) ranged from 19.5763' to 204.3197' final RMS
- Bit-for-bit identical results between v1 (tight) and v2 (loose) tolerances
  → tolerances were not the bottleneck; large initial residuals are the issue
- Total runtime: 0.1-0.2 min for 8 seeds (very fast)

**Diagnosis (see T3 critical section above for full writeup)**:
The multi-seed approach assumed the T3 problem was local-optimum trapping.
It isn't. The actual problem is data inconsistency between our landmarks and
rlx's — no restart strategy fixes contradictory constraints. Multi-seed,
cold-start, and auto-refine all share the same flaw and are removed from
the strategy list.

**Strategies still viable**: incremental refine-before-add, rlx landmark sync,
confidence-based weighting. See T3 critical section for details.

**Roll integration**: not started this session (planned, deprioritized in
favor of investigating T3 root cause). Still on the next-session list.

**Final state**:
- Reverted both patches via `cp tools/bundle_adjust.py.bak_pre_multiseed
  tools/bundle_adjust.py`, deleted both backups + both patch scripts.
- Working tree clean, nothing committed.
- CLAUDE_CONTEXT updated with multi-seed lesson learned (this entry +
  T3 section update).

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

**Next session priorities** (updated 2026-05-10):
1. **Roll slider Phase 10** — full pipeline integration. YANIS confirmed
   needed for Jason at sea + Chase 2. Touches save + optimize +
   bundle_adjust. ~2-3h focused work. Originally the goal of 2026-05-10
   session before multi-seed detour.
2. **Incremental refine-before-add for T3 absorption** — workflow that
   validates each new cam solo via `refine_camera.py` before bundle
   adjust pool entry. The leading T3 strategy after multi-seed was ruled
   out. Directly addresses data-inconsistency root cause.
3. **rlx port v2** — schema mapping written, port the 24 cams. Will
   exercise the incremental-refine workflow if (2) is done first.
4. **Vanishing points + verticals UX** — highest impact T3 feature per
   rlx + martipk Discord feedback. Multi-session.


---

<!-- ── SESSION-2026-05-13-CLEANUP ── -->
### 2026-05-13 — Repo cleanup (housekeeping, no code changes)

**Pre-cleanup state**: working tree had Ocean near Keys (N) cameras.json mods
uncommitted from previous PM session, 62 .bak files scattered across `tools/`,
`gtamapdata/`, and `tools/_archive/backups/` (4 of those tracked by git despite
.gitignore covering `*.bak*` — predated the rule). 5 local branches, 3 of them
merged-and-stale.

**Actions** (3 commits, all pushed to `origin/feature-svg-map`):

1. **`f2dca87` — Ocean near Keys (N) LEAK ground truth committed**:
   `gtamapdata/cameras.json` reflects exact game-debug-overlay params
   (xyz=(-3442.897, -7191.001, 0.501), ypr=(358.539, -2.172, -1.245),
   fov=(81.924, 52.054)). Refinement of ~0.1° from previously-converged values.
   No RMS impact (2.95→2.97 from yesterday already accounted).

2. **`fdf0736` — .bak files purged**:
   - 49 untracked .bak files in `tools/_archive/backups/` deleted locally
     (gitignored, no commit needed for these)
   - 9 untracked .bak files in `tools/` and `gtamapdata/` deleted locally
     (recent backups from yesterday's PM session, e.g. `*.bak_pre_phase12`,
     `*.bak_pre_onk_groundtruth`, `*.bak_pre_session_pm`)
   - **4 tracked .bak files** in `tools/_archive/backups/` removed via
     `git rm` (predated the `*.bak*` .gitignore rule):
     * `calib_fresh.html.bak_addpx`
     * `gtamapdata.py.bak_xyz_none`
     * `server.py.bak`
     * `server.py.bak2`
   - Net diff: 4 files removed, 2830 lines deleted from tracked history

3. **Branch cleanup** (local only, not committed):
   - Deleted `feature-rotating-minimap` (merged into feature-svg-map)
   - Deleted `recover-minimap` (merged into feature-svg-map)
   - **Kept**: `main` (GitHub default branch, useful as local reference),
     `item-3-intersect-rays` (not merged technically but functionality is
     shipped in feature-svg-map via Phase 8.1/8.2 — leave for now)
   - Result: `git branch` is now `feature-svg-map *`, `item-3-intersect-rays`, `main`

4. **macOS .DS_Store cleanup** (local only):
   - Deleted 8 `.DS_Store` files across the repo (all gitignored, none tracked).
   - macOS will recreate them as needed; no impact on git.

**Things investigated, decided to keep**:
- `tools/_archive/backups/calib_fresh.html` (56KB, 1189 lines): an older
  pre-bundle-adjust-v2 checkpoint of the calib tool (current is 3542 lines).
  Was deliberately archived in commit `a3851f6 chore: archive applied minimap
  patches and stale files`. Not referenced in code, no CLAUDE_CONTEXT mention,
  but kept as historical reference since `_archive/backups/` is gitignored and
  it costs nothing locally.
- `__init__.py` at repo root (0 bytes, tracked since Initial commit): empty
  Python package marker. Not referenced anywhere (the grep hits were just
  docstring `"Run from gtamaplib-main/"` strings). Convention from rlx's
  initial commit; safer to leave alone — 0 bytes harmless.

**Final state**:
- Working tree clean
- `feature-svg-map` is `origin/feature-svg-map` (3 commits ahead of pre-session HEAD `2b43446`, all pushed)
- No more .bak files anywhere
- 3 local branches instead of 5
- Repo ready for next productive session

**No data or solver changes this session**. RMS still ~2.95-2.97' on
171 cams, 680 LMs. Phase 12 workflow tools unchanged.

**Next session priorities** (unchanged from 2026-05-12 late PM):
1. Test calibration_order + calibrate_session on a real goldmine cam
   (Keys 56 LMs / Motorboats A 49 LMs / Mount Kalaga 02 Helicopter 38 LMs)
2. JSON output mode for calibration_order.py (replace fragile text-parsing
   coupling in calibrate_session.py)
3. Fix calibration_order's loss check (currently uses only anchor+high, so
   U-Turn (NE) flags as ✓ despite 866' loss on medium LM)
4. C — Verticals as solver constraints, take 2 (weight tuning experiment)
5. D — Multi-step relaxation
6. Pylon (3) LM bug (deferred but still extant)


---

<!-- ── SESSION-2026-05-13-DEPENDENCY-REFACTOR ── -->
### 2026-05-13 (afternoon) — Phase 13: gtamaplib as dependency (separate branch)

**Trigger**: rlx Discord message ("maybe easier, since it's not a fork, to
make gtamaplib a dependency, and keep the transforms external to it").

**Branch**: `feature-gtamaplib-dependency` (pushed to origin, NOT merged).
The main branch `feature-svg-map` is untouched and remains usable as-is
until the refactor is validated in real use.

**Architecture**:

Before:
```
gtamaplib-main/
├── gtamaplib.py          ← copy of rlx's lib (with 3 cosmetic mods)
├── gtamaputils.py        ← copy of rlx's lib (with 1 cosmetic mod)
├── gtamapdata.py         ← OUR JSON loader (custom)
└── tools/server.py       ← `sys.path.insert(0, REPO); import gtamaplib as ml`
```

After:
```
gtamaplib-main/
├── vendor/
│   └── gtamaplib/        ← rlx's repo as git submodule (pinned a1003c6)
│       ├── gtamaplib.py  ← pristine, untouched
│       ├── gtamaputils.py
│       └── gtamapdata.py ← rlx's hardcoded data (IGNORED via hijack)
├── gtamapdata.py         ← OUR JSON loader (unchanged)
├── gtamaplib_setup.py    ← sys.modules hijack (NEW)
└── tools/server.py       ← `sys.path.insert(...); import gtamaplib_setup;
                              import gtamaplib as ml`
```

**The hijack** (in `gtamaplib_setup.py`):

1. Adds `vendor/` (not `vendor/gtamaplib/`) to sys.path so Python sees
   `gtamaplib` as a **package** (vendor/gtamaplib/__init__.py exists).
   This is essential: rlx's lib uses `from . import gtamapdata as md`,
   which requires package context, not module context.
2. Pre-populates `sys.modules['gtamaplib.gtamapdata']` with OUR root-level
   `gtamapdata.py` BEFORE rlx's `gtamaplib.py` is executed. When rlx's lib
   runs `from . import gtamapdata`, Python finds our pre-registered module
   instead of loading vendor/gtamaplib/gtamapdata.py (with his hardcoded
   data).
3. Re-exports `gtamaplib.gtamaplib`'s public API onto the package
   namespace, so existing `import gtamaplib as ml; ml.Camera(...)` calls
   keep working (without this, `ml.Camera` doesn't exist because rlx's
   `__init__.py` is empty).

**Verified at import-time**:
- `import gtamaplib as ml` loads from `vendor/gtamaplib/__init__.py`
- `import gtamapdata as md` loads from `gtamapdata.py` (ours)
- `md.cameras` = 171 entries (ours, not rlx's ~150 hardcoded)
- `md.landmarks` = 680 entries (ours)
- `ml.Camera`, `ml.intersect_rays`, `ml.find_camera`, etc. all accessible

**Scripts patched** (21 total) via `patch_vendor_hijack_inject.py`:
Each got `import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]`
injected right after the existing `sys.path.insert(0, ...)`.

**Bonus fix**: 9 scripts in `tools/audit/` had a pre-existing path bug
(gotcha #11 of this doc) — `dirname(dirname(__file__))` gave `tools/`
instead of the repo root. Fixed to `dirname×3` in the same patch.
These scripts were previously unrunnable from CLI without
`PYTHONPATH=. python3 ...` workaround.

**Tested end-to-end**:
- `tools/calibrate_cam.py "Ocean near Keys (N)"` renders the full report
  with LEAK ground truth params (matching this morning's commit f2dca87)
- `tools/calibration_order.py --tier unverified --limit 3` correctly
  classifies unverified cams (U-Turn (NE) ✓ AUTO-OPTIMIZE READY, etc.)
- `tools/audit/check_camera_consistency.py` now runs from CLI for the
  first time (path bug + hijack both fix it)
- `import tools.server` resolves cleanly (server boots fine,
  "gtamaplib loaded ✓ — Leak cams: 92 — Leak-anchored landmarks: 60")

**Commits on `feature-gtamaplib-dependency`** (4 progressive, all pushed):
1. `5840714` — submodule + setup file
2. `29cd137` — remove local gtamaplib.py + gtamaputils.py (-3054 lines)
3. `723f9da` — patch 21 scripts (vendor hijack + audit/ path fix)
4. `dbbc1a1` — archive patch script

**How to update vendor/gtamaplib/ when rlx pushes new commits**:
```
cd vendor/gtamaplib && git pull origin main && cd ../..
git add vendor/gtamaplib
git commit -m "Bump vendor/gtamaplib to <commit_sha>"
```

**Convention for NEW scripts** that use gtamaplib (so we don't forget the
hijack):
```python
GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]
import gtamaplib as ml
```

**Merge plan**:
- Use feature-gtamaplib-dependency for next session(s) and confirm
  nothing breaks (run server, do calibrations, run a bundle_adjust,
  etc.)
- When confident: `git checkout feature-svg-map && git merge
  feature-gtamaplib-dependency && git push`
- Alternative: continue all new work on feature-gtamaplib-dependency
  and treat it as the new mainline; merge later when there's nothing
  to lose by doing so.

**Risks worth keeping in mind**:
1. **sys.modules hijack is magic** — when it breaks, the error message
   may be cryptic. Keep `gtamaplib_setup.py` simple and well-commented.
2. **Submodule pin discipline** — if rlx pushes a breaking change to
   `gtamaplib.py`, our scripts may break the moment we bump vendor.
   Test before bumping in production.
3. **Forgetting the hijack import in new scripts** — would silently
   fail because there's no longer a local `gtamaplib.py` to fall back
   on; the script will get `ModuleNotFoundError` immediately.

**Next session priorities**:
1. **Real-world test** of the dependency setup. Run the UI, do a calib
   session, run bundle_adjust, exercise everything. If clean, merge.
2. Decide whether to merge `feature-gtamaplib-dependency` into
   `feature-svg-map` (the obvious move once tested) or treat the new
   branch as the mainline.
3. Pre-T3 priorities (still relevant, unchanged from earlier today):
   - Run calibrate_session on a real goldmine cam (Keys / Motorboats A
     / Mount Kalaga 02 Helicopter)
   - JSON output mode for calibration_order.py
   - Fix calibration_order's loss check (U-Turn (NE) flags ✓ despite
     866' on a medium LM)
   - C — Verticals as solver constraints, take 2
   - D — Multi-step relaxation
   - Pylon (3) LM bug

**State at end of session**:
- `feature-svg-map`: clean, untouched by the refactor (this doc patch
  is the only delta vs cleanup commit)
- `feature-gtamaplib-dependency`: 4 commits ahead, pushed to origin
- Both branches usable; pick depending on whether you want the new
  architecture


---

<!-- ── SESSION-2026-05-14-LEAK-ANCESTRY ── -->
### 2026-05-14 — LEAK ancestry analysis: structural dataset problem identified

**Setup**: Started Thursday midday after Tuesday's big session (cleanup +
dependency refactor). Refactor branch `feature-gtamaplib-dependency`
still not merged; working on `feature-svg-map` (mainline).

**The discovery**

A LEAK cam has its xyz, ypr, AND fov **fixed** to the exact game-engine
values (extracted from the debug overlay). They are NOT calibrated — they
ARE ground truth. So any LM triangulated 100% from LEAK cams is also
ground truth (modulo marker pixel precision).

Ran an ancestry analysis on the 680 landmarks:

| Class | Count | % | Meaning |
|---|---|---|---|
| `all_leak` | 156 | 23% | 100% LEAK-sourced — ground truth |
| `partial_leak` | 63 | 9% | Mixed: ≥1 LEAK in sources |
| `no_leak` | 456 | 67% | 0% LEAK — pure calibration-derived |
| `no_source` | 5 | <1% | Orphan, no source_cameras field |

Then ran an aggregate over the 79 non-LEAK cams' marked LMs (1431 marker
pixels total):

| Marker by ancestry class | Count | % |
|---|---|---|
| markers on `all_leak` LMs | 16 | **1.1%** |
| markers on `partial_leak` LMs | 109 | 7.6% |
| markers on `no_leak` LMs | 844 | **59.0%** |
| markers on `no_source` LMs | 461 | 32.2% |

**87% of non-LEAK cams (69 of 79) have ZERO all_leak LMs marked.**
This includes all the pillar cams: Prison, Vice Beach A/B, Beach,
Motorboats A/B, Keys, Venetian Islands, Brickell, etc.

**Why this matters**: those pillar cams are calibrated entirely against
LMs that themselves carry residual calibration error. Their "anchor"
tier is illusory — they're anchored against fuzziness. Solver can
optimize them to RMS 0', but the absolute positions still drift away
from real game-engine coordinates. This is likely why bundle adjust
plateaus at ~2.95' and won't drop below 2'.

**Solution direction**: NOT a solver fix. NOT exotic retriangulation.
Manual marker work in the UI on pillar cams, prioritizing LEAK LMs
that are likely-visible in each cam's frame.

**Tools delivered this session**

1. `tools/audit/audit_all_leak_opportunities.py` — read-only audit.
   For each non-LEAK cam with zero `all_leak` markings, project all
   `all_leak` LMs into the cam's frame and list those that fall
   in-bounds. Sort cams by opportunity count.

2. `calibrate_cam.py` upgrade [ANCESTRY-V1]: the "LIKELY VISIBLE LMS"
   section now tags each suggestion with its LEAK ancestry and re-sorts
   so `all_leak` appears first.

   Before:
   ```
   [anchor]  dist=  2233m  px≈( 1635,  924)  The Ritz-Carlton Coconut Grove (S)
   [high ]  dist=  5607m  px≈( 1131,  933)  Icon at South Beach
   ```

   After:
   ```
   [anchor LEAK]  dist=  2233m  px≈( 1635,  924)  The Ritz-Carlton Coconut Grove (S)
   [high   ----]  dist=  5607m  px≈( 1131,  933)  Icon at South Beach
   ```

   Labels: `LEAK` = all_leak, `part` = partial_leak, `----` = no_leak,
   `????` = no_source.

**Top 12 realistic opportunities** (10+ LMs already marked AND 5-30
all_leak likely-visible — i.e. cams that ARE well-calibrated enough for
projections to be trustworthy, with substantial LEAK anchoring upside):

| Cam | Marked | LEAK visible |
|---|---|---|
| Highway (Peacock Bay) (A) | 10 | 27 |
| Raul Bautista 03 (Motorboat) | 14 | 23 |
| Vice City 03 (Basketball) | 67 | 16 |
| Beach | 35 | 13 |
| Vice Beach (A) | 45 | 12 |
| Vice Beach (B) | 72 | 12 |
| Jet Ski | 15 | 11 |
| Vice City Postcard | 60 | 11 |
| Convertible | 14 | 9 |
| Skyline | 32 | 8 |
| Prison | 37 | 6 |
| Grassrivers 02 (Watson Bay) | 39 | 6 |

That's ~154 markings to do (likely 5-15 min per cam in the UI). Should
substantially improve global RMS once done across these pillars.

**Cams with anomalously high "visible" counts** (filtered OUT of the
realistic list because projection is unreliable when cam params are
loose): Television (1 marked, 127 visible), Mount Kalaga 02 Helicopter
(38, 123), Ambrosia 04 Fires (49, 115), Mount Kalaga 04 (5, 100),
Motorboats A/B. These project lots of LMs in-frame because their fov
is wide and/or their params are off. Calibrate them properly first
before trusting these projections.

**Strategic note**: this analysis changes the way I think about the
solver loss. RMS of 2.95' on 171 cams looks "good" but most of the
constraint network is held together by no_leak LMs anchored on
no_leak LMs (transitive flou). Real ground-truth anchoring is sparse.
T3 cams will exacerbate this if they're all calibrated against existing
no_leak LMs instead of being grounded into all_leak (or new LEAK cams
if rlx releases more debug overlay data for T3 zones).

**Commits this session**: TBD (this patch + tool commits).

**Next session priorities**:

1. **Marking session on Highway (Peacock Bay) (A)** first (best ratio:
   10 marked, 27 LEAK visible). Use `calibrate_cam.py` for the LEAK-
   first ordered suggestions, mark in UI, save, re-run to verify drop
   in self-source divergence.
2. Then iterate down the top-12 list above. Goal: every pillar cam
   should have ≥3 all_leak LMs marked.
3. After marking, re-run bundle_adjust to see if RMS drops below 2.5'.
4. Older priorities still pending: JSON output for calibration_order;
   fix calibration_order's loss check (U-Turn (NE) false positive);
   C-verticals take 2; D-multi-step relaxation; Pylon (3) bug.
5. **Eventually** decide whether to merge `feature-gtamaplib-dependency`
   into feature-svg-map (still pending real-world test).

**State at end of session**:
- Branch: `feature-svg-map`
- Working tree: clean
- New tool: `tools/audit/audit_all_leak_opportunities.py`
- Upgraded tool: `tools/calibrate_cam.py` (ANCESTRY-V1)
- No data modifications, no calibration changes, no bundle_adjust runs


---

<!-- ── SESSION-2026-05-14-CLUSTERS ── -->
### 2026-05-14 (afternoon) — LEAK marker audit + dependency tree clusters

**Setup**: Continuing the same day as the morning's ancestry discovery
session. Goal was first to check if LEAK marker errors might invalidate
the ground-truth assumption, then to map the dependency tree structure
so we know which LEAK cams matter most.

**Pre-session sanity check**: 4 files use `LEAK_CAMS` variable.
3 use date-based detection (`bundle_adjust.py`, `server.py`,
`audit/audit_fixed_landmarks_quality.py`) — consistent with our analysis
across all recent sessions. 1 uses a hardcoded list
(`audit/audit_leak_consistency.py`) which incorrectly includes
Vice Beach A/B and is missing ~40 newer LEAK cams. The 3 production
files are NOT affected; `audit_leak_consistency.py` is the only one
out of sync — flagged for cleanup or deletion in a later session.
The new audit tools use date-based detection so they're consistent
with the production state.

#### Part 1 — LEAK marker quality audit

**Tool**: `tools/audit/audit_leak_marker_quality.py`

For each marker pixel on a LEAK cam, compute reprojection error in
arcmin. Because LEAK cam params are fixed (extracted from game debug
overlay, not optimized), any error is either:
  - **CASE A** (cam IS source of LM): geometrically impossible to
    have non-zero error at triangulation time → drift now means the
    marker was edited or the LM xyz was changed without retriangulation
  - **CASE B** (cam NOT source of LM): error reflects tension between
    this view and the triangulated LM position somewhere else

**Audited 311 markings across 92 LEAK cams** (some LEAK cams have no
complete params and were skipped).

Distribution:
- err < 1':   176 (159 A, 17 B) — clean
- err 1-3':    46 (40 A, 6 B)
- err 3-10':   62 (45 A, 17 B)
- err 10-30':  18 (12 A, 6 B) — outliers
- err 30-60':   6 (2 A, 4 B) — outliers
- err ≥ 60':    3 (1 A, 2 B) — severe

**15 CASE A outliers** (the most actionable — these are bugs):

| err | cam → LM |
|---|---|
| 92.8' | Gas Station (Jason) → 4937 E Hwy 98 (Gas Station) (SE) |
| 39.1' | Diner (S) → Easy Inn Sign |
| 33.2' | Diner (E) → Billboard (Hank's Waffles) (BE) |
| 30.0' | Diner (NE) → White Pole |
| 24.7' | Diner (E) → White Pole |
| 23.4' | Diner (SE) (A) → Traffic Sign |
| 21.6' | Car Wash → Tall Double Billboard |
| 18.9' | Gas Station (Lucia) → Oval Yellow Sign |
| 18.6' | Diner (NE) → Domed Hills Sign (TW) |
| 18.2' | Welcome Center (E) → Art Deco Welcome Center (S) |
| 17.2' | Diner (E) → Domed Hills Sign (TW) |
| 13.4' | Welcome Center (W) → Art Deco Welcome Center (S) |
| 11.4' | Diner (NE) → Mount Waffles (TW) |
| 10.9' | Car Wash → Springfield Community Church (CW) |
| 10.0' | Diner (N) → Mount Waffles (TW) |

**Patterns observed**:
- Diner (E) appears in 3 outliers — possibly a systematic marker offset
  issue on that one cam, OR the LMs themselves (White Pole, Domed Hills
  Sign, Billboard) have incorrect xyz
- "Mount Waffles (TW)" appears twice with Diner cams (NE, N) at 10-11' —
  borderline outliers suggesting that specific LM may have minor xyz drift
- "Art Deco Welcome Center (S)" appears in BOTH Welcome Center (E) and
  Welcome Center (W) — strongly suggests the LM xyz is offset; the
  Welcome Center cams agree with each other but not with their own LM

**CASE B severe outliers** (top 3):
- 166.4': Diner (SE) (A) → White Pole — White Pole xyz is suspect across
  multiple Diner views
- 98.1':  Diner (E) → Mount Mountain
- 54.1':  Police Chase (F) → White Billboard (Hamlet) — and same LM at
  47.4' (Police Chase H), 46.3' (Police Chase G), 35.5' (Police Chase E),
  25.7' (Police Chase I). FIVE Police Chase cams agree that this LM is
  in tension. Strong evidence that "White Billboard (Hamlet)" has a
  bad xyz.

#### Part 2 — LEAK influence tree

**Tool**: `tools/audit/audit_leak_influence_tree.py`

BFS dependency tree from each LEAK cam, using **B-strict** criterion:
cam C depends on cam B if C marks an LM L at tier `anchor` or `high`
AND B is in L.source_cameras. Each generation alternates LMs ↔ cams.
JSON saved to `tools/generated/leak_influence_tree.json` (regenerable,
not git-tracked).

**4 macro-clusters in the dataset**:

| Cluster | LEAK cams in it | Reach (cams / LMs) | Depth |
|---|---|---|---|
| Main (AIWE + Diner + Car Wash + Gas Stations + Hedge B) | 14 | 22 / 186 | 11 |
| Port / Sidewalk (Jason) (E) | 2 | 10 / 219 | 5 |
| Glitch (A) / Highway (NE) / Tennis Court (NE) | 3 | 4 / 26 | 5 |
| Airport (X) / Hangar (A) / Metro (SE) (A) (4K) / Tennis Stadium (4K) | 4 | 3 / 18 | 7 |
| Welcome Center (E/W) | 2 | 2 / 8 | 3 |
| Diner (SE) (A/B) | 2 | 1 / 3 | 3 |

**65 of 92 LEAK cams** have ZERO downstream cam reach. They either:
- Have no markings (Auto Shop x4, Boat Jason, Diner, Farm, Hangar B/C,
  Hedge D, Highway E, etc.) — reserve of potential anchors
- Have markings only at tier medium/low/unverified — not part of the
  trusted anchor graph
- Source LMs that nobody marked at anchor+high

**KEY STRATEGIC REVERSAL**: I expected Metro (SE) (A) (4K) and
Tennis Stadium (4K) to be high-influence because they source the
Brickell anchors (Ritz-Carlton, Nine at Mary Brickell, Four Seasons
40NE). They rank **22 and 23 out of LEAK cams**, with only 3 downstream
cams. Why: these LMs they source are NOT marked anchor+high on most
downstream cams. The Brickell anchors exist but are not pulled into
the trusted constraint network. **Marking these Brickell LMs as
anchor+high on more cams (especially Vice Beach A/B, Prison) would
massively elevate Metro/Tennis influence and likely improve global RMS.**

**Within the Main cluster** (the 14 LEAK cams with reach 22/186):
- All 14 reach the same 22 calibrated cams, but via different paths
- AIWE and Car Wash differ by exactly 1 cam (each includes the other)
- AIWE sources 70 LMs directly in gen 1 — by far the biggest direct
  contribution. Gen 2 onwards reaches diminishingly via interlocking
  rebounds (LM → cam → LM → cam ...)
- Total tree depth of 11 = 5-6 hops of indirection from the LEAK cam
  to the most-downstream LM
- **AIWE markers must be impeccable** — any drift cascades to 22 cams

#### Strategic implications for next sessions

1. **Direct marker fixes** are high-leverage on the AIWE/Diner cluster
   (gen 1 of 70 LMs for AIWE alone). The 15 CASE A outliers from
   Part 1 are the obvious starting set.
2. **Most influence is at gen 1** (direct LMs sourced). The deep tree
   adds reach but each subsequent generation has diminishing weight.
3. **Marking sessions on pillar cams** (Vice Beach A/B, Prison, etc.)
   to add Brickell LEAK LMs (sourced by Metro/Tennis) would activate
   the currently-low-influence cluster 4 and probably drop global RMS.
4. **65 LEAK cams with zero reach** is a reserve — most are unused or
   only marked at low/unverified tier. Some may be geographic isolates,
   others may just need their existing markings re-tiered to anchor/high.

#### Pending priorities (carried over)

1. Marking session on Highway (Peacock Bay) (A) — best all_leak
   opportunity from earlier today (10 marked, 27 LEAK visible)
2. Fix the 15 CASE A outliers (this session's main actionable list)
3. JSON output for calibration_order.py
4. Fix calibration_order's loss check (U-Turn (NE) false positive)
5. C — Verticals as solver constraints, take 2
6. D — Multi-step relaxation
7. Pylon (3) LM bug
8. Decide whether to merge `feature-gtamaplib-dependency` into
   feature-svg-map (still pending real-world test)
9. Cleanup: `audit_leak_consistency.py` has obsolete hardcoded LEAK list,
   either fix it or delete it

#### State at end of session

- Branch: `feature-svg-map`
- Working tree: clean
- New tools (commit b24bc26):
  - `tools/audit/audit_leak_marker_quality.py`
  - `tools/audit/audit_leak_influence_tree.py`
- Generated artifact (not tracked):
  - `tools/generated/leak_influence_tree.json`
- No data modifications, no calibrations, no bundle_adjust runs



<!-- [CLAUDE-CONTEXT-2026-05-14-PM] -->
### Session 2026-05-14 PM+evening — Priority ranking, 8 marker fixes, Yanis V12, adaptive map dots

After the morning's clusters analysis (b24bc26), this session shipped
the third audit tool, applied concrete marker quality fixes from the
top of its rankings, upgraded the map to yanis V12, and added
zoom-adaptive sizing to the SVG map dots.

#### Part 1 — Composite priority ranking (commit 4dd0d75)

Built `tools/audit/audit_leak_priority_ranking.py` to cross-reference
the influence tree (BFS reachability) with the marker quality outliers,
and classify each LEAK cam into 4 quadrants:

- **HIGH_PRIORITY** (8 cams) — high influence + has outliers → fix urgent
- **HIGH_IMPACT**   (10 cams) — high influence + no outliers → protect
- **LOW_PRIORITY**  (10 cams) — low influence + has outliers → fix later
- **IGNORE**        (64 cams) — low everywhere → leave alone

Sectoral score design (3 independent dimensions, not weighted-aggregate):
direct contribution (gen1 LMs sourced), downstream reach (cams + LMs in
transitive closure), outlier risk (CASE A/B count + max severity).

Top of HIGH_PRIORITY list (sorted by direct contribution then severity):

```
   cam                                  gen1  g1L  dn  dL   cA  cAm   cB  cBm
   Gas Station (Lucia)                  23   19   22  186   1  18.9   1  25.5
   Diner (NE)                           10   10   22  186   3  30.0   1  19.0
   Diner (N)                             8    8   22  186   1  10.0   0   0.0
   Diner (E)                             7    7   22  186   3  33.2   1  98.1
   Gas Station (Jason)                   6    6   22  186   1  92.8   0   0.0
   Diner (S)                             5    5   22  186   1  39.1   0   0.0
   Car Wash                              5    4   22  186   2  21.6   0   0.0
   Hedge (B) (X)                         1    1   22  186   0   0.0   1  12.2
```

All 8 are in the Main cluster — they each share reach to 22 calibrated
cams and 186 LMs. Their outliers cascade further than other cams' would.

JSON written to `tools/generated/leak_priority_ranking.json`
(gitignored, regenerable).

#### Part 2 — Marker quality fix workflow (commits 80557ed, 993a0d4, 0f2304b, c5bc765)

Validated a complete workflow for fixing CASE A outliers:

1. Identify outlier in `audit_leak_marker_quality.py` output
2. Open the source cam(s) in the UI
3. Visually verify the marker is on the right physical object
4. Either:
   - **Snap marker(s) to current projection** if xyz is good
     (witness from another cam at low err confirms xyz)
   - **Retriangulate** if 2+ source markers visually agree on the same
     point but xyz has drifted
5. Re-run audit to confirm

Path bug fix on `tools/refine/retriangulate_landmark.py`:
`dirname×2` → `dirname×3` to match other refine/ scripts and make the
CLI runnable from repo root without PYTHONPATH workaround (commit 993a0d4).

##### Concrete fixes applied

**4937 E Hwy 98 (Gas Station) (SE)** (commit 80557ed):
- AIWE marker fine-tuned (sub-pixel refinement)
- Auto-retriangulate triggered
- xyz: `[-6330.736, 2764.765, 17.649]` → `[-6330.5658, 2764.9323, 17.6587]`
- error_m: 0.943 → 0.475 (halved)
- Gas Station (Jason) reproj err: ~37px → 18.5px (also halved)
- Top CASE A outlier 92.8' → 46.4'

**Art Deco Welcome Center (S)** (in 0f2304b):
- Both Welcome Center (E) and (W) markers snapped to projection
- WC (E): `(167, 149)` → `(169.2, 155.8)`, err 7.2px → 0.1px
- WC (W): `(1518, 72)` → `(1519.4, 67.0)`, err 5.4px → 0.2px
- xyz unchanged (error_m 0.069m already excellent)
- Witness Park at 0.4px confirmed xyz was correct — markers were
  the only thing needing adjustment
- Two CASE A outliers eliminated (18.2' and 13.4')

**White Pole** (in 0f2304b):
- Diner (NE) and Diner (E) markers snapped to projection
- **Removed Diner (SE) (A) marker** — was at 166.4' (worst CASE B
  outlier of the dataset); the cam was marking a different physical
  pole, name collision confirmed by retriangulation showing the 3 cams
  produce a 68.2' optimum vs 11.3' optimum without Diner (SE) (A)
- Retriangulated from 2 remaining cams
- xyz: `[-6092.565, 4474.75, 27.138]` → `[-6076.247, 4469.9728, 29.3709]`
  (17m movement — long-distance triangulation drift correction)
- Diner (NE) reproj: 30.0' → 11.3' (acceptable, 100m+ distance limit)
- Diner (E) reproj: 24.7' → 10.4' (slight regression but xyz is now
  geometrically consistent with markers)

**Domed Hills Sign (TW)** (in c5bc765):
- Diner (NE): `[1773.5, 250]` → `(1770.7, 243.2)`, err 7.4px → 0.1px
- Diner (E):  `[1256, 506]`   → `(1257.9, 509.6)`, err 6.8px → 2.7px
- Witness Diner (SE) (A) unchanged at 0.4px — confirms xyz is correct
- Same Welcome Center pattern: 2 outliers eliminated in one LM

**Mount Waffles (TW)** + bonus **Mount Waffles** (in c5bc765):
- 3 markers snapped to their projections across Diner (NE), Diner (N),
  Diner (NE) for the second LM
- Both LMs now have all markers <3px err
- LMs are distant (>1km for Mount Waffles raw) — error_m stays elevated
  but reprojection on cam markers is now good

##### Skipped (distance limit identified)

- **Easy Inn Sign** (Diner (S) → 39.1', 128m distance): both markers
  visually on the same panel, but retriangulate trade-off makes
  Easy Inn (3.5') worse without improving Diner (S) below ~30'
- **Oval Yellow Sign** (Gas Station Lucia → 18.9', 761m distance):
  marker visually correct, retriangulate movement only 0.6m, no
  improvement possible at this distance with manual marker precision

##### Apprentissages

- **Distance <100m**: snap to projection works, fixes drop err to <5px
- **Distance >100m**: manual marker precision is the limit; 5-15px
  residual is the realistic floor
- **Witness pattern**: when a non-source cam marks an LM at <1px, it
  validates the xyz independently from source cams. Useful diagnostic.
- **Name collisions** (one LM name used for 2+ physical objects across
  different cams): detected by retriangulate residual divergence; fix
  by removing the offending marker

#### Part 3 — Audit count and bundle adjust impact

After all 5 fixes:
- CASE A outliers (≥10'): **15 → 8** (cut in half)
- Bundle adjust RMS: **2.95 → 2.97** (no measurable change)

The RMS doesn't move because the solver compensates marker shifts by
adjusting cam params on the calibrated (non-LEAK) cams. Individual LM
audit improvements are real but local; **real RMS reduction requires
fixing multi-outlier LMs** where the same LM has wrong xyz seen from
multiple cams.

Top multi-outlier LMs identified for next session:
- **White Billboard (Hamlet)** — 6 Police Chase outliers (47.7' down
  to 17.7'). Top of bundle adjust outlier list. Fixing this single LM's
  xyz could drop the RMS measurably.
- **Container Crane (3)** — 2 outliers (Amphitheater, Motorboats (B))
- **Flamingo South Beach (SRSW)** — 2 outliers (Vice Beach A + B)
- **Radio Tower #1 (Port Gellhorn)** — 2 outliers (Chase A + B)

#### Part 4 — Yanis V12 map upgrade (commit 8f0be2c)

Yanis published map V12 on May 13 2026 (denser visual detail than V11).

Infrastructure setup needed (one-time, persistent):
- **Homebrew** installed at `/opt/homebrew/` via official script
- `.zprofile` updated with `eval "$(/opt/homebrew/bin/brew shellenv)"`
- **git-lfs 3.7.1** installed via `brew install git-lfs`
- `git lfs install` ran to register LFS smudge filter

LFS pull from rlx vendor (~1.5 GB):
- `vendor/gtamaplib/maps.zip`  : 144 MB (was 134 byte LFS pointer)
- `vendor/gtamaplib/frames.zip`: 1.2 GB (not needed yet, ~10k frames)
- `vendor/gtamaplib/fonts.zip` : 245 KB

Asset preparation pipeline:
1. Extract `maps/yanis,12.png` (61.8 MB, 20000×20000, RGBA) from
   `vendor/gtamaplib/maps.zip` to repo's `maps/`
2. Verify alpha channel is constant 255 → drop to RGB safely
3. Downscale 20000×20000 → 12000×12000 (matches yanis_v11 asset dims)
4. Convert to JPG quality 92, drop transparency → 13 MB
   (vs WebP 90 at 8.4 MB but too blurry per visual check,
    vs PNG keeping alpha at 37 MB)

Code changes via `patch_yanis_v12_jpg.py` (idempotent, archived):
- `gtamapdata/maps.json:45` — `maps/yanis,11.png` → `maps/yanis,12.png`
- `tools/server.py` — `/yanis.png` endpoint → `/yanis.jpg`,
  asset `yanis_v11.png` → `yanis_v12.jpg`,
  Content-Type `image/png` → `image/jpeg`
- `tools/calib.html` — 7 `/yanis.png` URL references → `/yanis.jpg`
- `.gitignore` — `vendor/` added (local LFS clone, not committed)

Small syntax bug in the generated patch (the Python literal
`elif path == '/yanis.jpg'  # [YANIS-V12]:` had the `:` *after* the
comment, making it invalid Python). Fixed via sed move-before-comment.

#### Part 5 — Adaptive map dots (commit pending at end of session)

The cam-markers and lm-dots are SVG circles inside `#map-overlay`,
which is wrapped in a div with `transform: scale()` applied for zoom.
When zooming in, the circles grow with the wrapper, hiding the map
beneath. Fixed via `updateDotSizes()` injected in `applyMapTx()`:

- Captures `mapBaselineScale` at `resetMapView()` (fit-to-screen scale)
- On every transform update, computes
  `factor = (baseline / mapTx.scale) ^ 0.5`
  (square root softens the inverse-scale to keep dots barely visible
   at extreme zoom rather than infinitesimal)
- Iterates all `.cam-marker circle` and `.lm-dot` and sets `r` to
  `baseR * factor` (and `stroke-width` for cam markers)
- Base values cached in `dataset.baseR` / `dataset.baseSw` on first
  pass, so we don't lose them after the first update
- Also reduced CSS `.cam-marker:hover circle{stroke-width:50}` to
  `stroke-width:20` (50 was the original; in SVG units, scales with
  zoom and produced a huge black halo when zoomed)
- Sentinel `[CAM-DOT-ADAPTIVE]`

Bonus follow-up: LMs observed by the currently-selected cam are
sized 1.6× their normal size, so they stand out on the cam's
frustum. Sentinel `[OBSERVED-LM-BIGGER]`. Uses the existing
`observedSet` already built in `renderLandmarksOnMap()`.

#### State at end of session

- Branch: `feature-svg-map`
- HEAD: 8f0be2c (yanis V12) + uncommitted adaptive dots changes
- 9 commits pushed today (b24bc26, 5f379bc, 7d38907, 4dd0d75, 80557ed,
  993a0d4, 0f2304b, c5bc765, 8f0be2c)
- 5 LM xyz fixes applied (4937 E Hwy 98, Welcome Center, White Pole,
  Domed Hills Sign TW, Mount Waffles TW + Mount Waffles)
- Removed 1 marker (White Pole on Diner (SE) (A) — name collision)
- Old asset `tools/assets/yanis_v11.png` (18 MB) kept on disk as rollback
- LFS files in `vendor/gtamaplib/` not tracked (gitignored)

#### Updated pending priorities

1. **Commit the adaptive-dots changes** (calib.html only)
2. **White Billboard (Hamlet)** xyz fix — affects 6 Police Chase
   outliers, most likely candidate to drop the RMS measurably
3. Continue HIGH_PRIORITY fixes (Diner cluster, Car Wash)
4. Decide what to do with the 8 remaining CASE A outliers (some are
   distance-limited and may have to stay)
5. **Refine adaptive-dots tuning** if needed (power, hover behavior,
   selected-cam LM bump)
6. JSON output for calibration_order.py (carried over)
7. Fix calibration_order's loss check (U-Turn (NE) false positive)
8. C — Verticals as solver constraints, take 2
9. D — Multi-step relaxation
10. Pylon (3) LM bug
11. Decide whether to merge `feature-gtamaplib-dependency` into
    feature-svg-map (still pending real-world test)
12. Cleanup `audit_leak_consistency.py` (obsolete hardcoded LEAK list)



<!-- [CLAUDE-CONTEXT-2026-05-15-AM] -->
### Session 2026-05-15 morning — Four Seasons rigid-body model discovery (-35% RMS)

Started the day pivoting from yesterday's marker work toward exploring
rlx's chain-based calibration philosophy (from his Discord monologue).
Discovered that rlx has built a 3D rigid-body model for Four Seasons
Hotel Miami in his upstream code, applied it to landmarks.json, and
the bundle adjust RMS dropped from 2.97 to 1.94 arcmin (-35%).

This is the largest single-commit RMS improvement in the project's
history so far.

#### Part 1 — Exploring rlx's chain methodology

rlx published a long monologue on Discord describing his step-by-step
calibration optimizer (codex-written). Key insights:

1. Adding a single ray can change everything — adding reworld to
   Keys Airplane shifts Leonida Keys 01 by 0.874m, Postcard by 0.670m.
2. Parallel rays = problem. Turkey Point via Keys Airplane + Postcard
   has nearly-parallel rays, producing degenerate triangulation.
   Heuristic: skip ray pairs with <15deg angle.
3. Architecture proposal: ordered list of cameras (a chain), with
   global re-optimization after each step instead of one big global opt.
4. "Roll is an error sponge" — don't optimize roll on cams initialized
   with zero roll.
5. Per-cam loss can increase even when global loss decreases.

#### Part 2 — Testing rlx's chain on our tooling

Tried to replicate his chain (Keys Airplane -> Vice Beach B -> Watson
Bay -> Prison -> Ambrosia 02) using tools/calibrate_session.py.
The tool exists and works (already wired up via calibration_order.py
and batch_optimize.py). However:

- Our auto-optimize guardrail requires >=3 anchor+high LMs per cam
- All 5 cams in rlx's chain have 0-2 anchor+high (not enough)
- rlx's optimizer is more permissive (forces optimization)

Comparison of patterns regardless:
- Watson Bay self-source divergence: 12.3' on Portofino Tower (S) and
  11.1' on Nine at Mary Brickell Village (E) — matches the bundle
  adjust top outliers
- Our losses on Keys Airplane, Prison, Vice Beach B are better than
  rlx's test starting point (probably because our dataset is more
  raffined after yesterday's fixes)

Conclusion: can't run chain mechanically, but the *patterns* converge —
Watson Bay is a shared problem.

#### Part 3 — Discovering the structural weakness

Investigated which LMs are critical anchors for the south of Vice City.
Found that:

- Four Seasons Hotel Miami (BW) has 8 cams downstream but only 1 source
  (Handlebar (SW))
- Four Seasons (BE), (SE), (NW), (BW) all sourced by a single cam each
- Four Seasons (W) has corrupted xyz: (-2.5e14, 1.3e14, -1.1e14) —
  3e14 meters from origin
- Single-source LMs propagate noise to all downstream cams

Even worse, our triangulated xyz on these LMs don't form a coherent
building geometry — (BW) and (BE) are 44m apart per their xyz, but the
real Four Seasons is 30m wide. So 14m of internal incoherence in our
data, invisible to the solver.

#### Part 4 — Discovery: rlx has a rigid-body model

User insight: "je te garantie qu'il a un modele 3d". Searched vendor
upstream and found `class FourSeasons(Landmark)` in vendor/gtamaplib/
gtamaplib.py:1317.

It's a full parametric rigid-body model:
- 13 anchor points as __init__ parameters (corners at floors 40, 56,
  57 + handlebar features at floors 8, 28, 58)
- All other corners derived geometrically via `_construct()`:
  - intersect_ray_and_plane for 56th floor side corners
  - Horizontal extrapolation for 57th floor (penthouse)
  - get_point + dir_w for handlebar opposite corners
- floor_height = 4.029m, penthouse_height = 4.698m
- Total building dimensions: 48.7m east-west, 45.3m north-south,
  263.6m tall
- Orientation 339.5 deg

The `_landmarks()` method returns a dict of named LM corners
(BE, BW, E, NE, NW, SE, SW, W) with derived xyz. Other corners
(40NE, 40NW, 40E, 40W, 32NE, 56NE, HB28SE, HB8SE, HB58SE, HB58NE)
accessible directly as attributes.

#### Part 5 — Applying the model (commit e89e3e4)

Built `patch_four_seasons_rigid_model.py` to:

A. **Fix corrupted W**: override xyz (was 3e14m garbage) with model
   value (-818.00, -1316.42, 258.31).

B. **Override 4 drifted LMs** to model values:
   - BE: drift 4.79m -> rigid model
   - BW: drift 2.02m -> rigid model
   - NW: drift 2.95m -> rigid model
   - SE: drift 1.37m -> rigid model
   (E, NE, SW were already <0.5m drift, left alone)

C. **Add 9 missing LMs** that are already marked on Tennis Stadium (4K)
   and Metro (SE) (A) (4K) but absent from landmarks.json:
   40NW, 40W, 40E, 32NE, 56NE, HB28SE, HB8SE, HB58SE, HB58NE.
   Each assigned model xyz with the LEAK cam as source.

Sentinel [FOUR-SEASONS-RIGID-V1] in `notes` field; idempotent.

#### Part 6 — Bundle adjust impact

| Metric | Before | After | Delta |
|---|---|---|---|
| RMS | 2.97' | **1.94'** | -35% |
| Improvement | 8.8% | **44.1%** | |
| p50 | 1.24' | **0.52'** | -58% |
| p90 | 5.06' | **2.82'** | -44% |
| p99 | 12.22' | **9.19'** | -25% |
| obs >20' | 7 | **4** | |
| obs >10' | 18 | **10** | |
| obs <5' | 927/1037 | **1005/1037** | 97% now <5' |

White Billboard (Hamlet) on Police Chase still tops the outlier list
but with reduced magnitudes (47.7' -> 38.3' max). The rigid Four Seasons
acts as a strong anchor, the solver redresses the whole south coast
around it.

#### Part 7 — Strategic implications

The 3 levels of rigid-body integration:

**Level 1 (DONE)** — Override xyz from the rigid model.
- Cost: 30 min
- Impact: -35% RMS
- Mechanism: solver sees coherent geometry, redresses cams

**Level 2 (FUTURE)** — Rigid body as solver variable.
- Cost: 4-8h
- Mechanism: instead of optimizing 13 individual LM xyz (39 DOF), the
  solver optimizes the building's pose (6 DOF: translation + rotation)
  with the internal geometry locked. Far fewer DOFs, much more
  constrained.
- Requires: refactoring bundle_adjust to recognize "rigid group" LMs,
  parameterizing rotation (quaternion or axis-angle), Jacobian updates.
- Expected impact: further RMS drop, more confidence in poses.

**Level 3 (FUTURE)** — More rigid bodies.
- Cost: ongoing — model each major skyline building
- Candidates: Portofino Tower, Icon at South Beach, Bank of America
  Tower, Continuum on South Beach, Wells Fargo, Asia Brickell Key,
  Nine at Mary Brickell Village. Check if rlx already has models for any.
- Mechanism: same as Four Seasons, propagate rigidity across the south.

#### State at end of session

- Branch: `feature-svg-map`
- HEAD: e89e3e4
- Working tree: clean
- RMS: 1.94' (down from 2.97' yesterday and last week)
- Pattern proven: rigid-body anchors massively constrain the solver

#### Updated pending priorities

1. **Communicate the result to rlx** (Discord) — he'll be interested
   that his Four Seasons model produced -35% RMS on our dataset.
   Ask if he has models for other buildings (Portofino, Icon, etc.).

2. **Mark the 9 new Four Seasons LMs on downstream cams**: they're
   added to landmarks.json but only sourced by their LEAK cam. If we
   mark them on Vice Beach A+B, Prison, etc., the multi-anchor effect
   strengthens further. Could drop RMS more.

3. **White Billboard (Hamlet)** — still the top outlier cluster
   (6 Police Chase outliers). Investigate why all 6 cams agree this
   LM is misplaced. Probably the LM xyz needs fixing, or there's a
   name collision.

4. **Niveau 2 (rigid body as solver variable)** — major refactor
   of bundle_adjust. Worth investigating after we've exhausted the
   easy wins (Level 1 on more buildings).

5. **Niveau 3 (more buildings)** — check if rlx has Portofino, Icon,
   etc. models in vendor.

6. Carry-overs:
   - JSON output for calibration_order.py
   - Fix calibration_order's loss check (U-Turn (NE) false positive)
   - C — Verticals as solver constraints, take 2
   - D — Multi-step relaxation
   - Pylon (3) LM bug
   - Decide whether to merge `feature-gtamaplib-dependency` into
     feature-svg-map
   - Cleanup `audit_leak_consistency.py` (obsolete hardcoded LEAK list)



<!-- [CLAUDE-CONTEXT-2026-05-15-PM] -->
### Session 2026-05-15 afternoon — Niveau 2 rigid-body experiment + Watson Bay diagnosis

Pushed Niveau 1 in the morning (-35% RMS via Four Seasons rigid model
xyz overrides). This afternoon: attempted Niveau 2 (rigid body as solver
variable) and uncovered several structural insights about the dataset.

#### Part 1 — Niveau 2 implementation

Goal: instead of optimizing each Four Seasons LM xyz independently
(3 DOF each), treat the entire building as 6 DOFs (3 translation +
3 rotation around centroid). Reduces variables, enforces geometric
coherence.

Design doc: tools/RIGID_BODY_DESIGN.md (6 decisions, see file).

Implementation in 2 patch scripts (archived in
tools/_archive/patches/):
- patch_rigid_v2_edit1.py: inject rigid body setup after lm_idx
- patch_rigid_v2_edit2.py: inject helpers, modify x0, pixel_residuals,
  Jacobian sparsity (7 sub-patches A-G)

Multiple bugs encountered during integration:
1. REPO_DIR undefined (actual: GTAMAP_DIR)
2. Namespace collision: `import gtamaplib as ml` at line 34 binds the
   root namespace; `from gtamaplib.gtamaplib import FourSeasons`
   then fails
3. importlib relative import error in vendor module
4. Final fix: hardcode the 18 LM xyz directly in bundle_adjust.py via
   _FS_LM_MAP dict

#### Part 2 — Niveau 2 first run

Variables: 1789 -> 1774 (-7 LMs × 3 DOFs + 6 rigid DOFs = -21+6 = -15)

Result: RMS = 2.27 arcmin (vs 1.94 baseline). WORSE.

Top outlier: Grassrivers 02 (Watson Bay) -> Four Seasons (W) at 53.2'

#### Part 3 — Root cause discovery: bug in rlx's _landmarks() method

The rlx FourSeasons class defines a method _landmarks() that returns
"Four Seasons Hotel Miami (W)" -> self.fs57e (East penthouse, ~258m
altitude).

But our marker for that LM on Watson Bay at pixel (945.5, 497) was
pointing at the 40th floor West corner (fs40w, ~189m altitude). Tested
5 candidates for the marker:
- fs57e (Penthouse E, the rlx value): projects 70.3px from marker
- fs56sw (corner SW): 56.3px
- fs57nw: 62.8px
- fs57w computed: 60.5px
- **fs40w: 5.7px** ← match!

The bug: rlx's _landmarks() maps "W" to fs57e which is the East
penthouse, contradicting the W label. Our marker correctly identified
the 40th floor West corner as the visual feature.

Fix (commit 39ae6d3): rename the Watson Bay marker from
'Four Seasons Hotel Miami (W)' to 'Four Seasons Hotel Miami (40W)'.
Remove FS(W) entry from landmarks.json (no marker references it now).

Bundle adjust impact: the 53.2' outlier disappears. RMS at 1.9355
(no change vs Niveau 1 baseline 1.9357).

#### Part 4 — Niveau 2 second run, with FS(W) renamed

Re-ran Niveau 2 with the rename fix. RMS = 1.9477 (slightly worse than
1.9355 Niveau 1 baseline).

Conclusion: Niveau 2 works technically (solver converges, rigid body
operates correctly), but yields NO measurable gain on this dataset
because Niveau 1 already captured the geometric coherence via xyz
override. The remaining free LMs absorbed any small drift naturally.

Reverted bundle_adjust.py to Niveau 1 state (no rigid body in solver).

#### Part 5 — Watson Bay structural problem

Investigated why Watson Bay still has top outliers:
- Portofino Tower (S): 16.7px
- Nine at Mary Brickell Village (E): 15.1px
- Red Billboard (Hamlet): 12.7px

These are exactly the LMs rlx flagged in his Discord monologue (Watson
Bay self-source divergence on Portofino (S) 12.3', Nine Brickell (E)
11.1').

Tested:
1. Camera position grid search: current xyz is locally optimal
   (rmse 6.19px, no nearby point is better)
2. hfov sweep: 47° is optimal (47.0 -> avg 4.6px; 48 -> 25px; 46 -> 26px)
3. pitch/yaw sweep: -5.5° pitch, current yaw are both optimal

So Watson Bay cam params ARE optimal for the markers we have.

#### Part 6 — Comparison with rlx's Watson Bay

Found in vendor/gtamaplib/gtamapdata.py line 261:
- rlx xyz: (-5218.000, -3355.000, 27.233)
- our xyz: (-5472.6401, -3427.1089, 21.2183)
- Delta: +254m X, +72m Y, +6m Z, hfov 49.6 vs 47.0

Tried importing rlx's Watson Bay cam params: avg error went from 4.6px
to 10.0px on our markers. Reason: rlx's Turkey Point LMs are at
different xyz (drift 7-21m from ours). His cam Watson Bay is
self-coherent with HIS LM xyz, not with ours.

This means: pieces of rlx's calibration cannot be imported individually
without breaking coherence. Either we import the whole system (cam +
all dependent LMs), or we re-calibrate our system from scratch.

Decided NOT to import rlx's Watson Bay this session.

#### Part 7 — Strategic implications

Several insights:

1. **Niveau 2 produces no measurable gain when Niveau 1 already
   normalized the LM xyz**. Rigid body solver integration is an
   architectural improvement (LMs cannot drift apart geometrically)
   but does not unlock new accuracy on data that's already coherent.

2. **rlx's _landmarks() method has a labeling bug**: "W" -> fs57e.
   This is a small finding but useful to mention to rlx, and useful
   for any tool that depends on this method.

3. **Watson Bay's outliers are NOT cam param errors**. They're either:
   - Marker placement imprecision on distant features (~15px at 6km
     distance is near the limit of human marking accuracy on small
     visual features)
   - LM xyz triangulation errors compounding with Watson Bay's view
     angle
   - Our entire local coordinate system having a small offset from
     rlx's reference

4. **Cam param transplant across datasets does not work** without also
   transplanting all the dependent LM xyz. Datasets are self-coherent
   webs.

#### State at end of session

- Branch: feature-svg-map
- HEAD: 39ae6d3 (FS(W) rename) — pushed
- New commits this session:
  - c595fd2 fix: Sunshine Skyway Bridge (N) + (S) from rlx rigid model
  - 39ae6d3 fix: Watson Bay marker semantic bug FS(W) -> FS(40W)
- Working tree: clean
- RMS: 1.9355 (negligibly improved from 1.9357 morning)
- bundle_adjust.py: REVERTED to Niveau 1 state (no rigid body)
- Niveau 2 patches archived in tools/_archive/patches/
- Design doc tools/RIGID_BODY_DESIGN.md added

#### Updated pending priorities (revised)

1. **Communicate to rlx on Discord**:
   - The Niveau 1 -35% RMS win using his FourSeasons model
   - The bug in his _landmarks() method ('W' -> fs57e)
   - Ask if he has rigid models for Portofino, Icon, Nine at Mary
     Brickell, etc.

2. **Mark the 9 new Four Seasons LMs on downstream cams** (still
   pending from morning): Vice Beach A+B, Prison, etc. could
   amplify Niveau 1 win.

3. **Watson Bay re-calibration is hard**:
   - Either accept ~15px residual error on distant LMs as structural
     limit
   - Or do a holistic re-import from rlx (cam + dependent LM xyz)
   - Or do a marker re-placement session in the UI on Watson Bay
     specifically for Portofino (S), Nine Brickell (E), Red Billboard

4. **White Billboard (Hamlet)** — still top outlier cluster (Police
   Chase × 6). Different from Watson Bay; needs its own investigation.

5. **Niveau 3** still on table — finding more rigid models in vendor
   (we checked: only FourSeasons, HanksWaffles, SunshineSkywayBridge
   exist as classes). HanksWaffles already aligned (no gain), Skyway
   done. So Niveau 3 needs new rigid models we'd build ourselves,
   or wait for rlx to publish more.

6. **Niveau 2 architecture preserved** in archived patch scripts and
   design doc. Can be revived later if we find a building (or system)
   where rigid body solver integration would unlock gain that pure
   xyz override doesn't capture.

7. Carry-overs (unchanged from morning):
   - JSON output for calibration_order.py
   - Fix calibration_order's loss check (U-Turn (NE) false positive)
   - C — Verticals as solver constraints, take 2
   - D — Multi-step relaxation
   - Pylon (3) LM bug
   - Decide whether to merge feature-gtamaplib-dependency into
     feature-svg-map
   - Cleanup audit_leak_consistency.py (obsolete hardcoded LEAK list)
