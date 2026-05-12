#!/usr/bin/env python3
"""
Idempotent patch: update CLAUDE_CONTEXT.md with late-afternoon work of 2026-05-12.

Adds to the existing 2026-05-12 session section:
  - data fixes (Motorboats A revert, White Billboard PC B+C pixels, BA min_obs)
  - calibrate_cam.py workflow narratif
  - Ocean near Keys (N) LEAK ground truth update
  - RMS recovery: 5.78' → 2.95'
  - C abandoned (verticals as solver constraints — tuning issue)
  - new commits c281ad1..d8296cb

Sentinel: <!-- ── SESSION-2026-05-12-PM ── -->
"""

import os
import shutil
import sys

REPO = os.path.expanduser('~/Downloads/gtamaplib-main')
CTX = os.path.join(REPO, 'tools', 'CLAUDE_CONTEXT.md')
SENTINEL = '<!-- ── SESSION-2026-05-12-PM ── -->'


# Update Quick state RMS
OLD_QUICK = '''- **Bundle adjust RMS** : 5.78' (171 cams; baseline pre-port was 2.28'; 23 rlx-ported unverified cams pollute. Marking via UI or batch_optimize will clean.)'''

NEW_QUICK = '''- **Bundle adjust RMS** : 2.95' (recovered from 5.78' via data fixes; baseline pre-port was 2.28')'''


# Insert new PM section after the existing 2026-05-12 section.
# Anchor on its last paragraph before the next session header.
ANCHOR = '''**Next session priorities** (updated 2026-05-12):
1. **Pylon (3) LM bug** — concrete, ~30-45 min. Find bad source pixels, fix or
   remove. Surfaced by intake_camera on Chase (2) (A). Affects all cams looking
   south toward Pylon.
2. **C — Verticals as solver constraints** — user marks 1-2 vertical lines on
   screenshot in UI, solver uses these + LM pixels to better constrain
   yaw/pitch/roll. Math + UI marking. ~2-3h. Phase 11 visual was the prereq.
3. **D — Multi-step relaxation** — solver progressively relaxes constraints
   (start with z fixed and fov fixed, then relax). ~1.5-2h. Helps when very few
   obs are marked.
4. **Update LMs in batch** — currently batch_optimize doesn't trigger Update LMs
   by default (safety). Could add a stricter threshold version with whitelist.
5. **Manual marking session** — go through the 48 unverified cams that don't have
   enough anchor+high obs, mark landmarks in UI. Tedious but the only way to
   bring RMS back down.'''

