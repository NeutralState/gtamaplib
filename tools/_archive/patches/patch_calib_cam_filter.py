#!/usr/bin/env python3
"""
patch_calib_cam_filter.py — Adds search + type filter to the cam selector
in calib.html. Approach: keep the native <select> for compatibility with
existing code (selectSuspicious dispatches change events on it), but hide
it and overlay a custom search/filter UI that programmatically updates it.

Run from gtamaplib-main/:
    python3 tools/patch_calib_cam_filter.py
"""
import os
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'tools' \
    else os.path.dirname(os.path.abspath(__file__))

HTML_PATH = os.path.join(GTAMAP_DIR, 'tools', 'calib.html')

with open(HTML_PATH) as f:
    content = f.read()

if 'cam-search' in content:
    print("• Cam search/filter already patched")
    sys.exit(0)

# ── 1. Add CSS for the new search + filter UI ─────────────────────────────────
NEW_CSS = """
/* Cam search + filter */
.cam-picker{position:relative;display:flex;align-items:center;gap:6px;flex:1;max-width:520px}
#cam-sel{display:none}
#cam-search{font-family:var(--mono);font-size:11px;background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:5px 8px;border-radius:5px;flex:1;min-width:160px}
#cam-search:focus{outline:none;border-color:var(--green)}
.cam-dropdown{position:absolute;top:100%;left:0;right:0;background:var(--surface);border:1px solid var(--border);border-radius:5px;max-height:380px;overflow-y:auto;z-index:100;display:none;margin-top:3px}
.cam-dropdown.open{display:block}
.cam-opt{font-family:var(--mono);font-size:11px;padding:6px 10px;cursor:pointer;color:var(--text);border-bottom:1px solid var(--border)}
.cam-opt:hover{background:var(--surface2)}
.cam-opt.selected{background:var(--surface2);color:var(--green)}
.cam-opt .cam-opt-tag{font-size:9px;color:var(--dim);margin-left:8px}
.cam-opt.no-image{color:var(--dim)}
.cam-filter-chip{font-family:var(--mono);font-size:9px;font-weight:600;padding:3px 7px;border-radius:9px;background:var(--surface2);border:1px solid var(--border);color:var(--mid);cursor:pointer;transition:all .15s;user-select:none}
.cam-filter-chip:hover{color:var(--text)}
.cam-filter-chip.on{background:var(--surface)}
.cam-filter-chip[data-type=LEAK].on{border-color:var(--mid);color:var(--text)}
.cam-filter-chip[data-type="Trailer 1"].on{border-color:var(--blue);color:var(--blue)}
.cam-filter-chip[data-type="Trailer 2"].on{border-color:var(--green);color:var(--green)}
.cam-filter-chip[data-type=screenshots].on{border-color:var(--purple);color:var(--purple)}
"""

content = content.replace('#cam-sel{font-family:var(--mono)', NEW_CSS + '#cam-sel{font-family:var(--mono)')
print("✓ Added new CSS")

# ── 2. Replace the select with the new UI structure ───────────────────────────
OLD_SELECT = '<select id="cam-sel"><option value="">— Select camera —</option></select>'
NEW_UI = '''<div class="cam-picker">
  <input id="cam-search" placeholder="Search camera..." autocomplete="off" />
  <button class="cam-filter-chip on" data-type="LEAK">LEAK</button>
  <button class="cam-filter-chip on" data-type="Trailer 1">T1</button>
  <button class="cam-filter-chip on" data-type="Trailer 2">T2</button>
  <button class="cam-filter-chip on" data-type="screenshots">SS</button>
  <div class="cam-dropdown" id="cam-dropdown"></div>
  <select id="cam-sel"><option value="">— Select camera —</option></select>
</div>'''

content = content.replace(OLD_SELECT, NEW_UI)
print("✓ Replaced select with picker UI")

# ── 3. Replace the init() loadCams logic with the new picker logic ────────────
OLD_INIT_BLOCK = """async function init() {
  const cams = await fetch('/api/cameras').then(r => r.json());
  cams.forEach(c => {
    const o = document.createElement('option');
    o.value = c.name;
    o.textContent = `${c.name}${c.has_image ? '' : ' ✗'} (${c.n_pixels}px / ${c.n_independent} indep)`;
    if (!c.has_image) o.style.color = '#444';
    camSel.appendChild(o);
  });"""

