#!/usr/bin/env python3
"""
patch_claude_context_20260513_cleanup.py

Updates tools/CLAUDE_CONTEXT.md with:
  1. Quick state header: Last session date 2026-05-12 → 2026-05-13
  2. Appends new section: ### 2026-05-13 — Repo cleanup

Idempotent via sentinel check (SESSION-2026-05-13-CLEANUP).
Dry-run by default; pass --apply to write.

Run from gtamaplib-main/:
  python3 patch_claude_context_20260513_cleanup.py            # dry-run
  python3 patch_claude_context_20260513_cleanup.py --apply    # write
"""
import sys
import shutil
from pathlib import Path

CONTEXT_PATH = Path("tools/CLAUDE_CONTEXT.md")
SENTINEL = "── SESSION-2026-05-13-CLEANUP ──"

OLD_HEADER_LINE = "- **Last session** : 2026-05-12 — Phase 11 verticals end-to-end (overlay UI toggle V), physical z bounds, tier-weighted optimize, batch_optimize.py. Discord mapper+ obtenu de martipk. Marti confirms \"Four Seasons (BW) circular\" — already-anchored LMs don't get re-triangulated."

NEW_HEADER_LINE = "- **Last session** : 2026-05-13 — Repo cleanup. Commit Ocean near Keys (N) LEAK ground truth (f2dca87). Purged 53 .bak files (49 untracked + 4 tracked in _archive/backups/, commit fdf0736). Deleted 2 merged local branches (feature-rotating-minimap, recover-minimap). Cleaned local .DS_Store files. Working tree clean, pushed."

# The new session log section to append at the very end of the file
NEW_SECTION = """

---

<!-- ── SESSION-2026-05-13-CLEANUP ── -->
### 2026-05-13 — Repo cleanup (housekeeping, no code changes)

**Pre-cleanup state**: working tree had Ocean near Keys (N) cameras.json mods
uncommitted from previous PM session, 62 .bak files scattered across `tools/`,
`gtamapdata/`, and `tools/_archive/backups/` (4 of those tracked by git despite
.gitignore covering `*.bak*` — predated the rule). 5 local branches, 3 of them
merged-and-stale.

**Actions** (3 commits, all pushed to `origin/feature-svg-map`):

1. **`f2dca87` — Ocean near Keys (N) LEAK ground truth committed**:
   `gtamapdata/cameras.json` reflects exact game-debug-overlay params
   (xyz=(-3442.897, -7191.001, 0.501), ypr=(358.539, -2.172, -1.245),
   fov=(81.924, 52.054)). Refinement of ~0.1° from previously-converged values.
   No RMS impact (2.95→2.97 from yesterday already accounted).

2. **`fdf0736` — .bak files purged**:
   - 49 untracked .bak files in `tools/_archive/backups/` deleted locally
     (gitignored, no commit needed for these)
   - 9 untracked .bak files in `tools/` and `gtamapdata/` deleted locally
     (recent backups from yesterday's PM session, e.g. `*.bak_pre_phase12`,
     `*.bak_pre_onk_groundtruth`, `*.bak_pre_session_pm`)
   - **4 tracked .bak files** in `tools/_archive/backups/` removed via
     `git rm` (predated the `*.bak*` .gitignore rule):
     * `calib_fresh.html.bak_addpx`
     * `gtamapdata.py.bak_xyz_none`
     * `server.py.bak`
     * `server.py.bak2`
   - Net diff: 4 files removed, 2830 lines deleted from tracked history

3. **Branch cleanup** (local only, not committed):
   - Deleted `feature-rotating-minimap` (merged into feature-svg-map)
   - Deleted `recover-minimap` (merged into feature-svg-map)
   - **Kept**: `main` (GitHub default branch, useful as local reference),
     `item-3-intersect-rays` (not merged technically but functionality is
     shipped in feature-svg-map via Phase 8.1/8.2 — leave for now)
   - Result: `git branch` is now `feature-svg-map *`, `item-3-intersect-rays`, `main`

4. **macOS .DS_Store cleanup** (local only):
   - Deleted 8 `.DS_Store` files across the repo (all gitignored, none tracked).
   - macOS will recreate them as needed; no impact on git.

**Things investigated, decided to keep**:
- `tools/_archive/backups/calib_fresh.html` (56KB, 1189 lines): an older
  pre-bundle-adjust-v2 checkpoint of the calib tool (current is 3542 lines).
  Was deliberately archived in commit `a3851f6 chore: archive applied minimap
  patches and stale files`. Not referenced in code, no CLAUDE_CONTEXT mention,
  but kept as historical reference since `_archive/backups/` is gitignored and
  it costs nothing locally.
- `__init__.py` at repo root (0 bytes, tracked since Initial commit): empty
  Python package marker. Not referenced anywhere (the grep hits were just
  docstring `"Run from gtamaplib-main/"` strings). Convention from rlx's
  initial commit; safer to leave alone — 0 bytes harmless.

**Final state**:
- Working tree clean
- `feature-svg-map` is `origin/feature-svg-map` (3 commits ahead of pre-session HEAD `2b43446`, all pushed)
- No more .bak files anywhere
- 3 local branches instead of 5
- Repo ready for next productive session

**No data or solver changes this session**. RMS still ~2.95-2.97' on
171 cams, 680 LMs. Phase 12 workflow tools unchanged.

**Next session priorities** (unchanged from 2026-05-12 late PM):
1. Test calibration_order + calibrate_session on a real goldmine cam
   (Keys 56 LMs / Motorboats A 49 LMs / Mount Kalaga 02 Helicopter 38 LMs)
2. JSON output mode for calibration_order.py (replace fragile text-parsing
   coupling in calibrate_session.py)
3. Fix calibration_order's loss check (currently uses only anchor+high, so
   U-Turn (NE) flags as ✓ despite 866' loss on medium LM)
4. C — Verticals as solver constraints, take 2 (weight tuning experiment)
5. D — Multi-step relaxation
6. Pylon (3) LM bug (deferred but still extant)
"""


