"""dt_grid.py <cam> <x0> <y0> <x1> <y1> [x y z yaw pitch roll hfov] -> grid_<cam>.jpg : crop plein format (coordonnees image en grille 100 px) + meme crop avec meshs (fil de fer, labels)."""
import sys, json, numpy as np, cv2
sys.path.insert(0,'/Users/alexandreleblanc/Downloads/gtamaplib-main'); import gtamaplib as G
R='/Users/alexandreleblanc/Downloads/gtamaplib-main/'
name=sys.argv[1]; x0,y0,x1,y1=[int(a) for a in sys.argv[2:6]]; C=json.load(open(R+'gtamapdata/cameras.json'))[name]
if len(sys.argv)>6: v=[float(a) for a in sys.argv[6:13]]; xyz,ypr,hf=v[:3],v[3:6],v[6]
else: xyz,ypr,hf=C['xyz'],C['ypr'],C['fov'][0]
W,H=1920,1080; q=G.get_q(list(ypr)); fov=(hf,G.get_vfov(hf,(W,H)))
def P(X):
    p=G.get_pixel(np.array(X,float),xyz,q,fov,(W,H)); return None if p is None else (int(p[0]),int(p[1]))
fr=cv2.imread(R+'frames/%s.png'%name); plain=fr.copy(); ov=fr.copy()
M=json.load(open(R+'gtamapdata/building_meshes_procedural.json')); cols=[(0,255,255),(0,255,0),(255,128,0),(255,0,255),(0,128,255),(255,255,0)]
for i,(mname,m) in enumerate(sorted(M.items())):
    col=cols[i%len(cols)]
    for a,b in m['world_edges']:
        pa,pb=P(a),P(b)
        if pa and pb and all(-3000<c<5000 for c in pa+pb): cv2.line(ov,pa,pb,col,1,cv2.LINE_AA)
    E=np.array(m['world_edges'],float); top=E[E[:,:,2].max(axis=1)>E[:,:,2].max()-1][:,0,:]; c=top.mean(axis=0) if len(top) else E[:,0,:].mean(axis=0); pc=P(c)
    if pc and x0<=pc[0]<x1 and y0<=pc[1]<y1: cv2.putText(ov,mname[:20],(pc[0]+3,pc[1]-3),cv2.FONT_HERSHEY_SIMPLEX,0.45,col,1,cv2.LINE_AA)
for im in (plain,ov):
    for x in range(0,W,100): cv2.line(im,(x,0),(x,H),(80,80,80),1); cv2.putText(im,str(x),(x+2,y0+14),cv2.FONT_HERSHEY_SIMPLEX,0.4,(255,255,255),1)
    for y in range(0,H,100): cv2.line(im,(0,y),(W,y),(80,80,80),1); cv2.putText(im,str(y),(x0+2,y-2),cv2.FONT_HERSHEY_SIMPLEX,0.4,(255,255,255),1)
out=np.vstack([plain[y0:y1,x0:x1],ov[y0:y1,x0:x1]]); sc=min(1.0,1800/out.shape[1])
o='grid_%s.jpg'%name.replace(' ','_').replace('(','').replace(')',''); cv2.imwrite(o,cv2.resize(out,None,fx=sc,fy=sc,interpolation=cv2.INTER_AREA),[cv2.IMWRITE_JPEG_QUALITY,90]); print(o,out.shape,'pose',np.round(xyz,0),np.round(ypr,1),hf)
