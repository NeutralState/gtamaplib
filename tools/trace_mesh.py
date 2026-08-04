#!/usr/bin/env python3
"""trace_mesh.py — un massif dense: TA silhouette pour la forme, les
distances de rlx pour l'echelle, et les AUTRES traces comme juge. [TRACE-MESH-V1]

LA RECETTE (celle qui a marche sur Mount Ambrosia, generalisee):
  1. crete = la trace a la main dans la vue de REFERENCE, densifiee, portee
     en 3D a la distance D(azimut) interpolee sur les cretes DECLAREES de rlx;
  2. flancs avant/arriere en pente fixe vers la base, comme sa classe Mountain;
  3. VALIDATION sur les vues qui n'ont PAS servi: la crete 3D est reprojetee
     dans chaque camera temoin tracee, et on mesure l'ecart en pixels contre
     le trait. C'est un juge qui PEUT echouer — si la profondeur de rlx est
     fausse, la crete rate les traces temoins, et ca se chiffre.

En bonus, le balayage d'echelle: on multiplie toutes les distances par k
(0.75 a 1.35) et on regarde ou les vues temoins mettent le minimum. Si c'est
a k=1, la profondeur declaree de rlx est CONFIRMEE par des donnees
independantes; sinon le k optimal est la correction mesuree.

LIMITE DITE D'AVANCE: la silhouette d'un volume depend du point de vue — la
crete vue de face n'est pas exactement la ligne de ciel vue de biais. Le
residu temoin contient donc un fond incompressible; c'est pour ca qu'on
compare TOUJOURS au meme residu calcule sur la crete de rlx (25 aretes):
le fond est le meme pour les deux, la difference est le signal.

Le trait temoin fusionne TOUS les massifs de la frame (cam_profile prend le
plus haut par colonne). Un ecart POSITIF (crete sous le trait) peut donc etre
legitime — un autre massif domine cette colonne. Un ecart NEGATIF (crete
au-dessus du ciel trace) est toujours une violation.

Usage:
  PYTHONPATH=. python3 tools/trace_mesh.py --mountain 'Mount Waffles' \
      --ref 'Diner (N)' [--sweep] [--apply]
"""
import argparse
import json
import math
import os
import sys
import tempfile

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np

MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
BASE = 20.0
SLOPE = 30.0

# les cretes DECLAREES de rlx (upstream 54e49fe), par montagne:
# (camera, [(px, py, distance_m)...]) — memes chiffres que import_rlx_mountains
RLX_CRESTS = {
    'Mount Waffles': ('Diner (N)',
        [(654, 90, 1150), (814, 102, 1200), (938, 67, 1300), (1075, 15, 1450),
         (1136, 8.5, 1500), (1194, 16, 1450), (1443, 57.5, 1450)]),
    'Waffles Ridge': ('Gas Station (Lucia)',
        [(1214, 489, 2900), (1255, 486, 2900), (1320, 485, 2900)]),
    'Mount Mountain': ('Diner (N)',
        [(1478.5, 66.5, 1900), (1543, 52.5, 2000), (1603, 69, 2100)]),
    # ses chiffres upstream (EH, gtamaplib.py:3773) — slope 15, la colline douce
    'Easy Hill': ('Ambrosia 04 (Fires)',
        [(3218.0, 905.0, 4450), (3336, 886, 4500), (3462.0, 911.5, 4600)]),
}


def azimuth(o, p):
    d = np.asarray(p, float)[:2] - o[:2]
    return math.degrees(math.atan2(d[0], d[1])) % 360.0


def densify(strokes, step=3.0):
    """Les traits, echantillonnes tous les ~step px. L'ordre du trait est
    conserve (un trait = une polyligne, pas un nuage)."""
    out = []
    for s in strokes:
        P = np.asarray(s, float)
        if len(P) < 2:
            continue
        seg = []
        for a, b in zip(P[:-1], P[1:]):
            n = max(1, int(np.linalg.norm(b - a) / step))
            for t in np.linspace(0, 1, n, endpoint=False):
                seg.append(a + t * (b - a))
        seg.append(P[-1])
        out.append(np.asarray(seg))
    return out


