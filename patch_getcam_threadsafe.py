"""patch_getcam_threadsafe.py — GETCAM-THREADSAFE-V1 (2026-07-06).

Follow-up to MINIMAP-THREADLOCK-V1. That patch locked only the /api/minimap
endpoint, but the field log proved the bug persisted: cams STILL received
another cam's byte-identical image (e.g. Auto Shop (NW) got Ambrosia Postcard's
imgLen=283150; Beach Gym got Backyard's 126762).

Reason: ml.get_camera (functools.lru_cache, NOT thread-safe) is called from
MANY endpoints concurrently (minimap, project, save, colors, ...), and several
paths call ml.get_camera.cache_clear() mid-flight. Locking one endpoint can't
protect a cache that every other endpoint also hammers. Under contention the
lru_cache hands back the wrong cam object -> wrong minimap file path -> a cam
serves another cam's exact image + yaw.

Fix: wrap ml.get_camera ONCE, at import time, behind a reentrant lock, so every
call site everywhere is serialized. cache_clear / cache_info are preserved.

NOTE: still not reproducible in-sandbox (map tiles absent here, so rendering is
too fast to open the race window), but this addresses the proven root cause at
its source rather than one endpoint. Server-side: restart the server, then
verify visually. Idempotent. Backup: .bak_getcam.
"""
import shutil, sys
P = 'tools/server.py'
s = open(P).read()
if 'GETCAM-THREADSAFE-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_getcam')
if 'import threading' not in s:
    s = s.replace("import json\nimport math", "import json\nimport math\nimport threading", 1)
# inject right after the second 'import gtamaplib as ml'
anchor = "import gtamaplib as ml\nimport gtamapdata as md"
if anchor in s:
    at = s.index(anchor) + len(anchor) + 1
else:
    first = s.index("import gtamaplib as ml")
    second = s.index("import gtamaplib as ml", first + 1)
    at = s.index("\n", second) + 1
s = s[:at] + "\n# [GETCAM-THREADSAFE-V1] ml.get_camera is functools.lru_cache — NOT thread-safe.\n# The server is a ThreadingHTTPServer and many endpoints (minimap, project,\n# save, etc.) call get_camera concurrently, while some call cache_clear().\n# Under contention the lru_cache returns the WRONG cam's object (proven: a cam\n# served another cam's byte-identical minimap). Wrap it once, here, so EVERY\n# call site is serialized behind a single reentrant lock. cache_clear/cache_info\n# are preserved for the code that uses them.\nimport threading as _threading\n_GETCAM_LOCK = _threading.RLock()\n_ml_get_camera_orig = ml.get_camera\ndef _get_camera_locked(*a, **k):\n    with _GETCAM_LOCK:\n        return _ml_get_camera_orig(*a, **k)\n_get_camera_locked.cache_clear = _ml_get_camera_orig.cache_clear\n_get_camera_locked.cache_info = _ml_get_camera_orig.cache_info\nml.get_camera = _get_camera_locked\n" + "\n" + s[at:]
open(P, 'w').write(s)
print('GETCAM-THREADSAFE-V1 applique. Restart the server.')
