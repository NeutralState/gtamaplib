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

### 2026-05-10 — Multi-seed bundle_adjust experiment (ruled out)

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
