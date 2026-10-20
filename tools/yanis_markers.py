#!/usr/bin/env python3
"""yanis_markers.py — vectorize Yanis's V17 camera markers (raster -> data). [YANIS-MARKERS-V1 2026-10-19]

Alexandre: "transformer les marqueurs de Yanis en données" for him and the other mappers. Yanis draws every trailer /
screenshot camera on his V17 map (gtadb tiles yanis,17) as a coloured dot (= camera), two short lines (= FOV edges, a
"V") and a label "T3/146". They exist only as pixels; this tool turns them into records
  {id, series, x, y, heading, hfov, confidence, ...}
and compares each one with our pose of the same ID (gtamapdata/cameras.json "id").

Stages (cached in tools/generated/yanis_markers/):
  ocr     labels: macOS Vision OCR (tools/ocr_vision.swift) on 500 m chunks of the local z5 mirror, x4 upscale
  dots    marker dots (small round discs of a series colour) on the same chunks
  ocr2    second OCR pass on a 64 x 44 m crop around every dot (small labels the chunk pass misses)
  build   label -> series (label colour) + number; dot of the same colour next to it; V read from the dot with the
          labels and other dots masked; manual readings (by eye, 2026-10-18) override the automatic ones
  export  tools/data/yanis_v17_markers.json + .geojson + tools/generated/yanis_markers/report.md
Frame: the V17 tile frame is the world frame (x = px - 16384, y = 16384 - py at 1 m/px, no offset).
Usage: python3 tools/yanis_markers.py [ocr] [dots] [ocr2] [build] [export]      (no stage = all)
"""
import json, math, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np, cv2

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,17', '5')
OUT = os.path.join(THIS, 'generated', 'yanis_markers'); os.makedirs(OUT, exist_ok=True)
OCR_BIN = os.path.join(OUT, 'ocr_vision')
CHUNK, MARGIN, UP = 500, 30, 4
PANEL = (4000, -7300, 10300, 3700)          # the "Frames reference" thumbnail panel drawn on the map (its IDs are not markers)


def tile(tx, ty):
    p = os.path.join(TILES, '5,%d,%d.jpg' % (ty, tx))
    return cv2.imread(p) if os.path.exists(p) else None


