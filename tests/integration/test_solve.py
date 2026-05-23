"""
Integration tests for solver.solve.

These tests run the full pipeline (bootstrap -> iterate -> non-leak cal ->
bundle adjust -> metrics) on synthetic worlds and verify the recovered
state matches ground truth to within meter-scale accuracy.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
import pytest

from solver.geometry import Camera, project
from solver.io import (
    BootstrapHint,
    LeakCamMeasurement,
    Measurements,
    NonLeakCamMeta,
    Observations,
    PixelObservation,
    ZConstraint,
)
from solver.solve import solve


def _synth_world(
    leak_cam_specs,  # [(name, xyz, ypr, fov)]
    non_leak_cam_specs,  # [(name, xyz, ypr, fov)]
    lm_specs,  # [(name, xyz)]
    image_size=(1920, 1080),
    hint_noise_deg=0.5,
    pixel_noise_px=0.0,
    rng_seed=0,
):
    rng = np.random.default_rng(rng_seed)
    true_lm = dict(lm_specs)
    true_cam = {}
    leak_cams = {}
    non_leak_meta = {}
    bootstrap_hints = {}
    pixels = {}

    for name, xyz, ypr, fov in leak_cam_specs:
        true_cam[name] = {"xyz": xyz, "ypr": ypr, "fov": fov}
        leak_cams[name] = LeakCamMeasurement(
            xyz=xyz, fov=fov, source="synth", image_size=image_size,
        )
        bootstrap_hints[name] = BootstrapHint(
            yaw=ypr[0] + float(rng.normal(0, hint_noise_deg)),
            pitch=ypr[1] + float(rng.normal(0, hint_noise_deg)),
            roll=ypr[2] + float(rng.normal(0, hint_noise_deg)),
            confidence=0.5,
        )

    for name, xyz, ypr, fov in non_leak_cam_specs:
        true_cam[name] = {"xyz": xyz, "ypr": ypr, "fov": fov}
        non_leak_meta[name] = NonLeakCamMeta(image_size=image_size)

    all_cam_specs = leak_cam_specs + non_leak_cam_specs
    for name, xyz, ypr, fov in all_cam_specs:
        cam = Camera(xyz=xyz, ypr=ypr, hfov=fov, image_size=image_size)
        pixels[name] = {}
        for lm_name, lm_xyz in lm_specs:
            pix = project(lm_xyz, cam)
            if pix is None:
                continue
            x, y = pix
            if not (0 <= x < image_size[0] and 0 <= y < image_size[1]):
                continue
            if pixel_noise_px > 0:
                x += float(rng.normal(0, pixel_noise_px))
                y += float(rng.normal(0, pixel_noise_px))
            pixels[name][lm_name] = PixelObservation(pixel=(float(x), float(y)))

    obs = Observations(pixels=pixels)
    meas = Measurements(
        leak_cams=leak_cams,
        non_leak_cam_meta=non_leak_meta,
        bootstrap_hints=bootstrap_hints,
    )
    return obs, meas, true_lm, true_cam


def test_solve_3leak_no_noise():
    """3 leak cams, no noise: should recover ground truth."""
    leak_cams = [
        ("CamA", (-80, 0, 50), (5, -5, 0), 60.0),
        ("CamB", (80, 0, 60), (-5, -3, 0), 60.0),
        ("CamC", (0, -60, 40), (0, -8, 0), 60.0),
    ]
    lms = [
        ("LM0", (0, 200, 20)),
        ("LM1", (-30, 220, 30)),
        ("LM2", (40, 210, 40)),
        ("LM3", (-10, 240, 25)),
        ("LM4", (20, 230, 35)),
        ("LM5", (-25, 215, 45)),
    ]
    obs, meas, true_lm, true_cam = _synth_world(
        leak_cams, [], lms, hint_noise_deg=0.5, rng_seed=1,
    )
    state, diag = solve(obs, meas, max_iter=10)

    # Cams should be recovered to within a tiny fraction of a degree
    for name, true in true_cam.items():
        recovered = state.cameras[name]
        yaw_err = abs(((recovered.ypr[0] - true["ypr"][0] + 180) % 360) - 180)
        assert yaw_err < 0.1, f"{name} yaw {recovered.ypr[0]} vs {true['ypr'][0]}"
        assert abs(recovered.ypr[1] - true["ypr"][1]) < 0.1
        assert abs(recovered.ypr[2] - true["ypr"][2]) < 0.1

    # LMs to within centimeters
    for name, true_xyz in true_lm.items():
        if name not in state.landmarks:
            continue
        recovered = state.landmarks[name].xyz
        err = np.linalg.norm(np.array(recovered) - np.array(true_xyz))
        assert err < 1.0, f"LM {name} error {err}m"

    # Global RMS should be very small
    assert state.global_metrics.rms_loss_arcmin < 1.0


def test_solve_2leak_2nonleak():
    """2 leak + 2 non-leak cams: non-leak cams should be calibrated via PnP."""
    # Cams positioned south of LM cluster (which is at y~200), all looking north (yaw~0).
    leak_cams = [
        ("LeakA", (-60, -50, 50), (0, -5, 0), 60.0),
        ("LeakB", (60, -50, 60), (0, -3, 0), 60.0),
    ]
    non_leak_cams = [
        ("FreeA", (-30, -80, 30), (0, -3, 0), 55.0),
        ("FreeB", (30, -80, 35), (0, -4, 0), 65.0),
    ]
    lms = [
        ("LM0", (0, 200, 20)),
        ("LM1", (-30, 220, 30)),
        ("LM2", (30, 210, 40)),
        ("LM3", (-10, 240, 25)),
        ("LM4", (20, 230, 35)),
        ("LM5", (-25, 215, 45)),
        ("LM6", (15, 250, 28)),
        ("LM7", (-5, 200, 50)),
    ]
    obs, meas, true_lm, true_cam = _synth_world(
        leak_cams, non_leak_cams, lms, hint_noise_deg=0.3, rng_seed=2,
    )
    state, diag = solve(obs, meas, max_iter=15)

    # Both leak and non-leak cams should be calibrated
    assert "LeakA" in state.cameras
    assert "LeakB" in state.cameras
    assert "FreeA" in state.cameras
    assert "FreeB" in state.cameras

    # Non-leak cam positions should be recovered to within a few meters
    for name in ("FreeA", "FreeB"):
        recovered = state.cameras[name]
        true = true_cam[name]
        xyz_err = np.linalg.norm(np.array(recovered.xyz) - np.array(true["xyz"]))
        assert xyz_err < 5.0, f"{name} xyz error {xyz_err}m"
        # FOV recovered to within a few degrees
        assert abs(recovered.fov - true["fov"]) < 5.0, (
            f"{name} fov {recovered.fov} vs {true['fov']}"
        )


def test_solve_with_z_constraints():
    """LMs with z=0 should land at z=0."""
    leak_cams = [
        ("CamA", (-80, 0, 50), (5, -10, 0), 60.0),
        ("CamB", (80, 0, 60), (-5, -10, 0), 60.0),
        ("CamC", (0, -60, 40), (0, -10, 0), 60.0),
    ]
    lms = [
        ("Sea1", (0, 200, 0)),
        ("Sea2", (40, 220, 0)),
        ("Sea3", (-30, 230, 0)),
        ("LM3", (10, 240, 25)),
        ("LM4", (20, 230, 35)),
    ]
    obs, meas, true_lm, _ = _synth_world(
        leak_cams, [], lms, hint_noise_deg=0.3, rng_seed=3,
    )
    # Add z_constraints
    meas = Measurements(
        leak_cams=meas.leak_cams,
        bootstrap_hints=meas.bootstrap_hints,
        z_constraints={
            "Sea1": ZConstraint(z=0.0),
            "Sea2": ZConstraint(z=0.0),
            "Sea3": ZConstraint(z=0.0),
        },
    )
    state, _ = solve(obs, meas, max_iter=10)
    for name in ("Sea1", "Sea2", "Sea3"):
        assert state.landmarks[name].xyz[2] == 0.0


def test_solve_with_pixel_noise():
    """With ~1 pixel of marking noise, recovery should still be good."""
    leak_cams = [
        ("CamA", (-80, 0, 50), (5, -5, 0), 60.0),
        ("CamB", (80, 0, 60), (-5, -3, 0), 60.0),
        ("CamC", (0, -60, 40), (0, -8, 0), 60.0),
    ]
    lms = [
        (f"LM{i}", (float(x), float(y), float(z)))
        for i, (x, y, z) in enumerate([
            (0, 200, 20), (-30, 220, 30), (40, 210, 40),
            (-10, 240, 25), (20, 230, 35), (-25, 215, 45),
            (15, 250, 28), (-15, 205, 50),
        ])
    ]
    obs, meas, true_lm, true_cam = _synth_world(
        leak_cams, [], lms,
        hint_noise_deg=0.3, pixel_noise_px=1.0, rng_seed=4,
    )
    state, diag = solve(obs, meas, max_iter=15)

    # With 1px noise on 1920px images at 60deg fov, expect ~1 arcmin RMS
    assert state.global_metrics.rms_loss_arcmin < 5.0

    # LMs to within a few meters
    for name, true_xyz in true_lm.items():
        if name not in state.landmarks:
            continue
        err = np.linalg.norm(np.array(state.landmarks[name].xyz) - np.array(true_xyz))
        assert err < 7.0, f"LM {name} error {err}m"


def test_solve_returns_diagnostics():
    """The diagnostics dict should contain the iteration log."""
    leak_cams = [
        ("CamA", (-50, -50, 50), (0, -5, 0), 60.0),
        ("CamB", (50, -50, 60), (0, -3, 0), 60.0),
    ]
    lms = [
        ("LM0", (0, 200, 20)),
        ("LM1", (-30, 220, 30)),
        ("LM2", (30, 210, 40)),
        ("LM3", (-10, 240, 25)),
    ]
    obs, meas, _, _ = _synth_world(leak_cams, [], lms, hint_noise_deg=0.3, rng_seed=5)
    state, diag = solve(obs, meas, max_iter=5)
    assert "log" in diag
    assert "final_metrics" in diag
    phases = [entry["phase"] for entry in diag["log"]]
    assert "bootstrap" in phases
    assert "main_loop" in phases
    assert "bundle_adjust" in phases

