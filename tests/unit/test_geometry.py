"""
Unit tests for solver.geometry.

Tests cover:
- FOV conversion (vfov_from_hfov is inverse of hfov_from_vfov)
- Rotation roundtrip (ypr -> Rotation -> ypr)
- Projection forward (known cam + LM -> known pixel)
- Ray backward (pixel through cam -> ray passes through LM)
- Forward/backward consistency
- Triangulation precision (two rays from known LM -> recover LM)
- Behind-camera rejection
- Parity with legacy gtamaplib.get_pixel / get_pixel_direction

CONVENTION (matching legacy gtamaplib):
  At yaw=0, pitch=0, roll=0, the camera looks toward +y (north).
  The cam-local frame is: +x=right, +y=forward, +z=up.
  Increasing yaw rotates around +z (counterclockwise when viewed from above).
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
import pytest

from solver.geometry import (
    Camera,
    vfov_from_hfov,
    hfov_from_vfov,
    rotation_from_ypr,
    ypr_from_rotation,
    project,
    ray_from_pixel,
    triangulate_pair,
    triangulate_rays,
    angular_residual_arcmin,
)


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

def make_camera(xyz=(0, 0, 0), ypr=(0, 0, 0), hfov=60.0, size=(1920, 1080)) -> Camera:
    return Camera(xyz=xyz, ypr=ypr, hfov=hfov, image_size=size)


# ----------------------------------------------------------------------
# FOV conversion
# ----------------------------------------------------------------------

def test_fov_roundtrip():
    for hfov in [10.0, 30.0, 60.0, 90.0, 120.0]:
        for size in [(1920, 1080), (1024, 768), (3840, 2160), (640, 480)]:
            vfov = vfov_from_hfov(hfov, size)
            hfov_back = hfov_from_vfov(vfov, size)
            assert abs(hfov - hfov_back) < 1e-10


def test_vfov_square_image():
    assert abs(vfov_from_hfov(60.0, (1000, 1000)) - 60.0) < 1e-10


def test_vfov_wider_than_tall():
    vfov = vfov_from_hfov(60.0, (1920, 1080))
    assert vfov < 60.0
    assert 35.0 < vfov < 40.0


# ----------------------------------------------------------------------
# Rotation
# ----------------------------------------------------------------------

def test_rotation_roundtrip_simple():
    for ypr in [(0, 0, 0), (45, 0, 0), (90, 0, 0), (0, 30, 0), (0, 0, 15),
                (45, 30, 15), (-30, -45, -20)]:
        rot = rotation_from_ypr(ypr)
        ypr_back = ypr_from_rotation(rot)
        expected_yaw = ypr[0] % 360.0
        assert abs(ypr_back[0] - expected_yaw) < 1e-6, f"yaw mismatch for {ypr}"
        assert abs(ypr_back[1] - ypr[1]) < 1e-6, f"pitch mismatch for {ypr}"
        assert abs(ypr_back[2] - ypr[2]) < 1e-6, f"roll mismatch for {ypr}"


def test_yaw_zero_looks_positive_y():
    """At yaw=0, the cam should look toward +y (north). gtamaplib convention."""
    cam = make_camera(xyz=(0, 0, 0), ypr=(0, 0, 0))
    pixel = project((0, 10, 0), cam)
    assert pixel is not None
    w, h = cam.image_size
    assert abs(pixel[0] - (w / 2 - 0.5)) < 1e-6
    assert abs(pixel[1] - (h / 2 - 0.5)) < 1e-6


def test_yaw_90_looks_negative_x():
    """At yaw=90 (90deg CCW from +y), the cam looks toward -x."""
    cam = make_camera(xyz=(0, 0, 0), ypr=(90, 0, 0))
    pixel = project((-10, 0, 0), cam)
    assert pixel is not None
    w, h = cam.image_size
    assert abs(pixel[0] - (w / 2 - 0.5)) < 1e-6
    assert abs(pixel[1] - (h / 2 - 0.5)) < 1e-6


# ----------------------------------------------------------------------
# Projection forward
# ----------------------------------------------------------------------

def test_project_behind_camera_returns_none():
    """A point behind the camera should give None."""
    cam = make_camera(xyz=(0, 0, 0), ypr=(0, 0, 0))  # looking +y
    pixel = project((0, -10, 0), cam)
    assert pixel is None


def test_project_point_above_lands_above_center():
    """A point higher in z than the cam should project above center (lower py)."""
    cam = make_camera(xyz=(0, 0, 0), ypr=(0, 0, 0))  # looking +y
    pixel_center = project((0, 10, 0), cam)
    pixel_above = project((0, 10, 5), cam)
    assert pixel_center is not None
    assert pixel_above is not None
    assert pixel_above[1] < pixel_center[1]


def test_project_point_to_right_lands_right_of_center():
    """At yaw=0 looking +y, cam-local right is +x.
    A +x world point lands to the RIGHT of center (higher px).
    """
    cam = make_camera(xyz=(0, 0, 0), ypr=(0, 0, 0))
    pixel_center = project((0, 10, 0), cam)
    pixel_right = project((5, 10, 0), cam)
    assert pixel_center is not None
    assert pixel_right is not None
    assert pixel_right[0] > pixel_center[0]


# ----------------------------------------------------------------------
# Inverse projection: ray
# ----------------------------------------------------------------------

def test_ray_center_pixel_points_forward():
    """At yaw=0, the center pixel's ray = (0, 1, 0) world (=+y forward)."""
    cam = make_camera(xyz=(0, 0, 0), ypr=(0, 0, 0), size=(1920, 1080))
    w, h = cam.image_size
    origin, direction = ray_from_pixel((w / 2 - 0.5, h / 2 - 0.5), cam)
    assert np.allclose(origin, [0, 0, 0])
    assert np.allclose(direction, [0, 1, 0], atol=1e-6)


