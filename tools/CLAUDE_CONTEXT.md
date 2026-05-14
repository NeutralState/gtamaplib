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
- **Last session** : 2026-05-14 — Discovery: 87% of non-LEAK cams have ZERO all_leak LMs anchored. The dataset is structurally calibrated against calibration-derived LMs (not ground-truth). New audit tool `audit_all_leak_opportunities.py` identifies 1013 potential markings; 12 realistic opportunities (10+ marked cams w/ 5-30 LEAK visible) for next sessions. calibrate_cam.py upgraded: suggestions now tagged with LEAK ancestry (all_leak first). See session log for top opportunities list. **No data changes** — read-only analysis + tool upgrades.

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

