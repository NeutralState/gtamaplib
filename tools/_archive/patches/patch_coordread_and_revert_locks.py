"""patch_coordread_and_revert_locks.py — COORDREAD-V1 + lock revert (2026-07-06).

Three things:
1. Reverts the two useless server locks (MINIMAP-THREADLOCK-V1 +
   GETCAM-THREADSAFE-V1) — they were a wrong theory for the minimap bug
   (real fix was MINIMAP-DEDUP-V1, client-side). Harmless but dead code.
2. Adds COORDREAD-V1: a discreet live X/Y world-coordinate readout in the
   bottom-right of Map view, updating as the cursor moves. Fades in on hover,
   out on leave. Verified accurate against a known cam position.
   (The Island W (N) z=0.12 -> 0.0 CI fix is a data change, applied separately
   via the command in the chat — landmarks.json.)

Idempotent. Backups: .bak_coordrevert_*. Restart server (server changed) +
hard refresh.
"""
import shutil, sys

# ---- server.py: revert locks ----
P = 'tools/server.py'
s = open(P).read()
if 'MINIMAP-THREADLOCK-V1' in s or 'GETCAM-THREADSAFE-V1' in s:
    shutil.copy(P, P + '.bak_coordrevert_srv')
    # GETCAM wrapper
    if '# [GETCAM-THREADSAFE-V1]' in s:
        i = s.index('\n# [GETCAM-THREADSAFE-V1]')
        j = s.index('ml.get_camera = _get_camera_locked', i) + len('ml.get_camera = _get_camera_locked')
        end = s.index('\n', j)
        s = s.replace(s[i:end], '', 1)
    # MINIMAP lock decl
    if '# [MINIMAP-THREADLOCK-V1] ml.get_camera' in s:
        i = s.index('\n# [MINIMAP-THREADLOCK-V1] ml.get_camera')
        j = s.index('_MINIMAP_LOCK = threading.Lock()', i) + len('_MINIMAP_LOCK = threading.Lock()')
        s = s.replace(s[i:j], '', 1)
    # endpoint acquire/release
    s = s.replace("""            # [MINIMAP-THREADLOCK-V1] hold the lock across get_camera +
            # cache-path + render + read, so concurrent requests can't corrupt
            # the lru_cache or read a file mid-write.
            _MINIMAP_LOCK.acquire()
            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                _MINIMAP_LOCK.release()
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return
            cache_path = _minimap_cache_path(cam_name)""",
        """            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return
            cache_path = _minimap_cache_path(cam_name)""", 1)
    s = s.replace("""            if not os.path.exists(cache_path):
                _MINIMAP_LOCK.release()
                self.send_json({'error': 'minimap render failed'}, 500)
                return""",
        """            if not os.path.exists(cache_path):
                self.send_json({'error': 'minimap render failed'}, 500)
                return""", 1)
    s = s.replace("""            except Exception as e:
                self.send_json({'error': f'minimap read failed: {e}'}, 500)
            finally:
                try:
                    _MINIMAP_LOCK.release()
                except RuntimeError:
                    pass   # already released on an error path""",
        """            except Exception as e:
                self.send_json({'error': f'minimap read failed: {e}'}, 500)""", 1)
    open(P, 'w').write(s)
    print('server.py: locks reverted')
else:
    print('server.py: deja sans locks')

# ---- calib.html: add COORDREAD-V1 ----
P = 'tools/calib.html'
s = open(P).read()
if 'COORDREAD-V1' in s:
    print('calib.html: COORDREAD deja present'); sys.exit(0)
shutil.copy(P, P + '.bak_coordrevert_cal')

html_anchor = '''  <div class="map-svg-wrap" id="map-svg-wrap"></div>
    <div class="map-loading" id="map-loading">Loading yanis map…</div>'''
assert html_anchor in s, 'anchor html'
s = s.replace(html_anchor, html_anchor + '\n' + '    <!-- [COORDREAD-V1] live cursor world coordinates -->\n    <div class="map-coordread" id="map-coordread"></div>', 1)

css_anchor = '.map-health{position:absolute'
assert css_anchor in s, 'anchor css'
s = s.replace(css_anchor, '.map-coordread{position:absolute;right:10px;bottom:10px;z-index:30;background:rgba(10,10,13,.55);backdrop-filter:blur(5px);border-radius:8px;padding:4px 10px;font:11px ui-monospace,monospace;color:#8a8a94;pointer-events:none;letter-spacing:.02em;white-space:nowrap;opacity:0;transition:opacity .12s}\n.map-coordread.show{opacity:1}\n' + css_anchor, 1)

js_anchor = '''    window.mapTx = { scale: ns, tx: ntx, ty: nty };
    applyMapTx();
  }, { passive: false });'''
assert js_anchor in s, 'anchor js'
s = s.replace(js_anchor, js_anchor + "\n  // [COORDREAD-V1] live cursor world X/Y readout in map view.\n  (() => {\n    const readEl = document.getElementById('map-coordread');\n    if (!readEl) return;\n    mapView.addEventListener('mousemove', e => {\n      if (window.currentView !== 'map' || !window.mapImg || !window.mapTx || !window.svgToWorld) {\n        readEl.classList.remove('show'); return;\n      }\n      const rect = mapView.getBoundingClientRect();\n      const { scale, tx, ty } = window.mapTx;\n      // screen -> svg (inverse of applyMapTx: screen = svg*scale + t)\n      const svgX = (e.clientX - rect.left - tx) / scale;\n      const svgY = (e.clientY - rect.top  - ty) / scale;\n      const [wx, wy] = window.svgToWorld(svgX, svgY);\n      readEl.textContent = `X ${wx.toFixed(1)}   Y ${wy.toFixed(1)}`;\n      readEl.classList.add('show');\n    });\n    mapView.addEventListener('mouseleave', () => readEl.classList.remove('show'));\n  })();", 1)
open(P, 'w').write(s)
print('calib.html: COORDREAD-V1 added')
print('Done. Restart server + hard refresh.')