def crop(x0, y0, x1, y1):
    """1 m/px crop of the local V17 z5 mirror, world frame (no network)."""
    X0, X1, Y0, Y1 = 16384 + x0, 16384 + x1, 16384 - y1, 16384 - y0
    tx0, tx1, ty0, ty1 = int(X0 // 256), int((X1 - 1e-6) // 256), int(Y0 // 256), int((Y1 - 1e-6) // 256)
    out = np.full(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256, 3), 255, np.uint8)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            t = tile(tx, ty)
            if t is not None: out[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = t
    ox, oy = int(round(X0 - tx0 * 256)), int(round(Y0 - ty0 * 256))
    return out[oy:oy + int(round(Y1 - Y0)), ox:ox + int(round(X1 - X0))]


def extent():
    t = [tuple(map(int, f[:-4].split(',')[1:])) for f in os.listdir(TILES) if f.endswith('.jpg')]
    ty = [a for a, b in t]; tx = [b for a, b in t]
    return min(tx) * 256 - 16384, 16384 - (max(ty) + 1) * 256, (max(tx) + 1) * 256 - 16384, 16384 - min(ty) * 256


# ---------------------------------------------------------------- stage 1: OCR
def stage_ocr():
    if not os.path.exists(OCR_BIN):
        subprocess.run(['xcrun', 'swiftc', '-O', os.path.join(THIS, 'ocr_vision.swift'), '-o', OCR_BIN], check=True)
    X0, Y0, X1, Y1 = extent(); jobs = []
    tmp = tempfile.mkdtemp(prefix='ymk_', dir=OUT)
    for x in range(int(X0), int(X1), CHUNK):
        for y in range(int(Y0), int(Y1), CHUNK):
            if PANEL[0] <= x and x + CHUNK <= PANEL[2] and PANEL[1] <= y and y + CHUNK <= PANEL[3]: continue
            im = crop(x - MARGIN, y - MARGIN, x + CHUNK + MARGIN, y + CHUNK + MARGIN)
            hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(int)
            ink = (hsv[..., 1] > 110) & (hsv[..., 2] > 45) & ~((hsv[..., 0] >= 97) & (hsv[..., 0] <= 107))   # saturated, not water
            if ink.sum() < 150: continue
            p = os.path.join(tmp, '%d_%d.png' % (x, y))
            cv2.imwrite(p, cv2.resize(im, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)); jobs.append(p)
    print('ocr: %d chunks' % len(jobs))
    groups = [jobs[i::6] for i in range(6)]
    def run(g):
        return subprocess.run([OCR_BIN] + g, capture_output=True, text=True).stdout if g else ''
    with ThreadPoolExecutor(6) as ex: outs = list(ex.map(run, groups))
    rows = []
    for line in ''.join(outs).splitlines():
        f = line.split('\t')
        if len(f) < 5: continue
        x, y = map(int, os.path.basename(f[0])[:-4].split('_')); a, b, c, d = map(float, f[3].split())
        W = (CHUNK + 2 * MARGIN)                         # chunk side in m; Vision boxes are normalized, origin bottom-left
        rows.append(dict(text=f[1], conf=float(f[2]), alts=f[4].split('|'),
                         box=[round(x - MARGIN + a * W, 1), round(y - MARGIN + b * W, 1), round(x - MARGIN + c * W, 1), round(y - MARGIN + d * W, 1)]))
    for p in jobs: os.remove(p)
    os.rmdir(tmp)
    json.dump(rows, open(os.path.join(OUT, 'ocr.json'), 'w'), indent=0); print('ocr: %d text boxes' % len(rows))


# ---------------------------------------------------------------- stage 2a: dots
def dot_mask(hsv):
    """vectorized dot_series() != None."""
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    br = (S >= 150) & (V >= 200) & ((H <= 20) | (H >= 172) | ((H >= 22) & (H <= 36)) | ((H >= 45) & (H <= 81)) | ((H >= 82) & (H <= 98) & (V >= 225)) | ((H >= 106) & (H <= 124)) | ((H >= 138) & (H <= 168) & (V >= 215)))
    dk = (S >= 150) & (((H >= 45) & (H <= 85) & (V < 130) & (V > 40)) | ((H >= 125) & (H <= 137) & (V >= 90)))
    return br | dk



def find_dots(x0, y0, x1, y1, up=3):
    """marker dots = small filled discs of saturated colour (inscribed radius 1.4-8 m (T4 2.1): the dark label glyphs never match a dot colour), not inside big areas (water)."""
    im = cv2.resize(crop(x0, y0, x1, y1), None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(int)
    m = dot_mask(hsv).astype(np.uint8)                                          # pixels of a series DOT colour only
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5) / up
    pk = (dt >= 1.4) & (dt <= 8.0) & (cv2.dilate(dt, np.ones((2 * up + 1, 2 * up + 1), np.uint8)) <= dt + 1e-6)
    n, lab, stt, _ = cv2.connectedComponentsWithStats(m)
    out = []
    for py, px in zip(*np.where(pk)):
        if stt[lab[py, px], 4] > (30 * up) ** 2: continue
        if dt[py, px] < 2.1 and 45 <= hsv[py, px, 0] <= 85 and hsv[py, px, 2] < 130: continue   # T4: dots ~2.7 m, its (dark) glyph strokes ~1.7                       # part of a big area of that colour (water)
        x, y = x0 + (px + 0.5) / up, y1 - (py + 0.5) / up
        if any(abs(x - o['x']) < 3 and abs(y - o['y']) < 3 for o in out[-30:]): continue
        rr = dt[py, px] * up; ang = np.linspace(0, 2 * np.pi, 48, endpoint=False)    # round dot, not a glyph stroke: the ring just
        ring = [m[int(py + f * rr * math.sin(t)), int(px + f * rr * math.cos(t))] if 0 <= int(py + f * rr * math.sin(t)) < m.shape[0] and 0 <= int(px + f * rr * math.cos(t)) < m.shape[1] else 0
                for f in (1.45, 1.7) for t in ang]                                  # outside it is mostly free (only the 2 V lines exit)
        if np.mean(ring) > 0.5: continue
        r0 = max(1, int(0.9 * up))
        bgr = np.median(im[max(0, py - r0):py + r0 + 1, max(0, px - r0):px + r0 + 1].reshape(-1, 3), 0)
        out.append(dict(x=round(float(x), 2), y=round(float(y), 2), r=round(float(dt[py, px]), 2), bgr=[int(v) for v in bgr]))
    return out


def stage_dots():
    X0, Y0, X1, Y1 = extent(); D = []
    for x in range(int(X0), int(X1), CHUNK):
        for y in range(int(Y0), int(Y1), CHUNK):
            if PANEL[0] <= x and x + CHUNK <= PANEL[2] and PANEL[1] <= y and y + CHUNK <= PANEL[3]: continue
            for d in find_dots(x - 8, y - 8, x + CHUNK + 8, y + CHUNK + 8):
                if x <= d['x'] < x + CHUNK and y <= d['y'] < y + CHUNK: D.append(d)
    json.dump(D, open(os.path.join(OUT, 'dots.json'), 'w'), indent=0); print('dots: %d' % len(D))


def stage_ocr2():
    """second OCR pass: a 64 x 44 m crop around every marker-coloured dot (x6), where the full-chunk pass misses small labels."""
    D = [d for d in json.load(open(os.path.join(OUT, 'dots.json'))) if dot_series(d['bgr'])]
    tmp = tempfile.mkdtemp(prefix='ymk2_', dir=OUT); jobs = []; done = []
    for d in D:
        if any(abs(d['x'] - a) < 12 and abs(d['y'] - b) < 8 for a, b in done[-400:]): continue
        done.append((d['x'], d['y'])); x0, y0 = d['x'] - 32, d['y'] - 22
        p = os.path.join(tmp, '%.1f_%.1f.png' % (x0, y0))
        cv2.imwrite(p, cv2.resize(crop(x0, y0, x0 + 64, y0 + 44), None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)); jobs.append(p)
    print('ocr2: %d crops' % len(jobs))
    groups = [jobs[i::6] for i in range(6)]
    with ThreadPoolExecutor(6) as ex: outs = list(ex.map(lambda g: subprocess.run([OCR_BIN] + g, capture_output=True, text=True).stdout if g else '', groups))
    rows = []
    for line in ''.join(outs).splitlines():
        f = line.split('\t')
        if len(f) < 5: continue
        x0, y0 = map(float, os.path.basename(f[0])[:-4].split('_')); a, b, c, d = map(float, f[3].split())
        rows.append(dict(text=f[1], conf=float(f[2]), alts=f[4].split('|'), box=[round(x0 + a * 64, 1), round(y0 + b * 44, 1), round(x0 + c * 64, 1), round(y0 + d * 44, 1)], pass_=2))
    for p in jobs: os.remove(p)
    os.rmdir(tmp); json.dump(rows, open(os.path.join(OUT, 'ocr2.json'), 'w'), indent=0); print('ocr2: %d text boxes' % len(rows))


# ---------------------------------------------------------------- stage 2b: labels -> dots -> V
# dot colour (OpenCV HSV of the dot centre) -> series; measured on the V17 dots next to the labels read without ambiguity
def dot_series(bgr):
    """dot centre colour -> series. Dots are the BRIGHT shade of the series colour (labels and V lines are the dark shade,
    so a glyph stroke is never taken for a dot), except T4 (dark green dots) and S4 (dark purple)."""
    H, S, V = (int(v) for v in cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0, 0])
    if S < 150: return None
    if 45 <= H <= 85 and V < 130: return 'T4'
    if 125 <= H <= 137 and V >= 90: return 'S4'
    if V < 200: return None
    if H <= 8 or H >= 172: return 'S2'
    if 9 <= H <= 20: return 'S3'
    if 22 <= H <= 36: return 'L'
    if 45 <= H <= 85: return 'A'
    if 82 <= H <= 98: return 'T2' if V >= 225 else None          # shallow water has the same hue, but V ~205
    if 106 <= H <= 124: return 'T3'
    if 138 <= H <= 168: return 'T1' if V >= 215 else None        # the T1 label text is a lighter magenta (V ~200)
    return None


