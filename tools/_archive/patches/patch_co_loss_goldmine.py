#!/usr/bin/env python3
"""
Idempotent patch: add loss-check + goldmine-highlight to calibration_order.py.

Improvements:
  1. Compute current loss (RMS over anchor+high LMs) for each cam.
     If loss > 10' → flag as ⚠ BROKEN instead of "AUTO-OPTIMIZE READY".
  2. Highlight "goldmines" — cams with ≥20 LMs marked but ≤2 anchor+high.
     These are high-value targets: marking 1-3 anchors unlocks them.
  3. Show current loss inline for cams that have any anchor+high.

Sentinel: # ── CO-LOSS-GOLDMINE-V1 ──
"""

import os
import shutil
import sys

REPO = os.path.expanduser('~/Downloads/gtamaplib-main')
CO = os.path.join(REPO, 'tools', 'calibration_order.py')
SENTINEL = '# ── CO-LOSS-GOLDMINE-V1 ──'


# PATCH 1: Add helper function for loss calc + import gtamaplib
OLD_IMPORTS = '''import argparse
import json
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(THIS_DIR)
DATA_DIR = os.path.join(REPO_DIR, 'gtamapdata')
GEN_DIR = os.path.join(THIS_DIR, 'generated')'''

NEW_IMPORTS = '''import argparse
import json
import math
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(THIS_DIR)
DATA_DIR = os.path.join(REPO_DIR, 'gtamapdata')
GEN_DIR = os.path.join(THIS_DIR, 'generated')

sys.path.insert(0, REPO_DIR)
import gtamaplib as ml'''


# PATCH 2: Add the loss computation function
OLD_SCORE_FN = '''def score_cam(cam_name, pixels, lm_tiers, promoted_lms):
    """Returns (n_strong, n_total). n_strong = anchor+high (including promoted)."""
    cam_pixels = pixels.get(cam_name, {})
    n_strong = 0
    for lm_name in cam_pixels:
        tier = lm_tiers.get(lm_name, 'unverified')
        if tier in ('anchor', 'high') or lm_name in promoted_lms:
            n_strong += 1
    return n_strong, len(cam_pixels)'''

NEW_SCORE_FN = OLD_SCORE_FN + '''


''' + SENTINEL + '''
def compute_trusted_loss(cam_name, pixels, landmarks, lm_tiers):
    """RMS error in arcmin over anchor+high LMs. Returns None if no such LMs."""
    try:
        cam = ml.get_camera(cam_name)
    except Exception:
        return None
    cam_pixels = pixels.get(cam_name, {})
    errs = []
    for lm_name, mp in cam_pixels.items():
        tier = lm_tiers.get(lm_name, 'unverified')
        if tier not in ('anchor', 'high'):
            continue
        lm_data = landmarks.get(lm_name)
        lm_xyz = lm_data.get('xyz') if isinstance(lm_data, dict) else lm_data
        if not lm_xyz:
            continue
        try:
            proj = cam.get_pixel(lm_xyz)
            if proj is None:
                continue
            dx = (float(proj[0]) - mp[0]) * cam.hfov / cam.w * 60.0
            dy = (float(proj[1]) - mp[1]) * cam.vfov / cam.h * 60.0
            errs.append(math.sqrt(dx*dx + dy*dy))
        except Exception:
            continue
    if not errs:
        return None
    return math.sqrt(sum(e*e for e in errs) / len(errs))'''


# PATCH 3: Update the main loop to use loss + flag goldmines
OLD_ENTRY = '''        ordered.append({
            'cam': best_cam,
            'tier': cam_tiers.get(best_cam, 'unverified'),
            'n_strong': best_n_strong,
            'n_total': best_n_total,
            'promotions': new_promotions,
        })'''

NEW_ENTRY = '''        loss = compute_trusted_loss(best_cam, pixels, landmarks, lm_tiers)
        ordered.append({
            'cam': best_cam,
            'tier': cam_tiers.get(best_cam, 'unverified'),
            'n_strong': best_n_strong,
            'n_total': best_n_total,
            'promotions': new_promotions,
            'loss': loss,
        })'''


# PATCH 4: Update the print loop
OLD_PRINT_LOOP = '''        # Status icon
        if n_s >= 3:
            status = "✓"
            action = "AUTO-OPTIMIZE READY"
        elif n_s > 0:
            status = "◐"
            action = f"NEEDS {3 - n_s} MORE ANCHOR+HIGH"
        else:
            status = "○"
            action = "FRESH START (0 anchors)"

        print(f"  {i:>2}. {status} [{tier:<10}] {cn}")
        print(f"      {n_s} anchor+high · {n_t} total marked · {action}")'''

NEW_PRINT_LOOP = '''        loss = entry.get('loss')
        # Status icon + action logic with loss check + goldmine flag
        is_goldmine = n_t >= 20 and n_s <= 2
        if n_s >= 3:
            if loss is not None and loss > 10:
                status = "⚠"
                action = f"BROKEN (loss={loss:.1f}') — investigate before optimize"
            else:
                status = "✓"
                action = "AUTO-OPTIMIZE READY"
                if loss is not None:
                    action += f" (loss={loss:.2f}')"
        elif n_s > 0:
            status = "⭐" if is_goldmine else "◐"
            need = 3 - n_s
            goldmine_note = " GOLDMINE!" if is_goldmine else ""
            action = f"NEEDS {need} MORE ANCHOR+HIGH{goldmine_note}"
            if loss is not None:
                action += f" (current loss={loss:.2f}')"
        else:
            status = "⭐" if is_goldmine else "○"
            goldmine_note = " GOLDMINE!" if is_goldmine else ""
            action = f"FRESH START (0 anchors){goldmine_note}"

        print(f"  {i:>2}. {status} [{tier:<10}] {cn}")
        print(f"      {n_s} anchor+high · {n_t} total marked · {action}")'''


def main():
    apply = '--apply' in sys.argv

    with open(CO) as f:
        src = f.read()

    if SENTINEL in src:
        print(f"✓ Already patched")
        return

    if OLD_IMPORTS not in src:
        print("ERROR: imports anchor not found")
        sys.exit(1)
    if OLD_SCORE_FN not in src:
        print("ERROR: score_cam anchor not found")
        sys.exit(1)
    if OLD_ENTRY not in src:
        print("ERROR: ordered.append anchor not found")
        sys.exit(1)
    if OLD_PRINT_LOOP not in src:
        print("ERROR: print loop anchor not found")
        sys.exit(1)

    new_src = src.replace(OLD_IMPORTS, NEW_IMPORTS, 1)
    new_src = new_src.replace(OLD_SCORE_FN, NEW_SCORE_FN, 1)
    new_src = new_src.replace(OLD_ENTRY, NEW_ENTRY, 1)
    new_src = new_src.replace(OLD_PRINT_LOOP, NEW_PRINT_LOOP, 1)

    n_added = new_src.count('\n') - src.count('\n')
    print(f"Will add {n_added} lines")

    if not apply:
        print("(dry run — re-run with --apply)")
        return

    bak = CO + '.bak_pre_loss_goldmine'
    shutil.copy(CO, bak)
    print(f"✓ backup: {bak}")
    with open(CO, 'w') as f:
        f.write(new_src)
    print(f"✓ patched")


if __name__ == '__main__':
    main()
