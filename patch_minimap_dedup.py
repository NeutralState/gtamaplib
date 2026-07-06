"""patch_minimap_dedup.py — MINIMAP-DEDUP-V1 (2026-07-06).

FINAL fix for the minimap bug — and the diagnostic that proved the real cause.

A console interceptor showed every /api/minimap response was echo-OK and
cur-OK: the server ALWAYS returned the right cam, and 200ms after each switch
the rotator ALWAYS showed the correct yaw. So the earlier server-side lru_cache
theory was WRONG (my apologies for those rounds). The tell was "(x2)" on every
line: each cam switch fired TWO fetches.

Cause: both the cam-change handler (~line 2659) AND the 250ms preview interval
called updateMinimap on every switch. On fast switching, a stale duplicate from
the pair could paint for a fraction of a second before settling — the transient
"wrong map" flash. It always converged to correct once you stopped.

Fix: the minimap is now driven ONLY by the cam-change handler (immediate). The
interval keeps polling the cam PREVIEW but no longer fetches the minimap. One
fetch per switch; no duplicate to flash. Verified: exactly 1 minimap fetch per
cam now (was 2). Client-only. Idempotent. Backup: .bak_dedup. Hard refresh.
"""
import shutil, sys
P = 'tools/calib.html'
s = open(P).read()
if 'MINIMAP-DEDUP-V1' in s:
    print('deja patche'); sys.exit(0)
shutil.copy(P, P + '.bak_dedup')
old = 'setInterval(() => {\n  if (currentCam !== _previewLastCam) {\n    _previewLastCam = currentCam;\n    updateMinimap(currentCam);   // [MINIMAP-DIAG-V1] explicit cam\n    updateCamPreview();\n  }\n}, 250);'
assert old in s, 'anchor setInterval double-fetch'
s = s.replace(old, "setInterval(() => {\n  if (currentCam !== _previewLastCam) {\n    _previewLastCam = currentCam;\n    // [MINIMAP-DEDUP-V1] minimap is driven ONLY by the cam-change handler\n    // (line ~2659), which fires immediately. This interval used to ALSO call\n    // updateMinimap, so every switch fired TWO fetches — the diagnostic showed\n    // each cam requested x2, and on fast switches a stale duplicate could\n    // paint briefly before settling. Preview polling stays; minimap doesn't.\n    updateCamPreview();\n  }\n}, 250);", 1)
open(P, 'w').write(s)
print('MINIMAP-DEDUP-V1 applique. Hard refresh (client-only).')