def depth_profile(cam, crests):
    """D(azimut) depuis les cretes declarees de rlx, vues par NOTRE pose
    (identique a la sienne sur les cams leak — verifie a l'import)."""
    o = np.asarray(cam.xyz, float)
    az, dd = [], []
    for x, y, dist in crests:
        d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
        p = o + dist / np.hypot(d[0], d[1]) * d
        az.append(azimuth(o, p))
        dd.append(float(dist))
    order = np.argsort(az)
    return np.asarray(az)[order], np.asarray(dd)[order]


def build_crest(cam, strokes, az_p, d_p, k=1.0):
    """La crete 3D: chaque point de trace porte a D(azimut)*k."""
    o = np.asarray(cam.xyz, float)
    crest = []
    for seg in densify(strokes):
        pts = []
        for u, v in seg:
            d = np.asarray(cam.get_pixel_direction((float(u), float(v))), float)
            a = math.degrees(math.atan2(d[0], d[1])) % 360.0
            D = float(np.interp(a, az_p, d_p)) * k
            pts.append(o + D / np.hypot(d[0], d[1]) * d)
        crest.append(np.asarray(pts))
    return crest


def build_mesh(cam, crest, slope_every=6, contour_step=25.0, slope=SLOPE,
               side_slope=60.0):
    """Crete + pentes + courbes de niveau, dans le style du massif Ambrosia.

    slope_every / contour_step reglent la DENSITE du rendu, pas la geometrie:
    la crete et les pentes restent les memes, on en dessine plus ou moins.
    slope: rlx declare 15 deg pour Easy Hill (colline douce), 30 ailleurs.
    side_slope: la pente des FERMETURES d'extremite. 60 deg par defaut, comme
    la classe Mountain de rlx — un flanc a 30 deg courait h/tan(30) = 1.7x la
    hauteur et gonflait l'emprise en dome (Alexandre: "pas des domes comme ca,
    ca boost le footprint pour rien"). A 60 deg le rayon est divise par 3."""
    o = np.asarray(cam.xyz, float)
    edges = []
    sl = math.tan(math.radians(slope))
    slope_lines = []
    for seg in crest:
        for a, b in zip(seg[:-1], seg[1:]):
            edges.append([list(map(float, a)), list(map(float, b))])
        for i in range(0, len(seg), slope_every):
            T = seg[i]
            for sgn in (+1.0, -1.0):
                v = (o[:2] - T[:2]) * sgn
                v /= (np.linalg.norm(v) + 1e-9)
                run = max(0.0, (T[2] - BASE)) / sl
                F = np.array([T[0] + v[0] * run, T[1] + v[1] * run, BASE])
                edges.append([list(map(float, T)), list(map(float, F))])
                slope_lines.append((T, F, sgn))
    # flancs: fermer les EXTREMITES de chaque crete par un eventail de pentes
    # (Alexandre: "faudrait fermer les cotes pour pas laisser ouvert meme si
    # c'est speculatif"). SPECULATIF ET ASSUME: aucune camera ne mesure ces
    # flancs — on prolonge simplement la pente de 30 deg en eventail entre la
    # direction avant et la direction arriere, en passant par le prolongement
    # de la crete. C'est une fermeture visuelle, pas une donnee.
    for seg in crest:
        if len(seg) < 2:
            continue
        for T, nb in ((seg[0], seg[1]), (seg[-1], seg[-2])):
            ext = (T[:2] - nb[:2])
            ext /= (np.linalg.norm(ext) + 1e-9)
            fwd = (o[:2] - T[:2])
            fwd /= (np.linalg.norm(fwd) + 1e-9)
            a_f = math.atan2(fwd[1], fwd[0])
            a_e = math.atan2(ext[1], ext[0])
            # balayage avant -> arriere par le cote du prolongement de crete
            d1 = (a_e - a_f + math.pi) % (2 * math.pi) - math.pi
            sweep = 2 * d1                      # avant -> ext -> arriere
            feet = []
            run = max(0.0, (T[2] - BASE)) / math.tan(math.radians(side_slope))
            for t in np.linspace(0.0, 1.0, 9):
                a = a_f + t * sweep
                F = np.array([T[0] + math.cos(a) * run,
                              T[1] + math.sin(a) * run, BASE])
                edges.append([list(map(float, T)), list(map(float, F))])
                feet.append(F)
            # arcs de niveau SUR l eventail (pas seulement au pied): l arc a
            # z fixe traverse tous les rayons — meme densite que le corps
            for zc in np.arange(BASE, T[2], contour_step):
                if T[2] - BASE < 1e-6:
                    break
                tt = (T[2] - zc) / (T[2] - BASE)
                ring = [T + tt * (F - T) for F in feet]
                for a, b in zip(ring[:-1], ring[1:]):
                    edges.append([list(map(float, a)), list(map(float, b))])

    # courbes de niveau: relier les pieds de pente de meme cote a z fixe
    for zc in np.arange(BASE + contour_step,
                        max(s[0][2] for s in slope_lines), contour_step):
        for sgn in (+1.0, -1.0):
            ring = []
            for T, F, s in slope_lines:
                if s != sgn or T[2] <= zc:
                    continue
                t = (T[2] - zc) / (T[2] - F[2])
                ring.append(T + t * (F - T))
            for a, b in zip(ring[:-1], ring[1:]):
                if np.linalg.norm(np.asarray(b[:2]) - np.asarray(a[:2])) < 220:
                    edges.append([list(map(float, a)), list(map(float, b))])
    return edges


