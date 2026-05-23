"""
Main solver loop with procedural LMs and geometry priors.

Pipeline:
  1. Bootstrap to get initial state (leak cams + anchor LMs)
  2. Iterate: refine pixel-anchored LMs against current cams,
              compute procedural LMs from refined deps,
              refine leak cams against current LMs.
  3. Calibrate non-leak cams against the converged LM positions.
  4. Global bundle adjust with pixel + prior residuals.
  5. Compute global metrics.
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
from .priors import compute_prior_residuals, n_residuals_for_prior
from .procedural import (
    ProceduralError,
    compute_procedural,
    topological_order,
)
from .triangulate import triangulate_landmark


class SolveError(Exception):
    pass


def _apply_procedural_lms(
    landmarks: Dict[str, SolvedLandmark],
    measurements: Measurements,
) -> Dict[str, SolvedLandmark]:
    if not measurements.procedural_lms:
        return landmarks
    try:
        order = topological_order(measurements.procedural_lms)
    except ProceduralError:
        return landmarks
    out = dict(landmarks)
    for name in order:
        spec = measurements.procedural_lms[name]
        deps_xyz: Dict[str, Tuple[float, float, float]] = {}
        all_present = True
        for dep_name in spec.depends_on:
            if dep_name in out:
                deps_xyz[dep_name] = out[dep_name].xyz
            else:
                all_present = False
                break
        if not all_present:
            continue
        try:
            xyz = compute_procedural(spec.generator, deps_xyz, spec.params)
        except ProceduralError:
            continue
        out[name] = SolvedLandmark(
            kind="procedural", xyz=xyz, n_observers=0,
            computed_from=spec.generator,
        )
    return out


def _refine_landmarks(
    state: State,
    observations: Observations,
    measurements: Measurements,
) -> Tuple[Dict[str, SolvedLandmark], float]:
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
    proc_names = set(measurements.procedural_lms.keys())
    for lm_name, lm in state.landmarks.items():
        if lm_name in proc_names:
            updated[lm_name] = lm
            continue
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
        yaw_d = abs(((new_ypr[0] - sc.ypr[0] + 180) % 360) - 180)
        change = max(yaw_d, abs(new_ypr[1] - sc.ypr[1]), abs(new_ypr[2] - sc.ypr[2]))
        max_change = max(max_change, change)
        n_constraints = sum(
            1 for lm_name in state.landmarks
            if lm_name in observations.pixels.get(cam_name, {})
        )
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
    updated: Dict[str, SolvedCamera] = dict(state.cameras)
    for cam_name, meta in measurements.non_leak_cam_meta.items():
        if cam_name in updated:
            continue
        if cam_name not in observations.pixels:
            continue
        result = calibrate_non_leak_cam(
            cam_name, meta, state.landmarks, observations,
        )
        if result is None:
            continue
        xyz, ypr, fov, rms_px = result
        n_constraints = sum(
            1 for lm_name in state.landmarks
            if lm_name in observations.pixels.get(cam_name, {})
        )
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
    cam_names = sorted(state.cameras.keys())
    leak_set = set(measurements.leak_cams.keys())
    z_constraints = measurements.z_constraints
    proc_names = set(measurements.procedural_lms.keys())

    free_lm_names = sorted(n for n in state.landmarks if n not in proc_names)

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
    for name in free_lm_names:
        lm_offsets[name] = offset
        size = 2 if name in z_constraints else 3
        lm_sizes[name] = size
        offset += size
    n_params = offset

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
    for name in free_lm_names:
        lm = state.landmarks[name]
        off = lm_offsets[name]
        if lm_sizes[name] == 2:
            params0[off:off+2] = lm.xyz[:2]
        else:
            params0[off:off+3] = lm.xyz

    cam_image_sizes: Dict[str, Tuple[int, int]] = {}
    for name in cam_names:
        if name in leak_set:
            cam_image_sizes[name] = measurements.leak_cams[name].image_size
        elif name in measurements.non_leak_cam_meta:
            cam_image_sizes[name] = measurements.non_leak_cam_meta[name].image_size
        else:
            cam_image_sizes[name] = (1920, 1080)

    leak_meas = measurements.leak_cams

    obs_list = []
    for cam_name in cam_names:
        cam_pix = observations.pixels.get(cam_name, {})
        for lm_name in state.landmarks:
            if lm_name in cam_pix:
                pix_obs = cam_pix[lm_name]
                obs_list.append((cam_name, lm_name, pix_obs.pixel, pix_obs.confidence))
    n_obs = len(obs_list)

    prior_entries = []
    prior_total_residuals = 0
    for name, prior in measurements.geometry_priors.items():
        n_res = n_residuals_for_prior(prior.type, len(prior.lms))
        if n_res > 0:
            prior_entries.append((name, prior, n_res, prior_total_residuals))
            prior_total_residuals += n_res

    total_residuals = 2 * n_obs + prior_total_residuals
    if total_residuals == 0:
        return state

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

    def unpack_lm_xyz(params, lm_name):
        off = lm_offsets[lm_name]
        if lm_sizes[lm_name] == 2:
            return (float(params[off]), float(params[off+1]), z_constraints[lm_name].z)
        return (float(params[off]), float(params[off+1]), float(params[off+2]))

    def get_all_lm_xyz(params):
        out: Dict[str, Tuple[float, float, float]] = {}
        for name in free_lm_names:
            out[name] = unpack_lm_xyz(params, name)
        if proc_names:
            try:
                order = topological_order(measurements.procedural_lms)
            except ProceduralError:
                order = []
            for name in order:
                spec = measurements.procedural_lms[name]
                deps_xyz = {d: out[d] for d in spec.depends_on if d in out}
                if len(deps_xyz) < len(spec.depends_on):
                    continue
                try:
                    out[name] = compute_procedural(spec.generator, deps_xyz, spec.params)
                except ProceduralError:
                    continue
        return out

    def residuals(params):
        all_xyz = get_all_lm_xyz(params)
        out = np.zeros(total_residuals)
        for k, (cam_name, lm_name, pix, conf) in enumerate(obs_list):
            xyz, ypr, fov = unpack_cam(params, cam_name)
            if not (5.0 < fov < 175.0):
                out[2*k] = 1e4
                out[2*k+1] = 1e4
                continue
            if lm_name not in all_xyz:
                out[2*k] = 1e3 * conf
                out[2*k+1] = 1e3 * conf
                continue
            cam = Camera(xyz=xyz, ypr=ypr, hfov=fov, image_size=cam_image_sizes[cam_name])
            projected = project(all_xyz[lm_name], cam)
            if projected is None:
                out[2*k] = 1e3 * conf
                out[2*k+1] = 1e3 * conf
            else:
                out[2*k] = (projected[0] - pix[0]) * conf
                out[2*k+1] = (projected[1] - pix[1]) * conf
        base_offset = 2 * n_obs
        lm_xyz_np = {n: np.asarray(xyz, dtype=float) for n, xyz in all_xyz.items()}
        for name, prior, n_res, off in prior_entries:
            if not all(lm in lm_xyz_np for lm in prior.lms):
                continue
            try:
                r = compute_prior_residuals(
                    prior.type, lm_xyz_np, prior.lms,
                    prior.value if prior.value is not None else 0.0,
                    prior.weight,
                )
                for i, v in enumerate(r):
                    if base_offset + off + i < total_residuals:
                        out[base_offset + off + i] = v
            except Exception:
                continue
        return out

    result = least_squares(
        residuals, params0,
        method="trf", loss="huber", f_scale=huber_delta_px,
        max_nfev=100,
    )

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
    all_xyz_final = get_all_lm_xyz(result.x)
    for name, lm in state.landmarks.items():
        new_xyz = all_xyz_final.get(name, lm.xyz)
        new_landmarks[name] = SolvedLandmark(
            kind=lm.kind, xyz=new_xyz,
            error_m=lm.error_m, n_observers=lm.n_observers,
            computed_from=lm.computed_from,
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
    solver_version: str = "0.6.0-solve-with-procedural",
    max_iter: int = 20,
    tol_lm_change_m: float = 0.01,
    tol_cam_change_deg: float = 0.001,
    verbose: bool = False,
) -> Tuple[State, Dict[str, object]]:
    log = []
    state, boot_diag = bootstrap(observations, measurements, solver_version)
    new_lms = _apply_procedural_lms(state.landmarks, measurements)
    state = State(
        solver_version=state.solver_version, solved_at=state.solved_at,
        input_hash=state.input_hash, cameras=state.cameras,
        landmarks=new_lms, global_metrics=state.global_metrics,
    )
    log.append({"phase": "bootstrap", **boot_diag})
    if verbose:
        print(f"Bootstrap: {len(state.cameras)} cams, {len(state.landmarks)} LMs")

    iter_log = []
    for it in range(max_iter):
        new_lms, lm_change = _refine_landmarks(state, observations, measurements)
        new_lms = _apply_procedural_lms(new_lms, measurements)
        state = State(
            solver_version=state.solver_version, solved_at=state.solved_at,
            input_hash=state.input_hash, cameras=state.cameras,
            landmarks=new_lms, global_metrics=state.global_metrics,
        )
        new_cams, cam_change = _refine_leak_cams(state, observations, measurements)
        state = State(
            solver_version=state.solver_version, solved_at=state.solved_at,
            input_hash=state.input_hash, cameras=new_cams,
            landmarks=state.landmarks, global_metrics=state.global_metrics,
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

    cams_with_non_leak = _add_non_leak_cams(state, observations, measurements)
    state = State(
        solver_version=state.solver_version, solved_at=state.solved_at,
        input_hash=state.input_hash, cameras=cams_with_non_leak,
        landmarks=state.landmarks, global_metrics=state.global_metrics,
    )
    log.append({
        "phase": "non_leak_calibration",
        "n_non_leak_cams_added": len(cams_with_non_leak) - len(measurements.leak_cams),
    })

    state = _global_bundle_adjust(state, observations, measurements)
    log.append({"phase": "bundle_adjust", "complete": True})

    metrics = _compute_global_metrics(state, observations, measurements)
    state = State(
        solver_version=state.solver_version,
        solved_at=datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
        input_hash=state.input_hash,
        cameras=state.cameras, landmarks=state.landmarks,
        global_metrics=metrics,
    )
    diagnostics = {"log": log, "final_metrics": metrics}
    return state, diagnostics

