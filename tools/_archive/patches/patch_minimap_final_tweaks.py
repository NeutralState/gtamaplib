#!/usr/bin/env python3
"""
patch_minimap_final_tweaks.py

Re-applies the two tweaks from the lost `patch_minimap_arrow_zoom.py`:
1. Bump minimap radius from 350 to 500 (slightly more zoomed out)
2. Replace the semi-transparent triangle + green dot with a clean
   white-filled triangle (GTA V style pointer) — no center dot.

Idempotent: re-running it after a successful apply is a no-op.
Backs up calib.html to calib.html.bak_final_tweaks before writing.
"""

import os
import shutil
import sys

CALIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calib.html')

# ── Tweak 1: radius=350 → radius=500 ────────────────────────────────────────
RADIUS_OLD = "/api/minimap?cam=${encodeURIComponent(currentCam)}&radius=350"
RADIUS_NEW = "/api/minimap?cam=${encodeURIComponent(currentCam)}&radius=500"

# ── Tweak 2: pointer SVG (lines 209-212) ────────────────────────────────────
# Old: semi-transparent triangle + green dot at center
POINTER_OLD = '''        <path d="M 130,90 L 90,15 L 170,15 Z"
          fill="rgba(255,255,255,0.20)" stroke="rgba(255,255,255,0.6)"
          stroke-width="1"/>
        <circle cx="130" cy="90" r="4" fill="#4ade80" stroke="#fff" stroke-width="1.5"/>'''

# New: GTA V style — solid white triangle, thin black stroke, no center dot
POINTER_NEW = '''        <path d="M 130,90 L 90,15 L 170,15 Z"
          fill="#ffffff" stroke="#000000"
          stroke-width="1.5" stroke-linejoin="round"/>'''


def main():
    if not os.path.exists(CALIB):
        print(f"ERROR: {CALIB} not found", file=sys.stderr)
        sys.exit(1)

    with open(CALIB, 'r') as f:
        content = f.read()

    # Idempotency check: if both new strings are already present, do nothing
    already_radius = RADIUS_NEW in content
    already_pointer = POINTER_NEW in content
    if already_radius and already_pointer:
        print("✓ Already patched — no changes needed.")
        return

    # Sanity: old strings must be present (else we're patching the wrong file)
    if not already_radius and RADIUS_OLD not in content:
        print(f"ERROR: could not find radius=350 to replace.\n"
              f"Looked for: {RADIUS_OLD!r}", file=sys.stderr)
        sys.exit(2)
    if not already_pointer and POINTER_OLD not in content:
        print(f"ERROR: could not find pointer SVG to replace.\n"
              f"Expected lines 209-212 of calib.html.", file=sys.stderr)
        sys.exit(3)

    # Backup before writing
    backup = CALIB + ".bak_final_tweaks"
    if not os.path.exists(backup):
        shutil.copy(CALIB, backup)
        print(f"  backup created: {backup}")

    # Apply tweaks
    new_content = content
    if not already_radius:
        new_content = new_content.replace(RADIUS_OLD, RADIUS_NEW, 1)
        print("  ✓ radius 350 → 500")
    if not already_pointer:
        new_content = new_content.replace(POINTER_OLD, POINTER_NEW, 1)
        print("  ✓ pointer → solid white triangle (GTA V style)")

    # Atomic write
    tmp = CALIB + ".tmp"
    with open(tmp, 'w') as f:
        f.write(new_content)
    os.replace(tmp, CALIB)
    print("✓ Done.")


if __name__ == '__main__':
    main()
