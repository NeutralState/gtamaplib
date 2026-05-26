# V2 — Constraint Classes

Replaces the V1 model where every "leak cam" was treated as a homogeneous
anchor tier. The audit established that leak cams fall into 6 distinct
classes based on what the in-game HUD actually constrains. V2 makes the
solver, tier system, and dashboard respect those classes.

This document is the reference for the refactor that touches every tool
in the pipeline.

---

## The constraint classes

| Class                    | HUD provides         | DOF locked          | DOF refinable        |
|--------------------------|----------------------|---------------------|----------------------|
| `A_full_hud`             | P, C, Dir, Fov       | xyz, ypr, fov       | (none — anchor)      |
| `B_pos_fov_player`       | P, C, Fov + upright ped | xyz, fov          | ypr (soft roll prior) |
| `C_pos_fov_only`         | P, C, Fov            | xyz, fov            | ypr                  |
| `Cm_pos_only`            | P, C                 | xyz                 | ypr, fov             |
| `D_no_ground_truth`      | (no readable HUD)    | (none)              | xyz, ypr, fov        |
| `X_invalid_ground_truth` | corrupted            | EXCLUDED            | (skip everywhere)    |

Distribution on the 105 audited cams: A=16, B=5, **C=70**, Cm=2, D=12, X=0.

The dominant class is `C_pos_fov_only` (~67%). V1's uniform anchor treatment
masked this — the practical implication is that most leak cams need ypr as a
free variable in the BA, not pinned to a value the solver inherited from
nothing.

---

## Data model

The constraint class lives in two places:

1. **`gtamapdata/leak_cam_audit.json`** — canonical source. One entry per
   audited cam with HUD-derived ground truth values (hud_C_xyz, hud_dir_ypr,
   hud_fov) and notes. This file is the audit reproducibility record.

2. **`gtamapdata/cameras.json`** — adds a `constraint_class` field to each
   cam that has an audit entry. This is what the runtime tools read.
   Duplicated from the audit by `migrate_constraint_classes.py`.

Cams **without** an audit entry have no `constraint_class` field. They are
treated as ordinary user-calibrated cams: all DOF refinable, no ground-truth
locking. This matches today's behavior for non-leak cams.

---

## Per-class behavior in each tool

### `refine_cam_ypr.py` (or successor)

| Class | Behavior                                                            |
|-------|---------------------------------------------------------------------|
| A     | REFUSE. Anchor — there is nothing to refine. Print the audit ypr.   |
| B     | Refine ypr with soft prior `loss += (roll / sigma)^2`, sigma=2 deg. |
| C     | Refine ypr freely (current behavior).                               |
| Cm    | Refine ypr AND fov simultaneously (current scope expansion).        |
| D     | REFUSE here — handled by a full-calibration tool, not this one.     |
| X     | REFUSE.                                                             |
| (none)| REFUSE — this script is for audited cams only.                      |

### `intake_camera.py`

| Class | Behavior                                                              |
|-------|-----------------------------------------------------------------------|
| A     | Already calibrated — skip the intake gate, mark as anchor tier.        |
| B,C,Cm| Run the intake gate against anchor+high LMs as today.                  |
| D     | Treated as a fresh non-leak cam: full xyz/ypr/fov solve, must pass intake. |
| X     | REJECT.                                                                |

### `bundle_adjust_weighted.py`

Per-class DOF locking in the optimization:

| Class | xyz   | ypr             | fov   |
|-------|-------|-----------------|-------|
| A     | LOCKED| LOCKED          | LOCKED|
| B     | LOCKED| free (+roll prior) | LOCKED |
| C     | LOCKED| free            | LOCKED|
| Cm    | LOCKED| free            | free  |
| D     | free  | free            | free  |
| X     | excluded from BA entirely                  |

The "soft barrier" tier budget continues to apply on top of these locks for
the free DOF — class B/C/Cm cams that are also low-tier still get downweighted
relative to high-tier non-leak cams.

### `compute_confidence_tiers.py`

| Class | Tier assignment                                                  |
|-------|------------------------------------------------------------------|
| A     | Anchor (overrides any computed tier).                            |
| B     | Tier computed normally from triangulation residuals.             |
| C     | Tier computed normally.                                          |
| Cm    | Tier computed normally, but capped (fov is unknown — penalize).  |
| D     | Tier computed normally (D acts as a regular cam from here on).   |
| X     | Not considered; excluded from the tier listing.                  |

LMs sourced from class A/B/C/Cm cams are "leak-anchored" (xyz is ground truth),
so the `LEAK_SOURCE_BONUS` in tier weighting applies to them. LMs sourced
only from class D are NOT bonused.

### `build_cam_health.py`

Display the constraint_class for every audited cam as a colored badge in the
dashboard. Suggested palette:

- A: solid green (anchor)
- B: yellow (partial)
- C: yellow-orange (partial)
- Cm: orange (weaker)
- D: grey (no ground truth)
- X: red strike-through (excluded)

---

## Migration sequence

1. **`tools/leak_cam_audit.py`** — helper module. Single source of truth for
   `LOCKED_DOF_BY_CLASS`, `is_excluded()`, `get_class()`. Every other tool
   imports it.

2. **`tools/migrate_constraint_classes.py`** — adds `constraint_class` to
   each entry in `cameras.json`. Dry-run by default. The `--overwrite-a`
   flag also overwrites xyz/ypr/fov of class A cams with HUD ground truth
   (gated behind `dir_convention_verified=True` to protect Intersection (W)
   pending Dir-convention check).

3. **Patch the four runtime tools** to import the helper and respect the
   per-class DOF table:
   - `refine_cam_ypr.py`
   - `intake_camera.py`
   - `bundle_adjust_weighted.py`
   - `compute_confidence_tiers.py`

4. **`build_cam_health.py`** — dashboard color-coding.

After step 2 lands, V1 tools that don't yet know about `constraint_class`
will keep working on cams without the field, but they'll behave incorrectly
on cams that have it (e.g. attempting to refine the ypr of a class A cam).
Step 3 must follow promptly.

---

## Open questions for rlx review

1. **Class B soft-roll prior sigma.** Currently set to 2 deg. Confirm before
   wiring into the BA: a roll of 5 deg costs (5/2)^2 = 6.25 loss units,
   comparable to a ~3 arcmin per-LM contribution. Tune if the BA results
   suggest it.

2. **Cm class capping in tier computation.** Should Cm cams be capped at
   `medium` tier regardless of triangulation residuals, given fov is unknown?
   Or let the residuals speak?

3. **D class participation in BA.** Currently treated as a fresh non-leak
   cam with all DOF free. Alternative: exclude D from BA entirely until it
   has been intaked, to avoid the Ambrosia 01 failure mode (a D cam getting
   misleadingly low loss from a cluster of co-located LMs).

4. **Intersection (W) Dir convention.** The CameraStar overlay reports
   Orientation as P-R-Y (pitch-roll-yaw). The audit stores this as
   `(y, p, r) = (113.951, -7.998, 0.0)`. Need to confirm this mapping
   matches `gtamaplib.Camera.ypr` (the ZXY euler convention used by
   `refine_cam_ypr.py`). Test: project a known LM with the audit ypr through
   `gtamaplib` and compare pixel residual to the marked pixel. If residual
   is small, mapping is correct.
