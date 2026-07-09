#!/usr/bin/env python3
"""
compute_confidence_tiers.py — Classify every cam and landmark into a confidence tier.

Reads:
  gtamapdata/cameras.json
  gtamapdata/landmarks.json
  gtamapdata/pixels.json

Writes:
  tools/generated/confidence_tiers.json

The output is the truth source for the rest of the T3 intake pipeline (Phase B
intake gate, Phase C weighted bundle adjust, etc). Re-run after every batch
onboarding via bundle_adjust_apply.py — see Phase E (state hygiene) for the
automation hook.

# ── TIERS-PATCH-V2-RELAXED ──
# ── TIERS-PATCH-V3-SEMANTICS ──
CAMERA TIERS (v3 — semantic cleanup):
  anchor      LEAK cams (source matches YYYY-MM-DD). Ground truth, locked.
  high        Median residual ≤ 3' AND ≥ 5 obs against anchor+high LMs
              (or fallback) median ≤ 2' AND ≥ 15 medium-or-better obs
              with ≥ 2 anchor+high obs as sanity floor
  medium      ≥ 2 anchor+high obs with median ≤ 6' max ≤ 30',
              or ≥ 8 medium-or-better obs with median ≤ 4' max ≤ 20'
  low         v3: median residual > 10' over any ≥3 valid obs (bad residuals
              regardless of LM coverage), OR fails medium criteria above
  unverified  v3: <2 valid residuals, OR insufficient LM coverage to evaluate

LANDMARK TIERS (v3 — single-source split from low):
  anchor      All source_cameras are LEAK. Includes single-LEAK-source.
  high        ≥ 2 LEAK source cameras, OR
              ≥ 3 sources of which ≥ 1 is LEAK, OR
              ≥ 3 non-LEAK sources with median observation residual ≤ 3'
  medium      ≥ 2 sources, median residual ≤ 5'.
  low         v3: median residual > 8' OR max > 25' (actually problematic).
              No longer demotes for "1 source only" — that's now unverified.
  unverified  v3: 1 non-LEAK source only (cannot cross-validate yet),
              OR has xyz but no source_cameras (defensive).

The v3 split lets downstream tools (Phase B intake, weighted bundle adjust)
distinguish "actively suspect" (low) from "not yet validated" (unverified).
Both excluded as references at intake, but the reason matters for triage.

Run from gtamaplib-main/:
    python3 tools/compute_confidence_tiers.py
    python3 tools/compute_confidence_tiers.py --verbose      # per-cam summary
    python3 tools/compute_confidence_tiers.py --explain CAM  # why a cam got its tier
"""

import argparse
import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)

import gtamaplib as ml
import gtamapdata as md

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated')
OUT_PATH = os.path.join(OUT_DIR, 'confidence_tiers.json')


# ── Constraint-class API ───────────────────────────────────────────────────
#
# V2: All cam classification flows through the leak_cam_audit helper module.
# The audit defines per-cam DOF locking; the helper transparently handles
# the legacy date-pattern fallback for cams without explicit audit entries.
#
# Functions used here:
#   - is_anchor(name): cam has all DOF locked (class A or _legacy_date).
#       Used to short-circuit residual computation for anchor cams.
#   - is_triangulation_trusted(name): cam's xyz is locked (A/B/C/Cm/_legacy).
#       Used to flag LMs whose triangulating rays are HUD ground-truth.
#
# Tools that fall back to a date-pattern check inside this module are
# considered V1 legacy and should be migrated to the helper API.

from leak_cam_audit import (
    is_anchor,
    is_triangulation_trusted,
    legacy_cam_names,
)

# Warn about cams that fell through the audit but match the date pattern.
# They are treated like class A_full_hud (fully locked) by the helper, but
# should be added to leak_cam_audit.json for explicit classification.
_legacy_cams = legacy_cam_names(md.cameras)
if _legacy_cams:
    print(f"WARNING: {len(_legacy_cams)} cam(s) with date-source but no audit "
          f"entry — treated as fully-locked legacy:")
    for _n in _legacy_cams:
        print(f"  - {_n}")
    print(f"  (Add explicit constraint_class via leak_cam_audit.json for these.)")


def is_trailer(cam_name):
    s = md.cameras.get(cam_name, {}).get('source', '')
    return s.startswith('Trailer')


# ── Per-observation residual computation ────────────────────────────────────

