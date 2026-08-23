#!/usr/bin/env python3
"""horizon_resect.py — caler une pose sur la SILHOUETTE du terrain height map.

[HORIZON-V1] Reincarnation du trace-fit de la campagne mesh, mais contre la
height map (source de verite, 0.18 m median sur les players HUD) au lieu des
meshs traces. Principe: pour une pose candidate, on calcule l'horizon du
terrain (pour chaque azimut couvrant le fov, le point qui maximise l'angle
d'elevation), on le projette dans l'image, et on mesure l'ecart vertical
entre les clics de crete et cette courbe. Ce residu s'ajoute au residu des
ancres classiques (billboards): les ancres tiennent la position, la
silhouette tient yaw/pitch/roll/fov — exactement ce que des ancres proches
et serrees ne contraignent pas.

Usage:
  PYTHONPATH=. python3 tools/horizon_resect.py --cam 'Ambrosia 01 (Bikers)' \
      --crest 'Mount Ambrosia' [--lock-z 25.6] [--w-sil 1.0] [--apply]
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
import common

SC, ZX, ZY = 0.083188297, 1108.532, 938.091


def load_heightmap():
    p = os.path.join(REPO, 'gtamapdata', 'heightmap', 'GTA6HeightMap_L16.dds')
    d = open(p, 'rb').read()
    L = np.frombuffer(d[128:128 + 1536 * 1748 * 2], dtype='<u2')
    return L.reshape(1748, 1536).astype(np.float64) / 65535.0


HM = load_heightmap()


def ground(X, Y):
    """z terrain (vectorise). Hors donnees (v<0.005): -301 (jamais un horizon)."""
    U = ZX + np.asarray(X) * SC
    V = ZY - np.asarray(Y) * SC
    U = np.clip(U, 0, 1534.999)
    V = np.clip(V, 0, 1746.999)
    iu = U.astype(int); iv = V.astype(int)
    fu = U - iu; fv = V - iv
    s = (HM[iv, iu] * (1 - fu) * (1 - fv) + HM[iv, iu + 1] * fu * (1 - fv)
         + HM[iv + 1, iu] * (1 - fu) * fv + HM[iv + 1, iu + 1] * fu * fv)
    return 706.07 * s - 301.01


def horizon_points(x, y, z, az_deg, dmin=200.0, dmax=15000.0, step=12.0):
    """Pour chaque azimut (deg, 0=+y, sens horaire comme yaw), le point 3D du
    terrain qui maximise l'angle d'elevation vu de (x,y,z). Vectorise en 2D
    (distances x azimuts) — une seule passe numpy, pas de boucle python."""
    D = np.arange(dmin, dmax, step)
    r = np.radians(np.asarray(az_deg))
    Xs = x + np.sin(r)[None, :] * D[:, None]     # (nD, nAz)
    Ys = y + np.cos(r)[None, :] * D[:, None]
    Zs = ground(Xs, Ys)
    elev = np.arctan2(Zs - z, D[:, None])
    i = np.argmax(elev, axis=0)
    j = np.arange(len(r))
    return list(zip(Xs[i, j].tolist(), Ys[i, j].tolist(), Zs[i, j].tolist()))


class Fit:
    def __init__(self, cam, crest_prefix, lock_z, w_sil):
        self.px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
        self.cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
        lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
        self.cam = cam
        self.size = self.cams[cam].get('size') or [1920, 1080]
        self.lock_z = lock_z
        self.w_sil = w_sil
        # crest_prefix: prefixes OU noms exacts, separes par des virgules.
        # ATTENTION: ne mettre ici que des points sur la SKYLINE (l'enveloppe
        # superieure visible) — une crete intermediaire passee sous un massif
        # plus haut n'est PAS l'horizon et fausserait le residu.
        keys = [k.strip() for k in crest_prefix.split(',') if k.strip()]
        self.anchors, self.crest = [], []
        for lm, p in self.px[cam].items():
            if p is None:
                continue
            if any(lm == k or lm.startswith(k) for k in keys):
                self.crest.append((lm, p))
            elif isinstance(lms.get(lm), dict) and lms[lm].get('xyz'):
                self.anchors.append((lm, np.asarray(lms[lm]['xyz'], float), p))

    def load_traces(self):
        """[TRACES] ajoute les strokes de silhouette (tools/data/silhouettes.json)
        comme points de crete denses — c'est la ou la precision se gagne: le
        bruit de clic se moyenne sur ~100 points au lieu de 9."""
        p = os.path.join(REPO, 'tools', 'data', 'silhouettes.json')
        if not os.path.exists(p):
            return 0
        sil = json.load(open(p)).get(self.cam) or {}
        n = 0
        for mont, d in sil.items():
            for si, stroke in enumerate((d or {}).get('strokes') or []):
                for pi, pt in enumerate(stroke):
                    self.crest.append((f'{mont}~{si}.{pi}', pt))
                    n += 1
        return n

    def state(self, t):
        # keep_fov: fov d'origine (verite console pour les cams HUD) — le
        # fit n'a pas le droit d'y toucher (invariant LEAK du healthcheck).
        fov = getattr(self, 'keep_fov', None) or [t[6], None]
        return {'xyz': list(t[:3]), 'ypr': list(t[3:6]),
                'fov': list(fov), 'size': self.size}

    def anchor_res(self, t):
        c = common.get_cam(self.cam, self.state(t))
        out = []
        for lm, Q, p in self.anchors:
            pr = c.get_pixel([float(v) for v in Q])
            if pr is None:
                out.append((lm, 999.0)); continue
            dx = (pr[0] - p[0]) * c.hfov / c.w * 60.0
            dy = (pr[1] - p[1]) * c.vfov / c.h * 60.0
            out.append((lm, math.hypot(dx, dy)))
        return out

    def sil_res(self, t):
        """Residu vertical (arcmin) de chaque clic de crete vs la courbe
        d'horizon projetee, interpolee au meme x image."""
        c = common.get_cam(self.cam, self.state(t))
        # convention verifiee sur les ancres: boresight az(0=+y, horaire) = -yaw
        # (le yaw de common est anti-horaire).
        az = [-t[3] + a for a in np.linspace(-c.hfov * 0.75, c.hfov * 0.75, 240)]
        pts = horizon_points(t[0], t[1], t[2], az)
        proj = []
        for P in pts:
            pr = c.get_pixel(list(P))
            if pr is not None:
                proj.append(pr)
        if len(proj) < 4:
            return [(lm, 999.0) for lm, _ in self.crest]
        proj.sort(key=lambda q: q[0])
        U = [q[0] for q in proj]; V = [q[1] for q in proj]
        if getattr(self, 'debug', False):
            print(f'   [debug] horizon projete: {len(proj)}/{len(pts)} points, '
                  f'u de {U[0]:.0f} a {U[-1]:.0f}')
        out = []
        for lm, p in self.crest:
            u, v = p
            if u < U[0] or u > U[-1]:
                continue
            vs = float(np.interp(u, U, V))
            out.append((lm, (v - vs) * c.vfov / c.h * 60.0))
        return out

    def cost(self, t):
        ca = sum(math.log1p((a / 6.0) ** 2) for _, a in self.anchor_res(t))
        ca /= max(1, len(self.anchors))
        sr = self.sil_res(t)
        cs = sum(math.log1p((a / 6.0) ** 2) for _, a in sr) / max(1, len(sr))
        return ca + self.w_sil * cs

    def descend(self, t):
        _fix_xy = 0.0 if getattr(self, 'lock_xy', False) else 20.0
        STEP = [_fix_xy, _fix_xy,
                0.0 if self.lock_z is not None else 8.0,
                2.0, 1.5,
                0.0 if getattr(self, 'lock_roll', None) is not None else 1.0,
                0.0 if getattr(self, 'keep_fov', None) else 2.0]
        if self.lock_z is not None:
            t[2] = self.lock_z
        if getattr(self, 'lock_roll', None) is not None:
            t[5] = self.lock_roll
        best = self.cost(t)
        step = list(STEP)
        for _ in range(100):
            moved = False
            for i in range(7):
                if step[i] == 0.0:
                    continue
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
                if max(s for s in step) < 0.004:
                    break
        return t, best


