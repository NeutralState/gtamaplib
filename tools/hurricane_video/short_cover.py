"""short_cover.py — 1080x1920 cover of the hurricane Short: the storm from orbit on top, Leonida flooded in 3D below, the question
across the seam in the Short's caption style (heavy white caps, black outline)."""
import os, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from common import WORK, TOOLS
W, H = 1080, 1920
top = cv2.imread(os.path.join(WORK, 'space_v', '000428.jpg')).astype(np.float32)
isl = cv2.imread(os.path.join(WORK, 'rec_v', 'frames', '500600.jpg')).astype(np.float32)
SEAM = 960
a = top[560:560 + SEAM + 120]                                   # spiral, eye and the island
b = isl[560:]; b = cv2.resize(b, (W, int(b.shape[0] * W / b.shape[1])))[: H - SEAM + 120]
out = np.zeros((H, W, 3), np.float32); out[:SEAM + 120] = a; lo = out[SEAM - 120:].copy(); lo[:] = b[:H - SEAM + 120]
m = np.clip((np.arange(H - SEAM + 120) - 0) / 240.0, 0, 1)[:, None, None]
out[SEAM - 120:] = out[SEAM - 120:] * (1 - m) + lo * m                                    # soft seam
y = np.arange(H, dtype=np.float32)[:, None, None]; band = np.exp(-((y - SEAM) / 260.0) ** 2)
out *= 1 - 0.45 * band                                                                       # darker behind the text
F = '/System/Library/Fonts/Avenir Next.ttc'
im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
def line(txt, y, size):
    while d.textlength(txt, font=ImageFont.truetype(F, size, index=8)) > W - 90: size -= 4
    d.text((W // 2, y), txt, font=ImageFont.truetype(F, size, index=8), fill=(255, 255, 255, 255), anchor='mm', stroke_width=13, stroke_fill=(0, 0, 0, 255))
line('WHAT IF', SEAM - 210, 150); line('A HURRICANE', SEAM - 40, 150); line('HIT GTA 6?', SEAM + 130, 160)
al = im.split()[3]; sh = Image.new('RGBA', (W, H), (0, 0, 0, 255)); sh.putalpha(al.filter(ImageFilter.GaussianBlur(18)).point(lambda p: int(p * 0.55)))
lay = np.array(Image.alpha_composite(sh, im)).astype(np.float32); rgb, A = lay[:, :, [2, 1, 0]], lay[:, :, 3:] / 255.0
out = out * (1 - A) + rgb * A
p = os.path.join(TOOLS, 'generated', 'hurricane', 'video', 'short_cover_hurricane.jpg')
cv2.imwrite(p, np.clip(out, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 93]); print(p)
