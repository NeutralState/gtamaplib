#!/usr/bin/env python3
"""patch_ba_zpin_leakweight.py — Two fixes to tools/bundle_adjust_weighted.py.

P1 (z-pin): LMs with z_constraint {"type":"fixed"} get their z PINNED inside
the optimizer (get_lm_xyz overrides z). Before: BA optimized z freely, then
md.update_landmark snapped it at write time -> the optimized geometry was never
the written geometry (doctrine 2026-06-10). Now the optimizer converges on the
true constrained geometry; output JSON already carries the snapped z.

P2 (leak rays dominate): observations from HUD-locked cams (LOCKED_XYZ_CAMS)
get obs_w = anchor weight (15.0) instead of min(cam_w, lm_w). A leak pose is
ground truth; weighting its ray by the LM's tier let medium cams contest it
on shared LMs (root cause of the Pool 0'->416' massacre, 2026-06-10 doctrine).
Huber pass 2 still protects against a stale leak marking.

Idempotent (sentinel checks). Dry-run by default, --apply to write.
Backup: tools/bundle_adjust_weighted.py.bak_zpin_leakweight
"""
import os, shutil, sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(PROJ, "tools", "bundle_adjust_weighted.py")
APPLY = "--apply" in sys.argv

S1 = "LM_FIXED_Z"  # sentinel P1
S2 = "leak ray dominates"  # sentinel P2

H1_OLD = """def get_lm_xyz(p, name):
    if name in lm_idx:
        i = n_cam_params + lm_idx[name] * LM_PARAMS
        return p[i:i+3]
    return np.array(md.landmarks[name])"""

H1_NEW = """# LMs with a fixed z_constraint are pinned in the OPTIMIZER (not just at
# write time): md.update_landmark snaps z on write, so optimizing a free z
# means converging on geometry that will never reach the disk (2026-06-10).
LM_FIXED_Z = {
    n: float(m["z_constraint"]["value"])
    for n, m in md.landmarks_meta.items()
    if (m or {}).get("z_constraint") and m["z_constraint"].get("type") == "fixed"
}

def get_lm_xyz(p, name):
    if name in lm_idx:
        i = n_cam_params + lm_idx[name] * LM_PARAMS
        xyz = p[i:i+3]
        if name in LM_FIXED_Z:
            xyz = np.array([xyz[0], xyz[1], LM_FIXED_Z[name]])
        return xyz
    return np.array(md.landmarks[name])"""

H2_OLD = """        lm_t = lm_tier.get(lm_name, 'unknown')
        lm_w = TIER_WEIGHTS.get(lm_t, 1.0)
        obs_w = min(cam_w, lm_w)"""

H2_NEW = """        lm_t = lm_tier.get(lm_name, 'unknown')
        lm_w = TIER_WEIGHTS.get(lm_t, 1.0)
        if cam_xyz_is_locked:
            # leak ray dominates: HUD-locked pose is ground truth, so the obs
            # weight must not be capped by the LM's tier (min() let medium
            # cams contest leak rays on shared LMs -> Pool/Motel massacre).
            obs_w = TIER_WEIGHTS['anchor']
        else:
            obs_w = min(cam_w, lm_w)"""

src = open(TARGET).read()
n_todo = 0
for sent, old, new, label in ((S1, H1_OLD, H1_NEW, "P1 z-pin"),
                              (S2, H2_OLD, H2_NEW, "P2 leak weight")):
    if sent in src:
        print(f"SKIP {label}: already applied")
        continue
    if old not in src:
        sys.exit(f"ERROR {label}: hunk not found verbatim — target drifted, abort")
    src = src.replace(old, new, 1)
    n_todo += 1
    print(f"{'APPLY' if APPLY else 'WOULD APPLY'} {label}")

if n_todo and APPLY:
    shutil.copy(TARGET, TARGET + ".bak_zpin_leakweight")
    open(TARGET, "w").write(src)
    print(f"WRITTEN: {TARGET} (backup .bak_zpin_leakweight)")
elif n_todo:
    print("DRY-RUN: nothing written. Re-run with --apply.")
