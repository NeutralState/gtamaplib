#!/usr/bin/env python3
"""mesh_fit_solve.py — translation + echelle anisotrope d'une emprise de mesh, mesurees par ses aretes laterales. [MESH-FIT-V1 2026-10-06]

Complement de mesh_shift_solve (translation seule): quand un mesh est trop etroit/large dans plusieurs cams (erreur de
largeur = arete droite - arete gauche), on ajuste 4 parametres: translation (tx, ty) et facteurs d'echelle (su, sv) le long
des axes principaux de l'emprise (autour de son centre). Observations: erreurs L et R separees (px a 1280) de chaque cam
(--wide: cams >= 4 volumes juges, leur decalage global soustrait; sinon cams fiables seulement); modele: x extreme gauche /
droite de l'emprise projetee a mi-hauteur. Rapport seulement (rien n'est ecrit); --apply NOM applique au mesh NOM.
Usage: python3 tools/mesh_fit_solve.py "Nom" ["Nom2" ...] [--wide] [--apply]
"""
import json, os, sys, math, shutil
import numpy as np
from scipy.optimize import least_squares

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import common
import mesh_solids as MS
from mesh_pose_audit import basis, WORK

AUD = os.path.join(THIS, 'generated', 'pose_audit.json')
MESHES = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')


def solve(name, A, S, wide):
    if wide: good = {c: o for c, o in A.items() if o['n_judged'] >= 4 and o['fit'] and o['fit']['n'] >= 4}
    else: good = {c: o for c, o in A.items() if o['n_judged'] >= 8 and o['fit'] and abs(o['fit']['shift_px']) <= 1.5}
    so = S[name]
    FP = np.array([q for L in so['layers'] for p in L['polys'] for q in p['outer']], float)
    c0 = FP.mean(0); U, Sv, Vt = np.linalg.svd(FP - c0); ax = Vt                     # axes principaux
    zm = (so['layers'][0]['z0'] + so['layers'][-1]['z1']) / 2
    obs = []
    for cam, o in good.items():
        m = o['meshes'].get(name)
        if not m: continue
        E = {k: m['edges'][k]['d'] - o['fit']['shift_px'] for k in ('L', 'R') if k in m['edges'] and m['edges'][k]['mad'] <= 3}
        if not E: continue
        cm = common.get_cam(cam); B = basis(cm); s = WORK / B[5]
        obs.append((cam, B, s, E))
    if len(obs) < 2: return None

    def ext(B, s, prm):
        tx, ty, su, sv = prm
        loc = (FP - c0) @ ax.T; loc[:, 0] *= su; loc[:, 1] *= sv
        P = c0 + loc @ ax + [tx, ty]
        X = np.c_[P, np.full(len(P), zm)]; D = X - B[0]
        xs = (B[5] / 2 + B[4] * (D @ B[2]) / (D @ B[1])) * s
        return xs.min(), xs.max()

    def res(prm):
        r = []
        for cam, B, s, E in obs:
            l0, r0 = ext(B, s, (0, 0, 1, 1)); l1, r1 = ext(B, s, prm)
            if 'L' in E: r.append((l1 - l0) - E['L'])
            if 'R' in E: r.append((r1 - r0) - E['R'])
        r += [(prm[2] - 1) * 4, (prm[3] - 1) * 4]                                       # prior doux: echelle ~1
        return np.array(r)
    sol = least_squares(res, [0, 0, 1, 1], bounds=([-60, -60, 0.6, 0.6], [60, 60, 1.6, 1.6]))
    r0 = res([0, 0, 1, 1])[:-2]; r1 = res(sol.x)[:-2]
    return {'x': sol.x, 'n_obs': len(r0), 'cams': [o[0] for o in obs], 'rms0': float(np.sqrt(np.mean(r0 ** 2))), 'rms1': float(np.sqrt(np.mean(r1 ** 2))),
            'axes': ax, 'c0': c0, 'dims': [float(np.ptp((FP - c0) @ ax[0])), float(np.ptp((FP - c0) @ ax[1]))]}


def apply(name, r):
    M = json.load(open(MESHES)); e = M[name]; tx, ty, su, sv = r['x']; ax, c0 = r['axes'], r['c0']
    def tf(a):
        loc = (np.array(a[:2]) - c0) @ ax.T; loc[0] *= su; loc[1] *= sv; p = c0 + loc @ ax + [tx, ty]
        return [round(float(p[0]), 3), round(float(p[1]), 3), a[2]]
    e['world_edges'] = [[tf(a) for a in seg] for seg in e['world_edges']]
    e['note'] = e.get('note', '') + (' | MESH-FIT-V1 2026-10-06: plan translated (%+.1f, %+.1f) m and scaled x%.3f / x%.3f along its principal axes '
                                     '(%.0f / %.0f m), measured by the left/right silhouette edges in %d cams (%s), edge rms %.1f -> %.1f px (tools/mesh_fit_solve.py, eye-checked).'
                                     % (tx, ty, su, sv, r['dims'][0], r['dims'][1], len(r['cams']), ', '.join(r['cams'][:6]), r['rms0'], r['rms1']))
    json.dump(M, open(MESHES, 'w'), indent=1, ensure_ascii=True)


def main():
    names = [a for a in sys.argv[1:] if not a.startswith('--')]; wide = '--wide' in sys.argv
    A = json.load(open(AUD)); S = MS.build()
    if '--apply' in sys.argv: shutil.copy(MESHES, MESHES + '.bak_meshfit_1006')
    for n in names:
        r = solve(n, A, S, wide)
        if r is None: print(n, ': pas assez de cams'); continue
        tx, ty, su, sv = r['x']
        print('%-30s cams %d obs %d  t (%+.1f, %+.1f) m  scale x%.3f (%.0f m) x%.3f (%.0f m)  rms %.1f -> %.1f px  [%s]' % (n[:30], len(r['cams']), r['n_obs'], tx, ty, su, r['dims'][0], sv, r['dims'][1], r['rms0'], r['rms1'], ', '.join(r['cams'])))
        if '--apply' in sys.argv: apply(n, r); print('   applique')


if __name__ == '__main__':
    main()