FIX = str.maketrans({'$': 'S', 'Т': 'T', 'Д': '/', 'І': '1', '|': '/', ',': '/', '\\': '/', 'О': '0', 'S': 'S'})


def parse_label(t):
    """OCR text -> (letter or None, series digit or None, number) or None. '52/46' -> (None,'2',46): 5/8 ~ S, 7/1 ~ T."""
    t = t.translate(FIX).replace(' ', '')
    t = re.sub(r'^[^TSLA0-9/]+', '', t)
    m = re.search(r'([TSLA])(\d{1,2})/(\d{1,3})', t)
    if m: return m.group(1), m.group(2), int(m.group(3))
    m = re.match(r'^([5871])(\d)/(\d{1,3})', t)
    if m: return {'5': 'S', '8': 'S', '7': 'T', '1': 'T'}[m.group(1)], m.group(2), int(m.group(3))
    m = re.match(r'^([TS])([1-4])(\d{2,3})[^\d]*$', t)
    if m: return m.group(1), m.group(2), int(m.group(3))
    m = re.match(r'^(\d)?/(\d{1,3})[^\d]*$', t)
    if m: return None, m.group(1), int(m.group(2))
    return None


def label_id(letter, digit, num, ser):
    """combine the text with the dot series; returns Yanis's label form (T3/146, S2/04, L1/15, A2/01) or None if inconsistent."""
    if ser in ('T1', 'T2', 'T3', 'T4', 'S2', 'S3', 'S4'):
        if letter and letter != ser[0]: return None
        if digit and digit != ser[1]: return None
        return '%s/%02d' % (ser, num)
    if ser == 'L':
        return 'L%s/%d' % (digit, num) if digit and letter in (None, 'L') else None
    if ser == 'A':
        return 'A%s/%02d' % (digit, num) if digit and letter in (None, 'A') else None
    return None


