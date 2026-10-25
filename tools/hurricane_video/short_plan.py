"""short_plan.py — timeline of the vertical Short « A hurricane hits GTA 6 », cut on the bars of « Born in the 80's » (Falcon Dives,
Epidemic Sound, 117.5 bpm): the music starts 8 beats before its drop (81.82 s) so the dive bursts out of the clouds on the drop.
Run it to write the frame lists the vertical renders need (WORK/short_frames_space.txt, short_frames_top.txt)."""
import os, json, glob
from common import WORK
FPS = 60
BEAT = 60.0 / 117.5; BAR = 4 * BEAT
DROP = 0.116 + 160 * BEAT                     # 81.82 s in the track
MUSIC = os.path.expanduser("~/Downloads/ES_Born in the 80's - Falcon Dives.mp3")
M0 = DROP - 2 * BAR                           # track time at Short t = 0
S_SPACE = (0.0, 2 * BAR)                      # orbit + dive, 11 s of space.py squeezed into 2 bars
S_TOP = (2 * BAR, 4 * BAR)                    # Downtown floods, top-down, 0 -> 5 m
S_3D = (4 * BAR, 6 * BAR)                     # Brickell street level, view3d 40.5 -> 44.2 s (5 -> 8.9 m)
S_ISL = (6 * BAR, 11 * BAR)                   # all of Leonida, island_job 0 -> 17 s (sea 0 -> 8.5 m), question at the end
T_END = 11 * BAR
C_T0, C_T1 = 40.5, 44.2
def n5():
    TM = {}
    for p in glob.glob(os.path.join(WORK, 'top', 'meta_B*.json')):
        for m in json.load(open(p)): TM[m['n']] = m
    return next(n for n in sorted(TM) if TM[n]['level'] >= 5.0)
def space_frame(t): return int(round((t - S_SPACE[0]) / (S_SPACE[1] - S_SPACE[0]) * 11.0 * FPS))
def top_frame(t, nb5): return int(round(660 + (t - S_TOP[0]) / (S_TOP[1] - S_TOP[0]) * (nb5 - 660)))
def c3d_time(t): return C_T0 + (t - S_3D[0]) / (S_3D[1] - S_3D[0]) * (C_T1 - C_T0)
def isl_time(t): return (t - S_ISL[0]) / (S_ISL[1] - S_ISL[0]) * 17.0
if __name__ == '__main__':
    nb5 = n5(); N = int(round(T_END * FPS))
    sp = sorted({min(space_frame(n / FPS), 659) for n in range(N) if n / FPS < S_SPACE[1]})
    tp = sorted({top_frame(n / FPS, nb5) for n in range(N) if S_TOP[0] <= n / FPS < S_TOP[1]})
    open(os.path.join(WORK, 'short_frames_space.txt'), 'w').write(','.join(map(str, sp)))
    open(os.path.join(WORK, 'short_frames_top.txt'), 'w').write(','.join(map(str, tp)))
    print('bar %.4f s  drop %.3f s  music from %.3f s  Short %.2f s  n5 %d  space %d frames  top %d frames' % (BAR, DROP, M0, T_END, nb5, len(sp), len(tp)))
