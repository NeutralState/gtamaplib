#!/usr/bin/env python3
"""gen_rlx_requests.py — meshes demandes par rlx (2026-10-04): Miami Marine Stadium (Gloriana Key) et tour de controle du VCIA.

Consigne d'Alexandre: « base-toi sur l'empreinte et les dimensions et apparences IRL ».
- Marine Stadium: plan = V16 2974 (regions v16_tiers: bandeau arriere 0/1, grandes plaques du toit plisse, rangees de gradins).
  IRL (Miami Marine Stadium, 1963): tribune face au bassin, toit en plaques plissees de beton en porte-a-faux; dimensions
  ESTIMEES IRL: gradins de 2 m (bord de l'eau) a 13 m (haut), toit 17 m (bord avant) -> 21 m (arriere), plis +-1.2 m.
- Tour VCIA (FAA Miami ATCT): plan = V16 2045 (batiment de base en croix) + 2139 (octogone = cabine vue de haut);
  sommet MESURE = landmark 'FAA Miami ATCT (MIA)' 97.8 m (4 cams). Fut, cabine vitree et toit ESTIMES IRL (tour de ~99 m,
  cabine ~83-92 m); base 15 m ESTIMEE.
Usage: PYTHONPATH=. python3 tools/gen_rlx_requests.py [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import v16_resect as RR, v16_tiers as VT
r2 = lambda v: [round(float(a), 2) for a in v]


def ringz(E, P, z):
    for i in range(len(P)): E.append([r2([*P[i], z]), r2([*P[(i + 1) % len(P)], z])])


def marine_stadium():
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    E = []; L = lambda a, b: E.append([r2(a), r2(b)])
    F = {f['id']: f for f in json.load(open(os.path.join(ROOT, 'gtamapdata', 'v16_footprints.json')))['polygons']}
    O = np.array(F[2974]['ring']); c = O.mean(0)
    u = np.linalg.svd(O - c)[2][0]; n = np.array([-u[1], u[0]])
    # avant = cote de l'eau (bassin): teste la V16 a 40 m de part et d'autre
    V = np.asarray(Image.open(os.path.join(ROOT, 'maps', 'yanis,16svg.png')).convert('RGB').crop((16991 + int(c[0]) - 80, 11008 - int(c[1]) - 80, 16991 + int(c[0]) + 80, 11008 - int(c[1]) + 80))).astype(int)
    isw = lambda q: (lambda px: px[2] > px[0] + 40)(V[int(80 - (q[1] - int(c[1]))), int(80 + (q[0] - int(c[0])))])
    if not isw(c + n * 55) and isw(c - n * 55): n = -n                    # n pointe vers l'eau (avant)
    s = (O - c) @ u; t = (O - c) @ n; s0, s1 = s.min(), s.max(); tb, tf = t.min(), t.max()   # tb = arriere, tf = avant
    P = lambda a, b, z: [*(c + u * a + n * b), z]
    g = 1.5; NF = 8                                                          # 8 plis (IRL)
    # gradins: rake de 2 m (avant, cote eau) a 13 m (arriere), 12 rangees
    for k in range(13):
        b = tf - (tf - tb) * k / 12.0; z = 2.0 + 11.0 * k / 12.0
        L(P(s0, b, z), P(s1, b, z))
        if k: L(P(s0, b, z - 11.0 / 12), P(s0, b, z)); L(P(s1, b, z - 11.0 / 12), P(s1, b, z))
    for a in np.linspace(s0, s1, 7): L(P(a, tf, 2.0), P(a, tb, 13.0))     # escaliers
    # toit en plaques plissees en porte-a-faux: plis le long de la profondeur, aretes alternees (faite/noue)
    za = lambda b: 17.0 + 4.0 * (tf - b) / (tf - tb)                       # 17 m a l'avant -> 21 m a l'arriere
    xs = np.linspace(s0, s1, 2 * NF + 1)
    for k, a in enumerate(xs):
        dz = 1.2 if k % 2 else -1.2
        L(P(a, tb, za(tb) + dz), P(a, tf + 4.0, za(tf + 4.0) + dz))       # arete du pli (deborde de 4 m devant)
        if k:
            a0 = xs[k - 1]; dz0 = 1.2 if (k - 1) % 2 else -1.2
            for b in (tb, tf + 4.0): L(P(a0, b, za(b) + dz0), P(a, b, za(b) + dz))   # zigzag avant/arriere
    # mur arriere + poteaux du porte-a-faux
    for z in (g, 13.0, za(tb) - 1.2): L(P(s0, tb, z), P(s1, tb, z))
    for a in np.linspace(s0, s1, NF + 1): L(P(a, tb, g), P(a, tb, za(tb) + 1.2)); L(P(a, tb + 3.0, g), P(a, tb + 3.0, 13.0))
    for a in (s0, s1): L(P(a, tb, g), P(a, tf, g)); L(P(a, tf, g), P(a, tf, 2.0))
    L(P(s0, tf, 2.0), P(s1, tf, 2.0)); L(P(s0, tf, g), P(s1, tf, g))
    return {'Miami Marine Stadium (Gloriana Key)': {'color': '#f1f5f9', 'world_edges': E, '_credit': 'Alexandre Leblanc (V16) + Claude Opus 5.5 (demande rlx)',
            'note': 'RLX-REQ 2026-10-04: emprise = rectangle oriente de V16 2974, tribune face au bassin (eau V16); gradins 2->13 m (12 rangees), '
                    'toit a 8 plaques plissees en porte-a-faux 17->21 m (+-1.2 m), mur arriere: dimensions/aspect ESTIMES IRL (Miami Marine Stadium), '
                    'aucune image du jeu. Voir tools/gen_rlx_requests.py'}}


def VT_area(P):
    x, y = P[:, 0], P[:, 1]; return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def vcia_tower():
    E = []; F = {f['id']: f for f in json.load(open(os.path.join(ROOT, 'gtamapdata', 'v16_footprints.json')))['polygons']}
    B = np.array(F[2045]['ring']); Oc = np.array(F[2139]['ring']); g = RR.ground(*B.mean(0)); zb = g + 15.0
    ringz(E, B, g); ringz(E, B, zb); ringz(E, B, zb + 1.0)
    for p in B[::2]: E.append([r2([*p, g]), r2([*p, zb + 1.0])])
    c = Oc.mean(0); shaft = c + (Oc - c) * 0.40; neck = c + (Oc - c) * 0.62
    for z in np.arange(zb, 78.0, 9.0): ringz(E, shaft, z)
    ringz(E, shaft, 78.0)
    for p in shaft: E.append([r2([*p, zb]), r2([*p, 78.0])])
    for k in range(len(Oc)):                                              # evasement sous la cabine 78 -> 82
        E.append([r2([*shaft[k], 78.0]), r2([*neck[k], 81.0])]); E.append([r2([*neck[k], 81.0]), r2([*Oc[k], 83.0])])
    ringz(E, neck, 81.0)
    cab_top = c + (Oc - c) * 1.06                                         # vitrage incline vers l'exterieur
    ringz(E, Oc, 83.0); ringz(E, cab_top, 91.0); ringz(E, cab_top, 92.5)
    for k in range(len(Oc)): E.append([r2([*Oc[k], 83.0]), r2([*cab_top[k], 91.0])])
    L = json.load(open(os.path.join(ROOT, 'gtamapdata', 'landmarks.json')))['FAA Miami ATCT (MIA)']['xyz']
    E.append([r2([L[0], L[1], 92.5]), r2(L)])                            # mat/antenne au sommet mesure
    return {'VCIA Air Traffic Control Tower': {'color': '#e5e7eb', 'world_edges': E, '_credit': 'Alexandre Leblanc (V16 + landmarks) + Claude Opus 5.5 (demande rlx)',
            'note': 'RLX-REQ 2026-10-04: base = V16 2045 (15 m ESTIME), cabine = octogone V16 2139 (83-92.5 m), fut ESTIME IRL; '
                    'sommet 97.8 m MESURE (LM FAA Miami ATCT (MIA), 4 cams). Voir tools/gen_rlx_requests.py'}}


def schlott():
    """Schlott Construction (Port Gellhorn, pres du Diner / Hank's Waffle): cour cloturee = V16 1214. Mur d'enceinte + panneaux
    'SCHLOTT CONSTRUCTION' vus dans Diner (SW)/(S): coins du panneau = LMs '18635 SW 105th Ave (CE)/(CW)' (dessus 18.0-18.1 m, sol 15.6 m
    -> 2.5 m MESURE); facades basses de la cour 3.5 m LUES dans Diner (S); conteneurs ESTIMES."""
    E = []; L = lambda a, b: E.append([r2(a), r2(b)])
    F = {f['id']: f for f in json.load(open(os.path.join(ROOT, 'gtamapdata', 'v16_footprints.json')))['polygons']}
    O = np.array(F[1214]['ring']); g = RR.ground(*O.mean(0)); zw = g + 3.5
    ringz(E, O, g); ringz(E, O, zw)
    for p in O: L([*p, g], [*p, zw])
    c = O.mean(0); u = np.linalg.svd(O - c)[2][0]; n = np.array([-u[1], u[0]])
    if (np.array([-6191.1, 4481.2]) - c) @ n < 0: n = -n                       # n vers la facade a enseigne (cote route)
    s = (O - c) @ u; t = (O - c) @ n; s0, s1, t0, t1 = s.min(), s.max(), t.min(), t.max()
    P = lambda a, b, z: [*(c + u * a + n * b), z]
    LM = json.load(open(os.path.join(ROOT, 'gtamapdata', 'landmarks.json')))
    A, B = np.array(LM['18635 SW 105th Ave (CE)']['xyz']), np.array(LM['18635 SW 105th Ave (CW)']['xyz'])
    for z in (g + 0.8, A[2]): L([A[0], A[1], z], [B[0], B[1], z])            # panneau SCHLOTT (mesure)
    for q in (A, B): L([q[0], q[1], g], [q[0], q[1], q[2]])
    for k in range(3):
        a = s1 - 4 - k * 7.0
        Q = [P(a - 6.0, t1 - 4.5, g + 2.6), P(a, t1 - 4.5, g + 2.6), P(a, t1 - 2.1, g + 2.6), P(a - 6.0, t1 - 2.1, g + 2.6)]
        for q in range(4): L(Q[q], Q[(q + 1) % 4]); L([Q[q][0], Q[q][1], g], Q[q])
    return {'Schlott Construction (Port Gellhorn)': {'color': '#fca5a5', 'world_edges': E, '_credit': 'Alexandre Leblanc (V16 + landmarks) + Claude Opus 5.5 (demande rlx)',
            'note': 'RLX-REQ 2026-10-04: cour = V16 1214, facades 3.5 m (Diner (S)) et panneau SCHLOTT MESURE (LMs 18635 SW 105th Ave CE/CW); '
                    'conteneurs ESTIMES. Voir tools/gen_rlx_requests.py'}}


def build():
    out = {}; out.update(marine_stadium()); out.update(vcia_tower()); out.update(schlott()); return out


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print(k, len(v['world_edges']))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = os.path.join(ROOT, 'gtamapdata', 'building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_rlxreq_1004')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
