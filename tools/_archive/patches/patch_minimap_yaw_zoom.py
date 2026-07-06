"""patch_minimap_yaw_zoom.py — YAW-FIX-V1 + MINIMAP-ZOOM-V3 (2026-07-05).

1. YAW-FIX-V1: the minimap rotation was `rotate(-yaw)`, but the stored yaw
   is COUNTER-clockwise (verified empirically: Prison yaw=281 points to
   real-world bearing 79deg, i.e. dir = 360-yaw). So heading-up needs
   `rotate(+yaw)`. This is the "yaw often inverted" you saw. Both call sites
   fixed.
2. MINIMAP-ZOOM-V3: radius 800 -> 600m (your preference, between tight and
   wide). Clears cached PNGs so it re-renders.

Restart server + hard refresh. Idempotent. Backup: .bak_yawzoom.
NOTE: if the heading now points DOWN instead of up, the sign is flipped the
other way — tell me and I'll invert it (it's a one-char change).
"""
import shutil, sys, os, glob, re
P = 'tools/calib.html'
s = open(P).read()
if 'YAW-FIX-V1' not in s:
    shutil.copy(P, P + '.bak_yawzoom')
    a = "minimapRotator.style.transform = `rotate(${-data.yaw}deg)`;"
    b = "minimapRotator.style.transform = `rotate(${data.yaw}deg)`;   /* [YAW-FIX-V1] stored yaw is CCW (dir = 360-yaw); +yaw points heading up */"
    assert a in s, 'anchor yaw 1'
    s = s.replace(a, b, 1)
    a2 = "if (!isNaN(yaw)) minimapRotator.style.transform = `rotate(${-yaw}deg)`;"
    b2 = "if (!isNaN(yaw)) minimapRotator.style.transform = `rotate(${yaw}deg)`;   /* [YAW-FIX-V1] */"
    assert a2 in s, 'anchor yaw 2'
    s = s.replace(a2, b2, 1)
    open(P, 'w').write(s)
    print('tools/calib.html: YAW-FIX-V1 (2 sites)')
else:
    print('calib: deja patche')

P = 'tools/server.py'
s = open(P).read()
if 'MINIMAP-ZOOM-V3' not in s:
    m = re.search(r'_MINIMAP_RADIUS_M = [\d.]+.*', s)
    assert m, 'anchor radius'
    s = s[:m.start()] + '_MINIMAP_RADIUS_M = 600.0  # [MINIMAP-ZOOM-V3] 600m' + s[m.end():]
    open(P, 'w').write(s)
    cache = os.path.join('tools', 'generated', 'minimaps')
    n = 0
    if os.path.isdir(cache):
        for f in glob.glob(os.path.join(cache, '*.png')):
            os.remove(f); n += 1
    print(f'tools/server.py: radius 600m, {n} cached cleared')
else:
    print('server: deja patche')
print('Applique. Restart server + hard refresh.')
