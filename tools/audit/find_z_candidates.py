#!/usr/bin/env python3
"""
find_z_candidates.py — Scan landmarks.json pour proposer des candidats à
contraindre à z=0 (coastal points, pins, marina, beach, etc.).

Heuristic :
  - |z| < threshold (default 1.0m) ET
  - name match COASTAL_PATTERNS OU zone in COASTAL_ZONES

Output :
  - Table à reviewer dans le terminal
  - JSON dans /tmp/z_candidates.json à passer à apply_z_constraints.py

Run from gtamaplib-main/ :
    python3 tools/audit/find_z_candidates.py
    python3 tools/audit/find_z_candidates.py --z-threshold 0.5
    python3 tools/audit/find_z_candidates.py --include-all-near-zero
"""
import argparse
import json
import os
import re
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, GTAMAP_DIR)
import gtamapdata as md

OUTPUT_PATH = '/tmp/z_candidates.json'

# Patterns dans les noms qui suggèrent un objet au niveau du sol/eau
COASTAL_PATTERNS = re.compile(
    r'\b('
    r'Pin|Marina|Pier|Beach|Coast|Boat|Dock|Buoy|'
    r'Jetty|Boardwalk|Wharf|Quay|Lagoon|Inlet|Cove|'
    r'Harbor|Harbour|Mangrove|Shoreline|Surf'
    r')\b',
    re.IGNORECASE
)

# Zones connues côtières (heuristique conservatrice)
COASTAL_ZONES = {'leonida_keys'}  # Vice City a aussi des coastal mais beaucoup de buildings

parser = argparse.ArgumentParser()
parser.add_argument('--z-threshold', type=float, default=1.0,
                    help='Max |z| pour être considéré comme candidat (default: 1.0m)')
parser.add_argument('--include-all-near-zero', action='store_true',
                    help='Inclure TOUS les landmarks avec |z| < threshold, '
                         'sans filtrer par name/zone (plus large, plus de faux positifs)')
parser.add_argument('--output', default=OUTPUT_PATH,
                    help=f'Path du JSON output (default: {OUTPUT_PATH})')
args = parser.parse_args()


def is_already_constrained(meta):
    """A déjà un z_constraint set."""
    return bool(meta.get('z_constraint'))


def matches_coastal_name(name):
    return bool(COASTAL_PATTERNS.search(name))


def is_in_coastal_zone(meta):
    return meta.get('zone') in COASTAL_ZONES


# ── Scan ────────────────────────────────────────────────────────────────────

candidates = []
already_constrained = []
near_zero_skipped = []

for lm_name, xyz in md.landmarks.items():
    if xyz is None:
        continue
    z = float(xyz[2])
    if abs(z) >= args.z_threshold:
        continue

    meta = md.landmarks_meta.get(lm_name, {})

    if is_already_constrained(meta):
        already_constrained.append((lm_name, z, meta['z_constraint']))
        continue

    name_match = matches_coastal_name(lm_name)
    zone_match = is_in_coastal_zone(meta)

    if args.include_all_near_zero or name_match or zone_match:
        reasons = []
        if name_match: reasons.append('name')
        if zone_match: reasons.append('zone')
        if not reasons: reasons.append('near-zero')
        candidates.append({
            'lm': lm_name,
            'current_z': z,
            'zone': meta.get('zone'),
            'sources': meta.get('source_cameras', []),
            'reasons': reasons,
        })
    else:
        near_zero_skipped.append((lm_name, z, meta.get('zone')))


# ── Print report ────────────────────────────────────────────────────────────

print(f"Scan landmarks.json (|z| < {args.z_threshold}m, "
      f"{'ALL near-zero' if args.include_all_near_zero else 'coastal name/zone match'})")
print()
print(f"Total landmarks scanned : {sum(1 for v in md.landmarks.values() if v is not None)}")
print(f"  Already z-constrained : {len(already_constrained)}")
print(f"  Candidats proposés    : {len(candidates)}")
print(f"  Near-zero non matched : {len(near_zero_skipped)} "
      f"(re-run avec --include-all-near-zero pour les voir)")
print()

if candidates:
    print("─" * 100)
    print(f"  {'#':>3}  {'landmark':<45}  {'z':>7}  {'zone':<14}  reasons")
    print("─" * 100)
    candidates.sort(key=lambda c: (c['zone'] or '', c['lm']))
    for i, c in enumerate(candidates, 1):
        reasons_str = '+'.join(c['reasons'])
        print(f"  {i:>3}  {c['lm'][:45]:<45}  {c['current_z']:>+6.2f}m  "
              f"{(c['zone'] or '?')[:14]:<14}  {reasons_str}")
    print()

if already_constrained:
    print(f"⊘ Already z-constrained ({len(already_constrained)}, skipped):")
    for lm, z, zc in already_constrained[:10]:
        zc_str = f"{zc.get('type')}={zc.get('value')}" if zc else 'unknown'
        print(f"    {lm[:40]:<40}  z={z:+.2f}m  ({zc_str})")
    if len(already_constrained) > 10:
        print(f"    ... +{len(already_constrained) - 10} more")
    print()

# ── Write JSON ──────────────────────────────────────────────────────────────

if candidates:
    with open(args.output, 'w') as f:
        json.dump({
            'candidates': candidates,
            'meta': {
                'z_threshold': args.z_threshold,
                'include_all_near_zero': args.include_all_near_zero,
                'proposed_constraint': {'type': 'fixed', 'value': 0.0},
            }
        }, f, indent=2)
    print(f"Wrote {args.output}")
    print()
    print("Next steps :")
    print(f"  1. Review {args.output} et enlever les faux positifs si besoin :")
    print(f"     # ex: ouvrir avec ton éditeur, supprimer les entries indésirables")
    print()
    print(f"  2. Apply :")
    print(f"     python3 tools/refine/apply_z_constraints.py")
    print(f"     python3 tools/refine/apply_z_constraints.py --apply")
else:
    print("Aucun candidat trouvé. Essaie --include-all-near-zero ou un --z-threshold plus grand.")
