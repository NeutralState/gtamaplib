#!/usr/bin/env python3
"""
patch_minimap_pointer_smaller.py

Shrinks the GPS arrow pointer ~30% — same chevron shape, just smaller.
Previous: tip(130,72) wings(118,98)(142,98) notch(130,92)  → 26px tall
This:     tip(130,80) wings(122,96)(138,96) notch(130,92)  → 16px tall

Idempotent. Backs up to calib.html.bak_pointer_smaller.
"""

import os
import shutil
import sys

CALIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calib.html')

POINTER_OLD = '''        <path d="M 130,72 L 142,98 L 130,92 L 118,98 Z"
          fill="#ffffff" stroke="#000000"
          stroke-width="1.2" stroke-linejoin="round" stroke-linecap="round"/>'''

POINTER_NEW = '''        <path d="M 130,80 L 138,96 L 130,92 L 122,96 Z"
          fill="#ffffff" stroke="#000000"
          stroke-width="1.2" stroke-linejoin="round" stroke-linecap="round"/>'''


def main():
    if not os.path.exists(CALIB):
        print(f"ERROR: {CALIB} not found", file=sys.stderr)
        sys.exit(1)

    with open(CALIB, 'r') as f:
        content = f.read()

    if POINTER_NEW in content:
        print("✓ Already patched — no changes needed.")
        return

    if POINTER_OLD not in content:
        print(f"ERROR: could not find the previous pointer to replace.\n"
              f"(Did you skip patch_minimap_pointer_fix.py?)", file=sys.stderr)
        sys.exit(2)

    backup = CALIB + ".bak_pointer_smaller"
    if not os.path.exists(backup):
        shutil.copy(CALIB, backup)
        print(f"  backup created: {backup}")

    new_content = content.replace(POINTER_OLD, POINTER_NEW, 1)

    tmp = CALIB + ".tmp"
    with open(tmp, 'w') as f:
        f.write(new_content)
    os.replace(tmp, CALIB)
    print("  ✓ pointer shrunk: 26px tall → 16px tall (~30% smaller)")
    print("✓ Done.")


if __name__ == '__main__':
    main()
