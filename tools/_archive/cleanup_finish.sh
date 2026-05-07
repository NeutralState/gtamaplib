#!/usr/bin/env bash
#
# cleanup_finish.sh — Finit le cleanup là où cleanup_repo.sh a manqué :
#   - Move les .bak* dans tools/ (vrais noms avec dots) vers _archive/backups/
#   - Move les .bak* dans gtamapdata/ vers _archive/backups/
#   - Supprime cleanup_repo.sh (one-shot, plus utile)
#
# Run depuis la racine de gtamaplib-main/ après cleanup_repo.sh --apply.
#
# Usage :
#   ./cleanup_finish.sh              # dry-run
#   ./cleanup_finish.sh --apply

set -euo pipefail

APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

if [[ ! -d "tools/_archive/backups" ]]; then
  echo "✗ tools/_archive/backups/ n'existe pas — lance cleanup_repo.sh --apply d'abord"
  exit 1
fi

mv_safe() {
  local src="$1"
  local dst="$2"
  if [[ ! -e "$src" ]]; then
    echo "    [skip] $src n'existe pas"
    return
  fi
  if [[ -e "$dst" ]]; then
    echo "    [skip] $dst existe déjà"
    return
  fi
  if [[ $APPLY -eq 1 ]]; then
    git mv "$src" "$dst" 2>/dev/null || mv "$src" "$dst"
    echo "  mv $src -> $dst"
  else
    echo "    [dry-run] mv $src -> $dst"
  fi
}

rm_safe() {
  local f="$1"
  if [[ ! -e "$f" ]]; then
    echo "    [skip] $f n'existe pas"
    return
  fi
  if [[ $APPLY -eq 1 ]]; then
    rm -f "$f"
    echo "  rm $f"
  else
    echo "    [dry-run] rm $f"
  fi
}

if [[ $APPLY -eq 0 ]]; then
  echo "═══════════════════════════════════════════════════════════════"
  echo "  DRY-RUN — Lance avec --apply pour exécuter"
  echo "═══════════════════════════════════════════════════════════════"
  echo
fi

# ──────────────────────────────────────────────────────────────────────────
# 1. tools/*.bak* (vrais noms avec dots, pas underscores)
# ──────────────────────────────────────────────────────────────────────────
echo "── tools/*.bak* (avec dots) → tools/_archive/backups/ ──"
for f in tools/*.bak* tools/*.html.bak_* tools/*.py.bak* tools/*.py.bak_*; do
  if [[ -f "$f" ]]; then
    base=$(basename "$f")
    mv_safe "$f" "tools/_archive/backups/$base"
  fi
done
echo

# ──────────────────────────────────────────────────────────────────────────
# 2. gtamapdata/*.bak_* — les data backups
# ──────────────────────────────────────────────────────────────────────────
echo "── gtamapdata/*.bak_* → tools/_archive/backups/ ──"
for f in gtamapdata/*.bak_*; do
  if [[ -f "$f" ]]; then
    base=$(basename "$f")
    mv_safe "$f" "tools/_archive/backups/$base"
  fi
done
echo

# ──────────────────────────────────────────────────────────────────────────
# 3. Supprimer cleanup_repo.sh lui-même (one-shot job done)
# ──────────────────────────────────────────────────────────────────────────
echo "── Suppression cleanup_repo.sh (one-shot terminé) ──"
rm_safe "cleanup_repo.sh"
echo

# ──────────────────────────────────────────────────────────────────────────
# 4. Résumé
# ──────────────────────────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════════"
if [[ $APPLY -eq 1 ]]; then
  echo "  ✓ Fix-up terminé"
  echo
  echo "  Vérifier :"
  echo "    ls tools/                  # ne doit plus avoir de .bak*"
  echo "    ls tools/_archive/backups/ # doit contenir tous les bak*"
  echo "    git status                 # un dernier check"
  echo
  echo "  Puis :"
  echo "    git add -A"
  echo "    git commit -m 'cleanup: reorganize repo into audit/refine/_archive'"
  echo "    git push -u origin tools-cleanup"
else
  echo "  Lance avec --apply pour exécuter."
fi
echo "═══════════════════════════════════════════════════════════════"
