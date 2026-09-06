import sys, json, collections, time, os, re
sys.path.insert(0,'/private/tmp/claude-501/-Users-alexandreleblanc-Downloads-gtamaplib-main/b03356f6-af67-4086-b7cc-fad47ae03b07/scratchpad')
sys.path.insert(0,'/Users/alexandreleblanc/Downloads/gtamaplib-main/tools'); sys.path.insert(0,'/Users/alexandreleblanc/Downloads/gtamaplib-main')
from camlib import *
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
import structures as _structs
APPLY = len(sys.argv)>1 and sys.argv[1]=='apply'
REPO='/Users/alexandreleblanc/Downloads/gtamaplib-main/'
EX=json.load(open(ROOT+'excluded_markings.json')); MV=json.load(open(ROOT+'map_validated.json'))
LEAKREF=set(json.load(open(REPO+'tools/audit/leak_poses_ref.json'))); SOLVEDREF=set(json.load(open(REPO+'tools/audit/solved_poses_ref.json')))
X0,X1,Y0,Y1=[float(v) for v in sys.argv[2:6]] if len(sys.argv)>=6 else (-800,2600,-2800,2800)
ZTAG=sys.argv[6] if len(sys.argv)>=7 else 'DOWNTOWN'
def inzone(p): return X0<=p[0]<=X1 and Y0<=p[1]<=Y1
def ok(k): v=lms.get(k); return isinstance(v,dict) and isinstance(v.get('xyz'),list) and len(v['xyz'])==3 and all(isinstance(t,(int,float)) for t in v['xyz'])
def _cls(c): return str(cams[c].get('constraint_class') or '')
def semi(c):
    C=cams[c]; return (not C.get('pose_verified')) and c not in SOLVEDREF and _cls(c).startswith(('C_','Cm_'))
def locked(c):
    C=cams[c]; cls=_cls(c)
    if semi(c): return False
    return bool(C.get('pose_verified')) or c in LEAKREF or c in SOLVEDREF or bool(C.get('player')) or cls.startswith(('A_','B_','C_','Cm_')) or bool(re.match(r'\d{4}-\d{2}-\d{2}',str(C.get('source') or '')))
obs=collections.defaultdict(list)
for cn,d in px.items():
    if cn not in cams or cams[cn].get('excluded') or not cams[cn].get('xyz'): continue
    ex=set(EX.get(cn,[]))
    for lm,p in d.items():
        if lm in ex or not ok(lm): continue
        obs[lm].append((cn,np.array(p,float)))
def parallax(lm):
    X=np.array(lms[lm]['xyz']); us=[(X-cam(c)['xyz'])/np.linalg.norm(X-cam(c)['xyz']) for c,_ in obs[lm]]
    return max((np.degrees(np.arccos(np.clip(np.dot(a,b),-1,1))) for a in us for b in us),default=0)
ZFIX={k:float(lms[k]['z_constraint']['value']) for k in lms if isinstance(lms[k],dict) and (lms[k].get('z_constraint') or {}).get('type')=='fixed'}
STRUCT_MEMBERS={m for sname,sd in _structs.load().items() if isinstance(sd,dict) for m in (sd.get('members') or [])}
HARD={k for k,v in MV.items() if isinstance(v,dict) and v.get('verdict')=='validated' and k in lms and ok(k)}
# MONOCAM-ANCHOR-FIX 2026-09-06: les ancres tooltips validees comptent meme vues par une seule cam (sinon une cam libre s'en ecarte sans que le garde-fou le voie: Raul Bautista 03 / Four Seasons 300 px)
Lall=[lm for lm,o in obs.items() if len(o)>=2 or lm in HARD]
L=[lm for lm in Lall if inzone(lms[lm]['xyz']) and lm not in STRUCT_MEMBERS and (parallax(lm)>=2.0 or lm in HARD)]
camset=sorted({cn for lm in Lall for cn,_ in obs[lm]})
nclk=collections.Counter(cn for lm in Lall for cn,_ in obs[lm])
free=[c for c in camset if not locked(c) and inzone(cams[c]['xyz']) and nclk[c]>=8 and 'POSITION ALEXANDRE' not in str(cams[c].get('notes',''))]
print(f"zone: {len(Lall)} landmarks, {len(L)} libres dont {len([l for l in L if l in HARD])} ancres tooltips, {len([l for l in L if l in ZFIX])} z fixes | {len(camset)} cams, {len(free)} libres (lockees: {len([c for c in camset if locked(c)])})")
print("cams libres:",free)
ci={c:i for i,c in enumerate(free)}; li={lm:i for i,lm in enumerate(L)}; NC=7*len(free)
def cam0(c): C=cams[c]; return list(C['xyz'])+list(C['ypr'])+[C['fov'][0] if C['fov'][0] else G.get_hfov(C['fov'][1],tuple(C['size']))]
x0=np.concatenate([np.array([cam0(c) for c in free],float).ravel() if free else np.array([]), np.array([lms[lm]['xyz'] for lm in L],float).ravel()])
POS_SIG=np.array([1e-4 if semi(c) else 25.0 for c in free]); FOV_SIG=np.array([(1e-4 if _cls(c).startswith('C_') else 0.5) for c in free]); YAW_SIG=0.5
print('cams semi (xyz fixe, ypr libre):',[c for c in free if semi(c)])
def cam_of(x,c):
    if c in ci: v=x[7*ci[c]:7*ci[c]+7]; return cam(c,xyz=v[:3],ypr=v[3:6],hfov=v[6])
    return cam(c)
