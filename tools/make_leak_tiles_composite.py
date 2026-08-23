# [LEAK-TILES-V3] pyramide composite depuis la clean map FIXED (nord/sud
# enfin peints — fixed_ps.psd d'Alexandre, meme georef que fullmap.png):
# leak par-dessus yanis, bords adoucis (feather 12 px). Sortie: leak,1.
import os
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
WX0, WY0, MPP = -10740.0, 9736.0, 5.65
SRC = os.path.expanduser('~/Downloads/fullmap_fixed.png')
BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'vendor', 'gtadb.org', 'maps', 'tiles', '6')
YAN = f'{BASE}/yanis,14'
OUT = f'{BASE}/leak,1'
FEATHER = 12.0
leak = Image.open(SRC).convert('RGB')
W, H = leak.size
for z in range(0, 6):
    mppx = 32.0 / (2 ** z)
    sc = MPP / mppx
    lw, lh = int(round(W * sc)), int(round(H * sc))
    lvl = leak.resize((lw, lh), Image.LANCZOS)
    ox = (16384 + WX0) / mppx
    oy = (16384 - WY0) / mppx
    tx0, tx1 = int(ox // 256), int((ox + lw) // 256)
    ty0, ty1 = int(oy // 256), int((oy + lh) // 256)
    os.makedirs(f'{OUT}/{z}', exist_ok=True)
    n = 0
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            px0, py0 = tx * 256 - ox, ty * 256 - oy
            sx0, sy0 = max(0, int(round(px0))), max(0, int(round(py0)))
            sx1, sy1 = min(lw, int(round(px0)) + 256), min(lh, int(round(py0)) + 256)
            if sx1 <= sx0 or sy1 <= sy0:
                continue
            ypath = f'{YAN}/{z}/{z},{ty},{tx}.jpg'
            tile = Image.open(ypath).convert('RGB') if os.path.exists(ypath) \
                else Image.new('RGB', (256, 256), (10, 10, 12))
            bg = np.asarray(tile).astype(np.float32)
            crop = np.asarray(lvl.crop((sx0, sy0, sx1, sy1))).astype(np.float32)
            gx = np.arange(sx0, sx1, dtype=np.float32)
            gy = np.arange(sy0, sy1, dtype=np.float32)
            ax = np.minimum(gx + 0.5, lw - 0.5 - gx) / FEATHER
            ay = np.minimum(gy + 0.5, lh - 0.5 - gy) / FEATHER
            alpha = np.clip(np.minimum(ax[None, :], ay[:, None]), 0.0, 1.0)[..., None]
            dx, dy = sx0 - int(round(px0)), sy0 - int(round(py0))
            hh, ww = crop.shape[:2]
            bg[dy:dy+hh, dx:dx+ww] = bg[dy:dy+hh, dx:dx+ww] * (1 - alpha) + crop * alpha
            Image.fromarray(bg.astype(np.uint8)).save(f'{OUT}/{z}/{z},{ty},{tx}.jpg', quality=88)
            n += 1
    print(f'z{z}: {n} tiles', flush=True)
print('done', flush=True)
