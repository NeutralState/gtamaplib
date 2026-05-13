"""
gtamaplib_setup.py — make `vendor/gtamaplib/` importable as `gtamaplib`,
while routing its internal `from . import gtamapdata` to OUR JSON-based
gtamapdata module at the repo root.

Usage: at the top of any script that uses gtamaplib, do:

    import gtamaplib_setup  # noqa: F401
    import gtamaplib as ml

This must be imported BEFORE `import gtamaplib` for the hijack to work.

How it works:
1. vendor/gtamaplib/ is a Python package (has __init__.py).
2. We add `vendor/` (the PARENT) to sys.path so `import gtamaplib` finds
   the package and `from . import gtamapdata` becomes a valid relative
   import.
3. BEFORE rlx's gtamaplib.py module runs, we pre-populate
   `sys.modules['gtamaplib.gtamapdata']` with OUR root-level gtamapdata.py.
   When rlx's lib runs `from . import gtamapdata as md`, Python finds our
   pre-registered module and uses it instead of vendor/gtamaplib/gtamapdata.py
   (with rlx's hardcoded data).
4. rlx's __init__.py is empty, so `import gtamaplib as ml` only exposes the
   package shell — not Camera, intersect_rays, find_camera, etc. (which live
   in gtamaplib.gtamaplib). To keep the original `ml.Camera` / `ml.find_camera`
   API working without touching scripts, we explicitly import the inner
   `gtamaplib` module and re-export its public names onto the package.

This file is idempotent: safe to call multiple times.
"""
import os
import sys
import importlib
import importlib.util

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_VENDOR_DIR = os.path.join(_THIS_DIR, "vendor")
_VENDOR_LIB_DIR = os.path.join(_VENDOR_DIR, "gtamaplib")
_OUR_GTAMAPDATA = os.path.join(_THIS_DIR, "gtamapdata.py")

_SETUP_DONE_KEY = "_gtamaplib_setup_done"
if getattr(sys, _SETUP_DONE_KEY, False):
    pass  # already configured, no-op
else:
    # Sanity checks
    if not os.path.isdir(_VENDOR_LIB_DIR):
        raise RuntimeError(
            f"gtamaplib_setup: vendor dir not found at {_VENDOR_LIB_DIR}. "
            "Did you `git submodule update --init`?"
        )
    if not os.path.isfile(os.path.join(_VENDOR_LIB_DIR, "__init__.py")):
        raise RuntimeError(
            f"gtamaplib_setup: __init__.py missing in {_VENDOR_LIB_DIR}. "
            "The vendor dir must be a Python package."
        )
    if not os.path.isfile(_OUR_GTAMAPDATA):
        raise RuntimeError(
            f"gtamaplib_setup: our gtamapdata.py not found at {_OUR_GTAMAPDATA}. "
            "This refactor assumes gtamapdata.py sits at the repo root."
        )

    # Step 1 — Add vendor/ to sys.path
    if _VENDOR_DIR not in sys.path:
        sys.path.insert(0, _VENDOR_DIR)

    # Step 2 — Trigger the gtamaplib package init (empty __init__.py)
    gtamaplib_pkg = importlib.import_module("gtamaplib")

    # Step 3 — Build & register OUR gtamapdata under the qualified name
    #          BEFORE rlx's gtamaplib module runs
    spec = importlib.util.spec_from_file_location(
        "gtamaplib.gtamapdata", _OUR_GTAMAPDATA
    )
    our_gtamapdata = importlib.util.module_from_spec(spec)
    sys.modules["gtamaplib.gtamapdata"] = our_gtamapdata
    sys.modules["gtamapdata"] = our_gtamapdata  # top-level alias too
    setattr(gtamaplib_pkg, "gtamapdata", our_gtamapdata)
    spec.loader.exec_module(our_gtamapdata)

    # Step 4 — Now import rlx's inner gtamaplib module (which contains
    #          Camera, Map, intersect_rays, find_camera, etc.) and re-export
    #          its public names onto the package, so `import gtamaplib as ml`
    #          gives access to `ml.Camera`, `ml.intersect_rays`, etc.
    inner = importlib.import_module("gtamaplib.gtamaplib")
    for name in dir(inner):
        if name.startswith("_"):
            continue
        if not hasattr(gtamaplib_pkg, name):
            setattr(gtamaplib_pkg, name, getattr(inner, name))

    setattr(sys, _SETUP_DONE_KEY, True)
