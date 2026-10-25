"""compose_short.py [out.mp4] — vertical Short « A hurricane hits GTA 6 » (1080x1920, 60 fps, ~22.5 s), cut on the bars of the track
(short_plan.py): orbit + dive -> Downtown floods (top-down) -> Brickell at street level -> all of Leonida in 3D -> question.
Captions in short-form style: 1-3 words, heavy white caps with a black outline, popping in on the beat; zoom punch on the cuts."""
import sys, os, json, glob, subprocess, wave, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
os.environ['HV_VERTICAL'] = '1'
from common import TOOLS, WORK, W, H, FPS, ease
import short_plan as SP
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(TOOLS, 'generated', 'hurricane', 'video', 'gta6_hurricane_short.mp4')
SPACE, TOP, REC = os.path.join(WORK, 'space_v'), os.path.join(WORK, 'top_v'), os.path.join(WORK, 'rec_v')
HEAVY = ImageFont.truetype('/System/Library/Fonts/Avenir Next.ttc', 128, index=8)
HEAVY_S = ImageFont.truetype('/System/Library/Fonts/Avenir Next.ttc', 92, index=8)
B = SP.BEAT; BAR = SP.BAR
CAPS = [(0.10, BAR, 'A HURRICANE'), (BAR, 2 * BAR - 0.12, 'HITS GTA 6'),
        (2 * BAR + 0.08, 2 * BAR + 2 * B, 'DOWNTOWN'), (2 * BAR + 2 * B, 3 * BAR, 'VICE CITY'), (3 * BAR, 4 * BAR, 'UNDERWATER'),
        (4 * BAR + 0.08, 5 * BAR, 'KATRINA-LEVEL'), (5 * BAR, 6 * BAR, 'STORM SURGE'),
        (6 * BAR + 0.08, 7 * BAR, 'THE WHOLE MAP'), (8 * BAR, 8.8 * BAR, 'VICE CITY: GONE'), (8.8 * BAR, 10 * BAR, '54% UNDERWATER'),
        (10 * BAR, 11 * BAR, 'WHERE WOULD|YOU HIDE?')]
