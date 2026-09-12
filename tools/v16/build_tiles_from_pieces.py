"""build_tiles_from_pieces.py — regenere les tuiles z0..z6 de la pyramide calib yanis,16 depuis les pieces 2x, sans charger le raster complet (8 Go de RAM).
Plan z5 = 32768 px (1 m/px), raster colle a (OX, OY) = (16384 - X0, 16384 - Y0); z6 = plan 65536 (0.5 m/px), z<5 = plan 32768/2^(5-z).
Seules les tuiles deja presentes (memes noms z,y,x.jpg) sont reecrites.
usage: build_tiles_from_pieces.py <piecesdir> <X0> <Y0> <tilesdir> [zmin zmax]
"""
import sys, os, time
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pieces_lib import Pieces, OCEAN
pdir, X0, Y0, tdir = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
zmin, zmax = (int(sys.argv[5]), int(sys.argv[6])) if len(sys.argv) > 6 else (0, 6)
OX2 = 2 * (16384 - X0); OY2 = 2 * (16384 - Y0); Q = 88
P = Pieces(pdir, cache=4)
for z in range(zmax, zmin - 1, -1):
    zdir = os.path.join(tdir, str(z)); names = sorted(f for f in os.listdir(zdir) if f.endswith('.jpg'))
    tiles = sorted(((int(f[:-4].split(',')[1]), int(f[:-4].split(',')[2]), f) for f in names))
    F = 2 ** (6 - z)                        # px 2x par px de tuile
    t0 = time.time(); n = 0
    for ty, tx, f in tiles:
        rx0 = tx * 256 * F - OX2; ry0 = ty * 256 * F - OY2
        reg = P.region2x(rx0, ry0, 256 * F, 256 * F)
        tile = reg if F == 1 else reg.resize((256, 256), Image.BOX)
        tile.save(os.path.join(zdir, f), quality=Q, subsampling=0); n += 1
        if n % 4000 == 0: print(' z', z, n, '/', len(tiles), flush=True)
    print('z', z, 'tuiles', n, '%.0fs' % (time.time() - t0), flush=True)