def read_v(x, y, ser, masks, rd=2.5, R=26, S=6):
    """heading/hfov of the V drawn from the dot at (x, y). Ink = the series hue, darker than the dot (the V lines are the
    dark shade; T4 dots are already dark); other marker labels and dots are masked (never within 4 m of this dot). For
    every direction, the run of ink that starts at the dot edge; the V = the pair of runs with similar lengths, an
    opening of 12-175 deg, preferring runs that END inside the crop (a run reaching the border is a path to another dot)."""
    im = cv2.resize(crop(x - R, y - R, x + R, y + R), None, fx=S, fy=S, interpolation=cv2.INTER_CUBIC)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(int); H, Sa, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    c = R * S; ctr = hsv[c - 4:c + 5, c - 4:c + 5].reshape(-1, 3)
    h0 = int(np.median(ctr[:, 0])); v0 = int(np.median(ctr[:, 2]))
    dh = np.minimum(np.abs(H - h0), 180 - np.abs(H - h0))
    ink = (dh <= (12 if ser in ('T4', 'A') else 16)) & (Sa > 70) & (V > 20)
    ink &= (V < 150) if ser == 'T4' else (V < v0 - 15)
    if ser in ('S2', 'S3'):                                                     # thin brown-red lines: hue drifts to brown once blended
        ink = ((H <= 25) | (H >= 165)) & (Sa > 60) & (V > 20) & (V < 205)
    blk = np.zeros(ink.shape, np.uint8)
    for kind, a in masks:
        if kind == 'box':
            x0, y0, x1, y1 = a; cv2.rectangle(blk, (int((x0 - x + R) * S), int((y + R - y1) * S)), (int((x1 - x + R) * S), int((y + R - y0) * S)), 1, -1)
        else:
            cv2.circle(blk, (int((a[0] - x + R) * S), int((y + R - a[1]) * S)), int(3.0 * S), 1, -1)
    cv2.circle(blk, (c, c), int((rd + 1.5) * S), 0, -1)
    r0, r_first = max(2.4, 0.85 * rd), rd + 2.4                                # S2 dots are big: the lines start at their edge
    ink &= blk == 0
    run = np.zeros(720); thru = np.zeros(720, bool)
    for k in range(720):
        a = math.radians(k / 2); r = r0; L = 0; miss = 0; first = None; sa, ca = math.sin(a), math.cos(a)
        while r < R - 1.5:
            px, py = int(c + r * S * sa), int(c - r * S * ca)
            if ink[py - 1:py + 2, px - 1:px + 2].any(): L = r; miss = 0; first = first or r
            else:
                miss += 1
                if miss > (6 if L else 10): break
            r += 0.25
        ok = first is not None and first < r_first
        run[k] = L - r0 if ok else 0; thru[k] = ok and L >= R - 2.5
    sm = np.convolve(np.r_[run[-2:], run, run[:2]], np.ones(5) / 5, 'valid')
    pk = [k for k in range(720) if sm[k] >= 3 and sm[k] >= sm[(k - 1) % 720] and sm[k] >= sm[(k + 1) % 720] and sm[k] == max(sm[(k + d) % 720] for d in range(-12, 13))]
    best = None
    for i in pk:
        for j in pk:
            dd = (j - i) % 720 / 2
            if not 12 <= dd <= 175: continue
            l1, l2 = sm[i], sm[j]
            sc = min(l1, l2) - 0.6 * abs(l1 - l2) - 6 * (thru[i] + thru[j])
            if best is None or sc > best[0]: best = (sc, i, j, dd)
    if best is None:
        return dict(heading=None, hfov=None, edges=None, edge_len_m=None, v_conf='none')
    sc, i, j, dd = best; l1, l2 = float(sm[i]), float(sm[j])
    others = [sm[k] for k in pk if min(abs(k - i), 720 - abs(k - i)) > 12 and min(abs(k - j), 720 - abs(k - j)) > 12]
    rival = max(others) if others else 0.0
    conf = 'high' if min(l1, l2) >= 6 and abs(l1 - l2) <= 0.35 * max(l1, l2) and rival < 0.6 * min(l1, l2) else 'medium' if min(l1, l2) >= 4 else 'low'
    return dict(heading=round((i / 2 + dd / 2) % 360, 1), hfov=round(dd, 1), edges=[i / 2, j / 2], edge_len_m=[round(l1, 1), round(l2, 1)], v_conf=conf)


