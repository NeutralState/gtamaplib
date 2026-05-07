"""
topo_sort_landmarks.py — Full topological sort using triangulate.py dependencies.

Parses triangulate.py to extract which landmarks were used to calibrate
each camera (find_camera calls), then builds a complete dependency graph.

Usage: python3 topo_sort_landmarks.py
"""

import json
import os
import re
from collections import defaultdict, deque

DATA_DIR = "gtamapdata"
ZONES = ["vice_city", "ambrosia", "grassrivers", "leonida_keys", "port_gellhorn", "leonard_county"]

# ── Load all landmarks ────────────────────────────────────────────────────────

all_landmarks = {}
for zone in ZONES:
    path = f"{DATA_DIR}/landmarks/{zone}.json"
    if not os.path.exists(path): continue
    with open(path) as f:
        data = json.load(f)
    for name, entry in data.items():
        all_landmarks[name] = {**entry, "zone": zone}

print(f"Loaded {len(all_landmarks)} landmarks")

# ── Cameras that have known positions (no dependencies) ──────────────────────

# These are either leaks or cameras calibrated purely from geometry (AIWE, etc.)
# Cameras whose calibration method is not a find_camera() call in triangulate.py
# but whose positions are effectively known (manual calibration, geometry, etc.)
# Treated as roots for dependency ordering purposes.
MANUALLY_CALIBRATED_CAMERAS = {
    "Airport (X)", "Car Wash", "Glitch (A)", "Grassrivers Postcard (X)",
    "Handlebar (SE)", "Handlebar (SW)", "Hedge (B) (X)", "Hotel (W)",
    "Intersection (W)", "Penthouse (NE)", "Penthouse (NW)",
    "Penthouse (SE)", "Penthouse (SW)", "Pool", "Rooftop (SE)",
}

ROOT_CAMERAS = {
    # Leak cameras
    "Tennis Stadium (4K)", "Vice Beach (A)", "Vice Beach (B)",
    "Metro (SE) (A) (4K)", "Alley (W)", "Park", "Port",
    "Tennis Court (SE)", "Tennis Court (NE)", "Tennis Court (N)",
    "Tennis Court (SW)",
    # AIWE — calibrated from map geometry, no landmark deps
    "AI World Editor Map (4K)",
    # Diner cluster — calibrated from SSB geometry + AIWE
    "Diner (W) (A)", "Diner (W) (B)", "Diner (N)", "Diner (NW)",
    "Diner (NE)", "Diner (E)", "Diner (SE) (A)", "Diner (SE) (B)",
    "Diner (S)", "Diner (SW)", "Diner",
    # Gas stations — calibrated from AIWE + Diner
    "Gas Station (Lucia)", "Gas Station (Jason)",
    # Other leak/geometry-only cameras
    "Loading Zone near Prison (SW)", "Loading Zone near Prison (N)",
    "Ocean near Keys (N)", "Ocean near Keys (E)",
    "House with Boat (X)",
    "Highway (NE)",
    "Sidewalk (Jason) (E)", "Sidewalk (Jason) (S)",
    "Welcome Center (E)", "Welcome Center (W)",
    "Police Chase (A)", "Police Chase (D)",
    # Additional cameras calibrated outside triangulate.py
    "Airport (X)", "Car Wash", "Glitch (A)", "Grassrivers Postcard (X)",
    "Handlebar (SE)", "Handlebar (SW)", "Hedge (B) (X)", "Hotel (W)",
    "Intersection (W)", "Penthouse (NE)", "Penthouse (NW)",
    "Penthouse (SE)", "Penthouse (SW)", "Pool", "Rooftop (SE)",
}

# ── Parse triangulate.py: camera -> landmarks used for calibration ────────────
# Extract find_camera() calls and their lm_names lists

cam_calibration_lms = {}  # cam_name -> set of lm_names used to calibrate it

try:
    with open("triangulate.py") as f:
        content = f.read()
except FileNotFoundError:
    print("triangulate.py not found — using source_cameras from JSON only")
    content = ""

# Match find_camera("cam_name", [...lm_names...], [...rays...], ...)
# The lm_names list is the second argument (list of strings)
find_cam_pattern = re.compile(
    r'ml\.find_camera\s*\(\s*\n?\s*"([^"]+)".*?\[([^\]]*)\]',
    re.DOTALL
)

for match in find_cam_pattern.finditer(content):
    cam_name = match.group(1)
    lm_block = match.group(2)
    # Extract quoted strings from the lm_names list
    lm_names = re.findall(r'"([^"]+)"', lm_block)
    if cam_name not in cam_calibration_lms:
        cam_calibration_lms[cam_name] = set()
    cam_calibration_lms[cam_name].update(lm_names)

