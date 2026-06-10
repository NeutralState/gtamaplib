<!-- INDEX_DE_RETOUR_v1 -->

## Session 2026-06-04 (PM) — Politique roll + Dominion + Portofino NE

**Doctrine roll (NOUVEAU, calibre):** le prior roll `(roll/sigma)**2` etait inoperant
partout (echelle ~3500x trop petite, cosmetique meme pour classe B). Corrige via
`ROLL_PRIOR_WEIGHT=50` (central dans leak_cam_audit.py, a cote de CLASS_B_ROLL_PRIOR_SIGMA_DEG).
Calibre sur Diner (N) + valide par test de convergence (un vrai roll multi-deg passe,
le bruit ~0.07deg est ecrase). Applique sur les 3 outils:
- refine_cam_ypr: classes B/C (sigma 2), D (sigma 3)
- refine_cam_full: D/Cm/libre (sigma 3 si D, 2 sinon), dans le `penalty`
- bundle_adjust_weighted: composante roll du ypr-hinge remplacee par prior vers 0
  (seules les cams D/non-leak y passent; A/B/C/Cm ont xyz->roll fige)

**Dominion Hotel recalibre** (classe None): roll parasite -2.77deg ecrasait Portofino
NE a 45'. refine_cam_full --apply: roll->-0.05, RMS 9.56->3.06', Portofino NE 45->7.4'.
Marking Portofino NW ajoute (0.91'). xyz a bouge de 8m (acceptable, pas d'anchor).

**Portofino NE oriente** (mesh): peak box + pentagone NE etaient mal orientes vs NW/S.
PortofinoTower.py: `PEAK_BOX_NE_OFFSET=-22.5`, `PENTAGON_NE_OFFSET=-5` (le +180 d'origine
du pentagone enleve). Anchors NW/NE/S inchanges. Regle visuellement via wireframe.
Les LM PB-/PT-NE dans landmarks.json sont du vieux bruit (AI World Editor), pas ground truth.

**Repo cleanup (AM):** 63 .bak archives, solver/ retire (code mort), inventory regenere
(scanne tools/audit/), patches ranges, doublons retires, index de retour ajoute.

**TODO laisses en route:**
- Portofino NE chez Dominion encore a 7.4' (incoherence NE/NW): re-verifier le marking NE
  ou le xyz du mesh apres l'orientation corrigee
- Marking stale `Waffles Ridge (C)` a 9.6' sur Diner (N) — fix independant du roll
- Dominion Hotel: assigner une classe (actuellement None), n'a aucun LM anchor
- Toujours en file: recalibration cluster Ambrosia (WDNA+Skyway, rouvre le roll — le
  prior est pret), C2/C3, calibrer sigma_pose de lm_uncertainty


# gtamaplib — Point d'entree (lis ca en premier)

**Branche de travail: `feature-solver`** (c'est LA branche principale, pas une
experimentale — l'ancien solver/ from-scratch a ete abandonne et retire).

**Regle d'or:** l'UI (calib.html, port 8765) sert UNIQUEMENT a marquer des
pixels. Tout le solving = terminal. Ne jamais cliquer Optimize/Update LMs dans l'UI.

**Workflow (Claude ecrit les commandes, Alexandre les lance):** scripts Python
one-shot, dry-run par defaut + `--apply`, backups `.bak_<raison>`, heredoc
`<<'PY'` sans `#` inline (zsh bracketed-paste). Outils d'audit READ-ONLY dans
`tools/audit/`. La lib vendored `gtamaplib.py`/`vendor/` ne se touche jamais.

**Quand je reviens et je sais plus quoi faire — ou je lis:**
| Besoin | Fichier |
|---|---|
| Etat courant + journal des sessions | ce fichier (sections datees ci-dessous) |
| Liste de tous les outils/scripts | `tools/TOOLS_INVENTORY.md` |
| Classes de cams (A/B/C/Cm/D/X) | `tools/V2_CONSTRAINT_CLASSES.md` |
| Procedure apres nouveaux markings | `tools/RECALIBRATION_WORKFLOW.md` |
| Design des meshs (Portofino/WDNA...) | `tools/RIGID_BODY_DESIGN.md` |

**Outils d'audit (READ-ONLY, tous dans tools/audit/):**
- `retriangulation_candidates.py` — classe les LM par gain de retriangulation (Chantier A)
- `circular_deps.py` — detecte les cycles de dependance cam->cam, Tarjan (Chantier B)
- `lm_uncertainty.py` — incertitude 3D par LM via Monte-Carlo, r_pose/r_pix/ratio (Chantier C1)
- `audit_leak_influence_tree.py` — arbre d'influence descendante depuis les leaks

**Doctrine cle:** leak cam = source de verite (xyz/fov HUD-locked); le juge d'une
triangulation = PARALLAXE + DELTA, jamais le RMS seul; le roll (ypr[2]) est
hardcode a 0 dans tout le pipeline (dette connue, refactor a venir).

**TODO prioritaires (voir details dans les sections ci-dessous):**
- Recalibration cluster Ambrosia sur ancres externes (WDNA/Skyway), rouvre le roll
- Chantier C2 (viewer) / C3 (covariance dans bundle_adjust)
- Calibrer les sigma_pose de lm_uncertainty
- Petits restes: 4 LM quarantaine sweep A, Port Gellhorn Postcard sans source, Sunshine Skyway (S) a benner

---

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
- **Branch active** : `feature-solver`
- **Triangulation tool** : `tools/triangulate_lm.py` (ROBUST version — parallax filter + collinear dedup + outlier rejection; see 2026-05-31 session). Backup of pre-robust: `tools/triangulate_lm.py.bak_pre_robust`.
- **Mesh classes** (repo root, read LMs, NEVER touch vendored lib) : `PortofinoTower.py`, `WDNAFM.py`, `OneThousandVenetian.py`. Regenerate meshes with `python3 tools/extract_mesh_edges.py` (writes `building_meshes_procedural.json`; per-building key = `world_edges`).
- **Last session** : 2026-05-31 — robust triangulator, Portofino anchors re-triangulated via Sidewalk E (leak C now sources), Portofino mesh rebuilt from scratch (trifoliate), WDNA FM mesh ported. See bottom log.

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
│   ├── bundle_adjust.py            ← legacy global BA (pre-Phase-C)
│   ├── bundle_adjust_weighted.py   ← Phase C: tier-aware BA (USE THIS)
│   ├── compute_confidence_tiers.py ← Phase A: tier classifier
│   ├── intake_camera.py            ← Phase B: validates new cams vs trustworthy set
│   ├── refine_cam_full.py          ← single-cam 7-param fit (scipy Rotation ZXY)
│   ├── calibrate_batch.py          ← batch refine + re-triangulate
│   ├── calibration_plan.py         ← non-tree cam insertion analyzer
│   ├── build_cam_health.py         ← generates dependency graph dashboard
│   ├── gen_missing_thumbs.py       ← auto-generates dashboard thumbnails
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

- ✅ **T3 intake pipeline (Phase A/B/C) shipped 2026-05-25**.
  See "T3 Intake Pipeline Complete" section below for full workflow.
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

---

## Session: 2026-05-25 — T3 Intake Pipeline Complete + Dependency Dashboard

This is **the most important workflow shift in the project's history**. We
went from rlx's monolithic `triangulate.py` (hardcoded per-cam calibration
script, 2700+ lines of switch-cases) to a **proper reusable pipeline** that
auto-discovers structure, validates against trusted ground truth, and runs
global optimization.

### The lineage: from rlx's `triangulate.py` to our T3 pipeline

**rlx's approach (origin):**
- Single monolithic `triangulate.py` with flags `-fs`, `-ts`, `-mb`, `-lka`,
  etc. — each flag is a hardcoded recipe for ONE specific cam/LM.
