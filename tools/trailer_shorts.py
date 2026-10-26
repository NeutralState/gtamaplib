"""trailer_shorts.py [T4/10 ...|all] — one vertical Short (1080x1920, 60 fps) per launch-trailer shot, cut from the 3D tour video:
top panel = the real trailer frame (slow push-in), bottom panel = the 3D flight arriving on the spot, which then dissolves into the
same frame (the match is the payoff). Captions in short-form style (heavy white caps, black outline). No music: add a trending
sound in TikTok / YouTube. Shot times in the tour video = where each frame correlates best (tour_frames.json, made by --locate).
Output: tools/generated/t4/shorts/<id>_<name>.mp4"""
import sys, os, json, re, subprocess, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
TOUR = os.path.join(HERE, 'generated', 't4', 'video', 'gta6_launch_trailer_3d_tour.mp4')
OUT = os.path.join(HERE, 'generated', 't4', 'shorts'); os.makedirs(OUT, exist_ok=True)
TIMES = os.path.join(HERE, 'generated', 't4', 'shorts', 'tour_frames.json')
W, H, FPS = 1080, 1920, 60
PW, PH = 1080, 720                                    # each panel (3:2, centre crop of the 2:1 shot)
TOP_Y, BOT_Y = 250, 250 + PH + 24
PRE, POST = 4.0, 1.8                                   # seconds of 3D before the frame fades in / after
F = '/System/Library/Fonts/Avenir Next.ttc'
def font(sz): return ImageFont.truetype(F, sz, index=8)
def locate():
    C = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    shots = [(v['id'], k) for k, v in C.items() if str(v.get('id', '')).startswith('T4/')]
    refs = {}
    for i, k in shots:
        im = cv2.imread(os.path.join(REPO, 'frames', k + '.png'))
        if im is not None: g = cv2.cvtColor(cv2.resize(im, (96, 48)), cv2.COLOR_BGR2GRAY).astype(np.float32); refs[k] = (g - g.mean()) / (g.std() + 1e-6)
    names = list(refs); R = np.stack([refs[n] for n in names]); cap = cv2.VideoCapture(TOUR); S, T, i = [], [], 0
    while cap.grab():
        if i % 6 == 0:
            _, f = cap.retrieve(); g = cv2.cvtColor(cv2.resize(f[60:1020], (96, 48)), cv2.COLOR_BGR2GRAY).astype(np.float32)
            g = (g - g.mean()) / (g.std() + 1e-6); S.append((R * g).mean(axis=(1, 2))); T.append(i / 60)
        i += 1
    S = np.array(S); T = np.array(T); out = {}
    for j, n in enumerate(names):
        s = S[:, j]; k = int(np.argmax(s))
        if s[k] < 0.8: continue                         # not in the tour (added later)
        hi = s > 0.85 * s[k]; a = k
        while a > 0 and hi[a - 1]: a -= 1
        out[C[n]['id']] = dict(name=n, peak=float(T[k]), corr=float(s[k]), t0=float(T[a]))
    json.dump(out, open(TIMES, 'w'), indent=1); return out
