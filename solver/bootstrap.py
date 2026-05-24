"""
Bootstrap: produce a first State from observations + measurements,
without depending on any prior solver output.

The bootstrap is the chicken-and-egg breaker: we have no calibrated cams
and no known LM positions, but we have:
  - Leak cam xyz + fov (ground truth from GTA console)
  - Pixel markings (from humans)
  - Horizons drawn on some leak cam images (z=0 visual constraint)
  - Bootstrap hints (rough ypr estimates from humans for cams without horizon)
  - Z constraints (known z for some LMs, like sea level)

Algorithm (matches SOLVER_DESIGN.md section 6):

  1. For each leak cam, derive an initial ypr:
     - If a horizon is available, compute pitch + roll from it.
       Yaw still needs a hint (you can derive it from horizon only if you
       also know the cam's compass direction, which we don't).
     - Otherwise, use the bootstrap_hint.
     - Otherwise, error.

  2. Identify the anchor LM set: LMs visible to 2+ leak cams.

  3. For each anchor LM, rough-triangulate xyz from the first pair of cams.

  4. Joint refinement: nonlinear least-squares over all ypr + all anchor xyz,
     using all pixel observations as residuals. Levenberg-Marquardt with
     scipy.optimize.least_squares.

  5. Apply z_constraints: snap z for any anchor LM whose z is constrained.

The result is a State with:
  - All leak cams calibrated (xyz/fov from measurements, ypr from bootstrap)
  - All anchor LMs positioned (refined xyz)
  - Non-leak cams left empty (they get an initial PnP guess later)
"""

from __future__ import annotations

import datetime
import math
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import least_squares

from .geometry import (
    Camera,
    angular_residual_arcmin,
    project,
    ray_from_pixel,
    rotation_from_ypr,
    triangulate_pair,
    vfov_from_hfov,
)
from .io import (
    BootstrapHint,
    HorizonObservation,
    LeakCamMeasurement,
    Measurements,
    Observations,
    SolvedCamera,
    SolvedLandmark,
    State,
    ZConstraint,
)


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------

class BootstrapError(Exception):
    """Raised when bootstrap cannot complete due to insufficient inputs."""


# ----------------------------------------------------------------------
# Step 1: initial ypr per leak cam
# ----------------------------------------------------------------------

def _ypr_from_horizon(
    horizon: HorizonObservation, cam_xyz: Tuple[float, float, float],
    fov: float, image_size: Tuple[int, int],
) -> Tuple[float, float]:
    """Derive (pitch, roll) from a horizon line drawn on the image.

    The horizon is the line where z = 0 meets the image plane. Its
    vertical position tells us pitch; its slope tells us roll.

    Returns:
        (pitch_deg, roll_deg).

    Notes on the geometry:
      For a cam at altitude h looking at the horizon, the horizon
      appears at an apparent pitch of -arctan(h / d) where d is the
      distance to the horizon. For d >> h, this is ~0, so we can ignore
      Earth's curvature within Vice City.

      At yaw=0, pitch=0, roll=0, a flat horizon at world z=0 lands
      exactly on the image's vertical center (y = h/2 - 0.5).

      Pitch shifts the horizon up or down:
        py_horizon = (h/2 - 0.5) - (h/2) * tan(pitch) / tan(vfov/2)

      Roll tilts it.

    We use the midpoint of the horizon line for pitch and the line's
    angle for roll. Both are exact under a pinhole model with no curvature.
    """
    w, h = image_size
    vfov = vfov_from_hfov(fov, image_size)

    left = np.asarray(horizon.left_pixel, dtype=float)
    right = np.asarray(horizon.right_pixel, dtype=float)

    # Roll: angle of the horizon line in image space.
    # Positive image dy means line tilts down to the right. World up is +z.
    # Roll is positive when cam rotates clockwise around its forward axis.
    dx = right[0] - left[0]
    dy = right[1] - left[1]
    # Slope angle in image; positive if right end is lower than left end.
    image_tilt = math.degrees(math.atan2(dy, dx))
    # The roll that produces this tilt: a positive image tilt means the
    # right side is lower, which corresponds to a clockwise rotation of
    # the cam looking forward, which is positive roll in our convention.
    roll = image_tilt

    # Pitch: vertical position of horizon midpoint vs image center.
    # Use the midpoint of the segment.
    mid_y = 0.5 * (left[1] + right[1])
    center_y = h / 2.0 - 0.5
    # The "image y offset" of the horizon from center, as a fraction
    # of half-height, equals -tan(pitch)/tan(vfov/2) in our pinhole.
    # (Pitch up = horizon moves down in image = py > center_y = positive offset.)
    # Wait, let's be careful: when pitch is positive (cam looks up), the
    # horizon goes DOWN in the image (toward larger py).
    # Our formula: py = h/2-0.5 - (h/2) * ndc_y_horizon
    # where ndc_y_horizon = -tan(pitch) / tan(vfov/2) when looking at z=0
    # at infinite distance. So:
    #   mid_y = h/2 - 0.5 - (h/2) * (-tan(pitch) / tan(vfov/2))
    #         = (h/2 - 0.5) + (h/2) * tan(pitch) / tan(vfov/2)
    # Solving for pitch:
    offset_ratio = (mid_y - center_y) / (h / 2.0)  # in [-1, 1] for in-frame
    tan_pitch = offset_ratio * math.tan(math.radians(vfov) / 2)
    pitch = math.degrees(math.atan(tan_pitch))

    return pitch, roll


