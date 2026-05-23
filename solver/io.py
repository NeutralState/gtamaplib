"""
I/O layer for the solver.

Responsibilities:
  - Load observations + measurements + state from disk
  - Validate JSON schemas with clear error messages
  - Save inferences (state, convergence report, provenance) atomically

Design principles:
  - All loaders return immutable dataclasses
  - Validation errors are specific: they name the file, the path inside
    the JSON, and what was wrong
  - Atomic writes via temp-then-rename: no partial state ever lands on disk
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


# ----------------------------------------------------------------------
# Validation errors
# ----------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when loaded JSON doesn't match expected schema.

    Attributes:
        file: path to the file that failed validation
        json_path: dotted path within the JSON where the error is
        message: human-readable explanation
    """

    def __init__(self, file: str, json_path: str, message: str):
        self.file = file
        self.json_path = json_path
        self.message = message
        full = f"[{file}] at {json_path or '<root>'}: {message}"
        super().__init__(full)


def _validate(
    cond: bool, file: str, json_path: str, message: str,
) -> None:
    """Raise ValidationError if cond is falsy."""
    if not cond:
        raise ValidationError(file, json_path, message)


# ----------------------------------------------------------------------
# Dataclasses
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class PixelObservation:
    """A single pixel marking by a human."""
    pixel: Tuple[float, float]
    confidence: float = 1.0
    marked_at: Optional[str] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class HorizonObservation:
    """A horizon line drawn by a human, used for pitch+roll bootstrap."""
    left_pixel: Tuple[float, float]
    right_pixel: Tuple[float, float]
    confidence: float = 1.0


@dataclass(frozen=True)
class Observations:
    """All human-marked observations.

    pixels[cam_name][lm_name] = PixelObservation
    horizons[cam_name] = HorizonObservation (optional, only some cams have one)
    """
    pixels: Dict[str, Dict[str, PixelObservation]] = field(default_factory=dict)
    horizons: Dict[str, HorizonObservation] = field(default_factory=dict)


@dataclass(frozen=True)
class LeakCamMeasurement:
    """A leak cam with known xyz + fov (from GTA console)."""
    xyz: Tuple[float, float, float]
    fov: float
    source: str
    image_size: Tuple[int, int]
    image_path: Optional[str] = None


@dataclass(frozen=True)
class ZConstraint:
    """A z-coordinate constraint for a landmark."""
    z: float
    reason: str = ""


@dataclass(frozen=True)
class ProceduralLM:
    """A landmark whose xyz is computed from other LMs via a generator."""
    generator: str
    params: Dict[str, Any]
    depends_on: List[str]


@dataclass(frozen=True)
class GeometryPrior:
    """A geometric constraint between LMs."""
    type: str   # "distance", "vertical", "colinear", "coplanar"
    lms: List[str]
    value: Optional[float] = None
    weight: float = 1.0


@dataclass(frozen=True)
class BootstrapHint:
    """A rough ypr guess for a leak cam, used during bootstrap."""
    yaw: float
    pitch: float
    roll: float
    confidence: float = 0.5
    reason: str = ""


@dataclass(frozen=True)
class NonLeakCamMeta:
    """Metadata about a non-leak cam (image size, etc.)."""
    image_size: Tuple[int, int]
    image_path: Optional[str] = None


@dataclass(frozen=True)
class Measurements:
    """All external measurements."""
    leak_cams: Dict[str, LeakCamMeasurement] = field(default_factory=dict)
    z_constraints: Dict[str, ZConstraint] = field(default_factory=dict)
    procedural_lms: Dict[str, ProceduralLM] = field(default_factory=dict)
    geometry_priors: Dict[str, GeometryPrior] = field(default_factory=dict)
    bootstrap_hints: Dict[str, BootstrapHint] = field(default_factory=dict)
    non_leak_cam_meta: Dict[str, NonLeakCamMeta] = field(default_factory=dict)


@dataclass(frozen=True)
class SolvedCamera:
    """A camera as resolved by the solver."""
    kind: str  # "leak" or "non_leak"
    xyz: Tuple[float, float, float]
    ypr: Tuple[float, float, float]
    fov: float
    loss_arcmin: Optional[float] = None
    n_constraints: int = 0


