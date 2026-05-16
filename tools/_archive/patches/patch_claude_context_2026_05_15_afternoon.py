#!/usr/bin/env python3
"""
patch_claude_context_2026_05_15_afternoon.py

Append the 2026-05-15 afternoon session log to tools/CLAUDE_CONTEXT.md.
Idempotent via sentinel.
"""
import sys
from pathlib import Path

SENTINEL_TAG = "CLAUDE-CONTEXT-2026-05-15-PM"
SENTINEL = f"<!-- [{SENTINEL_TAG}] -->"
PATH = Path("tools/CLAUDE_CONTEXT.md")

APPEND_BLOCK = """

""" + SENTINEL + """
### Session 2026-05-15 afternoon — Niveau 2 rigid-body experiment + Watson Bay diagnosis

Pushed Niveau 1 in the morning (-35% RMS via Four Seasons rigid model
xyz overrides). This afternoon: attempted Niveau 2 (rigid body as solver
variable) and uncovered several structural insights about the dataset.

#### Part 1 — Niveau 2 implementation

Goal: instead of optimizing each Four Seasons LM xyz independently
(3 DOF each), treat the entire building as 6 DOFs (3 translation +
3 rotation around centroid). Reduces variables, enforces geometric
coherence.

Design doc: tools/RIGID_BODY_DESIGN.md (6 decisions, see file).

Implementation in 2 patch scripts (archived in
tools/_archive/patches/):
- patch_rigid_v2_edit1.py: inject rigid body setup after lm_idx
- patch_rigid_v2_edit2.py: inject helpers, modify x0, pixel_residuals,
  Jacobian sparsity (7 sub-patches A-G)

Multiple bugs encountered during integration:
1. REPO_DIR undefined (actual: GTAMAP_DIR)
2. Namespace collision: `import gtamaplib as ml` at line 34 binds the
   root namespace; `from gtamaplib.gtamaplib import FourSeasons`
   then fails
3. importlib relative import error in vendor module
4. Final fix: hardcode the 18 LM xyz directly in bundle_adjust.py via
   _FS_LM_MAP dict

#### Part 2 — Niveau 2 first run

Variables: 1789 -> 1774 (-7 LMs × 3 DOFs + 6 rigid DOFs = -21+6 = -15)

Result: RMS = 2.27 arcmin (vs 1.94 baseline). WORSE.

Top outlier: Grassrivers 02 (Watson Bay) -> Four Seasons (W) at 53.2'

#### Part 3 — Root cause discovery: bug in rlx's _landmarks() method

The rlx FourSeasons class defines a method _landmarks() that returns
"Four Seasons Hotel Miami (W)" -> self.fs57e (East penthouse, ~258m
altitude).

But our marker for that LM on Watson Bay at pixel (945.5, 497) was
pointing at the 40th floor West corner (fs40w, ~189m altitude). Tested
5 candidates for the marker:
- fs57e (Penthouse E, the rlx value): projects 70.3px from marker
- fs56sw (corner SW): 56.3px
- fs57nw: 62.8px
- fs57w computed: 60.5px
- **fs40w: 5.7px** ← match!

The bug: rlx's _landmarks() maps "W" to fs57e which is the East
penthouse, contradicting the W label. Our marker correctly identified
the 40th floor West corner as the visual feature.

Fix (commit 39ae6d3): rename the Watson Bay marker from
'Four Seasons Hotel Miami (W)' to 'Four Seasons Hotel Miami (40W)'.
Remove FS(W) entry from landmarks.json (no marker references it now).

Bundle adjust impact: the 53.2' outlier disappears. RMS at 1.9355
(no change vs Niveau 1 baseline 1.9357).

#### Part 4 — Niveau 2 second run, with FS(W) renamed

Re-ran Niveau 2 with the rename fix. RMS = 1.9477 (slightly worse than
1.9355 Niveau 1 baseline).

Conclusion: Niveau 2 works technically (solver converges, rigid body
operates correctly), but yields NO measurable gain on this dataset
because Niveau 1 already captured the geometric coherence via xyz
override. The remaining free LMs absorbed any small drift naturally.

Reverted bundle_adjust.py to Niveau 1 state (no rigid body in solver).

#### Part 5 — Watson Bay structural problem

Investigated why Watson Bay still has top outliers:
- Portofino Tower (S): 16.7px
- Nine at Mary Brickell Village (E): 15.1px
- Red Billboard (Hamlet): 12.7px

These are exactly the LMs rlx flagged in his Discord monologue (Watson
Bay self-source divergence on Portofino (S) 12.3', Nine Brickell (E)
11.1').

Tested:
1. Camera position grid search: current xyz is locally optimal
   (rmse 6.19px, no nearby point is better)
2. hfov sweep: 47° is optimal (47.0 -> avg 4.6px; 48 -> 25px; 46 -> 26px)
3. pitch/yaw sweep: -5.5° pitch, current yaw are both optimal

So Watson Bay cam params ARE optimal for the markers we have.

#### Part 6 — Comparison with rlx's Watson Bay

Found in vendor/gtamaplib/gtamapdata.py line 261:
- rlx xyz: (-5218.000, -3355.000, 27.233)
- our xyz: (-5472.6401, -3427.1089, 21.2183)
- Delta: +254m X, +72m Y, +6m Z, hfov 49.6 vs 47.0

Tried importing rlx's Watson Bay cam params: avg error went from 4.6px
to 10.0px on our markers. Reason: rlx's Turkey Point LMs are at
different xyz (drift 7-21m from ours). His cam Watson Bay is
self-coherent with HIS LM xyz, not with ours.

This means: pieces of rlx's calibration cannot be imported individually
without breaking coherence. Either we import the whole system (cam +
all dependent LMs), or we re-calibrate our system from scratch.

Decided NOT to import rlx's Watson Bay this session.

#### Part 7 — Strategic implications

Several insights:

1. **Niveau 2 produces no measurable gain when Niveau 1 already
   normalized the LM xyz**. Rigid body solver integration is an
   architectural improvement (LMs cannot drift apart geometrically)
   but does not unlock new accuracy on data that's already coherent.

2. **rlx's _landmarks() method has a labeling bug**: "W" -> fs57e.
   This is a small finding but useful to mention to rlx, and useful
   for any tool that depends on this method.

3. **Watson Bay's outliers are NOT cam param errors**. They're either:
   - Marker placement imprecision on distant features (~15px at 6km
     distance is near the limit of human marking accuracy on small
     visual features)
   - LM xyz triangulation errors compounding with Watson Bay's view
     angle
   - Our entire local coordinate system having a small offset from
     rlx's reference

4. **Cam param transplant across datasets does not work** without also
   transplanting all the dependent LM xyz. Datasets are self-coherent
   webs.

#### State at end of session

- Branch: feature-svg-map
- HEAD: 39ae6d3 (FS(W) rename) — pushed
- New commits this session:
  - c595fd2 fix: Sunshine Skyway Bridge (N) + (S) from rlx rigid model
  - 39ae6d3 fix: Watson Bay marker semantic bug FS(W) -> FS(40W)
- Working tree: clean
- RMS: 1.9355 (negligibly improved from 1.9357 morning)
- bundle_adjust.py: REVERTED to Niveau 1 state (no rigid body)
- Niveau 2 patches archived in tools/_archive/patches/
- Design doc tools/RIGID_BODY_DESIGN.md added

#### Updated pending priorities (revised)

1. **Communicate to rlx on Discord**:
   - The Niveau 1 -35% RMS win using his FourSeasons model
   - The bug in his _landmarks() method ('W' -> fs57e)
   - Ask if he has rigid models for Portofino, Icon, Nine at Mary
     Brickell, etc.

2. **Mark the 9 new Four Seasons LMs on downstream cams** (still
   pending from morning): Vice Beach A+B, Prison, etc. could
   amplify Niveau 1 win.

3. **Watson Bay re-calibration is hard**:
   - Either accept ~15px residual error on distant LMs as structural
     limit
   - Or do a holistic re-import from rlx (cam + dependent LM xyz)
   - Or do a marker re-placement session in the UI on Watson Bay
     specifically for Portofino (S), Nine Brickell (E), Red Billboard

4. **White Billboard (Hamlet)** — still top outlier cluster (Police
   Chase × 6). Different from Watson Bay; needs its own investigation.

5. **Niveau 3** still on table — finding more rigid models in vendor
   (we checked: only FourSeasons, HanksWaffles, SunshineSkywayBridge
   exist as classes). HanksWaffles already aligned (no gain), Skyway
   done. So Niveau 3 needs new rigid models we'd build ourselves,
   or wait for rlx to publish more.

6. **Niveau 2 architecture preserved** in archived patch scripts and
   design doc. Can be revived later if we find a building (or system)
   where rigid body solver integration would unlock gain that pure
   xyz override doesn't capture.

7. Carry-overs (unchanged from morning):
   - JSON output for calibration_order.py
   - Fix calibration_order's loss check (U-Turn (NE) false positive)
   - C — Verticals as solver constraints, take 2
   - D — Multi-step relaxation
   - Pylon (3) LM bug
   - Decide whether to merge feature-gtamaplib-dependency into
     feature-svg-map
   - Cleanup audit_leak_consistency.py (obsolete hardcoded LEAK list)
"""


def main():
    apply = "--apply" in sys.argv

    if not PATH.exists():
        print(f"ERROR: {PATH} not found")
        sys.exit(1)

    text = PATH.read_text()
    if SENTINEL in text:
        print(f"Already patched ({SENTINEL_TAG}). Nothing to do.")
        return

    if apply:
        backup = PATH.with_suffix(PATH.suffix + ".bak_pre_2026_05_15_pm")
        backup.write_text(text)
        PATH.write_text(text + APPEND_BLOCK)
        print(f"Appended afternoon session log to {PATH}")
    else:
        print(f"DRY-RUN: would append {len(APPEND_BLOCK)} chars.")
        print("Pass --apply to write.")


if __name__ == "__main__":
    main()
