#!/usr/bin/env python3
"""
patch_calibrate_cam_ancestry.py

Adds LEAK-ancestry tagging to calibrate_cam.py's "LIKELY VISIBLE LMS" section.

Each suggested LM gets one of these tags showing where its triangulated
position comes from:
  - all_leak     — 100% triangulated from LEAK cams (ground-truth quality)
  - partial_leak — mixed: at least one LEAK source
  - no_leak      — 0% LEAK in source_cameras (calibration-derived)
  - no_source    — no source_cameras field at all

Suggestions are re-sorted: all_leak first, then partial_leak, then no_leak,
each group sorted by distance.

Also adds 'import re' to the script's imports if not already there
(needed for matching LEAK cam date sources).

Idempotent via sentinel [ANCESTRY-V1].
Dry-run by default; pass --apply.

Run from gtamaplib-main/:
  python3 patch_calibrate_cam_ancestry.py
  python3 patch_calibrate_cam_ancestry.py --apply
"""
import sys
import shutil
import re
from pathlib import Path

TARGET = Path("tools/calibrate_cam.py")
SENTINEL = "[ANCESTRY-V1]"


ANCESTRY_HELPER = '''

# ── LEAK ancestry helper ──────────────────────────────────────────────────  [ANCESTRY-V1]

def compute_lm_ancestry(cameras, landmarks):
    """For each LM, classify by its source_cameras:
       all_leak / partial_leak / no_leak / no_source.
       LEAK cam = source field starts with 'YYYY-MM-DD' (real game recording)."""
    leak_cams = set()
    for cam_name, cam_data in cameras.items():
        src = cam_data.get('source', '') if isinstance(cam_data, dict) else ''
        if re.match(r'\\d{4}-\\d{2}-\\d{2}', src):
            leak_cams.add(cam_name)

    ancestry = {}
    for lm_name, lm_data in landmarks.items():
        if not isinstance(lm_data, dict):
            ancestry[lm_name] = 'no_source'
            continue
        src = lm_data.get('source_cameras', [])
        if not src:
            ancestry[lm_name] = 'no_source'
            continue
        leak_count = sum(1 for c in src if c in leak_cams)
        if leak_count == len(src):
            ancestry[lm_name] = 'all_leak'
        elif leak_count > 0:
            ancestry[lm_name] = 'partial_leak'
        else:
            ancestry[lm_name] = 'no_leak'
    return ancestry

'''


OLD_PRINT_BLOCK = """    if visible:
        print("─" * 70)
        print(f"  LIKELY VISIBLE LMS (not yet marked, sorted by distance)")
        print("─" * 70)
        for lm_name, tier, (px, py), dist in visible:
            print(f"    [{tier:<6}]  dist={dist:>6.0f}m  px≈({px:>5.0f}, {py:>4.0f})  {lm_name}")"""

NEW_PRINT_BLOCK = """    if visible:
        # ── ANCESTRY-V1 ── tag suggestions by LEAK ancestry, re-sort
        ancestry = compute_lm_ancestry(cameras, landmarks)
        anc_order = {'all_leak': 0, 'partial_leak': 1, 'no_leak': 2, 'no_source': 3}
        anc_label = {'all_leak': 'LEAK', 'partial_leak': 'part',
                     'no_leak': '----', 'no_source': '????'}
        visible_tagged = []
        for lm_name, tier, pxpy, dist in visible:
            a = ancestry.get(lm_name, 'no_source')
            visible_tagged.append((lm_name, tier, pxpy, dist, a))
        visible_tagged.sort(key=lambda v: (anc_order[v[4]], v[3]))

        print("─" * 70)
        print(f"  LIKELY VISIBLE LMS (not yet marked — LEAK ancestry first, then distance)")
        print("─" * 70)
        for lm_name, tier, (px, py), dist, anc in visible_tagged:
            print(f"    [{tier:<6} {anc_label[anc]}]  dist={dist:>6.0f}m  px≈({px:>5.0f}, {py:>4.0f})  {lm_name}")"""


def main():
    apply = "--apply" in sys.argv

    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found. Run from gtamaplib-main/.")
        sys.exit(1)

    text = TARGET.read_text()

    if SENTINEL in text:
        print(f"✓ Sentinel '{SENTINEL}' already present — patch already applied.")
        return

    if OLD_PRINT_BLOCK not in text:
        print("ERROR: expected old print block not found. File may have diverged.")
        sys.exit(1)

    main_def_marker = "def main():"
    if main_def_marker not in text:
        print(f"ERROR: '{main_def_marker}' not found.")
        sys.exit(1)

    new_text = text

    # Step 0: Add 'import re' if not already there.
    # Anchor: insert right after 'import os' (which is always present).
    if not re.search(r'^import re\b', new_text, re.MULTILINE):
        os_import_match = re.search(r'^import os\b', new_text, re.MULTILINE)
        if not os_import_match:
            print("ERROR: 'import os' not found, cannot anchor 'import re' insertion.")
            sys.exit(1)
        # Insert 'import re' on a new line right after 'import os'
        insert_pos = os_import_match.end()
        # Find end of that line
        line_end = new_text.find('\n', insert_pos)
        if line_end == -1:
            line_end = len(new_text)
        new_text = new_text[:line_end] + '\nimport re  # [ANCESTRY-V1]' + new_text[line_end:]
        added_import = True
    else:
        added_import = False

    # Step 1: Insert helper function before def main():
    new_text = new_text.replace(
        main_def_marker,
        ANCESTRY_HELPER.lstrip() + "\n" + main_def_marker,
        1,
    )

    # Step 2: Replace print block
    new_text = new_text.replace(OLD_PRINT_BLOCK, NEW_PRINT_BLOCK, 1)

    old_lines = text.count("\n")
    new_lines = new_text.count("\n")
    print("=== Patch summary ===")
    print(f"  Old: {old_lines} lines")
    print(f"  New: {new_lines} lines (+{new_lines - old_lines})")
    print(f"  0. {'Add' if added_import else 'Skip (already present)'} 'import re'")
    print(f"  1. Insert compute_lm_ancestry() helper before main()")
    print(f"  2. Replace print loop: tag w/ LEAK/part/----/???? + re-sort all_leak first")
    print()

    if not apply:
        print("DRY-RUN — no changes written. Pass --apply to write.")
        return

    backup = TARGET.with_suffix(TARGET.suffix + ".bak_pre_ancestry_v1")
    shutil.copy(TARGET, backup)
    print(f"Backup written: {backup}")

    TARGET.write_text(new_text)
    print(f"✓ {TARGET} updated.")


if __name__ == "__main__":
    main()
