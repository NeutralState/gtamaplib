"""grade.py in.png out.png : etalonnage de la mosaique (niveaux, CLAHE, saturation) sans toucher aux trous."""
import sys, cv2, numpy as np
img=cv2.imread(sys.argv[1]); m=img.sum(axis=2)>0
px=img[m].astype(np.float32); out=img.astype(np.float32)
for c in range(3):
    lo,hi=np.percentile(px[:,c],[0.8,99.5]); out[...,c]=np.clip((out[...,c]-lo)/max(1,hi-lo)*255,0,255)
out=out.astype(np.uint8)
lab=cv2.cvtColor(out,cv2.COLOR_BGR2LAB); l,a,b=cv2.split(lab)
l=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(12,12)).apply(l); out=cv2.cvtColor(cv2.merge([l,a,b]),cv2.COLOR_LAB2BGR)
hsv=cv2.cvtColor(out,cv2.COLOR_BGR2HSV).astype(np.float32); hsv[...,1]=np.clip(hsv[...,1]*1.45,0,255); out=cv2.cvtColor(hsv.astype(np.uint8),cv2.COLOR_HSV2BGR)
out=cv2.addWeighted(out,1.25,cv2.GaussianBlur(out,(0,0),1.2),-0.25,0)   # leger unsharp
out[~m]=0; cv2.imwrite(sys.argv[2],out); print('ok',sys.argv[2])
