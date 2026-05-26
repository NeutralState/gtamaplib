# gtamaplib solver — Design Document

**Status:** Draft v1
**Author:** Alexandre + Claude
**Date:** 2026-05-23

---

## 0. Purpose

This document describes the architecture and algorithm of a clean replacement
for the current ad-hoc calibration system in `gtamaplib`. The current system
mixes observations, measurements, and inferences in the same files, which
allows downstream operations to silently corrupt upstream ground truth.

The new system enforces a strict separation:

- **Observations** are immutable human inputs (pixels marked on images).
- **Measurements** are immutable external facts (leak cam positions from
  the GTA console, sea-level constraints, known building geometry).
- **Inferences** are the output of a single solver that consumes only
  observations + measurements and produces the world state.

The solver is **pure**: same input → same output, no global mutable state,
no half-baked intermediate writes. The UI is reduced to its proper role:
an editor for observations and a viewer for inferences. It cannot directly
modify inferences; it can only modify observations and trigger a re-solve.

---

## 1. Top-level architecture

### 1.1 Repository layout

The new code lives alongside the legacy code in the existing
`gtamaplib` repo. Old code stays untouched during development. Once
the new system is validated end-to-end, the legacy code moves to a
`legacy/` subfolder.

```
gtamaplib/
├── observations/
│   └── pixels.json             # IMMUTABLE: humans only
│
├── measurements/
│   ├── leak_cams.json          # IMMUTABLE: GTA console
│   ├── z_constraints.json      # IMMUTABLE: human knowledge
│   ├── procedural_lms.json     # IMMUTABLE: human knowledge
│   └── geometry_priors.json    # IMMUTABLE: human knowledge
│
├── inferences/
│   ├── state.json              # OUTPUT: solver writes only
│   ├── convergence_report.json # OUTPUT: solver writes only
│   └── provenance.json         # OUTPUT: solver writes only
│
├── solver/
│   ├── __init__.py
│   ├── __main__.py             # CLI entry point
│   ├── io.py                   # load/save with validation
│   ├── geometry.py             # pure math: projection, rays, etc.
│   ├── triangulate.py          # multi-cam triangulation
│   ├── calibrate.py            # cam ypr / xyz / fov optimization
│   ├── procedural.py           # procedural LM generators
│   ├── bootstrap.py            # initial ypr from sea-level + cross-cam
│   └── solve.py                # main iteration loop
│
├── ui/
│   └── (new minimal UI - editor for observations only)
│
├── legacy/
│   └── (old code, archived after cutover)
│
└── tests/
    ├── unit/
    ├── integration/
    └── regression/             # compares solver output to legacy
```

### 1.2 Data flow

```
observations/ + measurements/
            │
            ▼
       solver/solve.py
            │
            ▼
   inferences/state.json
            │
            ▼
       ui (read-only view)
            │
            │  (human edits pixels.json)
            │
            ▼
      observations/ updated
            │
            ▼
   click "Solve" → re-run solver
            │
            ▼
   inferences/ updated
```

The cycle is:
1. Human edits an observation (adds, moves, or deletes a pixel marker).
2. State becomes "stale".
3. Human clicks Solve.
4. Solver reads all observations + measurements, produces fresh state.
5. UI reloads.

There is no other way for state to change.

---

## 2. The three concept categories

### 2.1 Observations

**Definition:** facts produced by a human looking at an image.

**File:** `observations/pixels.json`

**Format:**
```json
{
  "Venetian Islands": {
    "1000 Venetian Way (SE)": {
      "pixel": [2123, 456],
      "confidence": 1.0,
      "marked_at": "2026-05-23T14:32:01Z"
    },
    "1000 Venetian Way (SW)": {
      "pixel": [2050, 458],
      "confidence": 0.7,
      "marked_at": "2026-05-23T14:33:15Z",
      "note": "blurry, approximate"
    }
  },
  "Vice City Postcard": {
    "1000 Venetian Way (SE)": {
      "pixel": [304, 828],
      "confidence": 1.0,
      "marked_at": "2026-05-22T09:15:00Z"
    }
  }
}
```

Fields:
- `pixel`: [x, y] in image coordinates. Required.
- `confidence`: 0.0 to 1.0. Default 1.0. Used to weight the residual in
  the solver. Lower confidence = lower weight.
- `marked_at`: ISO 8601 timestamp. Optional, used for audit.
- `note`: free-text. Optional.

**Mutability:** humans only, via the UI or by directly editing the file.
The solver MUST NOT write to this file. Git tracks every change.

### 2.2 Measurements

**Definition:** facts that come from outside the human pixel-marking process.
These are external truths: GTA console output, known geometry of objects in
the real world, sea level, etc.

There are four measurement files, each capturing a distinct kind of truth.

#### 2.2.1 `measurements/leak_cams.json`

The leak cameras: cameras whose xyz and fov are known from the GTA debug
console (the strings visible in leaked videos showing camera position +
parameters).

```json
{
  "Tennis Court (SE)": {
    "xyz": [-317.232, 1174.859, 5.021],
    "fov": 59.86,
    "source": "2022-09-01 14-37-21 [?]",
    "image_size": [1824, 1080],
    "image_path": "screenshots/tennis_court_se.png"
  },
  "Vice Beach (A)": {
    "xyz": [2352.147, 1104.727, 49.654],
    "fov": 50.0,
    "source": "Trailer 1 [415]",
    "image_size": [1920, 1080],
    "image_path": "screenshots/vice_beach_a.png"
  }
}
```

Fields:
- `xyz`: position in GTA world coordinates. From the console.
- `fov`: horizontal field of view in degrees. From the console.
- `source`: human-readable description of where this came from.
- `image_size`: [width, height] of the underlying image in pixels.
- `image_path`: relative path to the image file used for marking pixels.

