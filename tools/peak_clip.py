"""peak_clip.py <frames_dir> <first_n> <count> <rank> <name> <elevation_m> <out.mp4> [music.wav] — one ranked-summit clip for the
mountains video: the view3d flyover frames + "#rank" and the summit name in short-form caption style, the elevation counting up.
1920x1080, 60 fps."""
import sys, os, subprocess, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
D, N0, CNT, RANK, NAME, ELEV, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5], float(sys.argv[6]), sys.argv[7]
MUS = sys.argv[8] if len(sys.argv) > 8 else None
W, H, FPS = 1920, 1080, 60
F = '/System/Library/Fonts/Avenir Next.ttc'
def layer(draw):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); draw(ImageDraw.Draw(im)); a = im.split()[3]
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 255)); sh.putalpha(a.filter(ImageFilter.GaussianBlur(14)).point(lambda p: int(p * 0.5)))
    arr = np.array(Image.alpha_composite(sh, im)).astype(np.float32); return arr[:, :, [2, 1, 0]], arr[:, :, 3:] / 255.0
def txt(d, s, xy, size, anchor='lm', stroke=9):
    d.text(xy, s, font=ImageFont.truetype(F, size, index=8), fill=(255, 255, 255, 255), anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
TITLE = layer(lambda d: (txt(d, '#' + RANK, (90, 150), 170), txt(d, NAME.upper(), (90, 290), 92, stroke=8)))
cache = {}
def elev(v):
    k = int(v)
    if k not in cache: cache.clear(); cache[k] = layer(lambda d: txt(d, '%d m' % k, (W - 90, H - 110), 120, 'rm'))
    return cache[k]
def blend(dst, ov, al):
    if al <= 0.002: return
    rgb, a = ov; a = a * al; dst[:] = dst * (1 - a) + rgb * a
def ease(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
vid = OUT + '.v.mp4'
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                       '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', vid], stdin=subprocess.PIPE)
for i in range(CNT):
    t = i / FPS; fr = cv2.imread(os.path.join(D, '%06d.jpg' % (N0 + i))); fr = cv2.resize(fr, (W, H)).astype(np.float32)
    al = ease((t - 0.4) / 0.4); blend(fr, TITLE, al)
    blend(fr, elev(ELEV * ease((t - 0.8) / 3.0)), ease((t - 0.8) / 0.3))
    fr *= ease(t / 0.4)
    ff.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
ff.stdin.close(); ff.wait()
if MUS:
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', vid, '-i', MUS, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-shortest',
                    '-af', 'afade=t=out:st=%.2f:d=0.8,loudnorm=I=-14:TP=-1.5' % (CNT / FPS - 0.8), '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', OUT], check=True)
    os.remove(vid)
else: os.replace(vid, OUT)
print(OUT)
