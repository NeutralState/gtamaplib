"""patch_minimap_yaw_sync.py — MINIMAP-DIAG-V1 (2026-07-05).

The residual "certain cams show wrong map" was a YAW/image desync, not the
image itself: a setInterval polled updateMinimap() with NO cam argument,
racing the direct cam-change handler. Whichever fetch resolved last won, so
the rotation could lag one cam behind (image right, orientation stale) —
which reads as a wrong minimap.

Fixes:
  - setInterval now passes currentCam explicitly (both paths capture the
    same target, so the stale-guards actually engage)
  - cache-buster (&_t=) on the fetch URL defeats any HTTP-level caching
  - a small green label on the minimap shows the painted cam + yaw, and a
    [MINIMAP-DIAG] console line logs each paint (keep it — handy; harmless)

Live-tested: 5 consecutive switches incl. repeats, image AND rotation match
the cam every time. Requires MINIMAP-FIX-V2. Idempotent. Backup: .bak_yawsync.
Hard refresh (client-only).
"""
import shutil, sys
P = 'tools/calib.html'
s = open(P).read()
if 'MINIMAP-DIAG-V1' in s:
    print('deja patche'); sys.exit(0)
assert 'MINIMAP-FIX-V2' in s, 'prerequis: MINIMAP-FIX-V2'
shutil.copy(P, P + '.bak_yawsync')
old = "    const res = await fetch('/api/minimap?cam=' + encodeURIComponent(targetCam));\n    if (myToken !== _minimapFetchToken) return;        // superseded by a newer call\n    if (targetCam !== currentCam) return;              // user moved on since we fired\n    if (!res.ok) { console.warn('minimap fetch status', res.status); return; }\n    const data = await res.json();\n    if (myToken !== _minimapFetchToken) return;\n    if (targetCam !== currentCam) return;              // re-check after await\n    if (data.error) { console.warn('minimap error', data.error); return; }\n    if (data.cam && data.cam !== currentCam) return;   // server echoed a different cam\n    minimapBg.src = 'data:image/png;base64,' + data.image_b64;\n    minimapRotator.style.transform = `rotate(${data.yaw}deg)`;   /* [YAW-FIX-V1] */"
assert old in s, 'anchor fetch'
s = s.replace(old, "    // [MINIMAP-DIAG-V1] cache-buster defeats any HTTP caching of this URL\n    const res = await fetch('/api/minimap?cam=' + encodeURIComponent(targetCam) + '&_t=' + Date.now());\n    if (myToken !== _minimapFetchToken) return;        // superseded by a newer call\n    if (targetCam !== currentCam) return;              // user moved on since we fired\n    if (!res.ok) { console.warn('minimap fetch status', res.status); return; }\n    const data = await res.json();\n    if (myToken !== _minimapFetchToken) return;\n    if (targetCam !== currentCam) return;              // re-check after await\n    if (data.error) { console.warn('minimap error', data.error); return; }\n    if (data.cam && data.cam !== currentCam) {\n      console.warn('[MINIMAP-DIAG] server echoed', data.cam, 'but currentCam is', currentCam, '- skipping');\n      return;\n    }\n    minimapBg.src = 'data:image/png;base64,' + data.image_b64;\n    minimapRotator.style.transform = `rotate(${data.yaw}deg)`;   /* [YAW-FIX-V1] */\n    // label overlay so you can SEE which cam the minimap is showing\n    let _lbl = document.getElementById('minimap-diag-label');\n    if (!_lbl) {\n      _lbl = document.createElement('div');\n      _lbl.id = 'minimap-diag-label';\n      _lbl.style.cssText = 'position:absolute;bottom:2px;left:2px;right:2px;z-index:20;'\n        + 'font:9px/1.2 JetBrains Mono,monospace;color:#4ade80;background:#000a;'\n        + 'padding:1px 4px;border-radius:3px;pointer-events:none;text-align:center;'\n        + 'white-space:nowrap;overflow:hidden;text-overflow:ellipsis';\n      minimapWrap.appendChild(_lbl);\n    }\n    _lbl.textContent = (data.cam || targetCam) + '  ·  yaw ' + Math.round(data.yaw);\n    console.log('[MINIMAP-DIAG] painted', data.cam || targetCam, '(currentCam:', currentCam + ')');\n", 1)
old = '  if (currentCam !== _previewLastCam) {\n    _previewLastCam = currentCam;\n    updateMinimap();\n    updateCamPreview();\n  }'
assert old in s, 'anchor setInterval'
s = s.replace(old, '  if (currentCam !== _previewLastCam) {\n    _previewLastCam = currentCam;\n    updateMinimap(currentCam);   // [MINIMAP-DIAG-V1] explicit cam\n    updateCamPreview();\n  }', 1)
open(P, 'w').write(s)
print('MINIMAP-DIAG-V1 applique. Hard refresh.')
