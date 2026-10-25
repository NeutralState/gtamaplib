"""compose.py [out.mp4] — HURRICANE video v3 « How high must the sea rise to drown GTA 6? »: orbit + dive (space.py), top-down Vice City
under the storm (topdown.py B), the Brickell towers at street level to +20 m (view3d storm / calm passes, rec_job.js), top-down sea
rise to Mount Kalaga (topdown.py D), end card. GTA VI sunset palette (channel colours), synthesized sound (no samples). 1080p60."""
import sys, os, json, glob, subprocess, wave, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from common import TOOLS, WORK, W, H, FPS, ease
SPACE, TOP, REC = os.path.join(WORK, 'space'), os.path.join(WORK, 'top'), os.path.join(WORK, 'rec')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(TOOLS, 'generated', 'hurricane', 'video', 'gta6_hurricane_v3.mp4')
J = json.load(open(os.path.join(WORK, 'arrival_hi.json'))); CUR = np.array(J['curve'], float)
IMP = '/System/Library/Fonts/Supplemental/Impact.ttf'; FR = '/System/Library/Fonts/HelveticaNeue.ttc'
PURPLE = (36, 10, 52); SUNSET = [(255, 70, 170), (255, 110, 120), (255, 190, 90)]; NEON = [(255, 240, 250), (255, 150, 215), (200, 110, 255)]
T_B, T_C, T_D, T_E, T_END = 11.0, 23.0, 31.0, 57.2, 61.8
C_OFF = 43.0 - T_C                                    # 3D clip: view3d timeline 43.0-51.0 s
STRIKES = [14.0, 18.4, 21.7, 24.8, 28.3]
def at(lv): return float(np.interp(lv, CUR[:, 0], CUR[:, 1])), float(np.interp(lv, CUR[:, 0], CUR[:, 2]))
def fade(T, a, b, f=0.4): return ease((T - a) / f) * (1 - ease((T - (b - f)) / f))
def grad(h, stops):
    t = np.linspace(0, 1, max(1, h)); n = len(stops) - 1; out = np.zeros((len(t), 3))
    for i in range(n):
        a, b = np.array(stops[i], float), np.array(stops[i + 1], float); m = (t >= i / n) & (t <= (i + 1) / n); out[m] = a + (b - a) * ((t[m] - i / n) * n)[:, None]
    return out
def gtext(size_wh, xy, s, size, stops, anchor='mm', stroke=7, font=IMP, glow=(255, 60, 170)):
    Wl, Hl = size_wh; f = ImageFont.truetype(font, size)
    mask = Image.new('L', (Wl, Hl), 0); ImageDraw.Draw(mask).text(xy, s, font=f, fill=255, anchor=anchor)
    smask = Image.new('L', (Wl, Hl), 0); ImageDraw.Draw(smask).text(xy, s, font=f, fill=255, anchor=anchor, stroke_width=stroke)
    bb = mask.getbbox(); g = np.zeros((Hl, Wl, 3), np.uint8); g[bb[1]:bb[3]] = grad(bb[3] - bb[1], stops)[:, None, :].astype(np.uint8)
    fill = Image.fromarray(g).convert('RGBA'); fill.putalpha(mask)
    st = Image.new('RGBA', (Wl, Hl), PURPLE + (255,)); st.putalpha(smask)
    gw = Image.new('RGBA', (Wl, Hl), glow + (255,)); gw.putalpha(smask.filter(ImageFilter.GaussianBlur(12)).point(lambda p: int(p * 0.8)))
    sh = Image.new('RGBA', (Wl, Hl), (0, 0, 0, 255)); sh.putalpha(ImageChops.offset(smask, 4, 6).filter(ImageFilter.GaussianBlur(4)).point(lambda p: int(p * 0.6)))
    lay = Image.new('RGBA', (Wl, Hl), (0, 0, 0, 0))
    for L in (gw, sh, st, fill): lay = Image.alpha_composite(lay, L)
    return lay