CY = int(H * 0.30)
def cap_layer(text, font=HEAVY, stroke=11):
    lines = text.split('|'); im = Image.new('RGBA', (W, 520), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lh = int(font.size * 1.12); y0 = 260 - lh * (len(lines) - 1) // 2
    for i, l in enumerate(lines):
        size = font.size
        while d.textlength(l, font=ImageFont.truetype(font.path, size, index=font.index)) > W - 110: size -= 4
        f = ImageFont.truetype(font.path, size, index=font.index)
        d.text((W // 2, y0 + i * lh), l, font=f, fill=(255, 255, 255, 255), anchor='mm', stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    a = im.split()[3]; sh = Image.new('RGBA', im.size, (0, 0, 0, 255)); sh.putalpha(a.filter(ImageFilter.GaussianBlur(14)).point(lambda p: int(p * 0.5)))
    out = Image.alpha_composite(sh, im); arr = np.array(out).astype(np.float32); return arr[:, :, [2, 1, 0]], arr[:, :, 3:] / 255.0
CL = [(a, b, cap_layer(t)) for a, b, t in CAPS]
LV = {}
def lv_layer(v):
    k = round(v, 1)
    if k not in LV: LV.clear(); LV[k] = cap_layer('+%.1f m' % k, HEAVY_S, 9)
    return LV[k]
def put(dst, ov, cy, alpha, scale=1.0):
    if alpha <= 0.002: return
    rgb, a = ov
    if abs(scale - 1) > 1e-3:
        hh, ww = a.shape[:2]; nw, nh = int(ww * scale), int(hh * scale)
        rgb = cv2.resize(rgb, (nw, nh)); a = cv2.resize(a, (nw, nh))[..., None]
        x0 = (nw - W) // 2; rgb = rgb[:, x0:x0 + W] if nw >= W else np.pad(rgb, ((0, 0), ((W - nw) // 2, W - nw - (W - nw) // 2), (0, 0)))
        a = a[:, x0:x0 + W] if nw >= W else np.pad(a, ((0, 0), ((W - nw) // 2, W - nw - (W - nw) // 2), (0, 0)))
    hh = a.shape[0]; y0 = cy - hh // 2; ys, ye = max(0, y0), min(H, y0 + hh)
    a = a[ys - y0:ye - y0] * alpha; rgb = rgb[ys - y0:ye - y0]
    sub = dst[ys:ye]; sub[:] = sub * (1 - a) + rgb * a
def pop(T, a, b):
    """alpha, scale of a caption shown on [a, b): snaps in (scale 1.22 -> 1.0 in 0.12 s), quick fade out"""
    if T < a or T >= b: return 0.0, 1.0
    k = ease((T - a) / 0.12); out = 1 - ease((T - (b - 0.08)) / 0.08)
    return k * out, 1.22 - 0.22 * k
# frame sources
nb5 = SP.n5(); TM = {}
for p in glob.glob(os.path.join(WORK, 'top', 'meta_B*.json')):
    for m in json.load(open(p)): TM[m['n']] = m
RM = {}
for l in open(os.path.join(REC, 'meta.jsonl')):
    m = json.loads(l); RM[int(m['n'])] = m
ISL = sorted(k for k in RM if k >= 500000)
def src(T):
    if T < SP.S_SPACE[1]: n = min(SP.space_frame(T), 659); return os.path.join(SPACE, '%06d.jpg' % n), None
    if T < SP.S_TOP[1]: n = SP.top_frame(T, nb5); return os.path.join(TOP, '%06d.jpg' % n), TM[n]['level']
    if T < SP.S_3D[1]:
        n = int(round(SP.c3d_time(T) * FPS)) + 300000; n = min(n, max(k for k in RM if k < 400000)); return os.path.join(REC, 'frames', '%06d.jpg' % n), float(RM[n]['surge'])
    i = int(round(SP.isl_time(T) * FPS)); n = min(ISL, key=lambda k: abs(k - 500000 - i)); return os.path.join(REC, 'frames', '%06d.jpg' % n), float(RM[n]['level'])
def punch(fr, k):
    """zoom punch: k = 1 at the cut -> scale 1.07, easing back to 1"""
    if k <= 0.002: return fr
    s = 1 + 0.07 * k; big = cv2.resize(fr, (int(W * s), int(H * s))); x0 = (big.shape[1] - W) // 2; y0 = (big.shape[0] - H) // 2
    return big[y0:y0 + H, x0:x0 + W]
CUTS = [SP.S_TOP[0], SP.S_3D[0], SP.S_ISL[0]]
N = int(round(SP.T_END * FPS)); VID = OUT + '.video.mp4'
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                       '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', str(FPS), VID], stdin=subprocess.PIPE)
for n in range(N):
    T = n / FPS; p, lv = src(T); fr = cv2.imread(p); assert fr is not None, p
    if fr.shape[:2] != (H, W): fr = cv2.resize(fr, (W, H))
    fr = fr.astype(np.float32)
    k = max([1 - ease((T - c) / 0.35) for c in CUTS if T >= c] + [0.0]); fr = punch(fr, k)
    if SP.S_TOP[0] <= T < SP.S_TOP[0] + 0.25: fr = fr * ease((T - SP.S_TOP[0]) / 0.25) + 238 * (1 - ease((T - SP.S_TOP[0]) / 0.25))   # out of the clouds on the drop
    if SP.S_3D[0] <= T < SP.S_3D[0] + 0.18: fr = fr + 140 * (1 - (T - SP.S_3D[0]) / 0.18)                                     # lightning on the cut
    for a, b, ov in CL:
        al, sc = pop(T, a, b); put(fr, ov, CY, al, sc)
    if lv is not None and SP.S_TOP[0] + 0.2 <= T < 10 * BAR and (T < SP.S_ISL[0] or lv >= 8.0): put(fr, lv_layer(lv), CY + 190, 1.0)   # no counter reset on the island shot
    ff.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
ff.stdin.close(); ff.wait()
# ── sound: the track from 8 beats before its drop, + dive whoosh and thunder on the Brickell cut ──
SR = 48000; D = N / FPS; L = int(D * SR); t = np.arange(L) / SR
mus = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % SP.M0, '-t', '%.3f' % (D + 0.1), '-i', SP.MUSIC, '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
                                   capture_output=True).stdout, np.float32).reshape(-1, 2)[:L]
mus = np.pad(mus, ((0, L - len(mus)), (0, 0)))
def bandnoise(lo, hi, n, seed):
    x = np.random.default_rng(seed).standard_normal(n); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    X *= ((f >= lo) & (f <= hi)) / np.sqrt(np.maximum(f, 20) / 400); return np.fft.irfft(X, n)
def nrm(x): return x / (np.abs(x).max() + 1e-9)
fx = np.zeros(L)
a0, a1 = int(2.6 * SR), int(SP.S_TOP[0] * SR); tt = np.linspace(0, 1, a1 - a0)            # whoosh into the drop
fx[a0:a1] += nrm(bandnoise(300, 6000, a1 - a0, 8)) * tt ** 2 * 0.35
a = int(SP.S_3D[0] * SR); n = min(L - a, int(4 * SR)); tt = np.arange(n) / SR                  # thunder on the Brickell cut
fx[a:a + n] += nrm(bandnoise(1500, 9000, n, 100)) * np.exp(-tt / 0.07) * 0.30 + nrm(bandnoise(25, 220, n, 200)) * np.exp(-tt / 1.4) * 0.55
mix = mus * 0.85 + fx[:, None]
mix[:int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))[:, None]; e = int(0.25 * SR); mix[-e:] *= np.linspace(1, 0, e)[:, None]
st = (mix / (np.abs(mix).max() + 1e-9) * 0.95 * 32767).astype(np.int16)
WAV = OUT + '.wav'
with wave.open(WAV, 'wb') as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', VID, '-i', WAV, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11',
                '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-dn', '-map_chapters', '-1', '-map_metadata', '-1', '-movflags', '+faststart', '-shortest', OUT], check=True)
os.remove(VID); os.remove(WAV); print('ok', OUT, N, 'frames')
