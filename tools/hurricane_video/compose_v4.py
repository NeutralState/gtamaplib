"""compose_v4.py [out.mp4] — HURRICANE video v4 « What if a hurricane hit Leonida? », realistic surge only (up to Katrina's 8.5 m):
orbit + dive (space.py) -> Downtown Vice City floods, top-down (topdown.py B, 0 -> 5 m, sped up) -> Brickell at street level
(view3d storm pass, 5 -> 8.9 m) -> all of Leonida in 3D, the sea rising 0 -> 8.5 m while the dry land pops (island_job.js).
Typography: plain documentary style — white Avenir Next with a soft shadow, one thin magenta accent, no panels / gradients / glow."""
import sys, os, json, glob, subprocess, wave, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from common import TOOLS, WORK, W, H, FPS, ease
SPACE, TOP, REC = os.path.join(WORK, 'space'), os.path.join(WORK, 'top'), os.path.join(WORK, 'rec2')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(TOOLS, 'generated', 'hurricane', 'video', 'gta6_hurricane_v4.mp4')
AV = '/System/Library/Fonts/Avenir Next.ttc'
def font(size, face):                                   # face: 'demi' | 'medium' | 'regular'
    return ImageFont.truetype(AV, size, index={'demi': 2, 'medium': 5, 'regular': 7}[face])
