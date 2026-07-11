# gtamaplib — Tools & Features Inventory
Auto-generated. Run `python3 tools/generate_inventory.py` to refresh.
Bookmark this file when you forget what tools exist.

## Quick reference — "Where do I start?"

### Adding a new T3 cam (cold-start workflow)
```
1. Place frame in frames/{Cam Name}.png
2. Run: python3 tools/compute_confidence_tiers.py
3. Add cam entry to gtamapdata/cameras.json with dummy xyz/ypr/hfov
4. Mark 3+ landmarks in the calib UI (http://localhost:8765)
   -> Assist mode: P1/P2 prioritized ghosts, click = arm the marking
5. Run: python3 tools/intake_camera.py "Cam Name"
   -> see verdict (commit/review/reject) before applying
6. If verdict OK: python3 tools/refine_cam_full.py "Cam Name" --apply
   (the UI Optimize/Update LMs buttons are DECOMMISSIONED)
7. Re-run compute_confidence_tiers.py to update tiers
8. Global: bundle_adjust_weighted.py --cleanup, then guarded_apply
   (NEVER bundle_adjust_apply.py — blind wholesale apply is forbidden)
```

### The global cycle (guarded apply)
```
python3 tools/compute_confidence_tiers.py
python3 tools/bundle_adjust_weighted.py --cleanup --max-iter 30
python3 tools/refine/guarded_apply.py            # dry-run, review
python3 tools/refine/guarded_apply.py --apply
python3 tools/audit/rms_snapshot.py --tag <name>
PYTHONPATH=. python3 tools/ci_healthcheck.py --update-baseline  # if improved
```

### Triage — "Where is the pain?"
```
UI: Triage button (categorizes cams >5' + one-click actions)
CLI: python3 tools/outliers_report.py
     python3 tools/calibration_order.py --tier unverified
```

### Map evidence — "Is the position real?"
```
UI: LM inspector -> yanis crop + "propose retriangulation" + verdict
CLI: python3 tools/map_validate.py (HTML contact sheet)
Semantics: validated = map prior (5m budget), NOT frozen; rejected = excluded
```

### CI — guardrail on every push
```
PYTHONPATH=. python3 tools/ci_healthcheck.py   # locally before commit
Baseline: tools/ci_baseline.json (--update-baseline after an improvement)
```

---

## CLI Scripts (tools/*.py)

Total: 44 scripts

### `batch_optimize.py`
Batch-optimize multiple cams via the running server API.

**Usage:**
```
python3 tools/batch_optimize.py --tier unverified           # dry-run all unverified
    python3 tools/batch_optimize.py --tier unverified --apply   # actually run
    python3 tools/batch_optimize.py --cams "Yacht (1),Yacht (2)" --apply
    python3 tools/batch_optimize.py --tier low --apply --update-lms --update-threshold 5.0
    python3 tools/batch_optimize.py --apply --polish            # batch optimize + bundle_adjust
```

### `build_cam_health.py`
Generate tools/cam_health.html from live data.

### `bundle_adjust.py`
Two-pass bundle adjustment.

### `bundle_adjust_apply.py`
Apply bundle adjustment results to cameras.json and landmarks.json

### `bundle_adjust_weighted.py`
Phase C of the T3 intake pipeline.

### `calibrate_batch.py`
Interactive batch calibration following the topological

**Usage:**
```
python3 tools/calibrate_batch.py
    python3 tools/calibrate_batch.py --start-from "Vice Beach (B)"
    python3 tools/calibrate_batch.py --auto   # accept all without prompting (DANGEROUS)
```

### `calibrate_cam.py`
Narrative calibration assistant for a single camera.

**Usage:**
```
python3 tools/calibrate_cam.py "Yacht (1)"
    python3 tools/calibrate_cam.py "Leonida Keys 02 (Sidewalk)"
```

### `calibrate_session.py`
Interactive calibration session for a list of cams.

**Usage:**
```
python3 tools/calibrate_session.py --cams "Motorboats (A),Yacht (1)"
    python3 tools/calibrate_session.py --tier unverified --limit 5
    python3 tools/calibrate_session.py --from-order  # uses calibration_order
```

### `calibration_order.py`
Suggest optimal calibration order for a set of cams.

**Usage:**
```
python3 tools/calibration_order.py --tier unverified
    python3 tools/calibration_order.py --cams "Yacht (1),Yacht (2),Vice Beach (A)"
    python3 tools/calibration_order.py --tier unverified,low
```

