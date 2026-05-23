"""
Main solver loop.

Pipeline:
  1. Bootstrap to get initial state (leak cams + anchor LMs)
  2. Iterate: refine all LMs against current cams, refine all cams against
     current LMs. Stop when changes drop below tolerance or max iters hit.
  3. Calibrate non-leak cams against the converged LM positions.
  4. Run global bundle adjust: simultaneously refine ALL non-fixed params.
  5. Compute global metrics.

The non-leak cams are added in step 3, not step 2, because they require
4+ already-solved LMs to be well-posed via PnP.
"""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix

from .bootstrap import BootstrapError, bootstrap
from .calibrate import calibrate_leak_cam, calibrate_non_leak_cam
from .geometry import Camera, angular_residual_arcmin, project
from .io import (
    GlobalMetrics,
    Measurements,
    Observations,
    SolvedCamera,
    SolvedLandmark,
    State,
)
from .triangulate import triangulate_landmark


class SolveError(Exception):
    pass


def _solved_cameras_to_camera_dict(state: State) -> Dict[str, Camera]:
    """Convert solved cameras to Camera objects for geometry use."""
    return {
        name: Camera(
            xyz=sc.xyz, ypr=sc.ypr,
            hfov=sc.fov, image_size=(0, 0),  # image_size patched in caller
        )
        for name, sc in state.cameras.items()
    }


def _refine_landmarks(
    state: State,
    observations: Observations,
    measurements: Measurements,
) -> Tuple[Dict[str, SolvedLandmark], float]:
    """Re-triangulate every currently-known LM against current cams.

    Returns:
        (updated_landmarks, max_xyz_change_m)
    """
    # Build proper Camera dict with image sizes
    cameras: Dict[str, Camera] = {}
    for name, sc in state.cameras.items():
        if name in measurements.leak_cams:
            size = measurements.leak_cams[name].image_size
        elif name in measurements.non_leak_cam_meta:
            size = measurements.non_leak_cam_meta[name].image_size
        else:
            continue
        cameras[name] = Camera(
            xyz=sc.xyz, ypr=sc.ypr, hfov=sc.fov, image_size=size,
        )

    updated: Dict[str, SolvedLandmark] = {}
    max_change = 0.0
    for lm_name, lm in state.landmarks.items():
        z_c = measurements.z_constraints.get(lm_name)
        result = triangulate_landmark(
            lm_name, cameras, observations,
            z_constraint=z_c,
            initial_xyz=lm.xyz,
        )
        if result is None:
            updated[lm_name] = lm
            continue
        new_xyz, rms_px = result
        change = float(np.linalg.norm(np.array(new_xyz) - np.array(lm.xyz)))
        max_change = max(max_change, change)
        # Count observers
        n_obs = sum(
            1 for cam_name in state.cameras
            if lm_name in observations.pixels.get(cam_name, {})
        )
        updated[lm_name] = SolvedLandmark(
            kind=lm.kind, xyz=new_xyz,
            error_m=rms_px, n_observers=n_obs,
            computed_from=lm.computed_from,
        )
    return updated, max_change


def _refine_leak_cams(
    state: State,
    observations: Observations,
    measurements: Measurements,
) -> Tuple[Dict[str, SolvedCamera], float]:
    """Refine each leak cam's ypr against current LMs.

    Returns:
        (updated_cameras, max_ypr_change_deg)
    """
    updated: Dict[str, SolvedCamera] = dict(state.cameras)
    max_change = 0.0
    for cam_name, sc in state.cameras.items():
        if cam_name not in measurements.leak_cams:
            continue
        leak = measurements.leak_cams[cam_name]
        hint = measurements.bootstrap_hints.get(cam_name)
        hint_ypr = (hint.yaw, hint.pitch, hint.roll) if hint else None
        new_ypr, rms_px = calibrate_leak_cam(
            cam_name, leak, sc.ypr,
            state.landmarks, observations,
            hint_ypr=hint_ypr,
            hint_weight=0.05 if hint_ypr is not None else 0.0,
        )
        # Compute angular distance considering yaw wraparound
        yaw_d = abs(((new_ypr[0] - sc.ypr[0] + 180) % 360) - 180)
        change = max(yaw_d, abs(new_ypr[1] - sc.ypr[1]), abs(new_ypr[2] - sc.ypr[2]))
        max_change = max(max_change, change)
        # Count constraints (LMs visible from this cam)
        n_constraints = sum(
            1 for lm_name in state.landmarks
            if lm_name in observations.pixels.get(cam_name, {})
        )
        # Per-cam loss in arcmin
        cam = Camera(xyz=leak.xyz, ypr=new_ypr, hfov=leak.fov, image_size=leak.image_size)
        residuals = []
        for lm_name, lm in state.landmarks.items():
            pix_obs = observations.pixels.get(cam_name, {}).get(lm_name)
            if pix_obs is not None:
                residuals.append(
                    angular_residual_arcmin(cam, pix_obs.pixel, lm.xyz)
                )
        loss_arcmin = (
            float(np.sqrt(np.mean(np.array(residuals) ** 2)))
            if residuals else None
        )
        updated[cam_name] = SolvedCamera(
            kind="leak", xyz=leak.xyz, ypr=new_ypr, fov=leak.fov,
            loss_arcmin=loss_arcmin, n_constraints=n_constraints,
        )
    return updated, max_change


