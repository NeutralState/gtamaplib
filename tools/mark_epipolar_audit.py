#!/usr/bin/env python3
"""mark_epipolar_audit.py — deux clics designent-ils le meme objet ? [EPI-AUDIT-V1]

Pourquoi cet outil existe. Cinq tentatives de modelisation de massif ont
echoue cette session, chacune pour une raison apparemment differente. La
cause commune n'a ete vue qu'a la fin, a la main: sous le meme nom, deux
cameras ne marquaient pas le meme objet. Dans la frame helico, les clics
"Mount Ambrosia" sont sur une crete boisee a ~600 m; depuis Bikers, le
massif est a 1800-2600 m et sa crete se projette dans le CIEL au-dessus
d'eux. Les deux jeux ne se rencontrent jamais. Toute triangulation qui les
melange fabrique un point qui n'existe pas — et rien en aval ne peut le
rattraper.

LE TEST. Il ne demande ni profondeur ni triangulation, seulement les poses:
le rayon d'un clic dans la camera A, projete dans la camera B, y trace une
LIGNE EPIPOLAIRE. Si les deux clics designent le meme point du monde, le
clic de B est SUR cette ligne. L'ecart a la ligne est donc une mesure
directe de "est-ce le meme objet", en pixels, sans le moindre modele.

DEUX NIVEAUX:

  * MEME LANDMARK, deux cameras. L'ecart epipolaire doit etre de l'ordre de
    la precision de clic. Un ecart de plusieurs centaines de pixels dit que
    les deux clics ne visent pas le meme point.
  * MEME MASSIF, noms differents. Aucun clic de B ne tombe pres d'aucune
    ligne epipolaire des clics de A: les deux vues ne partagent alors AUCUN
    objet commun sur ce massif, et rien ne peut les relier.

LE GARDE QUI MANQUAIT. Un gros ecart epipolaire peut venir des CLICS ou des
POSES, et confondre les deux ferait accuser des marks innocents. On mesure
donc, pour chaque paire de cameras, un TEMOIN: le meme ecart sur leurs
landmarks NON-relief partages (batiments, panneaux, poteaux — des objets
ponctuels et nets). Si le temoin est bon et le relief mauvais, ce sont les
marks de relief. Si le temoin est mauvais aussi, c'est la paire de poses,
et l'outil le dit au lieu de designer un coupable au hasard.

Usage:
  PYTHONPATH=. python3 tools/mark_epipolar_audit.py
  PYTHONPATH=. python3 tools/mark_epipolar_audit.py --massif 'Mount Ambrosia'
"""
import argparse
import collections
import json
import math
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np

KEY = ('mount', 'hill', 'ridge', 'pass', 'bluff', 'peak', 'dome', 'redhill')
SKIP = ('bridge', 'sign', 'billboard', 'road', 'st ', 'tower', 'station',
        'overpass', 'tunnel', 'tree')


def massif_of(name):
    lo = name.lower()
    if not any(k in lo for k in KEY) or any(s in lo for s in SKIP):
        return None
    return name.split(' (')[0]


def _target_dist(lms, names, o):
    """Distance typique de l'objet, prise sur ceux de ses landmarks qui sont
    positionnes; a defaut une valeur prudente (loin = test plus severe)."""
    d = [float(np.linalg.norm(np.asarray(lms[n]['xyz'], float) - o))
         for n in names
         if isinstance(lms.get(n), dict) and lms[n].get('xyz')]
    return float(np.median(d)) if d else 3000.0


def posed(e):
    return bool(e.get('xyz') and e.get('ypr') and any(e['ypr'])
                and e.get('fov') and (e['fov'][0] or e['fov'][1]))


def epiline(camA, camB, p, near=80.0, far=12000.0, n=240):
    """Ligne epipolaire du clic p de A, tracee dans B en projetant le rayon a
    n profondeurs. Passer par des projections plutot que par une matrice
    fondamentale garde le modele de camera exact, quel qu'il soit."""
    o = np.asarray(camA.xyz, float)
    d = np.asarray(camA.get_pixel_direction((float(p[0]), float(p[1]))), float)
    nrm = np.linalg.norm(d)
    if nrm < 1e-9:
        return None
    d /= nrm
    out = []
    for t in np.geomspace(near, far, n):
        q = camB.get_pixel([float(v) for v in (o + t * d)])
        if q is not None:
            out.append((float(q[0]), float(q[1])))
    return np.array(out) if len(out) >= 2 else None