def compute_residual_arcmin(cam_name, lm_name):
    """Returns arcmin pixel error for this cam/lm pair, or None on failure."""
    try:
        cam = ml.get_camera(cam_name)
        lm_xyz = md.landmarks.get(lm_name)
        if lm_xyz is None:
            return None
        pixel = md.pixels[cam_name][lm_name]
        proj = cam.get_pixel(lm_xyz)
        if proj is None:
            return None
        dx = (proj[0] - pixel[0]) * cam.hfov / cam.w * 60
        dy = (proj[1] - pixel[1]) * cam.vfov / cam.h * 60
        return math.sqrt(dx * dx + dy * dy)
    except Exception:
        return None


def all_residuals_for_cam(cam_name):
    """List of (lm_name, residual_arcmin) for every valid pixel observation."""
    out = []
    for lm_name in md.pixels.get(cam_name, {}):
        r = compute_residual_arcmin(cam_name, lm_name)
        if r is not None:
            out.append((lm_name, r))
    return out


def all_residuals_for_landmark(lm_name):
    """List of (cam_name, residual_arcmin) for every cam observing this lm."""
    out = []
    for cam_name, pxs in md.pixels.items():
        if lm_name in pxs:
            r = compute_residual_arcmin(cam_name, lm_name)
            if r is not None:
                out.append((cam_name, r))
    return out


# ── Tiering logic ───────────────────────────────────────────────────────────

def classify_landmarks(cam_tier_fn):
    """
    First-pass landmark classification. cam_tier_fn(cam_name) returns a tier
    string for that cam. We use it to reason about source camera quality.

    Returns dict: lm_name -> {tier, n_sources, n_leak_sources, median_res, max_res, reason}
    """
    out = {}
    for lm_name, xyz in md.landmarks.items():
        meta = md.landmarks_meta.get(lm_name, {})
        sources = meta.get('source_cameras', [])
        z_const = meta.get('z_constraint')

        # No xyz = no triangulation yet; not in bundle pool
        if xyz is None:
            out[lm_name] = {
                'tier': 'unverified',
                'n_sources': 0,
                'n_leak_sources': 0,
                'median_res': None,
                'max_res': None,
                'reason': 'no xyz (untriangulated)',
            }
            continue

        n_sources = len(sources)
        # V2: count sources whose xyz is HUD-locked (= can anchor triangulation).
        # Classes A/B/C/Cm and legacy-date cams qualify; D and ordinary cams do not.
        n_locked = sum(1 for c in sources if is_triangulation_trusted(c, cameras=md.cameras))

        # Compute residuals for this landmark across all observers
        residuals = [r for _, r in all_residuals_for_landmark(lm_name)]
        median_res = statistics.median(residuals) if residuals else None
        max_res = max(residuals) if residuals else None

        # Classify (v2 criteria — "LEAK" is shorthand for xyz-locked sources)
        if n_sources == 0:
            tier = 'unverified'
            reason = 'has xyz but no source_cameras'
        elif n_sources >= 1 and n_locked == n_sources:
            tier = 'anchor'
            reason = f'all {n_sources} sources have HUD-locked xyz'
        elif n_locked >= 2:
            tier = 'high'
            reason = f'{n_locked} HUD-locked sources'
        elif n_sources >= 3 and n_locked >= 1:
            tier = 'high'
            reason = f'{n_sources} sources incl. {n_locked} HUD-locked'
        elif (n_sources >= 3 and n_locked == 0
              and median_res is not None and median_res <= 3.0):
            # v2: cross-validation across community cams
            tier = 'high'
            reason = f'{n_sources} community sources, median res {median_res:.2f}\''
        elif n_sources == 1 and n_locked == 1:
            # v2: single HUD-locked source = medium, not low
            tier = 'medium'
            reason = '1 HUD-locked source (high-confidence single observation)'
        elif n_sources == 1:
            # v3: single community source = unverified (cannot cross-validate),
            # NOT low (low means actually bad residuals)
            tier = 'unverified'
            reason = '1 community source only (cannot cross-validate)'
        elif median_res is not None and median_res > 8.0:
            tier = 'low'
            reason = f'median residual {median_res:.1f}\' > 8\''
        elif max_res is not None and max_res > 25.0:
            tier = 'low'
            reason = f'max residual {max_res:.1f}\' > 25\''
        else:
            tier = 'medium'
            reason = f'{n_sources} sources, median res {median_res:.1f}\'' if median_res else f'{n_sources} sources'

        out[lm_name] = {
            'tier': tier,
            'n_sources': n_sources,
            # n_leak_sources kept as JSON key for back-compat with downstream
            # consumers; semantically it now means "HUD-locked-xyz sources".
            'n_leak_sources': n_locked,
            'median_res': round(median_res, 2) if median_res is not None else None,
            'max_res': round(max_res, 2) if max_res is not None else None,
            'reason': reason,
        }
    return out


