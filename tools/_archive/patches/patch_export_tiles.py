#!/usr/bin/env python3
# EXPORT-TILES-V13 (2026-07-10): l'export map-validation compositait encore le
# vieux ml.get_map('yanis') = JPG V12 monolithique, alors que tout le reste
# (minimap, map view, MAP-EVIDENCE) est passe aux tiles yanis,13 (V13).
# Fix: helper _render_tiles_region (meme math que _render_minimap_for_cam:
# MAP_W=32768, ZERO=16384, m/px=32/2^z, zoom choisi pour >= out_px source) +
# swap du bloc V12 (clamps inclus — les tiles gerent le hors-carte par fond).
# Le mapping aval w2c est purement monde->pixels: markers/cone/labels intacts.
# Smoke-test sandbox: HTTP 200, PNG 1500x1500. Idempotent.
import sys
p = 'tools/server.py'
src = open(p).read()
if 'EXPORT-TILES-V13' in src:
    print('ok  deja patche'); sys.exit(0)
HELPER = '''
def _render_tiles_region(cx, cy, half_m, out_px=1500):
    # [EXPORT-TILES-V13, 2026-07-10] Rend une region monde carree (centre
    # cx,cy, demi-cote half_m) en compositant les tiles yanis,13 (V13) —
    # meme math que _render_minimap_for_cam (MAP_W=32768, ZERO=16384,
    # m/px = 32/2^z). Remplace le crop ml.get_map('yanis') (V12 monolithique)
    # dans l'export. Tiles manquants/hors-carte = fond sombre, pas d'erreur.
    TS = 256
    ZX = ZY = 16384
    TILE_RANGES = {
        0: [[0, 0], [2, 2]],
        1: [[0, 1], [4, 5]],
        2: [[0, 2], [9, 11]],
        3: [[0, 4], [19, 23]],
        4: [[0, 8], [38, 47]],
        5: [[0, 17], [77, 95]],
        6: [[0, 34], [155, 190]],
    }
    z = 0
    while z < 6 and (2.0 * half_m) / (32.0 / (2 ** z)) < out_px:
        z += 1
    mppx = 32.0 / (2 ** z)
    from PIL import Image
    cpx = (ZX + cx) / mppx
    cpy = (ZY - cy) / mppx
    hw = half_m / mppx
    left, top = cpx - hw, cpy - hw
    tx_min = int(left // TS)
    tx_max = int((cpx + hw - 1) // TS)
    ty_min = int(top // TS)
    ty_max = int((cpy + hw - 1) // TS)
    [[bx0, by0], [bx1, by1]] = TILE_RANGES[z]
    comp = Image.new('RGB', ((tx_max - tx_min + 1) * TS, (ty_max - ty_min + 1) * TS), (10, 10, 12))
    for ty in range(ty_min, ty_max + 1):
        for tx in range(tx_min, tx_max + 1):
            if tx < bx0 or tx > bx1 or ty < by0 or ty > by1:
                continue
            tp = os.path.join(TILES_DIR, str(z), f'{z},{ty},{tx}.jpg')
            if not os.path.exists(tp):
                continue
            try:
                t = Image.open(tp).convert('RGB')
            except Exception:
                continue
            comp.paste(t, ((tx - tx_min) * TS, (ty - ty_min) * TS))
    cx0 = int(round(left - tx_min * TS))
    cy0 = int(round(top - ty_min * TS))
    side = int(round(2 * hw))
    crop = comp.crop((cx0, cy0, cx0 + side, cy0 + side))
    return crop.resize((out_px, out_px), Image.BILINEAR)

'''
anchor = "def _render_minimap_for_cam(cam_name):"
assert anchor in src, 'ancre helper introuvable'
src = src.replace(anchor, HELPER + anchor, 1)
old = """            R=maxd*1.15
            try:
                mp=ml.get_map('yanis'); mp.open(add_padding=False)
                MAP_PX=mp.size[0] if hasattr(mp,'size') else 20000
            except Exception as e:
                self.send_json({'error':f'map open failed: {e}'},500); return
            p_test = mp.get_map_xy((0.0,0.0)); Xoff=p_test[0]; Yoff=p_test[1]
            WX_MIN=0-Xoff; WX_MAX=MAP_PX-Xoff; WY_MAX=Yoff-0; WY_MIN=Yoff-MAP_PX
            half=R; ctrx,ctry=cx,cy
            if ctrx-half<WX_MIN: ctrx=WX_MIN+half
            if ctrx+half>WX_MAX: ctrx=WX_MAX-half
            if ctry-half<WY_MIN: ctry=WY_MIN+half
            if ctry+half>WY_MAX: ctry=WY_MAX-half
            x0w,y0w,x1w,y1w=ctrx-half,ctry-half,ctrx+half,ctry+half
            try:
                px0,py_a=mp.get_map_xy((x0w,y0w)); px1,py_b=mp.get_map_xy((x1w,y1w))
                px0,px1=sorted((px0,px1)); py0,py1=sorted((py_a,py_b))
                vx0,vy0=max(0,int(px0)),max(0,int(py0))
                vx1,vy1=min(MAP_PX,int(px1)),min(MAP_PX,int(py1))
                req_w=int(px1-px0); req_h=int(py1-py0)
                canvas=Image.new('RGB',(req_w,req_h),INK_BG)
                if vx1>vx0 and vy1>vy0:
                    piece=mp.image.crop((vx0,vy0,vx1,vy1))
                    canvas.paste(piece,(vx0-int(px0),vy0-int(py0)))
            except Exception as e:
                self.send_json({'error':f'map crop failed: {e}'},500); return
            OUT=1500
            crop=canvas.resize((OUT,OUT),Image.BILINEAR).convert('RGBA')"""
new = """            R=maxd*1.15
            # [EXPORT-TILES-V13] crop depuis les tiles V13 (plus de get_map V12)
            x0w,y0w,x1w,y1w=cx-R,cy-R,cx+R,cy+R
            OUT=1500
            try:
                crop=_render_tiles_region(cx,cy,R,OUT).convert('RGBA')
            except Exception as e:
                self.send_json({'error':f'tiles crop failed: {e}'},500); return"""
assert old in src, 'ancre bloc V12 introuvable'
src = src.replace(old, new, 1)
open(p, 'w').write(src)
print('EDIT server.py: EXPORT-TILES-V13')
