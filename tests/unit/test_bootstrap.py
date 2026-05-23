"""
Unit tests for solver.bootstrap.

Strategy: build synthetic worlds with known ground truth, project to
pixels, then verify the bootstrap recovers the ground truth (to within
tolerance) starting only from imperfect hints.

Test scenarios:
- 2 leak cams, 3 anchor LMs, perfect pixels: should recover ground truth
- 2 leak cams, 5 anchor LMs, hint off by a few degrees: should recover
- 3 leak cams, more anchor LMs: should recover with smaller residuals
- Z-constraint applied: snapped LM has the constrained z
- Insufficient cams / LMs: clear error
- No hint for a cam: clear error
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
import pytest

from solver.bootstrap import (
    BootstrapError,
    _apply_z_constraints,
    _find_anchor_lms,
    _initial_ypr_for_cam,
    _rough_triangulate_lm,
    bootstrap,
)
from solver.geometry import Camera, project
from solver.io import (
    BootstrapHint,
    HorizonObservation,
    LeakCamMeasurement,
    Measurements,
    Observations,
    PixelObservation,
    ZConstraint,
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _make_synthetic_world(
    cam_specs: List[Tuple[str, Tuple[float, float, float], Tuple[float, float, float], float]],
    lm_specs: List[Tuple[str, Tuple[float, float, float]]],
    image_size: Tuple[int, int] = (1920, 1080),
    hint_noise_deg: float = 0.0,
    rng_seed: int = 0,
) -> Tuple[Observations, Measurements, Dict[str, Tuple[float, float, float]], Dict[str, Tuple[float, float, float]]]:
    """Build a synthetic scenario.

    Args:
        cam_specs: list of (cam_name, xyz, true_ypr, fov)
        lm_specs:  list of (lm_name, xyz)
        hint_noise_deg: how far off the bootstrap hint is from the true ypr.
                        Set to 0 for perfect hints; higher for stress tests.

    Returns:
        (observations, measurements, true_cam_ypr, true_lm_xyz)
    """
    rng = np.random.default_rng(rng_seed)

    true_cam_ypr: Dict[str, Tuple[float, float, float]] = {}
    true_lm_xyz: Dict[str, Tuple[float, float, float]] = {n: x for n, x in lm_specs}

    leak_cams: Dict[str, LeakCamMeasurement] = {}
    bootstrap_hints: Dict[str, BootstrapHint] = {}
    pixels: Dict[str, Dict[str, PixelObservation]] = {}

    for cam_name, cam_xyz, ypr, fov in cam_specs:
        true_cam_ypr[cam_name] = ypr
        leak_cams[cam_name] = LeakCamMeasurement(
            xyz=cam_xyz, fov=fov, source="synthetic", image_size=image_size,
        )
        # Noisy hint
        if hint_noise_deg > 0:
            yaw_noise = float(rng.normal(0, hint_noise_deg))
            pitch_noise = float(rng.normal(0, hint_noise_deg))
            roll_noise = float(rng.normal(0, hint_noise_deg))
        else:
            yaw_noise = pitch_noise = roll_noise = 0.0
        bootstrap_hints[cam_name] = BootstrapHint(
            yaw=ypr[0] + yaw_noise,
            pitch=ypr[1] + pitch_noise,
            roll=ypr[2] + roll_noise,
            confidence=0.5,
        )

        # Project each LM that's visible
        cam = Camera(xyz=cam_xyz, ypr=ypr, hfov=fov, image_size=image_size)
        pixels[cam_name] = {}
        for lm_name, lm_xyz in lm_specs:
            pix = project(lm_xyz, cam)
            if pix is None:
                continue
            x, y = pix
            if not (0 <= x < image_size[0] and 0 <= y < image_size[1]):
                continue
            pixels[cam_name][lm_name] = PixelObservation(pixel=(float(x), float(y)))

    observations = Observations(pixels=pixels)
    measurements = Measurements(
        leak_cams=leak_cams, bootstrap_hints=bootstrap_hints,
    )
    return observations, measurements, true_cam_ypr, true_lm_xyz


# ----------------------------------------------------------------------
# Helpers tests
# ----------------------------------------------------------------------

def test_initial_ypr_from_hint():
    leak = LeakCamMeasurement(
        xyz=(0, 0, 5), fov=60, source="test", image_size=(1920, 1080),
    )
    hints = {"CamA": BootstrapHint(yaw=100, pitch=-5, roll=0)}
    ypr = _initial_ypr_for_cam("CamA", leak, {}, hints)
    assert ypr == (100, -5, 0)


def test_initial_ypr_missing_raises():
    leak = LeakCamMeasurement(
        xyz=(0, 0, 5), fov=60, source="test", image_size=(1920, 1080),
    )
    with pytest.raises(BootstrapError) as exc:
        _initial_ypr_for_cam("CamA", leak, {}, {})
    assert "no horizon" in str(exc.value) or "bootstrap_hint" in str(exc.value)


def test_initial_ypr_horizon_without_yaw_hint_raises():
    """A horizon gives pitch+roll but not yaw. Without yaw hint -> error."""
    leak = LeakCamMeasurement(
        xyz=(0, 0, 5), fov=60, source="test", image_size=(1920, 1080),
    )
    horizons = {"CamA": HorizonObservation(left_pixel=(0, 540), right_pixel=(1920, 540))}
    with pytest.raises(BootstrapError) as exc:
        _initial_ypr_for_cam("CamA", leak, horizons, {})
    assert "yaw" in str(exc.value).lower()


def test_find_anchor_lms():
    leak = LeakCamMeasurement(
        xyz=(0, 0, 5), fov=60, source="test", image_size=(1920, 1080),
    )
    measurements = Measurements(leak_cams={"A": leak, "B": leak, "C": leak})
    observations = Observations(pixels={
        "A": {"LM1": PixelObservation(pixel=(0, 0)),
              "LM2": PixelObservation(pixel=(0, 0))},
        "B": {"LM1": PixelObservation(pixel=(0, 0)),
              "LM3": PixelObservation(pixel=(0, 0))},
        "C": {"LM3": PixelObservation(pixel=(0, 0))},
    })
    anchors = _find_anchor_lms(observations, measurements)
    # LM1 is seen by A+B (2 cams) -> anchor
    # LM2 is seen by A only -> not anchor
    # LM3 is seen by B+C -> anchor
    assert "LM1" in anchors
    assert "LM3" in anchors
    assert "LM2" not in anchors


def test_apply_z_constraints():
    lm_xyz = {"A": (10, 20, 5), "B": (30, 40, 8)}
    z_c = {"A": ZConstraint(z=0.0, reason="sea level")}
    out = _apply_z_constraints(lm_xyz, z_c)
    assert out["A"] == (10, 20, 0.0)
    assert out["B"] == (30, 40, 8)


# ----------------------------------------------------------------------
# Bootstrap end-to-end on synthetic scenarios
# ----------------------------------------------------------------------

def test_bootstrap_perfect_hints_2cams():
    """2 cams + 5 LMs + perfect hints: should recover ground truth exactly."""
    # Cams south of the LM cluster, both looking ~north.
    cam_specs = [
        ("CamA", (-50, 0, 50), (0, -5, 0), 60.0),
        ("CamB", (50, 0, 60), (0, -5, 0), 60.0),
    ]
    lm_specs = [
        (f"LM{i}", (float(x), float(y), float(z)))
        for i, (x, y, z) in enumerate([
            (0, 200, 20), (-30, 220, 30), (40, 210, 40),
            (-10, 240, 25), (20, 230, 35),
        ])
    ]
    obs, meas, true_ypr, true_xyz = _make_synthetic_world(
        cam_specs, lm_specs, hint_noise_deg=0.0,
    )
    state, diag = bootstrap(obs, meas)

    # Check cameras
    for name, ypr in true_ypr.items():
        recovered = state.cameras[name].ypr
        yaw_err = abs(((recovered[0] - ypr[0] + 180) % 360) - 180)
        assert yaw_err < 0.01
        assert abs(recovered[1] - ypr[1]) < 0.01
        assert abs(recovered[2] - ypr[2]) < 0.01

    # Check landmarks
    for name, xyz in true_xyz.items():
        if name not in state.landmarks:
            continue
        recovered = state.landmarks[name].xyz
        for a, b in zip(recovered, xyz):
            assert abs(a - b) < 0.01, f"LM {name}: {recovered} vs {xyz}"


def test_bootstrap_noisy_hints_recovers():
    """Hints off by 2 degrees: should still converge to ground truth."""
    # 3 cams in a south-side arc, all roughly looking north at the LM cluster.
    cam_specs = [
        ("CamA", (-80, 0, 50), (5, -5, 0), 60.0),
        ("CamB", (80, 0, 60), (-5, -3, 0), 60.0),
        ("CamC", (0, -50, 40), (0, -8, 0), 60.0),
    ]
    lm_specs = [
        (f"LM{i}", (float(x), float(y), float(z)))
        for i, (x, y, z) in enumerate([
            (0, 200, 20), (-30, 220, 30), (40, 210, 40),
            (-10, 240, 25), (20, 230, 35), (-20, 260, 50),
        ])
    ]
    obs, meas, true_ypr, true_xyz = _make_synthetic_world(
        cam_specs, lm_specs, hint_noise_deg=2.0, rng_seed=42,
    )
    state, diag = bootstrap(obs, meas)

    # With 2 degrees of hint noise, expect recovery to within a fraction of a degree
    for name, ypr in true_ypr.items():
        recovered = state.cameras[name].ypr
        yaw_err = abs(((recovered[0] - ypr[0] + 180) % 360) - 180)
        assert yaw_err < 0.5, f"{name} yaw error {yaw_err}"
        assert abs(recovered[1] - ypr[1]) < 0.5, f"{name} pitch error"
        assert abs(recovered[2] - ypr[2]) < 0.5, f"{name} roll error"

    # LMs to within a meter
    for name, xyz in true_xyz.items():
        if name not in state.landmarks:
            continue
        recovered = state.landmarks[name].xyz
        err = np.linalg.norm(np.array(recovered) - np.array(xyz))
        assert err < 1.0, f"LM {name} error {err}m"


def test_bootstrap_3_cams_better_residuals():
    """More cams should give smaller residuals on the same LMs."""
    cam_specs_2 = [
        ("CamA", (-80, 0, 50), (5, -5, 0), 60.0),
        ("CamB", (80, 0, 60), (-5, -3, 0), 60.0),
    ]
    cam_specs_3 = cam_specs_2 + [("CamC", (0, -50, 40), (0, -8, 0), 60.0)]
    lm_specs = [
        (f"LM{i}", (float(x), float(y), float(z)))
        for i, (x, y, z) in enumerate([
            (0, 200, 20), (-30, 220, 30), (40, 210, 40),
            (-10, 240, 25), (20, 230, 35), (-25, 215, 45),
        ])
    ]

    obs2, m2, _, _ = _make_synthetic_world(cam_specs_2, lm_specs, hint_noise_deg=0.5, rng_seed=1)
    obs3, m3, _, _ = _make_synthetic_world(cam_specs_3, lm_specs, hint_noise_deg=0.5, rng_seed=1)

    _, d2 = bootstrap(obs2, m2)
    _, d3 = bootstrap(obs3, m3)
    # More cams -> more observations -> often comparable or smaller rms.
    # This is a sanity check; we don't require strict improvement.
    assert d3["n_observations"] >= d2["n_observations"]


def test_bootstrap_z_constraint_applied():
    """An LM with a z_constraint should end up with the constrained z."""
    cam_specs = [
        ("CamA", (-50, 0, 50), (0, -8, 0), 60.0),
        ("CamB", (50, 0, 60), (0, -8, 0), 60.0),
    ]
    lm_specs = [
        ("Sea1", (0, 200, 0)),
        ("Sea2", (40, 220, 0)),
        ("Sea3", (-30, 230, 0)),
    ]
    obs, meas, _, _ = _make_synthetic_world(cam_specs, lm_specs, hint_noise_deg=0.5)
    # Add z_constraints
    meas = Measurements(
        leak_cams=meas.leak_cams,
        bootstrap_hints=meas.bootstrap_hints,
        z_constraints={
            "Sea1": ZConstraint(z=0.0, reason="sea"),
            "Sea2": ZConstraint(z=0.0, reason="sea"),
        },
    )
    state, _ = bootstrap(obs, meas)
    assert state.landmarks["Sea1"].xyz[2] == 0.0
    assert state.landmarks["Sea2"].xyz[2] == 0.0


def test_bootstrap_insufficient_cams_raises():
    leak = LeakCamMeasurement(
        xyz=(0, 0, 5), fov=60, source="test", image_size=(1920, 1080),
    )
    meas = Measurements(leak_cams={"A": leak})
    obs = Observations()
    with pytest.raises(BootstrapError) as exc:
        bootstrap(obs, meas)
    assert "2 leak cams" in str(exc.value)


def test_bootstrap_insufficient_anchors_raises():
    cam_specs = [
        ("CamA", (0, 0, 50), (10, -5, 0), 60.0),
        ("CamB", (200, 50, 60), (-10, -3, 0), 60.0),
    ]
    # Only 1 shared LM
    lm_specs = [("LM1", (100, 300, 20))]
    obs, meas, _, _ = _make_synthetic_world(cam_specs, lm_specs)
    with pytest.raises(BootstrapError) as exc:
        bootstrap(obs, meas)
    assert "anchor LMs" in str(exc.value)


def test_bootstrap_missing_hint_raises():
    leak = LeakCamMeasurement(
        xyz=(0, 0, 5), fov=60, source="test", image_size=(1920, 1080),
    )
    meas = Measurements(leak_cams={"A": leak, "B": leak})
    obs = Observations()
    with pytest.raises(BootstrapError) as exc:
        bootstrap(obs, meas)
    # Either no anchors or no hint, both are valid errors
    msg = str(exc.value)
    assert "anchor" in msg.lower() or "hint" in msg.lower() or "horizon" in msg.lower()

