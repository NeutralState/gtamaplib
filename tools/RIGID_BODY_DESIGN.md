# Rigid Body Solver Integration — Design Doc (Niveau 2)

**Status**: Design phase, pre-implementation.
**Author**: Alexandre + Claude, 2026-05-15 afternoon
**Context**: After Niveau 1 (xyz override from FourSeasons model) dropped RMS
from 2.97 to 1.94 arcmin (-35%), we want to make the solver
itself aware of rigid bodies for further constraints.

## Motivation

Currently in `tools/bundle_adjust.py`:
- Each LM has 3 independent DOFs (x, y, z) in the optimizer vector
- 9 Four Seasons LMs = 27 DOFs that can drift apart from each other
- Solver has no notion that "Four Seasons (BE) and (BW) are 30m apart by construction"

After Niveau 2:
- One rigid body "four_seasons" has 6 DOFs (translation + rotation)
- The 13+ Four Seasons LMs are derived from these 6 DOFs + their local-frame coords
- Internal geometry locked: building can move and rotate as a whole but cannot deform
- DOFs drop from 27 to 6 → far more constrained, expected to drop RMS further

## Architecture changes

### Current state

```
x0 = [cam_params (N_CAM × 7), lm_params (N_LM × 3)]

pixel_residuals(x):
    for (cam, lm) in observations:
        cam_xyz, cam_ypr, cam_hfov = extract from x or cache
        if lm in lm_idx:
            lm_xyz = x[lm slot]
        else:
            lm_xyz = _fixed_lm_xyz[lm]  # corrupted W, etc.
        proj = cam.project(lm_xyz)
        residual = (proj - marker) * arcmin
```

### New state

```
x0 = [cam_params (N_CAM × 7), lm_params (N_LM_FREE × 3), rigid_params (N_BODIES × 6)]

# At init:
rigid_bodies = {
    'four_seasons': {
        'centroid_world': (cx, cy, cz),  # initial centroid from Niveau 1 xyz
        'lm_local_coords': {
            'Four Seasons Hotel Miami (BE)':  (a, b, c),
            'Four Seasons Hotel Miami (BW)':  (d, e, f),
            ...
        },
        'param_offset': INT,  # where in x its 6 DOFs start
    }
}
lm_to_rigid_body = {
    'Four Seasons Hotel Miami (BE)':  'four_seasons',
    ...
}

# In pixel_residuals:
elif lm_name in lm_to_rigid_body:
    body = rigid_bodies[lm_to_rigid_body[lm_name]]
    tx, ty, tz, rx, ry, rz = x[body['param_offset']:body['param_offset']+6]
    local = body['lm_local_coords'][lm_name]
    lm_xyz = transform_rigid_to_world(local, body['centroid_world'], tx, ty, tz, rx, ry, rz)
```

## Decisions

### D1: Rotation representation

**Choice**: Euler XYZ small-angle, 3 params (rx, ry, rz) in radians.

Rationale:
- Building is initialized at the world position from Niveau 1; expected rotation
  deltas are tiny (< 5 degrees in any axis) during optimization
- Singularity at gimbal lock (rotation pi/2 around Y) is not a concern in this range
- 3 DOFs (no constraint to manage like quaternion unit norm)
- Composition with translation is straightforward

Alternative considered: Quaternions (4 DOFs + unit norm constraint, more robust
in larger rotation ranges). Rejected because:
- Constraint management complicates scipy.least_squares
- Doesn't help for our use case where rotations are small

### D2: Body origin (local frame)

**Choice**: Centroid of the body's anchor LMs.

```python
centroid = mean([all 13 anchor LM xyz from rlx model])
```

For Four Seasons, this is approximately (-832, -1286, 230).

Rationale:
- Numerically stable (rotations around centroid have minimal translation effect)
- Symmetric (no preferred corner)
- Easy to compute

### D3: Which LMs are part of the rigid body

**Choice**: All Four Seasons LMs currently in landmarks.json that match the rlx
FourSeasons model's `_landmarks()` output, plus the 9 additional corners added
in Niveau 1.

