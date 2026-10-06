#!/usr/bin/env python3
"""cam_rays_map.py — vue de dessus V16 d'une camera avec le rayon de chaque marking (pixels.json). [CAM-RAYS-V1 2026-10-06]

Deux panneaux: large (rayons jusqu'a --far m, tuiles V16 z3 = 4 m/px) et proche (+-400 m, z5 = 1 m/px).
Rayon = direction horizontale du pixel clique selon la pose courante (cameras.json); point rouge = landmark avec xyz.
Sortie: docs/rays/<cam>.jpg (image derivee de la V16, ignoree par git si docs/rays/ l'est).
Usage: python3 tools/cam_rays_map.py "Waning Sands (A) (X)" [--far 3000] [--exclude REGEX] [--tag suffixe]
"""
import json, os, sys, math
import numpy as np, cv2
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import common

TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,16')


def tile_crop(x0, x1, y0, y1, z):
    s = 256 * 2 ** (5 - z)                                  # metres par tuile
    tx0, tx1 = int((x0 + 16384) // s), int((x1 + 16384) // s); ty0, ty1 = int((16384 - y1) // s), int((16384 - y0) // s)
    im = Image.new('RGB', ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256), (44, 103, 165))   # hors tuiles = mer V16
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            fp = os.path.join(TILES, str(z), '%d,%d,%d.jpg' % (z, ty, tx))
            if os.path.exists(fp): im.paste(Image.open(fp), ((tx - tx0) * 256, (ty - ty0) * 256))
    mpp = s / 256.0
    X0, Y1 = tx0 * s - 16384, 16384 - ty0 * s               # coin haut-gauche (monde)
    return np.asarray(im).copy(), (lambda x, y: (int(round((x - X0) / mpp)), int(round((Y1 - y) / mpp)))), mpp


def main():
    cam = sys.argv[1]; far = float(sys.argv[sys.argv.index('--far') + 1]) if '--far' in sys.argv else 3000.0
    C = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json'))); st = C[cam]
    P = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json'))).get(cam, {})
    L = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    cm = common.get_cam(cam); o = np.array(st['xyz'], float)
    import re
    exc = sys.argv[sys.argv.index('--exclude') + 1] if '--exclude' in sys.argv else None
    tag = sys.argv[sys.argv.index('--tag') + 1] if '--tag' in sys.argv else ''
    rays = []
    for name, px in sorted(P.items()):
        if exc and re.search(exc, name, re.I): continue
        d = np.array(cm.get_pixel_direction(tuple(px)), float); h = d[:2] / np.linalg.norm(d[:2])
        el = math.degrees(math.atan2(d[2], np.linalg.norm(d[:2])))
        xyz = (L.get(name) or {}).get('xyz')
        rays.append((name, px, h, el, xyz))
    # cone du champ (bords gauche/droit au centre vertical)
    edges = []
    for x in (0, cm.w - 1):
        d = np.array(cm.get_pixel_direction((x, cm.h / 2)), float); edges.append(d[:2] / np.linalg.norm(d[:2]))
    panels = []
    for z, R in ((4, far), (6, 450.0)):
        pts = [o[:2]] + [o[:2] + h * R for _, _, h, _, _ in rays] + [o[:2] + e * R for e in edges]
        pts = np.array(pts); pad = 0.08 * R
        x0, x1 = pts[:, 0].min() - pad, pts[:, 0].max() + pad; y0, y1 = pts[:, 1].min() - pad, pts[:, 1].max() + pad
        img, W, mpp = tile_crop(x0, x1, y0, y1, z)
        lw = 2 if z == 5 else 2; fs = 0.5
        for e in edges: cv2.line(img, W(*o[:2]), W(*(o[:2] + e * R)), (60, 60, 60), 1, cv2.LINE_AA)
        ends = []
        for k, (name, px, h, el, xyz) in enumerate(rays):
            col = (220, 0, 0) if xyz else (0, 90, 200)
            end = o[:2] + h * R; ends.append(W(*end))
            cv2.line(img, W(*o[:2]), W(*end), col, 2, cv2.LINE_AA)
            if xyz:
                a = W(xyz[0], xyz[1]); cv2.circle(img, a, 7, (220, 0, 0), -1); cv2.circle(img, a, 8, (255, 255, 255), 2)
                v = np.array(xyz[:2]) - o[:2]; perp = abs(v[0] * h[1] - v[1] * h[0])
                cv2.putText(img, 'LM, %.1f m off ray' % perp, (a[0] + 10, a[1] + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 4, cv2.LINE_AA)
                cv2.putText(img, 'LM, %.1f m off ray' % perp, (a[0] + 10, a[1] + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 0, 0), 1, cv2.LINE_AA)
        # numeros au bout des rayons, empiles verticalement s'ils se chevauchent
        used = []
        for k, q in sorted(enumerate(ends), key=lambda t: t[1][1]):
            x, y = q[0] + 6, q[1]
            while any(abs(y - u[1]) < 16 and abs(x - u[0]) < 40 for u in used): y += 16
            used.append((x, y)); col = (220, 0, 0) if rays[k][4] else (0, 60, 160)
            cv2.putText(img, str(k + 1), (x, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 4, cv2.LINE_AA)
            cv2.putText(img, str(k + 1), (x, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 1, cv2.LINE_AA)
        c = W(*o[:2]); cv2.circle(img, c, 7, (255, 230, 0), -1); cv2.circle(img, c, 8, (0, 0, 0), 1)
        cv2.putText(img, '%s  |  %s m/px  |  yaw %.2f pitch %.2f roll %.2f hfov %.1f' % (cam, ('%g' % mpp), *st['ypr'], cm.hfov),
                    (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA)
        panels.append(img)
    leg = np.full((26 + 22 * len(rays), 560, 3), 255, np.uint8)
    cv2.putText(leg, 'Markings (red = landmark with xyz)', (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    for k, (name, px, h, el, xyz) in enumerate(rays):
        cv2.putText(leg, '%2d  %s  (brg %.1f, el %+.1f)' % (k + 1, name, math.degrees(math.atan2(h[0], h[1])) % 360, el), (10, 44 + 22 * k),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 0, 0) if xyz else (0, 60, 160), 1, cv2.LINE_AA)
    panels.insert(1, leg)
    out = os.path.join(REPO, 'docs', 'rays', cam + (' ' + tag if tag else '') + '.jpg'); os.makedirs(os.path.dirname(out), exist_ok=True)
    w = max(p.shape[1] for p in panels)
    canvas = np.full((sum(p.shape[0] + 10 for p in panels), w, 3), 255, np.uint8); y = 0
    for p in panels: canvas[y:y + p.shape[0], :p.shape[1]] = p; y += p.shape[0] + 10
    Image.fromarray(canvas).save(out, quality=88)
    for name, px, h, el, xyz in rays:
        print('%-50s px (%7.1f, %6.1f)  bearing %6.2f  elev %+.2f%s' % (name, px[0], px[1], math.degrees(math.atan2(h[0], h[1])) % 360, el, '  LM' if xyz else ''))
    print('->', out)


if __name__ == '__main__':
    main()
