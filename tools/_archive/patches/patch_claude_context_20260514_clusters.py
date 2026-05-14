#!/usr/bin/env python3
"""
patch_claude_context_20260514_clusters.py

Logs the 2026-05-14 afternoon session in CLAUDE_CONTEXT.md (same day as the
morning's ancestry discovery, continuing into clusters analysis):
  - LEAK marker quality audit (audit_leak_marker_quality.py) — 15 CASE A
    outliers identified
  - LEAK influence tree analysis (audit_leak_influence_tree.py) — 4 macro
    clusters discovered, most LEAK cams have low downstream reach
  - Strategic reframing: Metro/Tennis are NOT high-influence (rank 22-23),
    AIWE/Diner cluster dominates

Idempotent via SESSION-2026-05-14-CLUSTERS sentinel.
Dry-run by default; pass --apply.

Run from gtamaplib-main/:
  python3 patch_claude_context_20260514_clusters.py
  python3 patch_claude_context_20260514_clusters.py --apply
"""
import sys
import shutil
from pathlib import Path

CONTEXT_PATH = Path("tools/CLAUDE_CONTEXT.md")
SENTINEL = "── SESSION-2026-05-14-CLUSTERS ──"

OLD_HEADER_LINE = "- **Last session** : 2026-05-14 — Discovery: 87% of non-LEAK cams have ZERO all_leak LMs anchored. The dataset is structurally calibrated against calibration-derived LMs (not ground-truth). New audit tool `audit_all_leak_opportunities.py` identifies 1013 potential markings; 12 realistic opportunities (10+ marked cams w/ 5-30 LEAK visible) for next sessions. calibrate_cam.py upgraded: suggestions now tagged with LEAK ancestry (all_leak first). See session log for top opportunities list. **No data changes** — read-only analysis + tool upgrades."

NEW_HEADER_LINE = "- **Last session** : 2026-05-14 (afternoon) — Two new audit tools commited (b24bc26): (1) `audit_leak_marker_quality.py` flagged 15 CASE A reprojection outliers on LEAK markings (top: Gas Station (Jason) → 4937 E Hwy 98 at 92.8'). (2) `audit_leak_influence_tree.py` BFS dependency tree from each LEAK cam — reveals 4 macro-clusters; AIWE/Diner cluster dominates (14 LEAK cams sharing reach to 22 calibrated cams + 186 LMs, depth 11). Metro/Tennis Stadium surprisingly low rank (22-23) — their sourced LMs are rarely marked anchor+high downstream. 65 of 92 LEAK cams have zero downstream reach. Earlier same day: ancestry discovery (87% of non-LEAK cams have zero all_leak markings) + calibrate_cam.py ANCESTRY-V1 tagging + audit_all_leak_opportunities.py tool. No data changes."