### `ci_healthcheck.py`
CI guardrail: runs on every push (GitHub Actions) and

**Usage:**
```
PYTHONPATH=. python3 tools/ci_healthcheck.py
    PYTHONPATH=. python3 tools/ci_healthcheck.py --update-baseline
```

### `common.py`
Shared helpers for the gtamaplib tools.

### `compute_confidence_tiers.py`
Classify every cam and landmark into a confidence tier.

### `compute_venetian_xyz.py`
Computes the xyz of the 1000 Venetian Way LMs that are

**Usage:**
```
python3 tools/compute_venetian_xyz.py            # dry-run, print propositions
    python3 tools/compute_venetian_xyz.py --apply    # write to landmarks.json
```

### `cycle.py`
- LE cycle standard en une commande. [CYCLE-V1, 2026-07-07]

**Usage:**
```
python3 tools/cycle.py --tag ma_session                    # cycle standard
  python3 tools/cycle.py --tag t --harvest --scan            # apres imports/markings
  python3 tools/cycle.py --tag t --update-baseline           # si amelioration a geler
  python3 tools/cycle.py --tag t --commit "message"          # + git add/commit (pas de push)
```

### `densify_portofino_edges.py`
densify_portofino_edges.py

### `discover_mesh_candidates.py`
Find LM prefixes that could become procedural

### `exclude_marking.py`
exclude a (cam, lm) marking from the solver WITHOUT

**Usage:**
```
python3 tools/exclude_marking.py "Cam Name" "LM Name"            # exclude (dry-run)
  python3 tools/exclude_marking.py "Cam Name" "LM Name" --apply    # ecrire
  python3 tools/exclude_marking.py "Cam Name" "LM Name" --remove --apply  # re-inclure
  python3 tools/exclude_marking.py --list                          # tout lister
```

### `extract_mesh_edges.py`
Extract wireframe edges from gtamaplib's procedural Landmark classes

### `fit_minimal.py`
self-consistency bootstrap for under-determined cams.

**Usage:**
```
python3 tools/fit_minimal.py "Green Sports Car"              # dry-run
    python3 tools/fit_minimal.py "Green Sports Car" --apply
    python3 tools/fit_minimal.py "Landing Gear (B)" --solve-roll # 4th DOF
    python3 tools/fit_minimal.py --list                          # candidates
```

### `fix_audit_orientations.py`
Reconcile leak_cam_audit.json with cameras.json

### `gen_missing_thumbs.py`
Generate thumbnails for any calibrated cam that has

### `gen_portofino_lms.py`
Generate Portofino Tower LMs derived from 3 anchor LMs (NW, NE, S).

### `gen_portofino_precise.py`
Generate precise Portofino LMs based on measured pentagon dimensions.

### `gen_portofino_v2.py`
Generate complete Portofino mesh:

### `gen_portofino_v3.py`
Portofino V3: progressive widening.

### `gen_portofino_v4.py`
Portofino V4: corrected z levels and architecture.

### `generate_inventory.py`
Generate TOOLS_INVENTORY.md — a comprehensive map of everything available

### `intake_camera.py`
Validate a new (or existing) camera against the

**Usage:**
```
python3 tools/intake_camera.py "Some Cam Name"                  # ypr + hfov
    python3 tools/intake_camera.py "Some Cam Name" --refine-xyz     # also xyz, ±300m
    python3 tools/intake_camera.py "Some Cam Name" --no-hfov        # ypr only
```

**Workflow:**
```
1. Run compute_confidence_tiers.py first (produces tier JSON)
    2. Run this for each new cam → see verdict + diff
    3. If verdict is `commit`: refine_camera.py --apply to actually write
       (or apply manually via the calib UI)
    4. After committing changes, re-run compute_confidence_tiers.py to
       update the tier JSON, then bundle_adjust as usual.
```

### `leak_cam_audit.py`
Single source of truth for constraint-class semantics.

### `map_validate.py`
Map-proof at scale: generate a contact sheet of map crops

**Usage:**
```
# Generer le contact sheet (defaut: tiers low+medium avec xyz, pas deja juges)
  python3 tools/map_validate.py
  python3 tools/map_validate.py --tier low --zone vice_city
  python3 tools/map_validate.py --lms "Palazzo del Sol,Cruise Terminal D"
  # -> tools/generated/map_validate_sheet.html  (ouvrir dans le navigateur,
  #    cliquer les cartes: gris=?, vert=valide, rouge=rejete; Export -> JSON)
```