def dist_to_polyline(q, L):
    """Distance du point q a la polyligne L (segments, pas seulement sommets:
    la ligne epipolaire est echantillonnee, pas continue)."""
    a, b = L[:-1], L[1:]
    ab = b - a
    t = np.clip(((q - a) * ab).sum(axis=1) / np.maximum((ab * ab).sum(axis=1), 1e-9),
                0.0, 1.0)
    proj = a + t[:, None] * ab
    return float(np.min(np.linalg.norm(proj - q, axis=1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--massif', help='auditer un seul massif')
    ap.add_argument('--min-par', type=float, default=1.0,
                    help='parallaxe minimale (deg) sous laquelle le test '
                         'epipolaire degenere et ne conclut rien')
    ap.add_argument('--warn-px', type=float, default=25.0,
                    help='ecart epipolaire au-dela duquel on signale')
    args = ap.parse_args()

    import common
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))

    def frame_ok(c):
        return c in cams and posed(cams[c])

    # (massif, camera) -> [(landmark, pixel)]
    seen = collections.defaultdict(list)
    for c, mk in px.items():
        if not frame_ok(c):
            continue
        for lm, p in mk.items():
            m = massif_of(lm)
            if m and p is not None and not common.is_excluded_marking(c, lm):
                seen[(m, c)].append((lm, p))

    bym = collections.defaultdict(list)
    for (m, c), v in seen.items():
        bym[m].append((c, v))

    def control(cA, cB, camA, camB):
        """Temoin: ecart epipolaire de la paire sur les landmarks NON-relief
        partages. Il distingue un probleme de CLICS d'un probleme de POSES."""
        shared = [lm for lm in px[cA]
                  if px[cA][lm] is not None and px[cB].get(lm) is not None
                  and massif_of(lm) is None]
        ds = []
        for lm in shared[:40]:
            L = epiline(camA, camB, px[cA][lm])
            if L is None:
                continue
            ds.append(dist_to_polyline(np.asarray(px[cB][lm], float), L))
        return (float(np.median(ds)), len(ds)) if ds else (float('nan'), 0)

    print('AUDIT EPIPOLAIRE — deux clics designent-ils le meme objet ?\n')
    verdicts = []
    for m in sorted(bym):
        if args.massif and args.massif.lower() not in m.lower():
            continue
        obs = bym[m]
        if len(obs) < 2:
            continue
        print(f'== {m}   ({len(obs)} cameras)')
        for i in range(len(obs)):
            for j in range(i + 1, len(obs)):
                cA, vA = obs[i]
                cB, vB = obs[j]
                camA, camB = common.get_cam(cA), common.get_cam(cB)
                # CONDITIONNEMENT. Le test epipolaire suppose que les deux
                # cameras voient l'objet sous des angles differents. Si la
                # base est courte devant la distance, la ligne epipolaire
                # degenere en un point et l'ecart mesure n'a plus aucun
                # sens. Cas reel: Hedge (B) et Hedge (C) sont a 0.4 m l'une
                # de l'autre et regardent Mount Mountain a 7 km — parallaxe
                # 0.00 deg. La V1 en tirait un verdict "CLIC INCOMPATIBLE"
                # sur 152 px: un faux positif pur.
                oa = np.asarray(camA.xyz, float)
                ob = np.asarray(camB.xyz, float)
                base = float(np.linalg.norm(oa - ob))
                dist = float(np.median([np.linalg.norm(oa - ob)] ) )
                par = math.degrees(math.atan2(base, max(1.0, _target_dist(
                    lms, [lm for lm, _ in vA] + [lm for lm, _ in vB], oa))))
                if par < args.min_par:
                    print(f'   {cA[:26]:26s} x {cB[:26]:26s}')
                    print(f'      base {base:.1f} m -> parallaxe {par:.2f} deg '
                          f'< {args.min_par} : TEST DEGENERE, aucun verdict')
                    verdicts.append(('degenere', m, cA, cB, float('nan'), float('nan')))
                    continue
                ctl, nctl = control(cA, cB, camA, camB)
                # 1) memes landmarks vus des deux cotes
                same = [lm for lm, _ in vA if any(lm == l2 for l2, _ in vB)]
                rows = []
                for lm in same:
                    pA = dict(vA)[lm]
                    pB = np.asarray(dict(vB)[lm], float)
                    L = epiline(camA, camB, pA)
                    if L is not None:
                        rows.append((lm, dist_to_polyline(pB, L)))
                # 2) le massif est-il seulement CO-VISIBLE ?
                best = []
                for lmB, pB in vB:
                    dmin = math.inf
                    for lmA, pA in vA:
                        L = epiline(camA, camB, pA)
                        if L is not None:
                            dmin = min(dmin, dist_to_polyline(np.asarray(pB, float), L))
                    if math.isfinite(dmin):
                        best.append((lmB, dmin))
                covis = min((d for _, d in best), default=float('nan'))
                ctls = f'{ctl:.0f} px sur {nctl}' if nctl else 'aucun temoin'
                # SIGNAL FORT: un landmark porte le MEME NOM dans les deux
                # vues. Son clic de B doit etre SUR la ligne epipolaire de
                # son clic de A. Cet ecart-la ne se discute pas.
                worst = max((d for _, d in rows), default=float('nan'))
                if nctl >= 3 and ctl > args.warn_px * 2:
                    verdict = 'POSES SUSPECTES (le temoin non-relief est mauvais aussi)'
                elif not math.isnan(worst) and worst > args.warn_px * 4:
                    verdict = f'*** CLIC INCOMPATIBLE ({worst:.0f} px sur un meme nom) ***'
                elif math.isnan(covis):
                    verdict = 'incalculable'
                elif covis > args.warn_px * 8:
                    verdict = '*** AUCUN OBJET COMMUN ***'
                elif covis > args.warn_px:
                    verdict = 'douteux'
                elif math.isnan(worst):
                    # NUANCE QUI COMPTE: passer le test epipolaire ne prouve
                    # PAS que c'est le meme objet. La contrainte est a une
                    # dimension — deux points a des profondeurs differentes
                    # le long du meme rayon la satisfont tous les deux. Sans
                    # landmark de meme nom, on ne peut donc dire que "non
                    # refute", jamais "confirme".
                    verdict = 'non refute (aucun nom commun: test faible)'
                else:
                    verdict = 'compatible'
                print(f'   {cA[:26]:26s} x {cB[:26]:26s}')
                print(f'      temoin non-relief {ctls:22s} | '
                      f'meilleur ecart relief {covis:7.0f} px   -> {verdict}')
                for lm, d in sorted(rows, key=lambda r: -r[1])[:3]:
                    print(f'         {lm[:34]:34s} meme nom, ecart {d:7.0f} px')
                verdicts.append((verdict, m, cA, cB, covis, ctl))
        print()

    bad = [v for v in verdicts if v[0].startswith('***')]
    dub = [v for v in verdicts if v[0] == 'douteux']
    pose = [v for v in verdicts if v[0].startswith('POSES')]
    weak = [v for v in verdicts if v[0].startswith('non refute')]
    print(f'RESUME: {len(verdicts)} paires auditees — {len(bad)} REFUTEES, '
          f'{len(dub)} douteuses, {len(pose)} imputables aux poses, '
          f'{len(weak)} non refutees mais sans nom commun (test faible), '
          f'{len([v for v in verdicts if v[0] == "degenere"])} degenerees '
          f'(base trop courte, aucun verdict possible)')
    for v, m, cA, cB, cv, ctl in bad:
        print(f'   {m[:20]:20s} {cA[:24]:24s} x {cB[:24]:24s}  {v}')
    print('\nRAPPEL: passer ce test ne prouve rien. La contrainte epipolaire '
          'est a UNE dimension —\ndeux points a des profondeurs differentes '
          'sur le meme rayon la satisfont tous les deux.\nElle REFUTE, elle '
          'ne confirme pas.')


if __name__ == '__main__':
    main()
