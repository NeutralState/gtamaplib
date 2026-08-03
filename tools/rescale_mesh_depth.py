#!/usr/bin/env python3
"""rescale_mesh_depth.py — adopter le profil de PROFONDEUR d'un mesh de
reference sans toucher a la silhouette du notre. [DEPTHADOPT-V1]

LE CONSTAT QUI MOTIVE L'OUTIL. Sur Mount Ambrosia, notre mesh et celui de
rlx dessinent LA MEME silhouette depuis Ambrosia 01 (Bikers): a azimut egal
l'elevation concorde a 0.06-0.61 deg pres, sur une crete vue a 8 deg. Tout
le desaccord est en profondeur — lui 2400-3200 m, nous ~2100 m plats. Et
notre 2100 m ne repose plus sur rien: les quatre ancres Mount Ambrosia ont
ete retirees le 31 juillet (4da4d2f) comme non fondees, le mesh leur a
survecu. Le chiffre venait de "d=2246 par corde x Empty Lot", dont la note
archivee dit elle-meme "fourchette d 1902-2614".

CE QUE FAIT L'OUTIL. Pour chaque sommet du mesh source, on conserve
EXACTEMENT son azimut et son elevation vus depuis la camera, et on ne
change que la distance horizontale, prise sur le profil D(azimut) de la
reference. La silhouette projetee est donc invariante au pixel pres — c'est
verifie et imprime a chaque run, pas suppose.

POURQUOI PAS UN SIMPLE FACTEUR D'ECHELLE. Notre massif est un rideau plat
(2063-2135 m sur tout l'eventail); le sien recule de 800 m vers l'ouest. Un
k uniforme garderait le rideau. L'interpolation par azimut lui donne une
emprise en profondeur.

CE QUE CA N'EST PAS. Aucune mesure n'est faite ici. On adopte des distances
DECLAREES a la main par rlx, faute de parallaxe exploitable: toutes les
cameras d'Ambrosia regardent le massif sous a peu pres le meme azimut. La
sortie vaut ce que valent ses chiffres, ni plus ni moins.

Usage:
  PYTHONPATH=. python3 tools/rescale_mesh_depth.py \
      --src 'Mount Ambrosia' --ref 'Mount Ambrosia (rlx)' \
      --cam 'Ambrosia 01 (Bikers)' [--apply]
"""
import argparse
import json
import os
import sys
import tempfile

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

import numpy as np

MESH_PATH = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')


def verts(mesh, key):
    return np.array([p for e in mesh[key]['world_edges'] for p in e], float)


