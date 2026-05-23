"""
Unit tests for solver.io.

Tests cover:
- Loading valid files
- Loading missing files (returns empty)
- Schema validation: each malformed input raises ValidationError with a
  clear message identifying the file and the path
- Saving state atomically (no partial writes if interrupted)
- Roundtrip: save then load yields the same dataclass
- Input hash is stable and changes only when inputs change
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest

from solver.io import (
    ValidationError,
    PixelObservation,
    Observations,
    LeakCamMeasurement,
    Measurements,
    SolvedCamera,
    SolvedLandmark,
    State,
    GlobalMetrics,
    load_observations,
    load_measurements,
    load_state,
    save_state,
    save_convergence_report,
    save_provenance,
    compute_input_hash,
)


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _scaffold_empty(root: Path) -> None:
    """Create empty observations/measurements/inferences dirs."""
    for sub in ("observations", "measurements", "inferences"):
        (root / sub).mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------
# Loading observations
# ----------------------------------------------------------------------

def test_load_observations_missing_dir(tmp_path: Path):
    """If observations/ doesn't exist, return empty Observations."""
    _scaffold_empty(tmp_path)
    obs = load_observations(tmp_path)
    assert obs.pixels == {}
    assert obs.horizons == {}


def test_load_observations_basic(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "observations" / "pixels.json", {
        "CamA": {
            "LM1": {"pixel": [100, 200]},
            "LM2": {"pixel": [300, 400], "confidence": 0.7, "note": "blurry"},
        },
        "CamB": {
            "LM1": {"pixel": [500.5, 600.5]},
        },
    })
    obs = load_observations(tmp_path)
    assert set(obs.pixels.keys()) == {"CamA", "CamB"}
    assert obs.pixels["CamA"]["LM1"].pixel == (100.0, 200.0)
    assert obs.pixels["CamA"]["LM1"].confidence == 1.0
    assert obs.pixels["CamA"]["LM2"].confidence == 0.7
    assert obs.pixels["CamA"]["LM2"].note == "blurry"
    assert obs.pixels["CamB"]["LM1"].pixel == (500.5, 600.5)


def test_load_observations_invalid_pixel_length(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "observations" / "pixels.json", {
        "CamA": {"LM1": {"pixel": [100, 200, 300]}},
    })
    with pytest.raises(ValidationError) as exc_info:
        load_observations(tmp_path)
    assert "CamA.LM1.pixel" in str(exc_info.value)
    assert "length 2" in str(exc_info.value)


def test_load_observations_missing_pixel_field(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "observations" / "pixels.json", {
        "CamA": {"LM1": {"confidence": 0.5}},
    })
    with pytest.raises(ValidationError) as exc_info:
        load_observations(tmp_path)
    assert "CamA.LM1" in str(exc_info.value)
    assert "missing 'pixel'" in str(exc_info.value)


def test_load_observations_invalid_confidence(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "observations" / "pixels.json", {
        "CamA": {"LM1": {"pixel": [10, 20], "confidence": 1.5}},
    })
    with pytest.raises(ValidationError) as exc_info:
        load_observations(tmp_path)
    assert "CamA.LM1.confidence" in str(exc_info.value)


def test_load_observations_top_level_not_object(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "observations" / "pixels.json", ["not", "an", "object"])
    with pytest.raises(ValidationError) as exc_info:
        load_observations(tmp_path)
    assert "top-level must be an object" in str(exc_info.value)


def test_load_observations_with_horizons(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "observations" / "pixels.json", {})
    _write_json(tmp_path / "observations" / "horizons.json", {
        "VicedBeach": {
            "left_pixel": [10, 412],
            "right_pixel": [1910, 408],
            "confidence": 0.9,
        },
    })
    obs = load_observations(tmp_path)
    assert "VicedBeach" in obs.horizons
    h = obs.horizons["VicedBeach"]
    assert h.left_pixel == (10.0, 412.0)
    assert h.right_pixel == (1910.0, 408.0)
    assert h.confidence == 0.9


# ----------------------------------------------------------------------
# Loading measurements
# ----------------------------------------------------------------------

def test_load_measurements_empty(tmp_path: Path):
    _scaffold_empty(tmp_path)
    m = load_measurements(tmp_path)
    assert m.leak_cams == {}
    assert m.z_constraints == {}
    assert m.procedural_lms == {}


