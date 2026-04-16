"""
gtamapdata.py — loads from JSON files in gtamapdata/
Drop-in replacement for the hardcoded dict version.
"""

import json
import os
import zipfile

DIRNAME = os.path.dirname(__file__)
DATA_DIR = os.path.join(DIRNAME, "gtamapdata")
LANDMARK_ZONES = [
    "vice_city", "ambrosia", "grassrivers", "leonida_keys",
    "port_gellhorn", "leonard_county"
]

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
landmarks_meta = {}  # source_cameras + error_m, keyed by landmark name

for zone in LANDMARK_ZONES:
    zone_data = _load(f"landmarks/{zone}.json")
    for lm_name, data in zone_data.items():
        landmarks[lm_name] = tuple(data["xyz"])
        landmarks_meta[lm_name] = {
            "source_cameras": data.get("source_cameras", []),
            "error_m": data.get("error_m"),
            "zone": zone,
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


def update_landmark(lm_name, xyz, source_cameras=None, error_m=None, zone=None):
    """
    Updates a landmark in memory and persists to the appropriate JSON file.
    """
    landmarks[lm_name] = tuple(xyz)

    # Determine zone
    if zone is None:
        if lm_name in landmarks_meta:
            zone = landmarks_meta[lm_name]["zone"]
        else:
            zone = "misc"

    landmarks_meta[lm_name] = {
        "source_cameras": source_cameras or [],
        "error_m": error_m,
        "zone": zone,
    }

    # Persist to JSON
    zone_path = os.path.join(DATA_DIR, f"landmarks/{zone}.json")
    with open(zone_path) as f:
        zone_data = json.load(f)
    zone_data[lm_name] = {
        "xyz": list(xyz),
        "source_cameras": source_cameras or [],
        "error_m": error_m,
    }
    tmp = zone_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(zone_data, f, indent=2)
    os.replace(tmp, zone_path)


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
