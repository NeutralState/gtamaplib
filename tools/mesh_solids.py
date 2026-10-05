#!/usr/bin/env python3
"""mesh_solids.py — volumes pleins (prismes empiles) reconstruits depuis les aretes des meshes. [SOLIDS-V1 2026-10-04]

Les meshes proceduraux ne sont que des aretes (fil de fer). Pour un rendu plein (onglet 3D: eclairage, ombres
portees, fenetres la nuit), chaque mesh « batiment » est converti en champ de hauteur 2.5D:
  1. les aretes HORIZONTALES sont groupees par niveau z; a chaque niveau, les contours fermes (rasterises a
     0.25-0.5 m, regions enfermees par remplissage depuis le bord) donnent l'emprise de ce niveau;
  2. hauteur(x,y) = plus haut niveau dont l'emprise couvre (x,y); sol = z min du mesh;
  3. le champ est decoupe en prismes: pour chaque hauteur distincte h_k, region (hauteur >= h_k) extrudee de
     h_{k-1} a h_k; les niveaux qui ne changent pas l'emprise (bandes d'etage) sont fusionnes.
Ce qui n'est pas horizontal (toits a pans, domes, voutes, tabliers en pente) reste en fil de fer par-dessus.
Exclus (le champ de hauteur les remplirait a tort): ponts/viaducs/bretelles, reliefs, stades (cuvette),
chateaux d'eau/antennes/mats/grues, portiques/peages (arches), et tout mesh de plus de 450 m d'emprise.

FACES-V1 (2026-10-04): en plus des prismes, les FACES du fil de fer sont reconstruites: boucles fermees planes de
3 ou 4 aretes (sommets fusionnes a 5 cm, quadrilateres sans diagonale, tolerance de planeite ~10 cm). Avec un prisme,
on ne garde que les faces inclinees (toits a pans, domes, voutes) et ce qui depasse au-dessus du volume (pignons,
couronnes, edicules); sans prisme (structures exclues: chateaux d'eau, peage, stade, ponts...), toutes les faces.
Sortie: {name: {color, zmin, zmax, layers: [{z0, z1, polys: [{outer: [[x,y],...], holes: [...]}]}], fv: [x,y,z,...], ff: [i,j,k,...]}}
Usage: python3 tools/mesh_solids.py [--out f.json] [--only "Nom"] [--publish]
"""
import json, os, sys
import numpy as np
import cv2

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
MESHES = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
CACHE = os.path.join(THIS, 'generated', 'mesh_solids.json')
NO_FACES = ('Hill', 'Mountain', 'Ridge', 'Massif', 'Relief', 'Terrain', 'Fence', 'Cables')   # reliefs: le terrain 3D existe deja
# structures SANS prisme qui ont droit a des faces pleines (volumes massifs); tout le reste (antennes radio, grues, portiques,
# grande roue, treillis, ponts, viaducs, bretelles) reste en fil de fer (Alexandre 2026-10-04: « fait pas plein sur les radio tower »)
FACE_ONLY_OK = ('Water Tower', 'Silo', 'Smokestack', 'Stack', 'Tank', 'Toll Plaza', 'Chimney')
MAX_TRIS = 40000
EXCLUDE = ('Bridge', 'Viaduct', 'Ramp', 'Interchange', 'Causeway', 'Overpass', 'Hill', 'Mountain', 'Ridge', 'Massif',
           'Relief', 'Terrain', 'Stadium', 'Water Tower', 'Antenna', 'Mast', 'Crane', 'Pylon', 'Observation Wheel', 'Portique',
           'Gantry', 'Toll', 'Billboard', 'Sign', 'Fence', 'Cables', 'Roller Coaster', 'Coaster', 'Pier', 'Dock',
           'Stilts', 'Chimney', 'Stack', 'Silo', 'Lighthouse', 'FM', 'Tower (Radio)', 'Prison Towers')
MAX_EXTENT = 450.0


def _solid_ok(name):
    return not any(w.lower() in name.lower() for w in EXCLUDE)


