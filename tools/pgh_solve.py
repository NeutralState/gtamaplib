#!/usr/bin/env python3
"""pgh_solve.py — la zone Port Gellhorn ancree sur ses cams LEAK. [PGH-BA-V1]

Diagnostic qui declenche l'outil (2026-07-30): apres l'arbitrage des poses,
les deux cams de la zone issues du LEAK — Motel et Pool, dont la pose est
EXACTE par construction — affichent 192' et 528' de residu. Ce ne sont donc
pas elles qui ont tort: ce sont les objets et les autres poses. Et une
simple re-triangulation ne suffit pas (192 -> 185, 528 -> 505): les poses
de la zone sont mutuellement incoherentes.

Solve joint, meme doctrine que le solve d'Ambrosia:
  * FIGEES   : les cams leak (verite terrain) + les cams exterieures
               ancrees ailleurs (Chase, Ambrosia 04...) qui servent de
               temoins independants
  * LIBRES   : les poses non-leak de la zone (xyz, yaw, pitch, roll, fov)
  * OBJETS   : re-triangules a CHAQUE evaluation depuis l'etat courant
               (jamais figes, jamais circulaires)
  * COUT     : somme des residus angulaires, perte de Cauchy pour que
               quelques mauvais clics ne pilotent pas le solve

Le juge n'est PAS le cout: c'est le residu sur les cams FIGEES, qui ne
participent pas au solve mais mesurent le resultat.

Usage: PYTHONPATH=. python3 tools/pgh_solve.py [--rounds 40] [--apply]
"""
import argparse
import collections
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
import common
from common import ray_ls_point

FROZEN = ['Motel', 'Pool', 'Chase (2) (A)', 'Chase (2) (B)',
          'Ambrosia 04 (Fires)']
FREE = ['Port Gellhorn 01 (Starlet Motel)', 'Starlet Motel',
        'Port Gellhorn Postcard (X)', 'Port Gellhorn 04 (Delights) (X)']
STEP = [3.0, 3.0, 1.5, 1.0, 1.0, 0.5, 1.0]      # x y z yaw pitch roll fov