### `migrate_constraint_classes.py`
Migration step from V1 (no class info in

### `observability_report.py`
### `outliers_report.py`
Generate an HTML review report from bundle_adjust_result.json

### `port_rlx_batch.py`
Port all cams unique to rlx (with sourced timestamps)

**Usage:**
```
python3 tools/port_rlx_batch.py                # dry run (sourced cams only)
    python3 tools/port_rlx_batch.py --apply        # write changes
    python3 tools/port_rlx_batch.py --all          # include "?" sourced cams too
```

### `port_rlx_inventory.py`
port_rlx_inventory.py v4 — Read-only inventory of rlx upstream data.

**Usage:**
```
python3 tools/port_rlx_inventory.py            # generate report
    python3 tools/port_rlx_inventory.py --verbose
```

### `port_rlx_one_cam.py`
Port a single camera (and its pixels) from rlx's

**Usage:**
```
python3 tools/port_rlx_one_cam.py "Yacht (2)"             # dry run
    python3 tools/port_rlx_one_cam.py "Yacht (2)" --apply     # writes changes
```

### `portofino_v5.py`
Portofino V5 refactor - adds:

### `prerender_minimaps_fast.py`
bulk pre-render all missing minimaps.

**Usage:**
```
python3 tools/prerender_minimaps_fast.py
```

### `refine_cam_full.py`
Refine xyz+ypr+fov of a single non-leak camera using

**Usage:**
```
python3 tools/refine_cam_full.py "Vice Beach (B)"
    python3 tools/refine_cam_full.py "Vice Beach (B)" --apply
    python3 tools/refine_cam_full.py "Vice Beach (B)" --force-apply
```

### `refine_cam_ypr.py`
Refine the ypr of a single leak camera using

**Usage:**
```
python3 tools/refine_cam_ypr.py "Tennis Court (SE)"           # dry-run
    python3 tools/refine_cam_ypr.py "Tennis Court (SE)" --apply   # write
```

### `regen_index_camdata.py`
Regenerate the `const camData = {...}` block in

### `render_loss.py`
[RENDER-LOSS-V1] Render a local XY loss landscape for one camera.

### `sync_rlx.py`
- l'archeologie upstream automatisee. [SYNC-RLX-V1, 2026-07-07]

**Usage:**
```
git fetch upstream
  PYTHONPATH=. python3 tools/sync_rlx.py                  # vs dernier sync
  PYTHONPATH=. python3 tools/sync_rlx.py --since 396e7af  # vs ref explicite
  PYTHONPATH=. python3 tools/sync_rlx.py --apply          # ecrit ADD+SNAP,
                                                          # backups .bak_rlxsync,
                                                          # gele sync_state
Apres --apply: python3 tools/cycle.py --tag rlx_sync --harvest --scan
```

### `triangulate_lm.py`
Triangulate a single landmark using priority-based source selection.

**Usage:**
```
python3 tools/triangulate_lm.py "1000 Venetian Way (SW)"           # dry-run
    python3 tools/triangulate_lm.py "1000 Venetian Way (SW)" --apply   # write
```

---

## Audit Tools (tools/audit/*.py) — READ-ONLY

Diagnostic tools that NEVER modify data. Run periodically to check network health.

Total: 28 audit scripts

### `audit/audit_all_leak_opportunities.py`
For each non-LEAK cam with zero all_leak LMs

### `audit/audit_fixed_landmarks_quality.py`
For each FIXED landmark, evaluate the

**Usage:**
```
python3 tools/audit_fixed_landmarks_quality.py
```

### `audit/audit_leak_consistency.py`
Audit observations between LEAK cameras and

### `audit/audit_leak_influence_tree.py`
Compute the transitive influence of each LEAK

### `audit/audit_leak_marker_quality.py`
Audit reprojection errors for all markings

### `audit/audit_leak_priority_ranking.py`
Cross-reference LEAK cam influence with

### `audit/check_camera_consistency.py`
For each camera, count how often it produces

### `audit/check_landmark_consistency.py`
Detect landmarks where different cameras seem

### `audit/circular_deps.py`
READ-ONLY (Chantier B, etapes B1+B2).

**Usage:**
```
python3 tools/audit/circular_deps.py
    python3 tools/audit/circular_deps.py --dump-graph
    python3 tools/audit/circular_deps.py --min-scc 2
```

### `audit/collision_scan.py`
- WAR-SCAN-V1. Detecte a l'echelle les collisions de nom

**Usage:**
```
PYTHONPATH=. python3 tools/audit/collision_scan.py            # scan seul
  PYTHONPATH=. python3 tools/audit/collision_scan.py --plan     # + plan gated
  PYTHONPATH=. python3 tools/audit/collision_scan.py --apply    # execute le plan
  (--apply: exclude_marking + triangulate_lm CLI + snap z_constraint)
```

### `audit/compare_rlx_vs_current.py`
Compare camera positions between rlx (Initial commit)

**Usage:**
```
python3 compare_rlx_vs_current.py /tmp/cameras_rlx.json gtamapdata/cameras.json
```

### `audit/diagnose_camera.py`
Show every observation made by a given camera, ranked by

**Usage:**
```
python3 tools/diagnose_camera.py "Ambrosia 04 (Fires)"
    python3 tools/diagnose_camera.py "Diner (W) (B)"
```

### `audit/find_outlier_pixels.py`
List pixels with angular err > threshold that have

### `audit/find_z_candidates.py`
Scans landmarks.json to propose candidates for

### `audit/fossil_triage.py`

### `audit/invariants.py`
Pre-commit guardrail for gtamapdata/. Exit 1 on violation.

**Usage:**
```
python3 tools/audit/invariants.py            # check, exit 1 si echec
    python3 tools/audit/invariants.py --freeze   # (re)gele la reference leaks
Convention: rouler AVANT chaque `git commit` qui touche gtamapdata/.
```

### `audit/investigate_landmark.py`
For a given landmark, show where each camera's

**Usage:**
```
python3 tools/investigate_landmark.py "Easy Hill"
    python3 tools/investigate_landmark.py "Easy Inn Sign"
```

### `audit/keys_z_bias_analysis.py`
READ-ONLY. Where do the rays say sea level is?

### `audit/list_extra_observers.py`
Finds landmarks that have observers (cams

### `audit/lm_uncertainty.py`
READ-ONLY (Chantier C1).

**Usage:**
```
python3 tools/audit/lm_uncertainty.py --n 200 --top 60 --dump
  python3 tools/audit/lm_uncertainty.py --only "Sebring"
  python3 tools/audit/lm_uncertainty.py --no-pose   (bruit pixel seul)
```

### `audit/next_clicks.py`

### `audit/orphan_triage.py`

### `audit/retriangulation_candidates.py`
READ-ONLY audit (Chantier A, etape A1).

### `audit/rms_snapshot.py`
READ-ONLY. Per-cam RMS (arcmin) computed FRESH from disk.

### `audit/sigma_report.py`
- lecture de tools/generated/covariances.json. [COVARIANCE-V1]

**Usage:**
```
python3 tools/audit/sigma_report.py [--top 12] [--zone vice_city]
  python3 tools/audit/sigma_report.py --surprises   # tier vs sigma en conflit
```

### `audit/template_bench.py`

### `audit/tension_audit.py`
- WAR-SCAN niveau 2: structure de conflit des deltas rejetes.

**Usage:**
```
python3 tools/bundle_adjust_weighted.py --cleanup --max-iter 30
  PYTHONPATH=. python3 tools/audit/tension_audit.py [--tol 0.25] [--top 20]
```

### `audit/trace_ray_on_map.py`
Draw a ray on the map from a camera through a marked

**Usage:**
```
python3 tools/trace_ray_on_map.py "Airport (X)" "Bank of America Financial Center"
    python3 tools/trace_ray_on_map.py "Diner (SE) (A)" "Easy Inn Sign" --map yanis
```

## Server Endpoints (tools/server.py)

Total: 39 endpoints

| Endpoint | Note |
|---|---|
| `/api/scene3d` |  |
| `/api/map_data` | Single dump used by the SVG map view at load time. After this, |
| `/api/building_meshes_procedural` |  |
| `/api/building_meshes` | Reads gtamapdata/building_meshes.json and expands edges from |
| `/api/cameras` |  |
| `/api/lm_info` | Returns source cameras + all observers for a landmark. |
| `/api/dependency_graph` | Auto-generated camera dependency graph. |
| `/api/cam_health` | Per-cam health metrics. Reuses compute_projections to get |
| `/api/project` |  |
| `/api/verticals` | return their pixel coords. Frontend overlays these as yellow |
| `/api/optimize` | the UI visualizes and marks; solving lives in the CLI. |
| `/api/render_loss` | Returns JSON with samples {x, y, loss, color, params}. |
| `/api/export_validation` |  |
| `/api/export_map_validation` |  |
| `/api/lm_projections` | markers on this cam's image. |
| `/api/save_lines` |  |
| `/api/get_lines` | roll par _get_roll_from_vlines sur probe roll=0, puis pitch par |
| `/api/solve_lines` | ordre valide (4 poses synthetiques exactes): roll (pure |
| `/api/save` |  |
| `/api/update_landmarks` | = current xyz; optional orange crosshair (x2,y2) = proposed position. |
| `/api/lm_map_crop` | = current xyz; optional orange crosshair (x2,y2) = proposed position. |
| `/api/map_verdict` |  |
| `/api/fit_minimal` | (possibly unsaved) values. Returns the fitted pose WITHOUT |
| `/api/triage` | Reproduces the 2026-07-01 polish workflow: isolated-outlier |
| `/api/exclude_marking` | tools/exclude_marking.py) |
| `/api/quarantine_lm` | remain in pixels.json for future retriangulation) |
| `/api/suspicious` | Find outlier pixels by consensus across cams |
| `/api/set_pixel` | Update pixels.json |
| `/api/set_class` |  |
| `/api/heatmap_data` | Return all landmarks with xyz, error, zone for heatmap |
| `/api/all_landmarks` | Return all landmark names that have xyz |
| `/api/add_pixel` | Create new landmark entry if needed |
| `/api/triangulate` | Find all cams that see this landmark and are calibrated |
| `/api/cam_sources` | For a landmark, return all cams that see it and are calibrated |
| `/api/delete_pixel` | removes this cam fr |
| `/api/validate_pixel` | Just acknowledge — validation state is kept client-side |
| `/api/minimap` | ABSENT — so moving/recalibrating a cam left its minimap centered |
| `/api/other_cams_overlay` |  |
| `/view3d.html` |  |

---

## Calib UI Buttons (calib.html)

Total: 44 buttons

| ID | Title / Description |
|---|---|
| `cam-toggle-btn` | Toggle camera list |
| `(no id)` | Camera view (calibration) |
| `(no id)` | Map view (overview) |
| `(no id)` | 3D view (network in space) |
| `rays-toggle` | Show all rays from the selected cam to its landmarks |
| `heat-toggle` | Show loss landscape for the selected cam (heat map) |
| `dual-toggle` | Compare two cams side-by-side (D) |
| `proj-toggle` | Assist: unmarked LMs projected as ghosts, prioritized by gain |
| `btn-reset` | Reset |
| `btn-save` | Save |
| `btn-export` | ⬇ Export |
| `triage-btn` | Triage: cams categorized with recommended action |
| `(no id)` | LEAK |
| `(no id)` | T1 |
| `(no id)` | T2 |
| `(no id)` | S1 |
| `(no id)` | S2 |
| `oc-toggle-btn` | Toggle other cams overlay (O) |
| `btn-mkadj` | ◐ adjust |
| `mesh-ctrl-btn` | Per-mesh wireframe controls |
| `verts-toggle-btn` | Toggle vertical-lines overlay (V) |
| `pv3-copy-pose` | copy the full pose, ready to paste in a terminal command |
| `lm-map-propose` | propose retriangulation |
| `lm-map-ok` | ✓ map-validated |
| `lm-map-bad` | ✗ map-rejected |
| `lm-map-clear` | clear |
| `btn-add-px` | + Add |
| `(no id)` | All |
| `(no id)` | Indep |
| `(no id)` | Place on Image |
| `(no id)` | Cancel |
| `pxe-validate` | ✓ Validate |
| `pxe-fix-mode` | ✎ Fix Pixel |
| `pxe-delete` | ✕ Delete Pixel |
| `(no id)` | ✕ Close |
| `(no id)` | ✕ |
| `susp-filter-all` | All suspects |
| `susp-filter-leak` | ★ Leak-anchored |
| `(no id)` | close |
| `mk-confirm-ok` | ✓ confirm ⏎ |
| `mk-confirm-rv` | ↩ revert esc |
| `mk-confirm-del` | delete this marking (removes the pixel from pixels.json) |
| `mkadj-reset` | reset all |
| `mkadj-close` | ✕ |

---

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Escape` | closePxEditor |
| `f` | click |
| `F` | click |
| `ArrowLeft` | (see source) |
| `ArrowRight` | preventDefault |
| `ArrowUp` | Save |
| `ArrowDown` | Save |
| `s` | Save |
| `Enter` | Opt |
| `o` | ocUpdateBtn |
| `O` | ocUpdateBtn |
| `m` | updateMinimap |
| `M` | updateMinimap |

---

_Generated by `tools/generate_inventory.py`_
