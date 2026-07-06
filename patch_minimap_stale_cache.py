"""patch_minimap_stale_cache.py — MINIMAP-STALE-V1 (2026-07-05).

THE actual "wrong minimap on certain cams" bug. The minimap PNG cache was
only rendered when the file was ABSENT (`if not os.path.exists`). So once a
cam's minimap existed, moving or recalibrating that cam never re-centered it
— the cache stayed on the OLD position forever. "Certain cams" = exactly the
ones you had repositioned (GSC, Rooftop, GSC SE, etc.).

Fix: re-render when cameras.json is newer than the cached PNG — the freshness
rule the module comment always claimed but the lazy-render refactor had
dropped. Verified: touching cameras.json triggers a re-render on next fetch.

This is server-side and complements MINIMAP-FIX-V2 (client race guard). Both
are needed: V2 stops fast-switch races, this stops stale-position caches.
Restart server after. Idempotent. Backup: .bak_mmstalecache.
"""
import shutil, sys
P = 'tools/server.py'
s = open(P).read()
if 'MINIMAP-STALE-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_mmstalecache')
old = '            cache_path = _minimap_cache_path(cam_name)\n            if not os.path.exists(cache_path):\n                # Render on demand (fallback for any cam added after startup).\n                try:\n                    _render_minimap_for_cam(cam_name)\n                except Exception:\n                    pass'
assert old in s, 'anchor cache render'
s = s.replace(old, "            cache_path = _minimap_cache_path(cam_name)\n            # [MINIMAP-STALE-V1] The cache was only rendered when the file was\n            # ABSENT — so moving/recalibrating a cam left its minimap centered\n            # on the OLD position forever. Re-render when cameras.json is newer\n            # than the cached PNG (the freshness rule the comment always claimed\n            # but the code had lost in the lazy-render refactor).\n            _cam_json = os.path.join(DATA_DIR, 'cameras.json')\n            _stale = False\n            try:\n                if os.path.exists(cache_path) and os.path.exists(_cam_json):\n                    _stale = os.path.getmtime(_cam_json) > os.path.getmtime(cache_path)\n            except OSError:\n                _stale = True\n            if not os.path.exists(cache_path) or _stale:\n                try:\n                    _render_minimap_for_cam(cam_name)\n                except Exception:\n                    pass", 1)
open(P, 'w').write(s)
print('MINIMAP-STALE-V1 applique. Restart server.')