def _add_non_leak_cams(
    state: State,
    observations: Observations,
    measurements: Measurements,
) -> Dict[str, SolvedCamera]:
    """Calibrate non-leak cams against current landmarks.

    Returns updated cameras dict (incl. all leak cams unchanged).
    """
    updated: Dict[str, SolvedCamera] = dict(state.cameras)
    for cam_name, meta in measurements.non_leak_cam_meta.items():
        if cam_name in updated:
            continue  # already there from prior iter
        if cam_name not in observations.pixels:
            continue
        result = calibrate_non_leak_cam(
            cam_name, meta, state.landmarks, observations,
        )
        if result is None:
            continue
        xyz, ypr, fov, rms_px = result
        # Count constraints
        n_constraints = sum(
            1 for lm_name in state.landmarks
            if lm_name in observations.pixels.get(cam_name, {})
        )
        # Convert pixel RMS to angular (rough estimate)
        # For a 60deg hfov on 1920px image, 1 px ≈ 1.875 arcmin
        loss_arcmin = rms_px * (fov * 60.0 / meta.image_size[0])
        updated[cam_name] = SolvedCamera(
            kind="non_leak", xyz=xyz, ypr=ypr, fov=fov,
            loss_arcmin=loss_arcmin, n_constraints=n_constraints,
        )
    return updated


