"""
Migration script: gtamapdata.py -> JSON files
Run from gtamaplib-main directory.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gtamapdata as md

OUTPUT_DIR = "gtamapdata"
os.makedirs(f"{OUTPUT_DIR}/landmarks", exist_ok=True)

def to_list(val):
    if isinstance(val, (list, tuple)):
        return [to_list(v) for v in val]
    return val

# ── 1. cameras.json ──────────────────────────────────────────────────────────
cameras_out = {}
for name, data in md.cameras.items():
    cameras_out[name] = {
        "id": data.get("id"),
        "player": to_list(data.get("player")),
        "xyz": to_list(data.get("xyz")),
        "ypr": to_list(data.get("ypr")),
        "fov": to_list(data.get("fov")),
        "size": to_list(data.get("size")),
        "source": data.get("source"),
    }
with open(f"{OUTPUT_DIR}/cameras.json", "w") as f:
    json.dump(cameras_out, f, indent=2)
print(f"cameras.json: {len(cameras_out)} cameras")

# ── 2. metadata.json ─────────────────────────────────────────────────────────
metadata_out = {}
for name, data in md.metadata.items():
    metadata_out[name] = {
        "id": data.get("id"),
        "version": data.get("version"),
        "region": to_list(data.get("region")),
        "time": data.get("time"),
        "weather": to_list(data.get("weather")),
        "unknown": to_list(data.get("unknown")),
        "temperature": data.get("temperature"),
    }
with open(f"{OUTPUT_DIR}/metadata.json", "w") as f:
    json.dump(metadata_out, f, indent=2)
print(f"metadata.json: {len(metadata_out)} entries")

# ── 3. pixels.json ───────────────────────────────────────────────────────────
pixels_out = {}
for cam_name, pixel_dict in md.pixels.items():
    pixels_out[cam_name] = {
        lm_name: to_list(px)
        for lm_name, px in pixel_dict.items()
    }
with open(f"{OUTPUT_DIR}/pixels.json", "w") as f:
    json.dump(pixels_out, f, indent=2)
print(f"pixels.json: {len(pixels_out)} cameras")

# ── 4. maps.json & map_sections.json ─────────────────────────────────────────
maps_out = {}
for name, data in md.maps.items():
    maps_out[name] = {
        "version": data["version"],
        "scale": data["scale"],
        "zero": to_list(data["zero"]),
        "filename": data["filename"],
    }
with open(f"{OUTPUT_DIR}/maps.json", "w") as f:
    json.dump(maps_out, f, indent=2)
print(f"maps.json: {len(maps_out)} maps")

map_sections_out = {
    name: list(bounds)
    for name, bounds in md.map_sections.items()
}
with open(f"{OUTPUT_DIR}/map_sections.json", "w") as f:
    json.dump(map_sections_out, f, indent=2)
print(f"map_sections.json: {len(map_sections_out)} sections")

# ── 5. landmarks/ (split by zone) ────────────────────────────────────────────
# Load existing source_cameras and error_m from current JSON files
landmark_sources = {}
import glob
for json_file in glob.glob(f"{OUTPUT_DIR}/landmarks/*.json"):
    with open(json_file) as f:
        zone_data = json.load(f)
    for lm_name, data in zone_data.items():
        landmark_sources[lm_name] = {
            "source_cameras": data.get("source_cameras", []),
            "error_m": data.get("error_m"),
        }

def get_zone(name, xyz):
    x, y, z = xyz
    if x < -4000 and y > 1000:
        return "port_gellhorn"
    if y < -4000:
        return "leonida_keys"
    if -4000 <= y < -2000 and x < -1000:
        return "grassrivers"
    if x < -2000 and y > 2000:
        return "ambrosia"
    if y > 4000:
        return "leonard_county"
    return "vice_city"

zones = {
    "vice_city": {},
    "ambrosia": {},
    "grassrivers": {},
    "leonida_keys": {},
    "port_gellhorn": {},
    "leonard_county": {},
}

for lm_name, xyz in md.landmarks.items():
    zone = get_zone(lm_name, xyz)
    src = landmark_sources.get(lm_name, {})
    zones[zone][lm_name] = {
        "xyz": list(xyz),
        "source_cameras": src.get("source_cameras", []),
        "error_m": src.get("error_m"),
    }

for zone_name, landmarks in zones.items():
    with open(f"{OUTPUT_DIR}/landmarks/{zone_name}.json", "w") as f:
        json.dump(landmarks, f, indent=2)
    print(f"landmarks/{zone_name}.json: {len(landmarks)} landmarks")

total = sum(len(v) for v in zones.values())
print(f"\nTotal landmarks: {total}")
print(f"Total in gtamapdata: {len(md.landmarks)}")
print("Done!")
