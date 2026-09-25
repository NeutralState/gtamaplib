"""dt_overlay.py <cam> [x y z yaw pitch roll hfov] -> overlay_<cam>.jpg : meshs (fil de fer) + labels des landmarks hauts, pour identifier les tours."""
import sys, json, numpy as np, cv2
sys.path.insert(0,'/Users/alexandreleblanc/Downloads/gtamaplib-main'); import gtamaplib as G
R='/Users/alexandreleblanc/Downloads/gtamaplib-main/'
name=sys.argv[1]; C=json.load(open(R+'gtamapdata/cameras.json'))[name]
if len(sys.argv)>2:
    v=[float(a) for a in sys.argv[2:9]]; xyz,ypr,hf=v[:3],v[3:6],v[6]
else: xyz,ypr,hf=C['xyz'],C['ypr'],C['fov'][0]
W,H=1920,1080; q=G.get_q(list(ypr)); fov=(hf,G.get_vfov(hf,(W,H)))
def P(X):
    p=G.get_pixel(np.array(X,float),xyz,q,fov,(W,H)); return None if p is None else (int(p[0]),int(p[1]))
fr=cv2.imread(R+'frames/%s.png'%name)
M=json.load(open(R+'gtamapdata/building_meshes_procedural.json'))
for mname,m in M.items():
    for a,b in m['world_edges']:
        pa,pb=P(a),P(b)
        if pa and pb and all(-3000<c<5000 for c in pa+pb): cv2.line(fr,pa,pb,(0,255,255),1,cv2.LINE_AA)
    E=np.array(m['world_edges'],float); top=E[E[:,:,2].max(axis=1)>E[:,:,2].max()-1][:,0,:]; c=top.mean(axis=0) if len(top) else E[:,0,:].mean(axis=0)
    pc=P(c)
    if pc and 0<=pc[0]<W and 0<=pc[1]<H: cv2.putText(fr,mname[:22],(pc[0]+4,pc[1]-4),cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,200,255),1,cv2.LINE_AA)
LM=json.load(open(R+'gtamapdata/landmarks.json'))
for k,v in LM.items():
    X=v.get('xyz')
    if not X or X[2]<60 or k.split(' (')[0] in M: continue
    p=P(X)
    if p and 0<=p[0]<W and 0<=p[1]<H: cv2.drawMarker(fr,p,(255,0,255),cv2.MARKER_CROSS,14,1); cv2.putText(fr,k[:24],(p[0]+4,p[1]+12),cv2.FONT_HERSHEY_SIMPLEX,0.4,(255,0,255),1,cv2.LINE_AA)
# horizon (monde plat): points tres loin a z=cam
for az in range(0,360,2):
    p=P([xyz[0]+1e6*np.sin(np.radians(az)),xyz[1]+1e6*np.cos(np.radians(az)),0])
    if p and 0<=p[0]<W and 0<=p[1]<H: cv2.circle(fr,p,1,(0,0,255),2)
out='overlay_%s.jpg'%name.replace(' ','_'); cv2.imwrite(out,cv2.resize(fr,(1600,900),interpolation=cv2.INTER_AREA),[cv2.IMWRITE_JPEG_QUALITY,88]); print(out,'pose',np.round(xyz,0),np.round(ypr,1),hf)