Total expected: 14 LMs in `four_seasons` body
- BE, BW, E, NE, NW, SE, SW, W (the 8 from `_landmarks()`)
- 40NW, 40W, 40E, 32NE, 56NE, HB28SE, HB8SE, HB58SE, HB58NE (the 9 added)

Wait — that's 17 LMs total. Let me recount from landmarks.json after Niveau 1.

### D4: Local coordinate calculation

For each LM in the body:
```python
local_xyz = world_xyz_at_init - centroid_world
```

Where `world_xyz_at_init` is the Niveau 1 xyz (from rlx rigid model), so by
construction these local coords form a coherent geometry that the rigid body
will preserve.

### D5: Transformation local → world

```python
def transform_rigid_to_world(local, centroid, tx, ty, tz, rx, ry, rz):
    # Rotation matrix from Euler XYZ small angles
    R = rotation_matrix_xyz(rx, ry, rz)
    # Rotate local point around centroid, then translate
    return R @ local + centroid + np.array([tx, ty, tz])
```

Init values: tx=ty=tz=0, rx=ry=rz=0 → R=I → world_xyz = local + centroid =
world_xyz_at_init. So the solver starts at the Niveau 1 state and can move from
there.

### D6: Jacobian sparsity

Each observation of a rigid-body LM has its 2 residual rows (dx, dy) depend on:
- 7 cam params (if cam is optimizable)
- 6 rigid body params (instead of 3 LM params)

In J_sparsity update:
```python
if lm_name in lm_to_rigid_body:
    body_offset = LM_BLOCK + rigid_bodies[lm_to_rigid_body[lm_name]]['param_offset']
    for c in range(6):
        J_sparsity[2*k, body_offset+c] = 1
        J_sparsity[2*k+1, body_offset+c] = 1
```

### D7: LMs that remain individual (not in rigid bodies)

All other LMs (510 - 14 = 496 LMs) keep their original 3 DOFs and behavior.
The `lm_idx` is rebuilt to only include free (non-rigid) LMs.

### D8: Apply step

When writing optimized results back to landmarks.json:
- Free LMs: write their new xyz directly (unchanged from current code)
- Rigid LMs: compute their xyz from final rigid params, write each individually

## Implementation plan

### Step 1: Setup data structures (no solver change yet)
- Add `rigid_bodies` global dict
- Add `lm_to_rigid_body` global dict
- Populate from Four Seasons model on startup
- Compute centroid and local coords

### Step 2: Modify `x0` construction
- Add rigid body block at the end
- Rebuild `lm_idx` to exclude rigid LMs
- Adjust N_VARS, CAM_BLOCK, LM_BLOCK constants

### Step 3: Modify `pixel_residuals`
- Add new branch for `lm_name in lm_to_rigid_body`
- Implement `transform_rigid_to_world`

### Step 4: Modify Jacobian sparsity
- Sparsity pattern for rigid body LMs

### Step 5: Modify output / apply
- Compute rigid LM xyz from final params, write to landmarks.json

### Step 6: Test
- Run bundle adjust, compare RMS to Niveau 1 (1.94')
- Verify no Four Seasons LM xyz drifts from rigid geometry

## Risks

1. **Convergence**: 6-DOF rigid body might converge slower than 27-DOF free LMs.
   Initial values are good (Niveau 1 state), but local minima possible.
2. **Numerical**: Euler small-angle approximation breaks if rotations grow large.
   Mitigation: solver hits xtol before rotations grow.
3. **Sparsity bug**: easy to misalign indices when splitting `x` into 3 blocks
   (cam, free_lm, rigid). Need careful testing.
4. **Apply bug**: forgetting to recompute rigid LM xyz from final params would
   leave landmarks.json with stale values.

## Success metrics

- RMS at Niveau 2 < 1.94 arcmin (improvement vs Niveau 1)
- No Four Seasons LM xyz drifts more than 0.01m from rigid model post-optimization
  (proof that rigidity is enforced)
- Convergence within 500 iterations (same as before)
