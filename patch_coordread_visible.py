"""patch_coordread_visible.py — COORDREAD-V2 (2026-07-06).

The coord readout from V1 was hidden: it sat at bottom-right, underneath the
full-width map legend bar (which occupies the bottom ~44px). Moved to the
TOP-RIGHT corner of the map (clear area), made it more visible (green accent,
higher base opacity, subtle border), and it now shows a "X — Y —" placeholder
as soon as you enter Map view so it's easy to find; it fills with live coords
on cursor move.

Requires COORDREAD-V1. Idempotent. Backup: .bak_coordv2. Hard refresh.
"""
import shutil, sys
P = 'tools/calib.html'
s = open(P).read()
if 'COORDREAD-V2' not in s and 'top:10px;z-index:31' in s:
    print('deja en V2 (repositionne)'); sys.exit(0)
if 'COORDREAD-V1' not in s:
    print('ERREUR: COORDREAD-V1 requis d abord'); sys.exit(1)
shutil.copy(P, P + '.bak_coordv2')

old_css = '.map-coordread{position:absolute;right:10px;bottom:10px;z-index:30;background:rgba(10,10,13,.55);backdrop-filter:blur(5px);border-radius:8px;padding:4px 10px;font:11px ui-monospace,monospace;color:#8a8a94;pointer-events:none;letter-spacing:.02em;white-space:nowrap;opacity:0;transition:opacity .12s}'
new_css = '/* [COORDREAD-V2] top-right, visible */ .map-coordread{position:absolute;right:10px;top:10px;z-index:31;background:rgba(10,10,13,.72);backdrop-filter:blur(6px);border:1px solid #2c2c33;border-radius:8px;padding:5px 11px;font:11px ui-monospace,monospace;color:#4ade80;pointer-events:none;letter-spacing:.03em;white-space:nowrap;opacity:.55;transition:opacity .12s}'
assert old_css in s, 'anchor css V1'
s = s.replace(old_css, new_css, 1)

old_html = '<div class="map-coordread" id="map-coordread"></div>'
new_html = '<div class="map-coordread" id="map-coordread">X \u2014  Y \u2014</div>'
assert old_html in s, 'anchor html V1'
s = s.replace(old_html, new_html, 1)
open(P, 'w').write(s)
print('COORDREAD-V2 applique. Hard refresh.')
