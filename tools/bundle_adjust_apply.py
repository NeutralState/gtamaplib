#!/usr/bin/env python3
"""
bundle_adjust_apply.py — Apply bundle adjustment results to cameras.json and landmarks.json

Run AFTER bundle_adjust.py:
    python3 tools/bundle_adjust_apply.py

Creates a git commit with the results.
"""

import json
import os
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamapdata as md

RESULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bundle_adjust_result.json')

if not os.path.exists(RESULT_PATH):
    print("ERROR: bundle_adjust_result.json not found. Run bundle_adjust.py first.")
    sys.exit(1)

with open(RESULT_PATH) as f:
    result = json.load(f)

print(f"Bundle adjustment result:")
print(f"  Initial loss: {result['initial_loss']} arcmin")
print(f"  Final loss:   {result['final_loss']} arcmin")
print(f"  Improvement:  {result['improvement_pct']}%")
print(f"  Cameras:      {len(result['cameras'])}")
print(f"  Landmarks:    {len(result['landmarks'])}")

confirm = input("\nApply these results? (yes/no): ").strip().lower()
if confirm != 'yes':
    print("Aborted.")
    sys.exit(0)

# Apply camera updates
print("\nApplying camera updates...")
for cam_name, data in result['cameras'].items():
    xyz = data['xyz']
    ypr = data['ypr']
    hfov = data['hfov']
    md.update_camera(cam_name, xyz, ypr, [hfov, None])

# Apply landmark updates
print("Applying landmark updates...")
for lm_name, xyz in result['landmarks'].items():
    meta = md.landmarks_meta.get(lm_name, {})
    md.update_landmark(
        lm_name, xyz,
        source_cameras=meta.get('source_cameras', []),
        error_m=None,  # reset error_m — will need re-validation
        zone=meta.get('zone', 'unknown'),
    )

print(f"\nDone! Applied {len(result['cameras'])} cameras and {len(result['landmarks'])} landmarks.")
print(f"Review the changes with: git diff gtamapdata/cameras.json gtamapdata/landmarks.json")
print(f"Commit with: git add gtamapdata/ && git commit -m 'bundle_adjust: global optimization loss {result['initial_loss']} -> {result['final_loss']} ({result['improvement_pct']}%)'")