print(f"Parsed find_camera calls for {len(cam_calibration_lms)} cameras")

# Also parse find_landmark calls: find_landmark(cam_a, cam_b, lm_name)
# These triangulate landmarks using two cameras
find_lm_pattern = re.compile(
    r'ml\.find_landmark\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']'
)
lm_triangulation = defaultdict(set)  # lm_name -> set of camera names used
for match in find_lm_pattern.finditer(content):
    cam_a, cam_b, lm_name = match.group(1), match.group(2), match.group(3)
    lm_triangulation[lm_name].add(cam_a)
    lm_triangulation[lm_name].add(cam_b)

print(f"Parsed find_landmark calls for {len(lm_triangulation)} landmarks")

# ── Build full dependency graph ───────────────────────────────────────────────

# cam_deps[cam] = set of lm_names that cam depends on to be calibrated
cam_deps = {}
for cam_name, lm_names in cam_calibration_lms.items():
    cam_deps[cam_name] = lm_names
for cam_name in ROOT_CAMERAS | MANUALLY_CALIBRATED_CAMERAS:
    cam_deps[cam_name] = set()

# lm_deps[lm] = set of lm_names that lm depends on
lm_deps = {}
for lm_name, entry in all_landmarks.items():
    deps = set()
    # Source from JSON source_cameras
    for cam in entry.get("source_cameras", []):
        if cam in ("Gizmo",):
            continue
        deps.update(cam_deps.get(cam, set()))
    # Source from triangulate.py find_landmark
    for cam in lm_triangulation.get(lm_name, set()):
        deps.update(cam_deps.get(cam, set()))
    deps.discard(lm_name)
    # Only keep deps that are actual landmarks
    deps = {d for d in deps if d in all_landmarks}
    lm_deps[lm_name] = deps

# ── Kahn's topological sort ───────────────────────────────────────────────────

in_degree = {name: 0 for name in all_landmarks}
dependents = defaultdict(set)

for lm_name, deps in lm_deps.items():
    for dep in deps:
        in_degree[lm_name] += 1
        dependents[dep].add(lm_name)

# Start with all landmarks that have no dependencies, sorted alphabetically
queue = deque(sorted([n for n, d in in_degree.items() if d == 0]))
sorted_landmarks = []
visited = set()

while queue:
    name = queue.popleft()
    if name in visited: continue
    visited.add(name)
    sorted_landmarks.append(name)
    for dependent in sorted(dependents[name]):
        in_degree[dependent] -= 1
        if in_degree[dependent] == 0:
            queue.append(dependent)

remaining = [n for n in all_landmarks if n not in visited]
if remaining:
    print(f"Warning: {len(remaining)} landmarks not ordered (cycles or missing deps) — appended alphabetically")
    sorted_landmarks.extend(sorted(remaining))

print(f"Sorted {len(sorted_landmarks)} / {len(all_landmarks)} landmarks")

# ── Write reordered JSON files ────────────────────────────────────────────────

zone_data = {zone: {} for zone in ZONES}
for name in sorted_landmarks:
    entry = all_landmarks[name]
    zone = entry["zone"]
    zone_data[zone][name] = {
        "xyz": entry["xyz"],
        "source_cameras": entry.get("source_cameras", []),
        "error_m": entry.get("error_m"),
    }

for zone in ZONES:
    path = f"{DATA_DIR}/landmarks/{zone}.json"
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(zone_data[zone], f, indent=2)
    os.replace(tmp, path)
    print(f"  {zone}.json: {len(zone_data[zone])} landmarks")

# ── Write topo_order.txt ──────────────────────────────────────────────────────

ordered_set = set(sorted_landmarks[:len(sorted_landmarks) - len(remaining)])
with open("topo_order.txt", "w") as f:
    f.write("# TOPOLOGICALLY ORDERED LANDMARKS\n")
    f.write(f"# {len(sorted_landmarks) - len(remaining)} ordered, {len(remaining)} unresolved (cycles or unknown camera deps)\n\n")
    for i, name in enumerate(sorted_landmarks):
        entry = all_landmarks[name]
        src = ", ".join(entry.get("source_cameras", [])) or "root"
        deps = lm_deps.get(name, set())
        dep_str = f" (deps: {', '.join(sorted(deps)[:3])}{'...' if len(deps)>3 else ''})" if deps else ""
        if name in remaining:
            f.write(f"  ??. {name}  [{src}]{dep_str}  # UNRESOLVED\n")
        else:
            f.write(f"{i+1:4d}. {name}  [{src}]{dep_str}\n")

print("\ntopo_order.txt written")
print("Done!")
