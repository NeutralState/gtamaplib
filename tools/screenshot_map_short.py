"""screenshot_map_short.py [--cover] — vertical Short (1080x1920, 30 fps) "WHERE WERE THE NEW GTA 6 SCREENSHOTS TAKEN?": a flight over
the V17 map (Yanis's tiles, the whole pyramid: the level is picked from the zoom) from a Leonida overview to each Edge screenshot's
camera (gtamapdata/cameras.json), the screenshot as a card on top, a pin on the map, the place name and its real-life inspiration
(the V17 label in brackets) below. EXACT SPOT = a pose fitted on the skyline (view cone drawn), AREA = placed at town / block level.
Music: darksynth (DS_TRANSPOSE=1 DS_SEED=7) started one bar in, the drop on the first stop; one stop per bar.
Output: tools/generated/t4/shorts/map_edge_screenshots.mp4 (+ cover_map_edge.jpg with --cover)"""
import sys, os, json, math, subprocess, numpy as np, cv2
from collections import OrderedDict
from trailer_shorts import caption, tag, blend, W, H, BPM_BAR
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'generated', 't4', 'shorts')
TILES = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,17')
CAMS = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
FPS = 30; SEA = np.array([165, 102, 44], np.float32)
STOPS = [  # camera, place, real-life inspiration, exact?
    ('Ferris Wheel [Edge]', 'SHORELINE, VICE CITY', 'IRL: Bayfront Park, Miami', True),
    ('Jason and Lucia on a Motorbike [Edge]', 'STARFISH ISLAND BRIDGE', 'IRL: Star Island, Miami Beach', True),
    ('Open-Air Tattoo Parlour [Edge]', 'ROCKRIDGE', 'IRL: Riverside, Miami', False),
    ('Mendez on the Radio [Edge]', 'ROCKRIDGE', "same block as Trailer 3's robbery", False),
    ('Airboat in Emerald Springs [Edge]', 'EMERALD SPRINGS', 'IRL: Crystal River, Florida', False),
    ('Billy [Edge]', 'THRILLBILLY MUD CLUB', 'IRL: Redneck Yacht Club, Florida', False),
    ('Bikers in Millport [Edge]', 'MILLPORT', 'IRL: Fernandina Beach, Florida', False),
]
OVER = (-2500.0, 1500.0, 11.0)                                   # overview: centre x, y, metres per pixel (Leonida only: Yanis's legend /
                                                                 # frames panel east of x 4000 stays out of the shot)
_cache = OrderedDict()
def tile(L, ty, tx):
    k = (L, ty, tx)
    if k in _cache: _cache.move_to_end(k); return _cache[k]
    p = os.path.join(TILES, str(L), '%d,%d,%d.jpg' % (L, ty, tx)); t = cv2.imread(p) if os.path.exists(p) else None
    _cache[k] = t
    if len(_cache) > 1500: _cache.popitem(last=False)
    return t
