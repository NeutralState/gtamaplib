#!/usr/bin/env python3
"""
patch_pin_regex_fix.py — Fix mineur post-feedback rlx :
  - Retire `Pin` du regex COASTAL_PATTERNS dans find_z_candidates.py.
    Justification : les `Pin AXX/BXX/CXX/DXX` sont des shipping lane pins
    triangulés depuis les 2 cams Keys (LEAK), pas des coastal points.
    Ils ont z entre 1.26m et 4.29m donc le threshold 1.0m les a déjà
    skipped, mais retirer le pattern évite tout risque futur.
  - Update CLAUDE_CONTEXT.md pour documenter cette nuance.

Run depuis la racine du repo :
    python3 patch_pin_regex_fix.py             # dry-run
    python3 patch_pin_regex_fix.py --apply
"""
import argparse
import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
FIND_Z_PATH    = os.path.join(REPO_ROOT, 'tools', 'audit', 'find_z_candidates.py')
CONTEXT_PATH   = os.path.join(REPO_ROOT, 'tools', 'CLAUDE_CONTEXT.md')

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

if not all(os.path.isfile(p) for p in [FIND_Z_PATH, CONTEXT_PATH]):
    print("✗ Lance ce script depuis la racine de gtamaplib-main/")
    sys.exit(1)


def patch_file(path, replacements, marker_already_applied=None):
    with open(path) as f:
        content = f.read()
    if marker_already_applied and marker_already_applied in content:
        return 'already_patched'
    new_content = content
    for old, new in replacements:
        if old not in new_content:
            return f"error: pattern not found:\n{old[:200]}..."
        if new_content.count(old) > 1:
            return f"error: pattern found multiple times: {old[:100]}..."
        new_content = new_content.replace(old, new)
    if args.apply:
        shutil.copy(path, path + '.bak_pin_regex_fix')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


# ── Patch 1 : find_z_candidates.py ──────────────────────────────────────────

FIND_OLD_REGEX = '''# Patterns dans les noms qui suggèrent un objet au niveau du sol/eau
COASTAL_PATTERNS = re.compile(
    r'\\b('
    r'Pin|Marina|Pier|Beach|Coast|Boat|Dock|Buoy|'
    r'Jetty|Boardwalk|Wharf|Quay|Lagoon|Inlet|Cove|'
    r'Harbor|Harbour|Mangrove|Shoreline|Surf'
    r')\\b',
    re.IGNORECASE
)'''

FIND_NEW_REGEX = '''# Patterns dans les noms qui suggèrent un objet au niveau du sol/eau.
# NOTE : `Pin` exclu volontairement — les `Pin AXX/BXX/CXX/DXX` sont des
# shipping lane pins triangulés depuis les cams Keys (LEAK) et ont z=2-4m,
# pas z=0. Si on ajoute des "marina pins" plus tard, utilise un nom plus
# explicite (ex: "Marina Pin").
COASTAL_PATTERNS = re.compile(
    r'\\b('
    r'Marina|Pier|Beach|Coast|Boat|Dock|Buoy|'
    r'Jetty|Boardwalk|Wharf|Quay|Lagoon|Inlet|Cove|'
    r'Harbor|Harbour|Mangrove|Shoreline|Surf'
    r')\\b',
    re.IGNORECASE
)'''


# ── Patch 2 : CLAUDE_CONTEXT.md (gotcha) ────────────────────────────────────

CONTEXT_OLD_GOTCHA = '''## Gotchas / leçons apprises'''

CONTEXT_NEW_GOTCHA = '''## Gotchas / leçons apprises

> **Shipping lane pins ne sont PAS coastal** — les landmarks `Pin AXX/BXX/CXX/DXX`
> sont triangulés depuis les 2 cams Keys (LEAK) et flottent à z=2-4m, pas à
> sea level. Le scan `find_z_candidates.py` exclut explicitement `Pin` du
> regex. Source : feedback rlx 2026-05-07.
'''

# ── Apply ───────────────────────────────────────────────────────────────────

if not args.apply:
    print("═══════════════════════════════════════════════════════════════")
    print("  DRY-RUN — Lance avec --apply pour exécuter")
    print("═══════════════════════════════════════════════════════════════\n")

print("── Patch 1/2 : tools/audit/find_z_candidates.py ──")
res = patch_file(FIND_Z_PATH, [(FIND_OLD_REGEX, FIND_NEW_REGEX)],
                 marker_already_applied="`Pin` exclu volontairement")
print(f"  → {res}")

print("── Patch 2/2 : tools/CLAUDE_CONTEXT.md ──")
res = patch_file(CONTEXT_PATH, [(CONTEXT_OLD_GOTCHA, CONTEXT_NEW_GOTCHA)],
                 marker_already_applied="Shipping lane pins ne sont PAS coastal")
print(f"  → {res}")

print()
if args.apply:
    print("✓ Patches appliqués")
    print("\n  Vérifier :")
    print("    python3 tools/audit/find_z_candidates.py")
    print("    # devrait toujours retourner 65 candidats (Pin n'a aucun match <1m de toute façon)")
else:
    print("Lance avec --apply pour exécuter.")
