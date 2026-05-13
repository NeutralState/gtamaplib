#!/usr/bin/env python3
"""
patch_claude_context_20260513_evening.py

Updates tools/CLAUDE_CONTEXT.md to log the full 2026-05-13 session:
  - Morning cleanup (already logged in commit 3487281, this updates Quick state)
  - Afternoon refactor: "gtamaplib as dependency" on a separate branch
    feature-gtamaplib-dependency (vendor/ submodule + sys.modules hijack)

Idempotent via sentinel SESSION-2026-05-13-DEPENDENCY-REFACTOR.
Dry-run by default; pass --apply.

Run from gtamaplib-main/:
  python3 patch_claude_context_20260513_evening.py
  python3 patch_claude_context_20260513_evening.py --apply
"""
import sys
import shutil
from pathlib import Path

CONTEXT_PATH = Path("tools/CLAUDE_CONTEXT.md")
SENTINEL = "── SESSION-2026-05-13-DEPENDENCY-REFACTOR ──"

# Update Quick state: last session line
OLD_HEADER_LINE = "- **Last session** : 2026-05-13 — Repo cleanup. Commit Ocean near Keys (N) LEAK ground truth (f2dca87). Purged 53 .bak files (49 untracked + 4 tracked in _archive/backups/, commit fdf0736). Deleted 2 merged local branches (feature-rotating-minimap, recover-minimap). Cleaned local .DS_Store files. Working tree clean, pushed."

NEW_HEADER_LINE = "- **Last session** : 2026-05-13 — (1) Morning cleanup: Ocean near Keys (N) LEAK ground truth committed (f2dca87), 53 .bak files purged (fdf0736), 2 merged branches deleted, .DS_Store nettoyés. (2) Afternoon refactor: 'gtamaplib as dependency' on branch `feature-gtamaplib-dependency` (4 commits, 5840714→dbbc1a1) — vendor/ submodule + sys.modules hijack via gtamaplib_setup.py. 21 scripts patched, 9 audit/ path bugs fixed. **NOT MERGED into feature-svg-map yet** — pending real-world testing."

