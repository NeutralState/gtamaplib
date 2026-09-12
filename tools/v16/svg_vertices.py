"""svg_vertices2.py — extrait les sommets vectoriels de la V16 (SVG) en coordonnees monde (x = px - 16992, y = 11008 - py).
Gere <path d> (M/L/H/V/C/S/Q/Z absolus et relatifs), <rect>, <circle>, <ellipse>, <use> ignore, transforms translate/scale/rotate/matrix sur <g> et sur l'element.
usage: svg_vertices2.py <svg> <out.json> [old_vertices.json pour classer les couleurs]
"""
import re, sys, json, math, numpy as np
svg=open(sys.argv[1]).read(); out=sys.argv[2]; old=json.load(open(sys.argv[3]))['categories'] if len(sys.argv)>3 else None
import os; X0,Y0=int(os.environ.get("V16_X0","16992")),11008
tok=re.compile(r'<(/?)(g|path|rect|circle|ellipse|svg|defs|clipPath|mask|symbol)\b([^>]*?)(/?)>',re.S)
def parse_transform(s):
    M=np.eye(3)
    for name,args in re.findall(r'(matrix|translate|scale|rotate)\(([^)]*)\)',s or ''):
        a=[float(v) for v in re.split(r'[ ,]+',args.strip()) if v]
        T=np.eye(3)
        if name=='matrix' and len(a)==6: T=np.array([[a[0],a[2],a[4]],[a[1],a[3],a[5]],[0,0,1]])
        elif name=='translate': T[0,2]=a[0]; T[1,2]=a[1] if len(a)>1 else 0
        elif name=='scale': T[0,0]=a[0]; T[1,1]=a[1] if len(a)>1 else a[0]
        elif name=='rotate':
            r=math.radians(a[0]); R=np.array([[math.cos(r),-math.sin(r),0],[math.sin(r),math.cos(r),0],[0,0,1]])
            if len(a)==3: T=np.array([[1,0,a[1]],[0,1,a[2]],[0,0,1]])@R@np.array([[1,0,-a[1]],[0,1,-a[2]],[0,0,1]])
            else: T=R
        M=M@T
    return M
attr=lambda s,k: (re.search(r'\b'+k+r'="([^"]*)"',s) or [None,None])[1]
num=re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
def path_vertices(d):
    pts=[]; cur=np.zeros(2); start=np.zeros(2); cmd=None
    for m in re.finditer(r'([MLHVCSQTZmlhvcsqtz])|('+num.pattern+')',d):
        if m.group(1): cmd=m.group(1); nums=[];
        else:
            nums.append(float(m.group(2)))
        if not cmd: continue
        c=cmd; rel=c.islower(); C=c.upper()
        if C=='Z' and m.group(1): cur=start.copy(); continue
        need={'M':2,'L':2,'H':1,'V':1,'C':6,'S':4,'Q':4,'T':2}.get(C,0)
        if need==0 or len(nums)<need: continue
        a=nums[:need]; nums=nums[need:]
        if C in 'ML':
            p=np.array(a); p=cur+p if rel else p; cur=p; pts.append(p.copy())
            if C=='M': start=p.copy(); cmd='l' if rel else 'L'
        elif C=='H': cur=np.array([cur[0]+a[0] if rel else a[0],cur[1]]); pts.append(cur.copy())
        elif C=='V': cur=np.array([cur[0],cur[1]+a[0] if rel else a[0]]); pts.append(cur.copy())
        elif C in ('C','S','Q','T'):
            p=np.array(a[-2:]); p=cur+p if rel else p; cur=p; pts.append(p.copy())
    return pts
stack=[np.eye(3)]; skip=0; verts={}  # fill -> list
for m in tok.finditer(svg):
    close,tag,body,selfclose=m.groups()
    if tag in ('defs','clipPath','mask','symbol'):
        if close: skip=max(0,skip-1)
        elif not selfclose: skip+=1
        continue
    if tag=='g':
        if close: stack.pop()
        elif not selfclose: stack.append(stack[-1]@parse_transform(attr(body,'transform')))
        continue
    if skip or close or tag=='svg': continue
    M=stack[-1]@parse_transform(attr(body,'transform')); fill=(attr(body,'fill') or 'none').upper()
    if tag=='path':
        d=attr(body,'d');
        if not d: continue
        pts=path_vertices(d)
    elif tag=='rect':
        x=float(attr(body,'x') or 0); y=float(attr(body,'y') or 0); w=float(attr(body,'width') or 0); h=float(attr(body,'height') or 0); pts=[np.array(p) for p in ((x,y),(x+w,y),(x+w,y+h),(x,y+h))]
    elif tag in ('circle','ellipse'):
        cx=float(attr(body,'cx') or 0); cy=float(attr(body,'cy') or 0); r=float(attr(body,'r') or attr(body,'rx') or 0); pts=[np.array((cx,cy))]; fill='CIRCLE:'+fill+f':r{r:.1f}'
    else: continue
    for p in pts:
        q=M@np.array([p[0],p[1],1.0]); verts.setdefault(fill,[]).append((round(q[0]-X0,2),round(Y0-q[1],2)))
print('fills:',len(verts),'| sommets:',sum(len(v) for v in verts.values()))
# classement des couleurs par recouvrement avec les anciennes categories
cats={}
if old:
    from scipy.spatial import cKDTree
    trees={k:cKDTree(np.array(v)) for k,v in old.items()}
    for fill,pts in sorted(verts.items(),key=lambda kv:-len(kv[1])):
        P=np.array(pts); sc={k:float((t.query(P)[0]<1.5).mean()) for k,t in trees.items()}; best=max(sc,key=sc.get)
        cat=best if sc[best]>0.3 else 'other'; cats[fill]=cat
        if len(pts)>=50: print(f'  {fill:22s} n={len(pts):6d}  -> {cat:9s} (building {sc["building"]:.2f} structure {sc["structure"]:.2f} yellow {sc["yellow"]:.2f})')
res={'_comment':f"Sommets vectoriels de la carte communautaire V16 (SVG {sys.argv[1].split('/')[-1]}), coordonnees monde x=px-{X0}, y={Y0}-py; categories building/structure/yellow (couleurs classees par recouvrement avec la version precedente; les autres fills ne sont pas exportes)",'categories':{},'fills':{}}
for fill,pts in verts.items():
    cat=cats.get(fill,'other'); res['fills'][fill]={'n':len(pts),'cat':cat}
    if cat!='other': res['categories'].setdefault(cat,[]).extend(pts)
print({k:len(v) for k,v in res['categories'].items()})
json.dump(res,open(out,'w'),ensure_ascii=True)