def manual_readings():
    """readings done by eye on 2026-10-18 (YANIS-V-FIT notes in cameras.json) override the automatic V."""
    C = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json'))); out = {}
    for n, c in C.items():
        nt = c.get('notes') if isinstance(c.get('notes'), str) else ' '.join(c.get('notes') or [])
        m = re.search(r'YANIS-V-FIT .*?\): heading (\d+) / hfov (\d+) read by eye on the V of his V17 marker (\S+)', nt or '')
        if m: out[m.group(3)] = dict(heading=float(m.group(1)), hfov=float(m.group(2)), low='LOW confidence' in nt.split('YANIS-V-FIT')[-1], cam=n)
    return out


def canon(i):
    """'T3/04' -> 'T3/4' (our cameras.json id form)."""
    a, b = i.split('/'); return '%s/%d' % (a, int(b))


def stage_build():
    R = json.load(open(os.path.join(OUT, 'ocr.json'))); D = json.load(open(os.path.join(OUT, 'dots.json')))
    if os.path.exists(os.path.join(OUT, 'ocr2.json')): R += json.load(open(os.path.join(OUT, 'ocr2.json')))
    for d in D: d['ser'] = dot_series(d['bgr'])
    D = [d for d in D if d['ser']]
    xy = np.array([[d['x'], d['y']] for d in D])
    boxes = []
    for r in R:
        b = r['box']; cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if PANEL[0] <= cx <= PANEL[2] and PANEL[1] <= cy <= PANEL[3]: continue
        ps = [q for q in (parse_label(t) for t in [r['text']] + r['alts']) if q]
        boxes.append(dict(b=b, c=(cx, cy), text=r['text'], parses=ps))
    # candidate (label, dot) pairs: label box within 26 m of the dot, consistent text + dot colour
    CELLS = json.load(open(os.path.join(THIS, 'data', 'yanis_frames_cells.json')))['cells']
    def in_cell(yid, x, y, tol=200):
        c = CELLS.get(yid)
        if not c or c['interior']: return True
        x0 = -3000 + 1000 * (ord(c['cell'][0]) - ord('K')); y0 = (int(c['cell'][1:]) - 14) * 1000
        return x0 - tol <= x <= x0 + 1000 + tol and y0 - tol <= y <= y0 + 1000 + tol
    cand = []
    for li, bx in enumerate(boxes):
        if not bx['parses']: continue
        b = bx['b']
        near = np.where((xy[:, 0] > b[0] - 26) & (xy[:, 0] < b[2] + 26) & (xy[:, 1] > b[1] - 26) & (xy[:, 1] < b[3] + 26))[0]
        for di in near:
            d = D[di]; dx = max(b[0] - d['x'], 0, d['x'] - b[2]); dy = max(b[1] - d['y'], 0, d['y'] - b[3])
            # distance to the box + a little of the distance to its centre (two labels merged in one box), wide boxes cost more
            dist = math.hypot(dx, dy) + 0.25 * math.hypot(d['x'] - bx['c'][0], d['y'] - bx['c'][1]) + 0.1 * max(0, b[2] - b[0] - 40)
            for k, (le, dg, num) in enumerate(bx['parses']):
                yid = label_id(le, dg, num, d['ser'])
                if yid and not in_cell(yid, d['x'], d['y']): yid = None
                if yid: cand.append((dist + 3 * k + (0 if le and dg else 4), li, int(di), yid)); break
    cand.sort(); used_l, used_d, M = set(), set(), {}
    for cost, li, di, yid in cand:                       # greedy: closest consistent pairs first, one dot / one label each
        if li in used_l or di in used_d or yid in M: continue
        alt = [cc for cc in cand if cc[1] == li and cc[2] != di and cc[2] not in used_d and D[cc[2]]['ser'] == D[di]['ser'] and cc[0] < cost + 8]
        used_l.add(li); used_d.add(di)
        M[yid] = dict(label=boxes[li]['text'], label_box=boxes[li]['b'], dot=D[di], label_dist_m=round(cost, 1),
                      ambiguous=bool(alt), alt_dot=[D[alt[0][2]]['x'], D[alt[0][2]]['y']] if alt else None)
    print('build: %d markers from %d labels / %d dots' % (len(M), len(boxes), len(D)))
    man = manual_readings(); out = []
    for yid, m in sorted(M.items()):
        d = m['dot']; x, y = d['x'], d['y']
        masks = [('box', bb['b']) for bb in boxes if bb['parses'] and abs(bb['c'][0] - x) < 60 and abs(bb['c'][1] - y) < 60 and (bb['b'][2] - bb['b'][0]) < 60]
        masks += [('dot', (o['x'], o['y'])) for o in D if 1.5 < math.hypot(o['x'] - x, o['y'] - y) < 40]
        v = read_v(x, y, d['ser'], masks, rd=d['r'])
        rec = dict(id=yid, our_id=canon(yid), series=d['ser'] if d['ser'] not in ('L', 'A') else yid.split('/')[0], x=x, y=y, **v,
                   v_source='auto', label_ocr=m['label'], label_box=m['label_box'], label_dist_m=m['label_dist_m'],
                   ambiguous=m['ambiguous'], alt_dot=m['alt_dot'], inset=bool((CELLS.get(yid) or {}).get('interior')),
                   cell=(CELLS.get(yid) or {}).get('cell'))
        mm = man.get(canon(yid))
        if mm:
            rec.update(heading=mm['heading'], hfov=mm['hfov'], v_source='by eye 2026-10-18', v_conf='low' if mm['low'] else 'high', auto_heading=v['heading'], auto_hfov=v['hfov'])
        out.append(rec)
    json.dump(out, open(os.path.join(OUT, 'markers.json'), 'w'), indent=0)


