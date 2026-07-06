"""patch_minimap_zoom.py — MINIMAP-ZOOM-V1 (2026-07-05).

Camera-view minimap was cropped at a 350m radius — quite tight. Bumped to
600m so more context around the cam is visible. Still zoom z=5 (600 source
px -> 480 output, sharp). The endpoint re-renders on demand; this patch also
clears the cached minimap PNGs so the new radius takes effect immediately.
Idempotent. Backup: .bak_minizoom. Restart server after (server-side change).
"""
import shutil, sys, os, glob
P = 'tools/server.py'
s = open(P).read()
if 'MINIMAP-ZOOM-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_minizoom')
old = '_MINIMAP_RADIUS_M = 350.0'
assert old in s, 'anchor radius introuvable'
s = s.replace(old, '_MINIMAP_RADIUS_M = 600.0  # [MINIMAP-ZOOM-V1] was 350 — zoomed out for more context around the cam', 1)
open(P, 'w').write(s)

# vider le cache pour forcer le re-render au nouveau zoom
cache = os.path.join('tools', 'generated', 'minimaps')
n = 0
if os.path.isdir(cache):
    for f in glob.glob(os.path.join(cache, '*.png')):
        os.remove(f); n += 1
print(f'radius 350 -> 600m, {n} minimaps en cache supprimees')
print('MINIMAP-ZOOM-V1 applique. Redemarre le serveur.')
