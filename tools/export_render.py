#!/usr/bin/env python3
"""export_render.py — exports « shot » de la vue Camera et de la carte. [EXPORT-V2 2026-09-29]

Deux rendus, zero clic requis:
  render_camera(cam_name) -> PNG bytes : la frame + meshes projetes (fil de fer a
      la couleur du mesh) + etiquettes par mesh (pastille couleur du mesh, score de
      fit) + carte d'info en verre (nom, pose, jauge MESH FIT).
  render_map(cam_name, tiles_fn) -> PNG bytes : carte sombre autour de la cam,
      cone de vision en degrade, empreintes des meshes visibles a leur couleur +
      etiquettes, echelle, nord, meme carte d'info.
Le score vient de mesh_fit.compute() (contraste de decalage sur les silhouettes).
"""
import io, json, math, os, sys
THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import common
import mesh_fit

MESHES = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
CAMS = os.path.join(REPO, 'gtamapdata', 'cameras.json')


def _font(sz, bold=False):
    for fp in (('/System/Library/Fonts/SFNSDisplay-Bold.otf', '/System/Library/Fonts/Supplemental/Arial Bold.ttf') if bold else
               ('/System/Library/Fonts/SFNS.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf')) + ('/System/Library/Fonts/Menlo.ttc',):
        try: return ImageFont.truetype(fp, sz)
        except Exception: pass
    return ImageFont.load_default()


def _mono(sz):
    for fp in ('/System/Library/Fonts/SFNSMono.ttf', '/System/Library/Fonts/Menlo.ttc'):
        try: return ImageFont.truetype(fp, sz)
        except Exception: pass
    return ImageFont.load_default()


def _hex(c, default=(250, 204, 21)):
    try:
        c = c.lstrip('#'); return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except Exception: return default


def _score_col(s):
    if s is None: return (148, 163, 184)
    if s >= 70: return (52, 211, 153)
    if s >= 40: return (250, 204, 21)
    if s >= 15: return (251, 146, 60)
    return (248, 113, 113)


def _lum(c): return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _pill(draw, xy, text, bg, font, dot=None, pad=(10, 5), r=None, alpha=235):
    x, y = xy; bb = font.getbbox(text); tw, th = bb[2] - bb[0], bb[3] - bb[1]
    dw = (th + 4) if dot else 0
    w = tw + pad[0] * 2 + dw; h = th + pad[1] * 2; r = r if r is not None else h // 2
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=bg + (alpha,))
    if dot:
        cy = y + h / 2; draw.ellipse([x + pad[0] - 1, cy - th / 2 + 1, x + pad[0] + th - 3, cy + th / 2 - 3], fill=dot + (255,), outline=(255, 255, 255, 200), width=1)
    fg = (12, 12, 16) if _lum(bg) > 150 else (255, 255, 255)
    draw.text((x + pad[0] + dw, y + pad[1] - bb[1]), text, fill=fg + (255,), font=font)
    return w, h


def _gauge(draw, cx, cy, R, score, font_big, font_small):
    col = _score_col(score)
    draw.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(255, 255, 255, 40), width=max(3, R // 7))
    if score:
        draw.arc([cx - R, cy - R, cx + R, cy + R], start=-90, end=-90 + 360 * score / 100, fill=col + (255,), width=max(3, R // 7))
    t = '—' if score is None else str(score); bb = font_big.getbbox(t)
    draw.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1] - R * 0.08), t, fill=(255, 255, 255, 255), font=font_big)
    s = 'MESH FIT'; bb = font_small.getbbox(s)
    draw.text((cx - (bb[2] - bb[0]) / 2, cy + R * 0.32), s, fill=(200, 205, 220, 230), font=font_small)


