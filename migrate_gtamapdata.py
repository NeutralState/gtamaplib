"""
Migration script: gtamapdata.py -> JSON files

Output structure:
  gtamapdata/
    cameras.json
    metadata.json
    maps.json
    map_sections.json
    pixels.json
    landmarks/
      vice_city.json
      ambrosia.json
      leonida_keys.json
      port_gellhorn.json
      leonard_county.json
      misc.json
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Load gtamapdata ──────────────────────────────────────────────────────────

import gtamapdata as md

OUTPUT_DIR = "gtamapdata"
os.makedirs(f"{OUTPUT_DIR}/landmarks", exist_ok=True)

# ── Helper ───────────────────────────────────────────────────────────────────

def to_list(val):
    """Convert tuples to lists recursively for JSON serialization."""
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

# Parse source cameras from inline comments in gtamapdata.py
landmark_sources = {}
with open("gtamapdata.py", "r") as f:
    content = f.read()

# Match: "landmark name": (x, y, z),  # [d=X.XXX ]via CamA[ & CamB]
pattern = re.compile(
    r'"([^"]+)":\s*\([^)]+\)[^#\n]*#([^\n]+)'
)
for match in pattern.finditer(content):
    lm_name = match.group(1)
    comment = match.group(2).strip()

    # Parse error distance
    error_m = None
    d_match = re.search(r'd=([\d.]+)', comment)
    if d_match:
        error_m = float(d_match.group(1))

    # Parse source cameras
    via_match = re.search(r'via (.+)', comment)
    source_cameras = []
    if via_match:
        raw = via_match.group(1).strip()
        source_cameras = [c.strip() for c in raw.split("&")]
    elif "Gizmo" in comment:
        source_cameras = ["Gizmo"]
    elif comment.strip():
        source_cameras = [comment.strip()]

    landmark_sources[lm_name] = {
        "source_cameras": source_cameras,
        "error_m": error_m,
    }

# Zone assignment based on world coordinates
def get_zone(name, xyz):
    x, y, z = xyz
    # Port Gellhorn: far west
    if x < -4000 and y > 1000:
        return "port_gellhorn"
    # Leonida Keys: far south
    if y < -3000:
        return "leonida_keys"
    # Ambrosia: north-west mid
    if x < -2000 and y > 2000:
        return "ambrosia"
    # Leonard County: far north
    if y > 4000:
        return "leonard_county"
    # Vice City: the main area
    if -2000 <= x <= 2500 and -2000 <= y <= 2500:
        return "vice_city"
    return "misc"

zones = {
    "vice_city": {},
    "ambrosia": {},
    "leonida_keys": {},
    "port_gellhorn": {},
    "leonard_county": {},
    "misc": {},
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

print(f"\nTotal landmarks: {sum(len(v) for v in zones.values())}")
print(f"Total in gtamapdata: {len(md.landmarks)}")
print("\nDone!")