**Mutability:** humans only, when a new leak source becomes available.

#### 2.2.2 `measurements/z_constraints.json`

LMs whose z is known from external information (sea level, lake level,
floor counting on a building of known story height, etc.).

```json
{
  "Sea Level (Vice Beach)": {
    "z": 0.0,
    "reason": "ocean surface"
  },
  "1000 Venetian Way (W1)": {
    "z": 8.86,
    "reason": "3 stories above ground, 2.954 m/floor (22 floors, 65m total)"
  },
  "1000 Venetian Way (W4)": {
    "z": 44.31,
    "reason": "15 stories above ground"
  }
}
```

Fields:
- `z`: known z coordinate.
- `reason`: human-readable explanation.

**Mutability:** humans only.

#### 2.2.3 `measurements/procedural_lms.json`

LMs whose xyz is a deterministic function of other LMs + a generator rule
(building geometry, symmetry constraint, etc.).

```json
{
  "Portofino Tower (B-frontL-NW)": {
    "generator": "portofino.sub_corner",
    "params": {"face": "B-frontL", "side": "NW"},
    "depends_on": [
      "Portofino Tower (NW)",
      "Portofino Tower (NE)",
      "Portofino Tower (S)"
    ]
  }
}
```

Fields:
- `generator`: dotted reference to a Python function in `solver/procedural.py`
  or one of its submodules. Resolved at solve time.
- `params`: keyword arguments passed to the generator.
- `depends_on`: list of LM names this procedural LM depends on. The solver
  uses this to detect dependency cycles and to order computation.

**Mutability:** humans only. Adding a procedural LM is a code change
(new generator function) + a data change (new entry here).

#### 2.2.4 `measurements/geometry_priors.json`

Additional geometric constraints between LMs that the solver should respect
during optimization. Examples: "these two LMs are 47.2m apart" or
"these three LMs are colinear".

```json
{
  "distance:portofino_NW_NE": {
    "type": "distance",
    "lms": ["Portofino Tower (NW)", "Portofino Tower (NE)"],
    "value": 23.4,
    "weight": 0.5
  },
  "vertical:1000_venetian_SE_to_SE_palier": {
    "type": "vertical",
    "lms": ["1000 Venetian Way (SE)", "1000 Venetian Way (B-SE)"],
    "weight": 1.0
  }
}
```

Constraint types (extensible):
- `distance`: two LMs must be exactly `value` meters apart.
- `vertical`: two LMs must have the same x and y, only z differs.
- `colinear`: three+ LMs must be on a line.
- `coplanar`: four+ LMs must be on a plane.

`weight` controls how strongly the constraint pulls vs the pixel residuals.

**Mutability:** humans only.

### 2.3 Inferences

**Definition:** everything the solver computes.

There are three inference files. All are output-only from the solver's
perspective; nothing else writes to them.

#### 2.3.1 `inferences/state.json`

The single source of truth for the current solved world. Format:

```json
{
  "solver_version": "1.0.0",
  "solved_at": "2026-05-23T16:42:01Z",
  "input_hash": "sha256:abc123...",

  "cameras": {
    "Tennis Court (SE)": {
      "kind": "leak",
      "xyz": [-317.232, 1174.859, 5.021],
      "ypr": [258.59, -9.92, 0.01],
      "fov": 59.86,
      "loss_arcmin": 1.42,
      "n_constraints": 4
    },
    "Venetian Islands": {
      "kind": "non_leak",
      "xyz": [-33.89, 1097.15, 66.81],
      "ypr": [286.30, -12.96, -0.08],
      "fov": 50.0,
      "loss_arcmin": 2.03,
      "n_constraints": 14
    }
  },

  "landmarks": {
    "1000 Venetian Way (SE)": {
      "kind": "pixel_anchored",
      "xyz": [354.83, 1124.60, 65.35],
      "error_m": 0.31,
      "n_observers": 5
    },
    "Portofino Tower (B-frontL-NW)": {
      "kind": "procedural",
      "xyz": [1703.73, -211.37, 0.0],
      "computed_from": "portofino.sub_corner"
    }
  },

  "global_metrics": {
    "rms_loss_arcmin": 1.57,
    "median_loss_arcmin": 0.46,
    "p99_loss_arcmin": 8.74,
    "total_observations": 1055,
    "outlier_count_above_20_arcmin": 2
  }
}
```

Fields per camera:
- `kind`: `"leak"` or `"non_leak"`.
- `xyz`: position (locked for leak cams).
- `ypr`: yaw/pitch/roll (always solved).
- `fov`: field of view (locked for leak cams, solved for non-leak).
- `loss_arcmin`: this cam's RMS projection residual in arcminutes.
- `n_constraints`: how many LMs contributed to its calibration.

Fields per landmark:
- `kind`: `"pixel_anchored"` or `"procedural"`.
- `xyz`: position.
- `error_m`: max ray-to-point distance in meters (pixel-anchored only).
- `n_observers`: how many cams contributed (pixel-anchored only).
- `computed_from`: generator name (procedural only).

#### 2.3.2 `inferences/convergence_report.json`

A diagnostic report of how the solver got to the current state.

```json
{
  "iterations": 12,
  "converged": true,
  "convergence_criterion": "max_param_change < 0.001",

  "per_iteration": [
    {
      "iter": 0,
      "phase": "bootstrap",
      "loss_arcmin": 89.4,
      "max_param_change": null
    },
    {
      "iter": 1,
      "phase": "main",
      "loss_arcmin": 12.3,
      "max_param_change": 4.2
    }
  ],

  "warnings": [
    "Cam 'Yacht (2)' has only 1 LM observation, ypr underdetermined."
  ],

  "errors": []
}
```

