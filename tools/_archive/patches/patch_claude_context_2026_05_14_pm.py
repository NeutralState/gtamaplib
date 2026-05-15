#!/usr/bin/env python3
"""
patch_claude_context_2026_05_14_pm.py

Append the 2026-05-14 afternoon + evening session log to
tools/CLAUDE_CONTEXT.md. Idempotent via sentinel.

Run from gtamaplib-main/:
  python3 patch_claude_context_2026_05_14_pm.py             # dry-run
  python3 patch_claude_context_2026_05_14_pm.py --apply     # write
"""
import sys
from pathlib import Path

SENTINEL = "<!-- [CLAUDE-CONTEXT-2026-05-14-PM] -->"
PATH = Path("tools/CLAUDE_CONTEXT.md")

APPEND_BLOCK = """

<!-- [CLAUDE-CONTEXT-2026-05-14-PM] -->
### Session 2026-05-14 PM+evening — Priority ranking, 8 marker fixes, Yanis V12, adaptive map dots

After the morning's clusters analysis (b24bc26), this session shipped
the third audit tool, applied concrete marker quality fixes from the
top of its rankings, upgraded the map to yanis V12, and added
zoom-adaptive sizing to the SVG map dots.

#### Part 1 — Composite priority ranking (commit 4dd0d75)

Built `tools/audit/audit_leak_priority_ranking.py` to cross-reference
the influence tree (BFS reachability) with the marker quality outliers,
and classify each LEAK cam into 4 quadrants:

- **HIGH_PRIORITY** (8 cams) — high influence + has outliers → fix urgent
- **HIGH_IMPACT**   (10 cams) — high influence + no outliers → protect
- **LOW_PRIORITY**  (10 cams) — low influence + has outliers → fix later
- **IGNORE**        (64 cams) — low everywhere → leave alone

Sectoral score design (3 independent dimensions, not weighted-aggregate):
direct contribution (gen1 LMs sourced), downstream reach (cams + LMs in
transitive closure), outlier risk (CASE A/B count + max severity).

Top of HIGH_PRIORITY list (sorted by direct contribution then severity):

```
   cam                                  gen1  g1L  dn  dL   cA  cAm   cB  cBm
   Gas Station (Lucia)                  23   19   22  186   1  18.9   1  25.5
   Diner (NE)                           10   10   22  186   3  30.0   1  19.0
   Diner (N)                             8    8   22  186   1  10.0   0   0.0
   Diner (E)                             7    7   22  186   3  33.2   1  98.1
   Gas Station (Jason)                   6    6   22  186   1  92.8   0   0.0
   Diner (S)                             5    5   22  186   1  39.1   0   0.0
   Car Wash                              5    4   22  186   2  21.6   0   0.0
   Hedge (B) (X)                         1    1   22  186   0   0.0   1  12.2
```

All 8 are in the Main cluster — they each share reach to 22 calibrated
cams and 186 LMs. Their outliers cascade further than other cams' would.

JSON written to `tools/generated/leak_priority_ranking.json`
(gitignored, regenerable).

#### Part 2 — Marker quality fix workflow (commits 80557ed, 993a0d4, 0f2304b, c5bc765)

Validated a complete workflow for fixing CASE A outliers:

1. Identify outlier in `audit_leak_marker_quality.py` output
2. Open the source cam(s) in the UI
3. Visually verify the marker is on the right physical object
4. Either:
   - **Snap marker(s) to current projection** if xyz is good
     (witness from another cam at low err confirms xyz)
   - **Retriangulate** if 2+ source markers visually agree on the same
     point but xyz has drifted
5. Re-run audit to confirm

Path bug fix on `tools/refine/retriangulate_landmark.py`:
`dirname×2` → `dirname×3` to match other refine/ scripts and make the
CLI runnable from repo root without PYTHONPATH workaround (commit 993a0d4).

##### Concrete fixes applied

**4937 E Hwy 98 (Gas Station) (SE)** (commit 80557ed):
- AIWE marker fine-tuned (sub-pixel refinement)
- Auto-retriangulate triggered
- xyz: `[-6330.736, 2764.765, 17.649]` → `[-6330.5658, 2764.9323, 17.6587]`
- error_m: 0.943 → 0.475 (halved)
- Gas Station (Jason) reproj err: ~37px → 18.5px (also halved)
- Top CASE A outlier 92.8' → 46.4'

**Art Deco Welcome Center (S)** (in 0f2304b):
- Both Welcome Center (E) and (W) markers snapped to projection
- WC (E): `(167, 149)` → `(169.2, 155.8)`, err 7.2px → 0.1px
- WC (W): `(1518, 72)` → `(1519.4, 67.0)`, err 5.4px → 0.2px
- xyz unchanged (error_m 0.069m already excellent)
- Witness Park at 0.4px confirmed xyz was correct — markers were
  the only thing needing adjustment
- Two CASE A outliers eliminated (18.2' and 13.4')

**White Pole** (in 0f2304b):
- Diner (NE) and Diner (E) markers snapped to projection
- **Removed Diner (SE) (A) marker** — was at 166.4' (worst CASE B
  outlier of the dataset); the cam was marking a different physical
  pole, name collision confirmed by retriangulation showing the 3 cams
  produce a 68.2' optimum vs 11.3' optimum without Diner (SE) (A)
- Retriangulated from 2 remaining cams
- xyz: `[-6092.565, 4474.75, 27.138]` → `[-6076.247, 4469.9728, 29.3709]`
  (17m movement — long-distance triangulation drift correction)
- Diner (NE) reproj: 30.0' → 11.3' (acceptable, 100m+ distance limit)
- Diner (E) reproj: 24.7' → 10.4' (slight regression but xyz is now
  geometrically consistent with markers)

**Domed Hills Sign (TW)** (in c5bc765):
- Diner (NE): `[1773.5, 250]` → `(1770.7, 243.2)`, err 7.4px → 0.1px
- Diner (E):  `[1256, 506]`   → `(1257.9, 509.6)`, err 6.8px → 2.7px
- Witness Diner (SE) (A) unchanged at 0.4px — confirms xyz is correct
- Same Welcome Center pattern: 2 outliers eliminated in one LM

**Mount Waffles (TW)** + bonus **Mount Waffles** (in c5bc765):
- 3 markers snapped to their projections across Diner (NE), Diner (N),
  Diner (NE) for the second LM
- Both LMs now have all markers <3px err
- LMs are distant (>1km for Mount Waffles raw) — error_m stays elevated
  but reprojection on cam markers is now good

##### Skipped (distance limit identified)

- **Easy Inn Sign** (Diner (S) → 39.1', 128m distance): both markers
  visually on the same panel, but retriangulate trade-off makes
  Easy Inn (3.5') worse without improving Diner (S) below ~30'
- **Oval Yellow Sign** (Gas Station Lucia → 18.9', 761m distance):
  marker visually correct, retriangulate movement only 0.6m, no
  improvement possible at this distance with manual marker precision

##### Apprentissages

- **Distance <100m**: snap to projection works, fixes drop err to <5px
- **Distance >100m**: manual marker precision is the limit; 5-15px
  residual is the realistic floor
- **Witness pattern**: when a non-source cam marks an LM at <1px, it
  validates the xyz independently from source cams. Useful diagnostic.
- **Name collisions** (one LM name used for 2+ physical objects across
  different cams): detected by retriangulate residual divergence; fix
  by removing the offending marker

#### Part 3 — Audit count and bundle adjust impact

After all 5 fixes:
- CASE A outliers (≥10'): **15 → 8** (cut in half)
- Bundle adjust RMS: **2.95 → 2.97** (no measurable change)

The RMS doesn't move because the solver compensates marker shifts by
adjusting cam params on the calibrated (non-LEAK) cams. Individual LM
audit improvements are real but local; **real RMS reduction requires
fixing multi-outlier LMs** where the same LM has wrong xyz seen from
multiple cams.

Top multi-outlier LMs identified for next session:
- **White Billboard (Hamlet)** — 6 Police Chase outliers (47.7' down
  to 17.7'). Top of bundle adjust outlier list. Fixing this single LM's
  xyz could drop the RMS measurably.
- **Container Crane (3)** — 2 outliers (Amphitheater, Motorboats (B))
- **Flamingo South Beach (SRSW)** — 2 outliers (Vice Beach A + B)
- **Radio Tower #1 (Port Gellhorn)** — 2 outliers (Chase A + B)

#### Part 4 — Yanis V12 map upgrade (commit 8f0be2c)

Yanis published map V12 on May 13 2026 (denser visual detail than V11).

Infrastructure setup needed (one-time, persistent):
- **Homebrew** installed at `/opt/homebrew/` via official script
- `.zprofile` updated with `eval "$(/opt/homebrew/bin/brew shellenv)"`
- **git-lfs 3.7.1** installed via `brew install git-lfs`
- `git lfs install` ran to register LFS smudge filter

LFS pull from rlx vendor (~1.5 GB):
- `vendor/gtamaplib/maps.zip`  : 144 MB (was 134 byte LFS pointer)
- `vendor/gtamaplib/frames.zip`: 1.2 GB (not needed yet, ~10k frames)
- `vendor/gtamaplib/fonts.zip` : 245 KB

Asset preparation pipeline:
1. Extract `maps/yanis,12.png` (61.8 MB, 20000×20000, RGBA) from
   `vendor/gtamaplib/maps.zip` to repo's `maps/`
2. Verify alpha channel is constant 255 → drop to RGB safely
3. Downscale 20000×20000 → 12000×12000 (matches yanis_v11 asset dims)
4. Convert to JPG quality 92, drop transparency → 13 MB
   (vs WebP 90 at 8.4 MB but too blurry per visual check,
    vs PNG keeping alpha at 37 MB)

Code changes via `patch_yanis_v12_jpg.py` (idempotent, archived):
- `gtamapdata/maps.json:45` — `maps/yanis,11.png` → `maps/yanis,12.png`
- `tools/server.py` — `/yanis.png` endpoint → `/yanis.jpg`,
  asset `yanis_v11.png` → `yanis_v12.jpg`,
  Content-Type `image/png` → `image/jpeg`
- `tools/calib.html` — 7 `/yanis.png` URL references → `/yanis.jpg`
- `.gitignore` — `vendor/` added (local LFS clone, not committed)

Small syntax bug in the generated patch (the Python literal
`elif path == '/yanis.jpg'  # [YANIS-V12]:` had the `:` *after* the
comment, making it invalid Python). Fixed via sed move-before-comment.

#### Part 5 — Adaptive map dots (commit pending at end of session)

The cam-markers and lm-dots are SVG circles inside `#map-overlay`,
which is wrapped in a div with `transform: scale()` applied for zoom.
When zooming in, the circles grow with the wrapper, hiding the map
beneath. Fixed via `updateDotSizes()` injected in `applyMapTx()`:

- Captures `mapBaselineScale` at `resetMapView()` (fit-to-screen scale)
- On every transform update, computes
  `factor = (baseline / mapTx.scale) ^ 0.5`
  (square root softens the inverse-scale to keep dots barely visible
   at extreme zoom rather than infinitesimal)
- Iterates all `.cam-marker circle` and `.lm-dot` and sets `r` to
  `baseR * factor` (and `stroke-width` for cam markers)
- Base values cached in `dataset.baseR` / `dataset.baseSw` on first
  pass, so we don't lose them after the first update
- Also reduced CSS `.cam-marker:hover circle{stroke-width:50}` to
  `stroke-width:20` (50 was the original; in SVG units, scales with
  zoom and produced a huge black halo when zoomed)
- Sentinel `[CAM-DOT-ADAPTIVE]`

Bonus follow-up: LMs observed by the currently-selected cam are
sized 1.6× their normal size, so they stand out on the cam's
frustum. Sentinel `[OBSERVED-LM-BIGGER]`. Uses the existing
`observedSet` already built in `renderLandmarksOnMap()`.

#### State at end of session

- Branch: `feature-svg-map`
- HEAD: 8f0be2c (yanis V12) + uncommitted adaptive dots changes
- 9 commits pushed today (b24bc26, 5f379bc, 7d38907, 4dd0d75, 80557ed,
  993a0d4, 0f2304b, c5bc765, 8f0be2c)
- 5 LM xyz fixes applied (4937 E Hwy 98, Welcome Center, White Pole,
  Domed Hills Sign TW, Mount Waffles TW + Mount Waffles)
- Removed 1 marker (White Pole on Diner (SE) (A) — name collision)
- Old asset `tools/assets/yanis_v11.png` (18 MB) kept on disk as rollback
- LFS files in `vendor/gtamaplib/` not tracked (gitignored)

#### Updated pending priorities

1. **Commit the adaptive-dots changes** (calib.html only)
2. **White Billboard (Hamlet)** xyz fix — affects 6 Police Chase
   outliers, most likely candidate to drop the RMS measurably
3. Continue HIGH_PRIORITY fixes (Diner cluster, Car Wash)
4. Decide what to do with the 8 remaining CASE A outliers (some are
   distance-limited and may have to stay)
5. **Refine adaptive-dots tuning** if needed (power, hover behavior,
   selected-cam LM bump)
6. JSON output for calibration_order.py (carried over)
7. Fix calibration_order's loss check (U-Turn (NE) false positive)
8. C — Verticals as solver constraints, take 2
9. D — Multi-step relaxation
10. Pylon (3) LM bug
11. Decide whether to merge `feature-gtamaplib-dependency` into
    feature-svg-map (still pending real-world test)
12. Cleanup `audit_leak_consistency.py` (obsolete hardcoded LEAK list)

"""


def main():
    apply = "--apply" in sys.argv

    if not PATH.exists():
        print(f"ERROR: {PATH} not found")
        sys.exit(1)

    text = PATH.read_text()

    if SENTINEL in text:
        print(f"Already patched ({SENTINEL} found). Nothing to do.")
        return

    if apply:
        backup = PATH.with_suffix(PATH.suffix + ".bak_pre_2026_05_14_pm")
        backup.write_text(text)
        PATH.write_text(text + APPEND_BLOCK)
        print(f"Appended session log to {PATH}")
        print(f"Backup: {backup}")
    else:
        print(f"DRY-RUN: would append {len(APPEND_BLOCK)} chars to {PATH}")
        print(f"  starts with: {APPEND_BLOCK[:80]!r}")
        print(f"  ends with:   {APPEND_BLOCK[-80:]!r}")
        print("Pass --apply to write.")


if __name__ == "__main__":
    main()
