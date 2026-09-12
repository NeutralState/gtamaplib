"""pieces_lib.py — acces memoire-leger a la V16 rendue en pieces 2x (c{col}_r{row:02d}.png, 21000x2500 px = 10500x1250 unites SVG).
region2x(x0,y0,w,h): image RGB de la zone [x0,x0+w)x[y0,y0+h) du raster 2x (42000x40000), fond OCEAN hors canevas.
region1x(...): idem en coordonnees 1x (unites SVG = m), reduction BOX 2:1 exacte (grille alignee).
"""
import os
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
PW, PH, NCOL, NROW = 21000, 2500, 2, 16
RW2, RH2 = PW * NCOL, PH * NROW
OCEAN = (44, 104, 164)
class Pieces:
    def __init__(self, pdir, cache=4):
        self.pdir = pdir; self.cache = {}; self.ncache = cache
    def piece(self, c, r):
        k = (c, r)
        if k not in self.cache:
            while len(self.cache) >= self.ncache:
                del self.cache[next(iter(self.cache))]
            self.cache[k] = Image.open(os.path.join(self.pdir, f'c{c}_r{r:02d}.png')).convert('RGB')
        return self.cache[k]
    def region2x(self, x0, y0, w, h):
        im = Image.new('RGB', (w, h), OCEAN); x1 = x0 + w; y1 = y0 + h
        if x1 <= 0 or y1 <= 0 or x0 >= RW2 or y0 >= RH2: return im
        for c in range(max(0, x0 // PW), min(NCOL - 1, (x1 - 1) // PW) + 1):
            for r in range(max(0, y0 // PH), min(NROW - 1, (y1 - 1) // PH) + 1):
                bx0 = max(x0, c * PW); by0 = max(y0, r * PH); bx1 = min(x1, (c + 1) * PW); by1 = min(y1, (r + 1) * PH)
                if bx1 > bx0 and by1 > by0:
                    p = self.piece(c, r)
                    im.paste(p.crop((bx0 - c * PW, by0 - r * PH, bx1 - c * PW, by1 - r * PH)), (bx0 - x0, by0 - y0))
        return im
    def region1x(self, x0, y0, w, h):
        return self.region2x(2 * x0, 2 * y0, 2 * w, 2 * h).resize((w, h), Image.BOX)