@dataclass(frozen=True)
class SolvedLandmark:
    """A landmark as resolved by the solver."""
    kind: str  # "pixel_anchored" or "procedural"
    xyz: Tuple[float, float, float]
    error_m: Optional[float] = None
    n_observers: int = 0
    computed_from: Optional[str] = None


@dataclass(frozen=True)
class GlobalMetrics:
    rms_loss_arcmin: float
    median_loss_arcmin: float
    p99_loss_arcmin: float
    total_observations: int
    outlier_count_above_20_arcmin: int


@dataclass(frozen=True)
class State:
    """The complete solved world: output of the solver."""
    solver_version: str
    solved_at: str
    input_hash: str
    cameras: Dict[str, SolvedCamera] = field(default_factory=dict)
    landmarks: Dict[str, SolvedLandmark] = field(default_factory=dict)
    global_metrics: Optional[GlobalMetrics] = None


# ----------------------------------------------------------------------
# JSON loaders
# ----------------------------------------------------------------------

def _read_json(path: Path) -> Any:
    """Read JSON from path. Returns {} for missing or empty files."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        return {}
    return json.loads(text)


def _ensure_pixel_pair(value: Any, file: str, path: str) -> Tuple[float, float]:
    _validate(isinstance(value, (list, tuple)), file, path, "expected a [x, y] pair")
    _validate(len(value) == 2, file, path, f"expected length 2, got {len(value)}")
    _validate(all(isinstance(v, (int, float)) for v in value), file, path,
              "pixel values must be numbers")
    return (float(value[0]), float(value[1]))


def _ensure_xyz(value: Any, file: str, path: str) -> Tuple[float, float, float]:
    _validate(isinstance(value, (list, tuple)), file, path, "expected an [x, y, z] triple")
    _validate(len(value) == 3, file, path, f"expected length 3, got {len(value)}")
    _validate(all(isinstance(v, (int, float)) for v in value), file, path,
              "xyz values must be numbers")
    return (float(value[0]), float(value[1]), float(value[2]))


def _ensure_size(value: Any, file: str, path: str) -> Tuple[int, int]:
    _validate(isinstance(value, (list, tuple)), file, path,
              "expected [width, height]")
    _validate(len(value) == 2, file, path, f"expected length 2, got {len(value)}")
    _validate(all(isinstance(v, int) and v > 0 for v in value), file, path,
              "image_size must be positive integers")
    return (int(value[0]), int(value[1]))


def load_observations(input_dir: Union[str, Path]) -> Observations:
    """Load observations/pixels.json and observations/horizons.json (if present).

    Returns an Observations dataclass. Missing files are treated as empty.
    """
    input_dir = Path(input_dir)

    pixels_path = input_dir / "observations" / "pixels.json"
    pixels_raw = _read_json(pixels_path)
    file = str(pixels_path)
    _validate(isinstance(pixels_raw, dict), file, "",
              f"top-level must be an object, got {type(pixels_raw).__name__}")

    pixels: Dict[str, Dict[str, PixelObservation]] = {}
    for cam_name, lm_map in pixels_raw.items():
        _validate(isinstance(lm_map, dict), file, cam_name,
                  "expected an object of landmark->observation")
        cam_pixels: Dict[str, PixelObservation] = {}
        for lm_name, obs in lm_map.items():
            path = f"{cam_name}.{lm_name}"
            _validate(isinstance(obs, dict), file, path, "expected an object")
            _validate("pixel" in obs, file, path, "missing 'pixel' field")
            pix = _ensure_pixel_pair(obs["pixel"], file, f"{path}.pixel")
            conf = float(obs.get("confidence", 1.0))
            _validate(0.0 <= conf <= 1.0, file, f"{path}.confidence",
                      f"confidence must be in [0, 1], got {conf}")
            cam_pixels[lm_name] = PixelObservation(
                pixel=pix,
                confidence=conf,
                marked_at=obs.get("marked_at"),
                note=obs.get("note"),
            )
        pixels[cam_name] = cam_pixels

    horizons_path = input_dir / "observations" / "horizons.json"
    horizons_raw = _read_json(horizons_path)
    file = str(horizons_path)
    _validate(isinstance(horizons_raw, dict), file, "",
              f"top-level must be an object, got {type(horizons_raw).__name__}")

    horizons: Dict[str, HorizonObservation] = {}
    for cam_name, obs in horizons_raw.items():
        path = cam_name
        _validate(isinstance(obs, dict), file, path, "expected an object")
        _validate("left_pixel" in obs and "right_pixel" in obs, file, path,
                  "missing 'left_pixel' or 'right_pixel'")
        left = _ensure_pixel_pair(obs["left_pixel"], file, f"{path}.left_pixel")
        right = _ensure_pixel_pair(obs["right_pixel"], file, f"{path}.right_pixel")
        conf = float(obs.get("confidence", 1.0))
        horizons[cam_name] = HorizonObservation(
            left_pixel=left, right_pixel=right, confidence=conf,
        )

    return Observations(pixels=pixels, horizons=horizons)


def load_measurements(input_dir: Union[str, Path]) -> Measurements:
    """Load all measurement files. Missing files are treated as empty."""
    input_dir = Path(input_dir)
    mdir = input_dir / "measurements"

    # leak_cams.json
    raw = _read_json(mdir / "leak_cams.json")
    file = str(mdir / "leak_cams.json")
    _validate(isinstance(raw, dict), file, "", "top-level must be an object")
    leak_cams: Dict[str, LeakCamMeasurement] = {}
    for name, entry in raw.items():
        path = name
        _validate(isinstance(entry, dict), file, path, "expected an object")
        _validate("xyz" in entry, file, path, "missing 'xyz'")
        _validate("fov" in entry, file, path, "missing 'fov'")
        _validate("image_size" in entry, file, path, "missing 'image_size'")
        xyz = _ensure_xyz(entry["xyz"], file, f"{path}.xyz")
        fov = float(entry["fov"])
        _validate(1.0 < fov < 180.0, file, f"{path}.fov",
                  f"fov should be in (1, 180) degrees, got {fov}")
        size = _ensure_size(entry["image_size"], file, f"{path}.image_size")
        leak_cams[name] = LeakCamMeasurement(
            xyz=xyz, fov=fov, source=entry.get("source", ""),
            image_size=size, image_path=entry.get("image_path"),
        )

    # z_constraints.json
    raw = _read_json(mdir / "z_constraints.json")
    file = str(mdir / "z_constraints.json")
    _validate(isinstance(raw, dict), file, "", "top-level must be an object")
    z_constraints: Dict[str, ZConstraint] = {}
    for name, entry in raw.items():
        path = name
        _validate(isinstance(entry, dict), file, path, "expected an object")
        _validate("z" in entry, file, path, "missing 'z'")
        _validate(isinstance(entry["z"], (int, float)), file, f"{path}.z",
                  "z must be a number")
        z_constraints[name] = ZConstraint(
            z=float(entry["z"]),
            reason=entry.get("reason", ""),
        )

    # procedural_lms.json
    raw = _read_json(mdir / "procedural_lms.json")
    file = str(mdir / "procedural_lms.json")
    _validate(isinstance(raw, dict), file, "", "top-level must be an object")
    procedural_lms: Dict[str, ProceduralLM] = {}
    for name, entry in raw.items():
        path = name
        _validate(isinstance(entry, dict), file, path, "expected an object")
        _validate("generator" in entry, file, path, "missing 'generator'")
        _validate("depends_on" in entry, file, path, "missing 'depends_on'")
        _validate(isinstance(entry["depends_on"], list), file,
                  f"{path}.depends_on", "must be a list")
        procedural_lms[name] = ProceduralLM(
            generator=str(entry["generator"]),
            params=dict(entry.get("params", {})),
            depends_on=[str(s) for s in entry["depends_on"]],
        )

    # geometry_priors.json
    raw = _read_json(mdir / "geometry_priors.json")
    file = str(mdir / "geometry_priors.json")
    _validate(isinstance(raw, dict), file, "", "top-level must be an object")
    geometry_priors: Dict[str, GeometryPrior] = {}
    for name, entry in raw.items():
        path = name
        _validate(isinstance(entry, dict), file, path, "expected an object")
        _validate("type" in entry, file, path, "missing 'type'")
        _validate("lms" in entry, file, path, "missing 'lms'")
        _validate(isinstance(entry["lms"], list), file, f"{path}.lms",
                  "must be a list")
        geometry_priors[name] = GeometryPrior(
            type=str(entry["type"]),
            lms=[str(s) for s in entry["lms"]],
            value=float(entry["value"]) if "value" in entry else None,
            weight=float(entry.get("weight", 1.0)),
        )

    # bootstrap_hints.json
    raw = _read_json(mdir / "bootstrap_hints.json")
    file = str(mdir / "bootstrap_hints.json")
    _validate(isinstance(raw, dict), file, "", "top-level must be an object")
    bootstrap_hints: Dict[str, BootstrapHint] = {}
    for name, entry in raw.items():
        path = name
        _validate(isinstance(entry, dict), file, path, "expected an object")
        for k in ("yaw", "pitch", "roll"):
            _validate(k in entry, file, path, f"missing '{k}'")
        bootstrap_hints[name] = BootstrapHint(
            yaw=float(entry["yaw"]),
            pitch=float(entry["pitch"]),
            roll=float(entry["roll"]),
            confidence=float(entry.get("confidence", 0.5)),
            reason=entry.get("reason", ""),
        )

    # non_leak_cam_meta.json
    raw = _read_json(mdir / "non_leak_cam_meta.json")
    file = str(mdir / "non_leak_cam_meta.json")
    _validate(isinstance(raw, dict), file, "", "top-level must be an object")
    non_leak_cam_meta: Dict[str, NonLeakCamMeta] = {}
    for name, entry in raw.items():
        path = name
        _validate(isinstance(entry, dict), file, path, "expected an object")
        _validate("image_size" in entry, file, path, "missing 'image_size'")
        size = _ensure_size(entry["image_size"], file, f"{path}.image_size")
        non_leak_cam_meta[name] = NonLeakCamMeta(
            image_size=size, image_path=entry.get("image_path"),
        )

    return Measurements(
        leak_cams=leak_cams,
        z_constraints=z_constraints,
        procedural_lms=procedural_lms,
        geometry_priors=geometry_priors,
        bootstrap_hints=bootstrap_hints,
        non_leak_cam_meta=non_leak_cam_meta,
    )


def load_state(input_dir: Union[str, Path]) -> Optional[State]:
    """Load inferences/state.json if it exists. Returns None otherwise."""
    input_dir = Path(input_dir)
    path = input_dir / "inferences" / "state.json"
    if not path.exists():
        return None
    raw = _read_json(path)
    file = str(path)
    _validate(isinstance(raw, dict), file, "", "top-level must be an object")

    cams_raw = raw.get("cameras", {})
    cameras: Dict[str, SolvedCamera] = {}
    for name, entry in cams_raw.items():
        path_str = f"cameras.{name}"
        _validate(isinstance(entry, dict), file, path_str, "expected object")
        cameras[name] = SolvedCamera(
            kind=str(entry["kind"]),
            xyz=_ensure_xyz(entry["xyz"], file, f"{path_str}.xyz"),
            ypr=tuple(float(v) for v in entry["ypr"]),  # type: ignore[arg-type]
            fov=float(entry["fov"]),
            loss_arcmin=entry.get("loss_arcmin"),
            n_constraints=int(entry.get("n_constraints", 0)),
        )

    lms_raw = raw.get("landmarks", {})
    landmarks: Dict[str, SolvedLandmark] = {}
    for name, entry in lms_raw.items():
        path_str = f"landmarks.{name}"
        _validate(isinstance(entry, dict), file, path_str, "expected object")
        landmarks[name] = SolvedLandmark(
            kind=str(entry["kind"]),
            xyz=_ensure_xyz(entry["xyz"], file, f"{path_str}.xyz"),
            error_m=entry.get("error_m"),
            n_observers=int(entry.get("n_observers", 0)),
            computed_from=entry.get("computed_from"),
        )

    gm_raw = raw.get("global_metrics")
    global_metrics = None
    if gm_raw is not None:
        global_metrics = GlobalMetrics(
            rms_loss_arcmin=float(gm_raw["rms_loss_arcmin"]),
            median_loss_arcmin=float(gm_raw["median_loss_arcmin"]),
            p99_loss_arcmin=float(gm_raw["p99_loss_arcmin"]),
            total_observations=int(gm_raw["total_observations"]),
            outlier_count_above_20_arcmin=int(gm_raw["outlier_count_above_20_arcmin"]),
        )

    return State(
        solver_version=str(raw.get("solver_version", "")),
        solved_at=str(raw.get("solved_at", "")),
        input_hash=str(raw.get("input_hash", "")),
        cameras=cameras,
        landmarks=landmarks,
        global_metrics=global_metrics,
    )


# ----------------------------------------------------------------------
# Atomic writers
# ----------------------------------------------------------------------

def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON atomically: write to a temp file in the same dir, then rename.

    POSIX rename is atomic within a single filesystem, so readers either see
    the old file or the new file but never a partial write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=False)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        # Clean up the temp file if something went wrong before rename
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _state_to_dict(state: State) -> Dict[str, Any]:
    """Serialize a State dataclass to a JSON-friendly dict."""
    return {
        "solver_version": state.solver_version,
        "solved_at": state.solved_at,
        "input_hash": state.input_hash,
        "cameras": {
            name: {
                "kind": c.kind,
                "xyz": list(c.xyz),
                "ypr": list(c.ypr),
                "fov": c.fov,
                "loss_arcmin": c.loss_arcmin,
                "n_constraints": c.n_constraints,
            }
            for name, c in state.cameras.items()
        },
        "landmarks": {
            name: {
                "kind": lm.kind,
                "xyz": list(lm.xyz),
                "error_m": lm.error_m,
                "n_observers": lm.n_observers,
                "computed_from": lm.computed_from,
            }
            for name, lm in state.landmarks.items()
        },
        "global_metrics": (
            None if state.global_metrics is None else asdict(state.global_metrics)
        ),
    }


def save_state(state: State, output_dir: Union[str, Path]) -> None:
    """Atomically write inferences/state.json."""
    output_dir = Path(output_dir)
    _atomic_write_json(output_dir / "inferences" / "state.json", _state_to_dict(state))


def save_convergence_report(
    report: Dict[str, Any], output_dir: Union[str, Path],
) -> None:
    """Atomically write inferences/convergence_report.json."""
    output_dir = Path(output_dir)
    _atomic_write_json(
        output_dir / "inferences" / "convergence_report.json", report,
    )


def save_provenance(
    provenance: Dict[str, Any], output_dir: Union[str, Path],
) -> None:
    """Atomically write inferences/provenance.json."""
    output_dir = Path(output_dir)
    _atomic_write_json(
        output_dir / "inferences" / "provenance.json", provenance,
    )


# ----------------------------------------------------------------------
# Input hash
# ----------------------------------------------------------------------

def compute_input_hash(input_dir: Union[str, Path]) -> str:
    """Compute a stable hash of observations + measurements.

    Used to detect whether a re-solve is needed.
    """
    input_dir = Path(input_dir)
    paths_to_hash = [
        input_dir / "observations" / "pixels.json",
        input_dir / "observations" / "horizons.json",
        input_dir / "measurements" / "leak_cams.json",
        input_dir / "measurements" / "z_constraints.json",
        input_dir / "measurements" / "procedural_lms.json",
        input_dir / "measurements" / "geometry_priors.json",
        input_dir / "measurements" / "bootstrap_hints.json",
        input_dir / "measurements" / "non_leak_cam_meta.json",
    ]

    h = hashlib.sha256()
    for p in paths_to_hash:
        # Include the file path itself in the hash so renames register as
        # changes. Order matters; keep paths_to_hash stable.
        h.update(p.name.encode("utf-8"))
        h.update(b"\x00")
        if p.exists():
            with open(p, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
        h.update(b"\x00")

    return "sha256:" + h.hexdigest()
