#!/usr/bin/env python3
"""remove_landmark.py — Suppression SECURISEE d'un landmark.

gtamapdata n'a pas d'API de suppression (update_landmark ne couvre pas les
deletions de cle); cet outil est LE chemin canonique, avec gardes:
  - REFUSE si le LM a des markings vivants dans pixels.json
  - REFUSE si le LM est reference comme source_camera d'un autre LM (cas (geometric:))
  - REFUSE si le LM est reference dans un mesh procedural (tools/meshes/*.py)
Bypass des gardes: --force (toujours expliquer pourquoi dans le commit).

Premier usage: 'hotel Victor (SE)' (minuscule) — doublon case-insensitive de
'Hotel Victor (SE)', erreur 32.99m vs 0.10m, 82m du bon point, zero marking,
zero reference. Residu d'une vieille triangulation ratee.

Usage:
    python3 tools/refine/remove_landmark.py "Nom Du LM"           # dry-run
    python3 tools/refine/remove_landmark.py "Nom Du LM" --apply
"""
import argparse, glob, json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import gtamapdata as md
from common import save_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    name = args.name

    if name not in md.landmarks:
        sys.exit(f"ERROR: LM {name!r} introuvable")

    blocks = []
    observers = [c for c, obs in md.pixels.items() if obs.get(name) is not None]
    if observers:
        blocks.append(f"markings vivants dans {len(observers)} cam(s): {observers[:4]}")
    refs = [n for n, m in md.landmarks_meta.items()
            if name in ((m or {}).get("source_cameras") or []) and n != name]
    if refs:
        blocks.append(f"reference comme source par {len(refs)} LM(s): {refs[:4]}")
    mesh_refs = []
    for f in glob.glob(os.path.join(ROOT, "tools", "meshes", "*.py")):
        if name in open(f).read():
            mesh_refs.append(os.path.basename(f))
    if mesh_refs:
        blocks.append(f"reference dans mesh(es): {mesh_refs}")

    meta = md.landmarks_meta.get(name) or {}
    xyz = md.landmarks.get(name)
    print(f"LM: {name!r}")
    print(f"  xyz={[round(v, 2) for v in xyz] if xyz is not None else None} "
          f"err={meta.get('error_m')} srcs={meta.get('source_cameras')}")
    if blocks:
        for b in blocks:
            print("  GARDE:", b)
        if not args.force:
            sys.exit("REFUSE (utilise --force si c'est vraiment voulu)")
        print("  --force: gardes ignorees")
    else:
        print("  aucune reference vivante — suppression sure")

    if not args.apply:
        print("DRY-RUN. Relance avec --apply pour ecrire.")
        return

    lm_path = os.path.join(ROOT, "gtamapdata", "landmarks.json")
    shutil.copy(lm_path, lm_path + ".bak_remove")
    with open(lm_path) as f:
        data = json.load(f)
    del data[name]
    save_json(lm_path, data)
    # purge aussi les markings null residuels dans pixels.json le cas echeant
    px_path = os.path.join(ROOT, "gtamapdata", "pixels.json")
    with open(px_path) as f:
        px = json.load(f)
    touched = False
    for c in list(px):
        if name in px[c]:
            del px[c][name]
            touched = True
    if touched:
        shutil.copy(px_path, px_path + ".bak_remove")
        save_json(px_path, px)
    print(f"APPLIED: {name!r} supprime (backup landmarks.json.bak_remove"
          + (", pixels.json.bak_remove" if touched else "") + ")")


if __name__ == "__main__":
    main()
