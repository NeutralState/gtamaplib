#!/usr/bin/env python3
"""
Idempotent patch: append the 2026-05-12 session notes to CLAUDE_CONTEXT.md.

Surgical changes:
  - Updates the Quick state block (RMS, last session)
  - Inserts a new "### 2026-05-12" section BEFORE the existing
    "### 2026-05-10 (afternoon)" header in the Last session log
  - Leaves everything else untouched

Sentinel: <!-- ── SESSION-2026-05-12 ── -->
"""

import os
import shutil
import sys

REPO = os.path.expanduser('~/Downloads/gtamaplib-main')
CTX = os.path.join(REPO, 'tools', 'CLAUDE_CONTEXT.md')
SENTINEL = '<!-- ── SESSION-2026-05-12 ── -->'


# ── PATCH 1: Update Quick state
OLD_QUICK = '''- **Bundle adjust RMS** : 2.28' (clean state post Phase 10 + Ocean near Keys roll refinement)
- **Last session** : 2026-05-10 — Phase A (confidence tiers) + Phase B (intake_camera) + Phase 10 (roll end-to-end). Ocean near Keys (N) refined 2.21' → 1.64' as Phase 10 validation.'''

NEW_QUICK = '''- **Bundle adjust RMS** : 5.78' (171 cams; baseline pre-port was 2.28'; 23 rlx-ported unverified cams pollute. Marking via UI or batch_optimize will clean.)
- **171 cams** (148 base + 23 rlx ported), **680 landmarks**
- **Last session** : 2026-05-12 — Phase 11 verticals end-to-end (overlay UI toggle V), physical z bounds, tier-weighted optimize, batch_optimize.py. Discord mapper+ obtenu de martipk. Marti confirms "Four Seasons (BW) circular" — already-anchored LMs don't get re-triangulated.'''


# ── PATCH 2: Insert new session section
# We anchor on the header of the existing 2026-05-10 PM session.
ANCHOR = '### 2026-05-10 (afternoon) — Phase A + B + Phase 10: confidence tiering, intake gate, roll end-to-end'

