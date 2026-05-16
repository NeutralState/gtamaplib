#!/usr/bin/env python3
"""
[PORTOFINO-RIGID-V1] Add Portofino tower as a rigid body in bundle_adjust.

Idempotent. Sentinel: [PORTOFINO-RIGID-V1].

Usage:
  python3 tools/_archive/patches/patch_portofino_rigid_body.py          # dry-run
  python3 tools/_archive/patches/patch_portofino_rigid_body.py --apply  # apply
"""
import sys, os, shutil

PATH = 'tools/bundle_adjust.py'
SENTINEL = '[PORTOFINO-RIGID-V1]'

OLD = '''_fs_lms_present = {n: np.array(xyz) for n, xyz in _FS_LM_MAP.items() if n in md.landmarks}
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
    print(f"  [RIGID-BODY-V1] No FourSeasons LMs in optimizable set; rigid body skipped")'''

NEW = '''_fs_lms_present = {n: np.array(xyz) for n, xyz in _FS_LM_MAP.items() if n in md.landmarks}

# [PORTOFINO-RIGID-V1] Portofino Tower (3-peak star building)
_PORTOFINO_LM_MAP = {
    "Portofino Tower (NW)": (1720.3704, -196.3384, 142.3855),
    "Portofino Tower (NE)": (1753.6794, -181.3662, 143.0098),
    "Portofino Tower (S)":  (1734.8100, -223.8500, 140.3500),
}
_portofino_lms_present = {n: np.array(xyz) for n, xyz in _PORTOFINO_LM_MAP.items() if n in md.landmarks}

_rigid_bodies = {}
_lm_to_rigid_body = {}

if _fs_lms_present:
    _centroid_fs = np.mean(list(_fs_lms_present.values()), axis=0)
    _local_coords_fs = {n: xyz - _centroid_fs for n, xyz in _fs_lms_present.items()}
    _rigid_bodies["four_seasons"] = {
        "centroid": _centroid_fs,
        "lm_local_coords": _local_coords_fs,
    }
    for n in _fs_lms_present:
        _lm_to_rigid_body[n] = "four_seasons"
    print(f"  [RIGID-BODY-V1] Registered 'four_seasons' with {len(_fs_lms_present)} LMs, "
          f"centroid=({_centroid_fs[0]:.1f},{_centroid_fs[1]:.1f},{_centroid_fs[2]:.1f})")

if _portofino_lms_present:
    _centroid_pt = np.mean(list(_portofino_lms_present.values()), axis=0)
    _local_coords_pt = {n: xyz - _centroid_pt for n, xyz in _portofino_lms_present.items()}
    _rigid_bodies["portofino"] = {
        "centroid": _centroid_pt,
        "lm_local_coords": _local_coords_pt,
    }
    for n in _portofino_lms_present:
        _lm_to_rigid_body[n] = "portofino"
    print(f"  [PORTOFINO-RIGID-V1] Registered 'portofino' with {len(_portofino_lms_present)} LMs, "
          f"centroid=({_centroid_pt[0]:.1f},{_centroid_pt[1]:.1f},{_centroid_pt[2]:.1f})")

if not _rigid_bodies:
    print(f"  [RIGID-BODY-V1] No rigid body LMs in optimizable set; rigid bodies skipped")'''


def main():
    apply = '--apply' in sys.argv
    with open(PATH) as f:
        content = f.read()
    if SENTINEL in content:
        print(f'{SENTINEL} already applied. Nothing to do.')
        return
    if OLD not in content:
        print('ERROR: OLD block not found in', PATH)
        sys.exit(1)
    new_content = content.replace(OLD, NEW)
    if not apply:
        print('DRY-RUN. Diff preview:')
        print('-' * 60)
        print('OLD block matched, NEW block ready.')
        print(f'Run with --apply to write changes.')
        return
    shutil.copy(PATH, PATH + '.bak_portofino_rigid')
    with open(PATH, 'w') as f:
        f.write(new_content)
    print(f'Applied. Backup: {PATH}.bak_portofino_rigid')

if __name__ == '__main__':
    main()
