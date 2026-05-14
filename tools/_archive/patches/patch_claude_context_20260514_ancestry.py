#!/usr/bin/env python3
"""
patch_claude_context_20260514_ancestry.py

Logs the 2026-05-14 session in CLAUDE_CONTEXT.md:
  - Discovery: 87% of non-LEAK cams have zero all_leak LMs anchored
  - Analysis of LM ancestry distribution (all_leak/partial/no_leak/no_source)
  - New audit tool: tools/audit/audit_all_leak_opportunities.py
  - calibrate_cam.py upgrade: LEAK ancestry tagging in suggestions
  - Top 12 realistic opportunities for manual marking
  - Strategic implication: structural problem with dataset, not solver

Idempotent via SESSION-2026-05-14-LEAK-ANCESTRY sentinel.
Dry-run by default; pass --apply.

Run from gtamaplib-main/:
  python3 patch_claude_context_20260514_ancestry.py
  python3 patch_claude_context_20260514_ancestry.py --apply
"""
import sys
import shutil
from pathlib import Path

CONTEXT_PATH = Path("tools/CLAUDE_CONTEXT.md")
SENTINEL = "── SESSION-2026-05-14-LEAK-ANCESTRY ──"

OLD_HEADER_LINE = "- **Last session** : 2026-05-13 — (1) Morning cleanup: Ocean near Keys (N) LEAK ground truth committed (f2dca87), 53 .bak files purged (fdf0736), 2 merged branches deleted, .DS_Store nettoyés. (2) Afternoon refactor: 'gtamaplib as dependency' on branch `feature-gtamaplib-dependency` (4 commits, 5840714→dbbc1a1) — vendor/ submodule + sys.modules hijack via gtamaplib_setup.py. 21 scripts patched, 9 audit/ path bugs fixed. **NOT MERGED into feature-svg-map yet** — pending real-world testing."

NEW_HEADER_LINE = "- **Last session** : 2026-05-14 — Discovery: 87% of non-LEAK cams have ZERO all_leak LMs anchored. The dataset is structurally calibrated against calibration-derived LMs (not ground-truth). New audit tool `audit_all_leak_opportunities.py` identifies 1013 potential markings; 12 realistic opportunities (10+ marked cams w/ 5-30 LEAK visible) for next sessions. calibrate_cam.py upgraded: suggestions now tagged with LEAK ancestry (all_leak first). See session log for top opportunities list. **No data changes** — read-only analysis + tool upgrades."