rows=[(lm,cn,p,(3.0 if lm in HARD else 1.0)) for lm in Lall for cn,p in obs[lm]]; NR=2*len(rows)
_pp='/private/tmp/claude-501/-Users-alexandreleblanc-Downloads-gtamaplib-main/b03356f6-af67-4086-b7cc-fad47ae03b07/scratchpad/v16_pairs_'+ZTAG.lower()+'.json'
PAIRS=json.load(open(_pp)) if os.path.exists(_pp) else []
print('paires V16:',len(PAIRS),_pp if PAIRS else '(aucune)'); pi_=[(li[p['lm']],np.array(p['v16'])) for p in PAIRS if p['lm'] in li and p['lm'] not in HARD]; MAP_SIG=2.5
# HARD-XY-FIX 2026-09-06: les ancres validees gardent leur xy EXACT (le prior sigma 0.5 etait aplati par soft_l1: FS/Infinity avaient derive de 5-13 m); seul z reste libre
def lmpos(x,lm):
    if lm not in li: return np.array(lms[lm]['xyz'],float)
    i=NC+3*li[lm]
    if lm in HARD: return np.array([x0[i],x0[i+1],x[i+2]])
    return x[i:i+3]
HI=[li[lm] for lm in L if lm in HARD]; HARD_SIG=0.5
ZI=[(li[lm],ZFIX[lm]) for lm in L if lm in ZFIX]; Z_SIG=0.01
NP=NR+5*len(free); NQ=NP+2*len(pi_)+2*len(HI)
def resid(x):
    Cc={c:cam_of(x,c) for c in camset}; out=np.empty(NQ+len(ZI))
    for i,(lm,cn,p,w) in enumerate(rows):
        q=proj(Cc[cn],lmpos(x,lm)); out[2*i:2*i+2]=(q-p)*w if q is not None else 500.0
    for j in range(len(free)):
        v=x[7*j:7*j+7]; v0=x0[7*j:7*j+7]; out[NR+5*j:NR+5*j+3]=(v[:3]-v0[:3])/POS_SIG[j]*3.0; out[NR+5*j+3]=(v[6]-v0[6])/FOV_SIG[j]*3.0; out[NR+5*j+4]=(((v[3]-v0[3])+180)%360-180)/YAW_SIG*3.0
    for k,(i,v) in enumerate(pi_): out[NP+2*k:NP+2*k+2]=(x[NC+3*i:NC+3*i+2]-v)/MAP_SIG*3.0
    for k,i in enumerate(HI): out[NP+2*len(pi_)+2*k:NP+2*len(pi_)+2*k+2]=(x[NC+3*i:NC+3*i+2]-x0[NC+3*i:NC+3*i+2])/HARD_SIG*3.0
    for k,(i,zv) in enumerate(ZI): out[NQ+k]=(x[NC+3*i+2]-zv)/Z_SIG*3.0
    return out
Sp=lil_matrix((NQ+len(ZI),len(x0)),dtype=int)
for i,(lm,cn,p,w) in enumerate(rows):
    if cn in ci: Sp[2*i:2*i+2,7*ci[cn]:7*ci[cn]+7]=1
    if lm in li: Sp[2*i:2*i+2,NC+3*li[lm]:NC+3*li[lm]+3]=1
for j in range(len(free)): Sp[NR+5*j:NR+5*j+3,7*j:7*j+3]=1; Sp[NR+5*j+3,7*j+6]=1; Sp[NR+5*j+4,7*j+3]=1
for k,(i,v) in enumerate(pi_): Sp[NP+2*k:NP+2*k+2,NC+3*i:NC+3*i+2]=1
for k,i in enumerate(HI): Sp[NP+2*len(pi_)+2*k:NP+2*len(pi_)+2*k+2,NC+3*i:NC+3*i+2]=1
for k,(i,zv) in enumerate(ZI): Sp[NQ+k,NC+3*i+2]=1
def stats(x):
    r=resid(x)[:NR].reshape(-1,2); w=np.array([w for *_,w in rows]); return np.hypot(r[:,0],r[:,1])/w
