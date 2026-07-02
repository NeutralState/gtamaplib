#!/usr/bin/env python3
"""exclude_marking.py — exclude a (cam, lm) marking from the solver WITHOUT
supprimer de pixels.json (il reste visible dans l'UI visualizer).

Le marking liste ici est ignore par common.cam_rms et triangulate_lm.py.
Utile pour les markings rlx approximatifs: garder la trace visuelle,
retirer la contamination du calcul.

Usage:
  python3 tools/exclude_marking.py "Cam Name" "LM Name"            # exclude (dry-run)
  python3 tools/exclude_marking.py "Cam Name" "LM Name" --apply    # ecrire
  python3 tools/exclude_marking.py "Cam Name" "LM Name" --remove --apply  # re-inclure
  python3 tools/exclude_marking.py --list                          # tout lister
"""
import json, os, sys, argparse

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gtamapdata")
EXCL = os.path.join(DATA_DIR, "excluded_markings.json")
PIX  = os.path.join(DATA_DIR, "pixels.json")

def load():
    try:
        with open(EXCL) as f: return json.load(f)
    except FileNotFoundError:
        return {"_comment": "Per-(cam, landmark) markings excluded from solver. Stays in pixels.json (visible in UI)."}

def save(data):
    with open(EXCL, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=True); f.write("\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cam", nargs="?")
    ap.add_argument("lm", nargs="?")
    ap.add_argument("--remove", action="store_true", help="re-include (remove exclusion)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    data = load()
    if a.list or not a.cam:
        n = 0
        for cam, lms in data.items():
            if cam.startswith("_"): continue
            for lm in lms:
                print(f"  {cam}  <-  {lm}"); n += 1
        print(f"\n{n} excluded marking(s).")
        return 0

    if not a.lm:
        print("ERROR: need both CAM and LM (or --list)"); return 1

    pix = json.load(open(PIX))
    if a.cam not in pix or a.lm not in pix.get(a.cam, {}):
        print(f"WARNING: no marking '{a.lm}' on cam '{a.cam}' in pixels.json (excluding anyway).")

    cur = set(data.get(a.cam, []))
    if a.remove:
        if a.lm not in cur:
            print(f"'{a.lm}' not excluded on '{a.cam}' — nothing to do."); return 0
        cur.discard(a.lm); action = "RE-INCLUDE"
    else:
        if a.lm in cur:
            print(f"'{a.lm}' already excluded on '{a.cam}'."); return 0
        cur.add(a.lm); action = "EXCLUDE"

    if cur: data[a.cam] = sorted(cur)
    else: data.pop(a.cam, None)

    print(f"{action}: {a.cam}  <->  {a.lm}")
    if a.apply:
        save(data); print(f"written -> {EXCL}")
    else:
        print("DRY-RUN: use --apply to write.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
