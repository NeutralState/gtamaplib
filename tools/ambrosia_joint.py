#!/usr/bin/env python3
"""ambrosia_joint.py — le solve joint du bounty Ambrosia. [AMB-JOINT-V1]

Contexte (fil Discord bounty #23, 14 mois, ~4000 messages): rlx a resolu le
probleme relatif (cercles de camera autour de la Lollipop, aire des triangles
d'erreur), puis l'absolu par descente de coordonnees MANUELLE (tables de
console, une dimension a la fois) — 'least-squares-by-proxy as a long,
complicated detective story' (ses mots). Ce solveur fait la meme chose en
vraies moindres carrees jointes.

Design:
- Parametres libres: les 4 cams Ambrosia x (x, y, z, yaw, pitch, roll, hfov).
- LMs de ZONE (vus par >=2 cams du cluster): RE-TRIANGULES a chaque eval
  (ray_ls_point) avec, quand ils existent, les rayons EXTERNES de cams hors
  cluster a pose fixe (Mount Kalaga pour Daytona/Sebring WT, Keys Airplane
  pour le Wheelabrator = le monde 'brator' de rlx, Loading Zone pour WT
  Prison). Residu = angle rayon->point, arcmin, soft-l1.
- ANCRES SOLIDES (>=2 observateurs externes, jamais re-triangulees):
  FAA Miami ATCT, MIA North Terminal Tower, SSB (N)/(S) — reprojection pure.
- Audit anti-circularite fait en amont (lecon Infinity/Peacock).

Diagnostics rlx-corpus (rapportes, pas contraints en V1): hauteur du silo
(~45-48m attendu), verticalite des paires (B)/(top), z du sol de la zone.

Usage:
  PYTHONPATH=. python3 tools/ambrosia_joint.py [--rounds 60] [--no-brator]
  ... --init rlx     # initialise depuis la solution de rlx (2026-07-01)
  ... --apply        # ecrit les poses optimisees (dry-run par defaut)
"""
import argparse
import json
import math
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np
import common
from common import ray_ls_point

AMB = ['Ambrosia 01 (Bikers)', 'Ambrosia 02 (Panorama)',
       'Ambrosia 04 (Fires)', 'Ambrosia Postcard (X)']

# ancres solides: xyz fixe, jamais re-triangule (>=2 obs externes)
FIXED_ANCHORS = ['FAA Miami ATCT (MIA)', 'MIA North Terminal Tower',
                 'Sunshine Skyway Bridge (N)', 'Sunshine Skyway Bridge (S)']

# solution H de rlx (2026-07-25, bounty CLOS): candidat gagnant parmi 9,
# lu sur les barres d'info de ses PNG. A gagne le test de bassin contre
# notre solution dans NOTRE cout ancre (148.66 vs 156.62) et passe nos
# ancres absolues (FAA MIA 0.5', MIA N 0.8', SSB N 1.5'; seul SSB S a 17',
# et c'est le pilier qui depend de Chase 2, cam que rlx lui-meme suspecte).
# Il satisfait le pont en deplacant Fires de +444 m est et en resserrant
# son fov a 42.3 — pas en gardant la zone au sud.
RLX_H_POSES = {
    'Ambrosia 01 (Bikers)':    ((-2657.000, 4036.000, 20.265), (16.333,   0.300, 0.0), 36.100),
    'Ambrosia 02 (Panorama)':  ((-2415.000, 5340.000, 89.656), (160.757, -4.022, 0.0), 50.900),
    'Ambrosia 04 (Fires)':     ((-1015.000, 3232.000, 54.538), (96.915,  -1.710, 0.0), 42.300),
    'Ambrosia Postcard (X)':   ((-2676.000, 3974.000, 62.322), (148.598, -1.900, 0.0), 52.100),
}