def _initial_ypr_for_cam(
    cam_name: str,
    leak_cam: LeakCamMeasurement,
    horizons: Dict[str, HorizonObservation],
    hints: Dict[str, BootstrapHint],
) -> Tuple[float, float, float]:
    """Get initial (yaw, pitch, roll) for a leak cam.

    Priority:
      1. If a hint exists, use it as the full ypr (overrides horizon).
         Hints are a human override and take precedence.
      2. If a horizon exists, derive pitch + roll from it; raise an error
         because yaw cannot be derived from a horizon alone.
      3. Otherwise, raise BootstrapError.

    The yaw-from-horizon problem: without knowing which way is north in
    the image, we can't get yaw from a horizon. We could try to detect
    landmarks, but that's circular. So yaw always needs a hint.
    """
    if cam_name in hints:
        h = hints[cam_name]
        return (h.yaw, h.pitch, h.roll)

    if cam_name in horizons:
        raise BootstrapError(
            f"Cam '{cam_name}' has a horizon but no bootstrap_hint for yaw. "
            f"Add a bootstrap_hint with at least a yaw estimate."
        )

    raise BootstrapError(
        f"Cam '{cam_name}' has no horizon and no bootstrap_hint. "
        f"Add one to observations/horizons.json or measurements/bootstrap_hints.json."
    )


# ----------------------------------------------------------------------
# Step 2: anchor LMs
# ----------------------------------------------------------------------

def _find_anchor_lms(
    observations: Observations, measurements: Measurements,
) -> List[str]:
    """LMs visible to 2+ leak cams. These anchor the joint refinement."""
    leak_cam_names = set(measurements.leak_cams.keys())
    counts: Dict[str, int] = {}
    for cam_name, lm_map in observations.pixels.items():
        if cam_name not in leak_cam_names:
            continue
        for lm_name in lm_map:
            counts[lm_name] = counts.get(lm_name, 0) + 1
    return sorted([name for name, c in counts.items() if c >= 2])


# ----------------------------------------------------------------------
# Step 3: rough triangulation per anchor LM
# ----------------------------------------------------------------------