def test_ray_origin_is_cam_position():
    cam = make_camera(xyz=(100, -50, 30), ypr=(45, 10, 0))
    origin, _ = ray_from_pixel((100, 200), cam)
    assert np.allclose(origin, [100, -50, 30])


# ----------------------------------------------------------------------
# Forward/backward consistency
# ----------------------------------------------------------------------

def test_forward_backward_consistency():
    cam = make_camera(xyz=(50, 100, 20), ypr=(30, -5, 2), hfov=70.0)

    # Pick a point in front of the cam by extending its forward vector
    rot = rotation_from_ypr(cam.ypr)
    forward = rot.apply([0, 1, 0])
    world_xyz = np.array(cam.xyz) + forward * 100 + np.array([5, 3, 2])

    pixel = project(tuple(world_xyz), cam)
    assert pixel is not None

    origin, direction = ray_from_pixel(tuple(pixel), cam)
    delta = world_xyz - origin
    delta_norm = delta / np.linalg.norm(delta)
    assert np.allclose(delta_norm, direction, atol=1e-9)


def test_forward_backward_consistency_many_random():
    rng = np.random.default_rng(42)
    for _ in range(50):
        cam = make_camera(
            xyz=tuple(rng.uniform(-1000, 1000, 3)),
            ypr=(float(rng.uniform(0, 360)),
                 float(rng.uniform(-60, 60)),
                 float(rng.uniform(-30, 30))),
            hfov=float(rng.uniform(30, 90)),
            size=(int(rng.choice([1920, 2458, 1024])),
                  int(rng.choice([1080, 1604, 768]))),
        )
        rot = rotation_from_ypr(cam.ypr)
        forward = rot.apply([0, 1, 0])
        world_xyz = np.array(cam.xyz) + forward * rng.uniform(10, 500) + rng.normal(0, 5, 3)

        pixel = project(tuple(world_xyz), cam)
        if pixel is None:
            continue

        origin, direction = ray_from_pixel(tuple(pixel), cam)
        delta = world_xyz - origin
        delta_norm = delta / np.linalg.norm(delta)
        assert np.allclose(delta_norm, direction, atol=1e-8)


# ----------------------------------------------------------------------
# Triangulation
# ----------------------------------------------------------------------

def test_triangulate_perfect_intersection():
    """Two cams with perfect markings should triangulate to the exact LM."""
    lm = (100.0, 200.0, 30.0)
    cam_a = make_camera(xyz=(0, 0, 5), ypr=(40, -5, 0), hfov=60.0)
    cam_b = make_camera(xyz=(50, 50, 10), ypr=(20, 0, 0), hfov=60.0)

    pixel_a = project(lm, cam_a)
    pixel_b = project(lm, cam_b)
    assert pixel_a is not None
    assert pixel_b is not None

    xyz, dist = triangulate_pair(cam_a, tuple(pixel_a), cam_b, tuple(pixel_b))
    assert dist < 1e-6
    assert np.allclose(xyz, lm, atol=1e-6)


def test_triangulate_with_pixel_noise():
    """A few pixels of noise should give a few meters of error, not catastrophic."""
    # Place LM such that both cams comfortably see it.
    # Cam A looks +y, cam B is to the east also looking ~north.
    lm = (50.0, 300.0, 30.0)
    cam_a = make_camera(xyz=(0, 0, 20), ypr=(0, -2, 0), hfov=60.0)
    cam_b = make_camera(xyz=(100, 50, 25), ypr=(-20, -2, 0), hfov=60.0)

    pixel_a = project(lm, cam_a)
    pixel_b = project(lm, cam_b)
    assert pixel_a is not None, "cam_a doesn't see lm"
    assert pixel_b is not None, "cam_b doesn't see lm"

    rng = np.random.default_rng(1)
    pixel_a_noisy = tuple(pixel_a + rng.normal(0, 2, 2))
    pixel_b_noisy = tuple(pixel_b + rng.normal(0, 2, 2))

    xyz, dist = triangulate_pair(cam_a, pixel_a_noisy, cam_b, pixel_b_noisy)
    error_m = np.linalg.norm(np.array(xyz) - np.array(lm))
    assert error_m < 10.0, f"expected sub-10m error, got {error_m}m"


