"""svg_strokes.py — extrait les POLYLIGNES tracees en traits (stroke) de la V16 SVG dans une fenetre monde, en coordonnees monde.
Les tours a l'interieur d'un ilot sont souvent dessinees en traits fins (#797979) et pas en polygones remplis:
ce sont ces anneaux qu'il faut pour le plan d'un mesh. [2026-09-26]
usage: V16_X0=16991 svg_strokes.py <svg> <x0> <x1> <y0> <y1> <out.json>  -> {"strokes":[{"id","color","width","closed","area","centroid","ring":[[x,y],...]}]}
"""
import re, sys, os, json, math, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
svg = open(sys.argv[1]).read(); x0, x1, y0, y1 = [float(a) for a in sys.argv[2:6]]; out = sys.argv[6]
X0, Y0 = int(os.environ.get('V16_X0', '16991')), 11008
tok = re.compile(r'<(/?)(g|path|rect|svg|defs|clipPath|mask|symbol|polyline|polygon|line|ellipse|circle)\b([^>]*?)(/?)>', re.S)
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
def bez(p0, p1, p2, p3, n=8):
    t = np.linspace(0, 1, n + 1)[1:, None]; return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3
def path_polylines(d):
    """liste de (points, closed) par sous-chemin; courbes cubiques/quadratiques echantillonnees."""
    res = []; cur = np.zeros(2); start = np.zeros(2); cmd = None; pts = []; prev_c = None
    def flush(closed):
        nonlocal pts
        if len(pts) >= 2: res.append((np.array(pts), closed))
        pts = []
    for m in re.finditer(r'([MLHVCSQTAZmlhvcsqtaz])|(' + num.pattern + ')', d):
        if m.group(1): cmd = m.group(1); nums = []
        else: nums.append(float(m.group(2)))
        if not cmd: continue
        rel = cmd.islower(); C = cmd.upper()
        if C == 'Z' and m.group(1): flush(True); cur = start.copy(); continue
        need = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'C': 6, 'S': 4, 'Q': 4, 'T': 2, 'A': 7}.get(C, 0)
        if need == 0 or len(nums) < need: continue
        a = nums[:need]; nums = nums[need:]
        if C == 'M':
            flush(False); p = np.array(a); p = cur + p if rel else p; cur = p; start = p.copy(); pts = [p.copy()]; cmd = 'l' if rel else 'L'; prev_c = None
        elif C == 'L': p = np.array(a); cur = cur + p if rel else p; pts.append(cur.copy()); prev_c = None
        elif C == 'H': cur = np.array([cur[0] + a[0] if rel else a[0], cur[1]]); pts.append(cur.copy()); prev_c = None
        elif C == 'V': cur = np.array([cur[0], cur[1] + a[0] if rel else a[0]]); pts.append(cur.copy()); prev_c = None
        elif C in ('C', 'S'):
            if C == 'C': c1, c2, p3 = np.array(a[0:2]), np.array(a[2:4]), np.array(a[4:6])
            else: c2, p3 = np.array(a[0:2]), np.array(a[2:4]); c1 = (2 * cur - prev_c) if prev_c is not None else cur.copy()
            if rel: c1, c2, p3 = (c1 + cur if C == 'C' else c1), c2 + cur, p3 + cur
            pts += list(bez(cur, c1, c2, p3)); prev_c = c2; cur = p3
        elif C in ('Q', 'T'):
            if C == 'Q': c, p3 = np.array(a[0:2]), np.array(a[2:4])
            else: p3 = np.array(a[0:2]); c = (2 * cur - prev_c) if prev_c is not None else cur.copy()
            if rel: c, p3 = (c + cur if C == 'Q' else c), p3 + cur
            c1 = cur + 2 / 3 * (c - cur); c2 = p3 + 2 / 3 * (c - p3); pts += list(bez(cur, c1, c2, p3)); prev_c = c; cur = p3
        elif C == 'A': p3 = np.array(a[5:7]); cur = cur + p3 if rel else p3; pts.append(cur.copy()); prev_c = None
    flush(False); return res
def area_centroid(P):
    x, y = P[:, 0], P[:, 1]; x1, y1 = np.roll(x, -1), np.roll(y, -1); cross = x * y1 - x1 * y; A = cross.sum() / 2
    if abs(A) < 1e-9: return 0.0, P.mean(0)
    return A, np.array([((x + x1) * cross).sum() / (6 * A), ((y + y1) * cross).sum() / (6 * A)])
stack = [np.eye(3)]; skip = 0; strokes = []; idc = 0
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
    if skip or close: continue
    stroke = attr(body, 'stroke'); style = attr(body, 'style') or ''
    if not stroke:
        mm = re.search(r'stroke:\s*(#[0-9A-Fa-f]{6})', style); stroke = mm.group(1) if mm else None
    if not stroke or stroke.lower() == 'none': continue
    M = stack[-1] @ parse_transform(attr(body, 'transform')); pls = []
    if tag == 'path' and attr(body, 'd'): pls = path_polylines(attr(body, 'd'))
    elif tag == 'rect':
        x, y, w, h = [float(attr(body, k) or 0) for k in ('x', 'y', 'width', 'height')]; pls = [(np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]]), True)]
    elif tag in ('polyline', 'polygon') and attr(body, 'points'):
        v = [float(t) for t in num.findall(attr(body, 'points'))]; pls = [(np.array(v).reshape(-1, 2), tag == 'polygon')]
    elif tag == 'line': pls = [(np.array([[float(attr(body, 'x1') or 0), float(attr(body, 'y1') or 0)], [float(attr(body, 'x2') or 0), float(attr(body, 'y2') or 0)]]), False)]
    elif tag in ('ellipse', 'circle'):
        cx, cy = float(attr(body, 'cx') or 0), float(attr(body, 'cy') or 0); rx = float(attr(body, 'rx') or attr(body, 'r') or 0); ry = float(attr(body, 'ry') or attr(body, 'r') or 0)
        t = np.linspace(0, 2 * np.pi, 48, endpoint=False); pls = [(np.c_[cx + rx * np.cos(t), cy + ry * np.sin(t)], True)]
    for P, closed in pls:
        Q = (M @ np.c_[P, np.ones(len(P))].T).T[:, :2]; wx = Q[:, 0] - X0; wy = Y0 - Q[:, 1]
        if wx.max() < x0 or wx.min() > x1 or wy.max() < y0 or wy.min() > y1: continue
        W = np.c_[wx, wy]; A, c = area_centroid(W) if closed and len(W) >= 3 else (0.0, W.mean(0))
        strokes.append(dict(id=idc, color=stroke.upper(), width=float(attr(body, 'stroke-width') or 0), closed=bool(closed), area=round(abs(float(A)), 1), centroid=[round(float(c[0]), 2), round(float(c[1]), 2)], ring=[[round(float(a), 2), round(float(b), 2)] for a, b in W])); idc += 1
json.dump({'_comment': 'traits V16 (SVG) dans la fenetre x %g..%g y %g..%g, coordonnees monde' % (x0, x1, y0, y1), 'strokes': strokes}, open(out, 'w'))
cols = {}
for s in strokes: cols[s['color']] = cols.get(s['color'], 0) + 1
print('%d traits dans la fenetre -> %s ; couleurs: %s' % (len(strokes), out, cols))
