"""Tests for solver.priors."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
import pytest

from solver.priors import (
    PriorError,
    compute_prior_residuals,
    n_residuals_for_prior,
)


# ----------------------------------------------------------------------
# distance
# ----------------------------------------------------------------------

def test_distance_perfect():
    lm_xyz = {"A": np.array([0.0, 0.0, 0.0]), "B": np.array([10.0, 0.0, 0.0])}
    r = compute_prior_residuals("distance", lm_xyz, ["A", "B"], value=10.0, weight=1.0)
    assert len(r) == 1
    assert abs(r[0]) < 1e-9


def test_distance_too_short():
    lm_xyz = {"A": np.array([0.0, 0.0, 0.0]), "B": np.array([8.0, 0.0, 0.0])}
    r = compute_prior_residuals("distance", lm_xyz, ["A", "B"], value=10.0, weight=1.0)
    assert abs(r[0] - (-2.0)) < 1e-9


def test_distance_weight_applied():
    lm_xyz = {"A": np.array([0.0, 0.0, 0.0]), "B": np.array([12.0, 0.0, 0.0])}
    r = compute_prior_residuals("distance", lm_xyz, ["A", "B"], value=10.0, weight=5.0)
    assert abs(r[0] - 10.0) < 1e-9  # (12 - 10) * 5


def test_distance_wrong_arity():
    lm_xyz = {"A": np.array([0.0, 0.0, 0.0])}
    with pytest.raises(PriorError):
        compute_prior_residuals("distance", lm_xyz, ["A"], value=1.0, weight=1.0)


# ----------------------------------------------------------------------
# vertical
# ----------------------------------------------------------------------

def test_vertical_perfect():
    lm_xyz = {"A": np.array([5.0, 10.0, 0.0]), "B": np.array([5.0, 10.0, 100.0])}
    r = compute_prior_residuals("vertical", lm_xyz, ["A", "B"], value=0.0, weight=1.0)
    assert len(r) == 2
    assert abs(r[0]) < 1e-9 and abs(r[1]) < 1e-9


def test_vertical_misaligned():
    lm_xyz = {"A": np.array([5.0, 10.0, 0.0]), "B": np.array([7.0, 12.0, 100.0])}
    r = compute_prior_residuals("vertical", lm_xyz, ["A", "B"], value=0.0, weight=1.0)
    assert abs(r[0] - (-2.0)) < 1e-9
    assert abs(r[1] - (-2.0)) < 1e-9


# ----------------------------------------------------------------------
# colinear
# ----------------------------------------------------------------------

def test_colinear_perfect():
    lm_xyz = {
        "A": np.array([0.0, 0.0, 0.0]),
        "B": np.array([10.0, 0.0, 0.0]),
        "C": np.array([5.0, 0.0, 0.0]),
        "D": np.array([7.0, 0.0, 0.0]),
    }
    r = compute_prior_residuals(
        "colinear", lm_xyz, ["A", "B", "C", "D"], value=0.0, weight=1.0,
    )
    assert len(r) == 2
    assert all(abs(v) < 1e-9 for v in r)


def test_colinear_offset():
    """Point C is 3m off the line A-B."""
    lm_xyz = {
        "A": np.array([0.0, 0.0, 0.0]),
        "B": np.array([10.0, 0.0, 0.0]),
        "C": np.array([5.0, 3.0, 0.0]),
    }
    r = compute_prior_residuals("colinear", lm_xyz, ["A", "B", "C"], value=0.0, weight=1.0)
    assert len(r) == 1
    assert abs(r[0] - 3.0) < 1e-9


# ----------------------------------------------------------------------
# coplanar
# ----------------------------------------------------------------------

def test_coplanar_perfect():
    # 4 LMs all in the z=0 plane
    lm_xyz = {
        "A": np.array([0.0, 0.0, 0.0]),
        "B": np.array([10.0, 0.0, 0.0]),
        "C": np.array([0.0, 10.0, 0.0]),
        "D": np.array([5.0, 5.0, 0.0]),
    }
    r = compute_prior_residuals(
        "coplanar", lm_xyz, ["A", "B", "C", "D"], value=0.0, weight=1.0,
    )
    assert len(r) == 1
    assert abs(r[0]) < 1e-9


def test_coplanar_offset():
    """D is 2m above the plane of A, B, C (which is z=0)."""
    lm_xyz = {
        "A": np.array([0.0, 0.0, 0.0]),
        "B": np.array([10.0, 0.0, 0.0]),
        "C": np.array([0.0, 10.0, 0.0]),
        "D": np.array([5.0, 5.0, 2.0]),
    }
    r = compute_prior_residuals(
        "coplanar", lm_xyz, ["A", "B", "C", "D"], value=0.0, weight=1.0,
    )
    assert abs(r[0] - 2.0) < 1e-9


# ----------------------------------------------------------------------
# Misc
# ----------------------------------------------------------------------

def test_unknown_prior_type():
    with pytest.raises(PriorError):
        compute_prior_residuals("not_a_type", {}, [], 0.0, 1.0)


def test_n_residuals_predictions():
    assert n_residuals_for_prior("distance", 2) == 1
    assert n_residuals_for_prior("vertical", 2) == 2
    assert n_residuals_for_prior("colinear", 5) == 3
    assert n_residuals_for_prior("coplanar", 6) == 3