# solution rlx du 2026-07-01 (fil Discord) pour --init rlx
RLX_POSES = {
    'Ambrosia 02 (Panorama)':  ((-2465.725, 5095.552, 79.289), (160.149, -4.146, 0.0), 53.506),
    'Ambrosia 04 (Fires)':     ((-1347.711, 3150.504, 49.382), (100.564, -2.302, 0.0), 53.221),
    'Ambrosia Postcard (X)':   ((-2712.948, 3814.308, 54.386), (147.179, -1.863, 0.0), 55.409),
    'Ambrosia 01 (Bikers)':    ((-2748.745, 3684.920, 9.0),    (11.87, 0.17, 0.0),     37.2),
}


def load():
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    return px, lms, cams


# 'Sebring Water Tower' = alias de 'Daytona Beach Water Tower' (pixels
# IDENTIQUES dans toutes les cams — c'est LA Lollipop du bounty, dedoublee
# dans nos donnees). On n'en garde qu'une dans le solve.
ALIAS_SKIP = {'Sebring Water Tower', 'Sebring Water Tower (B)'}


def collect(px, lms, cams, use_brator=True, no_kalaga=False):
    """LMs solvables: >=2 rayons au TOTAL (cluster + externes fixes).
    Un LM a 1 obs cluster + 1 rayon externe est triangulable et contraint la
    cam du cluster — c'est exactement la contrainte 'brator' de rlx."""
    amb_obs = {}      # lm -> [(cam, px)]
    for c in AMB:
        for lm, p in (px.get(c) or {}).items():
            if p is None or common.is_excluded_marking(c, lm) or lm in ALIAS_SKIP:
                continue
            amb_obs.setdefault(lm, []).append((c, p))
    anchors = {lm: obs for lm, obs in amb_obs.items()
               if lm in FIXED_ANCHORS and isinstance(lms.get(lm), dict) and lms[lm].get('xyz')}
    # rayons externes fixes pour TOUT LM observe par le cluster
    ext_rays = {}     # lm -> [(origin, dir)]
    for c, marks in px.items():
        if c in AMB or c not in cams:
            continue
        if no_kalaga and 'Mount Kalaga' in c:
            continue
        try:
            cam = common.get_cam(c)
            assert cam is not None
        except Exception:
            continue
        for lm in amb_obs:
            if lm in FIXED_ANCHORS:
                continue
            p = marks.get(lm)
            if p is None or common.is_excluded_marking(c, lm):
                continue
            if not use_brator and 'Wheelabrator' in lm:
                continue
            try:
                d = cam.get_pixel_direction(p)
            except Exception:
                continue
            if d is None:
                continue
            d = np.asarray(d, float)
            ext_rays.setdefault(lm, []).append((np.asarray(cam.xyz, float), d / np.linalg.norm(d)))
    zone = {lm: obs for lm, obs in amb_obs.items()
            if lm not in FIXED_ANCHORS
            and len(obs) + len(ext_rays.get(lm, [])) >= 2}
    return zone, anchors, ext_rays


