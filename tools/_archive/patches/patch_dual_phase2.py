#!/usr/bin/env python3
"""DUAL-METRIC-V2 (Phase 2): promotion appliquee dans la convergence des tiers.
Regle: cam low/unverified avec median METRES <= 1.0m sur >= 3 obs -> MEDIUM
(redevient source de triangulation + poids BA decent; pas une ancre).
Liste des 12 validee humainement 2026-07-07. Idempotent."""
import sys
p = 'tools/compute_confidence_tiers.py'
src = open(p).read()
if 'DUAL-METRIC-V2' in src:
    print('ok  deja en Phase 2'); sys.exit(0)

a1 = "def two_pass_classify():"
b1 = '''# ── DUAL-METRIC-V2 (Phase 2, 2026-07-07): regle de promotion ────────────
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


def two_pass_classify():'''
assert a1 in src, 'ancre two_pass_classify introuvable'
src = src.replace(a1, b1, 1)

a2 = """            new_tiers = classify_cameras(lm_tiers)
            changes = sum(1 for c in new_tiers"""
b2 = """            new_tiers = classify_cameras(lm_tiers)
            apply_dual_promotions(new_tiers)  # DUAL-METRIC-V2
            changes = sum(1 for c in new_tiers"""
assert a2 in src, 'ancre boucle cams introuvable'
src = src.replace(a2, b2, 1)

i0 = src.index("    # ── DUAL-METRIC-V1: annotation metres")
i1 = src.index("    # ── Summary ──")
b3 = '''    # ── DUAL-METRIC: annotation metres + log des promotions appliquees ──
    from common import cam_rms_dual
    promoted = []
    for cam_name, rec in cam_tiers.items():
        d = cam_rms_dual(cam_name)
        rec['median_res_m'] = (None if d is None or d['median_m'] is None
                               else round(d['median_m'], 3))
        if rec.get('reason', '').startswith('DUAL-METRIC promotion'):
            promoted.append((rec['median_res_m'], d['n'] if d else 0, cam_name))
    if promoted:
        promoted.sort()
        print(f"\\n⚑ DUAL-METRIC-V2: {len(promoted)} cam(s) PROMUES medium "
              f"(median <= {PROMO_MAX_MEDIAN_M}m, arcmin trompeur):")
        for m, n, cam_name in promoted:
            print(f"    {m:6.3f}m  n={n:<3d} {cam_name}")

'''
src = src[:i0] + b3 + src[i1:]
open(p, 'w').write(src)
print('tiers: Phase 2 en place (promotion dans la convergence)')
