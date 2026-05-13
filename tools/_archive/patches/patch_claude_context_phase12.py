#!/usr/bin/env python3
"""
Idempotent patch: append Phase 12 (workflow tools) to CLAUDE_CONTEXT.md.

Phase 12 adds:
  - calibrate_cam.py (workflow narratif per cam)
  - calibration_order.py (greedy ordering with virtual promotion + goldmine detect)
  - calibrate_session.py (interactive marking session loop)

Sentinel: <!-- ── PHASE-12-WORKFLOW ── -->
"""

import os
import shutil
import sys

REPO = os.path.expanduser('~/Downloads/gtamaplib-main')
CTX = os.path.join(REPO, 'tools', 'CLAUDE_CONTEXT.md')
SENTINEL = '<!-- ── PHASE-12-WORKFLOW ── -->'


OLD_QUICK = '''- **Bundle adjust RMS** : 2.95' (recovered from 5.78' via data fixes; baseline pre-port was 2.28')'''

NEW_QUICK = '''- **Bundle adjust RMS** : 2.95' (recovered from 5.78' via data fixes; baseline pre-port was 2.28')
- **Phase 12 workflow tools** : calibrate_cam.py + calibration_order.py + calibrate_session.py — the narrative method for new cam calibration'''


# Anchor on the PM session "Next session priorities" block to insert AFTER it
ANCHOR = '''**Next session priorities** (updated 2026-05-12 PM):
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
   projected top position vs observed, not directions).'''

REPLACEMENT = ANCHOR + '''

''' + SENTINEL + '''
### 2026-05-12 (late PM) — Phase 12: Workflow tools

**3 new tools livrés** for narrative calibration of new cams.

**`tools/calibrate_cam.py "CAM_NAME"`** — per-cam state + action assistant:
- Tier, source, marked LMs broken down by tier with per-LM error in arcmin
- Trusted loss (RMS over anchor+high)
- Self-source divergence check (alerts on >10' — the Motorboats A bug)
- Suggested action based on what's marked:
  * ≥3 anchor+high → "Run batch_optimize"
  * <3 anchor+high but some marked → "Mark more anchor+high in UI"
  * 0 marked → "Fresh start in UI"
- Likely-visible LMs (projected in-frame, sorted by distance)
- Limitation: projection-based suggestions assume current params are roughly
  correct. For very-off cams, suggestions won't match the actual frame.

**`tools/calibration_order.py --tier unverified`** — greedy calibration order:
- Algorithm: score each cam by # anchor+high marked, pick highest, "promote"
  its self-source LMs (assume they become anchor-quality post-calibration),
  re-score remaining cams, repeat.
- Flags:
  * ✓ AUTO-OPTIMIZE READY (if ≥3 anchor+high AND loss < 10')
  * ⚠ BROKEN (≥3 anchor+high but loss > 10' — case U-Turn NE)
  * ◐ NEEDS MORE marking
  * ⭐ GOLDMINE (≥20 LMs total but ≤2 anchor+high — high-value targets)
  * ○ FRESH START (0 marked)
- Reveals goldmines: cams like Keys (56 LMs), Motorboats (A) (49), Mount Kalaga
  National Park 02 (Helicopter) (X) (38) — lots of obs but no anchor link.
- Limitation: loss check uses only anchor+high (not all LMs), so a cam with
  loss=0 on its single anchor+high but 866' on a medium LM (U-Turn NE) still
  flags as ✓. Worth refining in future.

**`tools/calibrate_session.py --cams "A,B,C"`** — interactive session:
- For each cam in list, shows the calibrate_cam.py report + prompt
- Commands:
  * [Enter] re-check after marking in UI
  * o  → run batch_optimize
  * u  → call Update LMs API (with server-side safety)
  * s  → skip to next
  * b  → run bundle_adjust (global polish)
  * q  → quit
- Server must be running on http://localhost:8765
- Use `--from-order` to drive session from calibration_order output
- Use `--limit N` to cap the session length

**Lessons discovered while building these**:

1. **Self-source divergence is a real bug class**: Motorboats (A) batch-optimized
   ended up 15m off from its own 8 self-source LMs (z=24-77m containers).
   Reverted via git. calibrate_cam.py now has built-in detection (>10' on any
   self-source LM → warning). Defense against future batch_optimize misuse.

2. **Goldmine cams are common in ported data**: when rlx ports a cam from his
   triangulate.py runs, it brings ~50 LMs all sourced from that cam (e.g. Keys
   has 56 LMs all self-source). These don't have anchor validation but the LMs
   are internally consistent (sub-5' max error to the source cam). Promoting
   such LMs to "high" requires independent validation from another cam, which
   often doesn't exist in our system.

3. **Tools' projection-based suggestions need anchor coverage**: when calibrate_cam.py
   tries to find "likely visible" anchors, it projects all anchor LMs and filters
   to in-frame. For cams with rough params (Leonida Keys 02 Sidewalk: 0 marked),
   nothing projects in-frame so the tool can't help. Reality requires user to
   visually identify what's in the scene first.

4. **calibrate_session.py's "from-order" mode** parses the output of
   calibration_order.py — a fragile coupling. If the latter's output format
   changes, parser breaks. Should refactor to JSON output mode for both later.

**The full narrative workflow now**:
```
# 1. See the optimal order to attack a batch of cams
python3 tools/calibration_order.py --tier unverified --limit 20

# 2. Open interactive session on those cams
python3 tools/calibrate_session.py --from-order --limit 20

# 3. For each cam, the session shows state + waits for user to mark in UI,
#    then offers Optimize / Update LMs / next / bundle_adjust / quit
```

This is the **method** for T3 intake. Replaces ad-hoc UI work with a guided
loop. Not yet stress-tested on a real fresh batch (T3 hasn't arrived) but
the pieces are in place.

**Next session priorities** (updated 2026-05-12 late PM):
1. **Run on real cams** — when T3 arrives or to attack one of the 3 goldmines
   (Keys / Motorboats A / Mount Kalaga 02), use the session tool. See what
   breaks in practice.
2. **JSON mode for the workflow tools** — refactor calibration_order to emit
   JSON so calibrate_session doesn't have to parse text.
3. **Address the projection limitation** — for cams with rough params, the
   "likely visible" suggestions don't match reality. Could add a tolerance
   mode (search wider than frame) or reverse-lookup (user types what they see).
4. **C — Verticals as solver constraints**, take 2 — still on deck if needed.
5. **D — Multi-step relaxation** — still on deck.

---

'''


def main():
    apply = '--apply' in sys.argv

    with open(CTX) as f:
        src = f.read()

    if SENTINEL in src:
        print(f"✓ Already patched")
        return

    if OLD_QUICK not in src:
        print("ERROR: Quick state anchor not found")
        sys.exit(1)
    if ANCHOR not in src:
        print(f"ERROR: anchor not found (PM priorities block)")
        sys.exit(1)

    new_src = src.replace(OLD_QUICK, NEW_QUICK, 1)
    new_src = new_src.replace(ANCHOR, REPLACEMENT, 1)

    n_added = new_src.count('\n') - src.count('\n')
    print(f"Will add ~{n_added} lines to CLAUDE_CONTEXT.md")

    if not apply:
        print("(dry run — re-run with --apply)")
        return

    bak = CTX + '.bak_pre_phase12'
    shutil.copy(CTX, bak)
    print(f"✓ backup: {bak}")
    with open(CTX, 'w') as f:
        f.write(new_src)
    print(f"✓ patched")


if __name__ == '__main__':
    main()
