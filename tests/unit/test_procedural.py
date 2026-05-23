"""Tests for solver.procedural."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
import pytest

from solver.procedural import (
    GENERATORS,
    ProceduralError,
    compute_procedural,
    topological_order,
)


# ----------------------------------------------------------------------
# Generators
# ----------------------------------------------------------------------

def test_linear_interpolation_midpoint():
    out = compute_procedural(
        "linear_interpolation",
        {"A": (0, 0, 0), "B": (10, 0, 0)},
        {"a": "A", "b": "B", "t": 0.5},
    )
    assert out == (5.0, 0.0, 0.0)


def test_linear_interpolation_at_endpoints():
    out_a = compute_procedural(
        "linear_interpolation",
        {"A": (1, 2, 3), "B": (10, 20, 30)},
        {"a": "A", "b": "B", "t": 0.0},
    )
    assert out_a == (1.0, 2.0, 3.0)
    out_b = compute_procedural(
        "linear_interpolation",
        {"A": (1, 2, 3), "B": (10, 20, 30)},
        {"a": "A", "b": "B", "t": 1.0},
    )
    assert out_b == (10.0, 20.0, 30.0)


def test_linear_interpolation_missing_params():
    with pytest.raises(ProceduralError):
        compute_procedural("linear_interpolation", {"A": (0, 0, 0)}, {})


def test_linear_interpolation_missing_dep():
    with pytest.raises(ProceduralError):
        compute_procedural(
            "linear_interpolation",
            {"A": (0, 0, 0)},
            {"a": "A", "b": "MISSING", "t": 0.5},
        )


def test_weighted_centroid_equal_weights():
    out = compute_procedural(
        "weighted_centroid",
        {"A": (0, 0, 0), "B": (10, 0, 0), "C": (0, 10, 0)},
        {"weights": {"A": 1, "B": 1, "C": 1}},
    )
    assert out == pytest.approx((10/3, 10/3, 0))


def test_weighted_centroid_implicit_equal_weights():
    out = compute_procedural(
        "weighted_centroid",
        {"A": (0, 0, 0), "B": (4, 0, 0)},
        {},
    )
    assert out == (2.0, 0.0, 0.0)


def test_weighted_centroid_unequal():
    out = compute_procedural(
        "weighted_centroid",
        {"A": (0, 0, 0), "B": (10, 0, 0)},
        {"weights": {"A": 1, "B": 3}},
    )
    assert out == (7.5, 0.0, 0.0)


def test_vertical_offset():
    out = compute_procedural(
        "vertical_offset",
        {"base": (5, 10, 20)},
        {"base": "base", "dz": 7.5},
    )
    assert out == (5.0, 10.0, 27.5)


def test_box_corner():
    # Square corners at z=0: A=(0,0), B=(10,0), C=(10,10), expect D=(0,10)
    out = compute_procedural(
        "box_corner",
        {"A": (0, 0, 0), "B": (10, 0, 0), "C": (10, 10, 0)},
        {"a": "A", "b": "B", "c": "C"},
    )
    assert out == (0.0, 10.0, 0.0)


def test_face_grid_corner():
    """u=0, v=0 should give NW corner exactly."""
    out = compute_procedural(
        "face_grid",
        {
            "NW": (0, 100, 50), "NE": (100, 100, 50),
            "SW": (0, 0, 50),   "SE": (100, 0, 50),
        },
        {"nw": "NW", "ne": "NE", "sw": "SW", "se": "SE", "u": 0.0, "v": 0.0},
    )
    assert out == (0.0, 100.0, 50.0)


def test_face_grid_center():
    """u=0.5, v=0.5 should give the centroid."""
    out = compute_procedural(
        "face_grid",
        {
            "NW": (0, 100, 50), "NE": (100, 100, 50),
            "SW": (0, 0, 50),   "SE": (100, 0, 50),
        },
        {"nw": "NW", "ne": "NE", "sw": "SW", "se": "SE", "u": 0.5, "v": 0.5},
    )
    assert out == (50.0, 50.0, 50.0)


def test_unknown_generator():
    with pytest.raises(ProceduralError) as exc:
        compute_procedural("not_a_generator", {}, {})
    assert "Unknown generator" in str(exc.value)


# ----------------------------------------------------------------------
# Topological order
# ----------------------------------------------------------------------

@dataclass
class FakeSpec:
    depends_on: List[str]


def test_topological_order_linear():
    specs = {
        "C": FakeSpec(depends_on=["B"]),
        "A": FakeSpec(depends_on=[]),
        "B": FakeSpec(depends_on=["A"]),
    }
    order = topological_order(specs)
    assert order.index("A") < order.index("B")
    assert order.index("B") < order.index("C")


def test_topological_order_diamond():
    # D depends on B and C, both depend on A.
    specs = {
        "A": FakeSpec(depends_on=[]),
        "B": FakeSpec(depends_on=["A"]),
        "C": FakeSpec(depends_on=["A"]),
        "D": FakeSpec(depends_on=["B", "C"]),
    }
    order = topological_order(specs)
    assert order.index("A") < order.index("B")
    assert order.index("A") < order.index("C")
    assert order.index("B") < order.index("D")
    assert order.index("C") < order.index("D")


def test_topological_order_external_deps_ok():
    """Deps that aren't in the procedural set (e.g. pixel-anchored LMs)
    should be ignored, not raise."""
    specs = {
        "Proc1": FakeSpec(depends_on=["PixelAnchored1", "PixelAnchored2"]),
    }
    order = topological_order(specs)
    assert order == ["Proc1"]


def test_topological_order_cycle_raises():
    specs = {
        "A": FakeSpec(depends_on=["B"]),
        "B": FakeSpec(depends_on=["A"]),
    }
    with pytest.raises(ProceduralError) as exc:
        topological_order(specs)
    assert "Cycle" in str(exc.value)