def _rough_triangulate_lm(
    lm_name: str,
    observations: Observations,
    leak_cams: Dict[str, LeakCamMeasurement],
    cam_ypr: Dict[str, Tuple[float, float, float]],
) -> Optional[Tuple[float, float, float]]:
    """Pick two leak cams that see lm_name, triangulate their rays, return xyz.

    Returns None if no valid pair is found.
    """
    observers = []
    for cam_name in leak_cams:
        if lm_name in observations.pixels.get(cam_name, {}):
            observers.append(cam_name)
    if len(observers) < 2:
        return None

    # Build Camera objects for each observer
    cams = {
        name: Camera(
            xyz=leak_cams[name].xyz,
            ypr=cam_ypr[name],
            hfov=leak_cams[name].fov,
            image_size=leak_cams[name].image_size,
        )
        for name in observers
    }

    # Try all pairs, pick the one with the largest angle between the two
    # rays (best parallax = most stable triangulation).
    # Among valid candidates, prefer largest angle to avoid near-parallel
    # rays that would place the LM anywhere along the rays.
    from .geometry import ray_from_pixel
    best_xyz = None
    best_angle = -1.0
    for i in range(len(observers)):
        for j in range(i + 1, len(observers)):
            a, b = observers[i], observers[j]
            try:
                _, dir_a = ray_from_pixel(observations.pixels[a][lm_name].pixel, cams[a])
                _, dir_b = ray_from_pixel(observations.pixels[b][lm_name].pixel, cams[b])
                cos_angle = float(np.dot(dir_a, dir_b))
                cos_angle = max(-1.0, min(1.0, cos_angle))
                angle = float(np.arccos(cos_angle))  # radians, in [0, pi]
                # Effective parallax = min(angle, pi - angle) so we treat
                # nearly-parallel and nearly-antiparallel the same way.
                # Actually we want angle close to 90deg, so:
                effective = abs(angle - np.pi/2)
                # We want SMALL effective (close to 90deg). So flip:
                # Score = pi/2 - effective = angle if <pi/2, else pi-angle
                score = min(angle, np.pi - angle)
                if score < 0.05:  # less than ~3deg parallax, skip
                    continue
                xyz, _ = triangulate_pair(
                    cams[a], observations.pixels[a][lm_name].pixel,
                    cams[b], observations.pixels[b][lm_name].pixel,
                )
                # Sanity check: the LM should be in front of both cams
                # (project should not return None)
                from .geometry import project
                if project(tuple(xyz), cams[a]) is None: continue
                if project(tuple(xyz), cams[b]) is None: continue
                if score > best_angle:
                    best_angle = score
                    best_xyz = tuple(float(v) for v in xyz)
            except ValueError:
                continue

    return best_xyz


# ----------------------------------------------------------------------
# Step 4: joint refinement
# ----------------------------------------------------------------------

