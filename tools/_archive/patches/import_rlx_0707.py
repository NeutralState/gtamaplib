#!/usr/bin/env python3
"""import_rlx_0707.py -- import des markings rlx du 2026-07-07. Idempotent.
Dry-run par defaut. --apply pour ecrire. Backups .bak_rlx0707.
IMPORTE: 3 markings Grassrivers River Mouth (Airplane X + Keys) + 2 LM skeletons;
FUSION rlx Island K -> Vake Island (rename markings Key Lento, pixels identiques,
suppression des 2 LM Island K orphelins mono-source; fusion PROUVEE par la
geometrie: rayons Key Lento+Keys se croisent a 4.2-4.4').
SKIP documentes: House with Boat (X) move 33px sur Postcard (collision de nom
pending, toucherait une source de notre LM 0.133m); Seven Mile Bridge B snaps
(markings absents chez nous); poses/xyz rlx (sa recalib massive du 07-07 = solve,
pas donnees — le fov Jason X qui bouge 58.8->57.0 l'a prouve)."""
import argparse, json, shutil

ADDS = {
    "Leonida Keys 01 (Airplane) (X)": {"Grassrivers River Mouth (W)": [1190.0, 661.5]},
    "Keys": {"Grassrivers River Mouth (W)": [176.0, 43.0],
             "Grassrivers River Mouth (E)": [219.0, 30.0]},
}
RENAMES_KEYLENTO = {"Island K (E)": "Vake Island (E)", "Island K (W)": "Vake Island (W)"}
NEW_LMS = {"Grassrivers River Mouth (W)": "grassrivers", "Grassrivers River Mouth (E)": "grassrivers"}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    A = ap.parse_args().apply
    print(("=== APPLY ===" if A else "=== DRY-RUN (use --apply) ===") + "\n")
    px = json.load(open("gtamapdata/pixels.json"))
    lms = json.load(open("gtamapdata/landmarks.json"))
    for cam, marks in ADDS.items():
        for lm, p in marks.items():
            if lm in px[cam]:
                print(f"ok   {cam} :: {lm} deja present"); continue
            print(f"ADD  {cam} :: {lm} @ {p}"); px[cam][lm] = p
    kl = px["Key Lento"]
    for old, new in RENAMES_KEYLENTO.items():
        if old in kl and new not in kl:
            print(f"REN  Key Lento :: {old} -> {new} (pixel {kl[old]})")
            kl[new] = kl.pop(old)
        elif new in kl:
            print(f"ok   Key Lento :: {new} deja renomme")
        else:
            print(f"??   Key Lento :: {old} absent -- skip")
    for old in RENAMES_KEYLENTO:
        if old in lms:
            print(f"DEL  LM {old} (orphelin mono-source apres fusion, xyz {lms[old].get('xyz')})")
            del lms[old]
        else:
            print(f"ok   LM {old} deja supprime")
    for lm, zone in NEW_LMS.items():
        if lm not in lms:
            lms[lm] = {"xyz": None, "source_cameras": [], "error_m": None, "zone": zone, "author": "rlx"}
            print(f"LM   skeleton: {lm} ({zone})")
    if A:
        shutil.copy("gtamapdata/pixels.json", "gtamapdata/pixels.json.bak_rlx0707")
        shutil.copy("gtamapdata/landmarks.json", "gtamapdata/landmarks.json.bak_rlx0707")
        for path, obj in (("gtamapdata/pixels.json", px), ("gtamapdata/landmarks.json", lms)):
            with open(path, "w") as f:
                json.dump(obj, f, indent=2, ensure_ascii=True); f.write("\n")
        print("ECRIT (backups .bak_rlx0707)")
    else:
        print("DRY-RUN: rien ecrit.")

if __name__ == "__main__":
    main()
