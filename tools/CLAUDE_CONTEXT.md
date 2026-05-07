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
- **Last session** : 2026-05-07 — cleanup repo (audit/refine/_archive split)

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