def caption(text, size, y, stroke=10):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); lines = text.split('|'); lh = int(size * 1.1)
    for k, l in enumerate(lines):
        s = size
        while d.textlength(l, font=font(s)) > W - 90: s -= 4
        d.text((W // 2, y + k * lh), l, font=font(s), fill=(255, 255, 255, 255), anchor='mm', stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    a = im.split()[3]; sh = Image.new('RGBA', (W, H), (0, 0, 0, 255)); sh.putalpha(a.filter(ImageFilter.GaussianBlur(12)).point(lambda p: int(p * 0.5)))
    arr = np.array(Image.alpha_composite(sh, im)).astype(np.float32); return arr[:, :, [2, 1, 0]], arr[:, :, 3:] / 255.0
def tag(text):
    f = font(34); im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); tw = int(d.textlength(text, font=f))
    d.rounded_rectangle([0, 0, tw + 36, 58], radius=14, fill=(0, 0, 0, 170)); d.text((18, 29), text, font=f, fill=(255, 255, 255, 255), anchor='lm')
    arr = np.array(im.crop((0, 0, tw + 36, 58))).astype(np.float32); return arr[:, :, [2, 1, 0]], arr[:, :, 3:] / 255.0
def blend(dst, ov, x, y, al):
    if al <= 0.002: return
    rgb, a = ov; h, w = a.shape[:2]; a = a * al; sub = dst[y:y + h, x:x + w]; sub[:] = sub * (1 - a) + rgb * a
def panel(img, zoom=1.0):
    """2:1 (or 16:9) image -> 1080x720 centre crop, optional push-in"""
    h, w = img.shape[:2]; ch = h / zoom; cw = ch * PW / PH
    if cw > w: cw = w; ch = cw * PH / PW
    x0 = (w - cw) / 2; y0 = (h - ch) / 2
    return cv2.resize(img[int(y0):int(y0 + ch), int(x0):int(x0 + cw)], (PW, PH), interpolation=cv2.INTER_AREA).astype(np.float32)
def make(sid, info):
    name = info['name']; frame = cv2.imread(os.path.join(REPO, 'frames', name + '.png'))
    t_fade = info['t0']; t_start = t_fade - PRE; t_end = t_fade + POST; dur = t_end - t_start; N = int(round(dur * FPS))
    cap = cv2.VideoCapture(TOUR); cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t_start * FPS)))
    TITLE = caption(name.upper().replace(' AND ', ' & '), 84, 140) if len(name) < 26 else caption(re.sub(r'^(.{10,24}?) ', r'\1|', name.upper(), 1), 72, 100)
    SUB = caption('REBUILT IN 3D', 64, BOT_Y + PH + 90, 8)
    T_GAME, T_3D = tag('GTA 6 TRAILER'), tag('MY 3D MAP')
    END = caption('IT MATCHES', 118, BOT_Y - 12)                      # over the seam between the panels
    bg = np.full((H, W, 3), 14, np.float32)
    vid = os.path.join(OUT, '_v.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', vid], stdin=subprocess.PIPE)
    for n in range(N):
        ok, f = cap.read()
        if not ok: break
        t = n / FPS; img = bg.copy()
        img[TOP_Y:TOP_Y + PH] = panel(frame, 1.0 + 0.06 * t / dur)
        img[BOT_Y:BOT_Y + PH] = panel(f[60:860, 300:1500])  # tour video: shot band 60-1020; crop off its own caption box (bottom) and label (top right)
        blend(img, TITLE, 0, 0, min(1.0, t / 0.25))
        blend(img, T_GAME, 24, TOP_Y + 20, 1.0); blend(img, T_3D, 24, BOT_Y + 20, 1.0 - min(1.0, max(0.0, (t - PRE) / 0.6)))
        blend(img, SUB, 0, 0, min(1.0, t / 0.25))
        blend(img, END, 0, 0, min(1.0, max(0.0, (t - PRE - 0.5) / 0.25)))
        ff.stdin.write(np.clip(img, 0, 255).astype(np.uint8).tobytes())
    ff.stdin.close(); ff.wait()
    out = os.path.join(OUT, '%s_%s.mp4' % (sid.replace('/', '_'), re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_')))
    os.replace(vid, out); return out
if __name__ == '__main__':
    info = json.load(open(TIMES)) if os.path.exists(TIMES) and '--locate' not in sys.argv else locate()
    want = [a for a in sys.argv[1:] if a.startswith('T4/')] or (list(info) if 'all' in sys.argv else [])
    for sid in want: print(make(sid, info[sid]))


# ── v2 (viral edit, 2026-10-26): music with its drop on the reveal, own wipe + flash on the drop, hook text, loop length ──
BPM_BAR = 4 * 60.0 / 117.5                             # darksynth.py grid: drop after 2 bars, Short = 3 bars (loops on the beat)
def make_v2(sid, info, music, approach=3.3, out_name=None):
    name = info['name']; frame = cv2.imread(os.path.join(REPO, 'frames', name + '.png'))
    DROP = 2 * BPM_BAR; DUR = 3 * BPM_BAR; N = int(round(DUR * FPS))
    t_fade = info['t0'] - 0.5; src0 = t_fade - approach              # stop before the tour's own dissolve starts
    cap = cv2.VideoCapture(TOUR); cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(src0 * FPS)))
    src = []
    for k in range(int(approach * FPS) + 2):
        ok, f = cap.read()
        if not ok: break
        src.append(panel(f[60:860, 300:1500]))
    src = src[:int(approach * FPS)]
    HOOK = caption('GTA 6 TRAILER|vs MY 3D MAP', 88, 78)
    WAIT = caption('WAIT FOR IT...', 96, BOT_Y - 12)
    MATCH = caption('IT MATCHES', 128, BOT_Y - 12)
    PLACE = caption(name.upper().replace(' AND ', ' & '), 58, BOT_Y + PH + 92, 8)
    T_GAME, T_3D = tag('GTA 6 TRAILER'), tag('MY 3D MAP')
    bg = np.full((H, W, 3), 14, np.float32)
    vid = os.path.join(OUT, '_v.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', vid], stdin=subprocess.PIPE)
    for n in range(N):
        t = n / FPS; img = bg.copy(); z = 1.0 + 0.05 * t / DUR
        real = panel(frame, z); img[TOP_Y:TOP_Y + PH] = real
        three = src[min(len(src) - 1, int(t / DROP * (len(src) - 1)))] if t < DROP else src[-1]
        w = min(1.0, max(0.0, (t - DROP) / 0.18))                       # wipe on the drop, left -> right
        bot = three.copy(); xw = int(PW * w); bot[:, :xw] = real[:, :xw]
        if 0 < xw < PW: bot[:, max(0, xw - 4):xw + 4] = 255
        img[BOT_Y:BOT_Y + PH] = bot
        fl = max(0.0, 1 - (t - DROP) / 0.22) if t >= DROP else 0.0       # white flash on the drop
        if fl > 0: img = img * (1 - 0.55 * fl) + 255 * 0.55 * fl
        if t >= DROP:                                                  # zoom punch
            k = max(0.0, 1 - (t - DROP) / 0.3); s = 1 + 0.05 * k
            if s > 1.001:
                big = cv2.resize(img, (int(W * s), int(H * s))); x0 = (big.shape[1] - W) // 2; y0 = (big.shape[0] - H) // 2; img = big[y0:y0 + H, x0:x0 + W]
        blend(img, HOOK, 0, 0, 1.0); blend(img, PLACE, 0, 0, 1.0)
        blend(img, T_GAME, 24, TOP_Y + 20, 1.0); blend(img, T_3D, 24, BOT_Y + 20, 1.0 if t < DROP else 0.0)
        if t < DROP: blend(img, WAIT, 0, 0, 0.55 + 0.45 * abs(np.sin(np.pi * t / (BPM_BAR / 4))))   # pulses on the beat
        else: blend(img, MATCH, 0, 0, 1.0)
        ff.stdin.write(np.clip(img, 0, 255).astype(np.uint8).tobytes())
    ff.stdin.close(); ff.wait()
    out = os.path.join(OUT, out_name or ('v2_%s_%s.mp4' % (sid.replace('/', '_'), re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_'))))
    fade = 0.08
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', vid, '-i', music, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-t', '%.3f' % DUR,
                    '-af', 'afade=t=in:d=0.03,afade=t=out:st=%.3f:d=%.2f,loudnorm=I=-14:TP=-1.5' % (DUR - fade, fade), '-c:a', 'aac', '-b:a', '256k',
                    '-dn', '-map_metadata', '-1', '-movflags', '+faststart', out], check=True)
    os.remove(vid); return out
