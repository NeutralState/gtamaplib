#!/usr/bin/env python3
"""mesh_triangulate.py — les meshes comme outil de triangulation. [MESH-TRI-V1 2026-09-30]

Trois usages (rapport a blanc; --apply n'ecrit que l'usage 1, et seulement les propositions sures):
  1. MONO   landmark clique dans UNE seule cam et qui est un point d'un mesh existant:
            xyz = entree du rayon du clic dans SON mesh (surface = prismes convexes par tranche de hauteur).
  2. CHECK  landmark triangule (2+ cams) qui est un point d'un mesh: distance a la surface/aux aretes
            du mesh -> clic mal etiquete ou pose fausse si grande.
  3. OCCL   clic dont le rayon traverse un AUTRE mesh bien avant d'atteindre le landmark -> impossible.

Garde anti-circularite: un mesh construit a partir du landmark lui-meme (le landmark est a < 1.5 m
d'un sommet du mesh, ou la note du mesh le cite) n'est pas utilise pour ce landmark.
Usage: PYTHONPATH=. python3 tools/mesh_triangulate.py [--apply] [--json out.json]
"""
import json, os, re, sys
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import numpy as np
from scipy.spatial import ConvexHull
import gtamaplib as G

D = lambda f: os.path.join(REPO, 'gtamapdata', f)
SUFFIX = re.compile(r'\s*\([^()]*\)\s*$')


def prisms(edges):
    """mesh -> liste de prismes convexes (poly xy CCW, zlo, zhi) par tranche de hauteur"""
    E = np.asarray(edges, float); z = E[..., 2]; zmin, zmax = z.min(), z.max()
    nb = max(1, min(16, int((zmax - zmin) / 5)))
    out = []
    for b in range(nb):
        lo = zmin + (zmax - zmin) * b / nb; hi = zmin + (zmax - zmin) * (b + 1) / nb
        sel = E[(np.maximum(E[:, 0, 2], E[:, 1, 2]) >= lo - 1e-6) & (np.minimum(E[:, 0, 2], E[:, 1, 2]) <= hi + 1e-6)]
        pts = sel.reshape(-1, 3)[:, :2]
        if len(pts) < 3: continue
        try: h = ConvexHull(pts)
        except Exception: continue
        out.append((pts[h.vertices], lo, hi))
    return out


def ray_prism(o, d, poly, lo, hi):
    """entree du rayon o + t d (t>0) dans le prisme convexe; None sinon (Cyrus-Beck + dalle z)"""
    t0, t1 = 1e-3, 1e9
    if abs(d[2]) < 1e-12:
        if not (lo <= o[2] <= hi): return None
    else:
        a, b = (lo - o[2]) / d[2], (hi - o[2]) / d[2]
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]; e = q - p; nrm = np.array([e[1], -e[0]])   # normale sortante (poly CCW)
        num = -(o[:2] - p) @ nrm; den = d[:2] @ nrm
        if abs(den) < 1e-12:
            if num < 0: return None
            continue
        t = num / den
        if den < 0: t0 = max(t0, t)
        else: t1 = min(t1, t)
        if t0 > t1: return None
    return t0 if t0 <= t1 else None


def first_hit(o, d, P):
    best = None
    for poly, lo, hi in P:
        t = ray_prism(o, d, poly, lo, hi)
        if t is not None and (best is None or t < best): best = t
    return best


SEE_THROUGH = re.compile(r'Bridge|Radio Tower|WDNA|Crane|Conveyor|Cables|Viaduct|Pylon|Antenna', re.I)


def solid_dist(x, P):
    """distance du point au volume (union des prismes); 0 dedans"""
    best = 1e9
    for poly, lo, hi in P:
        n = len(poly); inside = True; dxy = 1e9
        for i in range(n):
            p, q = poly[i], poly[(i + 1) % n]; e = q - p; nrm = np.array([e[1], -e[0]]) / max(np.linalg.norm(e), 1e-9)
            sd = (x[:2] - p) @ nrm
            if sd > 0: inside = False
            t = np.clip((x[:2] - p) @ e / max(e @ e, 1e-9), 0, 1); dxy = min(dxy, np.linalg.norm(p + e * t - x[:2]))
        h = 0.0 if inside else dxy; vz = max(lo - x[2], 0, x[2] - hi)
        best = min(best, float(np.hypot(h, vz)))
    return best