NEW_SECTION = """

---

<!-- ── SESSION-2026-05-13-DEPENDENCY-REFACTOR ── -->
### 2026-05-13 (afternoon) — Phase 13: gtamaplib as dependency (separate branch)

**Trigger**: rlx Discord message ("maybe easier, since it's not a fork, to
make gtamaplib a dependency, and keep the transforms external to it").

**Branch**: `feature-gtamaplib-dependency` (pushed to origin, NOT merged).
The main branch `feature-svg-map` is untouched and remains usable as-is
until the refactor is validated in real use.

**Architecture**:

Before:
```
gtamaplib-main/
├── gtamaplib.py          ← copy of rlx's lib (with 3 cosmetic mods)
├── gtamaputils.py        ← copy of rlx's lib (with 1 cosmetic mod)
├── gtamapdata.py         ← OUR JSON loader (custom)
└── tools/server.py       ← `sys.path.insert(0, REPO); import gtamaplib as ml`
```

After:
```
gtamaplib-main/
├── vendor/
│   └── gtamaplib/        ← rlx's repo as git submodule (pinned a1003c6)
│       ├── gtamaplib.py  ← pristine, untouched
│       ├── gtamaputils.py
│       └── gtamapdata.py ← rlx's hardcoded data (IGNORED via hijack)
├── gtamapdata.py         ← OUR JSON loader (unchanged)
├── gtamaplib_setup.py    ← sys.modules hijack (NEW)
└── tools/server.py       ← `sys.path.insert(...); import gtamaplib_setup;
                              import gtamaplib as ml`
```

**The hijack** (in `gtamaplib_setup.py`):

1. Adds `vendor/` (not `vendor/gtamaplib/`) to sys.path so Python sees
   `gtamaplib` as a **package** (vendor/gtamaplib/__init__.py exists).
   This is essential: rlx's lib uses `from . import gtamapdata as md`,
   which requires package context, not module context.
2. Pre-populates `sys.modules['gtamaplib.gtamapdata']` with OUR root-level
   `gtamapdata.py` BEFORE rlx's `gtamaplib.py` is executed. When rlx's lib
   runs `from . import gtamapdata`, Python finds our pre-registered module
   instead of loading vendor/gtamaplib/gtamapdata.py (with his hardcoded
   data).
3. Re-exports `gtamaplib.gtamaplib`'s public API onto the package
   namespace, so existing `import gtamaplib as ml; ml.Camera(...)` calls
   keep working (without this, `ml.Camera` doesn't exist because rlx's
   `__init__.py` is empty).

**Verified at import-time**:
- `import gtamaplib as ml` loads from `vendor/gtamaplib/__init__.py`
- `import gtamapdata as md` loads from `gtamapdata.py` (ours)
- `md.cameras` = 171 entries (ours, not rlx's ~150 hardcoded)
- `md.landmarks` = 680 entries (ours)
- `ml.Camera`, `ml.intersect_rays`, `ml.find_camera`, etc. all accessible

**Scripts patched** (21 total) via `patch_vendor_hijack_inject.py`:
Each got `import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]`
injected right after the existing `sys.path.insert(0, ...)`.

**Bonus fix**: 9 scripts in `tools/audit/` had a pre-existing path bug
(gotcha #11 of this doc) — `dirname(dirname(__file__))` gave `tools/`
instead of the repo root. Fixed to `dirname×3` in the same patch.
These scripts were previously unrunnable from CLI without
`PYTHONPATH=. python3 ...` workaround.

**Tested end-to-end**:
- `tools/calibrate_cam.py "Ocean near Keys (N)"` renders the full report
  with LEAK ground truth params (matching this morning's commit f2dca87)
- `tools/calibration_order.py --tier unverified --limit 3` correctly
  classifies unverified cams (U-Turn (NE) ✓ AUTO-OPTIMIZE READY, etc.)
- `tools/audit/check_camera_consistency.py` now runs from CLI for the
  first time (path bug + hijack both fix it)
- `import tools.server` resolves cleanly (server boots fine,
  "gtamaplib loaded ✓ — Leak cams: 92 — Leak-anchored landmarks: 60")

**Commits on `feature-gtamaplib-dependency`** (4 progressive, all pushed):
1. `5840714` — submodule + setup file
2. `29cd137` — remove local gtamaplib.py + gtamaputils.py (-3054 lines)
3. `723f9da` — patch 21 scripts (vendor hijack + audit/ path fix)
4. `dbbc1a1` — archive patch script

**How to update vendor/gtamaplib/ when rlx pushes new commits**:
```
cd vendor/gtamaplib && git pull origin main && cd ../..
git add vendor/gtamaplib
git commit -m "Bump vendor/gtamaplib to <commit_sha>"
```

**Convention for NEW scripts** that use gtamaplib (so we don't forget the
hijack):
```python
GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]
import gtamaplib as ml
```

**Merge plan**:
- Use feature-gtamaplib-dependency for next session(s) and confirm
  nothing breaks (run server, do calibrations, run a bundle_adjust,
  etc.)
- When confident: `git checkout feature-svg-map && git merge
  feature-gtamaplib-dependency && git push`
- Alternative: continue all new work on feature-gtamaplib-dependency
  and treat it as the new mainline; merge later when there's nothing
  to lose by doing so.

**Risks worth keeping in mind**:
1. **sys.modules hijack is magic** — when it breaks, the error message
   may be cryptic. Keep `gtamaplib_setup.py` simple and well-commented.
2. **Submodule pin discipline** — if rlx pushes a breaking change to
   `gtamaplib.py`, our scripts may break the moment we bump vendor.
   Test before bumping in production.
3. **Forgetting the hijack import in new scripts** — would silently
   fail because there's no longer a local `gtamaplib.py` to fall back
   on; the script will get `ModuleNotFoundError` immediately.

**Next session priorities**:
1. **Real-world test** of the dependency setup. Run the UI, do a calib
   session, run bundle_adjust, exercise everything. If clean, merge.
2. Decide whether to merge `feature-gtamaplib-dependency` into
   `feature-svg-map` (the obvious move once tested) or treat the new
   branch as the mainline.
3. Pre-T3 priorities (still relevant, unchanged from earlier today):
   - Run calibrate_session on a real goldmine cam (Keys / Motorboats A
     / Mount Kalaga 02 Helicopter)
   - JSON output mode for calibration_order.py
   - Fix calibration_order's loss check (U-Turn (NE) flags ✓ despite
     866' on a medium LM)
   - C — Verticals as solver constraints, take 2
   - D — Multi-step relaxation
   - Pylon (3) LM bug

**State at end of session**:
- `feature-svg-map`: clean, untouched by the refactor (this doc patch
  is the only delta vs cleanup commit)
- `feature-gtamaplib-dependency`: 4 commits ahead, pushed to origin
- Both branches usable; pick depending on whether you want the new
  architecture
"""


def main():
    apply = "--apply" in sys.argv

    if not CONTEXT_PATH.exists():
        print(f"ERROR: {CONTEXT_PATH} not found. Run from gtamaplib-main/.")
        sys.exit(1)

    text = CONTEXT_PATH.read_text()

    if SENTINEL in text:
        print(f"✓ Sentinel '{SENTINEL}' already present — patch already applied.")
        return

    if OLD_HEADER_LINE not in text:
        print("ERROR: expected header line not found. File may have diverged.")
        print(f"Looking for: {OLD_HEADER_LINE[:80]}...")
        sys.exit(1)

    new_text = text.replace(OLD_HEADER_LINE, NEW_HEADER_LINE, 1)
    new_text = new_text.rstrip() + "\n" + NEW_SECTION + "\n"

    old_lines = text.count("\n")
    new_lines = new_text.count("\n")
    print("=== Patch summary ===")
    print(f"  Old: {old_lines} lines")
    print(f"  New: {new_lines} lines (+{new_lines - old_lines})")
    print(f"  Header update: 'Last session' line updated with afternoon work")
    print(f"  Appended: new session log section with sentinel '{SENTINEL}'")
    print()

    if not apply:
        print("DRY RUN — no changes written. Pass --apply to write.")
        return

    backup = CONTEXT_PATH.with_suffix(
        CONTEXT_PATH.suffix + ".bak_pre_20260513_evening"
    )
    shutil.copy(CONTEXT_PATH, backup)
    print(f"Backup written: {backup}")

    CONTEXT_PATH.write_text(new_text)
    print(f"✓ {CONTEXT_PATH} updated.")


if __name__ == "__main__":
    main()