#### 2.3.3 `inferences/provenance.json`

For each output value, which inputs produced it. Used for debugging:
"why is this LM at this position?"

```json
{
  "landmarks": {
    "1000 Venetian Way (SE)": {
      "observed_by": [
        {"cam": "Venetian Islands", "pixel": [2123, 456], "weight": 1.0},
        {"cam": "Vice City Postcard", "pixel": [304, 828], "weight": 1.0}
      ],
      "constraints_applied": []
    }
  },
  "cameras": {
    "Venetian Islands": {
      "calibrated_against": [
        "1000 Venetian Way (SE)",
        "1000 Venetian Way (SW)",
        "Portofino Tower (NW)"
      ]
    }
  }
}
```

---

## 3. The solver: high-level overview

The solver is a single Python module invoked as:

```
python -m solver solve [--input-dir .] [--output-dir .] [--verbose]
```

It does the following, in order:

1. **Load**: read all observations + measurements. Validate.
2. **Hash input**: compute a hash of all input data. If the hash matches
   the one in current state.json, exit early (nothing to do).
3. **Bootstrap**: produce an initial guess for all unknowns (ypr of leak cams,
   xyz/ypr/fov of non-leak cams, xyz of all pixel-anchored LMs).
4. **Iterate**: alternate between calibrating cameras and triangulating LMs
   until convergence.
5. **Compute procedural LMs**: once pixel-anchored LMs have converged,
   compute procedural LMs in dependency order.
6. **Apply geometry priors**: optional final refinement that respects
   distance/coplanar/colinear constraints.
7. **Compute metrics**: per-cam loss, per-LM error, global stats.
8. **Write**: dump state.json, convergence_report.json, provenance.json.

The iteration in step 4 is the heart of the algorithm. It's described
in detail in section 5.

---

## 4. Coordinate system and projection model

To keep the solver readable, all projection math is centralized in
`solver/geometry.py`. This section documents the conventions so nothing
is ambiguous.

### 4.1 World coordinates

Right-handed, z-up. GTA convention:
- +x = east
- +y = north
- +z = up
- z = 0 at sea level (approximately)

All xyz in any file are in this system, in meters.

### 4.2 Camera convention

A camera has:
- position `xyz`
- orientation `ypr = (yaw, pitch, roll)` in degrees
  - yaw: rotation around z. 0 = looking +x. 90 = looking +y.
  - pitch: rotation around camera's local right axis. positive = looking up.
  - roll: rotation around camera's local forward axis.
- horizontal FOV `fov` in degrees
- `image_size = (width, height)` in pixels

The vertical FOV is derived from `fov`, `width`, and `height` (square pixels):
`vfov = 2 * atan(tan(fov/2) * height / width)`.

### 4.3 Pixel convention

Pixel (0, 0) is top-left. +x = right, +y = down. Standard image convention.

### 4.4 Projection function

`project(world_xyz, cam) → (pixel_x, pixel_y) or None`

Returns None if the point is behind the camera.

Implementation lives in `solver/geometry.py` and is the only place this
math exists. Everything else (triangulation, calibration) calls this.

### 4.5 Ray function

`ray_from_pixel(pixel, cam) → (origin_xyz, direction_unit)`

Inverse of project: given a pixel, return the ray that emanates from the
camera and would project to that pixel. Used for triangulation.

---

(End of part 1. Sections 5-8 cover the solver algorithm in detail,
convergence strategy, error handling, and validation. Continue in part 2.)

---

## 5. The solver algorithm

This section describes the main solving loop in detail. The goal is to
go from raw observations + measurements to a fully solved state, without
any human intervention and without depending on any prior solver output.

### 5.1 Big-picture loop

```
load_inputs()
bootstrap()
iterate until convergence:
    refine_leak_cams()        # ypr only; xyz and fov are locked
    refine_non_leak_cams()    # xyz + ypr + fov
    refine_landmarks()        # multi-cam triangulation
    check_convergence()
compute_procedural_landmarks()
apply_geometry_priors()       # optional final refinement
compute_metrics()
write_outputs()
```

Each step is implemented as a pure function: it takes the current state
as input, returns a new state. No in-place mutation, no global variables.
This makes the system easy to test and reason about.

### 5.2 Bootstrap (the hard problem)

Bootstrapping is the chicken-and-egg problem: we cannot calibrate any
camera's ypr without LMs of known xyz, and we cannot triangulate any
LM without calibrated cameras. The bootstrap phase breaks this loop using
two complementary techniques.

#### 5.2.1 Step A: horizon-based pitch and roll for leak cameras

For each leak camera whose image contains visible water (ocean or lake),
the horizon line is at z = 0 in world coordinates.

The horizon's apparent position in the image gives us two constraints:

- The vertical position of the horizon in the image determines pitch.
- The slope of the horizon line determines roll.

This requires a single marked pixel pair on the horizon, or even a
horizon-line annotation, to extract pitch ≈ atan((height/2 - horizon_y) /
focal_length_px) and roll = the line's tilt angle.

To formalize: we add a new observation type for horizons in
`observations/horizons.json` (or extended pixels.json):

```json
{
  "Vice Beach (A)": {
    "horizon": {
      "left_pixel": [10, 412],
      "right_pixel": [1910, 408],
      "confidence": 0.9
    }
  }
}
```

Not every leak cam has a usable horizon (interior shots, urban shots
without sky). For those, step B is the only option.

#### 5.2.2 Step B: simultaneous multi-leak triangulation

For leak cameras without horizon, we use the joint constraint that
multiple leak cameras observing the same LM must produce consistent rays.

The math:

- Unknowns: ypr_i for each of N leak cams. 3N parameters.
- Unknowns: xyz_j for each of M shared LMs. 3M parameters.
- Knowns: xyz_i, fov_i for each cam (from leak data).
- Observations: pixel_{i,j} for each (cam i, LM j) pair where it was marked.