def _joint_refine(
    cam_ypr_init: Dict[str, Tuple[float, float, float]],
    lm_xyz_init: Dict[str, Tuple[float, float, float]],
    observations: Observations,
    measurements: Measurements,
    hint_weight: float = 0.1,
    max_iter: int = 200,
    freeze_cams: bool = False,
) -> Tuple[
    Dict[str, Tuple[float, float, float]],
    Dict[str, Tuple[float, float, float]],
    Dict[str, float],  # diagnostics
]:
    """Run Levenberg-Marquardt joint optimization on all leak cam ypr +
    all anchor LM xyz simultaneously.

    Residuals (each squared in the loss):
      - For each (cam, lm) pixel observation:
          (projected_x - marked_x) * confidence, (projected_y - marked_y) * confidence
      - For each cam with a hint, a soft pull toward the hint's ypr:
          (yaw - hint_yaw) * hint_weight, (pitch - hint_pitch) * hint_weight, etc.

    The hint pull keeps the optimizer from running off into a local minimum,
    while still allowing it to refine the ypr by several degrees if needed.
    """
    leak_cams = measurements.leak_cams
    hints = measurements.bootstrap_hints

    cam_names = sorted(cam_ypr_init.keys())
    lm_names = sorted(lm_xyz_init.keys())

    n_cams = len(cam_names)
    n_lms = len(lm_names)

    # Pack initial parameters
    if freeze_cams:
        # Only LM xyz are free
        params0 = np.zeros(3 * n_lms, dtype=float)
        for j, name in enumerate(lm_names):
            params0[3 * j:3 * j + 3] = lm_xyz_init[name]
    else:
        params0 = np.zeros(3 * n_cams + 3 * n_lms, dtype=float)
        for i, name in enumerate(cam_names):
            params0[3 * i:3 * i + 3] = cam_ypr_init[name]
        for j, name in enumerate(lm_names):
            params0[3 * n_cams + 3 * j:3 * n_cams + 3 * j + 3] = lm_xyz_init[name]

    cam_idx = {name: i for i, name in enumerate(cam_names)}
    lm_idx = {name: j for j, name in enumerate(lm_names)}

    # Pre-compute the observation list: (cam_name, lm_name, pixel_xy, confidence)
    obs_list = []
    for cam_name in cam_names:
        if cam_name not in leak_cams:
            continue
        cam_pix = observations.pixels.get(cam_name, {})
        for lm_name in lm_names:
            if lm_name in cam_pix:
                obs = cam_pix[lm_name]
                obs_list.append((cam_name, lm_name, obs.pixel, obs.confidence))

    # Pre-compute hint pulls
    hint_pulls = []
    for cam_name in cam_names:
        if cam_name in hints:
            h = hints[cam_name]
            hint_pulls.append((cam_name, (h.yaw, h.pitch, h.roll), h.confidence))

    def residuals(params):
        out = []
        # Project each observation
        for cam_name, lm_name, pix, conf in obs_list:
            j = lm_idx[lm_name]
            if freeze_cams:
                ypr = cam_ypr_init[cam_name]
                xyz = tuple(params[3 * j:3 * j + 3])
            else:
                i = cam_idx[cam_name]
                ypr = tuple(params[3 * i:3 * i + 3])
                xyz = tuple(params[3 * n_cams + 3 * j:3 * n_cams + 3 * j + 3])
            cam = Camera(
                xyz=leak_cams[cam_name].xyz,
                ypr=ypr,
                hfov=leak_cams[cam_name].fov,
                image_size=leak_cams[cam_name].image_size,
            )
            projected = project(xyz, cam)
            if projected is None:
                # Point is behind the cam. Push the optimizer back by adding
                # a large residual. The magnitude is chosen to be much
                # larger than any plausible pixel error.
                out.extend([1e4 * conf, 1e4 * conf])
            else:
                out.append((projected[0] - pix[0]) * conf)
                out.append((projected[1] - pix[1]) * conf)

        # Soft hint pulls (skipped if cams are frozen)
        if freeze_cams:
            hint_pulls_iter = []
        else:
            hint_pulls_iter = hint_pulls
        for cam_name, hint_ypr, hint_conf in hint_pulls_iter:
            i = cam_idx[cam_name]
            ypr_cur = params[3 * i:3 * i + 3]
            weight = hint_weight * hint_conf
            # Use angular delta for yaw to handle 0/360 wraparound
            yaw_delta = ((ypr_cur[0] - hint_ypr[0] + 180) % 360) - 180
            out.append(weight * yaw_delta)
            out.append(weight * (ypr_cur[1] - hint_ypr[1]))
            out.append(weight * (ypr_cur[2] - hint_ypr[2]))

        return np.asarray(out)

    result = least_squares(
        residuals, params0,
        method="trf",
        loss="huber",
        f_scale=10.0,
        max_nfev=max_iter * len(params0),
    )

    # Unpack
    cam_ypr_out: Dict[str, Tuple[float, float, float]] = {}
    lm_xyz_out: Dict[str, Tuple[float, float, float]] = {}
    if freeze_cams:
        # Cams unchanged
        for name in cam_names:
            cam_ypr_out[name] = cam_ypr_init[name]
        for j, name in enumerate(lm_names):
            xyz = tuple(float(v) for v in result.x[3 * j:3 * j + 3])
            lm_xyz_out[name] = xyz
    else:
        for name in cam_names:
            i = cam_idx[name]
            ypr = tuple(float(v) for v in result.x[3 * i:3 * i + 3])
            ypr = (ypr[0] % 360.0, ypr[1], ypr[2])
            cam_ypr_out[name] = ypr
        for j, name in enumerate(lm_names):
            xyz = tuple(
                float(v) for v in result.x[3 * n_cams + 3 * j:3 * n_cams + 3 * j + 3]
            )
            lm_xyz_out[name] = xyz

    # Diagnostics
    n_obs = len(obs_list)
    final_loss = float(np.sum(result.fun ** 2))
    pixel_residuals = result.fun[:2 * n_obs]
    rms_px = float(np.sqrt(np.mean(pixel_residuals ** 2))) if n_obs > 0 else 0.0
    diagnostics = {
        "iterations": int(result.nfev),
        "final_loss": final_loss,
        "rms_pixel_residual": rms_px,
        "n_observations": n_obs,
        "n_cameras": n_cams,
        "n_landmarks": n_lms,
        "success": bool(result.success),
    }
    return cam_ypr_out, lm_xyz_out, diagnostics


# ----------------------------------------------------------------------
# Step 5: z_constraint snapping
# ----------------------------------------------------------------------

def _apply_z_constraints(
    lm_xyz: Dict[str, Tuple[float, float, float]],
    z_constraints: Dict[str, ZConstraint],
) -> Dict[str, Tuple[float, float, float]]:
    """For each LM with a z_constraint, override z while keeping x, y."""
    out = dict(lm_xyz)
    for name, c in z_constraints.items():
        if name in out:
            x, y, _ = out[name]
            out[name] = (x, y, c.z)
    return out