def _global_bundle_adjust(
    state: State,
    observations: Observations,
    measurements: Measurements,
    huber_delta_px: float = 5.0,
) -> State:
    """Run a global bundle adjustment.

    Free parameters:
      - For each leak cam: ypr (3)
      - For each non-leak cam: xyz, ypr, fov (7)
      - For each LM (non-z-constrained): xyz (3)
      - For each LM (z-constrained): xy (2), z fixed

    Sparse Jacobian: each observation depends only on the cam params and
    the LM params it involves. We build a sparsity pattern to let
    scipy compute Jacobians efficiently.
    """
    cam_names = sorted(state.cameras.keys())
    lm_names = sorted(state.landmarks.keys())

    leak_set = set(measurements.leak_cams.keys())
    z_constraints = measurements.z_constraints

    # Param offsets: leak ypr (3) | non-leak xyzyprfov (7) | LM xyz or xy
    cam_offsets: Dict[str, int] = {}
    cam_sizes: Dict[str, int] = {}
    offset = 0
    for name in cam_names:
        cam_offsets[name] = offset
        size = 3 if name in leak_set else 7
        cam_sizes[name] = size
        offset += size
    lm_offsets: Dict[str, int] = {}
    lm_sizes: Dict[str, int] = {}
    for name in lm_names:
        lm_offsets[name] = offset
        size = 2 if name in z_constraints else 3
        lm_sizes[name] = size
        offset += size
    n_params = offset

    # Pack initial values
    params0 = np.zeros(n_params, dtype=float)
    for name in cam_names:
        sc = state.cameras[name]
        off = cam_offsets[name]
        if cam_sizes[name] == 3:
            params0[off:off+3] = sc.ypr
        else:
            params0[off:off+3] = sc.xyz
            params0[off+3:off+6] = sc.ypr
            params0[off+6] = sc.fov
    for name in lm_names:
        lm = state.landmarks[name]
        off = lm_offsets[name]
        if lm_sizes[name] == 2:
            params0[off:off+2] = lm.xyz[:2]
        else:
            params0[off:off+3] = lm.xyz

    # Get image sizes
    cam_image_sizes: Dict[str, Tuple[int, int]] = {}
    for name in cam_names:
        if name in leak_set:
            cam_image_sizes[name] = measurements.leak_cams[name].image_size
        elif name in measurements.non_leak_cam_meta:
            cam_image_sizes[name] = measurements.non_leak_cam_meta[name].image_size
        else:
            cam_image_sizes[name] = (1920, 1080)  # fallback

    leak_meas = measurements.leak_cams

    # Build observation list and sparsity pattern
    obs_list = []  # (cam_name, lm_name, pix, conf)
    for cam_name in cam_names:
        cam_pix = observations.pixels.get(cam_name, {})
        for lm_name in lm_names:
            if lm_name in cam_pix:
                pix_obs = cam_pix[lm_name]
                obs_list.append((cam_name, lm_name, pix_obs.pixel, pix_obs.confidence))

    n_obs = len(obs_list)
    if n_obs == 0:
        return state

    # Sparsity: 2 rows per obs, each touches cam params + LM params
    sparsity = lil_matrix((2 * n_obs, n_params), dtype=int)
    for k, (cam_name, lm_name, _, _) in enumerate(obs_list):
        c_off = cam_offsets[cam_name]
        c_size = cam_sizes[cam_name]
        l_off = lm_offsets[lm_name]
        l_size = lm_sizes[lm_name]
        for row in (2*k, 2*k + 1):
            for c in range(c_off, c_off + c_size):
                sparsity[row, c] = 1
            for c in range(l_off, l_off + l_size):
                sparsity[row, c] = 1

    def unpack_cam(params, cam_name):
        off = cam_offsets[cam_name]
        if cam_sizes[cam_name] == 3:
            ypr = (float(params[off]), float(params[off+1]), float(params[off+2]))
            xyz = leak_meas[cam_name].xyz
            fov = leak_meas[cam_name].fov
        else:
            xyz = (float(params[off]), float(params[off+1]), float(params[off+2]))
            ypr = (float(params[off+3]), float(params[off+4]), float(params[off+5]))
            fov = float(params[off+6])
        return xyz, ypr, fov

    def unpack_lm(params, lm_name):
        off = lm_offsets[lm_name]
        if lm_sizes[lm_name] == 2:
            return (float(params[off]), float(params[off+1]), z_constraints[lm_name].z)
        return (float(params[off]), float(params[off+1]), float(params[off+2]))

    def residuals(params):
        out = np.zeros(2 * n_obs)
        for k, (cam_name, lm_name, pix, conf) in enumerate(obs_list):
            xyz, ypr, fov = unpack_cam(params, cam_name)
            if not (5.0 < fov < 175.0):
                out[2*k] = 1e4
                out[2*k+1] = 1e4
                continue
            lm_xyz = unpack_lm(params, lm_name)
            cam = Camera(xyz=xyz, ypr=ypr, hfov=fov, image_size=cam_image_sizes[cam_name])
            projected = project(lm_xyz, cam)
            if projected is None:
                out[2*k] = 1e3 * conf
                out[2*k+1] = 1e3 * conf
            else:
                out[2*k] = (projected[0] - pix[0]) * conf
                out[2*k+1] = (projected[1] - pix[1]) * conf
        return out

    result = least_squares(
        residuals, params0,
        method="trf", loss="huber", f_scale=huber_delta_px,
        jac_sparsity=sparsity,
        max_nfev=100,  # bundle is expensive; cap iterations
    )

    # Unpack
    new_cameras: Dict[str, SolvedCamera] = {}
    for name in cam_names:
        xyz, ypr, fov = unpack_cam(result.x, name)
        old = state.cameras[name]
        new_cameras[name] = SolvedCamera(
            kind=old.kind, xyz=xyz, ypr=(ypr[0] % 360.0, ypr[1], ypr[2]),
            fov=fov, loss_arcmin=old.loss_arcmin,
            n_constraints=old.n_constraints,
        )
    new_landmarks: Dict[str, SolvedLandmark] = {}
    for name in lm_names:
        old = state.landmarks[name]
        new_landmarks[name] = SolvedLandmark(
            kind=old.kind, xyz=unpack_lm(result.x, name),
            error_m=old.error_m, n_observers=old.n_observers,
            computed_from=old.computed_from,
        )

    return State(
        solver_version=state.solver_version,
        solved_at=state.solved_at,
        input_hash=state.input_hash,
        cameras=new_cameras,
        landmarks=new_landmarks,
        global_metrics=state.global_metrics,
    )


