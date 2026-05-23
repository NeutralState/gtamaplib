"""
Multi-camera landmark triangulation.

Given a set of calibrated cameras and pixel observations for one LM,
refine the LM's xyz to minimize the sum of squared angular residuals
across all observers.

Handles z_constraints by reducing the optimization to 2 degrees of
freedom (x, y) and snapping z afterward.
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
    Observations,
    PixelObservation,
    ZConstraint,
)


def triangulate_landmark(
    lm_name: str,
    cameras: Dict[str, Camera],
    observations: Observations,
    z_constraint: Optional[ZConstraint] = None,
    initial_xyz: Optional[Tuple[float, float, float]] = None,
    huber_delta_px: float = 5.0,
) -> Optional[Tuple[Tuple[float, float, float], float]]:
    """Refine the xyz of one landmark given calibrated cameras and pixel obs.

    Args:
        lm_name: name of the landmark
        cameras: {cam_name: Camera} for all cams that see this LM
        observations: pixel observations
        z_constraint: optional ZConstraint to enforce
        initial_xyz: starting xyz (if None, derive from any pair of cams)
        huber_delta_px: pixel threshold for Huber robust loss. Residuals
            below this are quadratic, above are linear. Reduces outlier impact.

    Returns:
        ((x, y, z), rms_pixel_residual) on success, or None if too few observers.
    """
    # Collect observers
    observers: List[Tuple[str, PixelObservation]] = []
    for cam_name, cam in cameras.items():
        cam_pix = observations.pixels.get(cam_name, {})
        if lm_name in cam_pix:
            observers.append((cam_name, cam_pix[lm_name]))

    if len(observers) < 2:
        return None

    # Get initial xyz: from input, or from any valid pair
    if initial_xyz is None:
        for i in range(len(observers)):
            for j in range(i + 1, len(observers)):
                name_a, obs_a = observers[i]
                name_b, obs_b = observers[j]
                try:
                    xyz, _ = triangulate_pair(
                        cameras[name_a], obs_a.pixel,
                        cameras[name_b], obs_b.pixel,
                    )
                    initial_xyz = tuple(float(v) for v in xyz)
                    break
                except ValueError:
                    continue
            if initial_xyz is not None:
                break
        if initial_xyz is None:
            return None

    # Build residuals function
    has_z = z_constraint is not None
    z_fixed = z_constraint.z if has_z else None

    def residuals(params):
        if has_z:
            xyz = (float(params[0]), float(params[1]), z_fixed)
        else:
            xyz = (float(params[0]), float(params[1]), float(params[2]))
        out = []
        for cam_name, pix_obs in observers:
            cam = cameras[cam_name]
            projected = project(xyz, cam)
            if projected is None:
                # Behind cam: large penalty proportional to confidence
                out.extend([1e3 * pix_obs.confidence, 1e3 * pix_obs.confidence])
            else:
                dx = (projected[0] - pix_obs.pixel[0]) * pix_obs.confidence
                dy = (projected[1] - pix_obs.pixel[1]) * pix_obs.confidence
                out.append(dx)
                out.append(dy)
        return np.asarray(out)

    if has_z:
        params0 = np.array(initial_xyz[:2], dtype=float)
    else:
        params0 = np.array(initial_xyz, dtype=float)

    result = least_squares(
        residuals, params0,
        method="trf",  # trf supports loss='huber'
        loss="huber",
        f_scale=huber_delta_px,
        max_nfev=200 * len(params0),
    )

    if has_z:
        xyz_out = (float(result.x[0]), float(result.x[1]), float(z_fixed))
    else:
        xyz_out = (float(result.x[0]), float(result.x[1]), float(result.x[2]))

    # RMS pixel residual (before huber weighting)
    final_res = residuals(result.x)
    rms_px = float(np.sqrt(np.mean(final_res ** 2))) if len(final_res) > 0 else 0.0

    return xyz_out, rms_px

