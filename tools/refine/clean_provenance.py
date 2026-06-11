#!/usr/bin/env python3
"""clean_provenance.py — Nettoie la dette de provenance identifiee le
2026-06-10 (32 refs orphelines + 1 entree pixels morte).

CONTEXTE (verifie avant d'ecrire cet outil):
- 'Port Gellhorn Postcard' (cam supprimee) a laisse 78 markings dans
  pixels.json. Ce n'est PAS un rename de 'Port Gellhorn Postcard (X)': les
  67 LMs communs ont des pixels completement differents (crops/frames
  distincts). Sans entree camera (pose+intrinsics supprimees), ces markings
  sont des rayons sans origine: inutilisables. PURGE (l'archive = git).
- Les source_cameras orphelines (26x 'Port Gellhorn Postcard', 3x 'Gizmo',
  3x 'Penthouse (SE/NE/SW)') deviennent des marqueurs "(legacy: NAME)" —
  l'historique est preserve sans pretendre une source vivante (precedent:
  "(geometric: ...)"). Aucun changement de comportement FIXED: une source
  inconnue et un marqueur retournent tous deux non-trusted.
- CONSEQUENCE ASSUMEE: les ~41 'Bay (...)' de port_gellhorn restent a 1 rayon
  -> leurs z_constraints sont PORTEUSES et conservees. Le T3 apportera les
  seconds rayons; a ce moment natural_z_sweep.py pourra les liberer.

Ecrit via md.update_landmark (source_cameras param) pour les LMs; pixels.json
est edite par chargement/sauvegarde du JSON complet, SEULE operation sans API
(suppression de cle — update_* ne couvre pas pixels), backup .bak_provenance.
Dry-run par defaut; --apply pour ecrire. Roule invariants.py apres: les WARN
doivent tomber a 0.
"""
import argparse, json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import gtamapdata as md
sys.path.insert(0, os.path.join(ROOT, "tools"))
from common import save_json

DEAD_PIXEL_CAMS = ["Port Gellhorn Postcard"]
ORPHANS = {"Port Gellhorn Postcard", "Gizmo", "Penthouse (SE)", "Penthouse (NE)", "Penthouse (SW)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    # 1. LMs avec sources orphelines -> marqueurs legacy
    to_fix = []
    for n, m in md.landmarks_meta.items():
        srcs = (m or {}).get("source_cameras") or []
        if any(s in ORPHANS for s in srcs):
            new_srcs = [f"(legacy: {s})" if s in ORPHANS else s for s in srcs]
            to_fix.append((n, srcs, new_srcs))
    for n, old, new in to_fix:
        print(f"PROVENANCE {n}: {old} -> {new}")

    # 2. entrees pixels mortes
    px_path = os.path.join(ROOT, "gtamapdata", "pixels.json")
    with open(px_path) as f:
        px = json.load(f)
    dead = [c for c in DEAD_PIXEL_CAMS if c in px]
    for c in dead:
        print(f"PURGE pixels: '{c}' ({len(px[c])} markings sans camera — archive = git history)")

    print(f"\n# {len(to_fix)} LMs a corriger, {len(dead)} entree(s) pixels a purger")
    if not args.apply:
        print("DRY-RUN. Relance avec --apply pour ecrire.")
        return

    shutil.copy(os.path.join(ROOT, "gtamapdata", "landmarks.json"),
                os.path.join(ROOT, "gtamapdata", "landmarks.json.bak_provenance"))
    shutil.copy(px_path, px_path + ".bak_provenance")
    for n, _old, new in to_fix:
        cur = md.landmarks.get(n)
        md.update_landmark(n, list(cur) if cur is not None else None, source_cameras=new)
    for c in dead:
        del px[c]
    save_json(px_path, px)  # convention projet: indent=2, ordre preserve
    print(f"APPLIED: {len(to_fix)} LMs + {len(dead)} purge(s) (backups .bak_provenance)")


if __name__ == "__main__":
    main()
