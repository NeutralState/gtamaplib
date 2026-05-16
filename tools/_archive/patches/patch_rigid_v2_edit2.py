#!/usr/bin/env python3
"""
patch_rigid_v2_edit2.py — Integrate rigid body into x0 and pixel_residuals.

Edit 2 of N for Niveau 2 rigid body integration.

Changes:
1. Add helper functions _rotation_matrix_xyz and _transform_rigid_to_world
2. Add RIGID_BLOCK and N_RIGID_BODIES already declared in edit 1
3. Build rigid_params_init (zeros)
4. Update x0 to include rigid params
5. Update LM_BLOCK and N_VARS to account for rigid params
6. Update lm_params reshape (slice to LM_BLOCK only, not [CAM_BLOCK:])
7. Add elif branch in pixel_residuals for rigid LMs

Idempotent via sentinel [RIGID-BODY-V1-EDIT2].
"""
import shutil
import sys
from pathlib import Path

PATH = Path("tools/bundle_adjust.py")
SENTINEL = "[RIGID-BODY-V1-EDIT2]"


def main():
    apply = "--apply" in sys.argv

    text = PATH.read_text()
    if SENTINEL in text:
        print(f"Already patched ({SENTINEL}). Nothing to do.")
        return

    # ─── PATCH A: Insert helper functions after the rigid body setup ──────
    # Anchor: the end-marker comment we left in edit 1
    anchor_a = "# ── End [RIGID-BODY-V1] setup ─────────────────────────────────────────────────"
    if anchor_a not in text:
        print(f"ERROR: anchor A not found")
        sys.exit(1)

    helpers = '''
# ── ''' + SENTINEL + ''' helpers ──────────────────────────────────────────────
def _rotation_matrix_xyz(rx, ry, rz):
    """Euler XYZ rotation matrix (Rz @ Ry @ Rx) for world axes."""
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def _transform_rigid_to_world(local_xyz, centroid, params6):
    """Apply rigid transform to a local coord. params6 = (tx, ty, tz, rx, ry, rz)."""
    tx, ty, tz, rx, ry, rz = params6
    R = _rotation_matrix_xyz(rx, ry, rz)
    return R @ local_xyz + centroid + np.array([tx, ty, tz])
'''
    text = text.replace(anchor_a, anchor_a + "\n" + helpers)

    # ─── PATCH B: Update lm_params_init loop to use opt_lm_names ──────────
    # Since edit 1 already set opt_lm_names = _free_lm_names, this should
    # already work. But check N_LM is also from the new opt_lm_names.
    # Find "N_LM      = len(opt_lm_names)"
    anchor_b = "N_LM      = len(opt_lm_names)"
    if anchor_b in text:
        # Need to make N_LM reflect the trimmed list. The line is BEFORE the
        # rigid body setup though, so it captures the original. Let's add a
        # rebind after the setup.
        anchor_b_new = "# Remove rigid LMs from lm_idx and opt_lm_names; computed via rigid body params instead"
        if anchor_b_new in text:
            # Add a re-assignment of N_LM after the setup
            rebind = '''
# ''' + SENTINEL + ''': rebind N_LM to reflect the rigid-LM-excluded opt_lm_names
N_LM = len(opt_lm_names)
LM_BLOCK = N_LM * 3'''
            # Insert after the existing rebind block
            text = text.replace(
                "N_RIGID_BODIES = len(_rigid_bodies)\nRIGID_BLOCK = N_RIGID_BODIES * 6",
                "N_RIGID_BODIES = len(_rigid_bodies)\nRIGID_BLOCK = N_RIGID_BODIES * 6" + rebind,
            )

    # ─── PATCH C: Update N_VARS to include RIGID_BLOCK ────────────────────
    # The original was N_VARS = CAM_BLOCK + N_LM * 3, which is set BEFORE
    # we trim N_LM. We need to recompute.
    text = text.replace(
        "N_VARS    = CAM_BLOCK + N_LM * 3",
        "N_VARS    = CAM_BLOCK + LM_BLOCK + RIGID_BLOCK  # " + SENTINEL,
    )

    # ─── PATCH D: Build rigid_params_init and update x0 ───────────────────
    anchor_d = "x0 = np.concatenate([cam_params_init.ravel(), lm_params_init.ravel()])"
    if anchor_d not in text:
        print(f"ERROR: anchor D not found")
        sys.exit(1)
    text = text.replace(
        anchor_d,
        '''# ''' + SENTINEL + ''': add rigid body params (init at zero = identity transform)
rigid_params_init = np.zeros(RIGID_BLOCK)
x0 = np.concatenate([cam_params_init.ravel(), lm_params_init.ravel(), rigid_params_init])''',
    )

    # ─── PATCH E: Update pixel_residuals lm_params reshape ────────────────
    # The original: lm_params  = x[CAM_BLOCK:].reshape(N_LM, 3)
    # We need to slice: x[CAM_BLOCK:CAM_BLOCK + LM_BLOCK].reshape(N_LM, 3)
    text = text.replace(
        "lm_params  = x[CAM_BLOCK:].reshape(N_LM, 3)",
        "lm_params  = x[CAM_BLOCK:CAM_BLOCK + LM_BLOCK].reshape(N_LM, 3)  # " + SENTINEL,
    )

    # ─── PATCH F: Add elif branch in pixel_residuals for rigid LMs ────────
    anchor_f = '''        if lm_name in lm_idx:
            lp = lm_params[lm_idx[lm_name]]
            z_val = float(lp[2])
            zc = _z_constraints.get(lm_name)
            if zc and zc.get('type') == 'fixed':
                z_val = float(zc['value'])
            lm_xyz = (float(lp[0]), float(lp[1]), z_val)
        else:
            lm_xyz = _fixed_lm_xyz[lm_name]'''

    new_branch = '''        if lm_name in lm_idx:
            lp = lm_params[lm_idx[lm_name]]
            z_val = float(lp[2])
            zc = _z_constraints.get(lm_name)
            if zc and zc.get('type') == 'fixed':
                z_val = float(zc['value'])
            lm_xyz = (float(lp[0]), float(lp[1]), z_val)
        elif lm_name in _lm_to_rigid_body:
            # ''' + SENTINEL + ''': compute LM xyz from rigid body 6 DOFs
            body_id = _lm_to_rigid_body[lm_name]
            body_keys = list(_rigid_bodies.keys())
            body_idx = body_keys.index(body_id)
            rigid_offset = CAM_BLOCK + LM_BLOCK + body_idx * 6
            body_params = x[rigid_offset:rigid_offset + 6]
            body = _rigid_bodies[body_id]
            local = body['lm_local_coords'][lm_name]
            world = _transform_rigid_to_world(local, body['centroid'], body_params)
            lm_xyz = (float(world[0]), float(world[1]), float(world[2]))
        else:
            lm_xyz = _fixed_lm_xyz[lm_name]'''

    if anchor_f not in text:
        print(f"ERROR: anchor F not found")
        sys.exit(1)
    text = text.replace(anchor_f, new_branch)

    # ─── PATCH G: Update Jacobian sparsity for rigid LMs ──────────────────
    # Find the existing if lm_name in lm_idx block
    anchor_g = '''    if lm_name in lm_idx:
        l = lm_idx[lm_name]
        for r in rows:
            for col in range(CAM_BLOCK + 3*l, CAM_BLOCK + 3*l + 3):
                J_sparsity[r, col] = 1'''

    new_sparsity = '''    if lm_name in lm_idx:
        l = lm_idx[lm_name]
        for r in rows:
            for col in range(CAM_BLOCK + 3*l, CAM_BLOCK + 3*l + 3):
                J_sparsity[r, col] = 1
    elif lm_name in _lm_to_rigid_body:
        # ''' + SENTINEL + ''': rigid LM depends on 6 body DOFs
        body_keys = list(_rigid_bodies.keys())
        body_idx = body_keys.index(_lm_to_rigid_body[lm_name])
        rigid_offset = CAM_BLOCK + LM_BLOCK + body_idx * 6
        for r in rows:
            for col in range(rigid_offset, rigid_offset + 6):
                J_sparsity[r, col] = 1'''

    if anchor_g not in text:
        print(f"ERROR: anchor G not found")
        sys.exit(1)
    text = text.replace(anchor_g, new_sparsity)

    if not apply:
        print(f"DRY-RUN: would apply 7 patches. Sentinel: {SENTINEL}")
        return

    backup = PATH.with_suffix(".py.bak_rigid_v2_edit2")
    shutil.copy(PATH, backup)
    PATH.write_text(text)
    print(f"Patched {PATH}")
    print(f"Backup: {backup}")
    print("7 sub-patches applied (A through G)")


if __name__ == "__main__":
    main()
