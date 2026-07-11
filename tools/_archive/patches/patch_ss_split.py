#!/usr/bin/env python3
# SS-SPLIT-V1 (2026-07-10): l'UI distingue les deux vagues de screenshots.
# - badge du header: "Screenshot 1" (violet) / "Screenshot 2" (fuchsia)
#   au lieu du generique "Screenshot"
# - pilules de filtre de la liste de cams: SS scinde en S1 / S2
# S'appuie sur les tags SCREENSHOT-TAGS (0d0b1a0) du champ source. Le
# fallback 'screenshots' reste pour toute cam future non taguee. Idempotent.
import sys
p = 'tools/calib.html'
src = open(p).read()
if 'SS-SPLIT-V1' in src:
    print('ok  deja patche'); sys.exit(0)
E = []
o = """  if (src.startsWith('Trailer')) return 'Trailer 2'; // fallback to T2 group
  return 'screenshots';
}"""
n = """  if (src.startsWith('Trailer')) return 'Trailer 2'; // fallback to T2 group
  if (src.startsWith('Screenshot 1')) return 'Screenshot 1';   // [SS-SPLIT-V1]
  if (src.startsWith('Screenshot 2')) return 'Screenshot 2';
  return 'screenshots';
}"""
assert o in src, 'ancre getCamType'; src = src.replace(o, n, 1); E.append('getCamType')
o = "const camFilters = { 'LEAK': true, 'Trailer 1': true, 'Trailer 2': true, 'screenshots': true };"
n = "const camFilters = { 'LEAK': true, 'Trailer 1': true, 'Trailer 2': true, 'Screenshot 1': true, 'Screenshot 2': true, 'screenshots': true }; // [SS-SPLIT-V1]"
assert o in src, 'ancre camFilters'; src = src.replace(o, n, 1); E.append('camFilters')
o = '        <button class="cam-filter-chip on" data-type="screenshots">SS</button>'
n = """        <button class="cam-filter-chip on" data-type="Screenshot 1">S1</button><!-- [SS-SPLIT-V1] -->
        <button class="cam-filter-chip on" data-type="Screenshot 2">S2</button>"""
assert o in src, 'ancre chip SS'; src = src.replace(o, n, 1); E.append('chips S1/S2')
o = '.cam-filter-chip[data-type=screenshots].on{border-color:var(--purple);color:var(--purple)}'
n = """.cam-filter-chip[data-type=screenshots].on{border-color:var(--purple);color:var(--purple)}
.cam-filter-chip[data-type="Screenshot 1"].on{border-color:var(--purple);color:var(--purple)} /* [SS-SPLIT-V1] */
.cam-filter-chip[data-type="Screenshot 2"].on{border-color:#e879f9;color:#e879f9}"""
assert o in src, 'ancre CSS chip'; src = src.replace(o, n, 1); E.append('CSS chips')
o = """    const src = cam.source || '';
    let t = 'Screenshot';
    if (src.startsWith('Trailer 1')) t = 'Trailer 1';
    else if (src.startsWith('Trailer')) t = 'Trailer 2';
    el.textContent = t;
    if (t === 'Trailer 1') { el.style.color='var(--blue)'; el.style.borderColor='var(--blue)'; }
    else if (t === 'Trailer 2') { el.style.color='var(--green)'; el.style.borderColor='var(--green)'; }
    else { el.style.color='var(--violet)'; el.style.borderColor='var(--violet)'; }"""
n = """    const src = cam.source || '';
    let t = 'Screenshot';
    if (src.startsWith('Trailer 1')) t = 'Trailer 1';
    else if (src.startsWith('Trailer')) t = 'Trailer 2';
    else if (src.startsWith('Screenshot 1')) t = 'Screenshot 1';   // [SS-SPLIT-V1]
    else if (src.startsWith('Screenshot 2')) t = 'Screenshot 2';
    el.textContent = t;
    if (t === 'Trailer 1') { el.style.color='var(--blue)'; el.style.borderColor='var(--blue)'; }
    else if (t === 'Trailer 2') { el.style.color='var(--green)'; el.style.borderColor='var(--green)'; }
    else if (t === 'Screenshot 2') { el.style.color='#e879f9'; el.style.borderColor='#e879f9'; }
    else { el.style.color='var(--violet)'; el.style.borderColor='var(--violet)'; }"""
assert o in src, 'ancre badge'; src = src.replace(o, n, 1); E.append('badge')
open(p, 'w').write(src)
print('EDIT calib.html 5/5:', ', '.join(E))