- Manually-chosen LM sets, manually-tuned grids, manually-picked anchor cams.
- Works but doesn't scale: every new cam needs new code, no way to reason
  about which LMs to trust globally, no automated verification.
- Output: cam params written manually after inspecting log.

**Our T3 pipeline (this is the new workflow — use it for everything):**

Stage 0 → **Schema (LM and cam tier semantics)**
Each LM and cam gets a confidence `tier`: anchor → high → medium → low →
unverified. Derived automatically from observation counts, source diversity,
and residuals. This is the **truth source** for every downstream decision.

Stage A → **`compute_confidence_tiers.py`**
- Produces `tools/generated/confidence_tiers.json` (cam_tier + lm_tier per
  entity, with reasons).
- Tier rules:
  - LMs: `>= 3 non-LEAK sources AND median res <= 3'` → high; `1 LEAK source`
    → high; `all sources LEAK` → anchor; etc.
  - Cams: `>= 5 anchor+high obs AND median <= 3'` → high; `>= 2 anchor+high
    obs AND median <= 6' AND max <= 30'` → medium; etc.
- Re-run after every batch of changes. This file gates Phase B + C.

Stage B → **`intake_camera.py`**
- Validates a NEW (or suspect) cam against ONLY anchor+high LMs.
- Solves ypr + (optionally) hfov + xyz against the trustworthy skeleton.
- Reports verdict: **COMMIT / REVIEW / REJECT** based on tier + post-residual.
- Does NOT modify cameras.json — the human decides whether to apply.
- The "wobbly" parts of the current state never pollute new-cam placement.

Stage C → **`bundle_adjust_weighted.py`**  *(built this session — the big new tool)*
- Global bundle adjustment over ALL non-leak cams + LMs simultaneously.
- **Per-observation weight** = `min(cam_tier_weight, lm_tier_weight)`
  - anchor=15, high=7.5, medium=2, low=0.5, unverified=0.1
  - weakest-link rule (anchor cam × low LM = 0.5, not 7.5)
- **Movement barriers per tier** (soft hinge penalty outside budget):
  - anchor cam: xyz ±1m, ypr ±0.2°, fov ±0.2°, stiffness 10
  - high: ±5m, ±0.5°, stiff 5
  - medium: ±20m, ±2°, stiff 2
  - low: ±50m, ±5°, stiff 1
  - unverified: ±200m, ±15°, stiff 0.5
- LMs locked tighter in proportion to their tier (anchor LMs barely move).
- Leak cams fully locked.
- Skips degenerate obs (LM <50m from cam — Beach LMs etc.) and aberrant LMs
  (|xyz| > 1e6m).
- "Behind cam" obs contribute 0, not huge penalty (avoids breaking the
  optimization when a cam temporarily flips a marker behind it).
- Sparse Jacobian (~0.4% density — essential for >100 params).
- 2-pass: linear → huber f_scale=5.
- Output JSON compatible with existing `bundle_adjust_apply.py`.

**End-to-end loop:**
```
add markings → run compute_confidence_tiers
            → intake_camera "Cam Name"   (verdict?)
            → refine_cam_full "Cam Name" --apply   (if commit)
            → bundle_adjust_weighted + bundle_adjust_apply   (global polish)
            → re-run compute_confidence_tiers
```

### Supporting tools we built this month (the foundation that makes T3 work)

- **`refine_cam_full.py`** — single-cam fit, 7-param (xyz + ypr + hfov).
  Critical fix: replaced manual rotation math with `scipy.spatial.transform.Rotation`
  using gtamaplib's **ZXY euler convention**. The original projection had a
  bug that made Ambrosia-zone cams unrecalibratable. Added `--use-indep-only`
  flag for cams whose LMs reference themselves (Ambrosia self-reference).
  Added `--fix-xy`, `--z-bounds`, `--no-hfov`, `--no-roll`.
- **`refine_cam_ypr.py`** — ypr-only fit. Same scipy Rotation fix.
- **`calibrate_batch.py`** — runs `refine_cam_full` over all stale/suspect
  cams, then re-triangulates affected LMs. Used to calibrate 24 cams in one
  pass (RMS net improvement across the board).
- **`calibration_plan.py`** — analyzes cams NOT in the dependency tree
  (`docs/index.html`) and suggests where to insert them. Treats leak cams as
  implicit tree root. Outputs "ready" / "needs N more LMs" / "depends on
  uncalibrated cams" verdicts.
- **`triangulate_lm.py`** — fixed leak detection (was using stale heuristic;
  now uses source-date regex `YYYY-MM-DD`).
- **`gen_missing_thumbs.py`** — auto-generates dashboard thumbnails for any
  cam with xyz that has a matching PNG in `frames/`. Generated 148 thumbs
  in one shot.
- **`build_cam_health.py`** — generates the new dependency graph dashboard
  (see next section).

### Dependency graph dashboard (replaces old cam_health table)

`tools/cam_health.html` is now an **auto-generated dependency graph** built
by `build_cam_health.py` from live data:

- **Auto-positioned**: each cam's (x,y) is its world position projected onto
  the canvas (2000×1600). North is up. PGH cluster lives in the NW, Vice in
  the east, Keys far south, etc.
- **Anti-overlap**: pairwise repulsion with spring-back to original position
  (200 iterations, target 38px min separation).
- **Auto edges**: built from `landmarks.json source_cameras`. If cam X marks
  LM L and L was triangulated by cam P, then P → X is an edge. Multiple
  parents in the same zone get aggregated into an LM cluster node (lm_vc,
  lm_ambrosia, lm_keys, lm_gv, lm_pgh).
- **Filter**: only cams with xyz + leak cams that are actually referenced
  as parents (29 useful leak cams kept, 63 unused dropped).
- **Tier-colored** nodes: anchor/leak=violet, high=green, medium=blue,
  low=yellow, unverified=gray, LM cluster=red.
- **Live tooltip** on hover: current xyz/ypr/fov, tier badge, source string,
  parents/children, AND the cam's thumbnail (200×130px).
- **Filters by tier** and **by zone** (top bar).
- Endpoint `/cam_health.html` (server.py serves the static file).
- Endpoint `/thumbs/<name>.jpg` (added this session, serves from `docs/thumbs/`).

### Calibration session results (this week)

- 29 non-leak cams calibrated in single-cam mode (24 batch + 4 Ambrosia + 1
  Mt Kalaga via rlx baseline).
- Ambrosia zone recovered: had been broken for months due to projection bug.
- Phase C BA: RMS 92.50' → 4.47' → 2.67' (95.41% improvement). Tier diff:
  cams +2 high, -1 low; LMs +3 anchor, +3 high, -3 low.
- Container Crane (1) outlier auto-corrected by BA (37m movement) — couldn't
  fix it manually.

### Tier state after this session

```
Cameras:                  Landmarks:
anchor=92 (leak cams)     anchor=164
high=24                   high=106
medium=7                  medium=227
low=2                     low=7
unverified=46             unverified=337
```

### Files added/changed

- `tools/bundle_adjust_weighted.py` (new — Phase C)
- `tools/refine_cam_full.py` (rewrite — scipy Rotation projection fix)
- `tools/refine_cam_ypr.py` (same fix)
- `tools/calibrate_batch.py` (new — batch refine + re-triangulate)
- `tools/calibration_plan.py` (new — non-tree cam insertion analysis)
- `tools/triangulate_lm.py` (leak detection fix)
- `tools/build_cam_health.py` (new — dashboard generator)
- `tools/gen_missing_thumbs.py` (new — thumbnail generator)
- `tools/cam_health.html` (rebuilt — dependency graph instead of table)
- `tools/server.py` (added `/api/dependency_graph` and `/thumbs/*` routes)
- `gtamapdata/cameras.json` (29 cams calibrated + BA polish on 46 cams)
- `gtamapdata/landmarks.json` (605 LMs re-triangulated + BA polish on 517 LMs)
- `gtamapdata/pixels.json` (markings cleanup)

