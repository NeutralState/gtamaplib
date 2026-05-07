# `_archive/`

Garde l'historique du projet pour référence sans polluer le path principal.

## `patches/`

Scripts `patch_*.py` / `fix_*.py` / `polish_*.py` / `upgrade_*.py` qui ont
été appliqués sur `server.py` ou `calib.html`. Le résultat de chaque patch
est *déjà dans le code actif* — ces scripts ne sont gardés que pour
comprendre ce qui a été fait quand.

**Ne pas les ré-exécuter.**

## `backups/`

Fichiers `*.bak*` créés automatiquement avant chaque patch. Gitignored.
Filet de sécurité local — peut être supprimé sans risque.

## `rlx_originals/`

Code de rlx hors path principal :
- `triangulate.py` : script CLI à 56 branches `if sys.argv[1] == "-XXX"`.
  rlx s'en servait pour les triangulations manuelles initiales.
- `triangulate_outputs/` : artifacts générés par les sessions ci-dessus.

## `root_legacy/`

Vieux scripts qui traînaient à la racine du repo avant le cleanup
2026-05-07 :
- `find_camera_optimizer.py` : ancien outil d'optimisation, remplacé par
  les scripts dans `tools/refine/`.
- `migrate_*.py` : scripts de migration de schema déjà appliqués.
- `scan_single.py`, `topo_sort_landmarks.py` : utilitaires ponctuels.
- `topo_order.txt`, `dependency_graph.html` : artifacts générés.

## Autres fichiers

- `bundle_adjust_v1.py` : version originale du solver. Remplacée par
  `bundle_adjust_v2.py` (et `v3_twopass.py`).
- `server_fresh.py` : doublon de `server.py`, gardé au cas où.
