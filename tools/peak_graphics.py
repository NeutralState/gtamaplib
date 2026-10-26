"""peak_graphics.py — infographics for the mountains video (1920x1080):
1) kalaga_vs_chiliad.png: Mount Kalaga's true W-E profile through the summit (game heightmap) drawn to scale, with the height of
   GTA V's Mount Chiliad (798 m, GTA Wiki / Fandom) and of Florida's real highest point Britton Hill (105 m, PeakVisor) as reference lines.
2) top10.png: the 10 highest summits of Leonida (tools/generated/peaks/peaks.json, one per named hill), bars to scale.
Elevations are ESTIMATED from the heightmap. Output: tools/generated/peaks/graphics/"""
import os, sys, json, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hurricane_surge as hs
OUT = os.path.join(HERE, 'generated', 'peaks', 'graphics'); os.makedirs(OUT, exist_ok=True)
W, H = 1920, 1080; AV = '/System/Library/Fonts/Avenir Next.ttc'
def f(sz, w='heavy'): return ImageFont.truetype(AV, sz, index={'heavy': 8, 'demi': 2, 'medium': 5, 'regular': 7}[w])
BG0, BG1 = (24, 10, 40), (58, 20, 64)                  # channel palette: dark purple
MAG, COR, AMB, WHITE = (255, 70, 170), (255, 110, 120), (255, 190, 90), (255, 255, 255)
def canvas():
    g = np.linspace(0, 1, H)[:, None, None]; arr = (np.array(BG0) * (1 - g) + np.array(BG1) * g) * np.ones((H, W, 3)); return Image.fromarray(arr.astype(np.uint8))
def text(d, xy, s, sz, fill=WHITE, w='heavy', anchor='la'): d.text(xy, s, font=f(sz, w), fill=fill, anchor=anchor)
P = json.load(open(os.path.join(HERE, 'generated', 'peaks', 'peaks.json')))
# ── 1) Kalaga vs Chiliad ──
k = P[0]; xs = np.linspace(k['x'] - 3200, k['x'] + 3200, 900); ys = np.full_like(xs, k['y'])
u = np.clip(np.round(hs.ZX + xs * hs.SC).astype(int), 0, hs.Z.shape[1] - 1); v = int(round(hs.ZY - k['y'] * hs.SC))
prof = np.maximum(hs.Z[v, u], 0)
im = canvas(); d = ImageDraw.Draw(im)
x0, x1, yb, top = 160, 1760, 930, 150; sc = (yb - top) / 860.0                     # px per metre (same scale for every height)
def Y(z): return yb - z * sc
pts = [(x0 + (x1 - x0) * i / (len(prof) - 1), Y(z)) for i, z in enumerate(prof)]
d.polygon([(x0, yb)] + pts + [(x1, yb)], fill=(46, 92, 58))
d.line(pts, fill=(140, 210, 140), width=4)
for z, col, lab, sub in ((798, MAG, 'MOUNT CHILIAD  798 m', 'GTA V'), (403, AMB, 'MOUNT KALAGA  403 m', 'GTA 6 (game heightmap)'), (105, COR, 'BRITTON HILL  105 m', "Florida's real highest point")):
    y = Y(z)
    for xx in range(x0, x1, 28): d.line([(xx, y), (xx + 16, y)], fill=col, width=4)
    text(d, (x0 + 10, y - 96), lab, 44, col); text(d, (x0 + 12, y - 44), sub, 26, (230, 220, 240), 'medium')
d.line([(x0, yb), (x1, yb)], fill=(200, 190, 210), width=3); text(d, (x1, yb + 14), 'sea level', 26, (200, 190, 210), 'medium', 'ra')
text(d, (W // 2, 60), "GTA 6'S TALLEST MOUNTAIN IS HALF OF CHILIAD", 64, WHITE, 'heavy', 'ma')
text(d, (W // 2, 1000), 'Mount Kalaga cross-section, west-east through the summit (6.4 km wide, heights x%.1f) - estimate from the game terrain' % (sc / ((x1 - x0) / 6400.0)), 26, (210, 200, 225), 'regular', 'ma')
im.save(os.path.join(OUT, 'kalaga_vs_chiliad.png'))
# ── 2) top 10 ──
seen, top10 = set(), []
for p in P:
    n = p['name'].split(',')[0].strip('"? ').strip()
    if not n or n in seen: continue
    seen.add(n); top10.append((n, p['z'], p['prominence']))
    if len(top10) == 10: break
im = canvas(); d = ImageDraw.Draw(im)
text(d, (W // 2, 50), "LEONIDA'S 10 HIGHEST SUMMITS", 66, WHITE, 'heavy', 'ma')
bx0, bx1, by0, bh, gap = 560, 1720, 160, 60, 24
for i, (n, z, pr) in enumerate(top10):
    y = by0 + i * (bh + gap); wpx = (bx1 - bx0) * z / top10[0][1]
    t = i / 9.0; col = tuple(int(a + (b - a) * t) for a, b in zip(MAG, AMB))
    d.rounded_rectangle([bx0, y, bx0 + wpx, y + bh], radius=14, fill=col)
    text(d, (bx0 - 24, y + bh // 2), '#%d  %s' % (i + 1, n.upper()), 38, WHITE, 'heavy', 'rm')
    text(d, (bx0 + wpx - 18, y + bh // 2), '%d m' % round(z), 36, BG0, 'heavy', 'rm')
text(d, (W // 2, 1050), 'elevation above sea level, estimated from the game heightmap', 26, (210, 200, 225), 'regular', 'ms')
im.save(os.path.join(OUT, 'top10.png'))
print([(n, round(z)) for n, z, _ in top10])
