"""patch_minimap_threadlock.py — MINIMAP-THREADLOCK-V1 (2026-07-06).

*** ROOT CAUSE, confirmed from a real-machine console log. ***

A cam sometimes showed ANOTHER cam's minimap — and the diagnostic proved it
was the *exact* image: e.g. "Amphitheater" received imgLen=355014, byte-for-byte
identical to "Auto Shop (NW)", same yaw too. That can't be a client race (the
client asked for Amphitheater and got a whole Auto-Shop-NW blob) — the SERVER
returned the wrong cam's response.

Why: ml.get_camera is decorated with functools.lru_cache, which is NOT
thread-safe under contention. The server is a ThreadingHTTPServer, so fast
cam-switching fires concurrent /api/minimap requests. Parallel get_camera()
calls corrupt the lru_cache and hand back a DIFFERENT cam's camera object;
_minimap_cache_path() then builds the wrong cam's file path, and that cam's
PNG + yaw get served. This is exactly the "wrong map every 4-5 cams" bug, and
why NO client-side guard could fix it — the bytes were already wrong.

Fix: serialize the whole /api/minimap endpoint (get_camera + cache-path +
render + file read) behind a single threading.Lock. One minimap resolved at a
time; the lru_cache can no longer be raced.

NOTE: I could NOT reproduce this in-sandbox (map tiles aren't present here, so
rendering short-circuits and the race window basically vanishes). The fix
follows directly from the console evidence + the lru_cache being non
thread-safe. It's server-side: restart the server, then verify visually.

Idempotent. Backup: .bak_threadlock.
"""
import shutil, sys, re
P = 'tools/server.py'
s = open(P).read()
if 'MINIMAP-THREADLOCK-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_threadlock')

# 1. import threading
if 'import threading' not in s:
    s = s.replace("import json\nimport math", "import json\nimport math\nimport threading", 1)

# 2. lock declaration after cache dir
old_dir = "_MINIMAP_CACHE_DIR = os.path.join(TOOL_DIR, 'generated', 'minimaps')"
assert old_dir in s, 'anchor cache dir'
s = s.replace(old_dir, old_dir + "\n" + "# [MINIMAP-THREADLOCK-V1] ml.get_camera is @lru_cache — NOT thread-safe.\n# ThreadingHTTPServer runs /api/minimap concurrently, so parallel calls\n# corrupted the lru_cache and returned another cam's camera object, making\n# _minimap_cache_path point at the WRONG file — a cam served another cam's\n# exact image+yaw. Serialize the whole minimap endpoint behind one lock.\n_MINIMAP_LOCK = threading.Lock()", 1)

# 3. acquire at endpoint start
old_start = """            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return
            cache_path = _minimap_cache_path(cam_name)"""
new_start = """            # [MINIMAP-THREADLOCK-V1] hold the lock across get_camera +
            # cache-path + render + read, so concurrent requests can't corrupt
            # the lru_cache or read a file mid-write.
            _MINIMAP_LOCK.acquire()
            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                _MINIMAP_LOCK.release()
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return
            cache_path = _minimap_cache_path(cam_name)"""
assert old_start in s, 'anchor endpoint start'
s = s.replace(old_start, new_start, 1)

# 4. release on the render-failed path
old_500 = """            if not os.path.exists(cache_path):
                self.send_json({'error': 'minimap render failed'}, 500)
                return"""
new_500 = """            if not os.path.exists(cache_path):
                _MINIMAP_LOCK.release()
                self.send_json({'error': 'minimap render failed'}, 500)
                return"""
assert old_500 in s, 'anchor 500'
s = s.replace(old_500, new_500, 1)

# 5. finally-release after the send block
send_anchor = "except Exception as e:\n                self.send_json({'error': f'minimap read failed: {e}'}, 500)"
idx = s.index("try:\n                with open(cache_path, 'rb') as f:")
exc_idx = s.index(send_anchor, idx)
end_idx = s.index('\n', exc_idx + len(send_anchor))
block = s[idx:end_idx]
new_block = block + "\n            finally:\n                try:\n                    _MINIMAP_LOCK.release()\n                except RuntimeError:\n                    pass   # already released on an error path"
s = s[:idx] + new_block + s[end_idx:]

open(P, 'w').write(s)
print('MINIMAP-THREADLOCK-V1 applique. Restart the server.')
