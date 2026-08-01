#!/usr/bin/env python3
# rederive_mono_0713.py -- re-derivation des LMs mono-source derives.
# Un LM a 1 seul temoin n'a jamais ete que "sur le rayon de sa source a
# distance d". Quand la pose de la source evolue (semaines de cycles), le
# point fige derive (pattern Round Water Tower, classe mono-source — le
# sweep ne peut pas les retrianguler: 1 temoin). Remede: new_xyz = origine
# + d * rayon_actuel(pixel) — meme distance, rayon a jour, residuel ~0.
# L'incertitude le long du rayon reste ce qu'elle a toujours ete.
import json, math, sys
sys.path.insert(0, 'tools'); sys.path.insert(0, '.')
import numpy as np
import common
from common import log_event

lms = json.load(open('gtamapdata/landmarks.json'))
px = json.load(open('gtamapdata/pixels.json'))
obs_by = {}
for c in px:
    for l in px[c]:
        obs_by.setdefault(l, []).append(c)
fixed = 0
for n, e in list(lms.items()):
    if not (e or {}).get('xyz'): continue
    src = e.get('source_cameras') or []
    if len(src) != 1 or len(obs_by.get(n, [])) != 1: continue
    c = src[0]
    cam = common.get_cam(c)
    if cam is None or n not in px.get(c, {}): continue
    a = common.residual_dual(cam, px[c][n], e['xyz'])[0]
    if a is None or a <= 8: continue
    O = np.asarray(cam.xyz, float)
    X = np.asarray(e['xyz'], float)
    d = float(np.linalg.norm(X - O))
    ray = np.asarray(cam.get_pixel_direction(px[c][n]), float)
    ray = ray / np.linalg.norm(ray)
    new = (O + d * ray).tolist()
    moved = math.dist(new, e['xyz'])
    e['xyz'] = [round(v, 4) for v in new]
    print(f"  {n}: {a:.1f}' -> ~0  (deplace {moved:.1f}m le long du rayon a jour)")
    fixed += 1
json.dump(lms, open('gtamapdata/landmarks.json', 'w'), indent=2, ensure_ascii=True)
log_event('rederive_0713', 'mono_source_rederive', count=fixed,
          reason='LMs mono-source re-derives le long du rayon actuel (drift de pose accumule)')
print(f'{fixed} re-derives.')