def azel_d(P, o):
    """azimut (deg, 0=N, sens horaire), elevation (deg), distance HORIZONTALE."""
    d = np.atleast_2d(np.asarray(P, float)) - o
    az = np.degrees(np.arctan2(d[:, 0], d[:, 1])) % 360.0
    h = np.hypot(d[:, 0], d[:, 1])
    return az, np.degrees(np.arctan2(d[:, 2], h)), h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='le mesh a re-profondir (le notre)')
    ap.add_argument('--ref', required=True, help='le mesh dont on prend la profondeur')
    ap.add_argument('--cam', required=True)
    ap.add_argument('--crest-above', type=float, default=0.5,
                    help='marge au-dessus du z minimal de la ref pour isoler '
                         'la crete des points de pied')
    ap.add_argument('--az-win', type=float, default=1.5,
                    help='demi-fenetre en azimut pour apparier une crete de '
                         'la reference a une crete de la source (deg)')
    ap.add_argument('--out', default=None, help='nom du mesh ecrit (defaut: --src)')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    import common
    mesh = json.load(open(MESH_PATH))
    for k in (args.src, args.ref):
        if k not in mesh:
            raise SystemExit(f'mesh absent: {k!r}')
    cam = common.get_cam(args.cam)
    o = np.asarray(cam.xyz, float)
    print(f'camera {args.cam} a ({o[0]:.1f}, {o[1]:.1f}, {o[2]:.1f})\n')

    # ── le profil de profondeur de la reference ──
    R = np.unique(verts(mesh, args.ref), axis=0)
    crest = R[R[:, 2] > R[:, 2].min() + args.crest_above]
    if len(crest) < 2:
        raise SystemExit('moins de 2 points de crete dans la reference')
    az_r, _, d_r = azel_d(crest, o)
    order = np.argsort(az_r)
    az_r, d_r = az_r[order], d_r[order]
    # plusieurs sommets peuvent partager un azimut: on garde le plus loin,
    # la crete est l'enveloppe arriere du massif
    ua, inv = np.unique(np.round(az_r, 3), return_inverse=True)
    ud = np.array([d_r[inv == i].max() for i in range(len(ua))])
    print(f'profil de {args.ref} — {len(ua)} cretes, azimut '
          f'{ua[0]:.1f} a {ua[-1]:.1f} deg')
    for a, d in zip(ua, ud):
        print(f'    az {a:7.2f}   d {d:7.0f} m')

    # ── application au mesh source ──
    S = mesh[args.src]['world_edges']
    P = np.array([p for e in S for p in e], float)
    az_s, el_s, d_s = azel_d(P, o)
    out_lo = az_s < ua[0]
    out_hi = az_s > ua[-1]

    # Un FACTEUR par azimut, pas une distance absolue. Fixer d = D(az)
    # enverrait tous les sommets d'une meme colonne a la meme profondeur —
    # le pied avant du massif (1494 m) partait a 2400 m et le volume
    # s'ecrasait en rideau, precisement le defaut qu'on corrige. On compare
    # donc crete a crete: k(az) = D_ref(az) / d_crete_source(az), applique
    # ensuite a la distance PROPRE de chaque sommet, ce qui conserve
    # l'epaisseur avant-arriere du massif.
    kk = np.empty(len(ua))
    for i, a in enumerate(ua):
        sel = np.abs(((az_s - a + 180.0) % 360.0) - 180.0) < args.az_win
        if sel.sum() < 3:
            kk[i] = np.nan
            continue
        crest = np.argmax(P[sel][:, 2])
        kk[i] = ud[i] / max(d_s[sel][crest], 1e-9)
    good = ~np.isnan(kk)
    if good.sum() < 2:
        raise SystemExit('pas assez d azimuts communs entre source et reference')
    if (~good).any():
        print(f'  ({int((~good).sum())} azimuts de la reference sans crete source '
              f'en vis-a-vis a +-{args.az_win} deg — ignores)')
    print('\nfacteur crete a crete par azimut:')
    for a, k_ in zip(ua[good], kk[good]):
        print(f'    az {a:7.2f}   x{k_:5.2f}')
    k = np.interp(az_s, ua[good], kk[good])
    D = d_s * k

    # reconstruction: az et el STRICTEMENT conserves, seule d change
    ar = np.radians(az_s)
    er = np.radians(el_s)
    Q = np.empty_like(P)
    Q[:, 0] = o[0] + D * np.sin(ar)
    Q[:, 1] = o[1] + D * np.cos(ar)
    Q[:, 2] = o[2] + D * np.tan(er)

    print(f'\n{args.src}: {len(P)} sommets, azimut {az_s.min():.1f} a {az_s.max():.1f} deg')
    print(f'  facteur applique: {k.min():.2f} a {k.max():.2f} (median {np.median(k):.2f})')
    print(f'  distance   {d_s.min():5.0f}-{d_s.max():5.0f} m  ->  {D.min():5.0f}-{D.max():5.0f} m')
    print(f'  altitude   {P[:,2].min():5.1f}-{P[:,2].max():5.1f} m  ->  '
          f'{Q[:,2].min():5.1f}-{Q[:,2].max():5.1f} m')
    ext = int(out_lo.sum() + out_hi.sum())
    print(f'  sommets hors de l eventail de la reference: {ext} '
          f'({100.0*ext/len(P):.1f} pct) — distance extrapolee a plat')

    # ── LE CONTROLE: la silhouette doit etre invariante ──
    def px(A):
        q = [cam.get_pixel(list(p)) for p in A]
        m_ = np.array([r is not None for r in q])
        return np.array([r for r in q if r is not None], float), m_
    qa, ma = px(P)
    qb, mb = px(Q)
    both = ma & mb
    if both.sum() and ma.sum() == mb.sum():
        err = np.linalg.norm(qa - qb, axis=1)
        print(f'\nCONTROLE silhouette (reprojection dans {args.cam}):')
        print(f'  deplacement median {np.median(err):.4f} px, max {err.max():.4f} px '
              f'sur {both.sum()} sommets')
        if err.max() > 0.5:
            print('  ATTENTION: la silhouette a bouge de plus d un demi-pixel')
    else:
        print(f'\nCONTROLE silhouette: {int(ma.sum())} -> {int(mb.sum())} sommets '
              f'projetables, comparaison impossible telle quelle')

    if not args.apply:
        print('\nDRY-RUN (--apply pour ecrire).')
        return
    idx = {}
    for i, p in enumerate(P):
        idx[tuple(np.round(p, 6))] = i
    new_edges = []
    i = 0
    for _ in S:
        new_edges.append([list(map(float, Q[i])), list(map(float, Q[i + 1]))])
        i += 2
    name = args.out or args.src
    mesh[name] = {'color': mesh[args.src].get('color', '#34d399'),
                  'world_edges': new_edges}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MESH_PATH), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(mesh, f, indent=1, ensure_ascii=True)
    os.replace(tmp, MESH_PATH)
    print(f'\nAPPLIED: "{name}" ({len(new_edges)} aretes)')


if __name__ == '__main__':
    main()