NEW_INIT_BLOCK = """// State for cam picker
let allCams = [];
const camFilters = { 'LEAK': true, 'Trailer 1': true, 'Trailer 2': true, 'screenshots': true };
let camSearchQ = '';

function getCamType(c) {
  const src = c.source || '';
  if (/^\\d{4}-\\d{2}-\\d{2}/.test(src)) return 'LEAK';
  if (src.startsWith('Trailer 1')) return 'Trailer 1';
  if (src.startsWith('Trailer 2') || src === 'Trailer 2') return 'Trailer 2';
  if (src.startsWith('Trailer')) return 'Trailer 2'; // fallback to T2 group
  return 'screenshots';
}

function renderCamDropdown() {
  const dd = document.getElementById('cam-dropdown');
  const filtered = allCams.filter(c => {
    const t = getCamType(c);
    if (!camFilters[t]) return false;
    if (camSearchQ && !c.name.toLowerCase().includes(camSearchQ.toLowerCase())) return false;
    return true;
  });
  if (filtered.length === 0) {
    dd.innerHTML = '<div class="cam-opt" style="color:var(--dim);cursor:default">No cams match</div>';
  } else {
    dd.innerHTML = filtered.map(c => {
      const t = getCamType(c);
      const cls = c.has_image ? 'cam-opt' : 'cam-opt no-image';
      const sel = c.name === currentCam ? ' selected' : '';
      return `<div class="${cls}${sel}" data-name="${c.name.replace(/"/g, '&quot;')}">
        ${c.name}${c.has_image ? '' : ' ✗'}
        <span class="cam-opt-tag">${t} · ${c.n_pixels}px / ${c.n_independent} indep</span>
      </div>`;
    }).join('');
  }
}

async function init() {
  allCams = await fetch('/api/cameras').then(r => r.json());
  // Populate hidden select for compatibility
  allCams.forEach(c => {
    const o = document.createElement('option');
    o.value = c.name;
    o.textContent = c.name;
    camSel.appendChild(o);
  });
  // Wire up cam picker
  const camSearch = document.getElementById('cam-search');
  const camDropdown = document.getElementById('cam-dropdown');
  camSearch.addEventListener('input', e => { camSearchQ = e.target.value; renderCamDropdown(); camDropdown.classList.add('open'); });
  camSearch.addEventListener('focus', () => { renderCamDropdown(); camDropdown.classList.add('open'); });
  document.addEventListener('click', e => {
    if (!e.target.closest('.cam-picker')) camDropdown.classList.remove('open');
  });
  camDropdown.addEventListener('click', e => {
    const opt = e.target.closest('.cam-opt[data-name]');
    if (!opt) return;
    const name = opt.dataset.name;
    camSel.value = name;
    camSearch.value = name;
    camDropdown.classList.remove('open');
    camSel.dispatchEvent(new Event('change'));
  });
  document.querySelectorAll('.cam-filter-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      btn.classList.toggle('on');
      camFilters[btn.dataset.type] = btn.classList.contains('on');
      renderCamDropdown();
    });
  });
  // Auto-load if URL has ?cam=
  const urlCam = new URLSearchParams(window.location.search).get('cam');
  if (urlCam && allCams.some(c => c.name === urlCam)) {
    camSel.value = urlCam;
    camSearch.value = urlCam;
    setTimeout(() => camSel.dispatchEvent(new Event('change')), 100);
  }"""

content = content.replace(OLD_INIT_BLOCK, NEW_INIT_BLOCK)
print("✓ Replaced init() with new picker logic")

# Update camSearch display when a cam is loaded externally (e.g. from selectSuspicious)
# Find the change handler on camSel and add a camSearch.value update
# We do this by hooking into the select's change event
HOOK_CSS = """document.getElementById('cam-sel').addEventListener('change', () => {
  const cs = document.getElementById('cam-search');
  if (cs) cs.value = document.getElementById('cam-sel').value;
});
"""

# Insert this hook right before the closing </script> tag
content = content.replace('</script>', HOOK_CSS + '</script>', 1)
print("✓ Added cam-search sync hook")

with open(HTML_PATH, 'w') as f:
    f.write(content)

print(f"\n✓ Done. Hard reload calib.html (Cmd+Shift+R) to see the new picker.")