### Reference: how a fresh calibration session should now go

1. Add new markings in calib UI (or via pixels.json edits).
2. `python3 tools/compute_confidence_tiers.py` — refresh tiers.
3. For each cam you want to calibrate:
   - `python3 tools/intake_camera.py "Cam Name"` — see verdict.
   - If COMMIT: `python3 tools/refine_cam_full.py "Cam Name" --apply`
   - If REVIEW: investigate, add more anchor markings, or accept rlx baseline.
4. Re-triangulate affected LMs (`triangulate_lm.py` per LM or via
   `calibrate_batch.py --retriangulate`).
5. `python3 tools/bundle_adjust_weighted.py` then `bundle_adjust_apply.py`
   — global polish.
6. `python3 tools/compute_confidence_tiers.py` — refresh tiers, check
   promotions.
7. `python3 tools/build_cam_health.py` — regenerate dashboard.
8. Commit.

**Don't** revert to rlx's per-flag pattern in `triangulate.py`. The pipeline
above is the new way.


---

## Session: 2026-05-31 — Robust triangulator + Portofino anchors re-triangulated + mesh rebuilt

**The headline shift this session: leak cams now SOURCE landmarks by constraint
class, and `triangulate_lm.py` chooses its own sources robustly (parallax +
collinear dedup + outlier rejection) instead of trusting a blind priority list.**

### The problem we were solving

The 3 Portofino tower peaks (the mesh anchors) sat at bad positions — NW was
at 13.9' error — because they had been triangulated from poor sources:
- **Amphitheater** = class `D_no_ground_truth` (preview shot, no HUD) — pure
  poison, no truth at all.
- **Port + Port (B)** = both class A but ~0.03-0.09° apart (same vantage) —
  the recurring **collinear trap**: near-parallel rays send the LSQ solution
  to ~1e15 ("under terre" / infinity).
- **Sidewalk (Jason) (E)** = leak class C, was being EXCLUDED as a source
  because its tier had dropped to `low` (high residuals on its far LMs), even
  though its pose is HUD-locked ground truth.

Alexandre's framing (correct): a leak cam with HUD-locked pose is a SOURCE OF
TRUTH. It should SOURCE the LMs it sees (the LMs adapt to it), not be excluded
because of residuals it didn't cause.

### `triangulate_lm.py` — the robust rewrite (THIS IS THE TOOL TO USE)

**`classify_cam`** now classifies by constraint class, not tier alone:
- leak `A_full_hud` → `leak_a` (best — full HUD, dir verified)
- leak `B/C/Cm` (pos+fov HUD-locked, dir uncertain) → `leak_pos` (good source:
  ray origin is exact, only the 3 dir params are soft)
- leak `D`/`X` (no ground truth / invalid) → `excluded` (Amphitheater)
- non-leak: `trusted_non_leak` (anchor/high) / `other` / `excluded` (low tier)

