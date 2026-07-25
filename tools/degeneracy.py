#!/usr/bin/env python3
"""degeneracy.py — ce que les donnees NE PEUVENT PAS dire. [DEGEN-V1]

Le bounty #23 a coute 14 mois, et sa cle tenait en une phrase que rlx a
fini par trouver a la main: "around 25 m north per meter of elevation".
C'est une DIRECTION DE DEGENERESCENCE: un deplacement du monde que le cout
ne voit presque pas. Trouver ces directions a la main prend des mois; les
calculer prend quelques secondes.

Methode: au minimum du cout joint ancre, on calcule la HESSIENNE exacte
(differences centrees sur les 28 parametres = 4 cams x xyz/ypr/fov), on la
preconditionne par sa diagonale (sinon on compare des metres a des degres),
et on la diagonalise. Les vecteurs propres de plus petite valeur propre
SONT les degenerescences. On les traduit ensuite en phrase physique: on
avance le long du mode jusqu'a +2 de cout (notre convention de sigma) et
on regarde comment le monde bouge — translation du nuage de landmarks,
altitude, echelle, et les couplages entre axes.

Sortie: la liste des modes du plus mou au plus raide, chacun avec sa
raideur, son amplitude a +2 de cout, et sa lecture physique.

Usage: PYTHONPATH=. python3 tools/degeneracy.py [--modes 6] [--polish 25]
"""
import argparse
import importlib.util
import json
import math
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np

spec = importlib.util.spec_from_file_location('aj', os.path.join(THIS, 'ambrosia_joint.py'))
aj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aj)

PNAMES = ['x', 'y', 'z', 'yaw', 'pitch', 'roll', 'fov']
STEP = [0.5, 0.5, 0.5, 0.02, 0.02, 0.02, 0.02]      # pas des differences finies


def theta_get(sv):
    return np.array([v for c in aj.AMB for v in sv.theta[c]], float)


def theta_set(sv, vec):
    for i, c in enumerate(aj.AMB):
        sv.theta[c] = list(vec[i * 7:(i + 1) * 7])


