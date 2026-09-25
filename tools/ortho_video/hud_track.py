"""Suivi des elements du HUD (mascotte, QR, textes) qui SE DEPLACENT au cours de la video.
Templates pris sur la frame 45, correlation normalisee sur le gradient (les textes sont semi-transparents).
usage: hud_track.py [step] [debug_frames...] -> hud_track.json {frame: {nom: [x, y, w, h, score]}}"""
import sys, json, cv2, numpy as np
step = int(sys.argv[1]) if len(sys.argv) > 1 else 3
debug = [int(a) for a in sys.argv[2:]]
REF = 45
# boites (x0, y0, x1, y1) plein format sur la frame de reference
BOXES = {
    'mascot': (1080, 80, 1220, 350),
    'show_support': (960, 355, 1335, 480),
    'decentralized': (830, 553, 1225, 600),
    'qr': (960, 592, 1090, 700),
    'gateway': (830, 690, 1225, 736),
    'url1': (840, 742, 1210, 790),
    'url2': (920, 793, 1130, 838),
}
def grad(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.GaussianBlur(np.sqrt(gx * gx + gy * gy), (0, 0), 1.0)
ref = cv2.imread('vid/v%04d.jpg' % REF); GR = grad(ref)
T = {n: GR[b[1]:b[3], b[0]:b[2]].copy() for n, b in BOXES.items()}
out = {}
for k in range(0, 720, step):
    img = cv2.imread('vid/v%04d.jpg' % k)
    if img is None: continue
    g = grad(img); rec = {}
    for n, t in T.items():
        r = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED); _, s, _, loc = cv2.minMaxLoc(r)
        rec[n] = [int(loc[0]), int(loc[1]), t.shape[1], t.shape[0], round(float(s), 3)]
    out[k] = rec
    if k % 60 == 0: print(k, {n: (v[0], v[1], v[4]) for n, v in rec.items()}, flush=True)
    if k in debug:
        vis = img.copy()
        for n, v in rec.items():
            c = (0, 255, 0) if v[4] > 0.5 else (0, 0, 255)
            cv2.rectangle(vis, (v[0], v[1]), (v[0] + v[2], v[1] + v[3]), c, 2); cv2.putText(vis, '%s %.2f' % (n, v[4]), (v[0], v[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)
        cv2.imwrite('hud_dbg_%04d.jpg' % k, cv2.resize(vis, (1280, 720)), [cv2.IMWRITE_JPEG_QUALITY, 85])
json.dump(out, open('hud_track.json', 'w'))
print('ok', len(out))
