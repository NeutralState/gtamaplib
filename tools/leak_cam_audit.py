#!/usr/bin/env python3
"""
leak_cam_audit.py — Single source of truth for constraint-class semantics.

Loads gtamapdata/leak_cam_audit.json once and exposes a small API that every
other tool imports instead of re-implementing the class -> DOF logic.

Per-class DOF locking
---------------------

    +-----------------------+----------------------------------------+
    | constraint_class      | DOF locked / DOF refinable             |
    +-----------------------+----------------------------------------+
    | A_full_hud            | locked: xyz, ypr, fov                  |
    |                       | refinable: (none — anchor)             |
    +-----------------------+----------------------------------------+
    | B_pos_fov_player      | locked: xyz, fov                       |
    |                       | refinable: ypr (with soft roll prior)  |
    +-----------------------+----------------------------------------+
    | C_pos_fov_only        | locked: xyz, fov                       |
    |                       | refinable: ypr                         |
    +-----------------------+----------------------------------------+
    | Cm_pos_only           | locked: xyz                            |
    |                       | refinable: ypr, fov                    |
    +-----------------------+----------------------------------------+
    | D_no_ground_truth     | locked: (none)                         |
    |                       | refinable: xyz, ypr, fov               |
    +-----------------------+----------------------------------------+
    | X_invalid_ground_truth| EXCLUDED (no operations allowed)       |
    +-----------------------+----------------------------------------+

Cams with no audit entry are treated as ordinary non-leak calibration cams
(everything refinable). This matches today's behavior for non-leak cams.

The audit file is the canonical reference for `constraint_class`. The same
value is also written into `cameras.json` by `migrate_constraint_classes.py`
so downstream tools don't need to load the audit on every call. This helper
loads the audit JSON lazily on first use.
"""

from __future__ import annotations

import json
import os
from typing import Optional

# DOF labels used everywhere
DOF_XYZ = "xyz"
DOF_YPR = "ypr"
DOF_FOV = "fov"
ALL_DOF = frozenset({DOF_XYZ, DOF_YPR, DOF_FOV})

# Per-class locked DOF (the rest is refinable)
LOCKED_DOF_BY_CLASS = {
    "A_full_hud":            frozenset({DOF_XYZ, DOF_YPR, DOF_FOV}),
    "B_pos_fov_player":      frozenset({DOF_XYZ, DOF_FOV}),
    "C_pos_fov_only":        frozenset({DOF_XYZ, DOF_FOV}),
    "Cm_pos_only":           frozenset({DOF_XYZ}),
    "D_no_ground_truth":     frozenset(),
    "X_invalid_ground_truth": None,  # excluded
}

# Soft-prior config for class B. Used as `loss += (roll / SIGMA) ** 2`
# inside the optimization, so SIGMA is in degrees.
# Roll of 10 deg costs (10/SIGMA)**2 = 25 at SIGMA=2, i.e. roughly comparable
# to a 5 arcmin RMS contribution per LM. Tunable.
CLASS_B_ROLL_PRIOR_SIGMA_DEG = 2.0

# A class is "anchor-equivalent for triangulation" if its xyz is locked.
# Used by compute_confidence_tiers to know which cams contribute trusted rays.
_TRIANGULATION_TRUSTED_CLASSES = frozenset({
    "A_full_hud",
    "B_pos_fov_player",
    "C_pos_fov_only",
    "Cm_pos_only",
})

VALID_CLASSES = frozenset(LOCKED_DOF_BY_CLASS.keys())


# ----------------------------------------------------------------------
# JSON loading (lazy, cached)
# ----------------------------------------------------------------------

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_DIR = os.path.dirname(_THIS_DIR)
_AUDIT_PATH = os.path.join(_REPO_DIR, "gtamapdata", "leak_cam_audit.json")

_audit_cache: Optional[dict] = None


def _load_audit() -> dict:
    """Load and cache leak_cam_audit.json. Returns {} if not found."""
    global _audit_cache
    if _audit_cache is not None:
        return _audit_cache
    if not os.path.exists(_AUDIT_PATH):
        _audit_cache = {}
        return _audit_cache
    with open(_AUDIT_PATH) as f:
        data = json.load(f)
    # Strip _meta key — only cam entries
    _audit_cache = {k: v for k, v in data.items() if k != "_meta"}
    return _audit_cache


def reload_audit() -> None:
    """Force a re-read of the audit file. Useful in long-running processes
    after an external edit (e.g. the dashboard)."""
    global _audit_cache
    _audit_cache = None
    _load_audit()


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def get_class(cam_name: str, cameras: Optional[dict] = None) -> Optional[str]:
    """Return the constraint_class for `cam_name`, or None if not in the audit.

    If `cameras` (the cameras.json dict) is supplied and contains a
    `constraint_class` field on this cam, that value wins. This lets tools
    pass the loaded cameras.json once and avoid the audit lookup.

    Returns None for cams with no audit entry (= ordinary non-leak cam).
    """
    if cameras is not None:
        cam_data = cameras.get(cam_name)
        if isinstance(cam_data, dict):
            cls = cam_data.get("constraint_class")
            if cls in VALID_CLASSES:
                return cls
            if cls is not None:
                # cameras.json has a value but it's invalid — fall through to
                # audit lookup to be safe, but flag.
                pass
    audit = _load_audit()
    entry = audit.get(cam_name)
    if not isinstance(entry, dict):
        return None
    cls = entry.get("constraint_class")
    return cls if cls in VALID_CLASSES else None