def seg_dist(x, E):
    a = E[:, 0]; b = E[:, 1]; ab = b - a; t = np.clip(((x - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-9), 0, 1)
    return float(np.min(np.linalg.norm(a + ab * t[:, None] - x, axis=1)))


def main():
    C = json.load(open(D('cameras.json'))); P = json.load(open(D('pixels.json'))); L = json.load(open(D('landmarks.json')))
    M = json.load(open(D('building_meshes_procedural.json')))
    A = set(json.load(open(os.path.join(THIS, 'audit', 'anchor_truth_xy.json')))['anchors'])
    ok = lambda n: n in C and C[n].get('xyz') and C[n].get('fov') and C[n]['fov'][0] and C[n].get('size')
    PR = {k: prisms(v['world_edges']) for k, v in M.items() if v.get('world_edges')}
    EG = {k: np.asarray(v['world_edges'], float) for k, v in M.items() if v.get('world_edges')}
    VX = {k: np.unique(EG[k].reshape(-1, 3).round(2), axis=0) for k in EG}
    CEN = {k: EG[k].reshape(-1, 3).mean(0) for k in EG}

    norm = lambda s_: re.sub(r'[^a-z0-9]', '', s_.lower())
    NM = {norm(k): k for k in M}

    def own_mesh(lm):
        r = lm
        for _ in range(4):                                   # 'X (Tank) (A) (R)' -> 'X (Tank A)'
            if norm(r) in NM: return NM[norm(r)]
            r2 = SUFFIX.sub('', r).strip()
            if r2 == r: break
            r = r2
        r = lm
        for _ in range(4):
            if r in M: return r
            r2 = SUFFIX.sub('', r).strip()
            if r2 == r: return None
            r = r2
        return r if r in M else None

    def ray(n, uv):
        c = C[n]; q = G.get_q(c['ypr']); fov = (c['fov'][0], G.get_vfov(c['fov'][0], tuple(c['size'])))
        d = np.array(G.get_pixel_direction(tuple(uv), q, fov, tuple(c['size'])), float)
        return np.array(c['xyz'], float), d / np.linalg.norm(d)

    clicks = {}
    for n, p in P.items():
        if isinstance(p, dict):
            for k in p:
                if ok(n): clicks.setdefault(k, []).append(n)
    R = {'mono': [], 'check': [], 'occl': []}
    for k, cs in clicks.items():
        v = L.get(k)
        if not isinstance(v, dict): continue
        m = own_mesh(k); xyz = np.array(v['xyz'], float) if v.get('xyz') else None
        circular = m is not None and ((xyz is not None and np.min(np.linalg.norm(VX[m] - xyz, axis=1)) < 1.5) or k in (M[m].get('note') or ''))
        # 1. MONO
        if m and len(cs) == 1 and k not in A:
            o, d = ray(cs[0], P[cs[0]][k]); t = first_hit(o, d, PR[m])
            if t is not None:
                X = o + d * t
                occ = [(mm, first_hit(o, d, PR[mm])) for mm in PR if mm != m and not SEE_THROUGH.search(mm) and np.linalg.norm(CEN[mm][:2] - o[:2]) < t + 50]
                occ = [(mm, tt) for mm, tt in occ if tt is not None and tt < t - 5]
                R['mono'].append({'lm': k, 'mesh': m, 'cam': cs[0], 'xyz_new': X.round(2).tolist(), 'xyz_old': None if xyz is None else xyz.round(2).tolist(),
                                  'move_m': None if xyz is None else round(float(np.linalg.norm(X - xyz)), 1), 'dist_m': round(float(t), 0),
                                  'circular': bool(circular), 'occluded_by': occ[0][0] if occ else None, 'mesh_prov': (M[m].get('note') or '')[:70]})
        # 2. CHECK
        if m and len(cs) >= 2 and xyz is not None:
            R['check'].append({'lm': k, 'mesh': m, 'n_cams': len(cs), 'dist_to_mesh_m': round(solid_dist(xyz, PR[m]), 1), 'circular': bool(circular)})
        # 3. OCCL
        if xyz is not None:
            for n in cs:
                o, d = ray(n, P[n][k]); tl = float(np.linalg.norm(xyz - o))
                for mm in PR:
                    if SEE_THROUGH.search(mm): continue
                    if (m and norm(mm).startswith(norm(m)[:12])): continue           # meme batiment (podium, annexe)
                    if mm == m or np.linalg.norm(CEN[mm][:2] - o[:2]) > tl: continue
                    if np.linalg.norm(CEN[mm][:2] - o[:2]) < 30: continue                 # mesh sur lequel la cam est posee
                    t = first_hit(o, d, PR[mm])
                    if t is not None and t < tl - 25:
                        # robuste: bloque encore avec le clic decale de +-3 px (pas un frolement de bord)
                        uv = np.array(P[n][k], float)
                        if not all((lambda oo, dd: (first_hit(oo, dd, PR[mm]) or 1e9) < tl - 25)(*ray(n, uv + off)) for off in ([3, 0], [-3, 0], [0, 3], [0, -3])): continue
                        R['occl'].append({'lm': k, 'cam': n, 'blocked_by': mm, 'hit_m': round(t, 0), 'lm_m': round(tl, 0)}); break
    return R, L


if __name__ == '__main__':
    R, L = main()
    mono = R['mono']; good = [r for r in mono if not r['circular'] and not r['occluded_by']]
    print('== 1. MONO (xyz depuis une seule cam par le mesh): %d candidats, %d surs (non circulaires, non occultes)' % (len(mono), len(good)))
    for r in sorted(mono, key=lambda r: (r['circular'], r['occluded_by'] is not None, -(r['move_m'] or 1e9))):
        flag = 'CIRCULAIRE' if r['circular'] else ('OCCULTE par ' + r['occluded_by'] if r['occluded_by'] else 'ok')
        print('   %-42s %-34s %6s m  -> %-28s (%s)' % (r['lm'][:42], r['cam'][:34], '—' if r['move_m'] is None else r['move_m'], r['xyz_new'], flag))
    ch = sorted(R['check'], key=lambda r: -r['dist_to_mesh_m'])
    bad = [r for r in ch if r['dist_to_mesh_m'] > 8 and not r['circular']]
    print('\n== 2. CHECK (triangules 2+ cams vs leur mesh): %d, dont %d a > 8 m de leur mesh (hors circulaires)' % (len(ch), len(bad)))
    for r in bad[:25]: print('   %-45s mesh %-32s %5.1f m (%d cams)' % (r['lm'][:45], r['mesh'][:32], r['dist_to_mesh_m'], r['n_cams']))
    oc = R['occl']
    print('\n== 3. OCCL (clic derriere un autre mesh): %d' % len(oc))
    for r in oc[:25]: print('   %-40s %-30s bloque par %-30s a %.0f m (LM a %.0f m)' % (r['lm'][:40], r['cam'][:30], r['blocked_by'][:30], r['hit_m'], r['lm_m']))
    if '--json' in sys.argv: json.dump(R, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
    if '--apply' in sys.argv:
        import shutil; shutil.copy(D('landmarks.json'), D('landmarks.json') + '.bak_meshtri')
        for r in good:
            v = L[r['lm']]; v['xyz'] = r['xyz_new']
            v['method'] = 'MESH-TRI-V1 2026-09-30: rayon du clic %s x surface du mesh %s (%.0f m); ancien %s | ' % (r['cam'], r['mesh'], r['dist_m'], r['xyz_old']) + (v.get('method') or '')
        json.dump(L, open(D('landmarks.json'), 'w'), indent=2, ensure_ascii=True); print('APPLIED', len(good))
