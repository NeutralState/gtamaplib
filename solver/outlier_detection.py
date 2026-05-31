"""
Outlier detection for pixel markings.

For each landmark observed by 3+ cameras, we triangulate from each pair
and project to the third. If a pair-triangulation produces a point that
the third camera sees far from the marked pixel, it suggests one of the
three markings is inconsistent.

We use a voting scheme: for each (cam, LM) pair, count how often it is
"the outlier" in triplet tests. Drop markings that lose most often.

This is run BEFORE the bootstrap to clean inputs.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set, Tuple

import numpy as np

from .geometry import Camera, project, triangulate_pair
from .io import (
    LeakCamMeasurement,
    Measurements,
    Observations,
    PixelObservation,
)


def detect_outliers(
    observations: Observations,
    measurements: Measurements,
    cam_ypr: Dict[str, Tuple[float, float, float]],
    *,
    outlier_pixel_threshold: float = 50.0,
    min_outlier_ratio: float = 0.5,
    verbose: bool = False,
) -> Tuple[Set[Tuple[str, str]], Dict[str, object]]:
    """Detect inconsistent (cam, LM) pixel markings.

    Args:
        observations: pixel markings
        measurements: provides leak_cams (xyz, fov, image_size)
        cam_ypr: initial ypr estimates (from bootstrap_hints typically)
        outlier_pixel_threshold: pixel error above which a triplet is
            considered inconsistent
        min_outlier_ratio: minimum fraction of triplets that must vote
            a (cam, LM) as outlier before dropping it. 0.5 = majority vote.

    Returns:
        (set_of_outlier_pairs, diagnostics) where outlier_pairs is a set
        of (cam_name, lm_name) tuples to drop, and diagnostics is a dict
        with counts.
    """
    leak_cams = measurements.leak_cams

    # Build Camera objects for each leak cam
    cams: Dict[str, Camera] = {}
    for name, lc in leak_cams.items():
        if name in cam_ypr:
            cams[name] = Camera(
                xyz=lc.xyz, ypr=cam_ypr[name],
                hfov=lc.fov, image_size=lc.image_size,
            )

    # For each LM, find all cams that observe it (only leak cams; we
    # need to trust their xyz/fov).
    lm_to_observers: Dict[str, List[str]] = defaultdict(list)
    for cam_name in cams:
        cam_pixels = observations.pixels.get(cam_name, {})
        for lm_name in cam_pixels:
            lm_to_observers[lm_name].append(cam_name)

    # Vote tracking: for each (cam, LM), count outlier votes
    # outlier_votes[(cam, lm)] = (num_outlier_votes, total_votes)
    outlier_votes: Dict[Tuple[str, str], List[int]] = defaultdict(lambda: [0, 0])

    n_lms_checked = 0
    for lm_name, observers in lm_to_observers.items():
        if len(observers) < 3:
            continue  # Need at least 3 cams to vote
        n_lms_checked += 1

        # For each pair (a, b), triangulate the LM, then project to each
        # other cam c and check pixel error vs marked.
        for i in range(len(observers)):
            for j in range(i + 1, len(observers)):
                a, b = observers[i], observers[j]
                pix_a = observations.pixels[a][lm_name].pixel
                pix_b = observations.pixels[b][lm_name].pixel
                try:
                    xyz, dist = triangulate_pair(cams[a], pix_a, cams[b], pix_b)
                except ValueError:
                    continue
                if dist > 100.0:
                    # Rays don't intersect well — at least one of a, b
                    # is wrong, but we can't tell which yet. Count this
                    # as a "no agreement" for both.
                    outlier_votes[(a, lm_name)][0] += 1
                    outlier_votes[(a, lm_name)][1] += 1
                    outlier_votes[(b, lm_name)][0] += 1
                    outlier_votes[(b, lm_name)][1] += 1
                    continue
                # For each third cam c, check projection
                for k in range(len(observers)):
                    if k == i or k == j:
                        continue
                    c = observers[k]
                    pix_c_marked = observations.pixels[c][lm_name].pixel
                    pix_c_proj = project(tuple(xyz), cams[c])
                    if pix_c_proj is None:
                        continue
                    err = float(np.linalg.norm(
                        np.array(pix_c_proj) - np.array(pix_c_marked)
                    ))
                    if err > outlier_pixel_threshold:
                        # c disagrees with a&b's triangulation.
                        # But maybe a or b is the actual outlier, not c.
                        # Vote: only c is the outlier here.
                        outlier_votes[(c, lm_name)][0] += 1
                    outlier_votes[(c, lm_name)][1] += 1

    # Decide outliers: those with outlier_ratio above threshold
    outliers: Set[Tuple[str, str]] = set()
    for (cam, lm), (n_out, n_total) in outlier_votes.items():
        if n_total < 2:
            continue  # Not enough data to decide
        if n_out / n_total >= min_outlier_ratio:
            outliers.add((cam, lm))

    diagnostics = {
        "n_lms_checked": n_lms_checked,
        "n_pair_lm_votes": len(outlier_votes),
        "n_outliers_dropped": len(outliers),
        "outlier_threshold_px": outlier_pixel_threshold,
        "outlier_ratio_threshold": min_outlier_ratio,
    }

    if verbose:
        print(f"Outlier detection:")
        print(f"  LMs checked (3+ observers): {n_lms_checked}")
        print(f"  (cam, LM) pairs voted on: {len(outlier_votes)}")
        print(f"  Outliers detected: {len(outliers)}")
        if outliers:
            print(f"  Sample outliers:")
            for cam, lm in list(outliers)[:10]:
                ratio = outlier_votes[(cam, lm)][0] / outlier_votes[(cam, lm)][1]
                print(f"    cam='{cam}', LM='{lm}' (voted outlier {ratio*100:.0f}% of time)")

    return outliers, diagnostics


def filter_observations(
    observations: Observations,
    outliers: Set[Tuple[str, str]],
) -> Observations:
    """Return a new Observations with outlier (cam, LM) pairs removed."""
    new_pixels: Dict[str, Dict[str, PixelObservation]] = {}
    for cam_name, lm_map in observations.pixels.items():
        new_lm_map: Dict[str, PixelObservation] = {}
        for lm_name, pix_obs in lm_map.items():
            if (cam_name, lm_name) in outliers:
                continue
            new_lm_map[lm_name] = pix_obs
        if new_lm_map:
            new_pixels[cam_name] = new_lm_map
    return Observations(pixels=new_pixels, horizons=observations.horizons)
