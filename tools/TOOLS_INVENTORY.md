# gtamaplib — Tools & Features Inventory
Auto-generated. Run `python3 tools/generate_inventory.py` to refresh.
Bookmark this file when you forget what tools exist.

## Quick reference — "Where do I start?"

### Adding a new T3 cam (cold-start workflow)
```
1. Place frame in frames/{Cam Name}.png
2. Run: python3 tools/compute_confidence_tiers.py
   (only once per session — produces tier classifications)
3. Add cam entry to gtamapdata/cameras.json with dummy xyz/ypr/hfov
4. Mark 3+ landmarks in the calib UI (http://localhost:8765)
5. Run: python3 tools/intake_camera.py "Cam Name"
   → see verdict (commit/review/reject) before applying
6. If verdict OK: apply via calib UI Optimize, or refine_camera.py
7. Re-run compute_confidence_tiers.py to update tiers
8. Run bundle_adjust.py for global refinement
```

### Calibration order — "What order to work on?"
```
python3 tools/calibration_order.py --tier unverified
python3 tools/calibration_order.py --cams "Cam A,Cam B"
```

### Outliers detection — "Which pixels are bad?"
```
python3 tools/outliers_report.py
```

---

## CLI Scripts (tools/*.py)

Total: 37 scripts

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

### `calibration_plan.py`
Analyze cams not currently in the dependency tree

**Usage:**
```
python3 tools/calibration_plan.py                       # analyze all
    python3 tools/calibration_plan.py --cam "Amphitheater"  # single cam
    python3 tools/calibration_plan.py --zone vice_city      # filter by zone
    python3 tools/calibration_plan.py --include-leak        # also include leak cams
```

### `compute_confidence_tiers.py`
Classify every cam and landmark into a confidence tier.

### `compute_venetian_xyz.py`
Calcule les xyz des LMs 1000 Venetian Way qui sont

**Usage:**
```
python3 tools/compute_venetian_xyz.py            # dry-run, print propositions
    python3 tools/compute_venetian_xyz.py --apply    # write to landmarks.json
```

### `densify_portofino_edges.py`
densify_portofino_edges.py

### `discover_mesh_candidates.py`
Find LM prefixes that could become procedural

### `extract_mesh_edges.py`
Extract wireframe edges from gtamaplib's procedural Landmark classes

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

### `migrate_constraint_classes.py`
Migration step from V1 (no class info in

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

### `triangulate_lm.py`
Triangulate a single landmark using priority-based source selection.

**Usage:**
```
python3 tools/triangulate_lm.py "1000 Venetian Way (SW)"           # dry-run
    python3 tools/triangulate_lm.py "1000 Venetian Way (SW)" --apply   # write
```

---

## Server Endpoints (tools/server.py)

Total: 26 endpoints

| Endpoint | Note |
|---|---|
| `/api/map_data` | Single dump used by the SVG map view at load time. After this, |
| `/api/building_meshes_procedural` |  |
| `/api/building_meshes` | Reads gtamapdata/building_meshes.json and expands edges from |
| `/api/cameras` |  |
| `/api/lm_info` | Returns source cameras + all observers for a landmark. |
| `/api/dependency_graph` | Auto-generated camera dependency graph. |
| `/api/cam_health` | Per-cam health metrics. Reuses compute_projections to get |
| `/api/project` |  |
| `/api/verticals` | return their pixel coords. Frontend overlays these as yellow |
| `/api/optimize` | LEAK-MODE-V1: optional flag — xyz and hfov frozen, only yaw/pitch/roll optimize |
| `/api/render_loss` | Returns JSON with samples {x, y, loss, color, params}. |
| `/api/lm_projections` | markers on this cam's image. |
| `/api/save` |  |
| `/api/update_landmarks` | Safety: refuse if cam loss is too high. A high-loss cam in a bad |
| `/api/suspicious` | Find outlier pixels by consensus across cams |
| `/api/set_pixel` | Update pixels.json |
| `/api/set_class` |  |
| `/api/heatmap_data` | Return all landmarks with xyz, error, zone for heatmap |
| `/api/all_landmarks` | Return all landmark names that have xyz |
| `/api/add_pixel` | Create new landmark entry if needed |
| `/api/triangulate` | Find all cams that see this landmark and are calibrated |
| `/api/cam_sources` | For a landmark, return all cams that see it and are calibrated |
| `/api/delete_pixel` |  |
| `/api/validate_pixel` | Just acknowledge — validation state is kept client-side |
| `/api/minimap` | Render on demand (fallback for any cam added after startup). |
| `/api/other_cams_overlay` |  |

---

## Calib UI Buttons (calib.html)

Total: 30 buttons

| ID | Title / Description |
|---|---|
| `cam-toggle-btn` | Toggle camera list |
| `(no id)` | Camera view (calibration) |
| `(no id)` | Map view (overview) |
| `rays-toggle` | Show all rays from the selected cam to its landmarks |
| `heat-toggle` | Show loss landscape for the selected cam (heat map) |
| `dual-toggle` | Compare two cams side-by-side (D) |
| `proj-toggle` | Show ghost LM projections on the opposite pane |
| `btn-reset` | Reset |
| `btn-save` | Save |
| `btn-update` | Update LMs |
| `btn-suspicious` | ⚠ Suspicious |
| `(no id)` | LEAK |
| `(no id)` | T1 |
| `(no id)` | T2 |
| `(no id)` | SS |
| `oc-toggle-btn` | Toggle other cams overlay (O) |
| `verts-toggle-btn` | Toggle vertical-lines overlay (V) |
| `btn-opt` | ⚡ Optimize |
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