def main():
    apply = "--apply" in sys.argv

    if not CONTEXT_PATH.exists():
        print(f"ERROR: {CONTEXT_PATH} not found. Run from gtamaplib-main/.")
        sys.exit(1)

    text = CONTEXT_PATH.read_text()

    # Idempotency check
    if SENTINEL in text:
        print(f"✓ Sentinel '{SENTINEL}' already present — patch already applied.")
        print("  Nothing to do.")
        return

    # Sanity: old header line must be present (otherwise the file diverged)
    if OLD_HEADER_LINE not in text:
        print(f"ERROR: expected header line not found:")
        print(f"  {OLD_HEADER_LINE[:80]}...")
        print("File may have diverged; refusing to patch.")
        sys.exit(1)

    new_text = text.replace(OLD_HEADER_LINE, NEW_HEADER_LINE, 1)
    new_text = new_text.rstrip() + "\n" + NEW_SECTION + "\n"

    # Stats
    old_lines = text.count("\n")
    new_lines = new_text.count("\n")
    print(f"=== Patch summary ===")
    print(f"  Old: {old_lines} lines")
    print(f"  New: {new_lines} lines (+{new_lines - old_lines})")
    print(f"  Header update: 'Last session' line 2026-05-12 → 2026-05-13")
    print(f"  Appended: new section with sentinel '{SENTINEL}'")
    print()

    if not apply:
        print("DRY RUN — no changes written. Pass --apply to write.")
        return

    # Backup before write
    backup = CONTEXT_PATH.with_suffix(CONTEXT_PATH.suffix + ".bak_pre_20260513_cleanup")
    shutil.copy(CONTEXT_PATH, backup)
    print(f"Backup written: {backup}")

    CONTEXT_PATH.write_text(new_text)
    print(f"✓ {CONTEXT_PATH} updated.")


if __name__ == "__main__":
    main()
