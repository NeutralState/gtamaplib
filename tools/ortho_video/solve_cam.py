"""solve_cam.py <cam> [fixfov] : pose + fov libre sur les clics d'Alexandre (landmarks avec xyz), priors roulis 0 (s 0.5 deg)"""
import sys, json, numpy as np
sys.path.insert(0,'/Users/alexandreleblanc/Downloads/gtamaplib-main'); import gtamaplib as G
from scipy.optimize import least_squares
R='/Users/alexandreleblanc/Downloads/gtamaplib-main/gtamapdata/'
cams=json.load(open(R+'cameras.json')); LM=json.load(open(R+'landmarks.json')); P=json.load(open(R+'pixels.json'))
EX=json.load(open(R+'excluded_markings.json')) if __import__('os').path.exists(R+'excluded_markings.json') else {}
name=sys.argv[1]; fixfov=len(sys.argv)>2 and sys.argv[2]=='fixfov'; c=cams[name]; W,H=c['size']
pts=[(n,np.array(LM[n]['xyz'],float),np.array(px,float)) for n,px in P[name].items() if LM.get(n,{}).get('xyz') and n not in set(EX.get(name,[]))]
print(name,len(pts),'points; init',c['xyz'],c['ypr'],c['fov'][0])
zprior=float(sys.argv[3]) if len(sys.argv)>3 else None
def resid(v):
    xyz,ypr,hf=v[:3],v[3:6],(c['fov'][0] if fixfov else v[6]); q=G.get_q(list(ypr)); fov=(hf,G.get_vfov(hf,(W,H)))
    r=[]
    for n,X,p in pts:
        pr=G.get_pixel(X,xyz,q,fov,(W,H)); r+= list((pr-p) if pr is not None else [1e3,1e3])
    r.append(ypr[2]/0.5*2.0)   # roulis ~0, s 0.5 deg exprime en ~2 px
    if zprior: r.append((xyz[2]-zprior)/10.0*2.0)
    return np.array(r)
v0=np.r_[c['xyz'],c['ypr'],[c['fov'][0]]]
sol=least_squares(resid,v0,x_scale=[5,5,5,0.2,0.2,0.2,0.5],max_nfev=400)
v=sol.x; hf=c['fov'][0] if fixfov else v[6]; q=G.get_q(list(v[3:6])); fov=(hf,G.get_vfov(hf,(W,H)))
res=[(n,np.linalg.norm(G.get_pixel(X,v[:3],q,fov,(W,H))-p),np.linalg.norm(X[:2]-v[:2])) for n,X,p in pts]
rms=np.sqrt(np.mean([r*r for _,r,_ in res]))
print('xyz',np.round(v[:3],1),'ypr',np.round(v[3:6],2),'hfov %.1f'%hf,'rms %.1f px'%rms)
for n,r,d in res: print('   %-28s %6.1f px   dist %4.0f m'%(n,r,d))
print('deplacement vs init: %.1f m'%np.linalg.norm(v[:3]-np.array(c['xyz'])))
json.dump({'xyz':[round(float(a),2) for a in v[:3]],'ypr':[round(float(a),3) for a in v[3:6]],'hfov':round(float(hf),3),'rms':round(float(rms),2),'n':len(pts)},open('solve_%s.json'%name.split(') ')[-1].replace(' ','_'),'w'))
