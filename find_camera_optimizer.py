"""
Patch pour gtamaplib.py — refinement scipy après le grid search de find_camera.
Requiert: scipy (pip install scipy)
"""

import numpy as np
from scipy.optimize import minimize


def compute_loss(cam, targets, n_points):
    from gtamaplib import intersect_ray_and_point, intersect_ray_and_ray
    n_targets = len(targets)
    loss = 0.0
    for i, (lm_name, target) in enumerate(targets):
        fn = intersect_ray_and_point if i < n_points else intersect_ray_and_ray
        cam_ray = (cam.xyz, cam.get_landmark_direction(lm_name))
        angle = fn(cam_ray, target)[-1]
        loss += (angle * 60) ** 2
    return loss / n_targets


def refine_camera(cam, targets, n_points, z_limits=None, pitch_bounds=None, hfov_bounds=None):
    """
    Affine x, y, z, yaw, pitch, hfov via Nelder-Mead.
    Yaw est libre (pas de recalibration analytique) pour éviter les instabilités.
    """
    x0 = np.array([cam.x, cam.y, cam.z, cam.yaw, cam.pitch, cam.hfov])
    PENALTY = 1e6

    def objective(params):
        x, y, z, yaw, pitch, hfov = params
        penalty = 0.0
        if z_limits:
            if z < z_limits[0]: penalty += PENALTY * (z_limits[0] - z) ** 2
            if z > z_limits[1]: penalty += PENALTY * (z - z_limits[1]) ** 2
        if pitch_bounds:
            if pitch < pitch_bounds[0]: penalty += PENALTY * (pitch_bounds[0] - pitch) ** 2
            if pitch > pitch_bounds[1]: penalty += PENALTY * (pitch - pitch_bounds[1]) ** 2
        if hfov_bounds:
            if hfov < hfov_bounds[0]: penalty += PENALTY * (hfov_bounds[0] - hfov) ** 2
            if hfov > hfov_bounds[1]: penalty += PENALTY * (hfov - hfov_bounds[1]) ** 2
        cam.set_xyz((x, y, z))
        cam.set_ypr((yaw, pitch, cam.roll))
        cam.set_fov((hfov, None))
        cam.clear_landmark_directions()
        return compute_loss(cam, targets, n_points) + penalty

    result = minimize(
        objective, x0,
        method="Nelder-Mead",
        options={"xatol": 1e-6, "fatol": 1e-8, "maxiter": 10_000, "adaptive": True}
    )
    objective(result.x)
    return cam, result.fun


def find_camera_with_refinement(
    cam_name, lm_names, rays,
    line, radius, step,
    z_limits, pitch_range, hfov_range,
    map_name, map_scale, map_area,
    projection_area, basename,
    bearing_limits=None, ray_pairs=None, max_size_delta=1.05,
    refine=True
):
    import gtamaplib as ml
    import gtamapdata as md

    cam, grid_loss = ml.find_camera(
        cam_name, lm_names, rays,
        line, radius, step,
        z_limits, pitch_range, hfov_range,
        map_name, map_scale, map_area,
        projection_area, basename,
        bearing_limits, ray_pairs, max_size_delta
    )

    if not refine:
        return cam, grid_loss

    print(f"\n{'='*60}")
    print(f"Grid search loss : {grid_loss:.6f} arcmin²")
    print(f"Démarrage refinement scipy (Nelder-Mead)...")

    targets = [
        (lm_name, md.landmarks[lm_name] if lm_name in md.landmarks else ml.get_camera(lm_name).xyz)
        for lm_name in lm_names
    ]
    for other_cam_name, lm_name in rays:
        other_cam = ml.get_camera(other_cam_name)
        targets.append((lm_name, (other_cam.xyz, other_cam.get_landmark_direction(lm_name))))
    n_points = len(lm_names)

    pitch_bounds = (pitch_range[0], pitch_range[1]) if pitch_range else None
    hfov_bounds  = (hfov_range[0],  hfov_range[1])  if hfov_range  else None

    cam, refined_loss = refine_camera(
        cam, targets, n_points,
        z_limits=z_limits,
        pitch_bounds=pitch_bounds,
        hfov_bounds=hfov_bounds
    )

    improvement = (grid_loss - refined_loss) / grid_loss * 100
    print(f"Refined loss     : {refined_loss:.6f} arcmin²")
    print(f"Amélioration     : {improvement:.1f}%")
    print(f"Caméra finale    : {cam}")
    print(f"{'='*60}\n")

    cam.register()
    ml.get_camera.cache_clear()
    return cam, refined_loss