def classify_cameras(lm_tiers):
    """
    Classify cams using landmark tiers as input.
    Anchor+high LM observations are "trustworthy reference observations".

    Returns dict: cam_name -> {tier, n_obs, n_anchor_high_obs, median_res_ref,
                                max_res_ref, median_res_all, reason}
    """
    out = {}
    for cam_name, cam_data in md.cameras.items():
        # Cams without xyz aren't in the bundle pool at all
        if cam_data.get('xyz') is None:
            out[cam_name] = {
                'tier': 'unverified',
                'n_obs': 0,
                'n_anchor_high_obs': 0,
                'median_res_ref': None,
                'max_res_ref': None,
                'median_res_all': None,
                'reason': 'no xyz (uncalibrated)',
            }
            continue

        # Class A cams (full HUD ground truth: xyz + ypr + fov) are anchor by
        # construction — their residuals are irrelevant because all DOF are
        # locked. Same treatment for legacy date-source cams that lack an
        # explicit audit entry (they are treated like A_full_hud by the helper).
        # B/C/Cm cams have xyz locked but their ypr (and fov for Cm) was
        # solver-refined, so they get evaluated like any other cam.
        if is_anchor(cam_name, cameras=md.cameras):
            out[cam_name] = {
                'tier': 'anchor',
                'n_obs': len(md.pixels.get(cam_name, {})),
                'n_anchor_high_obs': 0,  # not relevant
                'median_res_ref': None,
                'max_res_ref': None,
                'median_res_all': None,
                'reason': 'all DOF locked (HUD ground-truth)',
            }
            continue

        # Compute residuals
        all_res = all_residuals_for_cam(cam_name)
        n_obs = len(all_res)

        if n_obs < 2:
            # v3: lowered from <3 to <2 — 2 valid obs is informative
            out[cam_name] = {
                'tier': 'unverified',
                'n_obs': n_obs,
                'n_anchor_high_obs': 0,
                'median_res_ref': None,
                'max_res_ref': None,
                'median_res_all': None,
                'reason': f'only {n_obs} valid residuals (< 2, new arrival)',
            }
            continue

        # Filter to anchor+high LM observations only
        ref_res = [r for lm, r in all_res
                   if lm_tiers.get(lm, {}).get('tier') in ('anchor', 'high')]
        n_ref = len(ref_res)

        # v2: also collect medium-or-better observations as a fallback path
        med_or_better_res = [r for lm, r in all_res
                             if lm_tiers.get(lm, {}).get('tier')
                             in ('anchor', 'high', 'medium')]
        n_med_or_better = len(med_or_better_res)

        all_res_vals = [r for _, r in all_res]

        median_all = statistics.median(all_res_vals)
        max_all = max(all_res_vals)
        median_ref = statistics.median(ref_res) if ref_res else None
        max_ref = max(ref_res) if ref_res else None
        median_mob = (statistics.median(med_or_better_res)
                      if med_or_better_res else None)
        max_mob = max(med_or_better_res) if med_or_better_res else None

        # v3 classification — try ref-residual path first, fall back to
        # medium-or-better path when anchor+high coverage is sparse.
        # But FIRST: catch outright bad residuals regardless of LM coverage.

        # v3: if median residual is bad against ANY LMs (≥3 valid obs threshold),
        # the cam is low. Bad residuals are bad regardless of which LMs they
        # hit — this catches cams that fall through the LM-tier-dependent
        # classification when they have few anchor+high or medium obs.
        if n_obs >= 3 and median_all > 10.0:
            tier = 'low'
            reason = (f'median {median_all:.1f}\' over {n_obs} obs > 10\' '
                      f'(bad residuals regardless of LM coverage)')
            out[cam_name] = {
                'tier': tier,
                'n_obs': n_obs,
                'n_anchor_high_obs': n_ref,
                'n_med_or_better_obs': n_med_or_better,
                'median_res_ref': round(median_ref, 2) if median_ref is not None else None,
                'max_res_ref': round(max_ref, 2) if max_ref is not None else None,
                'median_res_med_or_better': round(median_mob, 2) if median_mob is not None else None,
                'median_res_all': round(median_all, 2),
                'reason': reason,
            }
            continue

        if n_ref >= 5 and median_ref <= 3.0 and (max_ref is None or max_ref <= 30.0):
            tier = 'high'
            reason = f'median ref-res {median_ref:.2f}\', {n_ref} anchor+high obs'
        elif (n_med_or_better >= 15 and median_mob is not None and median_mob <= 2.0
              and n_ref >= 2):
            # Fallback high: many medium-or-better obs with very tight residuals
            # and at least 2 anchor+high obs as sanity floor
            tier = 'high'
            reason = (f'median {median_mob:.2f}\' over {n_med_or_better} '
                      f'medium-or-better obs, {n_ref} anchor+high sanity')
        elif n_ref >= 2 and median_ref <= 6.0 and (max_ref is None or max_ref <= 30.0):
            tier = 'medium'
            reason = f'median ref-res {median_ref:.2f}\', {n_ref} anchor+high obs'
        elif (n_med_or_better >= 8 and median_mob is not None and median_mob <= 4.0
              and (max_mob is None or max_mob <= 20.0)):
            # Fallback medium: enough medium-or-better obs with reasonable residuals
            tier = 'medium'
            reason = (f'median {median_mob:.2f}\' over {n_med_or_better} '
                      f'medium-or-better obs (no anchor+high coverage)')
        elif n_ref >= 2:
            # Has reference obs but failed medium criteria → low
            tier = 'low'
            reason = (f'median ref-res {median_ref:.2f}\' > 6\' '
                      f'or max {max_ref:.1f}\' > 30\'')
        elif n_med_or_better >= 5 and median_mob is not None and median_mob > 6.0:
            # Has medium-or-better obs but residuals are bad
            tier = 'low'
            reason = (f'no anchor+high coverage; median {median_mob:.1f}\' '
                      f'over {n_med_or_better} medium-or-better obs > 6\'')
        else:
            # Genuinely no usable evaluation possible
            tier = 'unverified'
            reason = (f'insufficient coverage: {n_ref} anchor+high, '
                      f'{n_med_or_better} medium-or-better obs')

        out[cam_name] = {
            'tier': tier,
            'n_obs': n_obs,
            'n_anchor_high_obs': n_ref,
            'n_med_or_better_obs': n_med_or_better,
            'median_res_ref': round(median_ref, 2) if median_ref is not None else None,
            'max_res_ref': round(max_ref, 2) if max_ref is not None else None,
            'median_res_med_or_better': round(median_mob, 2) if median_mob is not None else None,
            'median_res_all': round(median_all, 2),
            'reason': reason,
        }
    return out