# ----------------------------------------------------------------------
# Top-level entry point
# ----------------------------------------------------------------------

def bootstrap(
    observations: Observations, measurements: Measurements,
    solver_version: str = "0.4.0-bootstrap",
) -> Tuple[State, Dict[str, float]]:
    """Produce a first State from observations + measurements.

    Returns:
        (state, diagnostics) where state.cameras has the leak cams and
        state.landmarks has the anchor LMs, and diagnostics is a dict
        with iteration count, residual norms, etc.

    Raises:
        BootstrapError on any of the failure modes from section 6.4.
    """
    leak_cams = measurements.leak_cams
    if len(leak_cams) < 2:
        raise BootstrapError(
            f"Need at least 2 leak cams, got {len(leak_cams)}."
        )

    # Step 1: initial ypr per leak cam
    cam_ypr_init: Dict[str, Tuple[float, float, float]] = {}
    for name, lc in leak_cams.items():
        cam_ypr_init[name] = _initial_ypr_for_cam(
            name, lc, observations.horizons, measurements.bootstrap_hints,
        )

    # Step 2: anchor LMs
    anchor_lms = _find_anchor_lms(observations, measurements)
    if len(anchor_lms) < 3:
        raise BootstrapError(
            f"Found {len(anchor_lms)} anchor LMs (LMs visible to 2+ leak cams). "
            f"Need at least 3 for a well-posed bootstrap."
        )

    # Step 3: rough triangulation
    lm_xyz_init: Dict[str, Tuple[float, float, float]] = {}
    failed_lms: List[str] = []
    for lm_name in anchor_lms:
        xyz = _rough_triangulate_lm(
            lm_name, observations, leak_cams, cam_ypr_init,
        )
        if xyz is None:
            failed_lms.append(lm_name)
        else:
            lm_xyz_init[lm_name] = xyz

    if len(lm_xyz_init) < 3:
        raise BootstrapError(
            f"Could only rough-triangulate {len(lm_xyz_init)} anchor LMs. "
            f"Failed for: {failed_lms[:5]}. Check that initial ypr "
            f"(from hints) is approximately correct."
        )

    # Step 4: joint refinement
    cam_ypr_final, lm_xyz_final, diagnostics = _joint_refine(
        cam_ypr_init, lm_xyz_init, observations, measurements,
    )

    # Step 5: z_constraints
    lm_xyz_final = _apply_z_constraints(lm_xyz_final, measurements.z_constraints)

    # Build State
    cameras: Dict[str, SolvedCamera] = {}
    for name, ypr in cam_ypr_final.items():
        lc = leak_cams[name]
        # Count constraints (LMs visible from this cam)
        n_constraints = sum(
            1 for lm in lm_xyz_final
            if lm in observations.pixels.get(name, {})
        )
        # Compute per-cam loss in arcmin
        cam_obj = Camera(xyz=lc.xyz, ypr=ypr, hfov=lc.fov, image_size=lc.image_size)
        residuals = []
        for lm_name, xyz in lm_xyz_final.items():
            pix_obs = observations.pixels.get(name, {}).get(lm_name)
            if pix_obs is not None:
                residuals.append(
                    angular_residual_arcmin(cam_obj, pix_obs.pixel, xyz)
                )
        loss_arcmin = (
            float(np.sqrt(np.mean(np.array(residuals) ** 2)))
            if residuals else None
        )
        cameras[name] = SolvedCamera(
            kind="leak",
            xyz=lc.xyz,
            ypr=ypr,
            fov=lc.fov,
            loss_arcmin=loss_arcmin,
            n_constraints=n_constraints,
        )

    landmarks: Dict[str, SolvedLandmark] = {}
    for name, xyz in lm_xyz_final.items():
        n_observers = sum(
            1 for cam in cam_ypr_final
            if name in observations.pixels.get(cam, {})
        )
        landmarks[name] = SolvedLandmark(
            kind="pixel_anchored",
            xyz=xyz,
            n_observers=n_observers,
        )

    state = State(
        solver_version=solver_version,
        solved_at=datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
        input_hash="",  # filled by solve.py at the top level
        cameras=cameras,
        landmarks=landmarks,
    )

    return state, diagnostics