**`select_sources`** builds a candidate pool by priority **leak_A > trusted >
leak_pos > other** (A before C, per Alexandre). Includes ALL reliable tiers
(doesn't stop at 2) so parallax/dedup downstream has material to work with.

**`robust_triangulate`** (new core function) — does what we used to do by hand:
1. **Parallax filter**: drop any cam whose best pairing with another cam is
   < **15°** (a cam collinear with everyone is useless/dangerous).
2. **Collinear dedup**: if two cams see the LM < **5°** apart (Port+PortB at
   0.09°, Leonida01+LeonidaPostcard at 0.6°), keep the better one
   (rank leak_a > trusted_non_leak > leak_pos > other), drop the redundant.
3. **Iterative outlier rejection**: triangulate, compute per-cam reprojection
   residual; if the worst > **2× median AND > 5'**, drop it and re-triangulate.
   Repeats while > 3 cams remain. (Auto-caught Sidewalk E's Venetian markings
   at 12.3' and dropped them.)
4. Logs everything: per-cam parallax, dedup drops, outlier drops, kept set.

Also a hard parallax guard inside `triangulate` (rejects < 3° → no more 1e15).
`source_cameras` is now written as the **kept** set (post-filter), not the raw pool.

Thresholds (Alexandre approved): parallax min **15°**, dedup **< 5°**, outlier
**> 2× median AND > 5'**, min **3** cams to allow a rejection (conservative).

### Sidewalk (Jason) (E) — leak C turned into a reliable source

- Class `C_pos_fov_only`, HUD-locked: xyz `[-464.0, 1233.8, 4.6]`, fov h=80.339
  / v=50.8, `has_dir: False`. Source date `2021-09-10 16-37-50`.
- We did NOT recalibrate its pose (refine_cam_ypr barely moved it: the pose is
  fine, the high residuals were from bad markings + circular LMs).
- **Removed its `1000 Venetian Way (SW)` and `(NW)` markings** from pixels.json
  — they were at y≈18 (top edge of the 1920×1080 frame), on buildings 2.4km+
  away → ~15' irreducible error, and Venetian already has good sources
  elsewhere (Tennis Court SE, Venetian Islands, Vice City Postcard). Backup:
  `pixels.json.bak_pre_remove_venetian_sidewalkE`.
- After cleanup, its 6 remaining LMs reproject at 0.6–5.5' — a genuinely good
  leak C source. It now sources Portofino NE/NW, Star Island, Floridian, etc.

### Portofino anchors — re-triangulated, then S locked geometrically

Applied with the robust tool:
- **NE** → `[1758.377, -189.128, 145.380]`, residual 0.57'.
  Sources: Rooftop Party + Sidewalk (Jason) E (parallax 61.7°).
- **NW** → `[1723.019, -195.567, 145.699]`, residual 5.76'.
  Sources kept: Port + Rooftop Party + Leonida Keys 01 + Sidewalk (Jason) E.
  (Robust tool auto-dropped Port (B) [collinear 0.09° with Port] and Leonida
  Postcard [collinear 0.60° with Leonida 01].)
- **S** → could NOT be triangulated: its only observers (Port, Port B,
  Grassrivers Watson Bay) are all within ~12.9° of each other — below the 15°
  parallax floor, so the tool refused. **Locked geometrically** as the
  equilateral third point from NW+NE: `[1746.274, -222.969, 145.539]`,
  `error_m: 0`, `source_cameras: ['(geometric: equilateral from NW+NE)']`.
  Justified: we know the tower is a perfect trifoliate (3 wings at 120°).

**New triangle**: equilateral, side **35.94m** (was 31.2m before — the tower
"grew" ~15% as the anchors moved out to truer positions), centroid
(1739.6, -203.0), **LM radius 20.75m** (was 18), LM z ≈ 145.5 (was 142).
Backup before S edit: `landmarks.json.bak_pre_S_equilateral`.

### PortofinoTower.py — mesh rescaled to the new anchors

The mesh is parametric (reads the 3 LMs, computes centroid/radius/azimuths)
but several constants were hardcoded to the OLD scale and had to be recaled:
- `R_CYLINDER_BASE`: 18.0 → **20.75** (= new LM radius, cylinder touches LMs).
- Heights raised to sit on the new LMs (LM z ≈ 145.5, real spec 484ft/147.5m):
  `Z_PEAK_WALL` 142 → **143.5** (peak-box wall top = LM−2m), `Z_CYL_TOP`
  137 → **140.5**, `Z_PENT_TOP` 125 → **128.5**. `Z_GROUND`=0, break z85-95
  left as-is.
- **Pyramid tip = the LM exactly**: `tip_pt` now uses `tip[2]` (the LM's real z)
  instead of a hardcoded `Z_PEAK_TOP`. So each turret peak lands precisely on
  its anchor, with a 2m pyramid above the box wall.

Mesh structure (built from scratch earlier this session, before the rescale):
cylinder (octagon) + 3 radial pentagonal wings (house-shape: wide inner base
at the cylinder rim → shoulders → outer tip) + peak boxes rotated +45° + a 180°
flip on the NE wing + shallow pyramidal roofs. Wings stop at Z_PENT_TOP; above
that only the cylinder + peak boxes. Regenerate: `python3 tools/extract_mesh_edges.py`.

NOTE: a residual offset on **Rooftop Party** only (mesh fits well on the leak
cams, slightly off on Rooftop) is a Rooftop CALIBRATION issue (it's a trusted
non-leak T1 cam, its ypr can drift), NOT a mesh problem. Don't bend the mesh
to fit one non-leak cam.

### How the Portofino mesh is built (PortofinoTower.py) — detailed

`PortofinoTower(md, ml)` is a standalone class at repo root. It READS the 3
anchor LMs from `md.landmarks` and computes everything else parametrically.
It never touches the vendored lib. `render_on_camera(cam)` emits the mesh as
`cam.render_line((xyz1, xyz2), color, bold)` calls; `extract_mesh_edges.py`
captures those via a FakeCam into `world_edges`.

**Anchors & coordinate frame**
- 3 LMs = the 3 turret tips: `Portofino Tower (NW)/(NE)/(S)`, stored as
  `self.nw/ne/s`. They form a perfect equilateral triangle (side 35.94m,
  z≈145.5). Azimuths from centroid: NE=45°, NW=165°, S=-75° (120° apart).
- `self.centroid_xy` = mean of the 3 LM xy. `self.branch_peaks =
  {'NW':nw, 'NE':ne, 'S':s}`.
- Per branch, the geometry is built on a local frame: `radial_unit` = unit
  vector centroid→LM, `perp` = 90° rotation of it. So "outward" = +radial,
  "sideways" = ±perp.

**Vertical levels** (z, bottom→top), shared codes B/K/L/P (+CT for cylinder):
- B  = Z_GROUND   = 0
- K  = Z_BASE_TOP = 85
- L  = Z_BREAK_TOP= 95     ← the break (a 3-floor ~10m pinch)
- P  = Z_PENT_TOP = 128.5  ← wings STOP here (~floor 38)
- CT = Z_CYL_TOP  = 140.5  ← cylinder alone above the wings
- peak boxes: PB=Z_PENT_TOP(128.5) → PT=Z_PEAK_WALL(143.5)
- pyramid tip = the LM's real z (~145.5), Z_PEAK_TOP(147.5) is the legacy
  ceiling constant (the tip now uses tip[2], i.e. the LM, not this).

**Body = octagonal cylinder + 3 radial pentagonal wings**

Cylinder (`_cylinder`, CYL_LEVELS): an 8-sided ring of radius
`R_CYLINDER_BASE × scale`. R_CYLINDER_BASE = 20.75 (= LM radius, so the
cylinder rim reaches the LMs). CYL_LEVELS scale = 1.0 at EVERY level → the
cylinder is a straight tube R=20.75 from ground to CT. In the body it is
hidden inside the wings; above z=128.5 it stands alone and thin under the
peak boxes. (Keeping it 1.0 everywhere avoids a tapering cone artifact.)

Wings (`_pentagon`, PENT_LEVELS): 3 wings, one per branch, each a 5-sided
"house" shape seen from above, extending OUTWARD from the cylinder:
- `innerL/innerR`: wide base at the LM (cylinder rim), half-width SIDE_INNER/2 = 4.5
- `sideL/sideR`: shoulders, set back along radial by SHOULDER_OUT=4.5,
  half-width SIDE_SIDE/2 = 4.85
- `peak`: the outer tip, at lm_xy + radial_unit × WING_DEPTH (9m out)
- Wing orientation rotated by `WING_ROT = -45°`, with the NE wing getting an
  EXTRA +180° (`_wr = WING_ROT + (180 if br=='NE' else 0)`) — this is what
  finally aligned all 3 wings+boxes to the leak-cam views.

**Per-level width (scale) — constant body with a light break**
PENT_LEVELS scales: B=1.6, K=1.6, L=1.5, P=1.6. So the wings are full-width
(1.6) top to bottom EXCEPT a light pinch to 1.5 at the break level (z85→95,
~3 floors). No gradual taper — same width all the way, just the one notch.
(scale acts as a multiplier on the wing half-widths and radial offsets.)

**Peak boxes** (`_peak_box`, PEAK_BOX_LEVELS): a square turret on each wing
tip, side PEAK_BOX_SIDE=8.6, walls from PB(128.5) to PT(143.5). The box axis
is `radial_unit` rotated +45° (corner-facing, not face-facing). Like the
wings, the NE box inherits the +180° flip so box+wing stay rigidly aligned.

**Pyramidal roofs**: for each branch, the 4 PT wall-top corners (z=143.5)
connect up to a single tip = the LM itself (`tip_pt = (tip[0], tip[1],
tip[2])`, i.e. exact LM z ≈145.5). So each turret ends in a ~2m pyramid whose
apex sits precisely on the anchor LM.

**Real-world calibration**: Portofino Tower South Beach = 484ft/147.5m, 44
floors, completed 1997 (Sieger Suarez). The new anchor z≈145.5 + 2m pyramid ≈
147.5m matches the real height. The break sits high (~floors 28-31).

**Render flow & iterating**
`render_on_camera` walks PENT_LEVELS → `_pentagon` (5 corners/level, connects
the pentagon outline + verticals between levels), CYL_LEVELS → `_cylinder`
(octagon + verticals), PEAK_BOX_LEVELS → `_peak_box` (square + verticals) +
the 4 pyramid edges per branch. ~192+ edges total.
To iterate: edit a constant in PortofinoTower.py → `python3
tools/extract_mesh_edges.py` → hard-refresh the viewer (Cmd+Shift+R). The
mesh auto-follows the LMs (centroid/radius/azimuth recomputed); only the
hardcoded constants (R_CYLINDER_BASE, the Z_* heights, wing/box sizes) need
manual rescaling if the anchors move a lot — as we did this session when the
triangle grew 31.2m→35.94m.

### WDNA FM radio tower — mesh ported from rlx

Ported rlx's `class WDNAFM` lattice (21 edges: 3 verticals N/SE/SW × 5 levels
z=5→396 converging to tip ~402). Created `WDNAFM.py` (color #f87171, reads LMs),
added 15 structure points to landmarks.json, integrated into extract_mesh_edges.py.

### Doctrine reinforced this session

- **Leak cam = source of truth.** It sources the LMs; the LMs/other cams adapt.
  Source by class: A > C/B/Cm; exclude only D/X. A leak C is still better than
  any non-leak frame (position + fov are HUD-exact).
- **Port + Port (B) are always collinear (~0.03-0.09°)** — never let them be
  the only two sources. The dedup handles this automatically now.
- **Amphitheater is class D** (no ground truth) — never a source. It was the
  original "poison" pulling the Portofino anchors.
- **Parallax + delta are the judges, not RMS.** A 0.5' residual with 0.1°
  parallax is a trap. The robust tool encodes this.
- When a leak cam has high residuals on FAR LMs at the frame edge, suspect the
  MARKINGS (edge of frame, distant), not the cam pose.

### Files changed this session

- `tools/triangulate_lm.py` (robust rewrite — classify by class, priority pool,
  robust_triangulate). Backup: `tools/triangulate_lm.py.bak_pre_robust`.
- `PortofinoTower.py` (built from scratch + rescaled to new anchors).
- `WDNAFM.py` (new), `OneThousandVenetian.py` (Z fix from a prior segment).
- `tools/extract_mesh_edges.py` (imports the 3 mesh classes; `world_edges` key).
- `gtamapdata/landmarks.json` (Portofino NE/NW retriangulated, S locked
  equilateral, +WDNA points). Backups: `.bak_pre_S_equilateral` etc.
- `gtamapdata/pixels.json` (removed Sidewalk E's Venetian markings).
  Backup: `.bak_pre_remove_venetian_sidewalkE`.

### TODO next session

1. The robust triangulator now lets MANY previously-excluded leak C cams source
   LMs. Consider a sweep: re-triangulate LMs that gained good (parallax-checked)
   sources, then re-run `compute_confidence_tiers.py`.
2. Rooftop Party ypr may want a `refine_cam_ypr` pass (it's the one cam the
   Portofino mesh is off on).
3. Optional: make the outlier rule allow dropping down to 2 cams when the
   outlier is egregious (currently needs >3 to reject) — Alexandre was leaning
   "conservative, leave as-is".


---

### Session 2026-06-XX — Chantier A (sweep retriangulation) DONE

**A1.** Construit `tools/audit/retriangulation_candidates.py` (READ-ONLY). Scanne
les 857 LM, rejoue observers → classify_cam → select_sources → robust_triangulate,
classe par gain (parallaxe≥15° ET delta≥2m ET ≥2 sources post-dedup). Réutilise
les fonctions de triangulate_lm (zéro reduplication sauf l'acos pairwise).
Sortie taggée CAND/NEAR/NOBASE/SKIP. Résultat: 34 CAND / 236 QUASI / 586 SKIP.

**A2.** 31 LM retriangulés via robust triangulator (29 batch + Mount Mountain
+ Mount Waffles). Gains majeurs: Wheelabrator S Broward (+31m), MIA North
Terminal (+29m), Mount Mountain (+16m via Hedge B). La plupart des gains
viennent des leak C nouvellement autorisées comme sources.

**Hedge (B)/(C) (X)** : confirmées leak C légitimes (glitch sous-map, mais xyz
console exact → origine de rayon valide). Le "(X)" du nom = label positionnel,
PAS la classe doctrine X. Formalisées `cc=C_pos_fov_only` dans cameras.json.
NE PAS ajouter d'exclusion par nom dans classify_cam (bannirait des leak C valides).

**Quarantaine (5 LM, non appliqués)** : résidu élevé ou base trop étroite.
- Park Grove Condominium (N): laissé à error_m=1.882. Retriangulation tirée à
  11.66' par Grassrivers 02; l'outlier rejection ne le drop pas (règle >3 cams).
- Trésor Tower (9.98'), W South Beach (BNW) (8.35'), Di Lido Island (N) (6.99'),
  Three Tequesta Point (6.01'): benchés. À revoir après refine_cam_ypr de
  Rooftop Party (source de W South Beach BNW notamment).

**A3.** compute_confidence_tiers.py regénéré (174 cam changes, convergé pass 3:
anchor 17c/91lm, high 36/110, medium 16/237, low 9/12, unverified 96/407).
Aucune régénération mesh: aucun des 31 LM recalés n'est une ancre de
PortofinoTower/WDNAFM/OneThousandVenetian; find_mary_brickell() est live (no cache).

**Dette connue** : compute_confidence_tiers warne sur Hedge B/C "no audit entry"
(il lit leak_cam_audit.json, pas le cc de cameras.json). Cosmétique, fallback =
fully-locked legacy (bénin pour xyz valide). Ajouter entrée audit pour silencer
si ça gêne — pas fait pour éviter d'inventer des valeurs HUD sur des cams glitch.

---

### Session 2026-06-03 — Chantier B (cycles de dependances) DONE

**Livrable**: tools/audit/circular_deps.py (READ-ONLY) + tools/generated/dep_graph.json
(regenerable, non versionne). Graphe cam->cam B-strict COMPLET (reutilise
build_indices/is_leak de audit_leak_influence_tree, applique a TOUTES les cams)
+ Tarjan SCC. Classe PUR (aucune leak) vs SAIN (leak dans la boucle).
Graphe: 77 noeuds, 464 aretes, 8 D/X exclues.

**5 SCC taille>=2: 2 SAINS, 3 PURS.**
SAINS (RAS): 42 cams (coeur Vice City/Keys), 16 cams (Diner/Waffles, Hedge B OK).

PURS:
1. AMBROSIA (04 Fires / 02 Panorama / Postcard X) — etait GRAVE, MAINTENANT
   ANCRABLE. 35 LM orphelins dont faux-high Sebring Water Tower A/B et
   1500 Sonora Ave (Tank) (confiance interne au cluster, trompeuse).
   ANCRES TROUVEES cette session:
     - Ambrosia 04 -> Sunshine Skyway Bridge (N): residu pose 0.6' (anchor,
       source Diner/leaks). Deja marque.
     - Ambrosia 02 -> mat WDNA: VERIFIE par repro pile WDNA (z=5->404), tombe a
       10 arcmin / 12px des clics sur le mat reel (4 points) -> c'est WDNA.
       WDNA source Prison/Leonida = ancre INDEPENDANTE d'Ambrosia.
   Cluster a donc 2 pieds externes (04->Skyway, 02->WDNA): pas auto-referentiel
   en realite, juste pas encore exploite dans les sources.
   RECALIBRATION DU CLUSTER sur ancres externes (= session dediee; rouvre le
   roll, donc a coupler avec la dette roll): marquer WDNA comme contrainte
   verticale plein-cadre sur 02 (sommet flou -> plusieurs points le long du mat),
   refine_cam_full (7 params dont roll libre, deja supporte) sur 02 puis 04,
   Postcard si contrainte par LM partages, PUIS retrianguler les 35 LM Ambrosia.
   REGLE ANTI-BOUCLE: WDNA reste source Prison/Leonida, JAMAIS Ambrosia.
   A fusionner avec la dette ROLL (Jason at sea, Chase 2).
   Wheelabrator/MIA (sweep A): bougeront quasi pas au recalage (02 deja a 10').
2. PORT GELLHORN (Postcard X / 04 Delights X / Postcard) — MOYEN. 45 LM
   orphelins (Bay, faible enjeu). 'Port Gellhorn Postcard' a source=''.
3. CHASE2 (Chase 2 A/B / U-Turn NW) — BENIN. Ancre par voisinage. 2 LM orphelins:
   Radio Tower #1 (Port Gellhorn), Sunshine Skyway Bridge (S) (NO_BASELINE 2585'
   du sweep A, a benner).

FakeCam WDNA: envisagee puis ECARTEE (reprojeter depuis xyz Ambrosia actuels
gelerait le cluster sans info externe). L'ancrage reel = WDNA observe sur 02.

---

### Session 2026-06-03 — Chantier C1 (incertitude par LM) DONE

**Livrable**: tools/audit/lm_uncertainty.py (READ-ONLY) + tools/generated/lm_uncertainty.json
(regenerable, non versionne, ~3min pour 382 LM a N=200).

Monte-Carlo par LM. Moteur: rayons reconstruits a la main (cam.xyz +
get_pixel_direction(pixel)) pour injecter bruit pixel ET pose independamment sans
toucher l'etat global ml. robust_triangulate fige le jeu 'kept' une fois, puis N
tirages perturbes -> covariance empirique -> rayon scalaire = sqrt(trace(cov)).

Modele de bruit:
  - sigma_px = 3px (constant, v1; hook pour variable plus tard).
  - sigma_pose par TIER cam (anchor 0.5m/0.05deg ... unverified 15m/1deg).
  - LEAK cams: sigma quasi nul (0m / 0.02deg) — pose HUD = verite, le tier d'une
    leak reflete ses markings pas sa pose. (Correction cle: sans ca, les LM
    ancres sur leaks etaient injustement penalises.)
  - tirages divergents (>10km du init, LSQ explose a parallaxe ~0) rejetes.

DECOMPOSITION cle: r_pose (bruit pixel+pose) vs r_pix (pixel seul), ratio=r_pose/r_pix.
  - ratio ~1 -> fragilite PHYSIQUE (point lointain, pixel x distance). Irreparable.
    Ex: Mount Mountain (16m, 2 leaks a 109deg mais dist 7000). Rien a faire.
  - ratio >2 -> fragilite REPARABLE (poses sources fragiles). Ex: Sebring (ratio 3.6).
    Action: reancrer les cams sources.

RESULTAT — l'insight central: RMS != incertitude. Des LM a residu ~0' ont
±100m+ d'incertitude (Wildfire Scooters: res 0', r_pose 150m). Le RMS mesure si
les rayons se croisent; le MC mesure si la position tient quand les poses bougent.

CONVERGENCE avec Chantier B: les 3 cycles purs ressortent spontanement en tete du
classement d'incertitude, sans lien code entre les deux outils:
  - Ambrosia -> billboards (Large Billboard, Diversity Motif), ratio 17-24.
  - Port Gellhorn -> Juice Fruit Sign x4 (ratio 60-65), Radio Tower #1 (97).
  - Chase2 -> Wildfire Scooters (ratio 330-660).
  Deux methodes independantes (graphe Tarjan vs propagation MC) pointent les memes
  zones = forte validation croisee.

Validation sweep A: Wheelabrator (124m, ratio 3.5) et MIA North (81m, ratio 3.3)
confirmes sous-contraints et REPARABLES -> coherent avec la prudence de la session B.

Facteur dominant de fragilite: nsrc=2. Quasi tout le top a 2 sources (incertitude
portee par la seule parallaxe). Regle de priorisation collecte: tout LM 2-sources
non-leak a ratio>2 = candidat a une 3e source / reancrage.

C2 (exposer dans le viewer) et C3 (remplacer les poids tier discrets du
bundle_adjust par la covariance) = sessions futures. sigma_pose sont des hypotheses
a calibrer (le CLASSEMENT relatif est robuste; les metres absolus dependent des sigma).

---

## Roadmap niveau supérieur (planifiée 2026-06-XX)

Objectif global : faire passer gtamaplib de "débogage expert au coup par coup"
à "pipeline rigoureux qui raisonne sur tout le réseau". Trois chantiers
INDÉPENDANTS. Ordre conseillé A → B → C (gain immédiat → explication
structurelle → fondation statistique). Chacun est autonome ; on peut en faire
un par session.

Rappels transverses pour TOUS les chantiers :
- Claude n'a PAS accès au disque : il écrit des commandes/scripts one-shot,
  Alexandre les lance et colle l'output.
- Scripts idempotents, dry-run par défaut, `--apply` pour écrire, backups
  `.bak_<reason>`. Scripts d'audit READ-ONLY dans `tools/audit/`.
- Le juge de toute triangulation = PARALLAXE + DELTA, jamais le RMS seul.
- Le robust triangulator (`tools/triangulate_lm.py`, session 2026-05-31) est
  la référence : classify par classe (A>C, exclude D/X), parallax filter 15°,
  collinear dedup <5°, outlier rejection >2x median & >5'.

---

### CHANTIER A — Sweep de retriangulation (quick win, ~1 session)

**Pourquoi** : avant la session 2026-05-31, les leak C étaient exclues comme
sources (tier low). Le robust triangulator les autorise maintenant (pos+fov
HUD-locked = ray origin exacte). Donc beaucoup de LM ont gagné des sources
fiables et peuvent être retriangulés — mais on ne sait pas lesquels en
profiteraient vraiment. Il faut un audit systématique, pas du cas par cas.

**Étape A1 — `tools/audit/retriangulation_candidates.py` (READ-ONLY)**
Pour chaque LM dans landmarks.json :
- lister ses observers (cams avec un pixel dans pixels.json), classer chacun
  via la même logique que `classify_cam` (leak_a / leak_pos / trusted / other
  / excluded — réutiliser/importer la fonction, ne pas la redupliquer).
- calculer la MEILLEURE parallaxe atteignable entre paires de sources non
  exclues (réutiliser le calcul d'angle entre rayons).
- estimer la position qu'une retriangulation robuste donnerait (peut appeler
  la logique de robust_triangulate en dry-run / import), et le delta vs xyz
  actuel.
- flag "gain potentiel" = (best_parallax >= 15°) ET (delta > seuil, ex. 2m)
  ET (sources kept >= 2 après dedup).
- sortie triée par delta décroissant : `LM | nb sources | best_parallax |
  delta | kept sources | flag`.
Aucune écriture. C'est la carte de ce qui vaut la peine.

**Étape A2 — application en lot contrôlée**
- dry-run `triangulate_lm.py "<LM>"` sur les candidats flaggés, vérifier que
  le log (parallaxe/dedup/outlier) est sain cas par cas.
- `--apply` sur ceux qui sont propres. Skip les delta ~0 (déjà bons) et les
  résidus douteux.
- Attention pièges connus : LM au bord de frame (markings imprécis, ex.
  Venetian depuis Sidewalk E), LM dont toutes les sources sont dans un même
  cluster (parallaxe faible même si nombreuses), LM ancres de mesh (vérifier
  l'impact sur le mesh après).

**Étape A3 — clôture**
- `compute_confidence_tiers.py` → voir les promotions de tier.
- éventuellement `bundle_adjust_weighted.py` + apply pour le polish global.
- regénérer les meshes touchés (`extract_mesh_edges.py`) si des ancres ont bougé.
- commit.

Livrable : un audit réutilisable + N LM recalés proprement + tiers à jour.

---

### CHANTIER B — Détection de cycles dans le graphe de dépendances (~1-2 sessions)

**Pourquoi** : le problème circulaire vu sur Portofino (Amphitheater source
des LM qui re-valident Amphitheater ; Sidewalk E sourçait Portofino NE dont
elle dépendait) est STRUCTUREL. Aujourd'hui on le découvre à la main quand un
LM a l'air faux. On veut le détecter sur tout le réseau.

**Étape B1 — `tools/audit/build_dep_graph.py` (READ-ONLY)**
Construire le graphe dirigé : pour chaque LM, ses `source_cameras` → arêtes
cam→LM. Pour chaque cam non-leak, les LM qui l'ont calibrée (via intake /
historique) → arêtes LM→cam. Les leak cams sont des racines (ground truth, pas
de parent). Sortir le graphe (dict adjacence + dump JSON dans tools/generated/).

**Étape B2 — `tools/audit/circular_deps.py` (READ-ONLY)**
- détecter les composantes fortement connexes (Tarjan/Kosaraju) — les cycles
  où des positions se valident mutuellement sans ancrage externe (leak).
- pour chaque cycle : lister les entités, le maillon le plus faible (classe /
  tier le plus bas), et dire "ce cycle a besoin d'un point d'ancrage externe
  (leak A ou anchor LM indépendant)".
- distinguer cycles "sains" (au moins une racine leak fiable dans/proche) des
  cycles "auto-référentiels purs" (aucune ground truth → suspect).

**Étape B3 — visualisation / action**
- marquer les zones auto-référentielles dans le viewer ou cam_health dashboard
  (couleur d'alerte).
- pour chaque cycle pur, proposer la cam/LM à ancrer en priorité.

Livrable : `circular_deps.py` + carte des zones auto-référentielles de la map +
liste priorisée d'ancrages manquants.

---

### CHANTIER C — Incertitude quantifiée par LM (ambitieux, ~2 sessions)

**Pourquoi** : tout le projet juge la qualité par RMS + parallaxe à la main, et
les poids du bundle adjust sont des tiers discrets (anchor=15, high=7.5, ...).
Une vraie covariance par LM dirait objectivement lesquels des 56 LM ancres sont
fiables et lesquels sont fragiles.

**Étape C1 — covariance par LM**
- pour chaque LM triangulé, propager l'incertitude : bruit pixel (~quelques px,
  pire au bord/loin) + incertitude pose des cams sources → ellipsoïde de
  covariance 3D (Jacobien de la triangulation, ou Monte-Carlo si plus simple).
- sortir, par LM, les axes/volume de l'ellipsoïde (un "rayon d'incertitude").

**Étape C2 — exposer dans le viewer**
- couleur/taille du dot LM ∝ incertitude (vert = serré, rouge = flou).
- endpoint server + frontend.

**Étape C3 — intégrer au bundle adjust**
- remplacer/compléter les poids de tier par l'inverse de la covariance
  (information matrix) dans `bundle_adjust_weighted.py`. Le BA devient
  statistiquement fondé (Gauss-Markov), plus de tiers arbitraires.

Livrable : incertitude réelle par LM, visible + utilisée par le BA.

---

### Reprises rapides en attente (TODO court)
- **Rooftop Party** : `refine_cam_ypr` — seule cam où le mesh Portofino dévie
  (c'est SA calibration qui drifte, pas le mesh ; ne pas toucher le mesh).
- **`git push origin feature-solver`** — vérifier que les commits sont backés.
- Optionnel : assouplir l'outlier rule du robust triangulator pour autoriser
  la descente à 2 cams quand l'outlier est flagrant (actuellement >3 requis ;
  Alexandre penchait "conservative, leave as-is").


## [SESSION-20260607-CHASE-CLUSTER] 2026-06-07 — Chase cluster, AI World Map doctrine, angular-precision limit

### Chase (2) (A) — RESOLVED (was loss 20.7 "Suspicious" -> RMS 2.4px)
Root cause was NOT pose: A's position/orientation were fine all along (moved 0.2m on recal).
The 20.7 loss came from two FAR landmarks (Sunshine Skyway Bridge N at 1311m, S at 1084m)
that A physically sees but cannot point precisely. A is a chase-frame cam from a floating
cluster: its angular precision is ~0.8deg. That 0.8deg is invisible on close LMs (<600m, all
at <5px) but explodes to 50-68px on the SSB at >1km. rlx had already excluded SSB(N) from A
for this reason.
Fix: removed SSB(N) marking from A; kept SSB(S) marking on A as observation but re-sourced its
position to Chase (2) (B) and excluded both from A's pose fit. A then recals to RMS 2.4px on
Juice Fruit x4 / Pylon(3) / Radio Tower #1 / Wildfire NW+S / Oval Yellow.

### DOCTRINE: angular precision vs landmark distance
A camera's finite angular precision sets a max usable landmark distance. Floating-cluster cams
(~0.8deg) are reliable only on near/mid LMs; very distant LMs (>~1km) will show large pixel
residuals that are NOT pose errors and NOT bad markings — they exceed what the cam can resolve.
Mark them as observations if visible, but EXCLUDE them from the pose fit. Forcing them corrupts
the pose (tug-of-war: distant LM wins -> near LMs break, or vice versa). No single pinhole pose
satisfies both. This is the "Mercator" problem: model can fit center OR edge, not both.

### DOCTRINE: AI World Editor Map (4K) pollutes 3D positions
Top-down (Google-Maps style), class D. Good x/y, z=10 default. BUT its top-down click is
imprecise (flat blurry aerial), so when it is a SOURCE for a landmark that also has good ground
views, it PULLS the position and creates residuals. Example today: Wildfire Scooters (S) was
perfect on AIW+B (0px) but 186px on A because AIW pulled it 5.3m off. Fix = retriangulate from
ground views, or use a 3-view equal-weight optimum. Wildfire (S) repositioned to 3-view optimum
[-6457.9, 3328.6, 9.0]: A 3.8px / B 7.6px / AIW 6.9px (was A 186px). Of 70 AIW-sourced LMs, 52
are AIW-only and all at z=10 (ground points, fine); only ~2 high LMs were correctable.

### Cluster bundle-adjustment solver — VALIDATED
Built and validated a solver that optimizes Chase(2) A+B poses + shared-LM positions together,
hard anchors (SSB N, Pylon 3) weighted 8x, prior roll, method trf. KEY LESSON: LMs with an
EXTERNAL source (non-cluster cam) must stay FIXED, not free — e.g. Radio Tower #1 is anchored by
U-Turn (NW) and is perfect there; letting it float made the solver drag it 69m to chase A. Only
truly-orphan LMs (no external source) are free. B solved cleanly (RMS 4.5px); A could not be
forced to satisfy SSB -> confirmed the angular-precision limit above. Solver is reusable; good
candidate for a tools/cluster_solve.py.

### Other this session
- Amphitheater: repositioned to rlx pose [-350,-100,8] (map proof beat the distant-LM "validation").
- Port Gellhorn Smokestack: z 49.9 -> 53.68 (ground cams Lucia+Jason, 0deg parallax so best-effort,
  RMS 5.8px). rlx has 49.861 (same top-down bias); we diverge on geometric grounds.
- NEXT (step 2): extract Chase scene frames from Trailer 2 (~2s) -> COLMAP SfM -> dense
  reconstruction to anchor the floating Port Gellhorn / west region. Manual per-frame marking of
  60 frames is NOT worth it; COLMAP (auto feature matching) is the right tool.

### Session 2026-06-08 — Beach/Metro/Ambrosia fixes + retriangulation sweep

RAPPEL CRITIQUE POUR PROCHAINES SESSIONS: commencer par lire ce fichier ET
lancer `circular_deps.py` + `lm_uncertainty.py` AVANT de toucher une cam.
Beaucoup de temps perdu cette session a re-decouvrir a la main des choses deja
faites/documentees (cycles Ambrosia, RMS!=incertitude, ancres WDNA/Skyway).

DATA ECRITE:
- Metro (SE) (C): reclassee None->C_pos_fov_only, pose HUD [-1555.7,-308.5,20.8]
  fov [None,49.6] (lue sur screenshot debug). RMS reste 23' = 3 LM mal positionnes
  (Ritz Coconut Grove S, Infinity Brickell, Park Grove N), pas la pose. NB: le
  "(C)" du nom != classe; Metro (SE) (B) est la vraie leak C voisine.
- Beach: z corrige -1.9 (sous l'eau!) -> 1.0. Cam de PROJECTION-SOL (coastline
  Beach A-F = intersection rayon-sol z=0, pas triangulation). z/pitch critiques
  pour ces cams. rlx pose [2219,-407,1.692] donne 27px sur NOS batiments ->
  referentiels divergents dans cette zone, garde la notre (4.5px).
- Ambrosia 02 (Panorama): refine_cam_full applique, RMS ~8px -> 5.24'. Reste
  US Sugar Mill R a 11.7'. PAS d'ancre WDNA marquee (manuel, pas fait).
- Retriangulations (parallaxe ~146-167deg, robust_triangulate): MIA North
  Terminal Tower (1.6'), Wheelabrator South Broward (2.7'), FAA Miami ATCT (3.2')
  [les 3 via Ambrosia02 x Leonida Keys 01 - baseline externe], Di Lido Island N
  (6'), Three Tequesta Point (6').
- SKIP volontaire: W South Beach BNW (marking Rooftop Party 8' suspect, gain 2m),
  Tresor Tower (marking Beach 9' suspect, gain 3m). Markings mous, gain marginal.

DOCTRINE confirmee (rien de neuf, deja dans logs C1/B mais re-prouve):
- Ambrosia = cycle PUR (circular_deps): 02/04/Postcard se calent entre eux. Les
  Silos/Smokestacks vus seulement par 02xPostcard a 2.5deg parallaxe = NON
  triangulables, plancher ~7px. Irreparables sans ancre. NE PAS s'acharner.
- "Sourced by cam X" ne garantit PAS 0px: si 2e source faible-parallaxe OU si la
  position est un compromis de rayons gauches. RMS != verite (cf C1).
- Les 2 pieds externes d'Ambrosia existent (04->Skyway N deja marque,
  02->WDNA pas encore marque). Vraie repair = marquer WDNA mat sur 02 (projette
  ligne verticale x~565, z=5..404 deja positionnes via Prison), refine_full 02,
  retrianguler. REGLE ANTI-BOUCLE: WDNA reste source Prison/Leonida JAMAIS Ambrosia.

NOUVEAUX SCRIPTS (cette session, possiblement redondants avec l'existant):
- tools/observability_report.py: carte stale/floating/under-anchored par zone.
  RESULTAT: 73/90 soft cams voient <2 ancres dures. vice_city=42% hard (roc),
  ambrosia=0% (floating), port_gellhorn=15%, leonida_keys=17%.
- tools/global_solve.py: bundle adjustment global SHADOW par zone, Huber loss,
  prior position (0.5) anti-teleportation. vice_city shadow: 15 IMPROVED 0 WORSE
  (Vice City Sign 200->0, Basketball 27->2, Yacht 14->1, Vice City 08, etc.).
  PAS ENCORE APPLIQUE EN ECRITURE. Note: recoupe audit_leak_influence_tree +
  retriangulation_candidates existants - a rationaliser.

PENDING (prochaine session):
- APPLIQUER global_solve sur vice_city en ecriture (poses cams IMPROVED seulement,
  blacklist Beach/Amphitheater/Vice Beach A, pas les landmarks). C'EST LE LIVRABLE.
- Marquer WDNA sur Ambrosia 02 -> recalibrer cluster sur ancres externes.
- Rationaliser observability_report/global_solve vs outils audit/ existants.

### REFLEXE D'OUVERTURE DE SESSION (ajoute 2026-06-08)

AVANT de toucher une cam, lancer ces 3 outils existants (ne PAS en recoder):
  1. python3 tools/audit/circular_deps.py
     -> cycles PURS (auto-ref, besoin ancre externe) vs SAINS. Ne pas recaler les PURS.
  2. python3 tools/audit/audit_leak_influence_tree.py
     -> ancrage TRANSITIF (multi-hop) au reseau dur. Une cam reliee (downstream
        d'une leak) est calibrable; une cam a ZERO downstream est isolee.
  3. python3 tools/audit/lm_uncertainty.py (ou lire tools/generated/lm_uncertainty.json)
     -> incertitude par LM. ratio>2 = reparable (reancrer sources); ratio~1 = physique, irreparable.

REGLE D'OR (apprise a la dure 2026-06-08): bouger une cam INVALIDE ses LM enfants,
toujours. Une cam ne se recale que sur des ancres EXTERNES (pas ses propres LM
engendres), et l'ancrage est TRANSITIF (via chaine de LM partages), pas seulement
direct. Un detecteur "1-hop hard anchors" (calibratability.py, supprime) est FAUX:
il declarait 0 calibrable alors que 51 cams le sont par propagation.

NON-REPARABLES connues (ne pas s'acharner):
  - Amphitheater: dans cycle Chase2/Portofino/Cranes, 2 ancres dures externes
    contradictoires avec fov reel (14px plancher). Reste sur pose rlx.
  - Ambrosia Silos/Smokestacks: parallaxe 02xPostcard ~2.5deg, non triangulables.
    Besoin ancre WDNA marquee sur 02 (mat vertical, projette x~565).

### CHANTIER PRIORITAIRE (diagnostique 2026-06-08) — Rebrancher l'ordre de calib sur le vrai graphe

PROBLEME DE FOND identifie: l'ordre de calibration ne respecte PAS le dependency
tree a jour. Trois sources d'ordre DECONNECTEES:
  - dep_graph.json (genere par circular_deps.py, 3 juin): LE vrai graphe.
    Structure {meta, adjacency}. adjacency[A]=[B,C] => "A depend de B,C"
    (B,C doivent etre calibrees AVANT A). 77 noeuds, B-strict, D/X exclus. A JOUR.
    -> Lu par PERSONNE pour planifier l'ordre.
  - calibration_plan.py: scrape docs/index.html par REGEX. Or index.html date du
    6 MAI (1 mois plus vieux que dep_graph). Ordre PERIME. CASSE.
  - calibration_order.py: score par tiers (anchor+high), ignore le graphe.

FIX (prochaine session, faire proprement, PAS en fin de session):
  1. Remplacer parse_tree_order() de calibration_plan.py: lire dep_graph.json au
     lieu de scraper index.html.
  2. Calculer l'ordre TOPOLOGIQUE depuis adjacency (leaks/ancres d'abord, puis
     cams dont toutes les deps sont satisfaites, niveau par niveau).
  3. Cycles purs (Ambrosia/Port Gellhorn/Chase2, deja detectes par circular_deps
     via Tarjan) = marquer "non-ordonnable sans ancre externe", ne pas inserer.
  4. Idealement aussi rebrancher calibration_order.py, ou le deprecier au profit
     de calibration_plan.py.
  RESULTAT VISE: un seul ordre de verite, derive du graphe regenere par
  circular_deps.py -> "l'ordre de calibration respecte en tout temps".
  Workflow d'ouverture: circular_deps.py (regen graphe) -> calibration_plan.py
  (ordre a jour) -> calibrer dans cet ordre.

REGLE D'OR (rappel): bouger une cam invalide ses LM enfants. Calibrer parent
AVANT enfant. C'est exactement ce que l'ordre topologique garantit.

### RECTIFICATION (2026-06-08, meme jour) — l'ordre de calib EST deja resolu

Le bloc "CHANTIER PRIORITAIRE rebrancher sur dep_graph" ci-dessus est ERRONE.
Diagnostic corrige apres verification:

- dep_graph.json n'est PAS un DAG. Les cams voisines se referencent
  mutuellement (Diner NE <-> Diner N <-> ...). Aucune racine, tout est cycle.
  => IMPOSSIBLE d'en tirer un ordre topologique. Ce graphe sert UNIQUEMENT a
  circular_deps.py pour detecter les cycles PURS (Ambrosia/PortGellhorn/Chase2).

- L'ORDRE DE CALIBRATION correct = calibration_order.py. Algo glouton ancre:
  score chaque cam par #LM anchor+high, prend la mieux ancree, "promeut" ses
  LM self-source comme fiables, repete. C'est l'algo JUSTE pour un graphe
  cyclique avec ancres (leaks). Lit confidence_tiers.json (a jour). Marque
  chaque cam READY (loss<seuil) ou BROKEN avec le loss reel. Validation
  croisee OK: il classe Amphitheater BROKEN 111', Chase2A READY 2.92' —
  exactement nos conclusions manuelles.

- calibration_plan.py = SUPPRIME. Etait casse (scrapait docs/index.html par
  regex, fichier du 6 mai donc 1 mois perime) ET doublon de calibration_order
  ET conceptuellement faux (pretendait un tri d'arbre sur un graphe cyclique).

WORKFLOW D'ORDRE (le bon, definitif):
  1. compute_confidence_tiers.py   (regenere les tiers depuis l'etat actuel)
  2. calibration_order.py --tier <...>   (ordre glouton ancre, a jour)
  3. calibrer les cams READY ; investiguer/laisser les BROKEN.
  (calibrate_session.py --from-order branche deja sur calibration_order.)

ATTENTION calibrate_batch.py: lui AUSSI lit docs/index.html (6 mai, perime) pour
son ordre (parse_tree_order ligne 90, "Loaded N cams from docs/index.html order").
Et il ECRIT (applique ypr/xyz/fov + retriangule). Donc son ordre est perime d'un
mois. NE PAS l'utiliser tel quel. Preferer calibrate_session.py --from-order
(branche sur calibration_order, a jour). TODO futur: rebrancher calibrate_batch
sur calibration_order, ou le supprimer s'il fait doublon avec calibrate_session.
