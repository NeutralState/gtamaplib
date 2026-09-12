"""raster_from_pieces.py — ecrit le raster 1 m/px (21000x20000 RGB PNG) depuis les pieces 2x par bandes (ecriture PNG en flux, ~80 Mo de RAM),
et regenere les crops yanis16_* de maps.json (memes zero / tailles) + zero de yanis16.
usage: raster_from_pieces.py <piecesdir> <out.png> <X0> <Y0> [--crops]
"""
import sys, os, json, zlib, struct
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pieces_lib import Pieces, PH, NROW
pdir, out, X0, Y0 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
W, H = 21000, 20000
P = Pieces(pdir, cache=2)
def chunk(f, typ, data):
    f.write(struct.pack('>I', len(data)) + typ + data + struct.pack('>I', zlib.crc32(typ + data) & 0xffffffff))
with open(out + '.tmp', 'wb') as f:
    f.write(b'\x89PNG\r\n\x1a\n')
    chunk(f, b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0))
    comp = zlib.compressobj(6)
    for r in range(NROW):
        band = P.region1x(0, r * PH, W, PH)          # 21000 x 1250
        raw = band.tobytes(); row = W * 3
        buf = b''.join(b'\x00' + raw[i * row:(i + 1) * row] for i in range(PH))
        data = comp.compress(buf)
        if data: chunk(f, b'IDAT', data)
        print('bande', r, flush=True)
    data = comp.flush()
    if data: chunk(f, b'IDAT', data)
    chunk(f, b'IEND', b'')
os.rename(out + '.tmp', out)
print('ecrit', out, os.path.getsize(out) // 1e6, 'Mo')
if '--crops' in sys.argv:
    M = json.load(open('gtamapdata/maps.json'))
    for k, v in M.items():
        if not k.startswith('yanis16_'): continue
        old = Image.open(v['filename']); w, h = old.size; zx, zy = v['zero']; old.close()
        px0 = X0 - zx; py0 = Y0 - zy
        P.region1x(px0, py0, w, h).save(v['filename'])
        print(k, 'crop raster', (px0, py0, w, h), '->', os.path.basename(v['filename']))
    M['yanis16']['zero'] = [X0, Y0]
    M['yanis16']['source'] = 'SVG rasterise 1 m/px 2026-09-12 (GTA VI Community Mapping Project-2.svg, canevas 21000x20000: x = px - 16991; rendu rsvg-convert en 32 pieces 2x puis reduction BOX)'
    json.dump(M, open('gtamapdata/maps.json', 'w'), indent=1, ensure_ascii=True)
    print('maps.json: yanis16 zero ->', [X0, Y0])