# ── Two-pass driver ─────────────────────────────────────────────────────────

# ── DUAL-METRIC-V2 (Phase 2, 2026-07-07): regle de promotion ────────────
# Une cam low/unverified dont la mediane METRES <= 1.0m sur >= 3 obs est
# promue MEDIUM (pas high: medium suffit pour redevenir source de
# triangulation et recevoir un poids BA decent, sans en faire une ancre).
# Justification: l'arcmin explose a courte portee; 12 cams etaient punies
# a tort (Metro SE B: 0.046m reels). Liste validee humainement 2026-07-07.
PROMO_MAX_MEDIAN_M = 1.0
PROMO_MIN_OBS = 3
_dual_memo = {}

def _median_m(cam_name):
    if cam_name not in _dual_memo:
        from common import cam_rms_dual
        d = cam_rms_dual(cam_name)
        _dual_memo[cam_name] = (None, 0) if d is None else (d['median_m'], d['n'])
    return _dual_memo[cam_name]

# ── TIERS-SIGMA-V1 (2026-07-08): demotion des LM a confiance non meritee ──
# Un LM anchor/high avec sigma_m > 20m (COVARIANCE-V1) a des sources qui
# s'accordent angulairement mais une geometrie molle (parallaxe faible):
# sa confiance de tier n'est pas meritee — il ne doit ni peser fort au BA
# ni cascader des promotions de cams. Symetrique de la promotion V2.
LM_DEMOTE_SIGMA_M = 20.0