def test_load_leak_cams_basic(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "measurements" / "leak_cams.json", {
        "Tennis Court (SE)": {
            "xyz": [-317.232, 1174.859, 5.021],
            "fov": 59.86,
            "source": "2022-09-01 14-37-21",
            "image_size": [1824, 1080],
        },
    })
    m = load_measurements(tmp_path)
    assert "Tennis Court (SE)" in m.leak_cams
    lc = m.leak_cams["Tennis Court (SE)"]
    assert lc.xyz == (-317.232, 1174.859, 5.021)
    assert lc.fov == 59.86
    assert lc.image_size == (1824, 1080)


def test_load_leak_cams_missing_fov(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "measurements" / "leak_cams.json", {
        "CamA": {"xyz": [0, 0, 0], "image_size": [1920, 1080]},
    })
    with pytest.raises(ValidationError) as exc_info:
        load_measurements(tmp_path)
    assert "CamA" in str(exc_info.value)
    assert "missing 'fov'" in str(exc_info.value)


def test_load_leak_cams_invalid_fov(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "measurements" / "leak_cams.json", {
        "CamA": {"xyz": [0, 0, 0], "fov": 200.0, "image_size": [1920, 1080]},
    })
    with pytest.raises(ValidationError) as exc_info:
        load_measurements(tmp_path)
    assert "CamA.fov" in str(exc_info.value)


def test_load_leak_cams_invalid_size(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "measurements" / "leak_cams.json", {
        "CamA": {"xyz": [0, 0, 0], "fov": 60.0, "image_size": [1920, 0]},
    })
    with pytest.raises(ValidationError) as exc_info:
        load_measurements(tmp_path)
    assert "image_size" in str(exc_info.value)


def test_load_z_constraints(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "measurements" / "z_constraints.json", {
        "Sea Level (Vice Beach)": {"z": 0.0, "reason": "ocean"},
        "1000 Venetian Way (W1)": {"z": 8.86},
    })
    m = load_measurements(tmp_path)
    assert m.z_constraints["Sea Level (Vice Beach)"].z == 0.0
    assert m.z_constraints["Sea Level (Vice Beach)"].reason == "ocean"
    assert m.z_constraints["1000 Venetian Way (W1)"].z == 8.86
    assert m.z_constraints["1000 Venetian Way (W1)"].reason == ""


def test_load_procedural_lms(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "measurements" / "procedural_lms.json", {
        "Portofino Tower (B-frontL-NW)": {
            "generator": "portofino.sub_corner",
            "params": {"face": "B-frontL", "side": "NW"},
            "depends_on": [
                "Portofino Tower (NW)",
                "Portofino Tower (NE)",
                "Portofino Tower (S)",
            ],
        },
    })
    m = load_measurements(tmp_path)
    p = m.procedural_lms["Portofino Tower (B-frontL-NW)"]
    assert p.generator == "portofino.sub_corner"
    assert p.params == {"face": "B-frontL", "side": "NW"}
    assert len(p.depends_on) == 3


def test_load_bootstrap_hints(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "measurements" / "bootstrap_hints.json", {
        "Tennis Court (SE)": {
            "yaw": 258.0,
            "pitch": -10.0,
            "roll": 0.0,
            "confidence": 0.3,
            "reason": "rough estimate",
        },
    })
    m = load_measurements(tmp_path)
    h = m.bootstrap_hints["Tennis Court (SE)"]
    assert h.yaw == 258.0
    assert h.pitch == -10.0
    assert h.confidence == 0.3


# ----------------------------------------------------------------------
# Loading state
# ----------------------------------------------------------------------

def test_load_state_missing_returns_none(tmp_path: Path):
    _scaffold_empty(tmp_path)
    assert load_state(tmp_path) is None


def test_load_state_basic(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "inferences" / "state.json", {
        "solver_version": "1.0.0",
        "solved_at": "2026-05-23T16:42:01Z",
        "input_hash": "sha256:abc123",
        "cameras": {
            "CamA": {
                "kind": "leak",
                "xyz": [10.0, 20.0, 30.0],
                "ypr": [45.0, -5.0, 0.0],
                "fov": 60.0,
                "loss_arcmin": 1.42,
                "n_constraints": 4,
            },
        },
        "landmarks": {
            "LM1": {
                "kind": "pixel_anchored",
                "xyz": [100.0, 200.0, 30.0],
                "error_m": 0.31,
                "n_observers": 5,
            },
        },
    })
    state = load_state(tmp_path)
    assert state is not None
    assert state.solver_version == "1.0.0"
    assert state.cameras["CamA"].kind == "leak"
    assert state.cameras["CamA"].ypr == (45.0, -5.0, 0.0)
    assert state.landmarks["LM1"].n_observers == 5


