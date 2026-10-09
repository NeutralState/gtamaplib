#!/usr/bin/env python3
"""gen_i97_explosion.py — I-97 viaduct between the I-97/I-404 interchange and the Explosion camera. [I97-VIADUCT-V1 2026-10-09]

The 3D roads had the I-97 at grade (3 m) between the interchange viaduct (ends at y ~ +150, deck 12 m ESTIMATED from
Explosion) and the Explosion camera (SOLVED, on the I-97 deck at z 15.5), so the camera floated 12 m above the road.
Plan = V16: the two I-97 carriageways (3D-road highway strokes, 17 m and 12 m wide) near x ~ -1000.
Height MEASURED in the Explosion frame: the armoured truck ahead (BearCat-type, 2.44-2.59 m wide, ~28 m away) puts the
camera 2.7-2.9 m above the road -> deck top 12.7 m at y ~ -185 (ground 3.2 m: viaduct ~9.5 m high, like IRL I-95).
Profile: 12.0 m where it meets the interchange viaduct (y +150), linear to 12.7 m at the measured point, held 50 m south,
then down to grade at max 4 % (ESTIMATED: no frame shows the south end).
Usage: PYTHONPATH=. python3 tools/gen_i97_explosion.py [--apply]
"""
import json, os, sys, shutil, math
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from gen_keys_bridges import Bridge
from horizon_resect import ground

NAME = 'I-97 Viaduct (Explosion)'
Y_JOIN, Z_JOIN = 150.0, 12.0          # interchange viaduct end (gen_interchange: y > WIN[2] - 150), its I-97 level
Y_MEAS, Z_MEAS = -185.0, 12.7         # measured deck top (Explosion frame)
HOLD = 50.0                           # plateau south of the measured point (the camera sits at y -212)
GRADE = 0.04
DEPTH, PARAPET = 1.8, 1.0


def carriageways():
    R = json.load(open(os.path.join(ROOT, 'tools', 'threejs', '_v16_roads.json')))
    out = []
    for s in R['hwy']:
        P = np.array(s['p'], float)[:, :2]
        if np.hypot(*(P - [-1001, -212]).T).min() < 15: out.append((P, s['w']))
    return out


def top(y, g_end):
    """deck top as a function of y (the I-97 runs ~north-south here)."""
    if y >= Y_JOIN: return None
    if y >= Y_MEAS: return Z_JOIN + (Z_MEAS - Z_JOIN) * (Y_JOIN - y) / (Y_JOIN - Y_MEAS)
    y_hold = Y_MEAS - HOLD
    if y >= y_hold: return Z_MEAS
    L = 1.5708 * (Z_MEAS - g_end) / GRADE                         # cosine ramp, max grade GRADE
    t = (y_hold - y) / L
    if t >= 1: return None
    return g_end + (Z_MEAS - g_end) * (0.5 + 0.5 * math.cos(math.pi * t))


def build():
    E = []; notes = []
    for P, w in carriageways():
        if P[0][1] < P[-1][1]: P = P[::-1]                            # north -> south
        br = Bridge(poly=P.tolist())
        ys = lambda s: float(np.interp(s, br.S, P[:, 1]))
        g_end = 3.5
        sel = [s for s in np.arange(0, br.S[-1], 4.0) if top(ys(s), g_end) is not None]
        if not sel: continue
        s0, s1 = min(sel), max(sel)
        zb = lambda s: top(ys(s), g_end) - DEPTH if top(ys(s), g_end) is not None else float(ground(*br.frame(s)[0]))
        hw = w / 2
        br.deck(s0, s1, zb, -hw, hw, depth=DEPTH, parapet=PARAPET, step=8.0, frame=24.0)
        for wq in (-hw / 2, 0.0, hw / 2):                              # lane lines on the deck surface: the 3D roads read the deck
            for a in np.arange(s0, s1 - 8, 8.0):                       # height within 4-8 m of their axis (edges alone are 8.5 m away)
                br.L(br.P(a, wq, zb(a) + DEPTH), br.P(min(a + 8, s1), wq, zb(min(a + 8, s1)) + DEPTH))
        for s in np.arange(s0 + 15, s1 - 10, 32.0):
            g = float(ground(*br.frame(s)[0]))
            if zb(s) - g > 3: br.bent(s, zb, -hw + 0.8, hw - 0.8, ncol=2 if w > 14 else 1, col=1.6, zw=g, cap=1.4)
        E += br.E; notes.append('%.0f m carriageway: %.0f m of deck' % (w, s1 - s0))
    return {NAME: {'color': '#9ca3af', 'world_edges': E, '_credit': 'Alexandre Leblanc (V16 leak) + Claude Opus 5.5',
                   'note': ('I97-VIADUCT-V1 2026-10-09: I-97 between the I-97/I-404 interchange viaduct (joins at y %.0f, %.1f m) and the Explosion camera. Plan = the two V16 I-97 carriageways. '
                            'Deck top %.1f m MEASURED in the Explosion frame (armoured truck ~28 m ahead, 2.44-2.59 m wide: camera 2.7-2.9 m above the road; camera z 15.5 SOLVED unchanged), '
                            'held %.0f m south, then down to grade at max %.0f %% (ESTIMATED, not seen). %s.' % (Y_JOIN, Z_JOIN, Z_MEAS, HOLD, GRADE * 100, '; '.join(notes)))}}


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print(k, len(v['world_edges']), 'edges |', v['note'][-120:])
    if '--apply' in sys.argv:
        mp = os.path.join(ROOT, 'gtamapdata', 'building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_i97_1009')
        M = json.load(open(mp)); M.update(out)
        json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applied ->', len(M))
