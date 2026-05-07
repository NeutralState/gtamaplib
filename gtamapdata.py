"""
gtamapdata.py — loads from JSON files in gtamapdata/
Drop-in replacement for the hardcoded dict version.
"""

import json
import os
import zipfile

DIRNAME = os.path.dirname(__file__)
DATA_DIR = os.path.join(DIRNAME, "gtamapdata")
for name in ("fonts", "frames", "maps"):
    dirname = f"{DIRNAME}/{name}"
    filename = f"{DIRNAME}/{name}.zip"
    if not os.path.exists(dirname) and os.path.exists(filename):
        print(f"Extracting {name}", end=" ... ", flush=True)
        with zipfile.ZipFile(filename) as z:
            z.extractall(dirname)
        print("Done")


def _load(filename):
    with open(os.path.join(DATA_DIR, filename)) as f:
        return json.load(f)


# ── Cameras ──────────────────────────────────────────────────────────────────

_cameras_raw = _load("cameras.json")

cameras = {
    name: {
        "id": data["id"],
        "player": tuple(data["player"]) if data["player"] else None,
        "xyz": tuple(data["xyz"]) if data["xyz"] else None,
        "ypr": tuple(data["ypr"]) if data["ypr"] else None,
        "fov": tuple(data["fov"]) if data["fov"] else None,
        "size": tuple(data["size"]) if data["size"] else None,
        "source": data["source"],
    }
    for name, data in _cameras_raw.items()
}

# ── Metadata ─────────────────────────────────────────────────────────────────

metadata = _load("metadata.json")

# ── Pixels ───────────────────────────────────────────────────────────────────

_pixels_raw = _load("pixels.json")

pixels = {
    cam_name: {
        lm_name: tuple(xy)
        for lm_name, xy in pixel_dict.items()
    }
    for cam_name, pixel_dict in _pixels_raw.items()
}

# ── Landmarks ────────────────────────────────────────────────────────────────

landmarks = {}
landmarks_meta = {}  # source_cameras + error_m + zone, keyed by landmark name

_landmarks_raw = _load("landmarks.json")
for lm_name, data in _landmarks_raw.items():
    xyz = data.get("xyz")
    landmarks[lm_name] = tuple(xyz) if xyz is not None else None
    landmarks_meta[lm_name] = {
        "source_cameras": data.get("source_cameras", []),
        "error_m": data.get("error_m"),
        "zone": data.get("zone", "unknown"),
        # z_constraint: None | {"type": "fixed", "value": <float>}
        # When set to a fixed value, the solver and triangulation respect it.
        # See tools/audit/find_z_candidates.py and tools/refine/apply_z_constraints.py.
        "z_constraint": data.get("z_constraint"),
    }

# ── Maps ─────────────────────────────────────────────────────────────────────

maps = _load("maps.json")
for name, data in maps.items():
    data["zero"] = tuple(data["zero"])

# ── Map sections ─────────────────────────────────────────────────────────────

map_sections = {
    name: tuple(bounds)
    for name, bounds in _load("map_sections.json").items()
}


# ── Helpers ──────────────────────────────────────────────────────────────────

_SENTINEL = object()  # marker for "argument not passed" in update_landmark()


def get_independent_landmarks(cam_name):
    """
    Returns landmark names that were NOT triangulated using cam_name.
    Safe to use as calibration constraints for that camera.
    """
    return [
        lm_name for lm_name, meta in landmarks_meta.items()
        if cam_name not in meta["source_cameras"]
        and lm_name in landmarks
    ]


def get_landmark_sources(lm_name):
    """Returns the source cameras used to triangulate a landmark."""
    return landmarks_meta.get(lm_name, {}).get("source_cameras", [])


def update_landmark(lm_name, xyz, source_cameras=None, error_m=None, zone=None,
                    z_constraint=_SENTINEL):
    """
    Updates a landmark in memory and persists to landmarks.json.

    Preserves any field not explicitly passed (z_constraint, author, etc).
    To explicitly clear z_constraint, pass z_constraint=None.

    If z_constraint = {"type": "fixed", "value": V}, snaps xyz[2] to V before
    persisting (single source of truth — JSON xyz always matches the constraint).

    Handles xyz=None for landmarks without triangulation yet.
    """
    # Read existing JSON to preserve untouched fields
    lm_path = os.path.join(DATA_DIR, "landmarks.json")
    with open(lm_path) as f:
        lm_data = json.load(f)
    existing = lm_data.get(lm_name, {})

    # Determine final z_constraint (sentinel = "not passed = preserve existing")
    if z_constraint is _SENTINEL:
        final_z_constraint = existing.get("z_constraint")
    else:
        final_z_constraint = z_constraint

    # Snap xyz[2] to fixed-z value if applicable (single source of truth)
    if xyz is not None and final_z_constraint and \
            final_z_constraint.get("type") == "fixed":
        xyz = list(xyz)
        xyz[2] = float(final_z_constraint["value"])

    landmarks[lm_name] = tuple(xyz) if xyz is not None else None

    # Determine zone
    if zone is None:
        if lm_name in landmarks_meta:
            zone = landmarks_meta[lm_name]["zone"]
        else:
            zone = existing.get("zone", "misc")

    landmarks_meta[lm_name] = {
        "source_cameras": source_cameras if source_cameras is not None
                          else existing.get("source_cameras", []),
        "error_m": error_m if error_m is not None else existing.get("error_m"),
        "zone": zone,
        "z_constraint": final_z_constraint,
    }

    # Build the JSON record, preserving fields we don't touch (e.g. author)
    new_record = dict(existing)  # start from existing to preserve all fields
    new_record["xyz"] = list(xyz) if xyz is not None else None
    if source_cameras is not None:
        new_record["source_cameras"] = source_cameras
    elif "source_cameras" not in new_record:
        new_record["source_cameras"] = []
    new_record["error_m"] = error_m if error_m is not None else new_record.get("error_m")
    new_record["zone"] = zone
    if final_z_constraint is None:
        new_record.pop("z_constraint", None)
    else:
        new_record["z_constraint"] = final_z_constraint

    lm_data[lm_name] = new_record
    tmp = lm_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(lm_data, f, indent=2)
    os.replace(tmp, lm_path)


def update_camera(cam_name, xyz=None, ypr=None, fov=None):
    """
    Updates a camera position in memory and persists to cameras.json.
    """
    if cam_name not in cameras:
        return
    if xyz: cameras[cam_name]["xyz"] = tuple(xyz)
    if ypr: cameras[cam_name]["ypr"] = tuple(ypr)
    if fov: cameras[cam_name]["fov"] = tuple(fov)

    cam_path = os.path.join(DATA_DIR, "cameras.json")
    with open(cam_path) as f:
        cam_data = json.load(f)
    cam_data[cam_name] = {
        k: list(v) if isinstance(v, tuple) else v
        for k, v in cameras[cam_name].items()
    }
    tmp = cam_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cam_data, f, indent=2)
    os.replace(tmp, cam_path)

# Lines not yet migrated to JSON
lines = {}
