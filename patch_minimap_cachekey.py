"""patch_minimap_cachekey.py — MINIMAP-CACHEKEY-V1 + MINIMAP-ATOMIC-V1 (2026-07-05).

ROOT CAUSE of "some cams show another cam's map": the disk cache filename was
keyed by cam NAME only. If a cam's cached PNG was ever wrong/stale (e.g.
rendered at an old position, or a race during first render), it was served
forever — no client guard could fix a bad file on disk.

Fix (server): the cache filename now includes the cam's position + yaw +
radius. A different pose => a different file, so a cam can NEVER serve
another cam's crop or a stale one. Old caches are cleared by this patch.

Fix (client): image is preloaded, then image + rotation applied together
with a final cam-match check right before painting (atomic). The diagnostic
label on the minimap is REMOVED.

NOTE: I could not reproduce the bug in-sandbox (map tiles aren't present
here, so every render falls back to the same blank background). The cache-key
fix is a structural guarantee that holds regardless. Restart server + hard
refresh. Idempotent. Backups: .bak_cachekey.
"""
import shutil, sys, os, glob
P = 'tools/server.py'
s = open(P).read()
if 'MINIMAP-CACHEKEY-V1' not in s:
    shutil.copy(P, P + '.bak_cachekey')
    old = "def _minimap_cache_path(cam_name):\n    return os.path.join(_MINIMAP_CACHE_DIR, f'{_minimap_safe_name(cam_name)}.png')"
    assert old in s, 'anchor _minimap_cache_path'
    s = s.replace(old, "def _minimap_cache_path(cam_name):\n    # [MINIMAP-CACHEKEY-V1] include position+yaw+radius in the filename so a\n    # cam that moved (or the radius changing) can NEVER serve a stale/other\n    # cam's cached crop — a different pose => a different file, period.\n    try:\n        cam = ml.get_camera(cam_name)\n        if cam.xyz is not None:\n            key = f'{cam.xyz[0]:.0f}_{cam.xyz[1]:.0f}_{float(cam.ypr[0]):.0f}_{int(_MINIMAP_RADIUS_M)}'\n        else:\n            key = 'noxyz'\n    except Exception:\n        key = 'err'\n    return os.path.join(_MINIMAP_CACHE_DIR, f'{_minimap_safe_name(cam_name)}__{key}.png')\n".rstrip(chr(10)), 1)
    open(P, 'w').write(s)
    # clear ALL old caches (name scheme changed)
    cache = os.path.join('tools', 'generated', 'minimaps')
    n = 0
    if os.path.isdir(cache):
        for f in glob.glob(os.path.join(cache, '*.png')):
            os.remove(f); n += 1
    print(f'server: MINIMAP-CACHEKEY-V1, {n} old caches cleared')
else:
    print('server: deja patche')

P = 'tools/calib.html'
s = open(P).read()
if 'MINIMAP-ATOMIC-V1' not in s:
    shutil.copy(P, P + '.bak_cachekey_calib')
    old = "    minimapBg.src = 'data:image/png;base64,' + data.image_b64;\n    minimapRotator.style.transform = `rotate(${data.yaw}deg)`;   /* [YAW-FIX-V1] */\n    // label overlay so you can SEE which cam the minimap is showing\n    let _lbl = document.getElementById('minimap-diag-label');\n    if (!_lbl) {\n      _lbl = document.createElement('div');\n      _lbl.id = 'minimap-diag-label';\n      _lbl.style.cssText = 'position:absolute;bottom:2px;left:2px;right:2px;z-index:20;'\n        + 'font:9px/1.2 JetBrains Mono,monospace;color:#4ade80;background:#000a;'\n        + 'padding:1px 4px;border-radius:3px;pointer-events:none;text-align:center;'\n        + 'white-space:nowrap;overflow:hidden;text-overflow:ellipsis';\n      minimapWrap.appendChild(_lbl);\n    }\n    _lbl.textContent = (data.cam || targetCam) + '  ·  yaw ' + Math.round(data.yaw);\n    console.log('[MINIMAP-DIAG] painted', data.cam || targetCam, '(currentCam:', currentCam + ')');\n"
    assert old in s, 'anchor client paint'
    s = s.replace(old, "    // [MINIMAP-ATOMIC-V1] preload the image, then apply image + rotation\n    // together, with a FINAL cam check right before painting — so a stale\n    // response can never land on the wrong cam. No label (removed).\n    const imgSrc = 'data:image/png;base64,' + data.image_b64;\n    const yawDeg = data.yaw;\n    await new Promise((resolve) => {\n      const pre = new Image();\n      pre.onload = pre.onerror = resolve;\n      pre.src = imgSrc;\n    });\n    if (myToken !== _minimapFetchToken) return;        // superseded during preload\n    if (targetCam !== currentCam) return;              // cam changed during preload\n    minimapBg.src = imgSrc;\n    minimapRotator.style.transform = `rotate(${yawDeg}deg)`;   /* [YAW-FIX-V1] */\n", 1)
    open(P, 'w').write(s)
    print('client: MINIMAP-ATOMIC-V1 (atomic paint, label removed)')
else:
    print('client: deja patche')
print('Applique. Restart server + hard refresh.')
