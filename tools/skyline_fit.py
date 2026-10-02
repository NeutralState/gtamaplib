#!/usr/bin/env python3
"""skyline_fit.py — controle d'un mesh par sa LIGNE DE CIEL, en pixels. [SKYLINE-FIT-V1 2026-10-01]

Remplace le « MESH FIT 0-100 » (contraste de bords: bruite, illisible). Ici on mesure une chose simple et verifiable:
pour chaque colonne ou le haut d'un mesh se decoupe sur le ciel, l'ecart vertical (px) entre le haut du mesh projete et la
frontiere ciel/non-ciel de l'image (segmentation SegFormer ADE20K, classe 2 = sky). Plus les bords gauche/droit du sommet.
Sortie par mesh: n colonnes, ecart median signe (+ = mesh trop haut), |ecart| median, et un verdict:
  OK (<= 4 px), A REVOIR (4-12 px), FAUX (> 12 px), — (pas de ciel au-dessus / occulte / brume).
Usage: PYTHONPATH=. python3 tools/skyline_fit.py "<cam>" [--json out] [--png out.png]
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import common
from edgefit_core import _project_pts
from scipy.spatial import ConvexHull
MESHES = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
SKY = 2


def _mask_top(cam, W, H, edges):
    """haut projete du mesh par colonne (union des enveloppes par troncon vertical/z) -> dict u -> v_top, et masque."""
    E = np.asarray(edges, float); z = E[..., 2]; zmin, zmax = z.min(), z.max(); nb = max(1, min(12, int((zmax - zmin) / 6)))
    m = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(m)
    for b in range(nb):
        lo = zmin + (zmax - zmin) * b / nb; hi = zmin + (zmax - zmin) * (b + 1) / nb
        sel = [ab for ab in edges if max(ab[0][2], ab[1][2]) >= lo - 1e-6 and min(ab[0][2], ab[1][2]) <= hi + 1e-6]
        pr = []
        for a, bb in sel:
            p, q = cam.get_pixel(tuple(a)), cam.get_pixel(tuple(bb))
            if p is not None and q is not None: pr += [p, q]
        if len(pr) < 3: continue
        A = np.array(pr)
        try: dr.polygon([tuple(map(float, p)) for p in A[ConvexHull(A).vertices]], fill=1)
        except Exception: pass
    return np.asarray(m, bool)


def run(cam_name, state=None, meshes=None, dmax=6000):
    M = meshes or json.load(open(MESHES)); C = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))[cam_name]
    W, H = C['size']; cam = common.get_cam(cam_name, state); o = np.array(cam.xyz, float)
    cls = np.load(os.path.join(THIS, 'generated', 'seg_veg', cam_name.replace('/', '_') + '_cls.npy'))
    if cls.shape != (H, W): cls = np.asarray(Image.fromarray(cls.astype(np.uint8)).resize((W, H), Image.NEAREST))
    sky = ndimage.binary_opening(cls == SKY, iterations=2)
    # premiere ligne non-ciel par colonne (depuis le haut, apres une bande de ciel)
    cand = []
    for name, v in M.items():
        e = v.get('world_edges') or []
        if not e: continue
        P = np.asarray(e, float).reshape(-1, 3); d = np.hypot(*(P[:, :2].mean(0) - o[:2]))
        if d < 40 or d > dmax: continue
        q = cam.get_pixel(tuple(P[np.argmax(P[:, 2])]))
        if q is None: continue
        cand.append((d, name, e))
    cand.sort()
    occ = np.zeros((H, W), bool); res = {}
    for d, name, e in cand:                                  # du plus proche au plus loin: les proches occultent
        mk = _mask_top(cam, W, H, e)
        if mk.sum() < 30: continue
        cols = np.nonzero(mk.any(0))[0]
        top = np.array([np.argmax(mk[:, u]) for u in cols])
        offs = []
        for u, vt in zip(cols, top):
            if occ[:vt + 1, u].any(): continue                                   # un mesh plus proche depasse au-dessus: pas la ligne de ciel
            # chercher la frontiere ciel -> non-ciel dans +-40 px autour du haut du mesh
            v0, v1 = max(1, vt - 40), min(H - 1, vt + 40)
            col = sky[v0:v1, u]
            if col.size < 5 or not col[:3].all(): continue              # pas de ciel au-dessus: colonne non mesurable
            tr = np.nonzero(col[:-1] & ~col[1:])[0]
            if not len(tr): continue
            vb = v0 + tr[0] + 1
            if sky[:vb, u].mean() < 0.97: continue                       # la frontiere doit etre LA ligne de ciel (rien au-dessus)
            offs.append((vt - vb) * 1920.0 / W)                          # px normalises 1920
        occ |= mk
        if len(offs) < 6: res[name] = {'n': len(offs), 'verdict': '—'}; continue
        offs = np.array(offs, float); med = float(np.median(offs)); mad = float(np.median(np.abs(offs)))
        verdict = 'OK' if mad <= 4 else ('A REVOIR' if mad <= 12 else 'FAUX')
        res[name] = {'n': int(len(offs)), 'bias_px': round(med, 1), 'abs_px': round(mad, 1),
                     'abs_arcmin': round(mad * (cam.fov[0] or 50) / 1920 * 60, 1), 'verdict': verdict, 'dist_m': int(d)}
    meas = [r for r in res.values() if r['verdict'] != '—']
    summ = {'n_mesures': len(meas), 'n_ok': sum(r['verdict'] == 'OK' for r in meas),
            'mediane_px': round(float(np.median([r['abs_px'] for r in meas])), 1) if meas else None}
    return {'cam': cam_name, 'resume': summ, 'meshes': res}


if __name__ == '__main__':
    cam = sys.argv[1]; r = run(cam)
    print('== %s  mesures %d, OK %d, mediane %s px' % (cam, r['resume']['n_mesures'], r['resume']['n_ok'], r['resume']['mediane_px']))
    for k, v in sorted(r['meshes'].items(), key=lambda kv: (kv[1]['verdict'] == '—', -(kv[1].get('abs_px') or 0))):
        if v['verdict'] != '—': print('   %-42s %-9s |ecart| %5.1f px  biais %+5.1f px  (%d col, %d m)' % (k[:42], v['verdict'], v['abs_px'], v['bias_px'], v['n'], v['dist_m']))
    if '--json' in sys.argv: json.dump(r, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