def _glass(base, box, radius, tint=(14, 16, 24), alpha=190):
    x0, y0, x1, y1 = [int(v) for v in box]
    region = base.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(14))
    base.paste(region, (x0, y0))
    ov = Image.new('RGBA', base.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    d.rounded_rectangle(box, radius=radius, fill=tint + (alpha,), outline=(255, 255, 255, 38), width=1)
    return Image.alpha_composite(base, ov)


def _pick_tags(tags, per, k=12):
    # seulement les meshes bien visibles (assez de silhouette non occultee), sans podiums/annexes
    t = [x for x in tags if per[x[2]]['n'] >= 40 and not any(w in x[2] for w in ('(Podium)', '(Annex)', '(Cables)'))]
    return sorted(t, key=lambda x: -per[x[2]]['n'])[:k]


def _info_card(img, cam_name, c, fit, n_meshes, scale):
    W, H = img.size; s = scale
    fT, fS, fM = _font(int(30 * s), True), _font(int(17 * s)), _mono(int(17 * s))
    fG, fGs = _font(int(40 * s), True), _font(int(12 * s), True)
    pad = int(22 * s); gauge_R = int(46 * s)
    lines = ['XYZ  %.0f  %.0f  %.1f' % tuple(c['xyz']), 'YPR  %.2f  %.2f  %.2f' % tuple(c['ypr']), 'FOV  %.1f°' % c['fov'][0]]
    tw = max([fT.getbbox(cam_name)[2]] + [fM.getbbox(l)[2] for l in lines])
    cw = pad * 3 + tw + gauge_R * 2 + int(10 * s); ch = pad * 2 + int(30 * s) + int(12 * s) + len(lines) * int(24 * s) + int(34 * s)
    x0, y0 = int(26 * s), H - ch - int(26 * s)
    img = _glass(img, (x0, y0, x0 + cw, y0 + ch), int(20 * s))
    d = ImageDraw.Draw(img)
    d.text((x0 + pad, y0 + pad), cam_name, fill=(255, 255, 255, 255), font=fT)
    y = y0 + pad + int(42 * s)
    for l in lines:
        d.text((x0 + pad, y), l, fill=(200, 206, 222, 255), font=fM); y += int(24 * s)
    pv = c.get('pose_verified'); cid = c.get('id', '')
    badge = (pv.split(' ')[0], (16, 185, 129)) if pv else ('UNVERIFIED', (100, 116, 139))
    bw, bh = _pill(d, (x0 + pad, y + int(6 * s)), badge[0], badge[1], fGs, pad=(int(9 * s), int(5 * s)))
    _pill(d, (x0 + pad + bw + int(8 * s), y + int(6 * s)), '%d meshes' % n_meshes, (51, 65, 85), fGs, pad=(int(9 * s), int(5 * s)))
    if cid: _pill(d, (x0 + pad + bw + int(8 * s) + int(100 * s), y + int(6 * s)), str(cid), (30, 41, 59), fGs, pad=(int(9 * s), int(5 * s)))
    _gauge(d, x0 + cw - pad - gauge_R, y0 + ch / 2, gauge_R, fit, fG, fGs)
    return img


def render_camera(cam_name, show_meshes=True):
    C = json.load(open(CAMS)); c = C[cam_name]; M = json.load(open(MESHES))
    cam = common.get_cam(cam_name)
    base = Image.open(os.path.join(REPO, 'frames', cam_name + '.png')).convert('RGBA')
    W, H = base.size; s = W / 1920.0
    fit = mesh_fit.compute(cam_name) or {'score': None, 'buildings': {}}
    per = fit.get('buildings', {})
    ov = Image.new('RGBA', base.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    cx, cy = cam.xyz[0], cam.xyz[1]; tags = []
    if show_meshes:
        for name, v in M.items():
            e = v.get('world_edges') or []
            if not e or math.hypot(e[0][0][0] - cx, e[0][0][1] - cy) < 25: continue
            col = _hex(v.get('color', '#facc15')); pts = []
            for a, b in e:
                pa, pb = cam.get_pixel(list(a)), cam.get_pixel(list(b))
                if pa is None or pb is None: continue
                if max(pa[0], pb[0]) < 0 or min(pa[0], pb[0]) > W or max(pa[1], pb[1]) < 0 or min(pa[1], pb[1]) > H: continue
                d.line([tuple(map(float, pa)), tuple(map(float, pb))], fill=col + (170,), width=max(1, int(1.2 * s)))
                pts += [pa, pb]
            if name in per and pts:
                P = np.array(pts, float); P = P[(P[:, 0] >= 0) & (P[:, 0] <= W) & (P[:, 1] >= 0) & (P[:, 1] <= H)]
                if len(P): tags.append((float(P[:, 0].mean()), float(P[:, 1].min()), name, col, per[name]['score']))
    img = Image.alpha_composite(base, ov)
    tags = _pick_tags(tags, per)
    # etiquettes: pastille couleur du mesh + point de score, empilees sans chevauchement
    d = ImageDraw.Draw(img); fL = _font(int(15 * s), True); placed = []
    for x, ytop, name, col, sc in sorted(tags, key=lambda t: t[1]):
        label = '%s  %s' % (name.replace(' (Ambrosia)', '').replace(' (Allied Crystal)', ''), '—' if sc is None else sc)
        bb = fL.getbbox(label); w = bb[2] - bb[0] + int(40 * s); h = bb[3] - bb[1] + int(12 * s)
        bx = max(6, min(x - w / 2, W - w - 6)); by = ytop - h - int(26 * s)
        for _ in range(40):
            if not any(not (bx + w < p[0] or bx > p[2] or by + h < p[1] or by > p[3]) for p in placed): break
            by -= h + int(4 * s)
        by = max(6, by); placed.append((bx, by, bx + w, by + h))
        d.line([(x, ytop - 2), (x, by + h)], fill=col + (200,), width=max(1, int(1.5 * s)))
        d.ellipse([x - 3 * s, ytop - 3 * s, x + 3 * s, ytop + 3 * s], fill=col + (255,))
        _pill(d, (bx, by), label, col, fL, dot=_score_col(sc), pad=(int(9 * s), int(6 * s)), alpha=225)
    img = _info_card(img, cam_name, c, fit.get('score'), len(per), s)
    buf = io.BytesIO(); img.convert('RGB').save(buf, 'PNG'); return buf.getvalue()


def render_map(cam_name, tiles_fn, OUT=1600):
    C = json.load(open(CAMS)); c = C[cam_name]; M = json.load(open(MESHES))
    cam = common.get_cam(cam_name); cx, cy = float(cam.xyz[0]), float(cam.xyz[1]); size = c.get('size') or [1920, 1080]
    fit = mesh_fit.compute(cam_name) or {'score': None, 'buildings': {}}; per = fit.get('buildings', {})
    # etendue: meshes visibles dans la frame
    ds = []
    for name in per:
        e = M[name]['world_edges']; P = np.array(e).reshape(-1, 3)[:, :2]; ds.append(np.hypot(*(P.mean(0) - [cx, cy])))
    Rm = max(300.0, min(float(np.percentile(ds, 85)) if ds else 300.0, 12000.0)) * 1.18
    try:
        from PIL import ImageOps, ImageEnhance
        tile = tiles_fn(cx, cy, Rm, OUT).convert('RGB')
        g = ImageOps.grayscale(tile); g = ImageEnhance.Contrast(g).enhance(1.15)
        base = ImageOps.colorize(g, (10, 12, 20), (120, 132, 160)).convert('RGBA')
    except Exception:
        base = Image.new('RGBA', (OUT, OUT), (12, 14, 22, 255))
    x0w, y1w, CM = cx - Rm, cy + Rm, 2 * Rm
    w2c = lambda x, y: ((x - x0w) / CM * OUT, (y1w - y) / CM * OUT)
    s = OUT / 1600.0
    # cone de vision en degrade
    try:
        vdir = cam.get_pixel_direction((size[0] / 2.0, size[1] / 2.0)); aim = math.atan2(float(vdir[1]), float(vdir[0]))
    except Exception: aim = math.radians(90)
    hf = math.radians(c['fov'][0] / 2); cone = Image.new('RGBA', (OUT, OUT), (0, 0, 0, 0)); cd = ImageDraw.Draw(cone)
    camx, camy = w2c(cx, cy)
    for i in range(24, 0, -1):
        L = CM * 1.5 * i / 24; a = int(60 * (1 - i / 24) + 6)
        cd.polygon([(camx, camy), w2c(cx + math.cos(aim - hf) * L, cy + math.sin(aim - hf) * L), w2c(cx + math.cos(aim + hf) * L, cy + math.sin(aim + hf) * L)], fill=(125, 211, 252, a))
    img = Image.alpha_composite(base, cone.filter(ImageFilter.GaussianBlur(2)))
    ov = Image.new('RGBA', (OUT, OUT), (0, 0, 0, 0)); d = ImageDraw.Draw(ov); tags = []
    for name, v in M.items():
        e = v.get('world_edges') or []
        if not e: continue
        P = np.array(e).reshape(-1, 3); c2 = P[:, :2].mean(0)
        if abs(c2[0] - cx) > Rm or abs(c2[1] - cy) > Rm: continue
        vis = name in per; col = _hex(v.get('color', '#facc15')); zb = P[:, 2].min()
        for a, b in e:
            if abs(a[2] - b[2]) < 0.1 and a[2] < zb + 1.0:
                d.line([w2c(*a[:2]), w2c(*b[:2])], fill=col + ((255,) if vis else (70,)), width=max(1, int((2.2 if vis else 1) * s)))
        if vis: tags.append((w2c(*c2), name, col, per[name]['score']))
    img = Image.alpha_composite(img, ov); d = ImageDraw.Draw(img); fL = _font(int(14 * s), True); placed = []
    tags = [t for t in tags if per[t[1]]['n'] >= 40 and not any(w in t[1] for w in ('(Podium)', '(Annex)', '(Cables)'))]
    tags = sorted(tags, key=lambda t: -per[t[1]]['n'])[:14]
    for (px, py), name, col, sc in sorted(tags, key=lambda t: t[0][1]):
        label = '%s  %s' % (name.replace(' (Ambrosia)', ''), '—' if sc is None else sc); bb = fL.getbbox(label)
        w = bb[2] - bb[0] + int(38 * s); h = bb[3] - bb[1] + int(12 * s); bx, by = px + 10 * s, py - h / 2
        if bx + w > OUT - 8: bx = px - 10 * s - w
        for _ in range(30):
            if not any(not (bx + w < q[0] or bx > q[2] or by + h < q[1] or by > q[3]) for q in placed): break
            by += h + 3 * s
        placed.append((bx, by, bx + w, by + h)); d.line([(px, py), (bx, by + h / 2)], fill=col + (200,), width=1)
        _pill(d, (bx, by), label, col, fL, dot=_score_col(sc), pad=(int(8 * s), int(6 * s)), alpha=230)
    # camera
    d.ellipse([camx - 11 * s, camy - 11 * s, camx + 11 * s, camy + 11 * s], fill=(125, 211, 252, 255), outline=(255, 255, 255, 255), width=int(3 * s))
    # echelle + nord
    nice = [50, 100, 200, 500, 1000, 2000, 5000]; m = min(nice, key=lambda v: abs(v / CM * OUT - 180 * s)); L = m / CM * OUT
    fS = _font(int(15 * s), True); ex, ey = OUT - L - 40 * s, 40 * s
    d.rounded_rectangle([ex - 14 * s, ey - 16 * s, OUT - 26 * s, ey + 30 * s], radius=int(10 * s), fill=(14, 16, 24, 190))
    d.line([(ex, ey + 8 * s), (ex + L, ey + 8 * s)], fill=(255, 255, 255, 255), width=int(3 * s))
    d.text((ex, ey - 12 * s), ('%d m' % m) if m < 1000 else ('%g km' % (m / 1000)), fill=(255, 255, 255, 255), font=fS)
    nx, ny = 52 * s, 60 * s
    d.polygon([(nx, ny - 26 * s), (nx - 12 * s, ny + 10 * s), (nx, ny + 3 * s), (nx + 12 * s, ny + 10 * s)], fill=(255, 255, 255, 235))
    d.text((nx - 6 * s, ny + 14 * s), 'N', fill=(255, 255, 255, 235), font=fS)
    img = _info_card(img, cam_name, c, fit.get('score'), len(per), s * 0.9)
    buf = io.BytesIO(); img.convert('RGB').save(buf, 'PNG'); return buf.getvalue()


if __name__ == '__main__':
    n = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else '/tmp/export_cam.png'
    open(out, 'wb').write(render_camera(n)); print('ok', out)
