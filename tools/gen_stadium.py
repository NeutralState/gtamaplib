#!/usr/bin/env python3
"""gen_stadium.py — stade a toit retractable (V16 2691) + portique nord. [STADIUM-V1 2026-10-03]

Complete tools/gen_stadium_portique.py (portique sud, MESURE). Demande d'Alexandre: le reste « base sur l'IRL, juste avoir de quoi
qui fait du sens ». Donc:
  - plan = regions V16 2691 (v16_tiers): bol = 0,4,5,1,6,7,10; panneaux du toit = 5, 1, 6; rails = 2/3 (nord), 8/9 (sud);
    tout decale de SHIFT (16 m au nord) comme le portique sud (position N-S donnee par Jason 05) -> plan coherent.
  - rails a la hauteur MESUREE du portique sud (dessus 43.1 / dessous 38.3 m), portique NORD = miroir du sud (memes x de barre et
    de piles) sur l'axe du rail nord V16: ESTIME (symetrie IRL loanDepot park: 2 rails, 2 portiques).
  - bol: mur exterieur 28 m (ESTIME IRL), toit en 3 panneaux voutes N-S: 43.6 m aux rails -> 57 m au faite (ESTIME IRL, fleche
    ~1/10 de la portee); poteaux sous les rails tous les ~20 m (ESTIME).
Usage: PYTHONPATH=.:tools python3 tools/gen_stadium.py [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import v16_resect as RR, v16_tiers as VT
import gen_stadium_portique as GP

SH = GP.N * GP.SHIFT
Z_WALL, Z_CREST = 28.0, 57.0
R = {r['id']: [list(np.array(p) + SH) for p in r['ring']] for r in VT.regions(2691)}
r2 = lambda v: [round(float(a), 2) for a in v]


def union(ids, K=4.0):
    A = np.vstack([np.array(R[i]) for i in ids]); x0, y0 = A.min(0) - 3; x1, y1 = A.max(0) + 3
    m = np.zeros((int((y1 - y0) * K) + 1, int((x1 - x0) * K) + 1), np.uint8)
    for i in ids: cv2.fillPoly(m, [np.array([[(x - x0) * K, (y1 - y) * K] for x, y in R[i]], np.int32)], 255)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    c = max(cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], key=cv2.contourArea)
    c = cv2.approxPolyDP(c, 0.8 * K, True).reshape(-1, 2)
    return np.array([[x0 + px / K, y1 - py / K] for px, py in c])


def build():
    E = []; L = lambda a, b: E.append([r2(a), r2(b)])
    # --- bol (mur exterieur)
    B = union([0, 4, 5, 1, 6, 7, 10]); g = RR.ground(*B.mean(0))
    for z in (g, 10.0, 20.0, Z_WALL):
        for i in range(len(B)): L([*B[i], z], [*B[(i + 1) % len(B)], z])
    for i in range(0, len(B), 2): L([*B[i], g], [*B[i], Z_WALL])
    # --- toit: 3 panneaux voutes (fleche le long de y, entre les rails)
    ys = [np.array(R[9])[:, 1].mean(), np.array(R[3])[:, 1].mean()]; yc, hy = np.mean(ys), (ys[1] - ys[0]) / 2
    zr = lambda y: GP.Z_TOP + 0.5 + (Z_CREST - GP.Z_TOP - 0.5) * max(0.0, 1 - ((y - yc) / hy) ** 2)
    for pid in (5, 1, 6):
        P = np.array(R[pid]); xa, xb = P[:, 0].min(), P[:, 0].max()
        yy = np.linspace(ys[0], ys[1], 17)
        for x in np.linspace(xa, xb, 6):
            for a, b in zip(yy[:-1], yy[1:]): L([x, a, zr(a)], [x, b, zr(b)])           # nervures
        for y in yy[::2]: L([xa, y, zr(y)], [xb, y, zr(y)])                              # pannes
    # --- rails sur toute la longueur (nord et sud) + poteaux
    for ids, ax0, ax1 in (((8, 9), None, None), ((2, 3), None, None)):
        P = np.vstack([np.array(R[i]) for i in ids]); yr = P[:, 1].mean(); xw = P[:, 0].min()
        for w in (-GP.HW, GP.HW):
            for z in (GP.Z_BOT, GP.Z_TOP):
                L([xw, yr + w, z], [GP.A[0], yr + w, z])
        for x in np.arange(xw + 10, GP.A[0], 20.0):
            for w in (-GP.HW + 1, GP.HW - 1):
                inside = cv2.pointPolygonTest(B.astype(np.float32).reshape(-1, 1, 2), (float(x), float(yr + w)), False) >= 0
                L([x, yr + w, Z_WALL if inside else RR.ground(x, yr + w)], [x, yr + w, GP.Z_BOT])
    out = {'Stadium (V16 2691)': {'color': '#e2e8f0', 'world_edges': E, '_credit': 'Alexandre Leblanc (V16) + Claude Opus 5.5',
           'note': 'STADIUM-V1 2026-10-03: plan V16 2691 (regions) decale de %.0f m au nord comme le portique sud (MESURE); rails a 43.1/38.3 m '
                   '(hauteur MESUREE du portique sud); mur du bol 28 m et toit voute 43.6 -> 57 m ESTIMES IRL (loanDepot park), demande '
                   'd Alexandre: « base sur l IRL, juste avoir de quoi qui fait du sens »' % GP.SHIFT}}
    # --- portique nord = miroir du sud sur l'axe du rail nord V16 (meme decalage)
    A3 = np.array([-1568.2, 1115.0]) + SH; B3 = np.array([-1482.2, 1112.2]) + SH
    U3 = (B3 - A3) / np.linalg.norm(B3 - A3); N3 = np.array([-U3[1], U3[0]])
    def P3(x, w, z):
        q = A3 + U3 * ((x - A3[0]) / U3[0]) + N3 * w; return [q[0], q[1], z]
    E = []; L = lambda a, b: E.append([r2(a), r2(b)])
    xs = list(np.arange(A3[0], GP.X_END, 8.0)) + [GP.X_END]
    for w in (-GP.HW, GP.HW):
        for z in (GP.Z_BOT, GP.Z_TOP, GP.Z_TOP + 0.5):
            for a, b in zip(xs[:-1], xs[1:]): L(P3(a, w, z), P3(b, w, z))
    for x in xs:
        c = [P3(x, -GP.HW, GP.Z_BOT), P3(x, GP.HW, GP.Z_BOT), P3(x, GP.HW, GP.Z_TOP), P3(x, -GP.HW, GP.Z_TOP)]
        for i in range(4): L(c[i], c[(i + 1) % 4])
    zm = GP._hit(GP._cm, 340, 718)[1]
    for (xa, xb), (ga, gb) in GP.LEGS:
        for w0, w1 in ((-GP.HW + 0.4, -GP.HW + 2.2), (GP.HW - 2.2, GP.HW - 0.4)):
            g = RR.ground(*P3((ga + gb) / 2, (w0 + w1) / 2, 0)[:2])
            top = [P3(xa, w0, GP.Z_BOT), P3(xb, w0, GP.Z_BOT), P3(xb, w1, GP.Z_BOT), P3(xa, w1, GP.Z_BOT)]
            mid = [P3(ga, w0, zm), P3(gb, w0, zm), P3(gb, w1, zm), P3(ga, w1, zm)]
            bot = [P3(ga, w0, g), P3(gb, w0, g), P3(gb, w1, g), P3(ga, w1, g)]
            for i in range(4): L(top[i], mid[i]); L(mid[i], bot[i]); L(mid[i], mid[(i + 1) % 4]); L(bot[i], bot[(i + 1) % 4])
    out['Stadium Roof Portique (North)'] = {'color': '#f8fafc', 'world_edges': E, '_credit': 'Alexandre Leblanc (V16) + Claude Opus 5.5',
        'note': 'STADIUM-V1 2026-10-03: portique nord = miroir du portique sud MESURE (meme barre, memes piles) sur l axe du rail nord V16 '
                '(region 3) decale de %.0f m: ESTIME (symetrie IRL loanDepot park)' % GP.SHIFT}
    return out


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print(k, len(v['world_edges']))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = os.path.join(ROOT, 'gtamapdata', 'building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_stadium_1003')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