class Solver:
    def __init__(self, zone, anchors, ext_rays, lms, cams, init='ours', use_corpus=False):
        self.zone, self.anchors, self.ext_rays = zone, anchors, ext_rays
        self.lms, self.cams_json = lms, cams
        self.use_corpus = use_corpus
        self.theta = {}
        for c in AMB:
            e = cams[c]
            if init == 'h' and c in RLX_H_POSES:
                (x, y, z), (yaw, pitch, roll), hfov = RLX_H_POSES[c]
            elif init == 'rlx' and c in RLX_POSES:
                (x, y, z), (yaw, pitch, roll), hfov = RLX_POSES[c]
            else:
                x, y, z = e['xyz']; yaw, pitch, roll = e['ypr']
                hfov = e['fov'][0] if e['fov'] and e['fov'][0] else 55.0
            self.theta[c] = [x, y, z, yaw, pitch, roll, hfov]
        self._cache = {}
        self._single_px = {}
        for (cn, ln) in [('Ambrosia Postcard (X)', 'Black Bison (1)'),
                         ('Ambrosia Postcard (X)', 'Black Bison (2)'),
                         ('Ambrosia Postcard (X)', 'Worker (Ambrosia) (B)'),
                         ('Ambrosia Postcard (X)', 'Worker (Ambrosia) (T)')]:
            px_all = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
            self._single_px[(cn, ln)] = (px_all.get(cn) or {}).get(ln)
        # bornes: xyz ±250m, yaw ±5, pitch ±3, roll ±1.5, hfov ±6
        self.bounds = {}
        for c in AMB:
            x, y, z, yaw, pitch, roll, hfov = self.theta[c]
            self.bounds[c] = [(x-250, x+250), (y-250, y+250), (max(0.5, z-40), z+40),
                              (yaw-5, yaw+5), (pitch-3, pitch+3), (roll-1.5, roll+1.5),
                              (hfov-6, hfov+6)]

    def cam(self, c):
        th = tuple(self.theta[c])
        if self._cache.get(c, (None,))[0] != th:
            x, y, z, yaw, pitch, roll, hfov = th
            state = {'xyz': [x, y, z], 'ypr': [yaw, pitch, roll], 'fov': [hfov, None]}
            self._cache[c] = (th, common.get_cam(c, state))
        return self._cache[c][1]

    def rays_for(self, lm):
        rays = []
        for c, p in self.zone[lm]:
            cam = self.cam(c)
            try:
                d = cam.get_pixel_direction(p)
            except Exception:
                d = None
            if d is None:
                return None
            d = np.asarray(d, float)
            rays.append((np.asarray(cam.xyz, float), d / np.linalg.norm(d)))
        rays += self.ext_rays.get(lm, [])
        return rays

    def _tri(self, lm):
        """Triangule un LM de zone avec les rayons courants (ou None)."""
        if lm not in self.zone:
            return None
        rays = self.rays_for(lm)
        if not rays or len(rays) < 2:
            return None
        try:
            P = np.asarray(ray_ls_point(rays), float)
        except Exception:
            return None
        return P if np.all(np.isfinite(P)) else None

    def _pair_depth_point(self, cam_name, lm_a, lm_b, true_len):
        """[corpus rlx] paire de pixels dans UNE cam + longueur connue ->
        position 3D du milieu (profondeur = L / separation angulaire)."""
        cam = self.cam(cam_name)
        px = json  # placeholder
        pa = self._single_px.get((cam_name, lm_a))
        pb = self._single_px.get((cam_name, lm_b))
        if pa is None or pb is None:
            return None
        try:
            da = np.asarray(cam.get_pixel_direction(pa), float)
            db = np.asarray(cam.get_pixel_direction(pb), float)
        except Exception:
            return None
        if da is None or db is None:
            return None
        da /= np.linalg.norm(da); db /= np.linalg.norm(db)
        ang = math.acos(float(np.clip(np.dot(da, db), -1, 1)))
        if ang < 1e-5:
            return None
        d = true_len / (2.0 * math.tan(ang / 2.0))
        mid = np.asarray(cam.xyz, float) + d * (da + db) / np.linalg.norm(da + db)
        return mid

    def corpus_cost(self, detail=None):
        """Contraintes du corpus rlx (fil Discord #23, config 2026-07-16):
        silo_ratio=3.2, bison_length=6.00, worker_height=1.80,
        bison colle au silo, worker au sol de la zone silo."""
        t = 0.0
        # silo: hauteur = ratio 3.2 x largeur (L-R), top a (L), base a (B)
        L = self._tri('1500 Sonora Ave (Silo) (L)')
        R = self._tri('1500 Sonora Ave (Silo) (R)')
        B = self._tri('1500 Sonora Ave (Silo) (B)')
        if L is not None and R is not None and B is not None:
            w = float(np.hypot(L[0] - R[0], L[1] - R[1]))
            h = float((L[2] + R[2]) / 2 - B[2])
            if w > 1:
                t += 2.0 * math.log1p(((h / w - 3.2) / 0.3) ** 2)
                if detail is not None:
                    detail['_silo_ratio'] = (np.array([w, h, h / w]), None)
        # bison (Postcard): longueur 6.00 -> profondeur -> le bison est PRES du silo
        bis = self._pair_depth_point('Ambrosia Postcard (X)',
                                     'Black Bison (1)', 'Black Bison (2)', 6.00)
        silo_base = B if B is not None else self._tri('1500 Sonora Ave (Silo) (N)')
        if bis is not None and silo_base is not None:
            dxy = float(np.hypot(bis[0] - silo_base[0], bis[1] - silo_base[1]))
            t += 2.0 * math.log1p((dxy / 25.0) ** 2)      # bison a <~25m du silo
            if detail is not None:
                detail['_bison'] = (bis, dxy)
        # worker (Postcard): hauteur 1.80 -> profondeur -> au sol pres du silo
        wk = self._pair_depth_point('Ambrosia Postcard (X)',
                                    'Worker (Ambrosia) (B)', 'Worker (Ambrosia) (T)', 1.80)
        if wk is not None and silo_base is not None:
            dxy = float(np.hypot(wk[0] - silo_base[0], wk[1] - silo_base[1]))
            t += 1.0 * math.log1p((dxy / 60.0) ** 2)
            if detail is not None:
                detail['_worker'] = (wk, dxy)
        return t

    def cost(self, collect_detail=False):
        tot = 0.0
        detail = {}
        # 1) zone: re-triangulation + residu angulaire par rayon
        for lm, obs in self.zone.items():
            rays = self.rays_for(lm)
            if rays is None or len(rays) < 2:
                continue
            try:
                P = np.asarray(ray_ls_point(rays), float)
            except Exception:
                continue
            if not np.all(np.isfinite(P)):
                continue
            errs = []
            for o, dvec in rays:
                v = P - o
                nv = np.linalg.norm(v)
                if nv < 1.0:
                    continue
                cosang = float(np.clip(np.dot(v / nv, dvec), -1, 1))
                errs.append(math.degrees(math.acos(cosang)) * 60.0)
            for e in errs:
                tot += math.log1p((e / 2.0) ** 2)      # Cauchy: les aberrants saturent
            if collect_detail:
                detail[lm] = (P, max(errs) if errs else None)
        # 1b) [V2 corpus rlx] contraintes structurelles douces
        if self.use_corpus:
            tot += self.corpus_cost(detail if collect_detail else None)
        # 2) ancres fixes: reprojection angulaire
        for lm, obs in self.anchors.items():
            X = self.lms[lm]['xyz']
            for c, p in obs:
                cam = self.cam(c)
                try:
                    d = cam.get_pixel_direction(p)
                except Exception:
                    continue
                if d is None:
                    tot += 30.0
                    continue
                d = np.asarray(d, float); d /= np.linalg.norm(d)
                v = np.asarray(X, float) - np.asarray(cam.xyz, float)
                v /= np.linalg.norm(v)
                e = math.degrees(math.acos(float(np.clip(np.dot(v, d), -1, 1)))) * 60.0
                tot += 3.0 * math.log1p((e / 2.0) ** 2)   # poids ancre
        return (tot, detail) if collect_detail else tot

    def descend(self, rounds=60, verbose=True):
        steps0 = [8.0, 8.0, 3.0, 0.3, 0.15, 0.05, 0.4]   # x y z yaw pitch roll hfov
        steps = {c: list(steps0) for c in AMB}
        best = self.cost()
        for r in range(rounds):
            improved = False
            for c in AMB:
                for i in range(7):
                    s = steps[c][i]
                    if s <= 0:
                        continue
                    for sgn in (1, -1):
                        old = self.theta[c][i]
                        cand = old + sgn * s
                        lo, hi = self.bounds[c][i]
                        if not (lo <= cand <= hi):
                            continue
                        self.theta[c][i] = cand
                        v = self.cost()
                        if v < best - 1e-9:
                            best = v
                            improved = True
                        else:
                            self.theta[c][i] = old
            if not improved:
                for c in AMB:
                    steps[c] = [s / 2 for s in steps[c]]
                if max(max(steps[c]) for c in AMB) < 1e-3:
                    break
            if verbose and (r % 5 == 0 or not improved):
                print(f'  round {r:3} cost {best:10.3f}' + ('' if improved else '  (halve steps)'))
        return best