def test_triangulate_parallel_rays_raises():
    o = np.array([0.0, 0.0, 0.0])
    d = np.array([1.0, 0.0, 0.0])
    with pytest.raises(ValueError):
        triangulate_rays(o, d, o + np.array([0, 10, 0]), d)


# ----------------------------------------------------------------------
# Angular residual
# ----------------------------------------------------------------------

def test_angular_residual_zero_for_perfect_match():
    """For a correctly projected pixel, residual is well below pixel-marking precision."""
    lm = (100.0, 200.0, 30.0)
    cam = make_camera(xyz=(0, 0, 5), ypr=(40, -5, 0))
    pixel = project(lm, cam)
    res = angular_residual_arcmin(cam, tuple(pixel), lm)
    # 1e-3 arcmin = ~0.001/60 deg = negligible vs pixel-marking error which is
    # measured in arcminutes.
    assert res < 1e-3


def test_angular_residual_grows_with_offset():
    lm = (100.0, 200.0, 30.0)
    cam = make_camera(xyz=(0, 0, 5), ypr=(40, -5, 0))
    pixel = project(lm, cam)
    offset_pixel = (pixel[0] + 5, pixel[1])
    res = angular_residual_arcmin(cam, offset_pixel, lm)
    assert res > 0
    assert res < 60  # less than 1 degree


# ----------------------------------------------------------------------
# Parity with legacy gtamaplib
# ----------------------------------------------------------------------

def test_parity_with_legacy_gtamaplib():
    """Our project() must match gtamaplib.get_pixel() to ~10 decimals.

    This is the most important regression test in this file.
    """
    try:
        import gtamaplib as ml_legacy
    except ImportError:
        pytest.skip("Legacy gtamaplib not importable; skipping parity test.")

    rng = np.random.default_rng(7)
    for _ in range(30):
        cam_xyz = tuple(rng.uniform(-500, 500, 3))
        ypr = (float(rng.uniform(0, 360)),
               float(rng.uniform(-45, 45)),
               float(rng.uniform(-20, 20)))
        hfov = float(rng.uniform(30, 90))
        size = (1920, 1080)

        cam = Camera(xyz=cam_xyz, ypr=ypr, hfov=hfov, image_size=size)

        vfov = vfov_from_hfov(hfov, size)
        q = ml_legacy.get_q(ypr)

        rot = rotation_from_ypr(ypr)
        forward = rot.apply([0, 1, 0])
        world = np.array(cam_xyz) + forward * rng.uniform(20, 200) + rng.normal(0, 3, 3)

        our_pixel = project(tuple(world), cam)
        legacy_pixel = ml_legacy.get_pixel(world, cam_xyz, q, (hfov, vfov), size)

        if our_pixel is None:
            assert legacy_pixel is None
            continue
        assert legacy_pixel is not None
        assert np.allclose(our_pixel, legacy_pixel, atol=1e-9), (
            f"pixel mismatch: ours={our_pixel}, legacy={legacy_pixel}"
        )


def test_parity_ray_with_legacy_gtamaplib():
    """Our ray_from_pixel() must match gtamaplib.get_pixel_direction()."""
    try:
        import gtamaplib as ml_legacy
    except ImportError:
        pytest.skip("Legacy gtamaplib not importable; skipping parity test.")

    rng = np.random.default_rng(11)
    for _ in range(30):
        cam_xyz = tuple(rng.uniform(-500, 500, 3))
        ypr = (float(rng.uniform(0, 360)),
               float(rng.uniform(-45, 45)),
               float(rng.uniform(-20, 20)))
        hfov = float(rng.uniform(30, 90))
        size = (1920, 1080)

        cam = Camera(xyz=cam_xyz, ypr=ypr, hfov=hfov, image_size=size)
        vfov = vfov_from_hfov(hfov, size)
        q = ml_legacy.get_q(ypr)

        pixel = (float(rng.uniform(0, size[0] - 1)),
                 float(rng.uniform(0, size[1] - 1)))

        _, our_dir = ray_from_pixel(pixel, cam)
        legacy_dir = ml_legacy.get_pixel_direction(pixel, q, (hfov, vfov), size)

        assert np.allclose(our_dir, legacy_dir, atol=1e-9)