e0=stats(x0); print(f"AVANT: mediane {np.median(e0):.2f} px, 90%={np.percentile(e0,90):.1f}, >15 px: {(e0>15).sum()} | ancres tooltips mediane {np.median([e for (lm,cn,p,w),e in zip(rows,e0) if lm in HARD]):.1f} px")
t=time.time(); r=least_squares(resid,x0,jac_sparsity=Sp,loss='soft_l1',f_scale=6.0,method='trf',max_nfev=150,x_scale='jac'); x=r.x
for lm in L:
    if lm in HARD: i=NC+3*li[lm]; x[i]=x0[i]; x[i+1]=x0[i+1]
e1=stats(x); print(f"APRES ({time.time()-t:.0f}s): mediane {np.median(e1):.2f} px, 90%={np.percentile(e1,90):.1f}, >15 px: {(e1>15).sum()} | ancres tooltips mediane {np.median([e for (lm,cn,p,w),e in zip(rows,e1) if lm in HARD]):.1f} px")
mv=np.array([np.linalg.norm(x[NC+3*i:NC+3*i+3]-x0[NC+3*i:NC+3*i+3]) for i in range(len(L))]); print(f"landmarks: deplacement mediane {np.median(mv):.2f} m, 90%={np.percentile(mv,90):.1f}, max {mv.max():.1f} ({L[int(mv.argmax())]})")
cm=[(c,float(np.linalg.norm(x[7*j:7*j+3]-x0[7*j:7*j+3])),float(abs(((x[7*j+3]-x0[7*j+3])+180)%360-180)),float(x[7*j+6]-x0[7*j+6])) for j,c in enumerate(free)]
print("cams (pos / yaw / fov), top 12:"); [print(f"   {c:44s} {dp:5.1f} m  yaw {dy:4.2f}  fov {df:+5.2f}") for c,dp,dy,df in sorted(cm,key=lambda t:-t[1])[:12]]
# cam gate: median residual over ALL its clicks (in-zone rows) must not degrade >20%
gate={}
for c in free:
    idx=[i for i,(lm,cn,p,w) in enumerate(rows) if cn==c]
    m0=np.median(e0[idx]); m1=np.median(e1[idx]); gate[c]=(m1<=m0*1.2+0.3, m0, m1)
bad=[c for c,(g,m0,m1) in gate.items() if not g]; print("cams refusees par le garde-fou (mediane +20%):",[(c,round(gate[c][1],1),round(gate[c][2],1)) for c in bad])
if APPLY:
    LM=json.load(open(ROOT+'landmarks.json')); CM=json.load(open(ROOT+'cameras.json'))
    tag=f'BA-{ZTAG}-6d 2026-09-06 (bundle zone; ancres mono-cam incluses; ancres tooltips x3 dont 8 coins Vizcayne; V16 sigma 2.5 m; cams SOLVED/leak/HUD hors variables; z_constraint et structures respectes)'
    nl=0; nsnap=0
    for i,lm in enumerate(L):
        p=[float(v) for v in x[NC+3*i:NC+3*i+3]]
        if lm in ZFIX: p[2]=ZFIX[lm]
        sn,applied=_structs.snap(lm,p,LM)
        if applied and list(sn)!=p: p=list(sn); nsnap+=1
        d=np.linalg.norm(np.array(p)-np.array(LM[lm]['xyz']))
        if d>30: LM[lm]['note']=(f"REVUE {tag}: voulait bouger de {d:.0f} m, garde | "+str(LM[lm].get('note','')))[:1500]; continue
        LM[lm]['xyz']=[round(v,3) for v in p]; nl+=1
        if d>=1.0: LM[lm]['note']=(f"{tag}: deplace {d:.1f} m | "+str(LM[lm].get('note','')))[:1500]
    nc=0
    for j,c in enumerate(free):
        if not gate[c][0]: continue
        v=x[7*j:7*j+7]; CM[c]['ypr']=[round(float(t),4) for t in v[3:6]]; nc+=1
        if not semi(c): CM[c]['xyz']=[round(float(t),3) for t in v[:3]]; CM[c]['fov']=[round(float(v[6]),3),None]
        elif _cls(c).startswith('Cm_'): CM[c]['fov']=[round(float(v[6]),3),None]
        CM[c]['notes']=(f"{tag} | "+str(CM[c].get('notes','')))[:1500]
    json.dump(LM,open(ROOT+'landmarks.json','w'),indent=2,ensure_ascii=True); json.dump(CM,open(ROOT+'cameras.json','w'),indent=1,ensure_ascii=True)
    print(f"APPLIQUE: {nl} landmarks ({nsnap} snaps structure), {nc} cams")
