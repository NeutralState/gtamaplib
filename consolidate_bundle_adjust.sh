#!/usr/bin/env bash
#
# consolidate_bundle_adjust.sh — Un seul bundle_adjust.py going forward.
#
#   - tools/bundle_adjust_v2.py        → tools/_archive/bundle_adjust_v2.py
#   - tools/bundle_adjust_v3_twopass.py → tools/bundle_adjust.py (canonical)
#   - Update les references textuelles dans 3 fichiers
#   - Update tools/CLAUDE_CONTEXT.md
#
# Usage :
#   ./consolidate_bundle_adjust.sh              # dry-run
#   ./consolidate_bundle_adjust.sh --apply

set -euo pipefail

APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

if [[ ! -f "tools/bundle_adjust_v3_twopass.py" ]]; then
  echo "✗ tools/bundle_adjust_v3_twopass.py introuvable — t'es à la racine du repo ?"
  exit 1
fi

run() {
  if [[ $APPLY -eq 1 ]]; then
    eval "$@"
    echo "  $*"
  else
    echo "    [dry-run] $*"
  fi
}

if [[ $APPLY -eq 0 ]]; then
  echo "═══════════════════════════════════════════════════════════════"
  echo "  DRY-RUN — Lance avec --apply pour exécuter"
  echo "═══════════════════════════════════════════════════════════════"
  echo
fi

# ──────────────────────────────────────────────────────────────────────────
# 1. Archive v2
# ──────────────────────────────────────────────────────────────────────────
echo "── 1. Archive bundle_adjust_v2.py ──"
run "git mv tools/bundle_adjust_v2.py tools/_archive/bundle_adjust_v2.py"
echo

# ──────────────────────────────────────────────────────────────────────────
# 2. Rename v3 → canonical
# ──────────────────────────────────────────────────────────────────────────
echo "── 2. Rename v3_twopass → bundle_adjust.py ──"
run "git mv tools/bundle_adjust_v3_twopass.py tools/bundle_adjust.py"
echo

# ──────────────────────────────────────────────────────────────────────────
# 3. Update le docstring/header dans le nouveau bundle_adjust.py
# ──────────────────────────────────────────────────────────────────────────
echo "── 3. Update docstring du nouveau bundle_adjust.py ──"
if [[ $APPLY -eq 1 ]]; then
  # Replace lines 3 + 19 (ref to filename in docstring + Usage)
  python3 << 'PYEOF'
import re
path = 'tools/bundle_adjust.py'
with open(path) as f:
    src = f.read()

# Remplace "bundle_adjust_v3_twopass.py" partout par "bundle_adjust.py"
src = src.replace('bundle_adjust_v3_twopass.py', 'bundle_adjust.py')
# La ligne "Output JSON format identical to v1/v2" devient pas pertinente
src = src.replace(
    'Output JSON format identical to v1/v2 — bundle_adjust_apply.py works as-is.',
    'Output JSON format compatible with bundle_adjust_apply.py.'
)

with open(path, 'w') as f:
    f.write(src)
print("  ✓ Updated docstring of tools/bundle_adjust.py")
PYEOF
else
  echo "    [dry-run] python3 fix-up des refs dans bundle_adjust.py"
fi
echo

# ──────────────────────────────────────────────────────────────────────────
# 4. Update les references dans les autres fichiers
# ──────────────────────────────────────────────────────────────────────────
echo "── 4. Update references dans outliers_report.py + batch_retriangulate + audit ──"

update_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "    [skip] $file introuvable"
    return
  fi
  if [[ $APPLY -eq 1 ]]; then
    # Replace bundle_adjust_v2.py → bundle_adjust.py partout
    # Sur macOS, sed -i wants '' arg
    sed -i '' 's|bundle_adjust_v2\.py|bundle_adjust.py|g' "$file"
    sed -i '' 's|bundle_adjust_v2|bundle_adjust|g' "$file"
    echo "  ✓ $file"
  else
    echo "    [dry-run] sed bundle_adjust_v2 → bundle_adjust dans $file"
  fi
}

update_file "tools/outliers_report.py"
update_file "tools/refine/batch_retriangulate_aiwe_fixed.py"
update_file "tools/audit/audit_leak_consistency.py"
echo

# ──────────────────────────────────────────────────────────────────────────
# 5. Update CLAUDE_CONTEXT.md
# ──────────────────────────────────────────────────────────────────────────
echo "── 5. Update CLAUDE_CONTEXT.md ──"
if [[ $APPLY -eq 1 ]]; then
  python3 << 'PYEOF'
path = 'tools/CLAUDE_CONTEXT.md'
with open(path) as f:
    src = f.read()

OLD = """│   ├── bundle_adjust_v2.py     ← solver actuel (L-BFGS-B sur cams + lms)
│   ├── bundle_adjust_v3_twopass.py
│   ├── bundle_adjust_apply.py"""
NEW = """│   ├── bundle_adjust.py        ← solver actuel (TRF two-pass: linear → huber)
│   ├── bundle_adjust_apply.py"""

if OLD in src:
    src = src.replace(OLD, NEW)
    print("  ✓ Updated tools/ tree section")
else:
    print("  ⚠ tools/ tree section non trouvée — update manuel à faire")

with open(path, 'w') as f:
    f.write(src)
PYEOF
else
  echo "    [dry-run] update CLAUDE_CONTEXT.md tools/ tree section"
fi
echo

echo "═══════════════════════════════════════════════════════════════"
if [[ $APPLY -eq 1 ]]; then
  echo "  ✓ Consolidation terminée"
  echo
  echo "  Vérifier :"
  echo "    grep -rn 'bundle_adjust_v[23]' tools/ --include='*.py' --include='*.md'"
  echo "    # devrait juste retourner les fichiers archivés dans _archive/"
  echo
  echo "  Puis :"
  echo "    git status"
  echo "    git add -A"
  echo "    git commit -m 'consolidate: drop bundle_adjust v2, rename v3 to canonical'"
else
  echo "  Lance avec --apply pour exécuter."
fi
echo "═══════════════════════════════════════════════════════════════"
