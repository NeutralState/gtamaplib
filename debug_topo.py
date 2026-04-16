import json, os, re
from collections import defaultdict

DATA_DIR = "gtamapdata"
ZONES = ["vice_city", "ambrosia", "grassrivers", "leonida_keys", "port_gellhorn", "leonard_county"]
all_landmarks = {}
for zone in ZONES:
    path = f"{DATA_DIR}/landmarks/{zone}.json"
    if not os.path.exists(path): continue
    with open(path) as f:
        for name, entry in json.load(f).items():
            all_landmarks[name] = {**entry, "zone": zone}

with open('triangulate.py') as f:
    content = f.read()
pattern = re.compile(r'ml\.find_camera\s*\(\s*\n?\s*"([^"]+)".*?\[([^\]]*)\]', re.DOTALL)
cam_calibration_lms = {}
for m in pattern.finditer(content):
    lms = re.findall(r'"([^"]+)"', m.group(2))
    cam_calibration_lms[m.group(1)] = set(lms)

ROOT_CAMERAS = {
    "Tennis Stadium (4K)", "Vice Beach (A)", "Vice Beach (B)",
    "Metro (SE) (A) (4K)", "Alley (W)", "Park", "Port",
    "Tennis Court (SE)", "Tennis Court (NE)", "Tennis Court (N)",
    "Tennis Court (SW)", "AI World Editor Map (4K)",
    "Diner (W) (A)", "Diner (W) (B)", "Diner (N)", "Diner (NW)",
    "Diner (NE)", "Diner (E)", "Diner (SE) (A)", "Diner (SE) (B)",
    "Diner (S)", "Diner (SW)", "Diner",
    "Gas Station (Lucia)", "Gas Station (Jason)",
    "Loading Zone near Prison (SW)", "Loading Zone near Prison (N)",
    "Ocean near Keys (N)", "Ocean near Keys (E)",
    "House with Boat (X)", "Highway (NE)",
    "Sidewalk (Jason) (E)", "Sidewalk (Jason) (S)",
    "Welcome Center (E)", "Welcome Center (W)",
    "Police Chase (A)", "Police Chase (D)",
}

unknown_cams = set()
for name, entry in all_landmarks.items():
    for cam in entry.get("source_cameras", []):
        if cam not in ROOT_CAMERAS and cam not in cam_calibration_lms and cam != "Gizmo":
            unknown_cams.add(cam)

print(f"Unknown cameras (not root, not parsed): {len(unknown_cams)}")
for c in sorted(unknown_cams)[:30]:
    print(f"  {c}")
