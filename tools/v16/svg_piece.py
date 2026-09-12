"""svg_piece.py — rend une piece de la V16 SVG a 2 px/unite (pour les tuiles z6).
Cairo refuse > 32767 px de cote: on ecrit une copie du SVG dont le root viewBox est restreint a la piece,
puis rsvg-convert -w -h. Canevas 21000x20000 -> 2 colonnes (10500) x 16 bandes (1250) rendues en 21000x2500.
usage: svg_piece.py <svg> <col 0|1> <row 0..15> <outdir>
"""
import sys, os, re, subprocess
svg, col, row, outdir = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
W, H = 21000, 20000; PW, PH = W // 2, H // 16; SCALE = 2
x0, y0 = col * PW, row * PH
out = os.path.join(outdir, f'c{col}_r{row:02d}.png')
if os.path.exists(out) and os.path.getsize(out) > 0:
    print('existe', out); sys.exit(0)
data = open(svg, 'rb').read()
head_end = data.index(b'>') + 1
head = data[:head_end].decode()
head2 = re.sub(r'\bwidth="[^"]*"', f'width="{PW}"', head, count=1)
head2 = re.sub(r'\bheight="[^"]*"', f'height="{PH}"', head2, count=1)
head2 = re.sub(r'\bviewBox="[^"]*"', f'viewBox="{x0} {y0} {PW} {PH}"', head2, count=1)
assert head2 != head
tmp = os.path.join(outdir, f'piece_c{col}_r{row:02d}.svg')
with open(tmp, 'wb') as f:
    f.write(head2.encode()); f.write(data[head_end:])
try:
    subprocess.check_call(['rsvg-convert', '--unlimited', '-w', str(PW * SCALE), '-h', str(PH * SCALE), '-o', out + '.tmp.png', tmp])
    os.rename(out + '.tmp.png', out)
    print('ok', out)
finally:
    os.remove(tmp)