def _compute_global_metrics(
    state: State,
    observations: Observations,
    measurements: Measurements,
) -> GlobalMetrics:
    """Compute residuals across all observations for diagnostics."""
    residuals: List[float] = []
    for cam_name, sc in state.cameras.items():
        if cam_name in measurements.leak_cams:
            size = measurements.leak_cams[cam_name].image_size
        elif cam_name in measurements.non_leak_cam_meta:
            size = measurements.non_leak_cam_meta[cam_name].image_size
        else:
            continue
        cam = Camera(xyz=sc.xyz, ypr=sc.ypr, hfov=sc.fov, image_size=size)
        cam_pix = observations.pixels.get(cam_name, {})
        for lm_name, pix_obs in cam_pix.items():
            if lm_name in state.landmarks:
                lm_xyz = state.landmarks[lm_name].xyz
                residuals.append(
                    angular_residual_arcmin(cam, pix_obs.pixel, lm_xyz)
                )

    if not residuals:
        return GlobalMetrics(
            rms_loss_arcmin=0.0, median_loss_arcmin=0.0, p99_loss_arcmin=0.0,
            total_observations=0, outlier_count_above_20_arcmin=0,
        )

    arr = np.array(residuals)
    return GlobalMetrics(
        rms_loss_arcmin=float(np.sqrt(np.mean(arr ** 2))),
        median_loss_arcmin=float(np.median(arr)),
        p99_loss_arcmin=float(np.percentile(arr, 99)),
        total_observations=len(residuals),
        outlier_count_above_20_arcmin=int(np.sum(arr > 20.0)),
    )


def solve(
    observations: Observations,
    measurements: Measurements,
    solver_version: str = "0.5.0-solve",
    max_iter: int = 20,
    tol_lm_change_m: float = 0.01,
    tol_cam_change_deg: float = 0.001,
    verbose: bool = False,
) -> Tuple[State, Dict[str, object]]:
    """Top-level solve: bootstrap, iterate, calibrate non-leak, bundle, metrics.

    Returns:
        (state, diagnostics) where diagnostics is a dict with iteration
        counts, per-iteration changes, and final metrics.
    """
    log = []

    # Step 1: bootstrap
    state, boot_diag = bootstrap(observations, measurements, solver_version)
    log.append({"phase": "bootstrap", **boot_diag})
    if verbose:
        print(f"Bootstrap: {len(state.cameras)} cams, {len(state.landmarks)} LMs")

    # Step 2: iterate LM + leak cam refinement until convergence
    iter_log = []
    for it in range(max_iter):
        # Refine LMs
        new_lms, lm_change = _refine_landmarks(state, observations, measurements)
        state = State(
            solver_version=state.solver_version, solved_at=state.solved_at,
            input_hash=state.input_hash,
            cameras=state.cameras, landmarks=new_lms,
            global_metrics=state.global_metrics,
        )
        # Refine leak cams
        new_cams, cam_change = _refine_leak_cams(state, observations, measurements)
        state = State(
            solver_version=state.solver_version, solved_at=state.solved_at,
            input_hash=state.input_hash,
            cameras=new_cams, landmarks=state.landmarks,
            global_metrics=state.global_metrics,
        )
        iter_log.append({
            "iter": it, "lm_max_change_m": lm_change,
            "cam_max_change_deg": cam_change,
        })
        if verbose:
            print(f"  iter {it}: lm Δ={lm_change:.4f}m, cam Δ={cam_change:.4f}deg")
        if lm_change < tol_lm_change_m and cam_change < tol_cam_change_deg:
            break
    log.append({"phase": "main_loop", "iterations": iter_log})

    # Step 3: add non-leak cams (calibrated via PnP against current LMs)
    cams_with_non_leak = _add_non_leak_cams(state, observations, measurements)
    state = State(
        solver_version=state.solver_version, solved_at=state.solved_at,
        input_hash=state.input_hash,
        cameras=cams_with_non_leak, landmarks=state.landmarks,
        global_metrics=state.global_metrics,
    )
    log.append({
        "phase": "non_leak_calibration",
        "n_non_leak_cams_added": len(cams_with_non_leak) - len(measurements.leak_cams),
    })
    if verbose:
        n_nl = len(cams_with_non_leak) - len(measurements.leak_cams)
        print(f"Non-leak cams added: {n_nl}")

    # Step 4: global bundle adjust
    state = _global_bundle_adjust(state, observations, measurements)
    log.append({"phase": "bundle_adjust", "complete": True})
    if verbose:
        print("Global bundle adjust complete")

    # Step 5: metrics
    metrics = _compute_global_metrics(state, observations, measurements)
    state = State(
        solver_version=state.solver_version,
        solved_at=datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
        input_hash=state.input_hash,
        cameras=state.cameras, landmarks=state.landmarks,
        global_metrics=metrics,
    )
    if verbose:
        print(f"Final RMS: {metrics.rms_loss_arcmin:.3f} arcmin, "
              f"median: {metrics.median_loss_arcmin:.3f}, "
              f"outliers (>20 arcmin): {metrics.outlier_count_above_20_arcmin}")

    diagnostics = {"log": log, "final_metrics": metrics}
    return state, diagnostics