# ----------------------------------------------------------------------
# Save state (atomic)
# ----------------------------------------------------------------------

def test_save_state_roundtrip(tmp_path: Path):
    _scaffold_empty(tmp_path)
    state = State(
        solver_version="0.1.0",
        solved_at="2026-05-23T16:00:00Z",
        input_hash="sha256:deadbeef",
        cameras={
            "CamA": SolvedCamera(
                kind="leak",
                xyz=(10.0, 20.0, 30.0),
                ypr=(45.0, -5.0, 0.0),
                fov=60.0,
                loss_arcmin=1.42,
                n_constraints=4,
            ),
        },
        landmarks={
            "LM1": SolvedLandmark(
                kind="pixel_anchored",
                xyz=(100.0, 200.0, 30.0),
                error_m=0.31,
                n_observers=5,
            ),
        },
        global_metrics=GlobalMetrics(
            rms_loss_arcmin=1.57,
            median_loss_arcmin=0.46,
            p99_loss_arcmin=8.74,
            total_observations=1055,
            outlier_count_above_20_arcmin=2,
        ),
    )
    save_state(state, tmp_path)
    loaded = load_state(tmp_path)
    assert loaded is not None
    assert loaded.cameras == state.cameras
    assert loaded.landmarks == state.landmarks
    assert loaded.global_metrics == state.global_metrics


def test_save_state_no_temp_left_behind(tmp_path: Path):
    """After a successful save, no .tmp files should remain in inferences/."""
    _scaffold_empty(tmp_path)
    state = State(
        solver_version="0.1.0",
        solved_at="2026-05-23T16:00:00Z",
        input_hash="sha256:x",
    )
    save_state(state, tmp_path)
    inf_dir = tmp_path / "inferences"
    leftovers = list(inf_dir.glob("*.tmp"))
    assert leftovers == [], f"temp files remained: {leftovers}"
    leftovers2 = list(inf_dir.glob("state.json.*"))
    assert leftovers2 == [] or all(
        not str(p).endswith(".tmp") for p in leftovers2
    )


def test_save_convergence_and_provenance(tmp_path: Path):
    _scaffold_empty(tmp_path)
    save_convergence_report({"iterations": 12, "converged": True}, tmp_path)
    save_provenance({"landmarks": {}}, tmp_path)
    assert (tmp_path / "inferences" / "convergence_report.json").exists()
    assert (tmp_path / "inferences" / "provenance.json").exists()


# ----------------------------------------------------------------------
# Input hash
# ----------------------------------------------------------------------

def test_input_hash_stable(tmp_path: Path):
    """Same inputs produce the same hash."""
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "observations" / "pixels.json", {"A": {"L": {"pixel": [1, 2]}}})
    h1 = compute_input_hash(tmp_path)
    h2 = compute_input_hash(tmp_path)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_input_hash_changes_on_pixel_change(tmp_path: Path):
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "observations" / "pixels.json", {"A": {"L": {"pixel": [1, 2]}}})
    h1 = compute_input_hash(tmp_path)
    _write_json(tmp_path / "observations" / "pixels.json", {"A": {"L": {"pixel": [3, 4]}}})
    h2 = compute_input_hash(tmp_path)
    assert h1 != h2


def test_input_hash_independent_of_inferences(tmp_path: Path):
    """Hash should not change when inferences/state.json changes."""
    _scaffold_empty(tmp_path)
    _write_json(tmp_path / "observations" / "pixels.json", {"A": {"L": {"pixel": [1, 2]}}})
    h1 = compute_input_hash(tmp_path)

    # Write a state file (in inferences/, which is NOT part of the hash)
    save_state(
        State(solver_version="x", solved_at="y", input_hash="z"),
        tmp_path,
    )
    h2 = compute_input_hash(tmp_path)
    assert h1 == h2


def test_input_hash_with_all_files_missing(tmp_path: Path):
    """Even with no files present, hash should return a stable value."""
    _scaffold_empty(tmp_path)
    h = compute_input_hash(tmp_path)
    assert h.startswith("sha256:")