def world_cloud(sv):
    """Nuage des landmarks de zone re-triangules a l'etat courant."""
    _, det = sv.cost(collect_detail=True)
    return {lm: P for lm, (P, e) in det.items() if not lm.startswith('_')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modes', type=int, default=6)
    ap.add_argument('--polish', type=int, default=25)
    ap.add_argument('--dcost', type=float, default=2.0)
    args = ap.parse_args()

    px, lms, cams = aj.load()
    zone, anchors, ext = aj.collect(px, lms, cams, use_brator=True, no_kalaga=False)
    sv = aj.Solver(zone, anchors, ext, lms, cams, init='ours')
    _, d0 = sv.cost(collect_detail=True)
    bad = [lm for lm, (P, e) in d0.items() if e is not None and e > 90.0]
    for lm in bad:
        zone.pop(lm, None)
    sv = aj.Solver(zone, anchors, ext, lms, cams, init='ours')
    if args.polish:
        sv.descend(rounds=args.polish, verbose=False)
    th0 = theta_get(sv)
    f0 = sv.cost()
    print(f'{len(zone)} LMs de zone, {len(anchors)} ancres, {len(bad)} en quarantaine')
    print(f'cout au minimum: {f0:.3f}\n')

    def f(vec):
        theta_set(sv, vec)
        v = sv.cost()
        theta_set(sv, th0)
        return v

    # ── hessienne exacte, differences centrees ──────────────────────────
    n = len(th0)
    h = np.array(STEP * len(aj.AMB), float)
    H = np.zeros((n, n))
    fp = np.zeros(n)
    fm = np.zeros(n)
    for i in range(n):
        e = np.zeros(n); e[i] = h[i]
        fp[i] = f(th0 + e); fm[i] = f(th0 - e)
        H[i, i] = (fp[i] - 2 * f0 + fm[i]) / (h[i] ** 2)
    for i in range(n):
        for j in range(i + 1, n):
            ei = np.zeros(n); ei[i] = h[i]
            ej = np.zeros(n); ej[j] = h[j]
            v = (f(th0 + ei + ej) - f(th0 + ei - ej)
                 - f(th0 - ei + ej) + f(th0 - ei - ej)) / (4 * h[i] * h[j])
            H[i, j] = H[j, i] = v

    # preconditionnement par la diagonale (metres vs degres)
    d = np.abs(np.diag(H)).copy()
    d[d < 1e-12] = 1e-12
    S = 1.0 / np.sqrt(d)
    Hs = H * np.outer(S, S)
    Hs = 0.5 * (Hs + Hs.T)
    w, V = np.linalg.eigh(Hs)

    cloud0 = world_cloud(sv)
    keys = sorted(cloud0)
    C0 = np.array([cloud0[k] for k in keys])

    print('ENVELOPPE D INCERTITUDE PAR MODE (ce que le monde peut faire a +%.0f de cout)' % args.dcost)
    print('=' * 100)
    stiff_report = []
    for m in range(min(args.modes, n)):
        lam = w[m]
        vec = V[:, m] * S
        vec = vec / np.linalg.norm(vec)
        lo, hi = 0.0, 1.0
        for _ in range(60):
            if f(th0 + hi * vec) - f0 < args.dcost:
                hi *= 2.0
                if hi > 1e7:
                    break
            else:
                break
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            if f(th0 + mid * vec) - f0 < args.dcost:
                lo = mid
            else:
                hi = mid
        a = 0.5 * (lo + hi)
        theta_set(sv, th0 + a * vec)
        cloud1 = world_cloud(sv)
        theta_set(sv, th0)
        C1 = np.array([cloud1.get(k, cloud0[k]) for k in keys])
        dP = C1 - C0
        t = dP.mean(axis=0)
        spread = float(np.linalg.norm(dP - t, axis=1).mean())
        dth = a * vec
        kind = 'PLATE (degeneree)' if lam < 0.02 else ('molle' if lam < 0.2 else 'raide')
        print(f'\nmode {m}  raideur {lam:+.4f}  [{kind}]')
        # enveloppe par cam
        for i, c in enumerate(aj.AMB):
            seg = dth[i * 7:(i + 1) * 7]
            if np.abs(seg[:3]).max() < 0.3 and np.abs(seg[3:]).max() < 0.02:
                continue
            print(f'    {c:26s} dx{seg[0]:+7.1f} dy{seg[1]:+7.1f} dz{seg[2]:+6.1f} m   '
                  f'yaw{seg[3]:+6.2f} pitch{seg[4]:+6.2f} roll{seg[5]:+6.2f} fov{seg[6]:+6.2f}')
        bits = [f'le nuage se translate de ({t[0]:+.0f}, {t[1]:+.0f}, {t[2]:+.1f}) m']
        if spread > 1.0:
            bits.append(f'et se deforme de {spread:.0f} m')
        if abs(t[2]) > 0.3 and abs(t[1]) > 1.0:
            bits.append(f'-> {abs(t[1] / t[2]):.0f} m de nord par m d altitude')
        print(f'    monde: ' + ', '.join(bits))
        stiff_report.append((m, lam, a, np.abs(dth)))

    # synthese
    print('\n' + '=' * 100)
    print('SYNTHESE — incertitude JOINTE vs incertitude par parametre')
    env = np.zeros(n)
    for m, lam, a, ad in stiff_report:
        if lam < 0.2:
            env = np.maximum(env, ad)
    for i, c in enumerate(aj.AMB):
        seg = env[i * 7:(i + 1) * 7]
        print(f'  {c:26s} +-{seg[0]:5.1f} m x  +-{seg[1]:5.1f} m y  +-{seg[2]:4.1f} m z   '
              f'+-{seg[3]:5.2f} yaw  +-{seg[6]:5.2f} fov')
    print('\n  (les barres par parametre du rapport du bounty etaient CONDITIONNELLES:')
    print('   un parametre bouge, les 27 autres restent figes. Ci-dessus, tout bouge')
    print('   ensemble le long des modes mous — c est la vraie incertitude.)')


if __name__ == '__main__':
    main()