The objective:

```
loss = sum over (i, j) of:
    || project(xyz_j, cam_i with ypr_i) - pixel_{i,j} ||^2
```

This is a nonlinear least-squares problem. For convergence, we need a
reasonable initial guess. We use:

- **Initial ypr from step A** where horizons are available.
- **Initial ypr from cardinal hints**: a `bootstrap_hints.json` file
  containing rough estimates for the remaining cams. Example:
  ```json
  {
    "Tennis Court (SE)": {"yaw": 260, "pitch": -10, "roll": 0,
                          "confidence": 0.3,
                          "reason": "looking SW from tennis court visible in trailer"}
  }
  ```
  Confidence is a soft weight: the bootstrap solver respects the hint
  with weight equal to confidence^2.
- **Initial xyz_j**: rough triangulation from the first pair of leak cams
  that both see LM j, using the initial ypr.

We then run Levenberg-Marquardt optimization on the joint system. This
typically converges in 50-200 iterations.

#### 5.2.3 Step C: non-leak cam initial guess

Once leak cams have rough ypr and shared LMs have rough xyz, every
non-leak cam that sees at least 4 LMs gets initial xyz + ypr + fov by
running a single P4P (or PnP) solve.

If a non-leak cam sees fewer than 4 LMs, it's marked as "underdetermined"
and will be resolved later in the main loop once more LMs become available.

### 5.3 Main iteration

After bootstrap, we have rough values for everything. The main loop
refines them.

#### 5.3.1 Refining leak cams

For each leak cam (locked xyz, locked fov), solve:

```
ypr* = argmin sum over LMs visible to this cam of:
       confidence^2 * || project(xyz_LM, cam) - pixel ||^2
```

This is 3 parameters, well-posed when at least 4 LMs are visible (8 equations).

Important: the LMs used here are the **current best estimate** of their
xyz. They were themselves derived from possibly imperfect cam orientations.
That's why we iterate.

#### 5.3.2 Refining non-leak cams

Same as leak cams, but with 7 parameters (xyz, ypr, fov) instead of 3.
Well-posed when at least 4 LMs are visible.

#### 5.3.3 Refining landmarks

For each pixel-anchored LM, collect every cam that observed it. Then
solve:

```
xyz_LM* = argmin sum over observing cams of:
          confidence^2 * angular_residual(ray_from_pixel, xyz_LM)^2
```

where `angular_residual` is the angle between the cam's ray (built from
the marked pixel and current cam orientation) and the line from the cam
to the candidate xyz_LM.

This is 3 parameters per LM, well-posed when at least 2 cams see it
**and** the cams are not co-located.

If the LM has a z constraint from measurements/z_constraints.json,
we constrain `xyz_LM[2] = z_constraint` and solve only for x, y.

If an LM has only one observer, it can't be solved at all; it's marked
as "unsolved" in state.json with xyz = null.

### 5.4 Convergence

The loop terminates when, between two consecutive iterations:

- No cam's ypr changes by more than ε_ypr (default: 0.001 degrees).
- No cam's xyz changes by more than ε_xyz (default: 0.001 meters).
- No cam's fov changes by more than ε_fov (default: 0.001 degrees).
- No LM's xyz changes by more than ε_lm (default: 0.001 meters).

If after 100 iterations none of these are satisfied, the solver reports
non-convergence in convergence_report.json but still writes the best
state it found. The user can inspect the report to diagnose
(usually: a cam with bad observations, or contradictory constraints).

### 5.5 Procedural LM computation

After the main loop converges, procedural LMs are computed in dependency
order (topological sort of the dependency graph).

For each procedural LM:

1. Load its parents from state.json (which now have solved xyz).
2. Call its generator function with the parents and the params.
3. Write the result to state.json with kind="procedural".

If a procedural LM's dependencies are not all solved, it's skipped and
logged as a warning.

Procedural LMs never participate in the main optimization loop. They
follow their parents passively. This is by design: it prevents bundle
adjustment from drifting them away from the formula they're supposed
to follow.

### 5.6 Geometry priors

After procedural LMs are computed, an optional final pass applies the
constraints in geometry_priors.json. This is a small additional
optimization that nudges LM positions to better satisfy distance,
coplanar, etc. constraints — without breaking pixel residuals
significantly (controlled by the constraint weights).

This pass is skipped if no priors are defined.

### 5.7 Metrics

Final pass computes:

- Per-cam: RMS loss in arcminutes, number of constraints.
- Per-LM: max ray-to-point distance in meters, number of observers.
- Global: RMS, median, p99 of all observations; outlier count above
  20 arcmin.

These are written to state.json and to convergence_report.json.

---

## 6. Detailed bootstrap algorithm

This section spells out the bootstrap so an implementer can write it
without further interpretation.

### 6.1 Input requirements for bootstrap

The bootstrap phase requires at least:

- 2+ leak cams.
- At least 3 LMs visible to 2+ leak cams each (the "anchor set").
- For each leak cam: either a horizon annotation, or a bootstrap_hints
  entry with ypr ± confidence.

If these are not met, the solver fails fast with a clear error message
asking the user to provide more bootstrap data.

### 6.2 Algorithm