# ---------------------------------------------------------------- stage 3: export + comparison with our poses
def stage_export():
    M = json.load(open(os.path.join(OUT, 'markers.json')))
    C = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    TI = json.load(open(os.path.join(THIS, 'generated', 'confidence_tiers.json')))['cameras']
    byid = {c.get('id'): (n, c) for n, c in C.items() if c.get('id')}
    recs = []
    for m in M:
        r = {k: m.get(k) for k in ('id', 'our_id', 'series', 'x', 'y', 'heading', 'hfov', 'v_source', 'v_conf', 'ambiguous', 'inset', 'cell', 'label_ocr')}
        r['x'], r['y'] = round(m['x'], 1), round(m['y'], 1)
        if m.get('edge_len_m'): r['edge_len_m'] = m['edge_len_m']
        if m.get('alt_dot'): r['alt_dot'] = [round(v, 1) for v in m['alt_dot']]
        n, c = byid.get(m['our_id'], (None, None))
        if c and c.get('xyz') and c.get('ypr'):
            nt = c.get('notes') if isinstance(c.get('notes'), str) else ' '.join(c.get('notes') or [])
            from_y = 'PROVISIONAL' in (nt or '') and not c.get('pose_verified')          # our pose was taken from his marker
            hd = (-c['ypr'][0]) % 360; fv = (c.get('fov') or [None])[0]
            o = dict(name=n, x=round(c['xyz'][0], 1), y=round(c['xyz'][1], 1), heading=round(hd, 1), hfov=fv, tier=(TI.get(n) or {}).get('tier'),
                     pose_verified=bool(c.get('pose_verified')), from_yanis=from_y)
            if not m['inset']:
                o['d_pos_m'] = round(math.hypot(c['xyz'][0] - m['x'], c['xyz'][1] - m['y']), 1)
                o['move_e_m'], o['move_n_m'] = round(c['xyz'][0] - m['x'], 1), round(c['xyz'][1] - m['y'], 1)   # how his marker must move to reach our pose
                if m['heading'] is not None: o['d_heading_deg'] = round((hd - m['heading'] + 180) % 360 - 180, 1)
                if m['hfov'] is not None and fv: o['d_hfov_deg'] = round(fv - m['hfov'], 1)
            r['ours'] = o
        recs.append(r)
    head = dict(_doc='Yanis V17 camera markers as data (dot = camera position, V = heading / horizontal FOV). Vectorized from the gtadb '
                     'tiles yanis,17 by tools/yanis_markers.py (OCR of the labels, dot colour = series, V read on the lines; "by eye" = '
                     'read by hand on 2026-10-18). Frame: gtamaplib world metres (x east, y north; = the V17 tile frame). heading: compass '
                     'degrees, 0 = north, clockwise (our yaw = -heading). His markers are eyeballed by him: they are his estimate, not '
                     'measurements. ours.move_*: how far his marker must move to reach our pose (only meaningful when our pose is solved, '
                     'i.e. ours.from_yanis is false). Markers and drawing: Yanis (map.gtadb.org); ask him before redistributing.',
                generated=__import__('time').strftime('%Y-%m-%d'), source='https://maps.gtadb.org/tiles/6/yanis,17', count=len(recs))
    F = []
    for r in recs:
        F.append(dict(type='Feature', geometry=dict(type='Point', coordinates=[r['x'], r['y']]), properties={k: v for k, v in r.items() if k not in ('x', 'y')}))
        if r['heading'] is not None and r['hfov'] is not None:
            for sg in (-1, 1):
                a = math.radians(r['heading'] + sg * r['hfov'] / 2)
                F.append(dict(type='Feature', geometry=dict(type='LineString', coordinates=[[r['x'], r['y']], [round(r['x'] + 20 * math.sin(a), 1), round(r['y'] + 20 * math.cos(a), 1)]]),
                              properties=dict(id=r['id'], kind='fov_edge')))
    json.dump(dict(type='FeatureCollection', name='yanis_v17_markers', crs_note='local gtamaplib world metres, not lon/lat', features=F),
              open(os.path.join(THIS, 'data', 'yanis_v17_markers.geojson'), 'w'), separators=(',', ':'))
    # report
    solved = [r for r in recs if r.get('ours') and not r['ours']['from_yanis'] and 'd_pos_m' in r['ours']]
    for r in solved:
        o = r['ours']; why = []
        if o['d_pos_m'] > 300: why.append('> 300 m: probably an inset or another label with the same ID')
        if r['ambiguous']: why.append('two candidate dots (moving shot?)')
        o['compare'] = 'check' if why else 'ok'
        if why: o['check_reason'] = '; '.join(why)
    json.dump(dict(**head, markers=recs), open(os.path.join(THIS, 'data', 'yanis_v17_markers.json'), 'w'), indent=1, ensure_ascii=True)
    json.dump(dict(**head, markers=recs), open(os.path.join(THIS, 'threejs', '_yanis_markers.json'), 'w'), separators=(',', ':'))
    good = sorted([r for r in solved if r['ours']['compare'] == 'ok'], key=lambda r: -r['ours']['d_pos_m'])
    chk = sorted([r for r in solved if r['ours']['compare'] == 'check'], key=lambda r: r['id'])
    import collections
    L = ['# Yanis V17 markers vs our poses', '', 'Generated %s by `tools/yanis_markers.py`. Data: `tools/data/yanis_v17_markers.json` (+ `.geojson`).' % head['generated'], '',
         '- markers read: **%d** (%s)' % (len(recs), ', '.join('%s %d' % (k, v) for k, v in sorted(collections.Counter(r['series'] for r in recs).items()))),
         '- with a V (heading + FOV): %d, of which %d read by eye; ambiguous dot (moving shot / two candidate dots): %d; interior insets: %d'
         % (sum(r['heading'] is not None for r in recs), sum(r['v_source'] != 'auto' for r in recs), sum(bool(r['ambiguous']) for r in recs), sum(bool(r['inset']) for r in recs)),
         '- compared with a SOLVED pose of ours: %d reliable + %d to check (cams whose pose came from his marker are not compared)' % (len(good), len(chk)), '',
         'Move = from his dot to our camera, metres (E, N). Heading / FOV = ours minus his. "?" = his V not read automatically.', '',
         '## Reliable comparisons', '', '| ID | camera | move (m) | E | N | heading | FOV | our tier | V |', '|---|---|---:|---:|---:|---:|---:|---|---|']
    fmt = lambda o, k: ('%+.0f°' % o[k]) if k in o else '?'
    for r in good:
        o = r['ours']
        L.append('| %s | %s | %.1f | %+.1f | %+.1f | %s | %s | %s | %s |' % (r['id'], o['name'], o['d_pos_m'], o['move_e_m'], o['move_n_m'], fmt(o, 'd_heading_deg'), fmt(o, 'd_hfov_deg'),
                 o['tier'] or '-', r['v_source'] if r['v_source'] != 'auto' else r['v_conf']))
    L += ['', '## To check', '', '| ID | camera | move (m) | reason |', '|---|---|---:|---|']
    for r in chk: L.append('| %s | %s | %.0f | %s |' % (r['id'], r['ours']['name'], r['ours']['d_pos_m'], r['ours']['check_reason']))
    open(os.path.join(OUT, 'report.md'), 'w').write('\n'.join(L) + '\n')
    print('export: %d markers, %d reliable comparisons, %d to check' % (len(recs), len(good), len(chk)))


if __name__ == '__main__':
    st = [a for a in sys.argv[1:] if not a.startswith('-')] or ['ocr', 'dots', 'ocr2', 'build', 'export']
    for s in st: globals()['stage_' + s]()
