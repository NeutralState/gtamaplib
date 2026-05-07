#!/usr/bin/env python3
"""
patch_minimap_pointer_fix.py

Fixes the previous patch:
1. Revert radius 500 -> 350 (500 was too zoomed out)
2. Replace the huge white triangle with a small GPS-style arrow pointer
   (small, sharp, white-filled with thin black outline, pointing up)

Idempotent: re-running after a successful apply is a no-op.
Backs up calib.html to calib.html.bak_pointer_fix before writing.
"""

import os
import shutil
import sys

CALIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calib.html')

# ── Tweak 1: revert radius=500 → radius=350 ─────────────────────────────────
RADIUS_OLD = "/api/minimap?cam=${encodeURIComponent(currentCam)}&radius=500"
RADIUS_NEW = "/api/minimap?cam=${encodeURIComponent(currentCam)}&radius=350"

# ── Tweak 2: replace the huge filled triangle with a small GPS arrow ────────
# Old (from previous patch): huge white triangle path from (90,15) to (170,15)
POINTER_OLD = '''        <path d="M 130,90 L 90,15 L 170,15 Z"
          fill="#ffffff" stroke="#000000"
          stroke-width="1.5" stroke-linejoin="round"/>'''

# New: small sharp GPS-style arrow centered at (130,90), pointing up.
# The shape: tip at top (130,72), wings at (118,98) and (142,98),
# small notch at the bottom-center (130,92) to give the classic GPS-arrow
# kite/chevron silhouette (like Google Maps / GTA V navigation arrow).
POINTER_NEW = '''        <path d="M 130,72 L 142,98 L 130,92 L 118,98 Z"
          fill="#ffffff" stroke="#000000"
          stroke-width="1.2" stroke-linejoin="round" stroke-linecap="round"/>'''


def main():
    if not os.path.exists(CALIB):
        print(f"ERROR: {CALIB} not found", file=sys.stderr)
        sys.exit(1)

    with open(CALIB, 'r') as f:
        content = f.read()

    already_radius = RADIUS_NEW in content and RADIUS_OLD not in content
    already_pointer = POINTER_NEW in content
    if already_radius and already_pointer:
        print("✓ Already patched — no changes needed.")
        return

    if not already_radius and RADIUS_OLD not in content:
        print(f"ERROR: could not find radius=500 to revert.\n"
              f"Looked for: {RADIUS_OLD!r}\n"
              f"(Did you skip the previous patch?)", file=sys.stderr)
        sys.exit(2)
    if not already_pointer and POINTER_OLD not in content:
        print(f"ERROR: could not find the huge triangle to replace.\n"
              f"Expected the path from patch_minimap_final_tweaks.py.",
              file=sys.stderr)
        sys.exit(3)

    backup = CALIB + ".bak_pointer_fix"
    if not os.path.exists(backup):
        shutil.copy(CALIB, backup)
        print(f"  backup created: {backup}")

    new_content = content
    if not already_radius:
        new_content = new_content.replace(RADIUS_OLD, RADIUS_NEW, 1)
        print("  ✓ radius 500 → 350 (reverted)")
    if not already_pointer:
        new_content = new_content.replace(POINTER_OLD, POINTER_NEW, 1)
        print("  ✓ pointer → small GPS arrow (kite shape)")

    tmp = CALIB + ".tmp"
    with open(tmp, 'w') as f:
        f.write(new_content)
    os.replace(tmp, CALIB)
    print("✓ Done.")


if __name__ == '__main__':
    main()
