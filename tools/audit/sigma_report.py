#!/usr/bin/env python3
"""
sigma_report.py -- lecture de tools/generated/covariances.json. [COVARIANCE-V1]

Produit par bundle_adjust_weighted (hook post-solve): sigma par pose et par LM
via diag((J^T J)^-1) * s2, priors/barrieres inclus. ECHELLE ABSOLUE a prendre
avec un grain de sel (depend du modele de bruit; a calibrer Phase B) — le
CLASSEMENT relatif est solide.

Usage:
  python3 tools/audit/sigma_report.py [--top 12] [--zone vice_city]
  python3 tools/audit/sigma_report.py --surprises   # tier vs sigma en conflit
"""
import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
os.chdir(ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=12)
    ap.add_argument('--zone', default=None)
    ap.add_argument('--surprises', action='store_true',
                    help='LM/cams dont le tier et le sigma se contredisent')
    args = ap.parse_args()

    cov = json.load(open('tools/generated/covariances.json'))
    lms_meta = json.load(open('gtamapdata/landmarks.json'))
    tiers = {}
    try:
        t = json.load(open('tools/generated/confidence_tiers.json'))
        tiers = {'cams': t.get('cameras', t.get('cams', {})),
                 'lms': t.get('landmarks', t.get('lms', {}))}
    except Exception:
        tiers = {'cams': {}, 'lms': {}}

    lms = [(v['sigma_m'], n) for n, v in cov['lms'].items()
           if args.zone is None or (lms_meta.get(n) or {}).get('zone') == args.zone]
    cams = [(v['sigma_pos_m'], max(v['sigma_ypr_deg']), v['sigma_hfov_deg'], n)
            for n, v in cov['cams'].items()]
    lms.sort()
    cams.sort()
    med_lm = lms[len(lms) // 2][0] if lms else None
    med_cam = cams[len(cams) // 2][0] if cams else None

    print(f"COVARIANCE — {len(lms)} LM (sigma median {med_lm}m) | "
          f"{len(cams)} cams (sigma pos median {med_cam}m) | s2={cov['meta']['s2']:.2f}")
    print(f"\nLM les plus incertains{' (' + args.zone + ')' if args.zone else ''}:")
    for s, n in lms[-args.top:][::-1]:
        tier = (tiers['lms'].get(n) or {}).get('tier', '?')
        print(f"  {s:8.2f}m [{tier:10s}] {n}")
    print(f"\nPoses les plus incertaines:")
    for s, sy, sf, n in cams[-args.top:][::-1]:
        tier = (tiers['cams'].get(n) or {}).get('tier', '?')
        print(f"  pos {s:7.2f}m  ypr {sy:6.3f}deg  fov {sf:6.3f}deg  [{tier:10s}] {n}")

    if args.surprises:
        print('\n=== SURPRISES (tier et sigma en desaccord) ===')
        print('LM anchor/high avec sigma > 20m (confiance tier non meritee geometriquement):')
        for s, n in sorted(lms, reverse=True):
            tier = (tiers['lms'].get(n) or {}).get('tier')
            if tier in ('anchor', 'high') and s > 20:
                print(f"  {s:8.2f}m [{tier}] {n}")
        print('\nLM low/unverified avec sigma < 2m (mieux contraints que leur tier):')
        for s, n in lms:
            tier = (tiers['lms'].get(n) or {}).get('tier')
            if tier in ('low', 'unverified') and s < 2:
                print(f"  {s:8.2f}m [{tier}] {n}")


if __name__ == '__main__':
    main()