NEW_SESSION = '''### 2026-05-12 — Phase 11 verticals + bounds + tier weights + batch_optimize  ''' + SENTINEL + '''

**13 commits today** (435e87d→c281ad1 spans 2 sessions, hashes for today's
commits: 5cd8765, b269dbf, 558b9c9, bbf3af7, 8b35f6c, a9aa09c, b93209d, c281ad1).

**Phase 11 verticals end-to-end**:
- Backend `/api/verticals?cam=NAME&xyz=...&ypr=...&hfov=...` — projects world-vertical
  lines (yaw-60° to yaw+60° step 0.5°, 20m tall at distance 10) through the cam,
  returns pixel pairs. Replicates rlx's `render_vertical_lines()` algo (gtamaplib L719).
- Frontend toggle button "⊕ verts" in calib.html, keyboard shortcut V. Yellow lines
  overlay the screenshot. Auto-updates when sliders move.
- **Visually validated** on Ocean near Keys (N): lines align perfectly with Seven Mile
  Bridge pillars. Calibration locked.
- Sentinels: `# ── VERTICALS-V1 ──`, `<!-- ── VERTICALS-FE-V1 ── -->`

**Phase 11.A — Physical z bounds**:
Server.py `optimize_camera()` had relative bounds (±50m on z from initial value).
This meant Yacht (2) with z=5 initial could solve to z=-45 (under sea level).
Fix: `lb[2] = max(xyz[2]-50, -5.0)` and `ub[2] = min(xyz[2]+50, 500.0)`.
Absolute floor at -5m prevents submarine solutions.

**Phase 11.B — Tier-weighted optimize**:
`optimize_camera()` was using binary weights (0.3 self-source, 1.0 indep). Now uses
tier weights: anchor=1.0, high=0.8, medium=0.4, low=0.1, unverified=0.0 (skipped),
multiplied by 0.3 if self-source (preserves anti-circular safeguard).
Loads `tools/generated/confidence_tiers.json` with graceful fallback.
Effect on bundle_adjust: 6.17' → 5.78' (~6% improvement, no regression).

**Phase 11.C — batch_optimize.py + safety**:
Calls server API per cam: Optimize → Save (optionally Update LMs if loss < threshold).
Supports `--tier`, `--cams`, `--apply`, `--update-lms`, `--save-threshold`,
`--regression-tolerance`, `--polish` (chains into bundle_adjust).
**Safety checks** added in same session: refuses save if loss_after > 10' (catastrophic)
or > loss_before * 1.05 (regression). First run revealed U-Turn (NE) at 866' loss
(garbage params) — correctly refused to persist.
Of 58 unverified cams: 9 successfully batch-optimized, 1 refused (U-Turn NE), 48
failed (<3 anchor+high obs each — these need manual marking in UI).

**rlx port v2 — done**:
- `port_rlx_inventory.py`: 24 cams unique-to-rlx with source, 27 unique LMs.
- `port_rlx_one_cam.py`: ports single cam with pixels (filters by our LMs).
  Pilot: Yacht (2) — 3 pixels, all to LMs we have. Optimized via UI with --refine-xyz
  initially gave z=-24m (sub-sea); Phase 11.A bound prevents this now.
- `port_rlx_batch.py`: ports the 23 sourced cams. Filters Minimap/Player/AIWE
  pixels (rlx skips these in his own solver — see gtamaplib L683, L1056). Result:
  9 portable with ≥3 usable pixels, 14 with 0 usable. Tier=anchor for most because
  source field matches LEAK pattern.
- **Cams ported are visualization-only**: most have few visible landmarks. They'll
  need manual marking via UI to be properly calibrated. RMS impact: 2.28' → 5.78'
  reflects this pollution.

**Four Seasons (BW) — circular dependency lesson**:
Originally triangulated from 1 cam (Handlebar SW), 8 cams mark the LM but only one
is source. Tried to re-triangulate from all 8 (best pair: Ocean near Keys N +
Rooftop Party, error 0.021m, xyz shifted ~17m). **rlx flagged this as circular**:
the 7 other cams' calibrations depend on Four Seasons (BW) being where it is, so
re-triangulating from them creates a feedback loop. Reverted via `git checkout`.
**Lesson**: anchor LMs stay anchored. Only retriangulate LMs that are genuinely
new or unanchored.

**Marti / Discord update**:
- Got **mapper+** from martipk (unilaterally — "haven't asked the others, inb4
  former staff", but "you definitely deserve it").
- Marti's note on Jason at Sea / Ocean near Keys (N) used as triangulation
  constraint: addressed by Phase 11 verticals (visual validation) + multi-cam
  triangulation already in `/api/update_landmarks` (with the source-cameras
  gate). Reply sent.
- rlx feedback on auto-triangulation: "too much work, the manual narration
  along the chain is more practical". Heeded. Don't try to fully automate the
  chain — narrate manually with tier system + verticals as guardrails.
- rlx confirms angular delta (arcmin) is the right metric — already what we
  use in `optimize_camera` and `bundle_adjust`.
- rlx's classification scheme (PLAYER / AIWE / MINIMAP / GIZMO / dir: prefix /
  high_precision overlay) is tribal knowledge, not stored in his code. Detectable
  via pixel markers ("Player", "AIWE", "Minimap (TL/N/BR)") but no urgent need
  to encode this until T3 arrives.

**Next session priorities** (updated 2026-05-12):
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
   bring RMS back down.

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
        print(f"ERROR: anchor not found: {ANCHOR!r}")
        sys.exit(1)

    new_src = src.replace(OLD_QUICK, NEW_QUICK, 1)
    new_src = new_src.replace(ANCHOR, NEW_SESSION + ANCHOR, 1)

    n_added = new_src.count('\n') - src.count('\n')
    print(f"Will add {n_added} lines to CLAUDE_CONTEXT.md")

    if not apply:
        print("(dry run — re-run with --apply)")
        return

    bak = CTX + '.bak_pre_session_20260512'
    shutil.copy(CTX, bak)
    print(f"✓ backup: {bak}")
    with open(CTX, 'w') as f:
        f.write(new_src)
    print(f"✓ patched")


if __name__ == '__main__':
    main()
