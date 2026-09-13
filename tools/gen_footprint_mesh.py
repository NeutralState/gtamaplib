#!/usr/bin/env python3
"""gen_footprint_mesh.py — meshs proceduraux par EXTRUSION des empreintes vectorielles V16. [FOOTPRINT-MESH-V1 2026-09-13]

Pour chaque batiment: coins triangules (landmarks '<B> (...)') -> polygone V16 (gtamapdata/v16_footprints.json,
tools/v16/svg_polygons.py) qui contient le plus de coins (a defaut le plus proche des coins, < 6 m) ->
prisme: anneau au sol (heightmap au centroide), anneau au toit (mediane des z de coins a moins de 10 m du max, les
annexes basses sont ignorees), aretes verticales a chaque sommet, anneaux intermediaires tous les --ring m.

Limites connues: la V16 dessine l'EMPREINTE AU SOL; quand la tour est en retrait sur un podium (Three Tequesta Point,
Southeast Financial Center: coins de toit a 15-17 m du bord), le prisme est trop large en haut -> refuse par defaut
(--max-retreat). Les toits ne sont pas modelises (pas de couronnement, pas d'helipad).

Usage: PYTHONPATH=. /usr/local/bin/python3 tools/gen_footprint_mesh.py "Marina Blue" "One Biscayne Tower" ...
       [--out draft.json] [--apply] [--ring 25] [--max-retreat 8] [--poly ID] [--z-roof Z]
"""
import argparse, json, os, sys
import numpy as np
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
from horizon_resect import ground

COLORS = ['#38bdf8', '#a3e635', '#f472b6', '#fbbf24', '#c084fc', '#34d399', '#fb7185', '#facc15', '#60a5fa', '#f97316']

def inside(R, p):
    x, y = p; n = len(R); c = False
    for i in range(n):
        x1, y1 = R[i]; x2, y2 = R[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c

def dist_edge(R, p):
    d = []
    for a, b in zip(R, np.roll(R, -1, axis=0)):
        ab = b - a; t = np.clip(np.dot(p - a, ab) / max(np.dot(ab, ab), 1e-9), 0, 1); d.append(np.linalg.norm(p - (a + t * ab)))
    return min(d)

def corners_of(L, b):
    return [(k, np.array(v['xyz'], float)) for k, v in L.items()
            if (k == b or k.startswith(b + ' (')) and isinstance(v, dict) and v.get('xyz') and v['xyz'][0] is not None]

def pick_polygon(F, cent, P, forced=None):
    if forced is not None:
        return forced, None
    near = np.where(np.linalg.norm(cent - P.mean(0), axis=1) < 150)[0]; best = None
    for i in near:
        R = np.array(F[i]['ring']); ins = sum(inside(R, p) for p in P); ds = [dist_edge(R, p) for p in P]
        key = (ins, -float(np.median(ds)))
        if (ins or min(ds) < 6) and (best is None or key > best[0]): best = (key, i, ins, float(np.median(ds)))
    return (best[1], best) if best else (None, None)

def build(b, F, cent, L, args, color):
    C = corners_of(L, b)
    if not C: return None, f'{b}: aucun coin triangule'
    P = np.array([c[1][:2] for c in C]); Z = np.array([c[1][2] for c in C])
    pid, info = pick_polygon(F, cent, P, args.poly)
    if pid is None: return None, f'{b}: aucun polygone V16 ne contient/borde les coins'
    R = np.array(F[pid]['ring'])
    ds = [dist_edge(R, p) for p in P]; retreat = float(np.median(ds))
    if retreat > args.max_retreat and args.poly is None:
        return None, f'{b}: coins de toit a {retreat:.1f} m du bord du polygone {pid} (podium ?) > --max-retreat {args.max_retreat}'
    z_roof = args.z_roof if args.z_roof is not None else float(np.median(Z[Z >= Z.max() - 10]))
    cx, cy = F[pid]['centroid']; z_ground = float(ground(cx, cy))
    if z_ground < -100: z_ground = 0.0
    def ring(z): return [[[float(a[0]), float(a[1]), z], [float(b_[0]), float(b_[1]), z]] for a, b_ in zip(R, np.roll(R, -1, axis=0))]
    edges = ring(z_ground) + ring(z_roof)
    for v in R: edges.append([[float(v[0]), float(v[1]), z_ground], [float(v[0]), float(v[1]), z_roof]])
    z = z_ground + args.ring
    while z < z_roof - 1: edges += ring(z); z += args.ring
    note = (f'FOOTPRINT-MESH-V1 {args.date}: extrusion de l\'empreinte V16 (polygone {pid}, {len(R)} sommets, {F[pid]["area"]:.0f} m2), '
            f'sol {z_ground:.1f} (heightmap), toit {z_roof:.1f} (mediane de {int((Z >= Z.max() - 10).sum())} coins), '
            f'coins a {retreat:.1f} m du bord (mediane); anneaux tous les {args.ring} m')
    return {'color': color, 'world_edges': edges, 'note': note, '_credit': 'empreinte: GTA VI Community Mapping Project (V16 SVG); hauteurs: triangulation gtamaplib'}, \
           f'{b}: polygone {pid} ({len(R)} sommets, {F[pid]["area"]:.0f} m2), coins dedans {info[2] if info else "?"}/{len(P)}, retrait {retreat:.1f} m, sol {z_ground:.1f}, toit {z_roof:.1f}, {len(edges)} aretes'

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('buildings', nargs='+'); ap.add_argument('--out', default=None); ap.add_argument('--apply', action='store_true')
    ap.add_argument('--ring', type=float, default=25.0); ap.add_argument('--max-retreat', type=float, default=8.0); ap.add_argument('--poly', type=int, default=None)
    ap.add_argument('--z-roof', type=float, default=None); ap.add_argument('--date', default='2026-09-13'); args = ap.parse_args()
    F = json.load(open(os.path.join(REPO, 'gtamapdata', 'v16_footprints.json')))['polygons']; cent = np.array([p['centroid'] for p in F])
    L = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    mp = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json'); M = json.load(open(mp))
    out = {}
    for i, b in enumerate(args.buildings):
        mesh, msg = build(b, F, cent, L, args, COLORS[(len(M) + i) % len(COLORS)]); print(('OK  ' if mesh else 'SKIP') + ' ' + msg)
        if mesh: out[b] = mesh
    if args.out: json.dump(out, open(args.out, 'w'), ensure_ascii=True); print('brouillon ->', args.out, list(out))
    if args.apply and out:
        M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique dans', mp, '->', len(M), 'meshs')

if __name__ == '__main__':
    main()
