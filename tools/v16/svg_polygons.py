"""svg_polygons.py — extrait les POLYGONES (anneaux fermes) des empreintes de la V16 SVG, en coordonnees monde.
Contrairement a svg_vertices.py (nuage de sommets pour le snap), on garde la structure: un anneau par sous-chemin (M ... Z),
avec la couleur de remplissage, l'aire et le centroide -> gtamapdata/v16_footprints.json (fills batiments/structures seulement).
usage: V16_X0=16991 svg_polygons.py <svg> <out.json>
"""
import re, sys, os, json, math, numpy as np
svg = open(sys.argv[1]).read(); out = sys.argv[2]
X0, Y0 = int(os.environ.get('V16_X0', '16991')), 11008
KEEP = {'#B0B0B0': 'building', '#797979': 'building', '#8A0000': 'building', '#BCBCBC': 'building_light',
        '#D9D9D9': 'structure', '#C4C4C4': 'structure', '#8C8C8C': 'structure', '#727272': 'structure_dark'}
tok = re.compile(r'<(/?)(g|path|rect|svg|defs|clipPath|mask|symbol)\b([^>]*?)(/?)>', re.S)
attr = lambda s, k: (re.search(r'\b' + k + r'="([^"]*)"', s) or [None, None])[1]
num = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
def parse_transform(s):
    M = np.eye(3)
    for name, args in re.findall(r'(matrix|translate|scale|rotate)\(([^)]*)\)', s or ''):
        a = [float(v) for v in re.split(r'[ ,]+', args.strip()) if v]; T = np.eye(3)
        if name == 'matrix' and len(a) == 6: T = np.array([[a[0], a[2], a[4]], [a[1], a[3], a[5]], [0, 0, 1]])
        elif name == 'translate': T[0, 2] = a[0]; T[1, 2] = a[1] if len(a) > 1 else 0
        elif name == 'scale': T[0, 0] = a[0]; T[1, 1] = a[1] if len(a) > 1 else a[0]
        elif name == 'rotate':
            r = math.radians(a[0]); R = np.array([[math.cos(r), -math.sin(r), 0], [math.sin(r), math.cos(r), 0], [0, 0, 1]])
            T = (np.array([[1, 0, a[1]], [0, 1, a[2]], [0, 0, 1]]) @ R @ np.array([[1, 0, -a[1]], [0, 1, -a[2]], [0, 0, 1]])) if len(a) == 3 else R
        M = M @ T
    return M
def path_rings(d):
    rings = []; cur = np.zeros(2); start = np.zeros(2); cmd = None; ring = []
    for m in re.finditer(r'([MLHVCSQTZmlhvcsqtz])|(' + num.pattern + ')', d):
        if m.group(1): cmd = m.group(1); nums = []
        else: nums.append(float(m.group(2)))
        if not cmd: continue
        rel = cmd.islower(); C = cmd.upper()
        if C == 'Z' and m.group(1):
            if len(ring) >= 3: rings.append(ring)
            ring = []; cur = start.copy(); continue
        need = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'C': 6, 'S': 4, 'Q': 4, 'T': 2}.get(C, 0)
        if need == 0 or len(nums) < need: continue
        a = nums[:need]; nums = nums[need:]
        if C == 'M':
            if len(ring) >= 3: rings.append(ring)
            p = np.array(a); p = cur + p if rel else p; cur = p; start = p.copy(); ring = [p.copy()]; cmd = 'l' if rel else 'L'
        elif C == 'L': p = np.array(a); cur = cur + p if rel else p; ring.append(cur.copy())
        elif C == 'H': cur = np.array([cur[0] + a[0] if rel else a[0], cur[1]]); ring.append(cur.copy())
        elif C == 'V': cur = np.array([cur[0], cur[1] + a[0] if rel else a[0]]); ring.append(cur.copy())
        else: p = np.array(a[-2:]); cur = cur + p if rel else p; ring.append(cur.copy())
    if len(ring) >= 3: rings.append(ring)
    return rings
def area_centroid(P):
    x, y = P[:, 0], P[:, 1]; x1, y1 = np.roll(x, -1), np.roll(y, -1); cross = x * y1 - x1 * y; A = cross.sum() / 2
    if abs(A) < 1e-9: return 0.0, P.mean(0)
    return A, np.array([((x + x1) * cross).sum() / (6 * A), ((y + y1) * cross).sum() / (6 * A)])
stack = [np.eye(3)]; skip = 0; polys = []; idc = 0
for m in tok.finditer(svg):
    close, tag, body, selfclose = m.groups()
    if tag in ('defs', 'clipPath', 'mask', 'symbol'):
        if close: skip = max(0, skip - 1)
        elif not selfclose: skip += 1
        continue
    if tag == 'g':
        if close: stack.pop()
        elif not selfclose: stack.append(stack[-1] @ parse_transform(attr(body, 'transform')))
        continue
    if skip or close or tag == 'svg': continue
    fill = (attr(body, 'fill') or 'none').upper()
    if fill not in KEEP: continue
    M = stack[-1] @ parse_transform(attr(body, 'transform'))
    if tag == 'path':
        d = attr(body, 'd')
        if not d: continue
        rings = path_rings(d)
    else:
        x = float(attr(body, 'x') or 0); y = float(attr(body, 'y') or 0); w = float(attr(body, 'width') or 0); h = float(attr(body, 'height') or 0)
        rings = [[np.array(p) for p in ((x, y), (x + w, y), (x + w, y + h), (x, y + h))]]
    for ring in rings:
        P = np.array([(M @ np.array([p[0], p[1], 1.0]))[:2] for p in ring]); P = np.c_[P[:, 0] - X0, Y0 - P[:, 1]]
        if np.linalg.norm(P[0] - P[-1]) < 1e-6: P = P[:-1]
        # dedoublonner les sommets consecutifs
        keep = [0] + [i for i in range(1, len(P)) if np.linalg.norm(P[i] - P[i - 1]) > 0.05]; P = P[keep]
        if len(P) < 3: continue
        A, c = area_centroid(P)
        polys.append({'id': idc, 'fill': fill, 'cat': KEEP[fill], 'area': round(abs(float(A)), 1), 'centroid': [round(float(c[0]), 2), round(float(c[1]), 2)],
                      'ring': [[round(float(a), 2), round(float(b), 2)] for a, b in P]}); idc += 1
print('polygones:', len(polys), '| par categorie:', {k: sum(1 for p in polys if p['cat'] == k) for k in set(KEEP.values())})
json.dump({'_comment': f'Empreintes vectorielles V16 ({os.path.basename(sys.argv[1])}), monde x=px-{X0}, y={Y0}-py; un anneau par sous-chemin des <path>/<rect> de couleur batiment/structure; area en m2', 'polygons': polys}, open(out, 'w'), ensure_ascii=True)
