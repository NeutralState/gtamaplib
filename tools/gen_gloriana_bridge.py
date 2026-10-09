#!/usr/bin/env python3
"""gen_gloriana_bridge.py — I-397 bridge over the channel between Gloriana Key and Catalan Key (IRL Bear Cut Bridge). [GLORIANA-BR-V1 2026-10-09]

Plan = V16: the two I-397 carriageways (strokes 3874 eastbound / 3876 westbound, 12 m each), over the channel (heightmap
bed below 1.5 m, down to -6.4 m; the V16 water beside the road), plus the approach ramps.
Height = MEASURED in the Oceanarium frame (camera at the west end of the deck, z 13.8 m after its Z-FIX):
  - car wheelbases (taxi 2.91 m, hatchback 2.70 m, convertible 2.74 m, pickup 2.92 m) and widths put the camera 4-6 m
    above the deck -> deck top 8.5 m at the camera, flat for the first ~40 m (cars at 13-42 m);
  - the overhead sign gantry ~119 m west (5.4 m clearance, 28 m span) stands on ground (~5-6.5 m): the westbound ramp
    is back at grade there -> ramp from 30 m to 125 m west of the camera;
  - the east ramp is not seen: mirrored (ESTIMATED).
Look (frame): two decks side by side with a concrete median barrier, concrete parapets ~1 m, piers below.
Usage: PYTHONPATH=. python3 tools/gen_gloriana_bridge.py [--apply]
"""
import json, os, sys, shutil, math
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from gen_keys_bridges import Bridge
from horizon_resect import ground
import v16_roads as VR

CAM = np.array([142.37, -2033.86])
TOP = 8.5            # deck top at the camera (m), measured
FLAT_W = 30.0        # plateau measured 30 m west of the camera
RAMP = 95.0          # then down to grade within 95 m (gantry at ~119 m stands on ground)
DEPTH, PARAPET, HALF_W = 1.5, 1.0, 6.0
NAME = 'Gloriana Key Bridge'


def water_mask():
    Image.MAX_IMAGE_PIXELS = None
    x0, y0, x1, y1 = -200, -2300, 600, -1800
    V = np.asarray(Image.open(os.path.join(ROOT, 'maps', 'yanis,16svg.png')).crop((x0 + 16991, 11008 - y1, x1 + 16991, 11008 - y0)).convert('RGB')).astype(int)
    W = (V[..., 2] > V[..., 0] + 40) & (V[..., 2] > 120)
    return lambda x, y: bool(W[int(y1 - y), int(x - x0)]) if (x0 <= x < x1 and y0 < y <= y1) else False


def axis(stroke_id):
    S = {s['id']: s for s in VR.strokes()}
    R = np.array(S[stroke_id]['ring'], float)
    if R[0][0] > R[-1][0] and stroke_id == 3874: R = R[::-1]
    keep = np.hypot(*(R - CAM).T) < 650
    R = R[keep]
    if R[0][0] > R[-1][0]: R = R[::-1]          # west -> east
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(R, axis=0).T))]
    t = np.arange(0, s[-1], 5.0)
    return np.c_[np.interp(t, s, R[:, 0]), np.interp(t, s, R[:, 1])]


def build():
    wet = water_mask(); br_all = []; notes = []
    for sid in (3874, 3876):
        A = axis(sid); S = np.r_[0, np.cumsum(np.hypot(*np.diff(A, axis=0).T))]
        sc = S[int(np.argmin(np.hypot(*(A - CAM).T)))]                       # station of the camera
        # channel = heightmap below 1.5 m (bed down to -6.4 m); the V16 water mask is hidden by the road strokes
        wetS = [S[i] for i, p in enumerate(A) if abs(S[i] - sc) < 250 and (float(ground(*p)) < 1.5 or wet(*(p + [0, 16])) or wet(*(p - [0, 16])))]
        s_w, s_e = min(min(wetS), sc), max(wetS)                              # channel 
        z0 = lambda s: float(ground(*A[min(len(A) - 1, int(np.searchsorted(S, s)))])) + 0.3
        a_w, b_w = sc - FLAT_W - RAMP, sc - FLAT_W                            # west ramp (measured)
        a_e, b_e = s_e + FLAT_W, s_e + FLAT_W + RAMP        # east ramp (mirrored, estimated)
        def top(s):
            if s <= a_w or s >= b_e: return z0(s)
            if b_w <= s <= a_e: return TOP
            if s < b_w: t = (s - a_w) / RAMP; g = z0(a_w)
            else: t = (b_e - s) / RAMP; g = z0(b_e)
            k = 0.5 - 0.5 * math.cos(math.pi * t)
            return g + (TOP - g) * k
        zb = lambda s: top(s) - DEPTH
        br = Bridge(poly=A.tolist())
        br.deck(a_w, b_e, zb, -HALF_W, HALF_W, depth=DEPTH, parapet=PARAPET, step=5.0, frame=15.0)
        for s in np.arange(a_w + 12.5, b_e - 5, 25.0):
            p = A[min(len(A) - 1, int(np.searchsorted(S, s)))]
            if zb(s) - float(ground(*p)) > 2.0:
                br.bent(s, zb, -HALF_W + 0.5, HALF_W - 0.5, ncol=2, col=1.3, zw=min(0.0, float(ground(*p))))
        br_all += br.E
        notes.append('carriageway %d: deck %.0f m over the channel (%.0f m wide), ramps %.0f m each side' % (sid, b_e - a_w, s_e - s_w, RAMP))
    return {NAME: {'color': '#cbd5e1', 'world_edges': br_all, 'name_game': NAME, 'name_irl': 'Bear Cut Bridge (Rickenbacker Causeway)',
                   '_credit': 'Alexandre Leblanc (V16) + Claude Opus 5.5',
                   'note': ('GLORIANA-BR-V1 2026-10-09: plan = the two V16 I-397 carriageways (strokes 3874/3876, 12 m each) over the channel; deck top %.1f m MEASURED in the Oceanarium frame '
                            '(car wheelbases/widths: camera 4-6 m above the deck; plateau seen for ~40 m), west ramp back to grade at the sign gantry ~119 m west (gantry posts on ground, measured); '
                            'east ramp mirrored (ESTIMATED, not seen). Concrete parapets 1.0 m and median barriers as in the frame; piers every 25 m where the deck clears the ground by > 2 m. %s. '
                            'Replaces nothing: the VC-BRIDGES estimate for this bridge (8 m, IRL) had been removed on 2026-09-30 for lack of an image.' % (TOP, '; '.join(notes)))}}


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print(k, len(v['world_edges']), 'edges |', v['note'][-260:])
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = os.path.join(ROOT, 'gtamapdata', 'building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_gloriana_1009')
        M = json.load(open(mp)); M.update(out)
        json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applied ->', len(M))
