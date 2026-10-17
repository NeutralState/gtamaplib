#!/usr/bin/env python3
"""fix_ic_citi_meshes.py — re-place InterContinental Miami and Citigroup Center from multi-camera silhouettes. [IC-CITI-V1 2026-10-17]

Alexandre (T4 "Skyline with Ferris Wheel"): both meshes looked off while every other tower fitted.
Silhouette edges read by hand in 4 independent cameras (T4/10 Ferris Wheel, Shitzu Squalo 01 (Bay), Vice City 10,
Biplane v1980; px at 3840 wide):
  - InterContinental: model edges 47-100 px off in all 4 cams, all pointing east. Least-squares plan shift
    (+26.3, -4.3) m brings them to <= 15 px, and puts the triangulated roof landmark "InterContinental Miami (N)"
    (-253.4, -463.2), which was 13 m outside the old V16-2260 footprint, inside it.
  - Citigroup: the V16-2259 footprint is too short to the south (edges up to 90 px off). The 4 triangulated roof
    corners (landmarks Citigroup Center NE/NW/SE/SW) already fit within 13 px, so the mesh is mapped onto them with
    an affine fit of its base quad (floor lines kept).
Usage: python3 tools/fix_ic_citi_meshes.py [--apply]
"""
import json, os, sys, tempfile
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
L = os.path.join(REPO, 'gtamapdata', 'landmarks.json')
TAG = 'IC-CITI-V1 2026-10-17'
IC_SHIFT = (26.3, -4.3)


def main():
    M = json.load(open(P)); LM = json.load(open(L))
    ic, ci = M['InterContinental Miami'], M['Citigroup Center']
    if TAG in ic.get('note', '') or TAG in ci.get('note', ''):
        print('already applied'); return
    E = np.asarray(ic['world_edges'], float); E[..., 0] += IC_SHIFT[0]; E[..., 1] += IC_SHIFT[1]
    ic['world_edges'] = np.round(E, 2).tolist()
    ic['note'] += (' | %s: plan shifted (%+.1f, %+.1f) m from silhouette edges in 4 cams (T4 Ferris Wheel, Shitzu Squalo 01, '
                   'Vice City 10, Biplane v1980): residuals 47-100 -> <= 15 px at 3840; the roof LM (N) now lies inside the footprint.') % ((TAG,) + IC_SHIFT)
    E = np.asarray(ci['world_edges'], float); z0 = E[..., 2].min()
    base = np.unique(np.round(E[(E[..., 2] < z0 + 0.5).all(1)][:, :, :2].reshape(-1, 2), 1), axis=0)
    src = np.array(sorted(base.tolist(), key=lambda q: (np.arctan2(q[1] - base[:, 1].mean(), q[0] - base[:, 0].mean()))))
    dst = np.array([LM['Citigroup Center (%s)' % k]['xyz'][:2] for k in ('SW', 'SE', 'NE', 'NW')])   # same angular order (-pi..pi)
    A = np.c_[src, np.ones(4)]; T, *_ = np.linalg.lstsq(A, dst, rcond=None)
    err = np.abs(A @ T - dst).max()
    xy = np.c_[E[..., :2].reshape(-1, 2), np.ones(E.size // 3)] @ T
    E[..., :2] = xy.reshape(E.shape[0], 2, 2)
    ci['world_edges'] = np.round(E, 2).tolist()
    ci['note'] += (' | %s: footprint mapped (affine, max corner error %.1f m) onto the 4 triangulated roof corners (LMs NE/NW/SE/SW): '
                   'the V16 footprint was ~40 m short to the south; silhouette edges in 3 cams (T4 Ferris Wheel, Shitzu Squalo 01, '
                   'Biplane v1980) go from up to 90 px to <= 13 px at 3840.') % (TAG, err)
    print('IC shift', IC_SHIFT, '| Citi affine corner error %.2f m' % err)
    if '--apply' in sys.argv:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(P))
        with os.fdopen(fd, "w") as f: json.dump(M, f, indent=1, ensure_ascii=True)
        os.replace(tmp, P); print('written', P)


if __name__ == '__main__':
    main()
