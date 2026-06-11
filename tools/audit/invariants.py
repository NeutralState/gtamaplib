#!/usr/bin/env python3
"""invariants.py — Garde-fou pre-commit pour gtamapdata/. Exit 1 si violation.

Ne le contourne JAMAIS: chaque famille de bug d'aujourd'hui (2026-06-10) aurait
ete pognee ici — poses fantomes (ecrit != simule), violations z ecrites en
bypassant update_landmark, leaks bougees par un solve trop confiant.

CHECKS:
  1. Z-CONSTRAINTS: tout LM avec z_constraint fixed a xyz[2] == value sur
     disque (doctrine "single source of truth", retablie session du soir).
  2. LEAKS IMMOBILES: toute cam HUD-locked (is_triangulation_trusted) a une
     pose identique a la reference gelee tools/audit/leak_poses_ref.json.
     Apres un intake T3 legitime qui AJOUTE des leaks: --freeze pour regeler.
     Une leak qui BOUGE n'est jamais legitime.
  3. SCHEMA: cameras (xyz3/ypr3/fov2/size2), landmarks (xyz None|3),
     pixels -> cams existantes, source_cameras -> cams existantes.

Usage:
    python3 tools/audit/invariants.py            # check, exit 1 si echec
    python3 tools/audit/invariants.py --freeze   # (re)gele la reference leaks
Convention: rouler AVANT chaque `git commit` qui touche gtamapdata/.
"""
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import gtamapdata as md
sys.path.insert(0, os.path.join(ROOT, "tools"))
from leak_cam_audit import is_triangulation_trusted

REF_PATH = os.path.join(ROOT, "tools", "audit", "leak_poses_ref.json")
EPS = 1e-6


def locked_cams():
    return sorted(n for n in md.cameras if is_triangulation_trusted(n, cameras=md.cameras))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true",
                    help="(re)gele la reference des poses leaks depuis l'etat actuel")
    ap.add_argument("--strict", action="store_true",
                    help="les WARN (dette legacy, ex: provenance orpheline) deviennent des FAIL")
    args = ap.parse_args()

    if args.freeze:
        ref = {n: {"xyz": md.cameras[n]["xyz"], "ypr": md.cameras[n]["ypr"],
                   "fov": md.cameras[n]["fov"]} for n in locked_cams()}
        with open(REF_PATH, "w") as f:
            json.dump(ref, f, indent=1, sort_keys=True)
        print(f"FROZEN: {len(ref)} poses leaks -> {REF_PATH} (a committer)")
        return 0

    fails = []
    warns = []

    def is_provenance_marker(s_):
        # "(geometric: ...)" et les marqueurs TOUT_EN_MAJUSCULES (ex:
        # CONSTRUCTED_FINAL_FIT du rebuild Portofino) ne sont pas des cams.
        return s_.startswith("(") or (s_.replace("_", "").isupper() and "_" in s_)

    # ── 1. z_constraints coherentes sur disque ──────────────────────────
    for n, m in md.landmarks_meta.items():
        zc = (m or {}).get("z_constraint")
        if zc and zc.get("type") == "fixed" and md.landmarks.get(n) is not None:
            if abs(md.landmarks[n][2] - float(zc["value"])) > EPS:
                fails.append(f"Z-CONSTRAINT: {n} z={md.landmarks[n][2]:+.3f} != {zc['value']}")

    # ── 2. leaks immobiles vs reference gelee ───────────────────────────
    if not os.path.exists(REF_PATH):
        fails.append(f"LEAK-REF: {REF_PATH} absent — roule --freeze une premiere fois")
    else:
        with open(REF_PATH) as f:
            ref = json.load(f)
        cur = set(locked_cams())
        for n, r in ref.items():
            if n not in md.cameras:
                fails.append(f"LEAK: {n} dans la ref mais absente de cameras.json")
                continue
            c = md.cameras[n]
            for k in ("xyz", "ypr", "fov"):
                a, b = c.get(k), r.get(k)
                if a is None or b is None:
                    if a != b:
                        fails.append(f"LEAK: {n}.{k} {b} -> {a}")
                    continue
                if any((x is None) != (y is None) or
                       (x is not None and abs(float(x) - float(y)) > EPS)
                       for x, y in zip(a, b)):
                    fails.append(f"LEAK: {n}.{k} a bouge: {b} -> {a}")
        new_leaks = cur - set(ref)
        if new_leaks:
            print(f"NOTE: {len(new_leaks)} nouvelles cams HUD-locked pas dans la ref "
                  f"(normal apres intake; --freeze pour les geler): {sorted(new_leaks)[:5]}...")

    # ── 3. schema ────────────────────────────────────────────────────────
    for n, c in md.cameras.items():
        for k, ln in (("xyz", 3), ("ypr", 3), ("fov", 2), ("size", 2)):
            v = c.get(k)
            if not isinstance(v, (list, tuple)) or len(v) != ln:
                fails.append(f"SCHEMA cam {n}.{k}: {v!r}")
    for n in md.landmarks:
        v = md.landmarks[n]
        if v is not None and (not hasattr(v, "__len__") or len(v) != 3):
            fails.append(f"SCHEMA lm {n}.xyz: {v!r}")
        srcs = (md.landmarks_meta.get(n) or {}).get("source_cameras") or []
        for s in srcs:
            if not is_provenance_marker(s) and s not in md.cameras:
                warns.append(f"PROVENANCE lm {n}: source_camera orpheline '{s}' "
                             "(rename/suppression historique — la protection FIXED "
                             "ne s'applique plus a cette source)")
    for cn in md.pixels:
        if cn not in md.cameras:
            warns.append(f"PROVENANCE pixels: cam orpheline '{cn}' "
                         f"({len(md.pixels[cn])} markings morts — TODO: remap vers la "
                         "cam renommee ou purger)")

    if warns:
        print(f"WARNINGS: {len(warns)} (dette legacy, --strict pour en faire des FAIL)")
        for w in warns[:8]:
            print("  WARN", w)
        if len(warns) > 8:
            print(f"  ... +{len(warns)-8}")
        if args.strict:
            fails.extend(warns)

    n_zc = sum(1 for m in md.landmarks_meta.values() if (m or {}).get("z_constraint"))
    if fails:
        print(f"INVARIANTS: {len(fails)} VIOLATION(S)")
        for f_ in fails[:30]:
            print("  FAIL", f_)
        if len(fails) > 30:
            print(f"  ... +{len(fails)-30}")
        return 1
    print(f"INVARIANTS OK — z_constraints={n_zc}, leaks_ref={len(json.load(open(REF_PATH))) if os.path.exists(REF_PATH) else 0}, "
          f"cams={len(md.cameras)}, lms={len(md.landmarks)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
