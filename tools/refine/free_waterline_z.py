#!/usr/bin/env python3
"""free_waterline_z.py — Retire le z_constraint fixed 0.0 des LM "ligne d'eau"
naturelle et les re-triangule librement (LS multi-rayons, poses actuelles).

DOCTRINE (analyse 2026-06-10, tools/audit/keys_z_bias_analysis.py):
La ligne d'eau VISIBLE dans les frames GTA VI n'est PAS le datum z=0 du moteur.
Re-triangulation libre des LM contraints: mediane Keys -1.30m, spread -2.9 a
+0.35 (pente de plage, maree, imprecision a faible parallaxe). Confirme par la
leak Ocean near Keys (E) (pose HUD ground truth) qui place sa ligne d'eau a
-0.60m. Ni biais rigide de zone, ni maree par frame: c'est le datum qui etait
faux. z_constraint fixed 0.0 reste valide UNIQUEMENT pour les structures
construites plates verifiees (quais, seawalls, piscines) — pas les rivages.

Mesure (sandbox): liberer les 5 LM snappes ameliore toutes les observatrices,
dont la LEAK Ocean near Keys (E): 4.70' -> 0.03'. Aucune cam ne regresse.

Cibles: 10 LM leonida_keys (5 en violation disque + 5 snappes) + Di Lido
Island (N) (vice_city; marking a +3..+5m = vegetation, pas l'eau).

Ecrit via md.update_landmark(..., z_constraint=None) — JAMAIS de bypass JSON.
Dry-run par defaut; --apply pour ecrire (backup landmarks.json.bak_waterline).
"""
import argparse, json, math, os, shutil, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import gtamaplib as ml
import gtamapdata as md

# policy "keep": clear le constraint, garde le xyz disque (deja une
# triangulation libre — la bouger en LS coutait Key Lento +0.47' et
# Venetian +0.35', au-dessus de la barre 0.25). policy "ls": re-triangule
# (snappes a 0, la liberation est mesuree gagnante, max regression 0.00).
TARGETS = {
    "Island J (E)": "keep", "Island J (W)": "keep", "Island G (E)": "keep",
    "Island G (W)": "keep", "Island V (S)": "keep",
    "Key Lento (J)": "ls", "Key Lento (A)": "ls", "Sombrero Key Light (B)": "ls",
    "Island A (W)": "ls", "Blimp Bay": "ls",
    "Di Lido Island (N)": "keep",
}


def ray_ls_point(rays):
    A = np.zeros((3, 3)); b = np.zeros(3)
    for o, d in rays:
        d = np.asarray(d, float); d /= np.linalg.norm(d)
        P = np.eye(3) - np.outer(d, d)
        A += P; b += P @ np.asarray(o, float)
    return np.linalg.solve(A, b)


def cam_rms(cn, override):
    cam = ml.get_camera(cn); st = md.cameras[cn]
    cam.set_xyz(tuple(st["xyz"])); cam.set_ypr(tuple(st["ypr"])); cam.set_fov(tuple(st["fov"]))
    acc = n = 0
    for ln, px in md.pixels[cn].items():
        x = override.get(ln, md.landmarks.get(ln))
        if x is None or px is None:
            continue
        p = cam.get_pixel(x)
        if p is None:
            continue
        dx = (p[0] - px[0]) * cam.hfov / cam.w * 60
        dy = (p[1] - px[1]) * cam.vfov / cam.h * 60
        acc += dx * dx + dy * dy; n += 1
    return math.sqrt(acc / n) if n else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    observers = {}
    for c, obs in md.pixels.items():
        for l, px in obs.items():
            if px is not None:
                observers.setdefault(l, []).append(c)

    new_xyz = {}
    keep_clear = []
    for lm, policy in TARGETS.items():
        meta = md.landmarks_meta.get(lm) or {}
        if not meta.get("z_constraint"):
            print(f"SKIP {lm}: pas de z_constraint (deja libere?)")
            continue
        if policy == "keep":
            keep_clear.append(lm)
            cur = md.landmarks.get(lm)
            print(f"CLEAR  {lm}: constraint retiree, xyz disque conserve (z={cur[2]:+.2f})")
            continue
        rays = []
        for cn in observers.get(lm, []):
            if cn not in md.cameras:
                continue
            cam = ml.get_camera(cn); st = md.cameras[cn]
            cam.set_xyz(tuple(st["xyz"])); cam.set_ypr(tuple(st["ypr"])); cam.set_fov(tuple(st["fov"]))
            try:
                d = cam.get_pixel_direction(md.pixels[cn][lm])
            except Exception:
                continue
            if d is not None:
                rays.append((st["xyz"], d))
        if len(rays) < 2:
            print(f"SKIP {lm}: <2 rayons, la constraint est porteuse, on n'y touche pas")
            continue
        p = ray_ls_point(rays)
        cur = md.landmarks.get(lm)
        new_xyz[lm] = tuple(float(v) for v in p)
        dz = "" if cur is None else f" (disque z={cur[2]:+.2f})"
        print(f"LIBERE {lm}: LS=({p[0]:.2f}, {p[1]:.2f}, {p[2]:+.2f}){dz}  rays={len(rays)}")

    affected = sorted({cn for lm in new_xyz for cn in observers.get(lm, []) if cn in md.pixels})
    print(f"\n{'cam affectee':<34}{'avant':>8}{'apres':>8}{'delta':>8}")
    worst = 0.0
    for cn in affected:
        b = cam_rms(cn, {}); a = cam_rms(cn, new_xyz)
        if b is not None and a is not None:
            worst = max(worst, a - b)
            print(f"{cn:<34}{b:>7.2f}'{a:>7.2f}'{a - b:>+7.2f}'")
    if worst > 0.25:
        print(f"\nATTENTION: regression max {worst:+.2f}' > 0.25' — verifier avant d'appliquer")

    if not args.apply:
        print("\nDRY-RUN. Relance avec --apply pour ecrire.")
        return

    shutil.copy(os.path.join(ROOT, "gtamapdata", "landmarks.json"),
                os.path.join(ROOT, "gtamapdata", "landmarks.json.bak_waterline"))
    for lm, xyz in new_xyz.items():
        md.update_landmark(lm, list(xyz), z_constraint=None)
    for lm in keep_clear:
        cur = md.landmarks.get(lm)
        md.update_landmark(lm, list(cur) if cur is not None else None, z_constraint=None)
    print(f"\nAPPLIED: {len(new_xyz)} re-triangules + {len(keep_clear)} constraints retirees"
          " (backup landmarks.json.bak_waterline)")


if __name__ == "__main__":
    main()