REPLACEMENT = '''**Next session priorities** (updated 2026-05-12 — superseded by PM section below):
1. ~~Pylon (3) LM bug~~ — deferred (Alex said "men fous pour now")
2. ~~C — Verticals as solver constraints~~ — **ATTEMPTED, abandoned** (see PM section)
3. D — Multi-step relaxation — still on deck for next session
4. Update LMs in batch with whitelist — still on deck
5. Manual marking session — still relevant for the 48 sous-contraintes

''' + SENTINEL + '''
### 2026-05-12 (PM) — Data fixes, narrative workflow, RMS recovery

**More commits today** (c281ad1..d8296cb): 8 additional commits in PM session.

**C — Verticals as solver constraints — ATTEMPTED AND ABANDONED**:
- Patched server.py to accept marked vertical lines in optimize_camera, with
  residuals comparing observed vs predicted pixel direction (angle in arcmin).
- Math validated: reproj test on Yacht (2) showed cam.get_pixel(cam.get_pixel_direction(p)*D + cam.xyz) == p exactly.
- BUT: weight tuning was wrong. On Yacht (2) (3 LM constraints) the vertical
  line dominated and shifted xyz Y by 9m. On Leonida Keys 01 (Airplane) (X) (12
  constraints, loss 2'), adding a single vertical line caused loss to BLOW UP
  to 16' (-694%). The vertical-line residual was at a different scale than the
  LM residuals.
- **Reverted** the patch. C is harder than it looks — needs experimental weight
  tuning and probably soft-cap on the residual. Deferred.

**Data fixes (RMS 5.78' → 2.95', recovered 95% of pollution from 23 rlx-ports)**:

1. **BA filter `min_obs >= 3`** (commit 3453507 also includes this) — `bundle_adjust.py`
   now excludes cams with fewer than 3 observations. 15 cams dropped (all
   unverified, 1-2 pixels). Modest RMS impact (5.78' → 5.72') because most
   were also under-constrained, not pulling.

2. **Removed bad pixels on Police Chase (B) and (C) for White Billboard (Hamlet)**.
   Both had loss > 100 arcmin (vs ~10' for siblings E-I). Investigation: 10 Police
   Chase LEAK cams march along a road (Y -3566→-3272, same yaw ~190°). The pixels
   on B and C pointed to a different building (mismatch). Removed via direct
   pixels.json edit. RMS 5.72' → 5.48'.

3. **Reverted Motorboats (A) drift** — biggest single win. batch_optimize.py
   had shifted xyz Y by 15m (1518 → 1503), which made the 8 LMs that Motorboats (A)
   was solo-source for (C TNE/TSE/BNE/BSE/TSW/BSW, Container Crane (3), CC (3)
   (BB2), all z=24-77m) outliers at 60-90 arcmin. Reverting to pre-port params
   brought RMS 5.48' → **2.95'**.

**Self-source divergence — lesson learned**:
   When a cam is solo-source for several LMs, batch_optimize can pull the cam
   away from those LMs by privileging the anchor+high LMs (with weight 1.0 / 0.8)
   over self-source LMs (×0.3 weight). Cam moves, self-source LMs stay put,
   residuals explode.

   **Defense**: after any batch_optimize, check max self-source error. If >10',
   either revert the cam or re-triangulate those LMs (if z-elevation compatible).
   This check is now built into `calibrate_cam.py`.

   Other batch-optimized cams checked clean (Convertible, Highway Peacock A/B,
   Jason Duval 05, Leonida Keys 05 Boats, Motorboats B, Raul Bautista 03,
   Yacht 2). Only Motorboats (A) had the bug.

**Ocean near Keys (N) — LEAK ground truth from game debug overlay**:
   Alex screenshot'd Ocean near Keys (N) in the leak debug overlay, exposing
   the **true** params: xyz=(-3442.897, -7191.001, 0.501), ypr=(358.539, -2.172,
   -1.245), fov=(81.924, 52.054). Our previously refined params were within
   0.1° of all angles. Updated cameras.json to match exact LEAK values.
   Slight RMS uptick (2.95→2.97) because LM positions are noisy, the math
   optimum != ground truth.
   **Implication**: LEAK cams should never be optimized. Their game-engine
   params are ground truth, our solver only adds noise.

**White Billboard (Hamlet) re-triangulation attempt — abandoned**:
   Tried to retriangulate from 7 rays (6 Police Chase LEAK + Leonida Keys 01).
   Convergence poor (max residual 40' after solve). Reason: Police Chase cams
   stretch 243-537m from the LM along a road with yaw varying ±14° — rays
   diverge too much. The LM is too far for these cams to converge sharply.
   Some pixels may also be on different billboards (visual inspection needed).
   Lesson: 6 LEAK cams marching down a road != 6 independent observation angles.

**calibrate_cam.py — workflow narratif livré** (commit d8296cb):
   For a given cam, prints:
   - State (tier, source, marked LMs broken down by tier with per-LM errors)
   - Trusted loss (RMS over anchor+high)
   - **Self-source divergence check** (alert if any > 10' — the Motorboats A bug)
   - Suggested action:
     * `>=3 anchor+high`: "Run `batch_optimize.py --cams 'NAME'`"
     * `<3 anchor+high but some marked`: "Mark more anchor+high in UI"
     * `0 marked`: "Fresh start, open in UI, mark these likely-visible"
   - Likely-visible LMs (projected in-frame, sorted by distance)
   - Post-action checklist (when to Update LMs, when to bundle_adjust)

   Tested on 4 cases (Vice Beach A, Yacht 2, Yacht 1, Leonida Keys 02 Sidewalk).
   All produced sensible narrative output. Use it as `python3 tools/calibrate_cam.py "CAM NAME"`.

**Next session priorities** (updated 2026-05-12 PM):
1. **Test calibrate_cam.py on real new cam intake** — when a new cam arrives
   (T3 or otherwise), run the script and see if its suggestions actually lead
   to good calibration. The workflow is now coded but unproven on a fresh case.
2. **D — Multi-step relaxation** — still on deck (~1.5-2h).
3. **Phase 12 — LEAK ground truth dump tool** — Alex can see exact LEAK cam
   params via the game's debug overlay. Could be huge if he can dump all 87
   LEAK cams' true params and we replace ours. Would establish a hard floor
   on RMS that no solver can improve. Need to find if dump is possible vs
   screenshot-only.
4. **C — Verticals as solver constraints**, take 2 — requires weight tuning,
   probably soft-cap on residual, OR a different math formulation (compare
   projected top position vs observed, not directions).

---

'''


def main():
    apply = '--apply' in sys.argv

    with open(CTX) as f:
        src = f.read()

    if SENTINEL in src:
        print(f"✓ Sentinel '{SENTINEL}' already present — nothing to do")
        return

    if OLD_QUICK not in src:
        print("ERROR: Quick state anchor not found")
        sys.exit(1)
    if ANCHOR not in src:
        print(f"ERROR: anchor not found (priorities block)")
        sys.exit(1)

    new_src = src.replace(OLD_QUICK, NEW_QUICK, 1)
    new_src = new_src.replace(ANCHOR, REPLACEMENT, 1)

    n_added = new_src.count('\n') - src.count('\n')
    print(f"Will add ~{n_added} lines to CLAUDE_CONTEXT.md")

    if not apply:
        print("(dry run — re-run with --apply)")
        return

    bak = CTX + '.bak_pre_session_pm'
    shutil.copy(CTX, bak)
    print(f"✓ backup: {bak}")
    with open(CTX, 'w') as f:
        f.write(new_src)
    print(f"✓ patched")


if __name__ == '__main__':
    main()
