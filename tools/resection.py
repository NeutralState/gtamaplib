#!/usr/bin/env python3
"""resection.py — poser une camera sur nos ancres, avec les gardes. [RESECT-V2]

Pourquoi une V2 sans qu'il y ait eu de V1 outillee: la premiere resection du
projet (RESECTION-V1, Mount Kalaga 04) a ete faite a la main, elle etait
FAUSSE, et c'est la carte qui l'a refutee — la route y restait a distance
constante (rapport 1.05), ce qui aurait fait d'elle un mur perpendiculaire a
la vue au lieu d'une route qui fuit. Un residu faible ne prouve rien: avec
sept parametres libres et des ancres mal reparties, on peut faire coller
n'importe quoi.

D'ou les gardes, qui sont le vrai contenu de cet outil:

  * REPARTITION. On mesure l'etendue angulaire des ancres dans l'image et
    leur etalement en profondeur. Des ancres serrees dans un coin, ou toutes
    a la meme distance, ne contraignent pas la pose — et on le dit.
  * PERTE ROBUSTE. Cauchy sur les residus angulaires: quelques clics faux ne
    doivent pas piloter la pose.
  * LAISSES-DEHORS. Une fraction des ancres est tiree au sort et EXCLUE du
    solve, puis sert de juge. C'est la seule facon de distinguer une pose
    juste d'un surajustement.
  * REFUS. Si le juge est mauvais, l'outil ne propose rien.

Usage:
  PYTHONPATH=. python3 tools/resection.py --cam 'Port Gellhorn Postcard' \
      [--init 'Port Gellhorn Postcard (X)'] [--holdout 0.3] [--apply]
"""
import argparse
import json
import math
import os
import random
import sys
import tempfile

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np

STEP = [40.0, 40.0, 15.0, 4.0, 3.0, 1.5, 4.0]     # x y z yaw pitch roll hfov


class Resection:
    def __init__(self, cam, px, cams, lms, holdout, seed, proxy=None,
                 exclude=None):
        import common
        self.common = common
        self.cam = cam
        # Une camera non posee (xyz null) ne peut pas etre instanciee. On
        # construit donc l'objet a partir d'une camera PROXY de MEME TAILLE
        # et on lui impose entierement notre etat: la projection ne depend
        # que de xyz/ypr/fov et des dimensions, donc rien du proxy ne fuit.
        self.proxy = cam if cams[cam].get('xyz') else proxy
        if self.proxy is None:
            raise SystemExit(
                f'{cam} n a pas de pose de depart: donner --proxy avec une '
                'camera de meme taille (--init sert souvent de proxy)')
        if list(cams[self.proxy].get('size') or []) != list(cams[cam].get('size') or []):
            raise SystemExit(
                f'proxy "{self.proxy}" {cams[self.proxy].get("size")} et '
                f'"{cam}" {cams[cam].get("size")} n ont pas la meme taille')
        self.px = px
        self.cams = cams
        e = cams[cam]
        self.size = e.get('size') or [1920, 1080]
        # EXCLUSIONS. Certains "landmarks" ne sont pas des points
        # caracteristiques mais des echantillons arbitraires le long d'une
        # courbe (rive, contour de lac): rien ne garantit que "Bay (N)"
        # designe le meme point physique d'une frame a l'autre, et ils
        # dominent le solve parce qu'ils sont nombreux et lointains.
        drop = tuple(x.strip().lower() for x in (exclude or '').split(',') if x.strip())
        pts, skipped = [], 0
        for lm, p in px[cam].items():
            if p is None or not (isinstance(lms.get(lm), dict) and lms[lm].get('xyz')):
                continue
            if drop and any(d in lm.lower() for d in drop):
                skipped += 1
                continue
            pts.append((lm, np.asarray(lms[lm]['xyz'], float), p))
        self.skipped = skipped
        # JUGE STRATIFIE PAR DISTANCE. Un tirage au sort simple peut mettre
        # dans le juge uniquement des objets proches: la pose passe alors le
        # test tout en se trompant de 70 m sur les objets lointains, parce
        # qu'une erreur de focale se compense par une erreur de position et
        # que seule la profondeur revele l'echange. On prend donc le juge a
        # parts egales dans chaque tiers de distance.
        rnd = random.Random(seed)
        ctr = np.mean([Q for _, Q, _ in pts], axis=0) if pts else np.zeros(3)
        order = sorted(range(len(pts)),
                       key=lambda i: float(np.linalg.norm(pts[i][1] - ctr)))
        thirds = [order[i::3] for i in range(3)]
        n_out = max(3, int(round(holdout * len(pts))))
        hold_i = []
        for k in range(n_out):
            band = thirds[k % 3]
            if not band:
                continue
            hold_i.append(band.pop(rnd.randrange(len(band))))
        self.hold = [pts[i] for i in hold_i]
        self.fit = [pts[i] for i in range(len(pts)) if i not in set(hold_i)]

    def state(self, t):
        return {'xyz': list(t[:3]), 'ypr': list(t[3:6]),
                'fov': [t[6], None], 'size': self.size}

    def residuals(self, t, pts):
        cam = self.common.get_cam(self.proxy, self.state(t))  # gotcha #5
        out = []
        for lm, Q, p in pts:
            pr = cam.get_pixel([float(v) for v in Q])
            if pr is None:
                out.append((lm, 999.0, 9e9))
                continue
            dx = (pr[0] - p[0]) * cam.hfov / cam.w * 60.0
            dy = (pr[1] - p[1]) * cam.vfov / cam.h * 60.0
            a = math.hypot(dx, dy)
            d = float(np.linalg.norm(Q - np.asarray(t[:3], float)))
            out.append((lm, a, math.radians(a / 60.0) * d))
        return out

    def cost(self, t):
        r = self.residuals(t, self.fit)
        return sum(math.log1p((a / 6.0) ** 2) for _, a, _ in r) / max(1, len(r))

    def judge(self, t):
        r = self.residuals(t, self.hold)
        return (float(np.median([a for _, a, _ in r])),
                float(np.median([m for _, _, m in r])))

    def by_range(self, t, pts):
        """Residus par bande de distance: c'est la ou se voit l'echange
        focale/position, invisible sur une mediane globale."""
        r = self.residuals(t, pts)
        D = [float(np.linalg.norm(Q - np.asarray(t[:3], float))) for _, Q, _ in pts]
        out = []
        if not D:
            return out
        q1, q2 = np.percentile(D, [33, 66])
        for lab, sel in (('proche', lambda d: d <= q1),
                         ('moyen', lambda d: q1 < d <= q2),
                         ('loin', lambda d: d > q2)):
            k = [i for i, d in enumerate(D) if sel(d)]
            if k:
                out.append((lab, len(k),
                            float(np.median([D[i] for i in k])),
                            float(np.median([r[i][2] for i in k]))))
        return out

    def descend(self, t, rounds=120):
        best = self.cost(t)
        step = list(STEP)
        for _ in range(rounds):
            moved = False
            for i in range(7):
                for s in (step[i], -step[i]):
                    old = t[i]
                    t[i] = old + s
                    v = self.cost(t)
                    if v < best - 1e-10:
                        best, moved = v, True
                    else:
                        t[i] = old
            if not moved:
                step = [s * 0.5 for s in step]
                if max(step) < 0.005:
                    break
        return t, best