def show(F, t, tag):
    ar = F.anchor_res(t)
    sr = F.sil_res(t)
    ma = float(np.median([a for _, a in ar])) if ar else float('nan')
    ms = float(np.median([abs(a) for _, a in sr])) if sr else float('nan')
    print(f'{tag}: ancres mediane {ma:.1f}\'  |  silhouette mediane {ms:.1f}\' '
          f'({len(sr)} points de crete dans l image)')
    return ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cam', required=True)
    ap.add_argument('--crest', default='',
                    help='prefixes/noms des markings de crete, virgules')
    ap.add_argument('--traces', action='store_true',
                    help='ajoute les strokes de tools/data/silhouettes.json')
    ap.add_argument('--traces-exclude', default='',
                    help='montagnes a ecarter des traces (virgules) — pour un '
                         'stroke irreconciliable (mal etiquete, ou crete '
                         'interieure et non skyline)')
    ap.add_argument('--lock-z', type=float, default=None)
    ap.add_argument('--keep-fov', action='store_true',
                    help='conserve le fov stocke tel quel (verite console '
                         'des cams HUD) — invariant LEAK du healthcheck')
    ap.add_argument('--lock-xy', action='store_true',
                    help='fige x,y (cam HUD-locked: la position est verite, '
                         'seule l orientation/fov se rejuge)')
    ap.add_argument('--lock-roll', type=float, default=None,
                    help='verrouille le roll (deg). Une cam vehicule/tripod '
                         'n a pas 5 deg de roll: laisse libre, ce parametre '
                         'mal contraint absorbe les erreurs des autres.')
    ap.add_argument('--debug', action='store_true')
    ap.add_argument('--init-z', type=float, default=None,
                    help='z de depart (sans le verrouiller) — pour sortir '
                         'd un minimum ou z/pitch se compensent')
    ap.add_argument('--restarts', type=int, default=0,
                    help='relances multi-departs (jitter deterministe xyz/ypr) '
                         'pour sortir des minima locaux — indispensable quand '
                         'les residus de silhouette ont des signes opposes')
    ap.add_argument('--w-sil', type=float, default=1.0,
                    help='poids du terme silhouette vs ancres')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    F = Fit(args.cam, args.crest, args.lock_z, args.w_sil)
    F.lock_roll = args.lock_roll
    F.lock_xy = args.lock_xy
    if args.keep_fov:
        F.keep_fov = list(F.cams[args.cam]['fov'])
    F.debug = args.debug
    if args.traces:
        nt = F.load_traces()
        excl = [k.strip() for k in args.traces_exclude.split(',') if k.strip()]
        if excl:
            before = len(F.crest)
            F.crest = [(lm, p) for lm, p in F.crest
                       if not ('~' in lm and any(lm.startswith(k) for k in excl))]
            print(f'traces: +{nt} points, {before - len(F.crest)} ecartes ({args.traces_exclude})')
        else:
            print(f'traces: +{nt} points de silhouette denses')
    if not F.crest:
        raise SystemExit('aucun point de crete (--crest et/ou --traces)')
    e = F.cams[args.cam]
    t = [e['xyz'][0], e['xyz'][1], e['xyz'][2],
         e['ypr'][0], e['ypr'][1], e['ypr'][2], e['fov'][0] or 60.0]
    if args.lock_z is not None:
        t[2] = args.lock_z
    if args.init_z is not None:
        t[2] = args.init_z
    print(f'{args.cam}: {len(F.anchors)} ancres 3D + {len(F.crest)} clics de '
          f'crete "{args.crest}*"'
          + (f'  [z verrouille {args.lock_z:.1f}]' if args.lock_z is not None else ''))
    show(F, t, 'AVANT')
    t, c = F.descend(t)
    # relances: jitter deterministe autour du meilleur, garde le meilleur cout
    JIT = [200.0, 200.0, 60.0, 4.0, 3.0, 0.0, 4.0]
    for k in range(args.restarts):
        t2 = [v + JIT[i] * (((k * 7 + i * 3) % 5) - 2) / 2.0
              for i, v in enumerate(t)]
        t2, c2 = F.descend(t2)
        if c2 < c - 1e-9:
            t, c = t2, c2
            print(f'   relance {k}: meilleur cout {c:.4f}')
    show(F, t, 'APRES')
    print(f'pose: xyz ({t[0]:.1f}, {t[1]:.1f}, {t[2]:.1f})  '
          f'ypr ({t[3]:.2f}, {t[4]:.2f}, {t[5]:.2f})  hfov {t[6]:.2f}')
    groups = {}
    for lm, a in F.sil_res(t):
        key = lm.split('~')[0] if '~' in lm else None
        if key:
            groups.setdefault(key, []).append(a)
        else:
            print(f'   {lm:30s} {a:+7.1f}\'')
    for key, vals in groups.items():
        print(f'   [trace] {key:22s} {len(vals):3d} pts  mediane {np.median(vals):+6.1f}\'  '
              f'IQR {np.percentile(vals,25):+.1f}..{np.percentile(vals,75):+.1f}')
    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    # [SOLVED-REF-V1] pose validee par Alexandre = intouchable sans son ordre
    if e.get('pose_verified') and not os.environ.get('OVERRIDE_SOLVED'):
        print(f"\nREFUS: {args.cam} est SOLVED — modification interdite sans "
              "ordre explicite d'Alexandre (OVERRIDE_SOLVED=1 apres son accord).")
        return
    e['xyz'] = [round(v, 3) for v in t[:3]]
    e['ypr'] = [round(v, 3) for v in t[3:6]]
    if not args.keep_fov:
        e['fov'] = [round(t[6], 3), None]
    e['note'] = (f'pose HORIZON-V1: {len(F.anchors)} ancres + silhouette '
                 f'height map ({len(F.crest)} clics de crete), '
                 f'z {"verrouille sol height map" if args.lock_z is not None else "libre"}.')
    p = os.path.join(REPO, 'gtamapdata', 'cameras.json')
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(F.cams, f, indent=1, ensure_ascii=True)
    os.replace(tmp, p)
    print(f'\nAPPLIED: {args.cam}')


if __name__ == '__main__':
    main()