def witness_residuals(crest, witness_cams, TR):
    """LE JUGE: la crete reprojetee dans chaque vue temoin, contre le trait.
    Retourne {cam: (n, mediane signee, mediane abs, pct violation)}."""
    import common
    from silhouette_hull import cam_profile
    P = np.vstack(crest)
    out = {}
    for cn in witness_cams:
        cam = common.get_cam(cn)          # gotcha #5: re-set avant CHAQUE usage
        prof = cam_profile(TR, cn, int(cam.w))
        dv = []
        for p in P:
            q = cam.get_pixel([float(x) for x in p])
            if q is None:
                continue
            u = int(round(q[0]))
            if not (0 <= u < len(prof)) or math.isnan(prof[u]):
                continue
            dv.append(q[1] - prof[u])     # >0: sous le trait; <0: dans le ciel
        if len(dv) < 10:
            out[cn] = None
            continue
        dv = np.asarray(dv)
        out[cn] = (len(dv), float(np.median(dv)), float(np.median(np.abs(dv))),
                   100.0 * float(np.mean(dv < -3.0)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mountain', required=True)
    ap.add_argument('--ref', required=True, help='camera de la trace de reference')
    ap.add_argument('--sweep', action='store_true',
                    help='balayer l echelle k et montrer ou les temoins mettent le minimum')
    ap.add_argument('--k', type=float, default=1.0,
                    help='echelle appliquee aux distances rlx (1.0 = telles '
                         'quelles; utiliser l optimum du --sweep)')
    ap.add_argument('--slope-every', type=int, default=6,
                    help='une ligne de pente tous les N points de crete')
    ap.add_argument('--contour-step', type=float, default=25.0,
                    help='courbes de niveau tous les N metres')
    ap.add_argument('--slope', type=float, default=30.0,
                    help='pente des flancs en degres (rlx: 15 pour Easy Hill)')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    import common
    from silhouette_hull import traced
    TR = traced()
    M, R = args.mountain, args.ref
    if M not in RLX_CRESTS:
        raise SystemExit(f'pas de cretes rlx declarees pour {M!r} '
                         f'(connues: {sorted(RLX_CRESTS)})')
    rlx_cam, rlx_pts = RLX_CRESTS[M]
    tr = (TR.get(R) or {}).get(M)
    if not tr:
        raise SystemExit(f'pas de trace {M!r} dans {R!r}')
    strokes = tr.get('strokes') or [tr.get('points')]
    witnesses = [c for c in TR if c != R and M in TR[c]
                 and c in json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))]

    cam = common.get_cam(R)
    az_p, d_p = depth_profile(common.get_cam(rlx_cam), rlx_pts)
    print(f'{M} — reference {R} ({sum(len(s) for s in strokes)} pts traces), '
          f'profil de profondeur rlx: {len(az_p)} cretes, '
          f'{d_p.min():.0f}-{d_p.max():.0f} m')
    print(f'temoins (traces NON utilisees pour construire): {", ".join(witnesses)}\n')

    cam = common.get_cam(R)
    crest = build_crest(cam, strokes, az_p, d_p, k=args.k)
    zs = np.vstack(crest)[:, 2]
    print(f'crete 3D (k={args.k:.2f}): {sum(len(s) for s in crest)} pts, '
          f'z {zs.min():.0f}-{zs.max():.0f} m\n')

    # ── la crete de rlx dans les memes temoins: le FOND de reference ──
    cam_r = common.get_cam(rlx_cam)
    o = np.asarray(cam_r.xyz, float)
    rlx_crest = []
    for x, y, dist in rlx_pts:
        d = np.asarray(cam_r.get_pixel_direction((float(x), float(y))), float)
        rlx_crest.append(o + dist / np.hypot(d[0], d[1]) * d)
    base_res = witness_residuals([np.asarray(rlx_crest)], witnesses, TR)
    ours_res = witness_residuals(crest, witnesses, TR)
    print(f'{"temoin":30s} {"pts":>5s} {"med signee":>11s} {"med |dv|":>9s} '
          f'{"viol%":>6s}   {"rlx |dv|":>9s} {"rlx viol%":>9s}')
    for cn in witnesses:
        a, b = ours_res.get(cn), base_res.get(cn)
        if a is None:
            print(f'{cn[:30]:30s}   — hors champ ou trace sans recouvrement')
            continue
        rb = f'{b[2]:9.1f} {b[3]:9.1f}' if b else f'{"—":>9s} {"—":>9s}'
        print(f'{cn[:30]:30s} {a[0]:5d} {a[1]:+11.1f} {a[2]:9.1f} {a[3]:6.1f}   {rb}')

    if args.sweep:
        print('\nbalayage d echelle (mediane |dv| cumulee sur les temoins):')
        best = (None, 1e9)
        for k in np.arange(0.75, 1.351, 0.05):
            ck = build_crest(common.get_cam(R), strokes, az_p, d_p, k=float(k))
            rr = witness_residuals(ck, witnesses, TR)
            vals = [v[2] for v in rr.values() if v]
            if not vals:
                continue
            m = float(np.median(vals))
            bar = '#' * int(m / 2)
            print(f'   k={k:4.2f}  med {m:6.1f} px  {bar}')
            if m < best[1]:
                best = (float(k), m)
        print(f'   -> minimum a k={best[0]:.2f} '
              f'({"la profondeur rlx est CONFIRMEE par les temoins" if abs(best[0]-1)<=0.05 else "correction mesuree: x" + format(best[0], ".2f")})')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    edges = build_mesh(common.get_cam(R), crest, slope_every=args.slope_every,
                       contour_step=args.contour_step, slope=args.slope)
    mesh = json.load(open(MESH_PATH))
    old = f'{M} (rlx)'
    # la couleur du mesh EXISTANT d abord: a la re-application, le (rlx) a
    # deja ete remplace et le repli sur le defaut peignait tout en cyan —
    # Mountain, Waffles et Ridge ont fini indiscernables ("mount mountain
    # est rendu ou?")
    color = (mesh.get(M, {}).get('color')
             or mesh.get(old, {}).get('color', '#22d3ee'))
    if old in mesh:
        del mesh[old]
        print(f'\n"{old}" retire (remplace par le mesh dense, meme couleur)')
    mesh[M] = {'color': color, 'world_edges': edges}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'APPLIED: "{M}" ({len(edges)} aretes)')


if __name__ == '__main__':
    main()