def apply_sigma_demotions(lm_tiers):
    demoted = []
    try:
        from common import lm_sigma_m
    except Exception:
        return demoted
    for lm_name, rec in lm_tiers.items():
        if rec.get('tier') not in ('anchor', 'high'):
            continue
        s = lm_sigma_m(lm_name)
        if s is not None and s > LM_DEMOTE_SIGMA_M:
            old_tier = rec['tier']
            rec['tier'] = 'medium'
            rec['reason'] = (f'TIERS-SIGMA demotion: sigma {s:.1f}m > '
                             f'{LM_DEMOTE_SIGMA_M}m (geometrie molle) — etait '
                             f'{old_tier}: ' + str(rec.get('reason', '?')))
            demoted.append((s, lm_name, old_tier))
    return demoted


def apply_dual_promotions(cam_tiers):
    promoted = []
    for cam_name, rec in cam_tiers.items():
        if rec['tier'] not in ('low', 'unverified'):
            continue
        m, n = _median_m(cam_name)
        if m is not None and m <= PROMO_MAX_MEDIAN_M and n >= PROMO_MIN_OBS:
            rec['tier'] = 'medium'
            rec['reason'] = (f'DUAL-METRIC promotion: median {m:.3f}m <= '
                             f'{PROMO_MAX_MEDIAN_M}m sur {n} obs '
                             f'(arcmin trompeur a courte portee) — etait: '
                             + rec.get('reason', '?'))
            promoted.append((m, n, cam_name))
    return promoted


