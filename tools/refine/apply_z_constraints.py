#!/usr/bin/env python3
"""
apply_z_constraints.py — Applique les z_constraint à un batch de landmarks
en lisant /tmp/z_candidates.json (généré par audit/find_z_candidates.py).

Pour chaque candidate :
  - Lit le z_constraint proposé (default: {"type": "fixed", "value": 0.0})
  - Snap xyz[2] = constraint.value (single source of truth)
  - Persiste dans landmarks.json via md.update_landmark()

Backup automatique : landmarks.json.bak_apply_z_constraints

Run from gtamaplib-main/ :
    python3 tools/refine/apply_z_constraints.py
    python3 tools/refine/apply_z_constraints.py --apply
    python3 tools/refine/apply_z_constraints.py --from-file /path/custom.json --apply
    python3 tools/refine/apply_z_constraints.py --lm "Marina Pin 03" --value 0.0 --apply
"""
import argparse
import json
import os
import shutil
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, GTAMAP_DIR)
import gtamapdata as md

LANDMARKS_PATH = os.path.join(GTAMAP_DIR, 'gtamapdata', 'landmarks.json')
DEFAULT_INPUT = '/tmp/z_candidates.json'

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true',
                    help='Persiste les changements dans landmarks.json')
parser.add_argument('--from-file', default=DEFAULT_INPUT,
                    help=f'JSON de candidats (default: {DEFAULT_INPUT})')
parser.add_argument('--lm', default=None,
                    help='Single landmark name (overrides --from-file)')
parser.add_argument('--value', type=float, default=0.0,
                    help='Valeur fixée pour z (default: 0.0). '
                         'Used with --lm or pour override le default du JSON.')
parser.add_argument('--type', default='fixed', choices=['fixed'],
                    help='Type de contrainte (default: fixed). '
                         'range pas encore supporté.')
args = parser.parse_args()


# ── Build the list of landmarks to apply ────────────────────────────────────

if args.lm:
    # Single landmark mode
    if args.lm not in md.landmarks:
        print(f"✗ Landmark '{args.lm}' n'existe pas dans landmarks.json")
        sys.exit(1)
    candidates = [{
        'lm': args.lm,
        'current_z': md.landmarks[args.lm][2],
    }]
    proposed_constraint = {'type': args.type, 'value': args.value}
    source = '--lm flag'
else:
    if not os.path.exists(args.from_file):
        print(f"✗ {args.from_file} n'existe pas. Run find_z_candidates.py d'abord, "
              f"ou utilise --lm <name>.")
        sys.exit(1)
    with open(args.from_file) as f:
        data = json.load(f)
    candidates = data.get('candidates', [])
    proposed_constraint = data.get('meta', {}).get(
        'proposed_constraint', {'type': 'fixed', 'value': args.value}
    )
    source = args.from_file

if not candidates:
    print("✗ Aucun candidate à appliquer.")
    sys.exit(1)


# ── Show plan ───────────────────────────────────────────────────────────────

c_type = proposed_constraint.get('type')
c_val = proposed_constraint.get('value')

print(f"Source : {source}")
print(f"Constraint à appliquer : {c_type} = {c_val}")
print(f"Landmarks à update     : {len(candidates)}")
print()

print("─" * 90)
print(f"  {'#':>3}  {'landmark':<45}  {'z avant':>9}  {'z après':>8}  {'Δz':>7}")
print("─" * 90)

skipped = []
to_apply = []
for i, c in enumerate(candidates, 1):
    lm_name = c['lm']
    if lm_name not in md.landmarks or md.landmarks[lm_name] is None:
        skipped.append((lm_name, 'no xyz'))
        continue
    cur_z = float(md.landmarks[lm_name][2])
    new_z = float(c_val)
    dz = new_z - cur_z

    existing = md.landmarks_meta.get(lm_name, {}).get('z_constraint')
    flag = ''
    if existing:
        if existing == proposed_constraint:
            skipped.append((lm_name, 'already constrained identically'))
            continue
        flag = f' (était {existing})'

    print(f"  {i:>3}  {lm_name[:45]:<45}  {cur_z:>+7.3f}m  "
          f"{new_z:>+6.2f}m  {dz:>+5.2f}m{flag}")
    to_apply.append((lm_name, new_z))

if skipped:
    print()
    print(f"⊘ Skipped ({len(skipped)}) :")
    for lm, reason in skipped[:10]:
        print(f"    {lm[:50]:<50}  ({reason})")
    if len(skipped) > 10:
        print(f"    ... +{len(skipped) - 10} more")

print()


# ── Apply ───────────────────────────────────────────────────────────────────

if not args.apply:
    print(f"(dry run — re-run with --apply pour persister {len(to_apply)} changes)")
    sys.exit(0)

if not to_apply:
    print("Rien à apply.")
    sys.exit(0)

# Backup
backup = LANDMARKS_PATH + '.bak_apply_z_constraints'
shutil.copy(LANDMARKS_PATH, backup)
print(f"✓ Backup : {backup}")

# Apply via update_landmark() — snap xyz[2] et write z_constraint
n_applied = 0
for lm_name, new_z in to_apply:
    cur_xyz = list(md.landmarks[lm_name])
    cur_xyz[2] = new_z  # snap (update_landmark le re-snap aussi by design)
    meta = md.landmarks_meta.get(lm_name, {})
    md.update_landmark(
        lm_name,
        xyz=cur_xyz,
        z_constraint=proposed_constraint,
        # Préserve source_cameras/error_m/zone (pas passés = preserve via _SENTINEL)
    )
    n_applied += 1

print(f"✓ Applied {n_applied} z_constraint(s) à landmarks.json")
print()
print("Next :")
print("  1. git diff gtamapdata/landmarks.json    # vérifier les changes")
print("  2. python3 tools/bundle_adjust.py        # re-run avec contraintes actives")
print("  3. python3 tools/bundle_adjust_apply.py  # apply les nouveaux résultats")