def view(cx, cy, s):
    """the map centred on world (cx, cy) at s metres per output pixel"""
    L = int(min(5, max(0, math.ceil(5 - math.log2(max(s, 1e-3)) - 1e-9)))); res = 2.0 ** (5 - L); T = 256 * res
    x0, x1, y0, y1 = cx - W / 2 * s, cx + W / 2 * s, cy - H / 2 * s, cy + H / 2 * s
    tx0, tx1 = int((x0 + 16384) // T), int((x1 + 16384) // T); ty0, ty1 = int((16384 - y1) // T), int((16384 - y0) // T)
    blk = np.empty(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256, 3), np.uint8); blk[:] = SEA.astype(np.uint8)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            t = tile(L, ty, tx)
            if t is not None: blk[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = t
    k = s / res; ox = (x0 + 16384) / res - tx0 * 256; oy = (16384 - y1) / res - ty0 * 256
    M = np.float32([[k, 0, ox], [0, k, oy]])
    return cv2.warpAffine(blk, M, (W, H), flags=cv2.WARP_INVERSE_MAP | (cv2.INTER_AREA if k > 1 else cv2.INTER_LINEAR), borderValue=SEA.tolist()).astype(np.float32)
def to_px(x, y, cx, cy, s): return ((x - cx) / s + W / 2, (cy - y) / s + H / 2)
def ease(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
MAG = (180, 40, 255); CORAL = (90, 110, 255); AMBER = (40, 190, 255)            # channel palette (BGR): magenta, coral, amber
def draw_pin(img, u, v, k=1.0, pulse=0.0):
    u, v = int(round(u)), int(round(v))
    if pulse > 0: cv2.circle(img, (u, v), int(22 + 60 * pulse), MAG, 4, cv2.LINE_AA)
    cv2.circle(img, (u, v), int(19 * k), (255, 255, 255), -1, cv2.LINE_AA); cv2.circle(img, (u, v), int(14 * k), MAG, -1, cv2.LINE_AA)
def draw_cone(img, cam, cx, cy, s, a):
    c = CAMS[cam]; h = 360 - c['ypr'][0]; hf = c['fov'][0]; x, y = c['xyz'][:2]; P = [to_px(x, y, cx, cy, s)]
    for d in np.linspace(h - hf / 2, h + hf / 2, 16):
        P.append(to_px(x + 900 * math.sin(math.radians(d)), y + 900 * math.cos(math.radians(d)), cx, cy, s))
    ov = img.copy(); cv2.fillPoly(ov, [np.int32(P)], MAG, cv2.LINE_AA); img[:] = img * (1 - 0.35 * a) + ov * 0.35 * a
def card(path, w=1000):
    im = cv2.imread(path); h = int(w * im.shape[0] / im.shape[1]); im = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)
    c = np.full((h + 16, w + 16, 3), 255, np.uint8); c[8:-8, 8:-8] = im; return c.astype(np.float32)
def main(music):
    cards = [card(os.path.join(REPO, 'frames', cam + '.png')) for cam, *_ in STOPS]
    pins = [CAMS[cam]['xyz'][:2] for cam, *_ in STOPS]
    HOOK = caption('WHERE WERE THE NEW|GTA 6 SCREENSHOTS|TAKEN?', 104, 700, 12)
    NAMES = [caption(p, 92, 1470, 10) for _, p, _, _ in STOPS]
    REAL = [caption(r, 54, 1575, 7) for _, _, r, _ in STOPS]
    T_EX, T_AR = tag('EXACT SPOT (3D MATCH)'), tag('AREA')
    COUNT = [tag('%d / %d' % (i + 1, len(STOPS))) for i in range(len(STOPS))]
    END = caption('WHICH ONE SHOULD|I REBUILD IN 3D?', 100, 760, 12); SRC = tag('MAP: YANIS V17 COMMUNITY MAP + MY 3D MAP')
    B = BPM_BAR; N1 = len(STOPS); DUR = (N1 + 2) * B; N = int(round(DUR * FPS))
    vid = os.path.join(OUT, '_m.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', vid], stdin=subprocess.PIPE)
    def cam_at(i, zoom):                                          # view on stop i: pin at v 1150 (under the card)
        x, y = pins[i]; return x, y + 190 * zoom, zoom
    ZS = [1.4 if ex else 2.2 for *_, ex in STOPS]
    for n in range(N):
        t = n / FPS; seg = int(t // B); u = (t - seg * B) / B
        if seg == 0:                                               # overview, slow push
            cx, cy, s = OVER[0], OVER[1], OVER[2] * (1 - 0.06 * u); i = -1
        elif seg <= N1:
            i = seg - 1; a = (OVER if i == 0 else cam_at(i - 1, ZS[i - 1])); b = cam_at(i, ZS[i]); f = ease(u / 0.34)
            d = math.hypot(b[0] - a[0], b[1] - a[1]); bump = math.log(1 + d / 1500) * 1.1 if i > 0 else 0.0
            cx, cy = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            s = math.exp(math.log(a[2]) + (math.log(b[2]) - math.log(a[2])) * f + bump * math.sin(math.pi * f)) * (1 - 0.04 * ease((u - 0.34) / 0.66))
        else:                                                      # outro: back to the overview, all pins
            i = N1; a = cam_at(N1 - 1, ZS[-1]); f = ease(u / 0.4); b = OVER
            cx, cy = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f; s = math.exp(math.log(a[2]) + (math.log(b[2]) - math.log(a[2])) * f)
        img = view(cx, cy, s)
        if 0 <= i < N1 and STOPS[i][3] and u > 0.34: draw_cone(img, STOPS[i][0], cx, cy, s, ease((u - 0.34) / 0.15))
        for j in range(len(pins)):
            if i == N1 or j < i or (j == i and u > 0.3):
                pu, pv = to_px(*pins[j], cx, cy, s)
                if -50 < pu < W + 50 and -50 < pv < H + 50:
                    pulse = ((u - 0.34) % 0.5) / 0.5 if j == i and u > 0.34 else 0.0
                    draw_pin(img, pu, pv, 1.0 if j == i or i == N1 else 0.7, pulse)
        img = img * 0.82 + 255 * 0.0                                 # slightly darker map: the text reads better
        if seg == 0:
            blend(img, HOOK, 0, 0, min(1.0, t / 0.2))
        elif i < N1:
            al = ease((u - 0.3) / 0.1)
            if al > 0:
                c = cards[i]; ch, cw = c.shape[:2]; y0 = 150 + int(30 * (1 - al)); x0 = (W - cw) // 2
                img[y0:y0 + ch, x0:x0 + cw] = img[y0:y0 + ch, x0:x0 + cw] * (1 - al) + c * al
                blend(img, COUNT[i], x0 + 20, y0 + 20, al)
                blend(img, NAMES[i], 0, 0, al); blend(img, REAL[i], 0, 0, al)
                tg = T_EX if STOPS[i][3] else T_AR; blend(img, tg, (W - tg[1].shape[1]) // 2, 1640, al)
            if 0.3 <= u < 0.3 + 0.12:                              # flash on the arrival beat
                k = 1 - (u - 0.3) / 0.12; img = img * (1 - 0.35 * k) + 255 * 0.35 * k
        else:
            blend(img, END, 0, 0, ease(u / 0.3)); blend(img, SRC, (W - SRC[1].shape[1]) // 2, 1780, ease(u / 0.3))
        ff.stdin.write(np.clip(img, 0, 255).astype(np.uint8).tobytes())
    ff.stdin.close(); ff.wait()
    out = os.path.join(OUT, 'map_edge_screenshots.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', vid, '-ss', '%.4f' % B, '-i', music, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-t', '%.3f' % DUR,
                    '-af', 'afade=t=out:st=%.3f:d=0.3,loudnorm=I=-14:TP=-1.5' % (DUR - 0.3), '-c:a', 'aac', '-b:a', '256k', '-dn', '-map_metadata', '-1',
                    '-movflags', '+faststart', out], check=True)
    os.remove(vid); return out
def make_cover():
    """1080x1920: the overview with every pin, three screenshot cards, the hook"""
    cx, cy, s = OVER[0], OVER[1], OVER[2]; img = view(cx, cy, s) * 0.8
    for cam, *_ in STOPS: draw_pin(img, *to_px(*CAMS[cam]['xyz'][:2], cx, cy, s))
    for k, (cam, y0) in enumerate((('Ferris Wheel [Edge]', 120), ('Bikers in Millport [Edge]', 1180), ('Billy [Edge]', 1470))):
        c = card(os.path.join(REPO, 'frames', cam + '.png'), 520 if k else 900); ch, cw = c.shape[:2]; x0 = (W - cw) // 2 if k == 0 else (40 if k == 1 else W - cw - 40)
        img[y0:y0 + ch, x0:x0 + cw] = c
    blend(img, caption('WHERE WERE THE NEW|GTA 6 SCREENSHOTS|TAKEN?', 110, 820, 14), 0, 0, 1.0)
    out = os.path.join(OUT, 'cover_map_edge.jpg'); cv2.imwrite(out, np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 93]); return out
if __name__ == '__main__':
    print(make_cover() if '--cover' in sys.argv else main(sys.argv[1]))
