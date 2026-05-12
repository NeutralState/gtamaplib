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
- **Bundle adjust RMS** : 5.78' (171 cams; baseline pre-port was 2.28'; 23 rlx-ported unverified cams pollute. Marking via UI or batch_optimize will clean.)
- **171 cams** (148 base + 23 rlx ported), **680 landmarks**
- **Last session** : 2026-05-12 — Phase 11 verticals end-to-end (overlay UI toggle V), physical z bounds, tier-weighted optimize, batch_optimize.py. Discord mapper+ obtenu de martipk. Marti confirms "Four Seasons (BW) circular" — already-anchored LMs don't get re-triangulated.

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

**Next session priorities** (updated 2026-05-12):
1. **Pylon (3) LM bug** — concrete, ~30-45 min. Find bad source pixels, fix or
   remove. Surfaced by intake_camera on Chase (2) (A). Affects all cams looking
   south toward Pylon.
2. **C — Verticals as solver constraints** — user marks 1-2 vertical lines on
   screenshot in UI, solver uses these + LM pixels to better constrain
   yaw/pitch/roll. Math + UI marking. ~2-3h. Phase 11 visual was the prereq.
3. **D — Multi-step relaxation** — solver progressively relaxes constraints
   (start with z fixed and fov fixed, then relax). ~1.5-2h. Helps when very few
   obs are marked.
4. **Update LMs in batch** — currently batch_optimize doesn't trigger Update LMs
   by default (safety). Could add a stricter threshold version with whitelist.
5. **Manual marking session** — go through the 48 unverified cams that don't have
   enough anchor+high obs, mark landmarks in UI. Tedious but the only way to
   bring RMS back down.

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
