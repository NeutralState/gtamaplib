#!/usr/bin/env python3
"""
delete_ambrosia_easy_hill.py — Delete the obsolete Ambrosia 04 (Fires) → Easy Hill
observation. The pixel projects to 11km from where Diner (SE) cams agree the
hill should be, so this obs is definitely wrong (likely became invalid after
Ambrosia 04 was recalibrated).

Run from gtamaplib-main/:
    python3 tools/delete_ambrosia_easy_hill.py        # dry run
    python3 tools/delete_ambrosia_easy_hill.py --apply
"""

import argparse
import json
import os
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamapdata as md

CAM = "Ambrosia 04 (Fires)"
LM  = "Easy Hill"

PIXELS_PATH    = os.path.join(GTAMAP_DIR, "gtamapdata", "pixels.json")
LANDMARKS_PATH = os.path.join(GTAMAP_DIR, "gtamapdata", "landmarks.json")

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

# ── Sanity ────────────────────────────────────────────────────────────────────

if CAM not in md.pixels or LM not in md.pixels[CAM]:
    print(f"No pixel '{LM}' in '{CAM}' — nothing to delete.")
    sys.exit(0)

bad_pixel = md.pixels[CAM][LM]
print(f"Will delete: pixels.json['{CAM}']['{LM}'] = {bad_pixel}")

# Check if landmark still has Ambrosia 04 in its source_cameras
lm_meta = md.landmarks_meta.get(LM, {})
sources = list(lm_meta.get('source_cameras', []))
needs_source_update = CAM in sources
if needs_source_update:
    new_sources = [s for s in sources if s != CAM]
    print(f"Will also update source_cameras of '{LM}': {sources} → {new_sources}")

# ── Apply ─────────────────────────────────────────────────────────────────────

if not args.apply:
    print("\n(dry run — re-run with --apply to write changes)")
    sys.exit(0)

# pixels.json
with open(PIXELS_PATH) as f:
    pixels_data = json.load(f)
del pixels_data[CAM][LM]
tmp = PIXELS_PATH + ".tmp"
with open(tmp, "w") as f:
    json.dump(pixels_data, f, indent=2)
os.replace(tmp, PIXELS_PATH)
print(f"✓ pixels.json: deleted '{CAM}' → '{LM}'")

# landmarks.json (only update sources, don't touch xyz)
if needs_source_update:
    with open(LANDMARKS_PATH) as f:
        lm_data = json.load(f)
    lm_data[LM]['source_cameras'] = new_sources
    tmp = LANDMARKS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(lm_data, f, indent=2)
    os.replace(tmp, LANDMARKS_PATH)
    print(f"✓ landmarks.json: updated source_cameras for '{LM}'")

print("\nDone.")