def get_locked_dof(cam_name: str, cameras: Optional[dict] = None) -> frozenset:
    """Return the set of DOF labels ({'xyz', 'ypr', 'fov'}) that are locked
    (ground-truth) for `cam_name`. Empty frozenset for cams with no audit
    entry (= fully refinable). Raises ValueError for excluded (class X) cams.
    """
    cls = get_class(cam_name, cameras=cameras)
    if cls is None:
        return frozenset()
    locked = LOCKED_DOF_BY_CLASS.get(cls)
    if locked is None:
        raise ValueError(
            f"Cam {cam_name!r} is class {cls!r} — excluded. "
            "Caller should skip this cam, not query its DOF."
        )
    return locked


def get_refinable_dof(cam_name: str, cameras: Optional[dict] = None) -> frozenset:
    """Complement of get_locked_dof. Returns the DOF the solver may move."""
    cls = get_class(cam_name, cameras=cameras)
    if cls is None:
        return ALL_DOF  # no audit entry = ordinary cam, everything refinable
    locked = LOCKED_DOF_BY_CLASS.get(cls)
    if locked is None:
        raise ValueError(f"Cam {cam_name!r} is class {cls!r} — excluded.")
    return ALL_DOF - locked


def is_excluded(cam_name: str, cameras: Optional[dict] = None) -> bool:
    """True iff this cam is class X (must be skipped by every solver step)."""
    cls = get_class(cam_name, cameras=cameras)
    return cls == "X_invalid_ground_truth"


def is_anchor(cam_name: str, cameras: Optional[dict] = None) -> bool:
    """True iff this cam is class A — full ground truth, anchor tier."""
    return get_class(cam_name, cameras=cameras) == "A_full_hud"


def is_audit_cam(cam_name: str, cameras: Optional[dict] = None) -> bool:
    """True iff this cam has an audit entry (i.e. is a leak/marketing cam,
    not an ordinary calibration cam)."""
    return get_class(cam_name, cameras=cameras) is not None


def is_triangulation_trusted(cam_name: str, cameras: Optional[dict] = None) -> bool:
    """True iff this cam's xyz is locked (i.e. its rays are ground-truth for
    triangulating LMs). Classes A, B, C, Cm. Excludes D (no xyz lock) and X."""
    return get_class(cam_name, cameras=cameras) in _TRIANGULATION_TRUSTED_CLASSES


def get_audit_entry(cam_name: str) -> Optional[dict]:
    """Return the full audit entry dict (hud_C_xyz, hud_dir_ypr, notes, ...)
    for `cam_name`, or None if not in the audit. For detailed inspection
    (e.g. by the migration tool); most callers should use the higher-level
    API above instead."""
    audit = _load_audit()
    entry = audit.get(cam_name)
    return entry if isinstance(entry, dict) else None


def get_hud_ground_truth(cam_name: str) -> dict:
    """Return whatever HUD-derived ground-truth values are available for
    `cam_name`, as a dict possibly containing keys 'xyz', 'ypr', 'fov'.
    Empty dict if cam not in audit or no ground-truth values."""
    entry = get_audit_entry(cam_name)
    if entry is None:
        return {}
    out = {}
    if entry.get("hud_C_xyz") is not None:
        out["xyz"] = list(entry["hud_C_xyz"])
    if entry.get("hud_dir_ypr") is not None:
        out["ypr"] = list(entry["hud_dir_ypr"])
    if entry.get("hud_fov") is not None:
        out["fov"] = entry["hud_fov"]
    return out


def class_b_roll_prior_sigma() -> float:
    """Public accessor for the soft-prior sigma used by class B in refinement.
    Exposed so tools can document the value they use without re-importing
    a private constant."""
    return CLASS_B_ROLL_PRIOR_SIGMA_DEG


# ----------------------------------------------------------------------
# CLI: quick inspection
# ----------------------------------------------------------------------

def _main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Quick CLI to inspect the constraint class of a cam.")
    ap.add_argument("cam_name", nargs="?",
                    help="Cam name. If omitted, print a class summary.")
    args = ap.parse_args()

    audit = _load_audit()
    if not audit:
        print(f"ERROR: audit file not found at {_AUDIT_PATH}")
        return 1

    if args.cam_name is None:
        from collections import Counter
        c = Counter(e.get("constraint_class") for e in audit.values())
        print(f"Audit entries: {len(audit)}")
        for cls in sorted(c, key=lambda x: (x is None, x)):
            print(f"  {str(cls):30s} {c[cls]:>4d}")
        return 0

    name = args.cam_name
    cls = get_class(name)
    if cls is None:
        print(f"{name!r}: no audit entry (ordinary calibration cam — all DOF refinable).")
        return 0
    locked = get_locked_dof(name) if not is_excluded(name) else None
    refinable = get_refinable_dof(name) if not is_excluded(name) else None
    print(f"{name!r}:")
    print(f"  class:     {cls}")
    if locked is None:
        print(f"  status:    EXCLUDED (skip in all solver steps)")
    else:
        print(f"  locked:    {sorted(locked) if locked else '(none)'}")
        print(f"  refinable: {sorted(refinable) if refinable else '(none — anchor)'}")
    gt = get_hud_ground_truth(name)
    if gt:
        print(f"  HUD ground-truth values:")
        for k, v in gt.items():
            print(f"    {k}: {v}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main())
