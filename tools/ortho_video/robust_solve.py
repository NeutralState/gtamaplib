"""robust_solve.py <cam> [fixfov] : solve multi-depart (yaw x distance x altitude x fov) + detection des clics aberrants (leave-one-out > 25 px)"""
import sys, json, numpy as np
sys.path.insert(0,'/Users/alexandreleblanc/Downloads/gtamaplib-main'); import gtamaplib as G
from scipy.optimize import least_squares
R='/Users/alexandreleblanc/Downloads/gtamaplib-main/gtamapdata/'; cams=json.load(open(R+'cameras.json')); LM=json.load(open(R+'landmarks.json')); P=json.load(open(R+'pixels.json')); EX=json.load(open(R+'excluded_markings.json'))
name=sys.argv[1]; fix=cams[name]['fov'][0] if 'fixfov' in sys.argv else None; W,H=1920,1080
pts=[(n,np.array(LM[n]['xyz'],float),np.array(p,float)) for n,p in P[name].items() if LM.get(n,{}).get('xyz') and n not in EX.get(name,[]) and 0<=p[0]<W and 0<=p[1]<H]
Xs=np.array([t[1] for t in pts]); cen=Xs.mean(axis=0)
def resid_f(use):
    def resid(v):
        xyz,ypr=v[:3],v[3:6]; hf=fix or v[6]; q=G.get_q(list(ypr)); fov=(hf,G.get_vfov(hf,(W,H))); r=[]
        for n,X,p in use:
            pr=G.get_pixel(X,xyz,q,fov,(W,H)); r+=list((pr-p) if pr is not None else [800,800])
        return np.array(r+[ypr[2]/0.5*2])
    return resid
def solve(use):
    resid=resid_f(use); best=None
    for az in range(0,360,30):
        for d in (400,900,1600):
            for z in (180,300):
                for hf0 in ((fix,) if fix else (65,85,105)):
                    xyz0=[cen[0]+d*np.sin(np.radians(az)),cen[1]+d*np.cos(np.radians(az)),z]; yaw=(360-(az+180))%360
                    v0=np.r_[xyz0,[yaw,-10,0]] if fix else np.r_[xyz0,[yaw,-10,0],[hf0]]
                    s=least_squares(resid,v0,x_scale=[10,10,10,0.5,0.5,0.5]+([] if fix else [1.0]),max_nfev=200)
                    if best is None or s.cost<best.cost: best=s
    v=best.x; r=np.linalg.norm(resid(v)[:-1].reshape(-1,2),axis=1); return v,r
v,r=solve(pts); hf=fix or v[6]; print('%s: %d pts | xyz %s ypr %s hfov %.1f rms %.1f'%(name,len(pts),np.round(v[:3],1),np.round(v[3:6],2),hf,np.sqrt((r**2).mean())))
for (n,_,_),ri in zip(pts,r): print('   %-42s %6.1f px'%(n,ri))
# aberrants: retirer iterativement le pire tant que > 25 px
use=list(pts); dropped=[]
while len(use)>4:
    v,r=solve(use)
    if r.max()<25: break
    i=int(np.argmax(r)); dropped.append((use[i][0],round(float(r[i]),1))); use.pop(i)
hf=fix or v[6]; rms=np.sqrt((r**2).mean()); print('SANS aberrants %s: %d pts | xyz %s ypr %s hfov %.1f rms %.1f'%(dropped,len(use),np.round(v[:3],1),np.round(v[3:6],2),hf,rms))
for (n,_,_),ri in zip(use,r): print('   %-42s %6.1f px'%(n,ri))
json.dump({'xyz':[round(float(a),2) for a in v[:3]],'ypr':[round(float(a),3) for a in v[3:6]],'hfov':round(float(hf),3),'rms':round(float(rms),2),'n':len(use),'dropped':dropped},open('solve_%s.json'%name.split(' ')[-1],'w'))
