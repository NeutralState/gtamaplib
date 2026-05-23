"""
Per-camera calibration.

Two flavors:
  - calibrate_leak_cam: refine only ypr (xyz and fov are ground truth)
  - calibrate_non_leak_cam: refine xyz + ypr + fov (full 7-dof PnP)

Both take a cam name, the current cameras and landmarks dicts, and the
observations, and produce a refined Camera or None on failure.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import least_squares

from .geometry import (
    Camera,
    project,
    triangulate_pair,
)
from .io import (
    LeakCamMeasurement,
    NonLeakCamMeta,
    Observations,
    PixelObservation,
    SolvedLandmark,
)


def calibrate_leak_cam(
    cam_name: str,
    leak_cam: LeakCamMeasurement,
    initial_ypr: Tuple[float, float, float],
    landmarks: Dict[str, SolvedLandmark],
    observations: Observations,
    hint_ypr: Optional[Tuple[float, float, float]] = None,
    hint_weight: float = 0.0,
    huber_delta_px: float = 5.0,
) -> Tuple[Tuple[float, float, float], float]:
    """Refine the ypr of one leak cam against the current landmarks.

    Args:
        cam_name: name of the cam
        leak_cam: ground-truth xyz and fov
        initial_ypr: starting orientation
        landmarks: {lm_name: SolvedLandmark} of currently-solved LMs
        observations: pixel observations
        hint_ypr: optional soft pull toward this ypr (defaults to no pull)
        hint_weight: weight of the hint pull, e.g. 0.1
        huber_delta_px: pixel threshold for Huber loss

    Returns:
        (refined_ypr, rms_pixel_residual)
    """
    cam_pix = observations.pixels.get(cam_name, {})
    obs_list: List[Tuple[str, PixelObservation, Tuple[float, float, float]]] = []
    for lm_name, pix_obs in cam_pix.items():
        if lm_name in landmarks:
            obs_list.append((lm_name, pix_obs, landmarks[lm_name].xyz))

    if len(obs_list) < 2:
        # Can't constrain ypr with < 2 LMs; return initial guess
        return initial_ypr, float("inf")

    def residuals(params):
        ypr = (float(params[0]), float(params[1]), float(params[2]))
        cam = Camera(
            xyz=leak_cam.xyz, ypr=ypr,
            hfov=leak_cam.fov, image_size=leak_cam.image_size,
        )
        out = []
        for _, pix_obs, lm_xyz in obs_list:
            projected = project(lm_xyz, cam)
            if projected is None:
                out.extend([1e3 * pix_obs.confidence, 1e3 * pix_obs.confidence])
            else:
                out.append((projected[0] - pix_obs.pixel[0]) * pix_obs.confidence)
                out.append((projected[1] - pix_obs.pixel[1]) * pix_obs.confidence)
        # Hint soft pull
        if hint_ypr is not None and hint_weight > 0:
            yaw_delta = ((ypr[0] - hint_ypr[0] + 180) % 360) - 180
            out.append(hint_weight * yaw_delta)
            out.append(hint_weight * (ypr[1] - hint_ypr[1]))
            out.append(hint_weight * (ypr[2] - hint_ypr[2]))
        return np.asarray(out)

    result = least_squares(
        residuals, np.array(initial_ypr, dtype=float),
        method="trf", loss="huber", f_scale=huber_delta_px,
        max_nfev=200 * 3,
    )
    ypr_out = (float(result.x[0]) % 360.0, float(result.x[1]), float(result.x[2]))
    final_res = residuals(np.array(ypr_out))
    n_px = 2 * len(obs_list)
    pixel_res = final_res[:n_px]
    rms_px = float(np.sqrt(np.mean(pixel_res ** 2))) if n_px > 0 else 0.0
    return ypr_out, rms_px


def calibrate_non_leak_cam(
    cam_name: str,
    meta: NonLeakCamMeta,
    landmarks: Dict[str, SolvedLandmark],
    observations: Observations,
    initial_xyz: Optional[Tuple[float, float, float]] = None,
    initial_ypr: Optional[Tuple[float, float, float]] = None,
    initial_fov: float = 60.0,
    huber_delta_px: float = 5.0,
) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float], float, float]]:
    """Refine a non-leak cam's full 7 dof (xyz, ypr, fov).

    Requires at least 4 visible landmarks for a well-posed PnP.

    Returns:
        (xyz, ypr, fov, rms_pixel_residual) on success, None if too few obs.
    """
    cam_pix = observations.pixels.get(cam_name, {})
    obs_list: List[Tuple[str, PixelObservation, Tuple[float, float, float]]] = []
    for lm_name, pix_obs in cam_pix.items():
        if lm_name in landmarks:
            obs_list.append((lm_name, pix_obs, landmarks[lm_name].xyz))

    if len(obs_list) < 4:
        return None

    # Initial guess
    if initial_xyz is None:
        # Centroid of visible LMs, shifted backward (away from them)
        lm_arr = np.array([lm_xyz for _, _, lm_xyz in obs_list])
        centroid = lm_arr.mean(axis=0)
        initial_xyz = (float(centroid[0]), float(centroid[1] - 100.0), float(centroid[2] + 30.0))
    if initial_ypr is None:
        # Point cam at centroid
        lm_arr = np.array([lm_xyz for _, _, lm_xyz in obs_list])
        centroid = lm_arr.mean(axis=0)
        dx = centroid[0] - initial_xyz[0]
        dy = centroid[1] - initial_xyz[1]
        # yaw: in our convention, yaw=0 looks +y. yaw=90 looks -x.
        # Cam-local +y is rotated by yaw around +z. We want it pointed
        # at (dx, dy). The angle from +y to (dx, dy) is atan2(-dx, dy).
        yaw = float(np.degrees(np.arctan2(-dx, dy))) % 360.0
        initial_ypr = (yaw, 0.0, 0.0)

    def residuals(params):
        xyz = (float(params[0]), float(params[1]), float(params[2]))
        ypr = (float(params[3]), float(params[4]), float(params[5]))
        fov = float(params[6])
        if fov <= 5.0 or fov >= 175.0:
            # Out-of-bounds fov: large penalty
            return np.full(2 * len(obs_list), 1e4)
        cam = Camera(xyz=xyz, ypr=ypr, hfov=fov, image_size=meta.image_size)
        out = []
        for _, pix_obs, lm_xyz in obs_list:
            projected = project(lm_xyz, cam)
            if projected is None:
                out.extend([1e3 * pix_obs.confidence, 1e3 * pix_obs.confidence])
            else:
                out.append((projected[0] - pix_obs.pixel[0]) * pix_obs.confidence)
                out.append((projected[1] - pix_obs.pixel[1]) * pix_obs.confidence)
        return np.asarray(out)

    params0 = np.array(
        list(initial_xyz) + list(initial_ypr) + [initial_fov], dtype=float,
    )
    result = least_squares(
        residuals, params0,
        method="trf", loss="huber", f_scale=huber_delta_px,
        max_nfev=200 * 7,
    )
    xyz_out = (float(result.x[0]), float(result.x[1]), float(result.x[2]))
    ypr_out = (float(result.x[3]) % 360.0, float(result.x[4]), float(result.x[5]))
    fov_out = float(result.x[6])
    final_res = residuals(result.x)
    rms_px = float(np.sqrt(np.mean(final_res ** 2))) if len(final_res) > 0 else 0.0
    return xyz_out, ypr_out, fov_out, rms_px

