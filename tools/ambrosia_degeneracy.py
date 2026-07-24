"""Sweep le long de l AXE DE DEGENERESCENCE de rlx (dy = ~31 m par m de dz).
t=0 = notre monde, t=1 = son 'latest gtamaplib' (dy+242, dz+7.7)."""
import sys, math, json
sys.path.insert(0, 'tools'); sys.path.insert(0, '.')
import numpy as np, importlib.util
spec = importlib.util.spec_from_file_location('aj', 'tools/ambrosia_joint.py')
aj = importlib.util.module_from_spec(spec); spec.loader.exec_module(aj)

DY, DZ = 242.0, 7.7
px, lms, cams = aj.load()
zone, anchors, ext = aj.collect(px, lms, cams, use_brator=True, no_kalaga=False)
sv0 = aj.Solver(zone, anchors, ext, lms, cams, init='ours')
_, d0 = sv0.cost(collect_detail=True)
for lm in [l for l,(P,e) in d0.items() if e is not None and e > 90.0]: zone.pop(lm, None)

def bridge_res(sv):
    out = []
    for lm in ('Sunshine Skyway Bridge (N)', 'Sunshine Skyway Bridge (S)'):
        if lm not in sv.anchors: continue
        X = np.asarray(sv.lms[lm]['xyz'], float)
        for c, p in sv.anchors[lm]:
            cam = sv.cam(c)
            d = np.asarray(cam.get_pixel_direction(p), float); d/=np.linalg.norm(d)
            v = X - np.asarray(cam.xyz, float); v/=np.linalg.norm(v)
            out.append(math.degrees(math.acos(float(np.clip(v@d,-1,1))))*60)
    return out

print(f'{"t":>6s} {"dy":>7s} {"dz":>6s} {"cout ancre":>11s} {"vs t=0":>8s}   piliers Skyway (Fires)')
base = None
for t in (-0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0, 1.25):
    sv = aj.Solver(zone, anchors, ext, lms, cams, init='ours')
    for c in aj.AMB:
        sv.theta[c][1] += DY*t; sv.theta[c][2] += DZ*t
        y, z = sv.theta[c][1], sv.theta[c][2]
        sv.bounds[c][1] = (y-5, y+5); sv.bounds[c][2] = (z-1.5, z+1.5)
    cost = sv.descend(rounds=25, verbose=False)
    if t == 0.0: base = cost
    br = bridge_res(sv)
    tag = '  <- notre monde' if t == 0 else ('  <- son latest gtamaplib' if t == 1.0 else '')
    print(f'{t:6.2f} {DY*t:+7.0f} {DZ*t:+6.1f} {cost:11.2f} {"" if base is None else f"{cost-base:+8.2f}"}   '
          + ' '.join(f'{e:6.1f}\'' for e in br) + tag, flush=True)