def two_pass_classify():
    """
    v2: 6-pass alternating classifier. The medium-LM fallback in cam tiering
    means cam tiers depend on medium LM tiers, which depend on previous-pass
    cam tiers. More passes = more chance to converge.

    Stops early if a pass produces no tier changes.
    """
    def source_only_cam_tier(cam_name):
        # Pass-1 bootstrap: a cam is treated as anchor for LM triangulation
        # iff its xyz is HUD ground-truth — i.e. constraint_class in
        # {A, B, C, Cm} (or the synthetic _legacy_date for cams whose source
        # matches YYYY-MM-DD but lack an audit entry). Class D (no HUD
        # readable) does NOT count — D cams have no ground-truth xyz.
        if is_triangulation_trusted(cam_name, cameras=md.cameras):
            return 'anchor'
        return 'unknown'

    print("Pass 1: classifying landmarks (cam source field only)...")
    lm_tiers = classify_landmarks(source_only_cam_tier)
    apply_sigma_demotions(lm_tiers)  # TIERS-SIGMA-V1
    cam_tiers = {}

    for pass_num in range(2, 7):  # passes 2 through 6
        if pass_num % 2 == 0:
            # Even pass: classify cams
            print(f"Pass {pass_num}: classifying cams using pass-{pass_num-1} LM tiers...")
            new_tiers = classify_cameras(lm_tiers)
            apply_dual_promotions(new_tiers)  # DUAL-METRIC-V2
            changes = sum(1 for c in new_tiers
                          if cam_tiers.get(c, {}).get('tier') != new_tiers[c]['tier'])
            cam_tiers = new_tiers
        else:
            # Odd pass: classify lms
            print(f"Pass {pass_num}: re-classifying LMs using pass-{pass_num-1} cam tiers...")
            def cam_tier_lookup(cam_name, _ct=cam_tiers):
                return _ct.get(cam_name, {}).get('tier', 'unknown')
            new_tiers = classify_landmarks(cam_tier_lookup)
            apply_sigma_demotions(new_tiers)  # TIERS-SIGMA-V1
            changes = sum(1 for l in new_tiers
                          if lm_tiers.get(l, {}).get('tier') != new_tiers[l]['tier'])
            lm_tiers = new_tiers

        print(f"  → {changes} tier changes in this pass")
        if changes == 0 and pass_num >= 3:
            print(f"  → Converged at pass {pass_num}, stopping early")
            break

    return cam_tiers, lm_tiers


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--verbose', action='store_true',
                    help='print per-tier summary table')
    ap.add_argument('--explain', metavar='NAME',
                    help='print full reasoning for one cam or landmark')
    args = ap.parse_args()

    cam_tiers, lm_tiers = two_pass_classify()

    # ── DUAL-METRIC: annotation metres + log des promotions appliquees ──
    from common import cam_rms_dual
    promoted = []
    for cam_name, rec in cam_tiers.items():
        d = cam_rms_dual(cam_name)
        rec['median_res_m'] = (None if d is None or d['median_m'] is None
                               else round(d['median_m'], 3))
        if rec.get('reason', '').startswith('DUAL-METRIC promotion'):
            promoted.append((rec['median_res_m'], d['n'] if d else 0, cam_name))
    lm_demoted = [(None, n) for n, r in lm_tiers.items()
                  if str(r.get('reason', '')).startswith('TIERS-SIGMA demotion')]
    try:
        from common import lm_sigma_m as _lsm
        lm_demoted = sorted((_lsm(n) or 0, n) for _s, n in lm_demoted)
    except Exception:
        pass
    if lm_demoted:
        print(f"\n⚑ TIERS-SIGMA-V1: {len(lm_demoted)} LM anchor/high DEMOTES "
              f"medium (sigma > {LM_DEMOTE_SIGMA_M}m, geometrie molle):")
        for s, n in lm_demoted:
            print(f"    {s:6.1f}m  {n}")
    if promoted:
        promoted.sort()
        print(f"\n⚑ DUAL-METRIC-V2: {len(promoted)} cam(s) PROMUES medium "
              f"(median <= {PROMO_MAX_MEDIAN_M}m, arcmin trompeur):")
        for m, n, cam_name in promoted:
            print(f"    {m:6.3f}m  n={n:<3d} {cam_name}")

    # ── Summary ────────────────────────────────────────────────────────────
    cam_tier_counts = Counter(v['tier'] for v in cam_tiers.values())
    lm_tier_counts  = Counter(v['tier'] for v in lm_tiers.values())

    print()
    print("─" * 72)
    print(f"{'Tier':<12} {'Cameras':>10} {'Landmarks':>12}")
    print("─" * 72)
    for tier in ('anchor', 'high', 'medium', 'low', 'unverified'):
        print(f"{tier:<12} {cam_tier_counts.get(tier, 0):>10} {lm_tier_counts.get(tier, 0):>12}")
    print("─" * 72)
    print(f"{'TOTAL':<12} {sum(cam_tier_counts.values()):>10} {sum(lm_tier_counts.values()):>12}")
    print()

    # ── Verbose / explain ─────────────────────────────────────────────────
    if args.verbose:
        print("\nLow-tier cameras (need attention):")
        low_cams = [(k, v) for k, v in cam_tiers.items() if v['tier'] == 'low']
        low_cams.sort(key=lambda kv: kv[1].get('median_res_ref') or 999, reverse=True)
        for name, info in low_cams[:20]:
            print(f"  {name}")
            print(f"    {info['reason']}")
        if len(low_cams) > 20:
            print(f"  … and {len(low_cams) - 20} more")
        print()

        print("Low-tier landmarks (need attention):")
        low_lms = [(k, v) for k, v in lm_tiers.items() if v['tier'] == 'low']
        low_lms.sort(key=lambda kv: kv[1].get('median_res') or 999, reverse=True)
        for name, info in low_lms[:20]:
            print(f"  {name}")
            print(f"    {info['reason']}")
        if len(low_lms) > 20:
            print(f"  … and {len(low_lms) - 20} more")

    if args.explain:
        name = args.explain
        if name in cam_tiers:
            info = cam_tiers[name]
            print(f"\nCAMERA: {name}")
            print(f"  Tier: {info['tier']}")
            for k, v in info.items():
                if k != 'tier':
                    print(f"  {k}: {v}")
        elif name in lm_tiers:
            info = lm_tiers[name]
            print(f"\nLANDMARK: {name}")
            print(f"  Tier: {info['tier']}")
            for k, v in info.items():
                if k != 'tier':
                    print(f"  {k}: {v}")
        else:
            print(f"\n'{name}' not found in cameras or landmarks")
            sys.exit(1)

    # ── Write output ──────────────────────────────────────────────────────
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {
        'cameras': cam_tiers,
        'landmarks': lm_tiers,
        'summary': {
            'cameras': dict(cam_tier_counts),
            'landmarks': dict(lm_tier_counts),
        },
        '_doc': (
            'Confidence tiers — generated by tools/compute_confidence_tiers.py. '
            'See script docstring for tier definitions. Used by Phase B intake '
            'gate and Phase C weighted bundle adjust.'
        ),
    }
    tmp = OUT_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(out, f, indent=2, sort_keys=True)
    os.replace(tmp, OUT_PATH)
    print(f"\n✓ Written: {OUT_PATH}")
    print(f"  Use this as input for Phase B (intake gate) and Phase C (weighted BA).")


if __name__ == '__main__':
    main()