NEW_SECTION = """

---

<!-- ── SESSION-2026-05-14-LEAK-ANCESTRY ── -->
### 2026-05-14 — LEAK ancestry analysis: structural dataset problem identified

**Setup**: Started Thursday midday after Tuesday's big session (cleanup +
dependency refactor). Refactor branch `feature-gtamaplib-dependency`
still not merged; working on `feature-svg-map` (mainline).

**The discovery**

A LEAK cam has its xyz, ypr, AND fov **fixed** to the exact game-engine
values (extracted from the debug overlay). They are NOT calibrated — they
ARE ground truth. So any LM triangulated 100% from LEAK cams is also
ground truth (modulo marker pixel precision).

Ran an ancestry analysis on the 680 landmarks:

| Class | Count | % | Meaning |
|---|---|---|---|
| `all_leak` | 156 | 23% | 100% LEAK-sourced — ground truth |
| `partial_leak` | 63 | 9% | Mixed: ≥1 LEAK in sources |
| `no_leak` | 456 | 67% | 0% LEAK — pure calibration-derived |
| `no_source` | 5 | <1% | Orphan, no source_cameras field |

Then ran an aggregate over the 79 non-LEAK cams' marked LMs (1431 marker
pixels total):

| Marker by ancestry class | Count | % |
|---|---|---|
| markers on `all_leak` LMs | 16 | **1.1%** |
| markers on `partial_leak` LMs | 109 | 7.6% |
| markers on `no_leak` LMs | 844 | **59.0%** |
| markers on `no_source` LMs | 461 | 32.2% |

**87% of non-LEAK cams (69 of 79) have ZERO all_leak LMs marked.**
This includes all the pillar cams: Prison, Vice Beach A/B, Beach,
Motorboats A/B, Keys, Venetian Islands, Brickell, etc.

**Why this matters**: those pillar cams are calibrated entirely against
LMs that themselves carry residual calibration error. Their "anchor"
tier is illusory — they're anchored against fuzziness. Solver can
optimize them to RMS 0', but the absolute positions still drift away
from real game-engine coordinates. This is likely why bundle adjust
plateaus at ~2.95' and won't drop below 2'.

**Solution direction**: NOT a solver fix. NOT exotic retriangulation.
Manual marker work in the UI on pillar cams, prioritizing LEAK LMs
that are likely-visible in each cam's frame.

**Tools delivered this session**

1. `tools/audit/audit_all_leak_opportunities.py` — read-only audit.
   For each non-LEAK cam with zero `all_leak` markings, project all
   `all_leak` LMs into the cam's frame and list those that fall
   in-bounds. Sort cams by opportunity count.

2. `calibrate_cam.py` upgrade [ANCESTRY-V1]: the "LIKELY VISIBLE LMS"
   section now tags each suggestion with its LEAK ancestry and re-sorts
   so `all_leak` appears first.

   Before:
   ```
   [anchor]  dist=  2233m  px≈( 1635,  924)  The Ritz-Carlton Coconut Grove (S)
   [high ]  dist=  5607m  px≈( 1131,  933)  Icon at South Beach
   ```

   After:
   ```
   [anchor LEAK]  dist=  2233m  px≈( 1635,  924)  The Ritz-Carlton Coconut Grove (S)
   [high   ----]  dist=  5607m  px≈( 1131,  933)  Icon at South Beach
   ```

   Labels: `LEAK` = all_leak, `part` = partial_leak, `----` = no_leak,
   `????` = no_source.

**Top 12 realistic opportunities** (10+ LMs already marked AND 5-30
all_leak likely-visible — i.e. cams that ARE well-calibrated enough for
projections to be trustworthy, with substantial LEAK anchoring upside):

| Cam | Marked | LEAK visible |
|---|---|---|
| Highway (Peacock Bay) (A) | 10 | 27 |
| Raul Bautista 03 (Motorboat) | 14 | 23 |
| Vice City 03 (Basketball) | 67 | 16 |
| Beach | 35 | 13 |
| Vice Beach (A) | 45 | 12 |
| Vice Beach (B) | 72 | 12 |
| Jet Ski | 15 | 11 |
| Vice City Postcard | 60 | 11 |
| Convertible | 14 | 9 |
| Skyline | 32 | 8 |
| Prison | 37 | 6 |
| Grassrivers 02 (Watson Bay) | 39 | 6 |

That's ~154 markings to do (likely 5-15 min per cam in the UI). Should
substantially improve global RMS once done across these pillars.

**Cams with anomalously high "visible" counts** (filtered OUT of the
realistic list because projection is unreliable when cam params are
loose): Television (1 marked, 127 visible), Mount Kalaga 02 Helicopter
(38, 123), Ambrosia 04 Fires (49, 115), Mount Kalaga 04 (5, 100),
Motorboats A/B. These project lots of LMs in-frame because their fov
is wide and/or their params are off. Calibrate them properly first
before trusting these projections.

**Strategic note**: this analysis changes the way I think about the
solver loss. RMS of 2.95' on 171 cams looks "good" but most of the
constraint network is held together by no_leak LMs anchored on
no_leak LMs (transitive flou). Real ground-truth anchoring is sparse.
T3 cams will exacerbate this if they're all calibrated against existing
no_leak LMs instead of being grounded into all_leak (or new LEAK cams
if rlx releases more debug overlay data for T3 zones).

**Commits this session**: TBD (this patch + tool commits).

**Next session priorities**:

1. **Marking session on Highway (Peacock Bay) (A)** first (best ratio:
   10 marked, 27 LEAK visible). Use `calibrate_cam.py` for the LEAK-
   first ordered suggestions, mark in UI, save, re-run to verify drop
   in self-source divergence.
2. Then iterate down the top-12 list above. Goal: every pillar cam
   should have ≥3 all_leak LMs marked.
3. After marking, re-run bundle_adjust to see if RMS drops below 2.5'.
4. Older priorities still pending: JSON output for calibration_order;
   fix calibration_order's loss check (U-Turn (NE) false positive);
   C-verticals take 2; D-multi-step relaxation; Pylon (3) bug.
5. **Eventually** decide whether to merge `feature-gtamaplib-dependency`
   into feature-svg-map (still pending real-world test).

**State at end of session**:
- Branch: `feature-svg-map`
- Working tree: clean
- New tool: `tools/audit/audit_all_leak_opportunities.py`
- Upgraded tool: `tools/calibrate_cam.py` (ANCESTRY-V1)
- No data modifications, no calibration changes, no bundle_adjust runs
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
    print(f"  Header update: 'Last session' line → 2026-05-14 ancestry discovery")
    print(f"  Appended: new session log w/ sentinel '{SENTINEL}'")
    print()

    if not apply:
        print("DRY-RUN — no changes written. Pass --apply to write.")
        return

    backup = CONTEXT_PATH.with_suffix(
        CONTEXT_PATH.suffix + ".bak_pre_20260514_ancestry"
    )
    shutil.copy(CONTEXT_PATH, backup)
    print(f"Backup written: {backup}")

    CONTEXT_PATH.write_text(new_text)
    print(f"✓ {CONTEXT_PATH} updated.")


if __name__ == "__main__":
    main()