```
def bootstrap(observations, measurements):
    # Step 1: get initial ypr for every leak cam
    leak_cams = measurements.leak_cams
    initial_ypr = {}
    for cam_name, cam_data in leak_cams.items():
        if horizon_available(cam_name, observations):
            initial_ypr[cam_name] = ypr_from_horizon(cam_name, observations, cam_data)
        elif hint_available(cam_name, measurements):
            initial_ypr[cam_name] = ypr_from_hint(cam_name, measurements)
        else:
            raise BootstrapError(
                f"No horizon or hint for {cam_name}. "
                f"Add one to observations/horizons.json or measurements/bootstrap_hints.json."
            )

    # Step 2: identify the anchor LM set
    anchor_lms = find_lms_visible_to_multiple_leak_cams(observations, leak_cams)
    if len(anchor_lms) < 3:
        raise BootstrapError(
            f"Found only {len(anchor_lms)} anchor LMs. Need at least 3."
        )

    # Step 3: rough initial xyz for each anchor LM
    initial_lm_xyz = {}
    for lm_name in anchor_lms:
        observers = [c for c in leak_cams if c sees lm_name]
        cam_a, cam_b = observers[0], observers[1]
        xyz = triangulate_pair(cam_a, cam_b, initial_ypr, lm_name, observations)
        initial_lm_xyz[lm_name] = xyz

    # Step 4: joint refinement
    # Parameters: [ypr_cam1, ypr_cam2, ..., xyz_lm1, xyz_lm2, ...]
    # Objective: sum of squared pixel residuals over all (cam, lm) observations
    # in the anchor set.
    params_initial = pack(initial_ypr, initial_lm_xyz)
    result = scipy.optimize.least_squares(
        residual_function,
        params_initial,
        method='lm',  # Levenberg-Marquardt
        max_nfev=500,
    )
    ypr_refined, lm_xyz_refined = unpack(result.x)

    # Step 5: apply z_constraints
    for lm_name, xyz in lm_xyz_refined.items():
        if lm_name in measurements.z_constraints:
            xyz[2] = measurements.z_constraints[lm_name]['z']

    return State(
        cam_ypr=ypr_refined,
        lm_xyz=lm_xyz_refined,
        non_leak_cams={},  # filled in step 6
    )
```

### 6.3 Non-leak cam initial guess (step 6 of bootstrap)

```
def initial_guess_non_leak_cams(state, observations, measurements):
    all_cam_names_in_pixels = set(observations.pixels.keys())
    leak_cam_names = set(measurements.leak_cams.keys())
    non_leak_cam_names = all_cam_names_in_pixels - leak_cam_names

    for cam_name in non_leak_cam_names:
        observed_lms = observations.pixels[cam_name]
        solved_lms = [name for name in observed_lms if name in state.lm_xyz]

        if len(solved_lms) < 4:
            mark_unresolved(cam_name)
            continue

        # PnP solve for xyz + ypr + fov
        cam_initial = pnp_solve(
            xyz_points=[state.lm_xyz[n] for n in solved_lms],
            pixel_points=[observed_lms[n]['pixel'] for n in solved_lms],
            image_size=infer_image_size(cam_name),
        )
        state.non_leak_cams[cam_name] = cam_initial

    return state
```

If `infer_image_size` cannot determine the image size for a non-leak cam,
that cam is skipped with a warning. (The image size needs to be
discoverable: from the image file itself, or from a `measurements/non_leak_cam_meta.json`
file that lists known image sizes.)

### 6.4 Failure modes during bootstrap

The bootstrap can fail in several specific ways. Each has a clear
diagnostic:

- **Insufficient anchor LMs**: fewer than 3 LMs visible to 2+ leak cams.
  Fix: add more pixel markings on shared LMs.
- **All anchor LMs colinear**: the LMs are roughly on a line, making
  triangulation ill-conditioned. Fix: add a LM far from the line.
- **All anchor LMs at similar z**: triangulation works, but later steps
  may be ill-conditioned. Warning only.
- **Levenberg-Marquardt didn't converge**: bootstrap_hints were too far
  off. Fix: improve the hints.

All of these produce specific error messages or warnings in
convergence_report.json.

---

## 7. Error handling and edge cases

### 7.1 Stale state detection

Every time the solver runs, it computes a hash of all input files
(observations + measurements). This hash is stored in state.json.

If a subsequent solve call finds the same hash, it exits early with
"already solved, no changes". The UI can use this to display "state is
fresh" vs "state is stale" without re-running the full solver.

### 7.2 Partial solves

If the solver is interrupted (Ctrl+C, crash), state.json is left
untouched: the solver only writes outputs at the very end, after all
computation is done. No half-baked partial states ever land on disk.

This is achieved with a temp-and-rename pattern: write to
`state.json.tmp`, then `os.rename` to `state.json`. POSIX guarantees
atomicity of the rename within a single filesystem.

### 7.3 Inconsistent observations

If two cameras observe the same LM and the ray triangulation has a
residual above a configurable threshold (default: 5 meters), the LM
is flagged as "suspicious" in state.json. The UI surfaces these so
the human can re-check the pixel markings.

This is detection, not auto-correction. The solver never deletes or
modifies observations; that's the human's job.

### 7.4 Conflicting constraints

