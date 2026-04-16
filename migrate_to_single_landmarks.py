"""
migrate_to_single_landmarks.py

Merges all zone-based landmark JSON files into a single landmarks.json
in topological order. Zone info is preserved as a field in each entry.

Run after topo_sort_landmarks.py has been run.
"""

import json
import os

DATA_DIR = "gtamapdata"
ZONES = ["vice_city", "ambrosia", "grassrivers", "leonida_keys", "port_gellhorn", "leonard_county"]

# Load topo order
topo_order = []
with open("topo_order.txt") as f:
    for line in f:
        if line.strip().startswith("#") or not line.strip():
            continue
        # Parse: "   1. Landmark Name  [source]..."  or "  ??. ..."
        parts = line.split(".")
        if len(parts) < 2:
            continue
        rest = ".".join(parts[1:]).strip()
        name = rest.split("  [")[0].strip()
        topo_order.append(name)

print(f"Topo order: {len(topo_order)} landmarks")

# Load all landmark data from zone files
all_data = {}
for zone in ZONES:
    path = f"{DATA_DIR}/landmarks/{zone}.json"
    if not os.path.exists(path):
        continue
    with open(path) as f:
        zone_data = json.load(f)
    for name, entry in zone_data.items():
        all_data[name] = {**entry, "zone": zone}

print(f"Loaded {len(all_data)} landmarks from zone files")

# Build single ordered dict
landmarks_single = {}
for name in topo_order:
    if name in all_data:
        landmarks_single[name] = all_data[name]

# Add any missing (shouldn't happen but just in case)
for name, entry in all_data.items():
    if name not in landmarks_single:
        landmarks_single[name] = entry

print(f"Single file: {len(landmarks_single)} landmarks")

# Write landmarks.json
out_path = f"{DATA_DIR}/landmarks.json"
tmp = out_path + ".tmp"
with open(tmp, "w") as f:
    json.dump(landmarks_single, f, indent=2)
os.replace(tmp, out_path)
print(f"Written: {out_path}")

# Remove old zone files
for zone in ZONES:
    path = f"{DATA_DIR}/landmarks/{zone}.json"
    if os.path.exists(path):
        os.remove(path)
        print(f"Removed: {path}")

# Remove landmarks/ directory if empty
try:
    os.rmdir(f"{DATA_DIR}/landmarks")
    print(f"Removed directory: {DATA_DIR}/landmarks/")
except OSError:
    pass

print("Done!")