ACCENT = (255, 70, 170)                                 # channel magenta, used as a thin line only
T_B, T_C, T_D, T_END3, T_END = 11.0, 18.0, 21.8, 38.8, 42.6
C_T0, C_T1 = 40.5, 44.2                                 # view3d timeline of the Brickell clip
def fade(T, a, b, f=0.5): return ease((T - a) / f) * (1 - ease((T - (b - f)) / f))
def layer(draw_fn):
    """RGBA text layer with a soft drop shadow (no stroke, no glow)."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); draw_fn(ImageDraw.Draw(im))
    a = im.split()[3]; sh = Image.new('RGBA', (W, H), (0, 0, 0, 255)); sh.putalpha(a.filter(ImageFilter.GaussianBlur(7)).point(lambda p: int(p * 0.55)))
    sh = Image.merge('RGBA', (*sh.split()[:3], Image.fromarray(np.roll(np.array(sh.split()[3]), (3, 2), axis=(0, 1)))))
    out = Image.alpha_composite(sh, im); arr = np.array(out).astype(np.float32); return arr[:, :, [2, 1, 0]], arr[:, :, 3:] / 255.0
def blend(dst, ov, alpha):
    if alpha <= 0.002: return
    rgb, a = ov; a = a * alpha; dst[:] = dst * (1 - a) + rgb * a
def title_layer():
    def d(g):
        g.line([(W // 2 - 40, 438), (W // 2 + 40, 438)], fill=ACCENT + (255,), width=4)
        g.text((W // 2, 505), 'What if a hurricane hit Leonida?', font=font(76, 'demi'), fill=(255, 255, 255, 255), anchor='mm')
        g.text((W // 2, 578), "Storm surge simulated on the game's real terrain", font=font(32, 'regular'), fill=(255, 255, 255, 215), anchor='mm')
    return layer(d)
def sub_layer(text, small=None):
    """one subtitle line, bottom centre"""
    def d(g):
        y = H - 150 if small else H - 120
        g.text((W // 2, y), text, font=font(42, 'medium'), fill=(255, 255, 255, 255), anchor='mm')
        if small: g.text((W // 2, y + 52), small, font=font(28, 'regular'), fill=(255, 255, 255, 200), anchor='mm')
    return layer(d)
def place_layer(text):
    """place name, top left, with the thin accent line"""
    def d(g):
        g.line([(72, 84), (122, 84)], fill=ACCENT + (255,), width=4)
        g.text((72, 100), text, font=font(36, 'demi'), fill=(255, 255, 255, 255), anchor='la')
    return layer(d)
LV_CACHE = {}
def level_layer(lv):
    key = round(lv, 1)
    if key not in LV_CACHE:
        def d(g):
            g.text((W - 72, 76), 'storm surge', font=font(24, 'regular'), fill=(255, 255, 255, 200), anchor='ra')
            g.text((W - 72, 106), '+%.1f m' % key, font=font(60, 'medium'), fill=(255, 255, 255, 255), anchor='ra')
        LV_CACHE.clear(); LV_CACHE[key] = layer(d)
    return LV_CACHE[key]
TITLE = title_layer()
_y = np.arange(H, dtype=np.float32)[:, None, None]
GRAD_BOT = np.clip((_y - (H - 340)) / 340.0, 0, 1) ** 1.4          # soft darkening behind the subtitles (no panel)
GRAD_TOP = np.clip(1 - _y / 230.0, 0, 1) ** 1.4                    # behind the place name / surge level
SUBS = [(12.2, 16.8, sub_layer('Downtown Vice City sits only a few metres above the sea.')),
        (23.2, 27.6, sub_layer('The same surge, across all of Leonida.')),
        (28.2, 32.4, sub_layer('+8.5 m: the highest storm surge ever measured in the US', 'Hurricane Katrina, 2005')),
        (32.6, 36.2, sub_layer('Vice City 91% underwater  ·  Vice Beach 99%  ·  the Keys gone')),
        (36.4, 39.2, sub_layer('Only the north stays dry.')),
        (39.4, 42.4, sub_layer('Half of Leonida is less than 7 m above the sea.', "estimate on the game's heightmap: still water, no levees"))]
PLACES = [(11.9, 15.6, place_layer('Downtown Vice City')), (18.2, 21.6, place_layer('Brickell')), (22.0, 26.0, place_layer('Leonida'))]
# frame sources
TM = {}
for p in glob.glob(os.path.join(TOP, 'meta_B*.json')):
    for m in json.load(open(p)): TM[m['n']] = m
bn = sorted(TM); n5 = next(n for n in bn if TM[n]['level'] >= 5.0)
RM = {}
for l in open(os.path.join(REC, 'meta.jsonl')):
    m = json.loads(l); RM[int(m['n'])] = m
def src(T):
    """(path, level) of the frame shown at time T"""
    if T < T_B: return os.path.join(SPACE, '%06d.jpg' % int(round(T * FPS))), None
    if T < T_C:
        n = int(round(660 + (T - T_B) / (T_C - T_B) * (n5 - 660))); return os.path.join(TOP, '%06d.jpg' % n), TM[n]['level']
    if T < T_D:
        t3 = C_T0 + (T - T_C) / (T_D - T_C) * (C_T1 - C_T0); n = int(round(t3 * FPS)) + 300000
        n = min(n, max(k for k in RM if k < 400000)); return os.path.join(REC, 'frames', '%06d.jpg' % n), float(RM[n]['surge'])
    i = min(int(round((T - T_D) * FPS)), max(k for k in RM if k >= 500000) - 500000); n = 500000 + i
    return os.path.join(REC, 'frames', '%06d.jpg' % n), float(RM[n]['level'])
N = int(round(T_END * FPS)); VID = OUT + '.video.mp4'
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                       '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', str(FPS), VID], stdin=subprocess.PIPE)
for n in range(N):
    T = n / FPS
    p, lv = src(min(T, T_END3 - 1.0 / FPS))
    fr = cv2.imread(p).astype(np.float32)
    if T_B <= T < T_B + 0.7: wo = 1 - ease((T - T_B) / 0.7); fr = fr * (1 - wo) + 238 * wo      # out of the clouds
    if T >= T_END3: fr *= 1 - 0.35 * ease((T - T_END3) / 0.8)                                    # held last frame, dimmed under the end line
    blend(fr, TITLE, fade(T, 1.2, 6.0, 0.7))
    sa = max([fade(T, a, b) for a, b, _ in SUBS] + [0.0]); la = ease((T - 11.8) / 0.5) * (1 - ease((T - 38.2) / 0.5)) if lv is not None and T < T_END3 else 0.0
    if sa > 0.002: fr *= 1 - 0.42 * sa * GRAD_BOT
    ta = max([fade(T, a, b) for a, b, _ in PLACES] + [la])
    if ta > 0.002: fr *= 1 - 0.30 * ta * GRAD_TOP
    for a, b, ov in PLACES: blend(fr, ov, fade(T, a, b))
    for a, b, ov in SUBS: blend(fr, ov, fade(T, a, b))
    if la > 0.002: blend(fr, level_layer(lv), la)
    fr *= 1 - ease((T - (T_END - 1.0)) / 1.0)
    ff.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
ff.stdin.close(); ff.wait()
# ── sound (synthesized): orbit hum + dive whoosh, storm (rain, wind, thunder) over Downtown and Brickell, then the calm island shot ──
SR = 48000; D = N / FPS; L = int(D * SR); t = np.arange(L) / SR; rng = np.random.default_rng(7)
def bandnoise(lo, hi, n=L, seed=0):
    x = np.random.default_rng(seed).standard_normal(n); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    X *= ((f >= lo) & (f <= hi)) / np.sqrt(np.maximum(f, 20) / 400); return np.fft.irfft(X, n)
def nrm(x): return x / (np.abs(x).max() + 1e-9)
def env(points): p = np.array(points, float); return np.interp(t, p[:, 0], p[:, 1])
storm = env([(0, 0), (10.6, 0), (11.2, 1), (21.4, 1), (22.6, 0.0), (D, 0)])
orbit = nrm(bandnoise(30, 300, seed=9)) * 0.10 * env([(0, 0.6), (6, 0.7), (10.0, 1.0), (11.0, 0), (D, 0)])
dive = nrm(bandnoise(200, 3000, seed=8)) * env([(0, 0), (6, 0), (9.5, 0.35), (10.9, 0.7), (11.3, 0), (D, 0)])
rainL = nrm(bandnoise(500, 9000, seed=2)) * 0.28 * storm; rainR = nrm(bandnoise(500, 9000, seed=3)) * 0.28 * storm
gust = 0.55 + 0.45 * np.sin(2 * np.pi * t / 7.3 + 1.0) * np.sin(2 * np.pi * t / 3.1)
wind = nrm(bandnoise(70, 500, seed=4)) * 0.36 * storm * gust
calm = nrm(bandnoise(60, 900, seed=1)) * (0.5 + 0.5 * np.sin(2 * np.pi * t / 6.5) ** 2) * 0.16 * env([(0, 0), (21.6, 0), (23.0, 1), (D - 1.0, 1), (D, 0)])
breeze = nrm(bandnoise(150, 1200, seed=5)) * 0.07 * env([(0, 0), (21.6, 0), (23.0, 1), (D, 0.6)])
drone = (np.sin(2 * np.pi * 55 * t) * 0.5 + np.sin(2 * np.pi * 82.4 * t) * 0.3 + np.sin(2 * np.pi * 110 * t + 0.3 * np.sin(2 * np.pi * 0.2 * t)) * 0.2)
drone *= 0.13 * env([(0, 0.3), (5, 0.6), (11, 1), (21.8, 1), (24, 0.7), (36, 0.9), (D - 1.0, 0.6), (D, 0)])
fx = np.zeros(L)
def add(tm, x):
    a = int(tm * SR); n = min(L - a, len(x))
    if n > 0: fx[a:a + n] += x[:n]
TB5 = TM[n5]['T']
strikes = [11.05] + [T_B + (s - T_B) * (T_C - T_B) / (TB5 - T_B) for s in (14.0, 18.4, 21.7) if s < TB5] + [T_C + (41.0 - C_T0) * (T_D - T_C) / (C_T1 - C_T0)]
for i, s in enumerate(strikes):
    d0 = s + (0.15 + 0.4 * rng.random() if i else 0.0); n = int(5.0 * SR); tt = np.arange(n) / SR
    crack = bandnoise(1500, 9000, n, 100 + i) * np.exp(-tt / 0.08)
    rumble = bandnoise(25, 220, n, 200 + i) * np.exp(-tt / 1.6) * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * tt * (1.3 + rng.random()))))
    add(d0, nrm(crack) * 0.30 + nrm(rumble) * 0.85)
mixL = orbit + dive + rainL + wind + calm + breeze + drone + fx; mixR = orbit + dive + rainR + wind * 0.95 + calm * 0.97 + breeze + drone + fx * 0.97
fo = 1 - np.clip((t - (D - 1.0)) / 1.0, 0, 1); mixL *= fo; mixR *= fo
st = np.stack([mixL, mixR], 1); st = (st / (np.abs(st).max() + 1e-9) * 0.9 * 32767).astype(np.int16)
WAV = OUT + '.wav'
with wave.open(WAV, 'wb') as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', VID, '-i', WAV, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11',
                '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-dn', '-map_chapters', '-1', '-map_metadata', '-1', '-movflags', '+faststart', '-shortest', OUT], check=True)
os.remove(VID); os.remove(WAV); print('ok', OUT, N, 'frames')
