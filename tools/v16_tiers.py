#!/usr/bin/env python3
"""v16_tiers.py — decoupe l'empreinte V16 d'un batiment en VOLUMES a partir des traits interieurs de la SVG. [V16-TIERS-V1 2026-09-30]

La V16 dessine souvent, a l'interieur du contour rempli d'un batiment, des traits gris (#797979) qui separent les
toits (lame centrale, ailes, gradins, podium, couronne). On rasterise le contour (0.2 m/px), on trace les traits comme
barrieres, on etiquette les regions connexes (cv2) et on les re-vectorise (contours simplifies a 0.3 m).
API: regions(poly_id, svg=None, win_margin=5) -> [{'id','ring':[[x,y]...],'area','centroid'}]
     render(regions, out_png, extra=None)  (plan annote, pour choisir les hauteurs)
Cache des traits: tools/generated/v16_strokes_cache/<poly>.json
"""
import json, os, subprocess, sys
import numpy as np
import cv2

THIS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(THIS)
SVG = os.path.expanduser('~/Downloads/GTA VI Community Mapping Project-3.svg')
CACHE = os.path.join(THIS, 'generated', 'v16_strokes_cache')
RES = 0.2


def _poly(pid):
    F = json.load(open(os.path.join(ROOT, 'gtamapdata', 'v16_footprints.json')))['polygons']
    return next(f for f in F if f['id'] == pid)


def strokes(pid, margin=5):
    os.makedirs(CACHE, exist_ok=True); cp = os.path.join(CACHE, '%d.json' % pid)
    if not os.path.exists(cp):
        r = np.array(_poly(pid)['ring']); x0, y0 = r.min(0) - margin; x1, y1 = r.max(0) + margin
        env = dict(os.environ, V16_X0='16991')
        subprocess.run([sys.executable, os.path.join(THIS, 'v16', 'svg_strokes.py'), SVG, str(x0), str(x1), str(y0), str(y1), cp],
                       check=True, env=env, capture_output=True)
    return json.load(open(cp))['strokes']


def regions(pid, min_area=12.0, colors=('#797979',)):
    P = _poly(pid); R = np.array(P['ring'], float); x0, y0 = R.min(0) - 2; x1, y1 = R.max(0) + 2
    W, H = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
    tp = lambda pts: np.array([[(x - x0) / RES, (y1 - y) / RES] for x, y in pts], np.int32)
    m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [tp(R)], 255)
    inner = cv2.erode(m, np.ones((3, 3), np.uint8))
    for s in strokes(pid):
        if s['color'] not in colors: continue
        r = np.array(s['ring'], float)
        if not len(r): continue
        # garder les traits dont au moins la moitie des points est dans l'empreinte (+1 m)
        ins = cv2.pointPolygonTest
        pts = tp(r); ok = [cv2.pointPolygonTest(tp(R).reshape(-1, 1, 2).astype(np.float32), (float(p[0]), float(p[1])), True) > -5 for p in pts]
        if np.mean(ok) < 0.5: continue
        cv2.polylines(m, [pts], bool(s.get('closed')), 0, thickness=2)
    n, lab = cv2.connectedComponents((m > 0).astype(np.uint8), connectivity=4)
    out = []
    for i in range(1, n):
        mk = (lab == i).astype(np.uint8)
        a = mk.sum() * RES * RES
        if a < min_area: continue
        mk = cv2.dilate(mk, np.ones((3, 3), np.uint8))          # recoller sur les traits (epaisseur 2 px)
        cs, _ = cv2.findContours(mk, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(cs, key=cv2.contourArea); c = cv2.approxPolyDP(c, 0.3 / RES, True).reshape(-1, 2)
        ring = [[round(x0 + px * RES, 2), round(y1 - py * RES, 2)] for px, py in c]
        out.append({'id': len(out), 'ring': ring, 'area': round(a, 1), 'centroid': np.array(ring).mean(0).round(2).tolist()})
    return out


def render(regs, out_png, extra=None, K=8):
    A = np.vstack([np.array(r['ring']) for r in regs]); x0, y0 = A.min(0) - 5; x1, y1 = A.max(0) + 5
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (int((x1 - x0) * K), int((y1 - y0) * K)), 'white'); d = ImageDraw.Draw(im)
    T = lambda p: ((p[0] - x0) * K, (y1 - p[1]) * K)
    for r in regs:
        d.polygon([T(p) for p in r['ring']], outline=(0, 0, 0)); d.text(T(r['centroid']), '%d\n%.0fm2' % (r['id'], r['area']), fill=(220, 0, 0))
    for (x, y, lab) in (extra or []):
        d.ellipse((T((x, y))[0] - 4, T((x, y))[1] - 4, T((x, y))[0] + 4, T((x, y))[1] + 4), outline=(0, 0, 255), width=2); d.text(T((x, y)), lab, fill=(0, 0, 255))
    im.save(out_png)


if __name__ == '__main__':
    pid = int(sys.argv[1]); R = regions(pid)
    for r in R: print(r['id'], r['area'], r['centroid'], len(r['ring']))
    if len(sys.argv) > 2: render(R, sys.argv[2])
