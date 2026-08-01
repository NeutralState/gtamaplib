#!/usr/bin/env python3
"""sky_carve.py — le relief taille par les rayons de CIEL. [SKYCARVE-V1]

L'idee, et pourquoi elle repond exactement a notre situation.

Le stereo dense (PSWEEP) a echoue sur nos massifs, et le diagnostic etait
sans appel: la geometrie est exacte (homographie verifiee a 0.00 px) mais
l'appariement photometrique se trompe. La cause de fond est la repartition
de nos cameras — les parallaxes vont de 40 a 127 degres. A 100 degres, deux
cameras voient deux FACES differentes du massif: aucune correlation d'image
n'existe, et c'est structurel, pas un defaut de reglage.

Or il existe une famille de methodes pour laquelle une grande parallaxe est
un ATOUT et non un handicap, parce qu'elle n'apparie rien: le space carving
/ shape-from-silhouette (Kutulakos & Seitz, A Theory of Shape by Space
Carving). On ne cherche pas le meme point dans deux images; on taille dans
l'espace tout ce que les images interdisent.

Pour du relief, la contrainte se simplifie enormement, et elle devient une
inegalite exacte:

    TOUT RAYON QUI TRAVERSE DU CIEL PASSE AU-DESSUS DU TERRAIN.

Donc pour une camera donnee et un azimut donne, la ligne d'horizon lue dans
l'image fixe une BORNE SUPERIEURE sur l'altitude du sol partout le long de
cette direction:

    H(x, y)  <=  z_cam + d * tan(elevation de la ligne de ciel a cet azimut)

C'est un champ de hauteur 2.5D — pas un volume de voxels — donc c'est
direct et peu couteux: pour chaque cellule, un azimut et une distance par
camera.

TROIS PROPRIETES QUI COMPTENT:

  * aucune correspondance. Rien a apparier, donc l'eclairage, l'heure, la
    meteo et la resolution des deux frames n'ont aucune importance. C'est
    precisement ce qui bloquait le stereo.
  * les occluders vont dans le BON SENS. Un poteau, un panneau ou un arbre
    devant la crete font monter la ligne de ciel apparente, donc RELACHENT
    la borne. On sous-taille, on ne sur-taille jamais. L'erreur est
    conservatrice, ce qui est l'inverse du comportement du stereo.
  * ca se cumule. Chaque camera supplementaire ne peut que baisser le
    champ, jamais le remonter. Les vues tres ecartees taillent des faces
    differentes du massif et se completent.

CE QUE CA NE DONNE PAS: une surface exacte, mais l'ENVELOPPE SUPERIEURE du
relief compatible avec toutes les vues. Pour un sommet vu de plusieurs
azimuts, l'enveloppe colle au sommet — c'est justement ce qu'on cherche.
Pour une vallee jamais vue de face, elle reste haute, et c'est honnete: on
ne l'a pas mesuree.

NOS ANCRES SERVENT DE PLANCHER, ET DE TEST: un landmark triangule est un
point du terrain, donc H doit rester au-dessus de lui. Si le carving passe
SOUS une ancre, c'est une contradiction — soit la ligne de ciel est mal
lue, soit l'ancre est fausse, soit une pose derive. L'outil les compte au
lieu de les cacher.

Usage:
  PYTHONPATH=. python3 tools/sky_carve.py --bbox -6400,-4400,4600,6800 \
      [--cell 25] [--cams 'A;B;C'] [--apply]
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
from PIL import Image

MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
NBINS = 1440          # 0.25 deg d'azimut


def posed(e):
    return bool(e.get('xyz') and e.get('ypr') and any(e['ypr'])
                and e.get('fov') and (e['fov'][0] or e['fov'][1]))


def skyline_profile(cam_name, step=3):
    """Ligne de ciel d'une camera, en fonction de l'AZIMUT monde.

    Retourne un tableau de NBINS elevations (tangente de l'angle), ou nan la
    ou la camera ne regarde pas. Pour chaque colonne de l'image on descend
    jusqu'au dernier pixel de ciel; le rayon de CE pixel est la limite
    superieure du terrain dans cette direction.
    """
    import common
    p = os.path.join(REPO, 'frames', f'{cam_name}.png')
    if not os.path.exists(p):
        return None, 0, 0.0, 0.0, 0.0
    a = np.asarray(Image.open(p).convert('RGB'), np.int16)
    blue = a[:, :, 2] - a[:, :, 0]
    bright = a.mean(axis=2)
    sky = (blue > 6) | (bright > 205)
    H, W = sky.shape
    cam = common.get_cam(cam_name)
    # AZIMUT RELATIF AU CAP. Le champ de vue d'une camera est un arc
    # CONTINU; en azimut absolu il peut chevaucher 0/360 et se retrouver
    # coupe en deux morceaux aux extremites du tableau. On travaille donc
    # en ecart au cap, ou l'arc est d'un seul tenant — c'est ce qui permet
    # de combler tous les trous internes sans jamais deborder hors champ.
    d0 = np.asarray(cam.get_pixel_direction((cam.w / 2.0, cam.h / 2.0)), float)
    yaw0 = math.degrees(math.atan2(d0[0], d0[1]))
    prof = np.full(NBINS, np.nan)
    n = 0
    for x in range(0, W, step):
        col = sky[:, x]
        if not col[0]:
            continue          # le haut de la colonne n'est pas du ciel
        # CONTIGUITE AU HAUT DE L'IMAGE. Sans cette regle, une route claire
        # ou une facade blanche en BAS de l'image est classee ciel, la
        # "ligne de ciel" tombe tout en bas, la borne devient enormement
        # negative et on taille le terrain a -10 000 m. Le ciel est la
        # bande connexe qui part du bord superieur, point.
        run = np.argmin(col) if (~col).any() else len(col)
        y = int(run) - 1
        if y < 2 or y >= H - 3:
            continue
        d = np.asarray(cam.get_pixel_direction((float(x), float(y))), float)
        nrm = np.linalg.norm(d)
        if nrm < 1e-9:
            continue
        d /= nrm
        horiz = math.hypot(d[0], d[1])
        if horiz < 1e-6:
            continue
        az = math.degrees(math.atan2(d[0], d[1]))
        rel = (az - yaw0 + 180.0) % 360.0 - 180.0     # dans [-180, 180)
        b = int((rel + 180.0) / 360.0 * NBINS)
        if not (0 <= b < NBINS):
            continue
        t = d[2] / horiz
        # On ne voit PAS de ciel loin sous l'horizon. Une colonne dont le
        # "dernier pixel de ciel" pointe a -70 degres n'est pas une ligne
        # d'horizon: c'est un plafond clair, un mur blanc ou une brume
        # surexposee pris pour du ciel. Ces colonnes tiraient la borne a
        # -6700 m. On garde ce qui peut etre une silhouette de terrain.
        # Un rayon de CIEL monte, strictement. Dans un monde plat, tout
        # rayon d'elevation negative rencontre le sol a distance finie —
        # ce ne serait donc pas du ciel. Une elevation negative signale une
        # pose dont le tangage derive ou un masque faux (plafond clair,
        # brume surexposee), et ces colonnes taillaient a -1300 m.
        if t <= 0.0:
            continue
        prof[b] = t if math.isnan(prof[b]) else min(prof[b], t)
        n += 1
    # COMBLEMENT LIMITE. On n'interpole qu'a travers de PETITS trous entre
    # deux azimuts observes. Interpoler largement revenait a faire
    # contraindre une camera dans des directions qu'elle ne regarde pas —
    # c'est ce qui laissait des cams a 7 km tailler un massif hors de leur
    # champ.
    # COMBLEMENT INTEGRAL DE L'ARC OBSERVE. Entre le premier et le dernier
    # azimut vus, la camera regarde partout: on interpole donc tous les
    # trous internes. Hors de l'arc, rien — c'est la que se jouait le bug
    # des cameras qui contraignaient des directions qu'elles ne voient pas.
    known = np.where(~np.isnan(prof))[0]
    if len(known) >= 2:
        lo_i, hi_i = int(known.min()), int(known.max())
        prof[lo_i:hi_i + 1] = np.interp(np.arange(lo_i, hi_i + 1), known, prof[known])
        # LISSAGE. La frontiere ciel/terrain saute de plusieurs pixels d'une
        # colonne a l'autre (arbres, poteaux, aretes de toits). Chaque saut
        # devient une TRAINEE RADIALE dans le champ de hauteur, parce que la
        # borne s'applique jusqu'a la portee maximale: 20 px de saut valent
        # 50 m a 5 km. On prend donc le MAXIMUM local puis une moyenne — le
        # maximum d'abord parce que la borne doit rester conservatrice: un
        # arbre fait monter la ligne et ne doit pas etre lisse vers le bas.
        w = 9
        pad = np.pad(prof[lo_i:hi_i + 1], w, mode='edge')
        mx = np.array([pad[i:i + 2 * w + 1].max() for i in range(hi_i - lo_i + 1)])
        ker = np.ones(w) / w
        prof[lo_i:hi_i + 1] = np.convolve(np.pad(mx, w // 2, mode='edge'),
                                          ker, mode='valid')[:hi_i - lo_i + 1]
    fin = prof[~np.isnan(prof)]
    lo = math.degrees(math.atan(fin.min())) if len(fin) else 0.0
    hi = math.degrees(math.atan(fin.max())) if len(fin) else 0.0
    return prof, n, lo, hi, yaw0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bbox', required=True, help='xmin,xmax,ymin,ymax')
    ap.add_argument('--cell', type=float, default=25.0)
    ap.add_argument('--cams', help='liste explicite separee par ";" '
                                   '(defaut: toutes les cams posees qui '
                                   'regardent la zone)')
    ap.add_argument('--ceiling', type=float, default=700.0)
    ap.add_argument('--max-dist', type=float, default=5000.0,
                    help='distance au-dela de laquelle une ligne de ciel ne '
                         'contraint plus. La brume et la distance '
                         "d'affichage la brouillent, et l'erreur de pose y "
                         'devient couteuse: 0.1 deg vaut 9 m a 5 km et 21 m '
                         'a 12 km.')
    ap.add_argument('--name', default='Relief (carve)')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    import common
    cams = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    xmin, xmax, ymin, ymax = [float(v) for v in args.bbox.split(',')]
    nx = int((xmax - xmin) / args.cell)
    ny = int((ymax - ymin) / args.cell)
    gx = xmin + (np.arange(nx) + 0.5) * args.cell
    gy = ymin + (np.arange(ny) + 0.5) * args.cell
    X, Y = np.meshgrid(gx, gy)
    Hf = np.full(X.shape, args.ceiling, np.float64)
    print(f'grille {nx} x {ny} cellules de {args.cell:.0f} m '
          f'({(xmax - xmin) / 1000:.1f} x {(ymax - ymin) / 1000:.1f} km), '
          f'plafond {args.ceiling:.0f} m')

    if args.cams:
        cand = [c.strip() for c in args.cams.split(';') if c.strip()]
    else:
        cand = [c for c, e in cams.items()
                if posed(e) and os.path.exists(os.path.join(REPO, 'frames', f'{c}.png'))]
    print(f'{len(cand)} cameras candidates\n')
    print(f'{"camera":40s} {"dist":>7s} {"colonnes":>9s}  cellules   '
          f'ligne de ciel')
    used = 0
    rejected = []
    yaw = {}
    for cn in sorted(cand):
        e = cams[cn]
        o = np.asarray(e['xyz'], float)
        dx, dy = X - o[0], Y - o[1]
        D = np.hypot(dx, dy)
        if D.min() > args.max_dist:
            continue
        prof, ncol, lo, hi, yaw0 = skyline_profile(cn)
        yaw[cn] = yaw0
        if prof is None or ncol < 30:
            if prof is not None and ncol:
                rejected.append((cn, lo, hi, ncol))
            continue
        AZ = np.degrees(np.arctan2(dx, dy))
        REL = (AZ - yaw[cn] + 180.0) % 360.0 - 180.0
        B = np.clip(((REL + 180.0) / 360.0 * NBINS).astype(np.int32), 0, NBINS - 1)
        T = prof[B]
        ok = ~np.isnan(T)
        # la borne n'a de sens qu'a distance raisonnable: tres pres de la
        # camera, une erreur d'un pixel sur la ligne de ciel ne coute rien,
        # mais la cellule est souvent hors champ
        ok &= (D > 3.0 * args.cell) & (D < args.max_dist)
        if not ok.any():
            continue
        lim = o[2] + D * T
        before = Hf.copy()
        Hf = np.where(ok, np.minimum(Hf, lim), Hf)
        cut = int((Hf < before - 0.5).sum())
        if cut:
            used += 1
            tv = T[ok]
            print(f'{cn[:40]:40s} {D.min():7.0f} {ncol:9d}  {cut:8d}   '
                  f'elevation {math.degrees(math.atan(np.nanmin(tv))):6.1f} a '
                  f'{math.degrees(math.atan(np.nanmax(tv))):5.1f} deg')
    print(f'\n{used} cameras ont effectivement taille')
    if rejected:
        print('\ncameras ecartees (ligne de ciel sous l horizon — pose ou '
              'masque suspect):')
        for cn, lo, hi, k in sorted(rejected, key=lambda r: r[1])[:8]:
            print(f'   {cn[:42]:42s} elevation {lo:6.1f} a {hi:5.1f} deg '
                  f'({k} colonnes)')

    inside = Hf < args.ceiling - 1.0
    print(f'cellules contraintes: {int(inside.sum())} / {Hf.size} '
          f'({100.0 * inside.mean():.1f} pct)')
    if inside.any():
        print(f'enveloppe: z {Hf[inside].min():.0f} a {Hf[inside].max():.0f} m, '
              f'mediane {np.median(Hf[inside]):.0f} m')

    # PLANCHER ET TEST: une ancre triangulee est un point du terrain, donc
    # l'enveloppe doit rester au-dessus d'elle. Un passage en dessous est
    # une contradiction, pas un detail.
    viol, checked = [], 0
    for lm, v in lms.items():
        if not (isinstance(v, dict) and v.get('xyz')):
            continue
        q = v['xyz']
        if not (xmin < q[0] < xmax and ymin < q[1] < ymax):
            continue
        j = int((q[0] - xmin) / args.cell)
        i = int((q[1] - ymin) / args.cell)
        if not (0 <= i < ny and 0 <= j < nx) or not inside[i, j]:
            continue
        checked += 1
        if Hf[i, j] < q[2] - 5.0:
            viol.append((lm, q[2], float(Hf[i, j])))
    print(f'\nplancher: {checked} ancres dans la zone contrainte, '
          f'{len(viol)} sous l enveloppe (contradiction)')
    for lm, z, h in sorted(viol, key=lambda r: r[1] - r[2], reverse=True)[:8]:
        print(f'   {lm[:38]:38s} ancre z {z:6.1f} > enveloppe {h:6.1f} '
              f'({z - h:.0f} m de trop)')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    edges = []
    st = max(1, int(round(50.0 / args.cell)))
    for i in range(0, ny - st, st):
        for j in range(0, nx - st, st):
            if not (inside[i, j] and inside[i, j + st] and inside[i + st, j]):
                continue
            a = [float(X[i, j]), float(Y[i, j]), float(Hf[i, j])]
            b = [float(X[i, j + st]), float(Y[i, j + st]), float(Hf[i, j + st])]
            c = [float(X[i + st, j]), float(Y[i + st, j]), float(Hf[i + st, j])]
            edges.append([a, b])
            edges.append([a, c])
    mesh = json.load(open(MESH_PATH)) if os.path.exists(MESH_PATH) else {}
    mesh[args.name] = {'color': '#4ade80', 'world_edges': edges}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'\nAPPLIED: {args.name} ({len(edges)} aretes)')


if __name__ == '__main__':
    main()
