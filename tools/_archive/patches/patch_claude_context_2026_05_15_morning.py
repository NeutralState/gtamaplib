#!/usr/bin/env python3
"""
patch_claude_context_2026_05_15_morning.py

Append the 2026-05-15 morning session log to tools/CLAUDE_CONTEXT.md.
Idempotent via sentinel.

Run from gtamaplib-main/:
  python3 patch_claude_context_2026_05_15_morning.py             # dry-run
  python3 patch_claude_context_2026_05_15_morning.py --apply
"""
import sys
from pathlib import Path

SENTINEL_TAG = "CLAUDE-CONTEXT-2026-05-15-AM"
SENTINEL = f"<!-- [{SENTINEL_TAG}] -->"
PATH = Path("tools/CLAUDE_CONTEXT.md")

APPEND_BLOCK = """

""" + SENTINEL + """
### Session 2026-05-15 morning — Four Seasons rigid-body model discovery (-35% RMS)

Started the day pivoting from yesterday's marker work toward exploring
rlx's chain-based calibration philosophy (from his Discord monologue).
Discovered that rlx has built a 3D rigid-body model for Four Seasons
Hotel Miami in his upstream code, applied it to landmarks.json, and
the bundle adjust RMS dropped from 2.97 to 1.94 arcmin (-35%).

This is the largest single-commit RMS improvement in the project's
history so far.

#### Part 1 — Exploring rlx's chain methodology

rlx published a long monologue on Discord describing his step-by-step
calibration optimizer (codex-written). Key insights:

1. Adding a single ray can change everything — adding reworld to
   Keys Airplane shifts Leonida Keys 01 by 0.874m, Postcard by 0.670m.
2. Parallel rays = problem. Turkey Point via Keys Airplane + Postcard
   has nearly-parallel rays, producing degenerate triangulation.
   Heuristic: skip ray pairs with <15deg angle.
3. Architecture proposal: ordered list of cameras (a chain), with
   global re-optimization after each step instead of one big global opt.
4. "Roll is an error sponge" — don't optimize roll on cams initialized
   with zero roll.
5. Per-cam loss can increase even when global loss decreases.

#### Part 2 — Testing rlx's chain on our tooling

Tried to replicate his chain (Keys Airplane -> Vice Beach B -> Watson
Bay -> Prison -> Ambrosia 02) using tools/calibrate_session.py.
The tool exists and works (already wired up via calibration_order.py
and batch_optimize.py). However:

- Our auto-optimize guardrail requires >=3 anchor+high LMs per cam
- All 5 cams in rlx's chain have 0-2 anchor+high (not enough)
- rlx's optimizer is more permissive (forces optimization)

Comparison of patterns regardless:
- Watson Bay self-source divergence: 12.3' on Portofino Tower (S) and
  11.1' on Nine at Mary Brickell Village (E) — matches the bundle
  adjust top outliers
- Our losses on Keys Airplane, Prison, Vice Beach B are better than
  rlx's test starting point (probably because our dataset is more
  raffined after yesterday's fixes)

Conclusion: can't run chain mechanically, but the *patterns* converge —
Watson Bay is a shared problem.

#### Part 3 — Discovering the structural weakness

Investigated which LMs are critical anchors for the south of Vice City.
Found that:

- Four Seasons Hotel Miami (BW) has 8 cams downstream but only 1 source
  (Handlebar (SW))
- Four Seasons (BE), (SE), (NW), (BW) all sourced by a single cam each
- Four Seasons (W) has corrupted xyz: (-2.5e14, 1.3e14, -1.1e14) —
  3e14 meters from origin
- Single-source LMs propagate noise to all downstream cams

Even worse, our triangulated xyz on these LMs don't form a coherent
building geometry — (BW) and (BE) are 44m apart per their xyz, but the
real Four Seasons is 30m wide. So 14m of internal incoherence in our
data, invisible to the solver.

#### Part 4 — Discovery: rlx has a rigid-body model

User insight: "je te garantie qu'il a un modele 3d". Searched vendor
upstream and found `class FourSeasons(Landmark)` in vendor/gtamaplib/
gtamaplib.py:1317.

It's a full parametric rigid-body model:
- 13 anchor points as __init__ parameters (corners at floors 40, 56,
  57 + handlebar features at floors 8, 28, 58)
- All other corners derived geometrically via `_construct()`:
  - intersect_ray_and_plane for 56th floor side corners
  - Horizontal extrapolation for 57th floor (penthouse)
  - get_point + dir_w for handlebar opposite corners
- floor_height = 4.029m, penthouse_height = 4.698m
- Total building dimensions: 48.7m east-west, 45.3m north-south,
  263.6m tall
- Orientation 339.5 deg

The `_landmarks()` method returns a dict of named LM corners
(BE, BW, E, NE, NW, SE, SW, W) with derived xyz. Other corners
(40NE, 40NW, 40E, 40W, 32NE, 56NE, HB28SE, HB8SE, HB58SE, HB58NE)
accessible directly as attributes.

#### Part 5 — Applying the model (commit e89e3e4)

Built `patch_four_seasons_rigid_model.py` to:

A. **Fix corrupted W**: override xyz (was 3e14m garbage) with model
   value (-818.00, -1316.42, 258.31).

B. **Override 4 drifted LMs** to model values:
   - BE: drift 4.79m -> rigid model
   - BW: drift 2.02m -> rigid model
   - NW: drift 2.95m -> rigid model
   - SE: drift 1.37m -> rigid model
   (E, NE, SW were already <0.5m drift, left alone)

C. **Add 9 missing LMs** that are already marked on Tennis Stadium (4K)
   and Metro (SE) (A) (4K) but absent from landmarks.json:
   40NW, 40W, 40E, 32NE, 56NE, HB28SE, HB8SE, HB58SE, HB58NE.
   Each assigned model xyz with the LEAK cam as source.

Sentinel [FOUR-SEASONS-RIGID-V1] in `notes` field; idempotent.

#### Part 6 — Bundle adjust impact

| Metric | Before | After | Delta |
|---|---|---|---|
| RMS | 2.97' | **1.94'** | -35% |
| Improvement | 8.8% | **44.1%** | |
| p50 | 1.24' | **0.52'** | -58% |
| p90 | 5.06' | **2.82'** | -44% |
| p99 | 12.22' | **9.19'** | -25% |
| obs >20' | 7 | **4** | |
| obs >10' | 18 | **10** | |
| obs <5' | 927/1037 | **1005/1037** | 97% now <5' |

White Billboard (Hamlet) on Police Chase still tops the outlier list
but with reduced magnitudes (47.7' -> 38.3' max). The rigid Four Seasons
acts as a strong anchor, the solver redresses the whole south coast
around it.

#### Part 7 — Strategic implications

The 3 levels of rigid-body integration:

**Level 1 (DONE)** — Override xyz from the rigid model.
- Cost: 30 min
- Impact: -35% RMS
- Mechanism: solver sees coherent geometry, redresses cams

**Level 2 (FUTURE)** — Rigid body as solver variable.
- Cost: 4-8h
- Mechanism: instead of optimizing 13 individual LM xyz (39 DOF), the
  solver optimizes the building's pose (6 DOF: translation + rotation)
  with the internal geometry locked. Far fewer DOFs, much more
  constrained.
- Requires: refactoring bundle_adjust to recognize "rigid group" LMs,
  parameterizing rotation (quaternion or axis-angle), Jacobian updates.
- Expected impact: further RMS drop, more confidence in poses.

**Level 3 (FUTURE)** — More rigid bodies.
- Cost: ongoing — model each major skyline building
- Candidates: Portofino Tower, Icon at South Beach, Bank of America
  Tower, Continuum on South Beach, Wells Fargo, Asia Brickell Key,
  Nine at Mary Brickell Village. Check if rlx already has models for any.
- Mechanism: same as Four Seasons, propagate rigidity across the south.

#### State at end of session

- Branch: `feature-svg-map`
- HEAD: e89e3e4
- Working tree: clean
- RMS: 1.94' (down from 2.97' yesterday and last week)
- Pattern proven: rigid-body anchors massively constrain the solver

#### Updated pending priorities

1. **Communicate the result to rlx** (Discord) — he'll be interested
   that his Four Seasons model produced -35% RMS on our dataset.
   Ask if he has models for other buildings (Portofino, Icon, etc.).

2. **Mark the 9 new Four Seasons LMs on downstream cams**: they're
   added to landmarks.json but only sourced by their LEAK cam. If we
   mark them on Vice Beach A+B, Prison, etc., the multi-anchor effect
   strengthens further. Could drop RMS more.

3. **White Billboard (Hamlet)** — still the top outlier cluster
   (6 Police Chase outliers). Investigate why all 6 cams agree this
   LM is misplaced. Probably the LM xyz needs fixing, or there's a
   name collision.

4. **Niveau 2 (rigid body as solver variable)** — major refactor
   of bundle_adjust. Worth investigating after we've exhausted the
   easy wins (Level 1 on more buildings).

5. **Niveau 3 (more buildings)** — check if rlx has Portofino, Icon,
   etc. models in vendor.

6. Carry-overs:
   - JSON output for calibration_order.py
   - Fix calibration_order's loss check (U-Turn (NE) false positive)
   - C — Verticals as solver constraints, take 2
   - D — Multi-step relaxation
   - Pylon (3) LM bug
   - Decide whether to merge `feature-gtamaplib-dependency` into
     feature-svg-map
   - Cleanup `audit_leak_consistency.py` (obsolete hardcoded LEAK list)

"""


def main():
    apply = "--apply" in sys.argv

    if not PATH.exists():
        print(f"ERROR: {PATH} not found")
        sys.exit(1)

    text = PATH.read_text()

    if SENTINEL in text:
        print(f"Already patched ({SENTINEL_TAG} found). Nothing to do.")
        return

    if apply:
        backup = PATH.with_suffix(PATH.suffix + ".bak_pre_2026_05_15_morning")
        backup.write_text(text)
        PATH.write_text(text + APPEND_BLOCK)
        print(f"Appended session log to {PATH}")
        print(f"Backup: {backup}")
    else:
        print(f"DRY-RUN: would append {len(APPEND_BLOCK)} chars to {PATH}")
        print(f"  sentinel: {SENTINEL_TAG}")
        print(f"  starts: {APPEND_BLOCK[:100]!r}")
        print(f"  ends:   {APPEND_BLOCK[-100:]!r}")
        print("Pass --apply to write.")


if __name__ == "__main__":
    main()
