"""patch_minimap_stale_fix.py — MINIMAP-FIX-V2 (2026-07-05).

Switching cams still showed the WRONG (previous) minimap intermittently.
updateMinimap() read the global currentCam at fetch time, so a fast switch
(or out-of-order async cam-change handlers) could paint a stale cam. Now it:
  - takes the target cam explicitly (updateMinimap(currentCam))
  - re-checks targetCam === currentCam after EACH await (fetch + json)
  - verifies the server echoed the same cam (data.cam) before painting
Live-tested: slow switches all match; a 3-cam burst in 100ms ends on the
correct minimap. Requires MINIMAP-FIX-V1 chain. Idempotent. Backup: .bak_mmstale.
Hard refresh after (client-only).
"""
import shutil, sys
P = 'tools/calib.html'
s = open(P).read()
if 'MINIMAP-FIX-V2' in s:
    print('deja patche'); sys.exit(0)
assert 'MINIMAP-FIX-V1' in s, 'prerequis: MINIMAP-FIX-V1'
shutil.copy(P, P + '.bak_mmstale')
old = "async function updateMinimap() {\n  if (!minimapEnabled) {\n    minimapWrap.style.display = 'none';\n    return;\n  }\n  if (!currentCam) {\n    minimapWrap.style.display = 'block';\n    minimapBg.removeAttribute('src');\n    return;\n  }\n  minimapWrap.style.display = 'block';\n  const myToken = ++_minimapFetchToken;\n  try {\n    const res = await fetch('/api/minimap?cam=' + encodeURIComponent(currentCam));\n    if (myToken !== _minimapFetchToken) return;  // newer request superseded\n    if (!res.ok) {\n      console.warn('minimap fetch status', res.status);\n      return;\n    }\n    const data = await res.json();\n    if (myToken !== _minimapFetchToken) return;\n    if (data.error) {\n      console.warn('minimap error', data.error);\n      return;\n    }\n    minimapBg.src = 'data:image/png;base64,' + data.image_b64;\n    // Rotate so cam direction (yaw) points UP. Yaw 0 = north.\n    minimapRotator.style.transform = `rotate(${data.yaw}deg)`;   /* [YAW-FIX-V1] stored yaw is CCW (dir = 360-yaw); +yaw points heading up */\n  } catch (e) {\n    if (myToken === _minimapFetchToken) {\n      console.error('minimap fetch failed', e);\n    }\n  }\n}"
assert old in s, 'anchor updateMinimap'
s = s.replace(old, "async function updateMinimap(camArg) {\n  // [MINIMAP-FIX-V2] capture the target cam explicitly so a fast switch\n  // can't paint a stale cam. The token guards against out-of-order fetches;\n  // we ALSO verify the captured cam still matches currentCam before painting.\n  if (!minimapEnabled) {\n    minimapWrap.style.display = 'none';\n    return;\n  }\n  const targetCam = camArg || currentCam;\n  if (!targetCam) {\n    minimapWrap.style.display = 'block';\n    minimapBg.removeAttribute('src');\n    return;\n  }\n  minimapWrap.style.display = 'block';\n  const myToken = ++_minimapFetchToken;\n  try {\n    const res = await fetch('/api/minimap?cam=' + encodeURIComponent(targetCam));\n    if (myToken !== _minimapFetchToken) return;        // superseded by a newer call\n    if (targetCam !== currentCam) return;              // user moved on since we fired\n    if (!res.ok) { console.warn('minimap fetch status', res.status); return; }\n    const data = await res.json();\n    if (myToken !== _minimapFetchToken) return;\n    if (targetCam !== currentCam) return;              // re-check after await\n    if (data.error) { console.warn('minimap error', data.error); return; }\n    if (data.cam && data.cam !== currentCam) return;   // server echoed a different cam\n    minimapBg.src = 'data:image/png;base64,' + data.image_b64;\n    minimapRotator.style.transform = `rotate(${data.yaw}deg)`;   /* [YAW-FIX-V1] */\n  } catch (e) {\n    if (myToken === _minimapFetchToken) console.error('minimap fetch failed', e);\n  }\n}", 1)
old = "  if (typeof updateMinimap === 'function') updateMinimap();   // [MINIMAP-FIX-V1] was never called on direct cam change -> stale minimap"
assert old in s, 'anchor call'
s = s.replace(old, "  if (typeof updateMinimap === 'function') updateMinimap(currentCam);   // [MINIMAP-FIX-V2] pass cam explicitly", 1)
open(P, 'w').write(s)
print('MINIMAP-FIX-V2 applique. Hard refresh.')