def sigmas(sv, dcost=2.0):
    """Sensibilite par parametre: delta qui augmente le cout de +dcost
    (profil 1D, les autres parametres figes) — la barre d'erreur honnete
    du minimum local."""
    base = sv.cost()
    names = ['x', 'y', 'z', 'yaw', 'pitch', 'roll', 'hfov']
    out = {}
    for c in AMB:
        row = []
        for i in range(7):
            step = [4.0, 4.0, 2.0, 0.15, 0.08, 0.05, 0.2][i]
            old = sv.theta[c][i]
            d = step
            for _ in range(12):
                sv.theta[c][i] = old + d
                up = sv.cost() - base
                sv.theta[c][i] = old
                if up > dcost * 1.3:
                    d *= 0.7
                elif up < dcost * 0.7:
                    d *= 1.4
                else:
                    break
            row.append(d)
        out[c] = row
    print(f'\nSENSIBILITES (+{dcost} de cout):')
    for c in AMB:
        r = out[c]
        print(f'  {c[:26]:26} dx±{r[0]:5.1f} dy±{r[1]:5.1f} dz±{r[2]:5.1f} '
              f'dyaw±{r[3]:5.2f} dpitch±{r[4]:5.2f} droll±{r[5]:4.2f} dhfov±{r[6]:4.2f}')
    return out