class Solver:
    def __init__(self, px, cams, lms):
        self.px, self.cams, self.lms = px, cams, lms
        self.theta = {c: [cams[c]['xyz'][0], cams[c]['xyz'][1], cams[c]['xyz'][2],
                          cams[c]['ypr'][0], cams[c]['ypr'][1], cams[c]['ypr'][2],
                          cams[c]['fov'][0] or 60.0] for c in FREE}
        # objets: tout landmark vu par >=2 cams du groupe (figees + libres)
        group = set(FROZEN) | set(FREE)
        obs = collections.defaultdict(list)
        for c in group:
            for lm, p in (px.get(c) or {}).items():
                if p is not None and not common.is_excluded_marking(c, lm):
                    obs[lm].append(c)
        self.obs = {lm: cs for lm, cs in obs.items() if len(cs) >= 2}

    def state(self, c):
        if c in self.theta:
            t = self.theta[c]
            return {'xyz': t[:3], 'ypr': t[3:6], 'fov': [t[6], None]}
        e = self.cams[c]
        return {'xyz': e['xyz'], 'ypr': e['ypr'], 'fov': e['fov']}

    def rays(self, lm):
        out = []
        for c in self.obs[lm]:
            st = self.state(c)
            cam = common.get_cam(c, st)          # gotcha #5
            d = np.asarray(cam.get_pixel_direction(self.px[c][lm]), float)
            out.append((c, np.asarray(st['xyz'], float), d / np.linalg.norm(d)))
        return out

    def points(self):
        pts = {}
        for lm in self.obs:
            r = self.rays(lm)
            if len(r) < 2:
                continue
            try:
                P = np.asarray(ray_ls_point([(o, d) for _, o, d in r]), float)
            except Exception:
                continue
            if not (np.all(np.isfinite(P)) and abs(P[0]) < 17000):
                continue
            # GARDES: le point doit etre DEVANT chaque cam contributrice et
            # a plus de 2 m (une triangulation qui s'effondre sur la camera
            # produit des residus astronomiques et pilote le solve)
            ok = True
            for _, o, d in r:
                t = float(np.dot(P - o, d))
                if t < 2.0:
                    ok = False
                    break
            if ok:
                pts[lm] = P
        return pts

    def cost(self, judge_only=False):
        pts = self.points()
        tot, n = 0.0, 0
        judge = []
        for lm, P in pts.items():
            for c in self.obs[lm]:
                st = self.state(c)
                cam = common.get_cam(c, st)
                pr = cam.get_pixel([float(v) for v in P])
                if pr is None:
                    continue
                p = self.px[c][lm]
                dx = (pr[0] - p[0]) * cam.hfov / cam.w * 60.0
                dy = (pr[1] - p[1]) * cam.vfov / cam.h * 60.0
                e = math.hypot(dx, dy)
                if c in FROZEN:
                    # JUGE en METRES: l'arcmin ecrase tout sur les plans
                    # rapproches (1 m a 3 m de distance = 1200 arcmin)
                    dist = float(np.linalg.norm(P - np.asarray(st['xyz'], float)))
                    judge.append(math.radians(e / 60.0) * dist)
                if c in self.theta or c in FROZEN:
                    tot += math.log1p((e / 8.0) ** 2)   # Cauchy
                    n += 1
        j = float(np.median(judge)) if judge else float('nan')
        return (j if judge_only else tot / max(1, n)), j

    def descend(self, rounds):
        best, j0 = self.cost()
        print(f'depart: cout {best:.4f}   JUGE (cams figees) {j0:.2f} m (mediane)')
        step = list(STEP)
        for r in range(rounds):
            improved = False
            for c in FREE:
                for i in range(7):
                    for s in (step[i], -step[i]):
                        old = self.theta[c][i]
                        self.theta[c][i] = old + s
                        v, _ = self.cost()
                        if v < best - 1e-9:
                            best = v
                            improved = True
                        else:
                            self.theta[c][i] = old
            if not improved:
                step = [s * 0.5 for s in step]
                if max(step) < 0.02:
                    break
            if r % 5 == 0:
                _, j = self.cost()
                print(f'  round {r:3d}: cout {best:.4f}   juge {j:.2f} m')
        _, j = self.cost()
        print(f'fin: cout {best:.4f}   JUGE {j:.2f} m')
        return j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rounds', type=int, default=40)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))

    sv = Solver(px, cams, lms)
    print(f'{len(sv.obs)} objets, {len(FREE)} poses libres, {len(FROZEN)} figees\n')
    j_before = sv.cost(judge_only=True)[0] if False else sv.cost()[1]
    j_after = sv.descend(args.rounds)

    print('\nposes resolues:')
    for c in FREE:
        t = sv.theta[c]
        o = cams[c]
        print(f'  {c[:36]:36s} xyz ({t[0]:8.1f},{t[1]:8.1f},{t[2]:6.1f}) '
              f'ypr ({t[3]:7.2f},{t[4]:6.2f},{t[5]:5.2f}) fov {t[6]:5.1f}')
        print(f'  {"":36s} bouge de {math.dist(t[:3], o["xyz"]):.1f} m, '
              f'yaw {t[3] - o["ypr"][0]:+.2f}')
    print(f'\nJUGE (cams LEAK + temoins exterieurs, hors solve): '
          f'{j_before:.2f} -> {j_after:.2f} m (mediane)')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    pts = sv.points()
    for c in FREE:
        t = sv.theta[c]
        e = cams[c]
        e['xyz'] = [round(v, 3) for v in t[:3]]
        e['ypr'] = [round(v, 3) for v in t[3:6]]
        e['fov'] = [round(t[6], 3), e['fov'][1]]
        e['note'] = ('pose PGH-BA-V1 (2026-07-30): solve joint de la zone avec les cams '
                     'LEAK (Motel, Pool) et les temoins exterieurs (Chase, Ambrosia 04) '
                     f'FIGES; juge (metres medians sur les figees) {j_before:.2f} -> {j_after:.2f} m.')
    n = 0
    for lm, P in pts.items():
        ent = lms.get(lm) if isinstance(lms.get(lm), dict) else {}
        ent.update({'xyz': [round(float(v), 2) for v in P],
                    'source_cameras': sv.obs[lm],
                    'method': f'PGH-BA-V1: solve joint zone Port Gellhorn '
                              f'({len(sv.obs[lm])} cams, leak figees)'})
        lms[lm] = ent
        n += 1
    for path, data in ((os.path.join(REPO, 'gtamapdata', 'cameras.json'), cams),
                       (os.path.join(REPO, 'gtamapdata', 'landmarks.json'), lms)):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=1, ensure_ascii=True)
        os.replace(tmp, path)
    print(f'\nAPPLIED: {len(FREE)} poses + {n} objets.')


if __name__ == '__main__':
    main()