def spread(pts, o):
    """Repartition des ancres: etendue angulaire vue depuis o, et etalement
    des profondeurs. C'est ce qui fait qu'une pose est contrainte ou non."""
    D = np.array([np.linalg.norm(Q - o) for _, Q, _ in pts])
    dirs = np.array([(Q - o) / max(1e-9, np.linalg.norm(Q - o)) for _, Q, _ in pts])
    amax = 0.0
    for i in range(0, len(dirs), max(1, len(dirs) // 40)):
        for j in range(i + 1, len(dirs), max(1, len(dirs) // 40)):
            c = float(np.clip(dirs[i] @ dirs[j], -1, 1))
            amax = max(amax, math.degrees(math.acos(c)))
    return amax, float(D.min()), float(D.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cam', required=True)
    ap.add_argument('--init', help='camera dont on part (meme scene)')
    ap.add_argument('--proxy', help='camera de MEME TAILLE servant a '
                                    'instancier l objet (defaut: --init)')
    ap.add_argument('--exclude', help='motifs de noms a ecarter, separes par '
                                      'des virgules (ex: "Bay,Ocean,Lake")')
    ap.add_argument('--holdout', type=float, default=0.30)
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--max-judge', type=float, default=5.0,
                    help='METRES medians toleres sur les ancres laissees '
                         "dehors. En metres et pas en arcmin: c'est la lecon "
                         'de PGH-BA-V1 — sur une scene rapprochee l arcmin '
                         'ecrase tout (1 m a 3 m de distance = 1200 arcmin) '
                         'et classe une pose correcte comme catastrophique.')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    if args.cam not in cams:
        raise SystemExit(f'camera absente de cameras.json: {args.cam}')

    R = Resection(args.cam, px, cams, lms, args.holdout, args.seed,
                  proxy=args.proxy or args.init, exclude=args.exclude)
    n = len(R.fit) + len(R.hold)
    print(f'{args.cam}: {n} ancres 3D ({len(R.fit)} pour le solve, '
          f'{len(R.hold)} laissees DEHORS comme juge)'
          + (f'  [{R.skipped} ecartees par --exclude]' if R.skipped else ''))
    if len(R.fit) < 6:
        raise SystemExit('moins de 6 ancres pour le solve: resection impossible')

    if args.init and args.init in cams:
        e = cams[args.init]
        t = [e['xyz'][0], e['xyz'][1], e['xyz'][2],
             e['ypr'][0], e['ypr'][1], e['ypr'][2], e['fov'][0] or 60.0]
        print(f'depart: pose de "{args.init}"')
    else:
        A = np.array([Q for _, Q, _ in R.fit])
        c = A.mean(axis=0)
        t = [c[0], c[1], max(20.0, c[2] + 30.0), 0.0, 0.0, 0.0, 60.0]
        print('depart: barycentre des ancres, orientation nulle '
              '(donner --init accelere et fiabilise)')

    amax, dmin, dmax = spread(R.fit + R.hold, np.asarray(t[:3], float))
    print(f'repartition des ancres: etendue angulaire {amax:.1f} deg, '
          f'profondeurs {dmin:.0f}-{dmax:.0f} m (rapport {dmax / max(1, dmin):.2f})')
    if amax < 15:
        print('  ATTENTION: ancres serrees, la pose sera mal contrainte')
    if dmax / max(1.0, dmin) < 1.5:
        print('  ATTENTION: toutes les ancres a la meme distance, '
              'la position le long de l axe sera molle')

    j0 = R.judge(t)
    t, c = R.descend(t)
    # RELANCES: la descente par coordonnees se coince. On repart de la
    # solution avec des pas ranimes, plusieurs fois, et on garde le meilleur
    # JUGE — pas le meilleur cout, qui lui peut toujours etre ameliore en
    # surajustant les ancres du solve.
    best_t, best_j = list(t), R.judge(t)
    for k in range(4):
        t2, _ = R.descend([v + s * (0.5 - ((k * 7 + i) % 3) / 2.0)
                           for i, (v, s) in enumerate(zip(best_t, STEP))])
        j2 = R.judge(t2)
        if j2[1] < best_j[1]:
            best_t, best_j = list(t2), j2
    t, j1 = best_t, best_j
    c = R.cost(t)
    print(f'\ncout (ancres du solve): {c:.5f}')
    print(f'JUGE (ancres laissees dehors): {j0[0]:.1f}\' / {j0[1]:.2f} m'
          f'  ->  {j1[0]:.1f}\' / {j1[1]:.2f} m')
    print(f'\npose: xyz ({t[0]:.1f}, {t[1]:.1f}, {t[2]:.1f})  '
          f'ypr ({t[3]:.2f}, {t[4]:.2f}, {t[5]:.2f})  hfov {t[6]:.2f}')

    r = sorted(R.residuals(t, R.fit + R.hold), key=lambda x: -x[1])
    print('\nles 8 pires ancres:')
    for lm, a, m in r[:8]:
        print(f'   {lm[:40]:40s} {a:8.1f}\'  {m:8.2f} m')
    allr = np.array([a for _, a, _ in r])
    print(f'\nmediane sur les {len(allr)} ancres: {np.median(allr):.1f}\'')
    print('\nresidu par bande de distance (l echange focale/position s y voit):')
    for lab, k, dmed, mmed in R.by_range(t, R.fit + R.hold):
        print(f'   {lab:7s} {k:3d} ancres a {dmed:7.0f} m  ->  {mmed:7.2f} m d erreur')

    if j1[1] > args.max_judge:
        print(f'\nREFUS: juge {j1[1]:.2f} m au-dela du seuil '
              f'{args.max_judge:.2f} m. La pose n est pas proposee.')
        return
    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    e = cams[args.cam]
    e['xyz'] = [round(v, 3) for v in t[:3]]
    e['ypr'] = [round(v, 3) for v in t[3:6]]
    e['fov'] = [round(t[6], 3), None]
    e['note'] = (f'pose RESECT-V2: resection sur {len(R.fit)} ancres, '
                 f'juge {len(R.hold)} ancres laissees dehors '
                 f'{j0[0]:.1f} -> {j1[0]:.1f} arcmin ({j1[1]:.2f} m).')
    p = os.path.join(REPO, 'gtamapdata', 'cameras.json')
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(cams, f, indent=1, ensure_ascii=True)
    os.replace(tmp, p)
    print(f'\nAPPLIED: {args.cam}')


if __name__ == '__main__':
    main()
