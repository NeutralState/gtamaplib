"""screenshot_short.py [--cover] — the v2 Short format (trailer_shorts.make_v2: real image on top, the 3D arriving below, wipe + flash
on the drop, IT MATCHES, darksynth, 3 bars = loops on the beat) for a SCREENSHOT whose 3D approach was rendered on its own
(frames ~/gta6_hurricane_work/peaks/frames/<first>..), instead of a cut of the trailer tour video.
S4/24 Ferris Wheel [Edge] (2026-10-29): approach 570000..570249 (dolly-in from 320 m NE / 125 m up to the estimated pose, the
camera's own look from tour_styles.json), music darksynth DS_TRANSPOSE=3 DS_SEED=24.
Output: tools/generated/t4/shorts/v2_S4_24_Ferris_Wheel_Edge.mp4 (+ cover_S4_24.jpg with --cover)"""
import sys, os, subprocess, numpy as np, cv2
from trailer_shorts import caption, tag, blend, panel, font, W, H, FPS, BPM_BAR, PW, PH, TOP_Y, BOT_Y, OUT
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
FR = os.path.expanduser('~/gta6_hurricane_work/peaks/frames')
SHOT = dict(sid='S4_24', img=os.path.join(REPO, 'frames', 'Ferris Wheel [Edge].png'), first=570000, n=250, place='SHORELINE, VICE CITY',
            hook='NEW GTA 6 SCREENSHOT|vs MY 3D MAP', tag_real='NEW SCREENSHOT', name='Ferris_Wheel_Edge')
def make(S, music):
    real0 = cv2.imread(S['img']); DROP = 2 * BPM_BAR; DUR = 3 * BPM_BAR; N = int(round(DUR * FPS))
    src = [panel(cv2.imread(os.path.join(FR, '%06d.jpg' % (S['first'] + k)))) for k in range(S['n'])]
    HOOK = caption(S['hook'], 88, 78); WAIT = caption('WAIT FOR IT...', 96, BOT_Y - 12); MATCH = caption('IT MATCHES', 128, BOT_Y - 12)
    PLACE = caption(S['place'], 58, BOT_Y + PH + 92, 8); T_REAL, T_3D = tag(S['tag_real']), tag('MY 3D MAP')
    bg = np.full((H, W, 3), 14, np.float32); vid = os.path.join(OUT, '_v.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', vid], stdin=subprocess.PIPE)
    for n in range(N):
        t = n / FPS; img = bg.copy(); real = panel(real0, 1.0 + 0.05 * t / DUR); img[TOP_Y:TOP_Y + PH] = real
        three = src[min(len(src) - 1, int(t / DROP * (len(src) - 1)))] if t < DROP else src[-1]
        w = min(1.0, max(0.0, (t - DROP) / 0.18)); bot = three.copy(); xw = int(PW * w); bot[:, :xw] = real[:, :xw]
        if 0 < xw < PW: bot[:, max(0, xw - 4):xw + 4] = 255
        img[BOT_Y:BOT_Y + PH] = bot
        fl = max(0.0, 1 - (t - DROP) / 0.22) if t >= DROP else 0.0
        if fl > 0: img = img * (1 - 0.55 * fl) + 255 * 0.55 * fl
        if t >= DROP:
            k = max(0.0, 1 - (t - DROP) / 0.3); s = 1 + 0.05 * k
            if s > 1.001:
                big = cv2.resize(img, (int(W * s), int(H * s))); x0 = (big.shape[1] - W) // 2; y0 = (big.shape[0] - H) // 2; img = big[y0:y0 + H, x0:x0 + W]
        blend(img, HOOK, 0, 0, 1.0); blend(img, PLACE, 0, 0, 1.0)
        blend(img, T_REAL, 24, TOP_Y + 20, 1.0); blend(img, T_3D, 24, BOT_Y + 20, 1.0 if t < DROP else 0.0)
        if t < DROP: blend(img, WAIT, 0, 0, 0.55 + 0.45 * abs(np.sin(np.pi * t / (BPM_BAR / 4))))
        else: blend(img, MATCH, 0, 0, 1.0)
        ff.stdin.write(np.clip(img, 0, 255).astype(np.uint8).tobytes())
    ff.stdin.close(); ff.wait()
    out = os.path.join(OUT, 'v2_%s_%s.mp4' % (S['sid'], S['name']))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', vid, '-i', music, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-t', '%.3f' % DUR,
                    '-af', 'afade=t=in:d=0.03,afade=t=out:st=%.3f:d=0.08,loudnorm=I=-14:TP=-1.5' % (DUR - 0.08), '-c:a', 'aac', '-b:a', '256k',
                    '-dn', '-map_metadata', '-1', '-movflags', '+faststart', out], check=True)
    os.remove(vid); return out
def make_cover(S):
    """1080x1920: the screenshot on top, the 3D at the pose below, hook on the seam (trailer_shorts.make_cover layout)"""
    HH = H // 2; real = cv2.imread(S['img']); f3 = cv2.imread(os.path.join(FR, '%06d.jpg' % (S['first'] + S['n'] - 1)))
    def crop(img):
        h, w = img.shape[:2]; cw = min(w, h * W / HH); ch = cw * HH / W; x0 = (w - cw) / 2; y0 = (h - ch) / 2
        return cv2.resize(img[int(y0):int(y0 + ch), int(x0):int(x0 + cw)], (W, HH), interpolation=cv2.INTER_AREA).astype(np.float32)
    img = np.zeros((H, W, 3), np.float32); img[:HH] = crop(real); img[HH:] = crop(f3); img[HH - 3:HH + 3] = 255
    blend(img, caption('NEW GTA 6 SCREENSHOT', 104, HH - 150, 14), 0, 0, 1.0)
    blend(img, caption('vs', 104, HH + 8, 12), 0, 0, 1.0)
    blend(img, caption('MY 3D MAP', 138, HH + 150, 14), 0, 0, 1.0)
    for txt, y in (('GAME', 60), ('3D', H - 120)):
        f = font(52); im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); tw = int(d.textlength(txt, font=f))
        d.rounded_rectangle([0, 0, tw + 48, 80], radius=18, fill=(20, 12, 30, 200)); d.text((24, 40), txt, font=f, fill=(255, 255, 255, 255), anchor='lm')
        arr = np.array(im.crop((0, 0, tw + 48, 80))).astype(np.float32); blend(img, (arr[:, :, [2, 1, 0]], arr[:, :, 3:] / 255.0), 36, y, 1.0)
    out = os.path.join(OUT, 'cover_%s.jpg' % S['sid']); cv2.imwrite(out, np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 93]); return out
if __name__ == '__main__':
    if '--cover' in sys.argv: print(make_cover(SHOT))
    else: print(make(SHOT, sys.argv[1]))
