"""onmap.py ortho.png meta.json out.jpg [marge_m] : ortho opaque posee sur la V16 (carte visible seulement hors couverture)."""
import sys, cv2, numpy as np, json
o=cv2.imread(sys.argv[1]); m=json.load(open(sys.argv[2])); out=sys.argv[3]; marg=float(sys.argv[4]) if len(sys.argv)>4 else 400
x0,x1,y0,y1,res=m['x0'],m['x1'],m['y0'],m['y1'],m['res']
X0,X1,Y0,Y1=x0-marg,x1+marg,y0-marg,y1+marg
v=cv2.imread('/Users/alexandreleblanc/Downloads/gtamaplib-main/maps/yanis,16svg.png')[int(11008-Y1):int(11008-Y0), int(X0+16991):int(X1+16991)]
sc=1.0/res; canvas=cv2.resize(v,None,fx=sc,fy=sc,interpolation=cv2.INTER_CUBIC)
mask=(o.sum(axis=2)>0).astype(np.uint8)
import os
INP=float(os.environ.get('INPAINT_M','0'))     # remplit les petits trous (sol sous les tabliers, slivers) par inpainting si leur demi-largeur < INPAINT_M
if INP>0:
    holes=(1-mask).astype(np.uint8); dt=cv2.distanceTransform(holes,cv2.DIST_L2,3)
    n,lab,st,cen=cv2.connectedComponentsWithStats(holes,8); small=np.zeros_like(holes)
    for i in range(1,n):
        if st[i,4]<4: continue
        sel=lab==i
        if dt[sel].max()*res<INP: small[sel]=1
    if small.any():
        o=cv2.inpaint(o,small,5,cv2.INPAINT_TELEA); mask=(o.sum(axis=2)>0).astype(np.uint8); print('inpainting: %.2f%% de l emprise'%(100*small.mean()))
mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8)); mask=cv2.erode(mask,np.ones((5,5),np.uint8))   # bords propres
# fondu de 6 px sur le bord pour eviter le decoupage net
alpha=cv2.GaussianBlur(mask.astype(np.float32),(0,0),2.5)[...,None]
r0,c0=int((Y1-y1)*sc),int((x0-X0)*sc); H,W=o.shape[:2]
roi=canvas[r0:r0+H,c0:c0+W].astype(np.float32); roi=roi*(1-alpha)+o.astype(np.float32)*alpha; canvas[r0:r0+H,c0:c0+W]=roi.astype(np.uint8)
cv2.imwrite(out,canvas,[cv2.IMWRITE_JPEG_QUALITY,90]); print(out,canvas.shape)