def solidify(edges):
    E = np.asarray(edges, float)
    if E.ndim != 3 or len(E) < 3: return None
    zmin, zmax = float(E[..., 2].min()), float(E[..., 2].max())
    hz = E[np.abs(E[:, 0, 2] - E[:, 1, 2]) < 0.05]
    if len(hz) < 3: return None
    P = hz[..., :2].reshape(-1, 2); x0, y0 = P.min(0) - 2; x1, y1 = P.max(0) + 2
    ext = max(x1 - x0, y1 - y0)
    if ext > MAX_EXTENT: return None
    res = 0.25 if ext < 160 else 0.5
    W, H = int(np.ceil((x1 - x0) / res)) + 1, int(np.ceil((y1 - y0) / res)) + 1
    toPx = lambda p: (int(round((p[0] - x0) / res)), int(round((y1 - p[1]) / res)))
    levels = {}
    for a, b in hz:
        levels.setdefault(round(float(a[2]), 1), []).append((a, b))
    Hf = np.full((H, W), -1e9, np.float32)
    for z, segs in levels.items():
        m = np.zeros((H, W), np.uint8)
        for a, b in segs: cv2.line(m, toPx(a), toPx(b), 255, 1)
        if m.sum() == 0: continue
        ff = m.copy(); mask = np.zeros((H + 2, W + 2), np.uint8)
        cv2.floodFill(ff, mask, (0, 0), 128)             # exterieur (le bord est libre: marge de 2 m)
        inside = (ff != 128)                               # interieur + traits
        n, lab, st, _ = cv2.connectedComponentsWithStats(inside.astype(np.uint8), 4)
        keep = np.zeros_like(inside)
        for i in range(1, n):
            if st[i, cv2.CC_STAT_AREA] * res * res >= 4.0 and (st[i, cv2.CC_STAT_AREA] - (lab == i)[m > 0].sum()) * res * res >= 2.0:
                keep |= lab == i
        Hf[keep] = np.maximum(Hf[keep], z)
    if (Hf > -1e8).sum() * res * res < 4.0: return None
    hs = sorted(set(np.round(Hf[Hf > -1e8], 1).tolist()))
    hs = [h for h in hs if h > zmin + 0.5]
    if not hs: return None
    layers, start = [], zmin
    masks = [(Hf >= h - 0.05).astype(np.uint8) for h in hs]
    for k, h in enumerate(hs):
        if k + 1 < len(hs):
            diff = int(masks[k].sum()) - int(masks[k + 1].sum())
            if diff * res * res < max(2.0, 0.01 * masks[k].sum() * res * res): continue   # emprise inchangee: on fusionne
        cs, hier = cv2.findContours(masks[k], cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        polys = []
        if hier is not None:
            hier = hier[0]
            for i, c in enumerate(cs):
                if hier[i][3] != -1: continue                  # trou: rattache a son parent ci-dessous
                if cv2.contourArea(c) * res * res < 4.0: continue
                out = cv2.approxPolyDP(c, 0.35 / res, True).reshape(-1, 2)
                if len(out) < 3: continue
                holes = []
                j = hier[i][2]
                while j != -1:
                    if cv2.contourArea(cs[j]) * res * res >= 6.0:
                        hh = cv2.approxPolyDP(cs[j], 0.35 / res, True).reshape(-1, 2)
                        if len(hh) >= 3: holes.append(hh)
                    j = hier[j][0]
                w = lambda a: [[round(float(x0 + u * res), 2), round(float(y1 - v * res), 2)] for u, v in a]
                polys.append({'outer': w(out), 'holes': [w(hh) for hh in holes]})
        if polys: layers.append({'z0': round(start, 2), 'z1': round(float(h), 2), 'polys': polys})
        start = float(h)
    if not layers: return None
    def top_at(x, y):
        u, v = int(round((x - x0) / res)), int(round((y1 - y) / res))
        if 0 <= u < W and 0 <= v < H:
            h = float(Hf[v, u])
            return h if h > -1e8 else None
        return None
    return {'zmin': round(zmin, 2), 'zmax': round(zmax, 2), 'layers': layers, '_top': top_at}


def cycle_faces(edges, top_at=None):
    """faces planes (triangles + quadrilateres sans diagonale) du graphe d'aretes -> (sommets [n,3], triangles [m,3])."""
    E = np.asarray(edges, float)
    if E.ndim != 3 or len(E) < 3: return None
    P = E.reshape(-1, 3); key = np.round(P / 0.05).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    V = np.zeros((len(uniq), 3)); cnt = np.zeros(len(uniq))
    np.add.at(V, inv, P); np.add.at(cnt, inv, 1); V /= cnt[:, None]
    es = set()
    for i in range(0, len(inv), 2):
        a, b = int(inv[i]), int(inv[i + 1])
        if a != b: es.add((min(a, b), max(a, b)))
    if len(es) > 60000: return None
    adj = {}
    for a, b in es: adj.setdefault(a, set()).add(b); adj.setdefault(b, set()).add(a)
    has = lambda a, b: (min(a, b), max(a, b)) in es
    seen, tris = set(), []
    def keep(idx):
        Q = V[list(idx)]
        n = np.cross(Q[1] - Q[0], Q[2] - Q[0]); ln = np.linalg.norm(n)
        if ln < 1e-3: return False
        n /= ln
        if len(Q) == 4:
            if abs(np.dot(Q[3] - Q[0], n)) > 0.10 + 0.01 * np.linalg.norm(Q[2] - Q[0]): return False
        if top_at is None: return True
        nz = abs(n[2]); c = Q.mean(0); t = top_at(c[0], c[1])
        if nz > 0.985: return False                                   # horizontal: les chapeaux des prismes s'en chargent
        if nz < 0.15: return t is None or c[2] > t + 0.3               # vertical: seulement au-dessus du volume / hors emprise
        return t is None or c[2] > t - 0.6                             # incline: toits, domes, voutes
    for a, b in es:
        for c in adj[b]:
            if c == a: continue
            if has(a, c):
                k = tuple(sorted((a, b, c)))
                if k not in seen:
                    seen.add(k)
                    if keep((a, b, c)): tris.append((a, b, c))
            for d in adj[c]:
                if d in (a, b) or not has(d, a): continue
                if has(a, c) or has(b, d): continue                    # diagonale presente: les triangles suffisent
                k = tuple(sorted((a, b, c, d)))
                if k in seen: continue
                seen.add(k)
                if keep((a, b, c, d)): tris += [(a, b, c), (a, c, d)]
        if len(tris) > MAX_TRIS: return None
    if not tris: return None
    T = np.array(tris, np.int64); used = np.unique(T)
    remap = -np.ones(len(V), np.int64); remap[used] = np.arange(len(used))
    return V[used], remap[T]


def build(only=None):
    M = json.load(open(MESHES)); out = {}
    for name, m in M.items():
        if only and name != only: continue
        edges = m.get('world_edges') or []
        s = solidify(edges) if _solid_ok(name) else None
        f = None
        if not any(w.lower() in name.lower() for w in NO_FACES) and (s is not None or any(w.lower() in name.lower() for w in FACE_ONLY_OK)):
            try: f = cycle_faces(edges, s['_top'] if s else None)
            except Exception: f = None
        if s is None and f is None: continue
        if s is None:
            Pz = np.asarray(edges, float)[..., 2]; s = {'zmin': round(float(Pz.min()), 2), 'zmax': round(float(Pz.max()), 2), 'layers': []}
        s.pop('_top', None)
        if f is not None:
            s['fv'] = [round(float(v), 2) for v in f[0].reshape(-1)]; s['ff'] = [int(i) for i in f[1].reshape(-1)]
        s['color'] = m.get('color', '#9ca3af')
        if m.get('facade'): s['facade'] = m['facade']          # [FACADES-V1] style de facade lu sur les frames (optionnel)
        out[name] = s
    return out


def cached():
    """solides a jour (recalcules si le JSON des meshes est plus recent que le cache)."""
    if os.path.exists(CACHE) and os.path.getmtime(CACHE) >= os.path.getmtime(MESHES) and os.path.getmtime(CACHE) >= os.path.getmtime(__file__):
        return json.load(open(CACHE))
    out = build(); os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(out, open(CACHE, 'w'), separators=(',', ':'))
    publish(out); return out


def publish(out=None):
    """copie servie par la route statique /threejs/ (marche sans redemarrer le serveur; ignoree par git)."""
    out = out if out is not None else build()
    json.dump(out, open(os.path.join(THIS, 'threejs', '_mesh_solids.json'), 'w'), separators=(',', ':'))
    return out


if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    import time; t = time.time(); out = build(only)
    print('%d solides en %.1fs' % (len(out), time.time() - t))
    for k, v in list(out.items())[:8]: print('  %-40s %d couches %d faces' % (k[:40], len(v['layers']), len(v.get('ff', [])) // 3))
    print('faces totales: %d triangles' % sum(len(v.get('ff', [])) // 3 for v in out.values()))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--publish' in sys.argv and not only: publish(out); print('publie: tools/threejs/_mesh_solids.json')
