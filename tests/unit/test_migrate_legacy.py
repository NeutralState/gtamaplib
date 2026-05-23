"""Tests for solver.migrate_legacy.

Builds a tiny fake legacy gtamapdata/ in tmp_path and verifies the
output files are valid for the new solver loaders.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest

from solver.io import load_measurements, load_observations
from solver.migrate_legacy import (
    find_procedural_candidates,
    find_z_zero_candidates,
    migrate,
)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _make_fake_legacy(root: Path) -> Path:
    legacy = root / "gtamapdata"
    _write_json(legacy / "cameras.json", {
        "Diner": {
            "id": 1, "player": [100.5, 200.3, 5.0],
            "xyz": [100.5, 200.3, 5.0], "ypr": [180.5, -5.2, 0.1],
            "fov": [59.86, 33.76], "size": [1824, 1080],
            "source": "2022-09-01 14-37-21",
        },
        "Beach (A)": {
            "id": 2, "player": None,
            "xyz": [50.0, 100.0, 10.0], "ypr": [90.0, 0.0, 0.0],
            "fov": [60.0, 33.75], "size": [1920, 1080],
            "source": "screenshot.png",
        },
        "Diner (NE)": {
            "id": 3, "player": [120.0, 220.0, 8.0],
            "xyz": [120.0, 220.0, 8.0], "ypr": [200.0, -3.0, 0.0],
            "fov": [55.0, 31.0], "size": [1920, 1080],
            "source": "from leak archive",
        },
    })
    _write_json(legacy / "pixels.json", {
        "Diner": {
            "LM_A": [500.0, 600.0],
            "LM_B": [800.5, 400.5],
        },
        "Beach (A)": {
            "LM_A": [950.0, 540.0],
        },
        "Diner (NE)": {
            "LM_A": [400.0, 500.0],
            "LM_B": [600.0, 350.0],
            "LM_C": [750.0, 450.0],
        },
    })
    _write_json(legacy / "landmarks.json", {
        "LM_A": [0.0, 50.0, 10.0],
        "LM_B": [10.0, 60.0, 15.0],
        "1000 Venetian Way (W1)": [5.0, 5.0, 9.0],
        "1000 Venetian Way (W2)": [5.0, 5.0, 18.0],
        "Portofino Tower (B-frontL-NW)": [100.0, 100.0, 50.0],
        "Sea Level (Beach)": [0.0, 0.0, 0.0],
    })
    return legacy


def test_migrate_basic(tmp_path: Path):
    legacy = _make_fake_legacy(tmp_path)
    output = tmp_path / "out"
    stats = migrate(legacy, output, verbose=False)

    assert stats["leak_cams"] == 2          # Diner + Diner (NE)
    assert stats["non_leak_cams"] == 1       # Beach (A)
    assert stats["bootstrap_hints"] == 3
    assert stats["pixel_observations"] == 6


def test_migrate_output_loads_with_solver_io(tmp_path: Path):
    """Migrated files must be valid input for the solver.io loaders."""
    legacy = _make_fake_legacy(tmp_path)
    output = tmp_path / "out"
    migrate(legacy, output, verbose=False)

    obs = load_observations(output)
    meas = load_measurements(output)

    # Verify content
    assert "Diner" in obs.pixels
    assert obs.pixels["Diner"]["LM_A"].pixel == (500.0, 600.0)

    assert "Diner" in meas.leak_cams
    assert meas.leak_cams["Diner"].xyz == (100.5, 200.3, 5.0)
    assert meas.leak_cams["Diner"].fov == 59.86
    assert meas.leak_cams["Diner"].image_size == (1824, 1080)

    assert "Beach (A)" in meas.non_leak_cam_meta
    assert meas.non_leak_cam_meta["Beach (A)"].image_size == (1920, 1080)

    assert "Diner" in meas.bootstrap_hints
    assert meas.bootstrap_hints["Diner"].yaw == 180.5
    assert meas.bootstrap_hints["Diner"].pitch == -5.2


def test_migrate_missing_legacy_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        migrate(tmp_path / "nonexistent", tmp_path / "out", verbose=False)


def test_find_procedural_candidates(tmp_path: Path):
    legacy = _make_fake_legacy(tmp_path)
    cand = find_procedural_candidates(legacy)
    assert "1000 Venetian Way (W1)" in cand["venetian_paliers"]
    assert "1000 Venetian Way (W2)" in cand["venetian_paliers"]
    assert "Portofino Tower (B-frontL-NW)" in cand["portofino_sub_corners"]


def test_find_z_zero_candidates(tmp_path: Path):
    legacy = _make_fake_legacy(tmp_path)
    cand = find_z_zero_candidates(legacy)
    # Default keywords look for "sea level", which matches "Sea Level (Beach)"
    assert "Sea Level (Beach)" in cand


def test_migrate_writes_empty_stubs(tmp_path: Path):
    """Sections we don't migrate should still get empty stub files."""
    legacy = _make_fake_legacy(tmp_path)
    output = tmp_path / "out"
    migrate(legacy, output, verbose=False)

    # These should be {} but exist
    for sub in [
        "observations/horizons.json",
        "measurements/z_constraints.json",
        "measurements/procedural_lms.json",
        "measurements/geometry_priors.json",
    ]:
        path = output / sub
        assert path.exists(), f"Missing stub: {sub}"
        data = json.loads(path.read_text())
        assert data == {}, f"{sub} should be empty"

