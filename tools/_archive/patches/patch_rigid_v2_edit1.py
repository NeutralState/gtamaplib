#!/usr/bin/env python3
"""
patch_rigid_v2_edit1.py — Inject rigid body setup after line 138.

This is edit 1 of 5 for Niveau 2 rigid body integration.
Idempotent via sentinel [RIGID-BODY-V1-EDIT1].
"""
import shutil
import sys
from pathlib import Path

PATH = Path("tools/bundle_adjust.py")
SENTINEL = "[RIGID-BODY-V1-EDIT1]"

NEW_BLOCK = '''
# ── [RIGID-BODY-V1] Rigid body setup ──────────────────────────────────────────
# Some LMs form rigid 3D structures (e.g. Four Seasons Hotel Miami).
# Instead of optimizing each LM xyz independently (3 DOF each), we treat
# the whole structure as 6 DOFs (3 translation + 3 rotation around centroid).
# See tools/RIGID_BODY_DESIGN.md for the full design.
import sys as _sys_rigid
_sys_rigid.path.insert(0, os.path.join(REPO_DIR, "vendor"))
try:
    from gtamaplib.gtamaplib import FourSeasons as _FourSeasons
    _fs = _FourSeasons()
    _fs_lm_map = {
        "Four Seasons Hotel Miami (BE)":     _fs.hb58se,
        "Four Seasons Hotel Miami (BW)":     _fs.hb58sw,
        "Four Seasons Hotel Miami (E)":      _fs.fs57e,
        "Four Seasons Hotel Miami (NE)":     _fs.fs57ne,
        "Four Seasons Hotel Miami (NW)":     _fs.fs57nw,
        "Four Seasons Hotel Miami (SE)":     _fs.fs56se,
        "Four Seasons Hotel Miami (SW)":     _fs.fs56sw,
        "Four Seasons Hotel Miami (W)":      _fs.fs57e,
        "Four Seasons Hotel Miami (40NE)":   _fs.fs40ne,
        "Four Seasons Hotel Miami (40NW)":   _fs.fs40nw,
        "Four Seasons Hotel Miami (40W)":    _fs.fs40w,
        "Four Seasons Hotel Miami (40E)":    _fs.fs40e,
        "Four Seasons Hotel Miami (32NE)":   _fs._get_point_at_floor(_fs.fs40ne, 32),
        "Four Seasons Hotel Miami (56NE)":   _fs.fs56ne,
        "Four Seasons Hotel Miami (HB28SE)": _fs.hb28se,
        "Four Seasons Hotel Miami (HB8SE)":  _fs.hb8se,
        "Four Seasons Hotel Miami (HB58SE)": _fs.hb58se,
        "Four Seasons Hotel Miami (HB58NE)": _fs.hb58ne,
    }
    _fs_lms_present = {n: np.array(xyz) for n, xyz in _fs_lm_map.items() if n in lm_idx}
    if _fs_lms_present:
        _centroid_fs = np.mean(list(_fs_lms_present.values()), axis=0)
        _local_coords_fs = {n: xyz - _centroid_fs for n, xyz in _fs_lms_present.items()}
        _rigid_bodies = {
            "four_seasons": {
                "centroid": _centroid_fs,
                "lm_local_coords": _local_coords_fs,
            }
        }
        _lm_to_rigid_body = {n: "four_seasons" for n in _fs_lms_present}
        print(f"  [RIGID-BODY-V1] Registered 'four_seasons' with {len(_fs_lms_present)} LMs, "
              f"centroid=({_centroid_fs[0]:.1f},{_centroid_fs[1]:.1f},{_centroid_fs[2]:.1f})")
    else:
        _rigid_bodies = {}
        _lm_to_rigid_body = {}
        print(f"  [RIGID-BODY-V1] No FourSeasons LMs in optimizable set; rigid body skipped")
except ImportError:
    print(f"  [RIGID-BODY-V1] vendor/gtamaplib not available; rigid body disabled")
    _rigid_bodies = {}
    _lm_to_rigid_body = {}

# Remove rigid LMs from lm_idx and opt_lm_names; computed via rigid body params instead
_rigid_lm_names = set(_lm_to_rigid_body.keys())
_free_lm_names = [n for n in opt_lm_names if n not in _rigid_lm_names]
lm_idx = {n: i for i, n in enumerate(_free_lm_names)}
opt_lm_names = _free_lm_names

N_RIGID_BODIES = len(_rigid_bodies)
RIGID_BLOCK = N_RIGID_BODIES * 6
# ── End [RIGID-BODY-V1] setup ─────────────────────────────────────────────────
'''

ANCHOR = "lm_idx  = {n: i for i, n in enumerate(opt_lm_names)}"


def main():
    apply = "--apply" in sys.argv

    text = PATH.read_text()
    if SENTINEL in text or "[RIGID-BODY-V1]" in text:
        print(f"Already patched ({SENTINEL} or [RIGID-BODY-V1] found). Nothing to do.")
        return

    if ANCHOR not in text:
        print(f"ERROR: anchor not found: {ANCHOR!r}")
        sys.exit(1)

    # Insert NEW_BLOCK right after the ANCHOR line
    new_text = text.replace(ANCHOR, ANCHOR + "\n" + NEW_BLOCK)

    if not apply:
        print(f"DRY-RUN: would insert {len(NEW_BLOCK)} chars after the lm_idx line.")
        print(f"Sentinel will be visible in code: [RIGID-BODY-V1]")
        return

    backup = PATH.with_suffix(".py.bak_rigid_v2_edit1")
    shutil.copy(PATH, backup)
    PATH.write_text(new_text)
    print(f"Patched {PATH}")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