def report(sv, lms):
    cost, detail = sv.cost(collect_detail=True)
    print(f'\ncost final: {cost:.3f}')
    print('\nPOSES:')
    for c in AMB:
        x, y, z, yaw, pitch, roll, hfov = sv.theta[c]
        print(f'  {c:26} ({x:9.2f},{y:9.2f},{z:7.2f}) ypr=({yaw:7.2f},{pitch:6.2f},{roll:5.2f}) hfov={hfov:6.2f}')
    worst = sorted([(e, lm) for lm, (P, e) in detail.items() if e], reverse=True)[:12]
    print('\npires residus (arcmin, max par LM):')
    for e, lm in worst:
        print(f'  {e:8.1f}\'  {lm}')
    # diagnostics corpus rlx
    def z_of(lm):
        d = detail.get(lm)
        return d[0][2] if d else None
    silo_top = z_of('1500 Sonora Ave (Silo) (L)') or z_of('1500 Sonora Ave (Silo)')
    silo_b = z_of('1500 Sonora Ave (Silo) (B)')
    print('\nDIAGNOSTICS corpus rlx:')
    if silo_top is not None and silo_b is not None:
        print(f'  hauteur silo: {silo_top - silo_b:.2f} m (rlx attend ~45-48)')
    elif silo_top is not None:
        print(f'  silo top z: {silo_top:.2f} (base non triangulable)')
    for tag, label in (('_silo_ratio', 'silo (w, h, ratio; rlx: ratio 3.2)'),
                       ('_bison', 'bison 6.00m -> pos + dist au silo'),
                       ('_worker', 'worker 1.80m -> pos + dist au silo')):
        dd = detail.get(tag)
        if dd:
            print(f'  {label:44} {np.round(dd[0], 2)}  d={dd[1] if dd[1] is not None else "-"}')
    for name in ('Daytona Beach Water Tower', 'Sebring Water Tower', 'US Sugar Mill (Factory)',
                 'Wheelabrator South Broward (TE)', 'USSM Smokestack (7)'):
        d = detail.get(name)
        if d:
            P = d[0]
            print(f'  {name:36} -> ({P[0]:9.2f},{P[1]:9.2f},{P[2]:7.2f})  res {d[1]:.1f}\'')
    return cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rounds', type=int, default=60)
    ap.add_argument('--init', choices=['ours', 'rlx', 'h'], default='ours')
    ap.add_argument('--no-brator', action='store_true')
    ap.add_argument('--corpus', action='store_true', help='contraintes structurelles rlx (V2)')
    ap.add_argument('--no-kalaga', action='store_true',
                    help='exclut les rayons de Mount Kalaga (pose devinee, chiffres ronds — jamais resolue)')
    ap.add_argument('--sigma', action='store_true', help='calcule les sensibilites par parametre')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    px, lms, cams = load()
    zone, anchors, ext_rays = collect(px, lms, cams, use_brator=not args.no_brator, no_kalaga=args.no_kalaga)
    n_obs = sum(len(o) for o in zone.values())
    n_ext = sum(len(r) for r in ext_rays.values())
    print(f'zone: {len(zone)} LMs partages ({n_obs} obs cluster, {n_ext} rayons externes fixes)')
    print(f'ancres fixes: {list(anchors)}')
    print(f'monde brator: {not args.no_brator}   init: {args.init}')

    sv = Solver(zone, anchors, ext_rays, lms, cams, init=args.init, use_corpus=args.corpus)
    # quarantaine: LM dont le residu initial explose = appariement suspect
    # (ex: 'Mount Ambrosia' vue par Explosion n'est PAS la meme colline)
    _, det0 = sv.cost(collect_detail=True)
    bad = [lm for lm, (P, e) in det0.items() if e is not None and e > 90.0]
    if bad:
        print(f'QUARANTAINE ({len(bad)} LMs, residu initial > 90\'): {bad}')
        for lm in bad:
            zone.pop(lm, None)
        sv = Solver(zone, anchors, ext_rays, lms, cams, init=args.init, use_corpus=args.corpus)
    print(f'cost initial: {sv.cost():.3f}')
    sv.descend(rounds=args.rounds)
    report(sv, lms)
    if args.sigma:
        sigmas(sv)

    if args.apply:
        path = os.path.join(REPO, 'gtamapdata', 'cameras.json')
        cj = json.load(open(path))
        for c in AMB:
            x, y, z, yaw, pitch, roll, hfov = sv.theta[c]
            cj[c]['xyz'] = [round(x, 3), round(y, 3), round(z, 3)]
            cj[c]['ypr'] = [round(yaw, 4), round(pitch, 4), round(roll, 4)]
            cj[c]['fov'] = [round(hfov, 4), None]
        tmp = path + '.tmp'
        json.dump(cj, open(tmp, 'w'), indent=2, ensure_ascii=True)
        os.replace(tmp, path)
        # LMs de zone: xyz re-triangules par le solve (rayons externes inclus),
        # ecrits seulement si le residu max est sain (<30')
        _, det = sv.cost(collect_detail=True)
        lp = os.path.join(REPO, 'gtamapdata', 'landmarks.json')
        lj = json.load(open(lp))
        n_lm = 0
        for lm, (P, e) in det.items():
            if lm.startswith('_') or e is None or e > 30.0:
                continue
            if lm not in lj or not isinstance(lj[lm], dict):
                continue
            lj[lm]['xyz'] = [round(float(v), 3) for v in P]
            lj[lm]['error_m'] = None
            n_lm += 1
        tmp = lp + '.tmp'
        json.dump(lj, open(tmp, 'w'), indent=2, ensure_ascii=True)
        os.replace(tmp, lp)
        common.log_event('ambrosia_joint', 'poses_applied',
                         reason=f'solve joint 4 cams + {n_lm} LMs de zone, init={args.init}, brator={not args.no_brator}')
        print(f'\nAPPLIED: 4 poses + {n_lm} LMs de zone.')
    else:
        print('\nDRY-RUN (--apply pour ecrire).')


if __name__ == '__main__':
    main()