def to_ov(im): a = np.array(im).astype(np.float32); return a[:, :, [2, 1, 0]], a[:, :, 3:] / 255.0
def blend(dst, ov, x, y, alpha):
    if alpha <= 0.002: return
    rgb, a = ov; x = max(0, x); y = max(0, y); a = a[:dst.shape[0] - y, :dst.shape[1] - x] * alpha; rgb = rgb[:a.shape[0], :a.shape[1]]
    sub = dst[y:y + a.shape[0], x:x + a.shape[1]]; sub[:] = sub * (1 - a) + rgb * a
def band(w, h, r=22, a=170): im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=(30, 8, 44, a), outline=(255, 110, 190, 150), width=2); return im
def tw(txt, f): return int(ImageDraw.Draw(Image.new('RGBA', (8, 8))).textlength(txt, font=f))
def centre_block(lines, y0=None, pad=50):
    """lines: (text, size, stops|None, font) — centred block on a soft purple panel."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); hs = [int(s * 1.25) for _, s, _, _ in lines]; tot = sum(hs)
    y = (H - tot) // 2 if y0 is None else y0
    bw = max(tw(t, ImageFont.truetype(f, s)) for t, s, _, f in lines) + 2 * pad
    b = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(b).rounded_rectangle([W // 2 - bw // 2, y - pad // 2, W // 2 + bw // 2, y + tot + pad // 2], radius=36, fill=(30, 8, 44, 160))
    im = Image.alpha_composite(im, b.filter(ImageFilter.GaussianBlur(5)))
    for (t, s, st, f), h in zip(lines, hs):
        if st: im = Image.alpha_composite(im, gtext((W, H), (W // 2, y + h // 2), t, s, st, stroke=max(4, s // 14), font=f))
        elif t: ImageDraw.Draw(im).text((W // 2, y + h // 2), t, font=ImageFont.truetype(f, s), fill=(255, 225, 240, 255), anchor='mm')
        y += h
    return to_ov(im)
def tag(txt, size=46):
    f = ImageFont.truetype(IMP, size); w = tw(txt, f) + 70; h = int(size * 1.85)
    im = band(w, h); im = Image.alpha_composite(im, gtext((w, h), (w // 2, h // 2), txt, size, SUNSET, stroke=4)); return to_ov(im)
TITLE = centre_block([('HOW HIGH MUST THE SEA RISE', 104, SUNSET, IMP), ('TO DROWN ALL OF GTA 6?', 104, SUNSET, IMP), ("on the game's real terrain", 40, None, FR)])
STARTS = tag('IT STARTS WITH A HURRICANE...', 44)
STORMPASS = centre_block([('THE STORM PASSES...', 80, NEON, IMP), ('THE WATER KEEPS RISING', 80, SUNSET, IMP)], y0=110)
LASTPLACE = centre_block([('LAST PLACE STANDING', 96, SUNSET, IMP), ('MOUNT KALAGA  —  403 m', 70, NEON, IMP)], y0=90)
END = centre_block([('AT +403 m', 120, SUNSET, IMP), ('ALL OF GTA 6 IS UNDERWATER', 92, SUNSET, IMP), ('', 20, None, FR),
                    ('half of Leonida is less than 7 m above the sea  ·  Vice City is gone at +40 m', 36, None, FR),
                    ('estimate: sea connected to the ocean over the game heightmap, YANIS V17 map', 28, None, FR)])
TAGS = [(11.9, 15.2, tag('VICE CITY  —  DOWNTOWN')), (23.3, 26.6, tag('BRICKELL  —  STREET LEVEL')), (36.6, 40.0, tag('LEONIDA'))]
GONE = [('KEY LENTO', 8.7), ('WATSON BAY', 8.6), ('PEREGRINE BAY', 9.9), ('VICE BEACH', 15.3), ('CAPRI', 16.9), ('HAMLET', 19.0), ('VC AIRPORT', 20.8),
        ('BELVILLE', 25.0), ('VICE CITY', 40.0), ('VICE-DALE COUNTY', 44.5), ('WANING SANDS', 48.0), ('MARIANA COUNTY', 52.0), ('AMBROSIA', 55.5),
        ('LEONARD COUNTY', 73.5), ('GELLHORN RACEWAY', 97.5), ('PORT GELLHORN', 106.0), ('KELLY COUNTY', 206.5)]
GONE.sort(key=lambda g: g[1])
BIG = {'VICE CITY': centre_block([('VICE CITY IS GONE', 104, SUNSET, IMP), ('+40 m', 60, NEON, IMP)], y0=120),
       'PORT GELLHORN': centre_block([('PORT GELLHORN IS GONE', 96, SUNSET, IMP), ('+106 m', 60, NEON, IMP)], y0=120),
       'KELLY COUNTY': centre_block([('ONLY THE NORTH HILLS ARE LEFT', 92, SUNSET, IMP), ('+207 m', 60, NEON, IMP)], y0=120)}
F_G = ImageFont.truetype(IMP, 34); F_GH = ImageFont.truetype(IMP, 30); F_GL = ImageFont.truetype(FR, 28)
def gone_panel(items, newest_alpha):
    w, rowh = 430, 50; h = 70 + rowh * len(items)
    im = band(w, h, 22); d = ImageDraw.Draw(im); d.text((28, 22), 'GONE', font=F_GH, fill=(255, 190, 220, 255))
    for i, (name, lv) in enumerate(items):
        y = 66 + i * rowh; a = int(255 * (newest_alpha if i == len(items) - 1 else 1.0))
        d.text((28, y), name, font=F_G, fill=(255, 240, 250, a)); d.text((w - 28, y + 4), '+%s m' % (('%.1f' % lv) if lv < 10 else '%d' % round(lv)), font=F_GL, fill=(255, 190, 120, a), anchor='ra')
        tl = tw(name, F_G); d.line([(26, y + 22), (30 + tl, y + 22)], fill=(255, 70, 170, a), width=3)
    return to_ov(im)
F_LBL = ImageFont.truetype(IMP, 30); F_NUM = ImageFont.truetype(IMP, 52)
HUD_W, HUD_H = 540, 330; HUD_BG = band(HUD_W, HUD_H, 26)
def hud(lv):
    nb, left = at(lv)
    im = HUD_BG.copy(); d = ImageDraw.Draw(im)
    d.text((34, 26), 'SEA LEVEL', font=F_LBL, fill=(255, 190, 220, 255))
    im = Image.alpha_composite(im, gtext((HUD_W, HUD_H), (32, 118), ('+%.1f m' % lv) if lv < 10 else '+%d m' % int(lv), 96, SUNSET, anchor='lm', stroke=5))
    d = ImageDraw.Draw(im)
    d.text((34, 190), 'BUILDINGS UNDERWATER', font=F_LBL, fill=(255, 190, 220, 255)); d.text((HUD_W - 34, 182), '{:,}'.format(int(round(nb))), font=F_NUM, fill=(255, 240, 250, 255), anchor='ra')
    d.text((34, 262), 'LAND LEFT', font=F_LBL, fill=(255, 190, 220, 255)); d.text((HUD_W - 34, 254), ('%.1f%%' % left) if left < 10 else '%d%%' % int(round(left)), font=F_NUM, fill=(255, 240, 250, 255), anchor='ra')
    return to_ov(im)
L_BEFORE = to_ov(gtext((360, 110), (180, 55), 'BEFORE', 60, NEON, stroke=6)); L_NOW = to_ov(gtext((300, 110), (150, 55), 'NOW', 60, SUNSET, stroke=6))
TM = {}
for p in glob.glob(os.path.join(TOP, 'meta_*.json')):
    for m in json.load(open(p)): TM[m['n']] = m
RM = {}
for l in open(os.path.join(REC, 'meta.jsonl')):
    m = json.loads(l); RM[int(m['n'])] = m
N = int(round(T_END * FPS)); NMAX = max(TM)
def level_at(n):
    T = n / FPS
    if T < T_B: return 0.0
    if T < T_C or T >= T_D: return TM[min(n, NMAX)]['level']
    return float(RM[int(round((T + C_OFF) * FPS)) + 300000]['surge'])
LEV = np.array([level_at(n) for n in range(N)])
cross = {}
for name, lv in GONE:
    k = np.nonzero(LEV >= lv)[0]; cross[name] = k[0] / FPS if len(k) else None
print({k: (round(v, 2) if v else None) for k, v in cross.items()})
def rd(p): im = cv2.imread(p); assert im is not None, p; return im.astype(np.float32)
VID = OUT + '.video.mp4'
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                       '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', str(FPS), VID], stdin=subprocess.PIPE)
hud_cache = {}; gone_cache = {}; last = None
for n in range(N):
    T = n / FPS; lv = LEV[n]
    if T < T_B:
        fr = rd(os.path.join(SPACE, '%06d.jpg' % n))
        blend(fr, TITLE, 0, 0, fade(T, 0.7, 5.7, 0.6)); blend(fr, STARTS, 60, 56, fade(T, 5.9, 9.6))
    elif T < T_C or (T_D <= T < T_E):
        fr = rd(os.path.join(TOP, '%06d.jpg' % n))
        if T < T_C: wo = 1 - ease((T - T_B) / 0.7); fr = fr * (1 - wo) + 238 * wo          # out of the white-out
    elif T < T_D:
        m3 = int(round((T + C_OFF) * FPS)); fr = rd(os.path.join(REC, 'frames', '%06d.jpg' % (m3 + 300000)))
        k = ease((T - 28.3) / 0.5) * (1 - ease((T - 29.9) / 0.5))     # one look back at the sunny street
        if k > 0.002:
            xi = int(round(W - W * 0.5 * k)); calm = rd(os.path.join(REC, 'frames', '%06d.jpg' % (m3 + 400000)))
            fr[:, xi:] = calm[:, xi:]
            if xi < W:
                cv2.line(fr, (xi, 0), (xi, H), (255, 245, 255), 6); cv2.line(fr, (xi, 0), (xi, H), (170, 70, 255), 2)
                if xi > 330: blend(fr, L_NOW, xi - 20 - L_NOW[1].shape[1], 150, min(1, k * 1.5))
                if xi < W - 280: blend(fr, L_BEFORE, xi + 20, 150, min(1, k * 1.5))
    else:
        if last is None: last = rd(os.path.join(TOP, '%06d.jpg' % (int(round(T_E * FPS)) - 1)))
        k = ease((T - T_E) / 0.8); fr = last * (1 - 0.5 * k); blend(fr, END, 0, 0, k)
        fr *= 1 - ease((T - (T_END - 0.9)) / 0.9)
    if T_B <= T < T_E:
        for a, b, ov in TAGS: blend(fr, ov, 60, 56, fade(T, a, b))
        ha = ease((T - 11.6) / 0.6) * (1 - ease((T - 56.8) / 0.4))
        key = round(lv, 1) if lv < 10 else int(lv)
        if key not in hud_cache: hud_cache = {key: hud(float(key))}
        blend(fr, hud_cache[key], 60, H - HUD_H - 60, ha)
        items = [(g, l) for g, l in GONE if cross[g] is not None and cross[g] <= T]
        if items:
            na = round(ease((T - cross[items[-1][0]]) / 0.35), 2); gk = (len(items), na)
            if gk not in gone_cache: gone_cache = {gk: gone_panel(items[-7:], na)}
            ov = gone_cache[gk]; blend(fr, ov, W - ov[1].shape[1] - 50, 56, ha)
        for name, ov in BIG.items():
            c = cross[name]
            if c is not None: blend(fr, ov, 0, 0, fade(T, c + 0.1, c + 2.6, 0.35))
        blend(fr, STORMPASS, 0, 0, fade(T, 31.5, 35.2, 0.5))
        blend(fr, LASTPLACE, 0, 0, fade(T, 53.6, 57.1, 0.5))
    ff.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
ff.stdin.close(); ff.wait()
# ── sound: orbit hum, dive whoosh, rain / wind / thunder under the storm, deep water and a falling drone as the sea rises ──
SR = 48000; D = N / FPS; L = int(D * SR); t = np.arange(L) / SR; rng = np.random.default_rng(7)
def bandnoise(lo, hi, n=L, seed=0):
    x = np.random.default_rng(seed).standard_normal(n); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    X *= ((f >= lo) & (f <= hi)) / np.sqrt(np.maximum(f, 20) / 400); return np.fft.irfft(X, n)
def nrm(x): return x / (np.abs(x).max() + 1e-9)
def env(points): p = np.array(points, float); return np.interp(t, p[:, 0], p[:, 1])
storm = env([(0, 0), (10.6, 0), (11.2, 1), (31.0, 1), (35.0, 0.0), (D, 0)])
orbit = nrm(bandnoise(30, 300, seed=9)) * 0.10 * env([(0, 0.6), (6, 0.7), (10.0, 1.0), (11.0, 0), (D, 0)])
dive = nrm(bandnoise(200, 3000, seed=8)) * env([(0, 0), (6, 0), (9.5, 0.35), (10.9, 0.7), (11.3, 0), (D, 0)])
rainL = nrm(bandnoise(500, 9000, seed=2)) * 0.30 * storm; rainR = nrm(bandnoise(500, 9000, seed=3)) * 0.30 * storm
gust = 0.55 + 0.45 * np.sin(2 * np.pi * t / 7.3 + 1.0) * np.sin(2 * np.pi * t / 3.1)
wind = nrm(bandnoise(70, 500, seed=4)) * 0.40 * storm * gust
water = nrm(bandnoise(40, 600, seed=12)) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 5.0) ** 2) * 0.22 * env([(0, 0), (30, 0), (34, 1), (56, 1.3), (57.3, 0), (D, 0)])
f0 = 55 * env([(0, 1), (31, 1), (56, 0.75), (D, 0.75)]); ph = 2 * np.pi * np.cumsum(f0) / SR
drone = (np.sin(ph) * 0.5 + np.sin(ph * 1.498) * 0.3 + np.sin(ph * 2 + 0.3 * np.sin(2 * np.pi * 0.2 * t)) * 0.2)
drone *= 0.18 * env([(0, 0.3), (5, 0.6), (11, 1), (31, 1), (45, 1.4), (56.5, 1.8), (57.3, 0.6), (D - 0.9, 0.5), (D, 0)])
fx = np.zeros(L)
def add(tm, x):
    a = int(tm * SR); n = min(L - a, len(x))
    if n > 0: fx[a:a + n] += x[:n]
for i, s in enumerate(STRIKES + [11.05]):
    d0 = s + (0.12 + 0.5 * rng.random() if s != 11.05 else 0.0); n = int(5.5 * SR); tt = np.arange(n) / SR
    crack = bandnoise(1500, 9000, n, 100 + i) * np.exp(-tt / 0.08)
    rumble = bandnoise(25, 220, n, 200 + i) * np.exp(-tt / 1.6) * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * tt * (1.3 + rng.random()))))
    add(d0, nrm(crack) * 0.35 + nrm(rumble) * 0.95)
for j, c in enumerate([cross[k] for k in BIG if cross[k] is not None] + [53.6, T_E]):   # low boom for the big moments
    n = int(3.0 * SR); tt = np.arange(n) / SR
    add(c, nrm(np.sin(2 * np.pi * 42 * tt * (1 - 0.15 * tt)) * np.exp(-tt / 0.9) + 0.3 * bandnoise(20, 160, n, 300 + j) * np.exp(-tt / 0.6)) * 0.9)
for name, lv in GONE:                                                  # soft tick for each region gone
    c = cross[name]
    if c is None: continue
    n = int(0.25 * SR); tt = np.arange(n) / SR; add(c, np.sin(2 * np.pi * 880 * tt) * np.exp(-tt / 0.05) * 0.18)
mixL = orbit + dive + rainL + wind + water + drone + fx; mixR = orbit + dive + rainR + wind * 0.95 + water * 0.97 + drone + fx * 0.97
fo = 1 - np.clip((t - (D - 0.9)) / 0.9, 0, 1); mixL *= fo; mixR *= fo
st = np.stack([mixL, mixR], 1); st = (st / (np.abs(st).max() + 1e-9) * 0.9 * 32767).astype(np.int16)
WAV = OUT + '.wav'
with wave.open(WAV, 'wb') as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', VID, '-i', WAV, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11',
                '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-dn', '-map_chapters', '-1', '-map_metadata', '-1', '-movflags', '+faststart', '-shortest', OUT], check=True)
os.remove(VID); os.remove(WAV); print('ok', OUT, N, 'frames')
