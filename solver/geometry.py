"""
Pure geometry: projection, rays, triangulation.

Conventions (matching legacy gtamaplib for regression compatibility):

  World coordinates:
    Right-handed, z-up.
    +x = east, +y = north, +z = up.
    All units in meters.

  Camera orientation:
    Euler angles in the "ZXY" intrinsic order, in degrees:
      yaw   = rotation around +z  (0 = looking +x, 90 = looking +y)
      pitch = rotation around the cam's local right axis (positive = up)
      roll  = rotation around the cam's local forward axis

  Camera local frame (after rotation):
    +x = right, +y = forward (into the scene), +z = up.

  Field of view:
    hfov in degrees. vfov derived from hfov + image aspect ratio.

  Pixel convention:
    (0, 0) is the top-left of the image. +x = right, +y = down.
    A pixel's center is at integer + 0.5; pixel index N spans [N, N+1).

This module is pure: no global state, no side effects. Every function
returns a value or None.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from scipy.spatial.transform import Rotation


# ----------------------------------------------------------------------
# Camera data class
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Camera:
    """A camera pose + intrinsics. Immutable.

    All angles in degrees, all positions in meters, all pixels relative
    to the image's top-left.
    """
    xyz: Tuple[float, float, float]
    ypr: Tuple[float, float, float]
    hfov: float
    image_size: Tuple[int, int]  # (width, height) in pixels

    @property
    def vfov(self) -> float:
        return vfov_from_hfov(self.hfov, self.image_size)

    @property
    def width(self) -> int:
        return self.image_size[0]

    @property
    def height(self) -> int:
        return self.image_size[1]


# ----------------------------------------------------------------------
# FOV conversion
# ----------------------------------------------------------------------

def vfov_from_hfov(hfov_deg: float, image_size: Tuple[int, int]) -> float:
    """Compute vertical FOV from horizontal FOV and image size.

    Uses the standard pinhole-camera relation:
      tan(vfov/2) = tan(hfov/2) / aspect_ratio
    where aspect_ratio = width / height.
    """
    w, h = image_size
    ratio = w / h
    return float(np.degrees(2 * np.arctan(np.tan(np.radians(hfov_deg) / 2) / ratio)))


def hfov_from_vfov(vfov_deg: float, image_size: Tuple[int, int]) -> float:
    """Inverse of vfov_from_hfov."""
    w, h = image_size
    ratio = w / h
    return float(np.degrees(2 * np.arctan(np.tan(np.radians(vfov_deg) / 2) * ratio)))


# ----------------------------------------------------------------------
# Rotation helpers
# ----------------------------------------------------------------------

def rotation_from_ypr(ypr_deg: Tuple[float, float, float]) -> Rotation:
    """Build a scipy Rotation from (yaw, pitch, roll) in degrees, intrinsic ZXY."""
    return Rotation.from_euler("ZXY", ypr_deg, degrees=True)


def ypr_from_rotation(rot: Rotation) -> Tuple[float, float, float]:
    """Inverse of rotation_from_ypr. Yaw is normalized to [0, 360)."""
    yaw, pitch, roll = rot.as_euler("ZXY", degrees=True)
    return (float(yaw) % 360.0, float(pitch), float(roll))


# ----------------------------------------------------------------------
# Projection: world -> pixel
# ----------------------------------------------------------------------

def project(world_xyz: Tuple[float, float, float], cam: Camera) -> Optional[np.ndarray]:
    """Project a world-space point to a pixel on the camera's image.

    Returns:
        np.ndarray of shape (2,) with [pixel_x, pixel_y], or None if the
        point is behind the camera or projection is otherwise invalid.

    Notes:
        Pixel coordinates are continuous (not integer). The center of
        pixel (i, j) is at (i + 0.5, j + 0.5) in this convention. A
        return value of (px, py) means the world point maps exactly to
        that continuous location.
    """
    rot = rotation_from_ypr(cam.ypr)
    delta = np.asarray(world_xyz, dtype=float) - np.asarray(cam.xyz, dtype=float)
    cam_dir = rot.inv().apply(delta)  # express delta in camera-local frame

    # Behind the camera? Cam-local +y points forward.
    if cam_dir[1] <= 0:
        return None

    tan_h = np.tan(np.radians(cam.hfov) / 2)
    tan_v = np.tan(np.radians(cam.vfov) / 2)

    ndc_x = cam_dir[0] / cam_dir[1] / tan_h
    ndc_y = cam_dir[2] / cam_dir[1] / tan_v

    w, h = cam.image_size
    px = (ndc_x + 1) * 0.5 * w - 0.5
    py = (1 - (ndc_y + 1) * 0.5) * h - 0.5

    if not (np.isfinite(px) and np.isfinite(py)):
        return None

    return np.array([px, py], dtype=float)


# ----------------------------------------------------------------------
# Inverse projection: pixel -> world ray
# ----------------------------------------------------------------------

def ray_from_pixel(
    pixel: Tuple[float, float], cam: Camera
) -> Tuple[np.ndarray, np.ndarray]:
    """Build the world-space ray that projects to the given pixel.

    Returns:
        (origin, direction) tuple. origin is cam.xyz as np.ndarray;
        direction is a unit vector in world coordinates.
    """
    x, y = pixel
    w, h = cam.image_size

    ndc_x = 2 * ((x + 0.5) / w) - 1
    ndc_y = 2 * ((y + 0.5) / h) - 1

    tan_h = np.tan(np.radians(cam.hfov) / 2)
    tan_v = np.tan(np.radians(cam.vfov) / 2)

    # Build direction in camera-local frame: +x right, +y forward, +z up.
    # Note the minus on ndc_y: image y increases downward, but cam z is up.
    cam_x = ndc_x * tan_h
    cam_z = -ndc_y * tan_v
    cam_dir_local = np.array([cam_x, 1.0, cam_z], dtype=float)

    rot = rotation_from_ypr(cam.ypr)
    world_dir = rot.apply(cam_dir_local)
    world_dir = world_dir / np.linalg.norm(world_dir)

    origin = np.asarray(cam.xyz, dtype=float)
    return origin, world_dir


# ----------------------------------------------------------------------
# Triangulation of two rays
# ----------------------------------------------------------------------

def triangulate_pair(
    cam_a: Camera, pixel_a: Tuple[float, float],
    cam_b: Camera, pixel_b: Tuple[float, float],
) -> Tuple[np.ndarray, float]:
    """Find the world point closest to both camera rays.

    Uses the closed-form midpoint of the common perpendicular between
    two skew lines.

    Returns:
        (xyz, distance) where:
          xyz is the closest point (midpoint of the common perpendicular),
          distance is the shortest distance between the two rays in meters.
          A small distance means the rays nearly intersect; a large
          distance means the observation is inconsistent.

    Raises:
        ValueError: if the two rays are parallel (degenerate).
    """
    o_a, d_a = ray_from_pixel(pixel_a, cam_a)
    o_b, d_b = ray_from_pixel(pixel_b, cam_b)
    return triangulate_rays(o_a, d_a, o_b, d_b)


def triangulate_rays(
    origin_a: np.ndarray, direction_a: np.ndarray,
    origin_b: np.ndarray, direction_b: np.ndarray,
) -> Tuple[np.ndarray, float]:
    """Triangulate two rays (lower-level entry point).

    Both directions must be unit vectors.

    Returns:
        (midpoint, distance) of the common perpendicular segment.

    Raises:
        ValueError: if the rays are parallel.
    """
    o_a = np.asarray(origin_a, dtype=float)
    d_a = np.asarray(direction_a, dtype=float)
    o_b = np.asarray(origin_b, dtype=float)
    d_b = np.asarray(direction_b, dtype=float)

    w0 = o_a - o_b
    a = np.dot(d_a, d_a)
    b = np.dot(d_a, d_b)
    c = np.dot(d_b, d_b)
    d = np.dot(d_a, w0)
    e = np.dot(d_b, w0)

    denom = a * c - b * b
    if abs(denom) < 1e-12:
        raise ValueError("Rays are parallel; cannot triangulate.")

    t_a = (b * e - c * d) / denom
    t_b = (a * e - b * d) / denom

    point_a = o_a + t_a * d_a
    point_b = o_b + t_b * d_b
    midpoint = 0.5 * (point_a + point_b)
    distance = float(np.linalg.norm(point_a - point_b))

    return midpoint, distance


# ----------------------------------------------------------------------
# Convenience: angular residual
# ----------------------------------------------------------------------

def angular_residual_arcmin(
    cam: Camera, pixel: Tuple[float, float], world_xyz: Tuple[float, float, float],
) -> float:
    """Return the angle (in arcminutes) between the cam's ray for `pixel`
    and the actual direction from cam to `world_xyz`.

    This is the standard projection-residual metric: zero means perfect
    match, larger means the marked pixel and the world point disagree.
    """
    origin, ray_dir = ray_from_pixel(pixel, cam)
    target_dir = np.asarray(world_xyz, dtype=float) - origin
    norm = np.linalg.norm(target_dir)
    if norm < 1e-12:
        return 0.0
    target_dir = target_dir / norm
    cos_theta = np.clip(np.dot(ray_dir, target_dir), -1.0, 1.0)
    angle_deg = np.degrees(np.arccos(cos_theta))
    return float(angle_deg * 60.0)