If a z_constraint and the triangulated z disagree by more than a
configurable threshold (default: 2 meters), it's a warning, not an
error. The z_constraint wins (it's a measurement), but the discrepancy
is logged.

If a geometry_prior is impossible to satisfy without breaking pixel
residuals badly (raises pixel loss by more than 50%), it's logged as
overcontraining and skipped for that solve. The user can lower its
weight.

### 7.5 Cameras with no observations

If a camera is defined in measurements/leak_cams.json but has zero
pixel observations, its ypr is undetermined. The solver leaves its
ypr null in state.json and logs a warning.

### 7.6 Landmarks with no observations

If a landmark appears in measurements (e.g., as a procedural LM
dependency or in a geometry prior) but has zero pixel observations
and is not procedural, its xyz is null in state.json and a warning
is logged.

---

## 8. Validation strategy

To prove the new system is correct, we run several validation passes
during development.

### 8.1 Regression test against legacy

We migrate the current repo data into the new format (see section 9).
Then we run the new solver and compare its state.json output against
the legacy cameras.json + landmarks.json.

Acceptance criterion: for every LM and cam that exists in both, the
difference must be within a tight tolerance:

- Cam xyz: within 1 meter for leak cams (should be 0 since locked),
  within 5 meters for non-leak cams.
- Cam ypr: within 0.1 degrees.
- Cam fov: within 0.5 degrees.
- LM xyz: within 1 meter for high-confidence LMs, within 3 meters for
  others.

Larger discrepancies are investigated case by case: usually they
reveal a bug in the legacy system that the new solver correctly fixes.

### 8.2 Self-consistency test

Take the solved state, generate synthetic observations from it (project
every LM onto every cam that saw it), then run the solver on the
synthetic observations. The output should match the original state
to numerical precision.

This proves the solver is fixed-point: it correctly resolves any
self-consistent input.

### 8.3 Perturbation robustness

Take the solved state, add Gaussian noise (1-2 pixels stddev) to all
observations, then re-solve. The output should differ from ground
truth by an amount proportional to the noise, but never catastrophically.

### 8.4 Observation deletion robustness

Take the solved state, remove 10% of pixel observations at random,
re-solve. Most LMs should remain within 1m of ground truth. LMs that
had only 2 observers and lost one will become unresolved; that's
expected.

### 8.5 Bootstrap from scratch test

Wipe inferences/ entirely. Run solve from observations + measurements
only. Compare to the previous state. Differences should be within the
same tolerances as the regression test.

This is the most important test: it proves the solver doesn't need
any prior state to converge to the right answer.


---

## 9. Migration from legacy

The migration is a one-shot script that runs once: `solver/migrate_legacy.py`.

### 9.1 What it does

It reads the legacy `gtamapdata/landmarks.json`, `gtamapdata/cameras.json`,
and `gtamapdata/pixels.json`, and produces the new directory structure:

```
observations/
  pixels.json              # straight copy + normalize to new format
  horizons.json            # empty initially; humans add later

measurements/
  leak_cams.json           # extracted from cameras.json where source matches leak pattern
  z_constraints.json       # extracted from landmarks_meta z_constraint field
  procedural_lms.json      # generated from known procedural classes
  geometry_priors.json     # empty initially
  bootstrap_hints.json     # extracted from current cam ypr (as initial guess)
  non_leak_cam_meta.json   # image sizes etc for non-leak cams
```

### 9.2 Classification rules

A camera is a leak cam if its `source` field matches any of:
- `"Trailer 1 [...]"`
- `"Trailer 2 [...]"`
- `"2022-09-01 ..."`, `"2024-..."`, etc. (timestamps from leaked videos)
- explicit `"leak"` flag (if present)

All others are non-leak. The current cameras.json doesn't have a strict
boolean for this, so the classification is done by pattern match on
`source`, with the result reviewed by hand once.

A landmark is procedural if its name matches a known procedural class:
- Anything matching `^Portofino Tower \(B-.*-NW\)$` → procedural
- Anything matching `^Portofino Tower \(L-.*-NW\)$` → procedural
- Anything matching `^Four Seasons Hotel Miami \(.*sub.*\)$` (if any) → procedural
- The rest of 1000 Venetian etc → pixel_anchored

For the very first migration, we list the procedural patterns explicitly
in a constant in `migrate_legacy.py`. After migration, this knowledge
lives in `measurements/procedural_lms.json` as proper data.

### 9.3 Bootstrap hints from legacy

The legacy cameras.json has ypr values for all cams. These were
solved over many iterations by previous tools. We don't trust them as
ground truth, but they're a good initial guess.

We copy these into `measurements/bootstrap_hints.json` with
`confidence: 0.5` (medium-confidence hint). The solver will use them
as starting points and refine.

### 9.4 Z-constraints from legacy

The legacy code has a step that imports z_constraints for sea-level
landmarks (commit `033df0f`). The migration reads `landmarks_meta`
and extracts every LM with a `z_constraint` field, writing it to
`measurements/z_constraints.json`.

### 9.5 Procedural LMs from legacy classes

The migration script imports the existing classes (Portofino, Four
Seasons, OneThousandVenetian, etc.) and asks each one to enumerate
its procedural sub-LMs and dependencies.

For this to work cleanly, each procedural class gets a small new
method `enumerate_procedural_lms() → list[dict]`:

```python
class Portofino:
    def enumerate_procedural_lms(self):
        return [
            {
                "name": "Portofino Tower (B-frontL-NW)",
                "generator": "portofino.sub_corner",
                "params": {"face": "B-frontL", "side": "NW"},
                "depends_on": ["Portofino Tower (NW)",
                               "Portofino Tower (NE)",
                               "Portofino Tower (S)"],
            },
            # ... ~115 entries
        ]
```

This is a small addition to each class. The legacy compute code stays
intact; we're just exposing the dependency graph.

### 9.6 Migration validation

After migration, the script runs:

1. The new solver on the migrated data.
2. Compares its output to the legacy state.
3. Reports any discrepancies above the tolerances in section 8.1.

If discrepancies are small, migration is successful. If large, we
investigate (usually a misclassification of a cam or a procedural LM).

The script is idempotent: running it twice produces the same result.
It refuses to overwrite existing observations/ or measurements/ unless
`--force` is passed.

---

## 10. The new UI

The legacy UI mixes three things badly: an observation editor, a state
viewer, and a solver controller. The new UI separates them cleanly.

### 10.1 Principles

1. **No buttons that can corrupt data silently.** The only way to change
   the world state is to edit observations or measurements.
2. **No state mutation in the UI.** The UI is a renderer of files.
3. **One verb: Solve.** Everything that re-computes state is triggered
   by this one button.
4. **Fast feedback loop.** Marking a pixel takes 1 click, solving takes
   ~10-30s, viewing the result takes 0 clicks.

### 10.2 Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ [Cam: Tennis Court (SE) ▼]      State: fresh ●     [Solve]      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌────────────────────────────────────────┐                     │
│   │                                        │                     │
│   │     Camera image with markers          │                     │
│   │                                        │                     │
│   │     [+] Add marker mode                │                     │
│   │     [⛬] Add horizon                    │                     │
│   │                                        │                     │
│   └────────────────────────────────────────┘                     │
│                                                                  │
│   LMs visible in this cam:                                       │
│   ─────────────────────────────────────────────                  │
│   ● 1000 Venetian Way (SE)   marked:(304,828)  err: 1.4 px       │
│   ● 1000 Venetian Way (SW)   marked:(443,831)  err: 2.1 px       │
│   ○ 1000 Venetian Way (NE)   not marked yet                      │
│   ...                                                            │
│                                                                  │
│   Last solve: 2026-05-23T16:42:01Z (12 iterations, converged)    │
└──────────────────────────────────────────────────────────────────┘
```

State indicator:
- `fresh ●` (green): state.json matches the current hash of inputs.
- `stale ●` (yellow): inputs changed since last solve.
- `solving ●` (blue, pulsing): solver is running.
- `error ●` (red): last solve failed; click for details.

### 10.3 Interactions

**Add marker**: click `[+]`, then click on the image, then pick the LM
from a dropdown (or type a new name → creates a new LM). The new pixel
is written to `observations/pixels.json` immediately. State becomes stale.

**Move marker**: drag an existing marker on the image. New pixel
position is written immediately. State becomes stale.

**Delete marker**: right-click a marker → Delete. Marker is removed
from `observations/pixels.json`. State becomes stale.

**Add horizon**: click `[⛬]`, draw a line on the image. The line's
endpoints become the horizon annotation in `observations/horizons.json`.

**Solve**: click `[Solve]`. The UI invokes `python -m solver solve` as
a subprocess. Output streams are tailed in a side panel for live progress
(iteration count, current loss). When done, the UI reloads state.json
and refreshes the display.

**Switch cam**: pick from the dropdown. The UI loads the relevant image
and renders all markers from observations/pixels.json for that cam,
plus projected positions for LMs that exist in state.json.

### 10.4 What the UI does NOT do

- No "Optimize this cam" button.
- No "Update LMs from this cam" button.
- No "Triangulate this LM" button.
- No sliders to manually adjust xyz/ypr/fov.
- No "Save" button (observations are saved on every edit; state is
  saved by the solver).
- No "Reset" button (use git to revert).

If the user wants any of those behaviors, the answer is the same: edit
observations and click Solve.

### 10.5 Tech stack

For consistency with the existing project, the UI is HTML/CSS/JS
served by a small Python HTTP server (much smaller than the legacy
server.py — perhaps 200 lines):

```
ui/
  server.py         # static file serving + /api/solve endpoint
  static/
    index.html
    app.js
    style.css
```

The `/api/solve` endpoint just runs the solver subprocess and streams
its stdout back. Everything else is static files reading observations
and state JSON directly from disk via fetch.

The UI does not have its own database or in-memory state. Refreshing
the browser is a no-op; everything is read from files.

---

## 11. Implementation plan

This section breaks the work into concrete phases. Each phase is
independently shippable and verifiable.

### Phase 0: Design freeze (this document)

Status: in progress. Done when this document is reviewed and accepted.

Deliverable: SOLVER_DESIGN.md committed to the repo.

### Phase 1: Project scaffolding

Create the new directory structure alongside legacy code. Empty files
and folders only. No logic yet.

Deliverable: directory layout from section 1.1 exists in the repo,
with empty placeholder files where appropriate.

Acceptance: `python -m solver --help` prints a usage message.

### Phase 2: Geometry foundations

Implement `solver/geometry.py`:

- `project(world_xyz, cam) → pixel or None`
- `ray_from_pixel(pixel, cam) → (origin, direction)`
- `triangulate_pair(cam_a, pixel_a, cam_b, pixel_b) → xyz` (closest
  point between two skew rays)

Each function is pure, has type hints, and has unit tests covering:
- Forward projection of a known LM at a known cam matches expected pixel
- Backward ray for a pixel passes through the LM that produced it
- Triangulation of two rays gives the original LM xyz to numerical
  precision

Deliverable: `solver/geometry.py` with 100% test coverage on its
public functions.

Acceptance: `pytest tests/unit/test_geometry.py` passes.

### Phase 3: I/O layer

Implement `solver/io.py`:

- `load_observations(dir) → Observations`
- `load_measurements(dir) → Measurements`
- `load_state(dir) → State or None`
- `save_state(state, dir)` (atomic, temp+rename)
- `save_convergence_report(report, dir)`
- `save_provenance(prov, dir)`

Each loader validates the JSON schema and raises clear errors on
malformed input.

Deliverable: `solver/io.py` plus a small schema validation library
(or hand-written validators; jsonschema is fine if it's already a dep).

Acceptance: synthetic test fixtures (intentionally malformed) raise
the expected errors with helpful messages.

### Phase 4: Bootstrap

Implement `solver/bootstrap.py`:

- `bootstrap(observations, measurements) → State`

This is section 6 of this document, fully implemented. The function
handles horizon-based bootstrap, hint-based bootstrap, anchor LM
identification, simultaneous joint optimization, and z-constraint
application.

Deliverable: `solver/bootstrap.py` plus tests on hand-crafted small
scenarios (2 cams, 3 LMs) where the answer is known.

Acceptance: synthetic 2-cam-3-LM bootstrap converges to known answer
within 0.01 degrees and 0.01 meters.

### Phase 5: Main loop and convergence

Implement `solver/calibrate.py`, `solver/triangulate.py`, and
`solver/solve.py`:

- `calibrate_leak_cam(cam_name, state, observations) → updated_ypr`
- `calibrate_non_leak_cam(cam_name, state, observations) → updated_xyz_ypr_fov`
- `triangulate_landmark(lm_name, state, observations) → updated_xyz`
- `solve(observations, measurements, initial_state=None) → State, Report`

The `solve` function is the top-level entry point. It calls bootstrap
if no initial state, then runs the main iteration to convergence.

Deliverable: a working solver that produces state from observations
+ measurements alone.

Acceptance: on synthetic data with known ground truth, solver converges
to within tolerances in section 8.1.

### Phase 6: Procedural LMs and geometry priors

Implement `solver/procedural.py`:

- `compute_procedural_lms(state, measurements) → updated_state`
- `apply_geometry_priors(state, measurements) → updated_state`

The procedural module imports each known generator (portofino.sub_corner,
four_seasons.corner, etc.) and dispatches based on the `generator` field
in procedural_lms.json. The generators themselves live in
`solver/generators/` as small focused files.

Deliverable: procedural LMs computed from solved parents, matching
the legacy Portofino/FourSeasons output.

Acceptance: regression test against legacy procedural output passes.

### Phase 7: Migration

Implement `solver/migrate_legacy.py` per section 9.

Deliverable: running the migration script on the current repo produces
a valid set of observations/ and measurements/ files. Then running
`python -m solver solve` produces a state that matches legacy to
the tolerances in section 8.1.

Acceptance: the regression test in section 8.1 passes.

### Phase 8: UI

Implement the new UI per section 10.

Deliverable: a working UI that lets a human add/move/delete pixel
markers, trigger a solve, and view the resulting state.

Acceptance: a session of "add a marker → solve → see the LM appear
at the right place" works end-to-end.

### Phase 9: Cutover

Move legacy code to `legacy/`. Update README to point to the new
workflow. Remove the legacy server.py from the default workflow.

Deliverable: a clean repo where the new system is the default and
the legacy code is archived but still runnable for reference.

Acceptance: a fresh clone of the repo, following only README.md,
can produce a solved state without touching legacy/ at all.

---

## 12. Open questions

These need to be resolved before or during implementation. Listing them
here so they're not forgotten.

### 12.1 How do we handle leak cams that don't see any non-water LM?

Some leak cams might be over open water with no visible buildings, so
they have a horizon but no LMs. They can be bootstrapped (pitch and
roll from horizon, yaw from a hint), but they can't participate in
LM triangulation. They should still be solvable in principle, but
they don't contribute to anything. Decision: include them in state.json
with their bootstrapped ypr, but they're not used in the main loop.

### 12.2 What if the same LM is observed by leak and non-leak cams?

The LM xyz is solved using all observers, weighted by confidence. There's
no special treatment of "leak observers" vs "non-leak observers" in
the LM solve itself. The asymmetry is already encoded in the cam solve:
leak cams have locked xyz, non-leak cams don't.

### 12.3 How do we handle moving objects across screenshots?

Currently, all observations are assumed to be of static world points.
If a screenshot shows a moving object (a vehicle, a person), markings
on it would be useless. The system assumes humans don't mark moving
objects. No special handling.

### 12.4 What's the right way to represent "this LM is the same as that LM"?

Sometimes two cameras see the same point from different sides and
the human accidentally creates two distinct LM names. The system has
no way to know they're the same.

Decision: this is a human error and the fix is to rename one to match
the other in observations/pixels.json. Could later add an `aliases.json`
in measurements/ to map alternate names.

### 12.5 Performance

For 5000 LMs and 100 cams, the main loop is O(LMs × observers per LM
+ cams × LMs per cam) per iteration. Should be well under a minute
per iteration. Bundle adjustment with proper Jacobian sparsity could
be faster but isn't necessary for the current scale.

If performance becomes a problem, the upgrade path is to use
`scipy.optimize.least_squares` with `jac_sparsity` instead of independent
per-cam and per-LM solves. But we start with the simple approach.

### 12.6 Long-term: support for video sequences

Out of scope for v1. The current system handles screenshots, one
camera position per image. Video would require per-frame poses and
temporal smoothing, which is a larger system. Not addressed here.

---

## 13. What this document does NOT cover

Things that are deliberately out of scope of v1:

- **Automatic pixel detection** (SIFT/SuperGlue feature matching).
  Humans still mark every pixel. AI-assisted marking can be added later.
- **3D mesh extraction**. The current `extract_mesh_edges.py` workflow
  for procedural buildings is preserved and runs after the solver
  produces state.json. It reads state.json the same way it read
  landmarks.json.
- **Multi-user collaboration**. The system assumes one human at a time
  editing the repo. Collaborative editing is a future concern.
- **Cloud sync**. Everything lives in the repo, versioned by git.

---

## 14. Glossary

- **Leak cam**: a camera whose xyz and fov are known from the GTA debug
  console output visible in leaked videos.
- **Non-leak cam**: a camera whose all parameters must be solved.
- **Procedural LM**: an LM whose xyz is a deterministic function of
  other LMs.
- **Pixel-anchored LM**: an LM whose xyz is solved by triangulating
  pixel observations.
- **Observation**: a pixel marking by a human.
- **Measurement**: an external fact (GTA xyz, sea level, etc.).
- **Inference**: a solver output.
- **Bootstrap**: the initial step that gives rough values to all
  unknowns so the main loop can refine.
- **Convergence**: the main loop's stopping criterion: no parameter
  changes more than ε between two consecutive iterations.

---

## End of document

This is the design. Implementation starts at Phase 1 (project scaffolding).
