"""Compare l'ortho a la leak map (z5 = 1 m/px, px = x+16384, py = 16384-y) et estime le decalage par fenetres (phase correlation sur gradients)."""
import sys, json, os, cv2, numpy as np
TILES='/Users/alexandreleblanc/Downloads/gtamaplib-main/vendor/gtadb.org/maps/tiles/6/leak,1/5'; T=256
def leak_crop(x0,x1,y0,y1):
    lx,ty=x0+16384,16384-y1; rx,by=x1+16384,16384-y0
    tx0,tx1=int(lx//T),int(rx//T); ty0,ty1=int(ty//T),int(by//T)
    comp=np.zeros(((ty1-ty0+1)*T,(tx1-tx0+1)*T,3),np.uint8)
    for tyy in range(ty0,ty1+1):
        for txx in range(tx0,tx1+1):
            p=f'{TILES}/5,{tyy},{txx}.jpg'
            if os.path.exists(p): comp[(tyy-ty0)*T:(tyy-ty0+1)*T,(txx-tx0)*T:(txx-tx0+1)*T]=cv2.imread(p)
    return comp[int(ty-ty0*T):int(by-ty0*T), int(lx-tx0*T):int(rx-tx0*T)]
if __name__=="__main__":
  pass
name=sys.argv[1] if __name__=="__main__" else None
if name:
    m=json.load(open(name+'.json')); o=cv2.imread(name+'_graded.png' if os.path.exists(name+'_graded.png') else name+'.png')
    x0,x1,y0,y1,res=m['x0'],m['x1'],m['y0'],m['y1'],m['res']
    L=leak_crop(x0,x1,y0,y1); o1=cv2.resize(o,(L.shape[1],L.shape[0]),interpolation=cv2.INTER_AREA)   # 1 m/px
    cv2.imwrite(name+'_leak.jpg',L,[cv2.IMWRITE_JPEG_QUALITY,88])
    def grad(img):
        g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY).astype(np.float32); g=cv2.GaussianBlur(g,(0,0),1.5)
        gx=cv2.Sobel(g,cv2.CV_32F,1,0); gy=cv2.Sobel(g,cv2.CV_32F,0,1); mag=np.sqrt(gx*gx+gy*gy); return mag/ (mag.mean()+1e-6)
    GO,GL=grad(o1),grad(L); cov=(o1.sum(axis=2)>0).astype(np.float32); cov=cv2.erode(cov,np.ones((15,15),np.uint8))
    win=300; rows=[]
    for r in range(0,L.shape[0]-win,win//2):
        for c in range(0,L.shape[1]-win,win//2):
            if cov[r:r+win,c:c+win].mean()<0.9: continue
            a=GO[r:r+win,c:c+win]*cv2.createHanningWindow((win,win),cv2.CV_32F); b=GL[r:r+win,c:c+win]*cv2.createHanningWindow((win,win),cv2.CV_32F)
            (dx,dy),resp=cv2.phaseCorrelate(a,b)
            if resp>0.03 and abs(dx)<60 and abs(dy)<60: rows.append((x0+c+win/2, y1-(r+win/2), dx, dy, resp))
    rows=np.array(rows); print('%d fenetres retenues'%len(rows))
    if len(rows):
        # dx>0: la leak est decalee de dx px vers la droite par rapport a l'ortho -> l'ortho doit bouger de +dx en x (est) et -dy en y (nord = -py)
        print('decalage ortho->leak median: dx %+.1f m (est), dy %+.1f m (nord); MAD %.1f / %.1f'%(np.median(rows[:,2]),-np.median(rows[:,3]),np.median(abs(rows[:,2]-np.median(rows[:,2]))),np.median(abs(rows[:,3]-np.median(rows[:,3])))))
        for wx,wy,dx,dy,resp in rows: print('  fenetre (%.0f,%.0f): dx %+5.1f dy(nord) %+5.1f resp %.2f'%(wx,wy,dx,-dy,resp))
    json.dump(rows.tolist(),open(name+'_leakshift.json','w'))
    # visuel: damier ortho/leak
    ck=o1.copy(); s=200
    for r in range(0,L.shape[0],s):
        for c in range(0,L.shape[1],s):
            if ((r//s)+(c//s))%2: ck[r:r+s,c:c+s]=L[r:r+s,c:c+s]
    cv2.imwrite(name+'_leakcheck.jpg',ck,[cv2.IMWRITE_JPEG_QUALITY,88])
