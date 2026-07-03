#!/usr/bin/env python3
"""invariants.py — Pre-commit guardrail for gtamapdata/. Exit 1 on violation.

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
from leak_cam_audit import is_triangulation_trusted, get_class

# [CLASS-AWARE-V1] DOF verrouillees par classe V2 — seules celles-la sont
# comparees a la reference gelee. C laisse ypr libre, Cm laisse ypr+fov.
_LOCKED_KEYS = {
    'A': ('xyz', 'ypr', 'fov'),
    'B': ('xyz', 'ypr', 'fov'),
    'C': ('xyz', 'fov'),
    'Cm': ('xyz',),
}
def _locked_keys(cam_name):
    cls = (get_class(cam_name, cameras=md.cameras) or '')
    for pref in ('Cm', 'A', 'B', 'C'):
        if cls.startswith(pref):
            return _LOCKED_KEYS[pref]
    return ('xyz', 'ypr', 'fov')

REF_PATH = os.path.join(ROOT, "tools", "audit", "leak_poses_ref.json")
EPS = 1e-6


def locked_cams():
    return sorted(n for n in md.cameras if is_triangulation_trusted(n, cameras=md.cameras))


# [CAM-Z-V1] No camera below ground/water. Catches depth-degenerate solves
# that slide underground while keeping perfect residuals (Gas Station (Chase)
# (S) was found at z=-34.7 on 2026-07-02).
CAM_Z_MIN = -1.0
CAM_Z_WHITELIST = {
    # legit out-of-bounds glitch view (rough east-coast sketch)
    'Glitch (A)': 'out-of-bounds glitch capture',
    # 4 obs = all high towers (Four Seasons x3 + WDNA 409m): depth-degenerate,
    # sub-arcmin solutions span 2.4km. Pending a LOW anchor (the sign itself).
    'Vice City 01 (Vice City Sign)': 'depth-degenerate, pending low anchor',
    # z=-2.34, mild — but load-bearing source of 14 km-fragile triangulations
    # (Sunny Isles towers). Solo re-solve shatters them (near-miss 2026-07-02).
    # Fix must go through the bundle (joint move), never solo.
    'Jet Ski': 'load-bearing source of 14 fragile LMs; fix via bundle only',
}

def check_cam_z(fails):
    for n, c in md.cameras.items():
        xyz = c.get('xyz')
        if not xyz:
            continue
        if xyz[2] < CAM_Z_MIN and n not in CAM_Z_WHITELIST:
            fails.append(f"CAM-Z: {n} at z={xyz[2]:.2f} (< {CAM_Z_MIN}) — "
                         f"underground/underwater camera (depth-degenerate solve?)")


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
    check_cam_z(fails)  # [CAM-Z-V1]
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
            for k in _locked_keys(n):  # [CLASS-AWARE-V1]
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

    # ── 2b. doublons case-insensitive (LMs et cams) ─────────────────────
    import collections as _coll
    for label, keys in (("landmarks", md.landmarks), ("cameras", md.cameras)):
        low = _coll.Counter(k.lower() for k in keys)
        for k, v in low.items():
            if v > 1:
                originals = [o for o in keys if o.lower() == k]
                fails.append(f"DOUBLON {label}: {originals} ne different que par la casse")

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
