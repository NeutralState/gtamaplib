#!/usr/bin/env python3
"""gen_stadium_portique.py — portique sud du toit retractable du stade (V16 2691, region 9 = rail sud). [STADIUM-PORTIQUE-V1 2026-10-03]

Le rail sud V16 (region 9: x -1560 -> -1486, largeur 7 m) se prolonge en realite ~55 m plus a l'est sur un portique blanc
(Street (Jason) recalee: barre de x <= -1476 (cachee a gauche par un panneau) a -1430, jambes obliques).
Mesures Street (Jason) (cam a ~440 m): dessus de la barre 41.7 m, dessous 37.1 m (axe y 982); jambes a x ~-1474 et ~-1444,
la jambe est s'evase vers l'est (pied ~-1436 a 29 m visible). C'est sur ce portique que se tient Jason 05.
Plan = axe du rail sud V16 prolonge (direction du rail), largeur V16 (7 m). Profondeur N-S: une seule vue -> axe V16.
Usage: PYTHONPATH=. python3 tools/gen_stadium_portique.py [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import v16_resect as RR

A0 = np.array([-1560.5, 984.4]); B0 = np.array([-1486.4, 982.0])      # axe du rail sud V16 (milieux des petits cotes)
U = (B0 - A0) / np.linalg.norm(B0 - A0); N = np.array([-U[1], U[0]]); HW = 3.6
# [PORTIQUE-V2] decalage N-S: Street (Jason) ne fixe pas la profondeur; Jason 05 (tours, independant) se tient a y ~998-1003
# -> axe decale de +16 m vers le nord (V16 locale = dessin communautaire d'apres Street (Lucia) (N), pas la leak)
SHIFT = 16.0
A = A0 + N * SHIFT
# pixels LUS dans Street (Jason) (1920x1080): barre (u, v_dessus, v_dessous), piles (u_ouest, u_est) a v 685 (haut) et 718 (bas visible)
BAR_U = (225, 394); BAR_V = (668.0, 685.0)
PILES = [((220, 238), (220, 230)), ((340, 382), (340, 363))]


def _street_cam():
    import common
    return common.get_cam('Street (Jason)')


def _hit(cm, u, v):
    """rayon du pixel (u,v) de Street (Jason) coupe par le plan vertical de l'axe decale -> (x, z)."""
    o = np.array(cm.xyz); d = np.array(cm.get_pixel_direction((u, v)), float)
    t = ((A - o[:2]) @ N) / (d[:2] @ N); q = o + t * d
    return float(q[0]), float(q[2])


_cm = _street_cam()
X_END = _hit(_cm, BAR_U[1], BAR_V[0])[0]
Z_TOP = _hit(_cm, 300, BAR_V[0])[1]; Z_BOT = _hit(_cm, 300, BAR_V[1])[1]
# piles: bords lus a v 685 (haut) et v 718 (bas visible, ~29 m); en dessous (cache par les arbres) prolongees verticalement
def _legs():
    out = []
    for (ua, ub), (ga, gb) in PILES:
        (xa, za), (xb, _) = _hit(_cm, ua, 685), _hit(_cm, ub, 685)
        (xga, zg), (xgb, _) = _hit(_cm, ga, 718), _hit(_cm, gb, 718)
        out.append(((xa, xb), (xga, xgb)))        # pas d'extrapolation: sous le bas visible (z~29) la pile est prolongee droite
    return out
LEGS = _legs()


def P(x, w, z):
    """point a l'abscisse x (le long de l'axe), decale de w (m) perpendiculairement, a l'altitude z."""
    s = (x - A[0]) / U[0]; q = A + U * s + N * w
    return [round(float(q[0]), 2), round(float(q[1]), 2), round(float(z), 2)]


def build():
    E = []; L = lambda a, b: E.append([a, b])
    xs = list(np.arange(A[0], X_END, 8.0)) + [X_END]
    for w in (-HW, HW):
        for z in (Z_BOT, Z_TOP, Z_TOP + 0.5):
            for a, b in zip(xs[:-1], xs[1:]): L(P(a, w, z), P(b, w, z))
    for x in xs:
        a, b, c, d = P(x, -HW, Z_BOT), P(x, HW, Z_BOT), P(x, HW, Z_TOP), P(x, -HW, Z_TOP)
        L(a, b); L(b, c); L(c, d); L(d, a)
    for (xa, xb), (ga, gb) in LEGS:
        for w0, w1 in ((-HW + 0.4, -HW + 2.2), (HW - 2.2, HW - 0.4)):          # une pile sous chaque bord de la barre
            g = RR.ground(*P((ga + gb) / 2, (w0 + w1) / 2, 0)[:2])
            zm = _hit(_cm, 340, 718)[1]
            top = [P(xa, w0, Z_BOT), P(xb, w0, Z_BOT), P(xb, w1, Z_BOT), P(xa, w1, Z_BOT)]
            mid = [P(ga, w0, zm), P(gb, w0, zm), P(gb, w1, zm), P(ga, w1, zm)]
            bot = [P(ga, w0, g), P(gb, w0, g), P(gb, w1, g), P(ga, w1, g)]
            for i in range(4): L(top[i], mid[i]); L(mid[i], bot[i]); L(bot[i], bot[(i + 1) % 4]); L(mid[i], mid[(i + 1) % 4])
            for f in (0.33, 0.66):                                                # cerclages
                ring = [[t + (b - t) * f for t, b in zip(top[i], bot[i])] for i in range(4)]
                for i in range(4): L([round(v, 2) for v in ring[i]], [round(v, 2) for v in ring[(i + 1) % 4]])
        g = RR.ground(*P((ga + gb) / 2, 0, 0)[:2])
        L(P((ga + gb) / 2, -HW + 1.3, g + 14), P((ga + gb) / 2, HW - 1.3, g + 14))   # entretoise
    return {'Stadium Roof Portique (South)': {'color': '#f8fafc', 'world_edges': E, '_credit': 'Alexandre Leblanc (V16) + Claude Opus 5.5',
            'note': 'STADIUM-PORTIQUE-V2 2026-10-03: rail sud du toit retractable (V16 2691 region 9) prolonge sur un portique jusqu a x=%.0f; '
                    'geometrie = pixels LUS dans Street (Jason) recalee (barre, piles) coupes par le plan vertical de l axe; axe decale de +%.0f m au nord '
                    'du trace V16 (position N-S donnee par Jason 05, qui se tient dessus: tours independantes). Dessus %.1f m, dessous %.1f m (+-2 m). '
                    'Largeur N-S des piles ESTIMEE. Voir tools/gen_stadium_portique.py' % (X_END, SHIFT, Z_TOP, Z_BOT)}}


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print(k, len(v['world_edges']))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = os.path.join(ROOT, 'gtamapdata', 'building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_portique_1003')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