NEW_SECTION = """

---

<!-- ── SESSION-2026-05-14-CLUSTERS ── -->
### 2026-05-14 (afternoon) — LEAK marker audit + dependency tree clusters

**Setup**: Continuing the same day as the morning's ancestry discovery
session. Goal was first to check if LEAK marker errors might invalidate
the ground-truth assumption, then to map the dependency tree structure
so we know which LEAK cams matter most.

**Pre-session sanity check**: 4 files use `LEAK_CAMS` variable.
3 use date-based detection (`bundle_adjust.py`, `server.py`,
`audit/audit_fixed_landmarks_quality.py`) — consistent with our analysis
across all recent sessions. 1 uses a hardcoded list
(`audit/audit_leak_consistency.py`) which incorrectly includes
Vice Beach A/B and is missing ~40 newer LEAK cams. The 3 production
files are NOT affected; `audit_leak_consistency.py` is the only one
out of sync — flagged for cleanup or deletion in a later session.
The new audit tools use date-based detection so they're consistent
with the production state.

#### Part 1 — LEAK marker quality audit

**Tool**: `tools/audit/audit_leak_marker_quality.py`

For each marker pixel on a LEAK cam, compute reprojection error in
arcmin. Because LEAK cam params are fixed (extracted from game debug
overlay, not optimized), any error is either:
  - **CASE A** (cam IS source of LM): geometrically impossible to
    have non-zero error at triangulation time → drift now means the
    marker was edited or the LM xyz was changed without retriangulation
  - **CASE B** (cam NOT source of LM): error reflects tension between
    this view and the triangulated LM position somewhere else

**Audited 311 markings across 92 LEAK cams** (some LEAK cams have no
complete params and were skipped).

Distribution:
- err < 1':   176 (159 A, 17 B) — clean
- err 1-3':    46 (40 A, 6 B)
- err 3-10':   62 (45 A, 17 B)
- err 10-30':  18 (12 A, 6 B) — outliers
- err 30-60':   6 (2 A, 4 B) — outliers
- err ≥ 60':    3 (1 A, 2 B) — severe

**15 CASE A outliers** (the most actionable — these are bugs):

| err | cam → LM |
|---|---|
| 92.8' | Gas Station (Jason) → 4937 E Hwy 98 (Gas Station) (SE) |
| 39.1' | Diner (S) → Easy Inn Sign |
| 33.2' | Diner (E) → Billboard (Hank's Waffles) (BE) |
| 30.0' | Diner (NE) → White Pole |
| 24.7' | Diner (E) → White Pole |
| 23.4' | Diner (SE) (A) → Traffic Sign |
| 21.6' | Car Wash → Tall Double Billboard |
| 18.9' | Gas Station (Lucia) → Oval Yellow Sign |
| 18.6' | Diner (NE) → Domed Hills Sign (TW) |
| 18.2' | Welcome Center (E) → Art Deco Welcome Center (S) |
| 17.2' | Diner (E) → Domed Hills Sign (TW) |
| 13.4' | Welcome Center (W) → Art Deco Welcome Center (S) |
| 11.4' | Diner (NE) → Mount Waffles (TW) |
| 10.9' | Car Wash → Springfield Community Church (CW) |
| 10.0' | Diner (N) → Mount Waffles (TW) |

**Patterns observed**:
- Diner (E) appears in 3 outliers — possibly a systematic marker offset
  issue on that one cam, OR the LMs themselves (White Pole, Domed Hills
  Sign, Billboard) have incorrect xyz
- "Mount Waffles (TW)" appears twice with Diner cams (NE, N) at 10-11' —
  borderline outliers suggesting that specific LM may have minor xyz drift
- "Art Deco Welcome Center (S)" appears in BOTH Welcome Center (E) and
  Welcome Center (W) — strongly suggests the LM xyz is offset; the
  Welcome Center cams agree with each other but not with their own LM

**CASE B severe outliers** (top 3):
- 166.4': Diner (SE) (A) → White Pole — White Pole xyz is suspect across
  multiple Diner views
- 98.1':  Diner (E) → Mount Mountain
- 54.1':  Police Chase (F) → White Billboard (Hamlet) — and same LM at
  47.4' (Police Chase H), 46.3' (Police Chase G), 35.5' (Police Chase E),
  25.7' (Police Chase I). FIVE Police Chase cams agree that this LM is
  in tension. Strong evidence that "White Billboard (Hamlet)" has a
  bad xyz.

#### Part 2 — LEAK influence tree

**Tool**: `tools/audit/audit_leak_influence_tree.py`

BFS dependency tree from each LEAK cam, using **B-strict** criterion:
cam C depends on cam B if C marks an LM L at tier `anchor` or `high`
AND B is in L.source_cameras. Each generation alternates LMs ↔ cams.
JSON saved to `tools/generated/leak_influence_tree.json` (regenerable,
not git-tracked).

**4 macro-clusters in the dataset**:

| Cluster | LEAK cams in it | Reach (cams / LMs) | Depth |
|---|---|---|---|
| Main (AIWE + Diner + Car Wash + Gas Stations + Hedge B) | 14 | 22 / 186 | 11 |
| Port / Sidewalk (Jason) (E) | 2 | 10 / 219 | 5 |
| Glitch (A) / Highway (NE) / Tennis Court (NE) | 3 | 4 / 26 | 5 |
| Airport (X) / Hangar (A) / Metro (SE) (A) (4K) / Tennis Stadium (4K) | 4 | 3 / 18 | 7 |
| Welcome Center (E/W) | 2 | 2 / 8 | 3 |
| Diner (SE) (A/B) | 2 | 1 / 3 | 3 |

**65 of 92 LEAK cams** have ZERO downstream cam reach. They either:
- Have no markings (Auto Shop x4, Boat Jason, Diner, Farm, Hangar B/C,
  Hedge D, Highway E, etc.) — reserve of potential anchors
- Have markings only at tier medium/low/unverified — not part of the
  trusted anchor graph
- Source LMs that nobody marked at anchor+high

**KEY STRATEGIC REVERSAL**: I expected Metro (SE) (A) (4K) and
Tennis Stadium (4K) to be high-influence because they source the
Brickell anchors (Ritz-Carlton, Nine at Mary Brickell, Four Seasons
40NE). They rank **22 and 23 out of LEAK cams**, with only 3 downstream
cams. Why: these LMs they source are NOT marked anchor+high on most
downstream cams. The Brickell anchors exist but are not pulled into
the trusted constraint network. **Marking these Brickell LMs as
anchor+high on more cams (especially Vice Beach A/B, Prison) would
massively elevate Metro/Tennis influence and likely improve global RMS.**

**Within the Main cluster** (the 14 LEAK cams with reach 22/186):
- All 14 reach the same 22 calibrated cams, but via different paths
- AIWE and Car Wash differ by exactly 1 cam (each includes the other)
- AIWE sources 70 LMs directly in gen 1 — by far the biggest direct
  contribution. Gen 2 onwards reaches diminishingly via interlocking
  rebounds (LM → cam → LM → cam ...)
- Total tree depth of 11 = 5-6 hops of indirection from the LEAK cam
  to the most-downstream LM
- **AIWE markers must be impeccable** — any drift cascades to 22 cams

#### Strategic implications for next sessions

1. **Direct marker fixes** are high-leverage on the AIWE/Diner cluster
   (gen 1 of 70 LMs for AIWE alone). The 15 CASE A outliers from
   Part 1 are the obvious starting set.
2. **Most influence is at gen 1** (direct LMs sourced). The deep tree
   adds reach but each subsequent generation has diminishing weight.
3. **Marking sessions on pillar cams** (Vice Beach A/B, Prison, etc.)
   to add Brickell LEAK LMs (sourced by Metro/Tennis) would activate
   the currently-low-influence cluster 4 and probably drop global RMS.
4. **65 LEAK cams with zero reach** is a reserve — most are unused or
   only marked at low/unverified tier. Some may be geographic isolates,
   others may just need their existing markings re-tiered to anchor/high.

#### Pending priorities (carried over)

1. Marking session on Highway (Peacock Bay) (A) — best all_leak
   opportunity from earlier today (10 marked, 27 LEAK visible)
2. Fix the 15 CASE A outliers (this session's main actionable list)
3. JSON output for calibration_order.py
4. Fix calibration_order's loss check (U-Turn (NE) false positive)
5. C — Verticals as solver constraints, take 2
6. D — Multi-step relaxation
7. Pylon (3) LM bug
8. Decide whether to merge `feature-gtamaplib-dependency` into
   feature-svg-map (still pending real-world test)
9. Cleanup: `audit_leak_consistency.py` has obsolete hardcoded LEAK list,
   either fix it or delete it

#### State at end of session

- Branch: `feature-svg-map`
- Working tree: clean
- New tools (commit b24bc26):
  - `tools/audit/audit_leak_marker_quality.py`
  - `tools/audit/audit_leak_influence_tree.py`
- Generated artifact (not tracked):
  - `tools/generated/leak_influence_tree.json`
- No data modifications, no calibrations, no bundle_adjust runs
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
    print(f"  Header update: 'Last session' line → 2026-05-14 (afternoon) clusters")
    print(f"  Appended: new session log w/ sentinel '{SENTINEL}'")
    print()

    if not apply:
        print("DRY-RUN — no changes written. Pass --apply to write.")
        return

    backup = CONTEXT_PATH.with_suffix(
        CONTEXT_PATH.suffix + ".bak_pre_20260514_clusters"
    )
    shutil.copy(CONTEXT_PATH, backup)
    print(f"Backup written: {backup}")

    CONTEXT_PATH.write_text(new_text)
    print(f"✓ {CONTEXT_PATH} updated.")


if __name__ == "__main__":
    main()
