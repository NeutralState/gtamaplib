#!/usr/bin/env python3
"""
patch_lm_info.py — Adds a landmark info panel that shows source cameras
and other observers when a landmark is clicked. Helps avoid the
"delete pixel that's actually the only source" footgun.

Backend: new endpoint /api/lm_info?lm=NAME
Frontend: panel between cam-meta and Landmarks list

Run from gtamaplib-main/:
    python3 tools/patch_lm_info.py
"""
import os

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'tools' \
    else os.path.dirname(os.path.abspath(__file__))

SERVER_PATH = os.path.join(GTAMAP_DIR, 'tools', 'server.py')
HTML_PATH = os.path.join(GTAMAP_DIR, 'tools', 'calib.html')

# ── Backend: add /api/lm_info ─────────────────────────────────────────────────

with open(SERVER_PATH) as f:
    server_content = f.read()

if '/api/lm_info' in server_content:
    print("• server.py already has /api/lm_info")
else:
    ENDPOINT = '''
        elif path == '/api/lm_info':
            # Returns source cameras + all observers for a landmark.
            lm_name = unquote(qs.get('lm', [''])[0])
            if lm_name not in md.landmarks_meta:
                self.send_json({'error': 'unknown landmark'}, 404)
                return
            meta = md.landmarks_meta[lm_name]
            sources = list(meta.get('source_cameras') or [])
            error_m = meta.get('error_m')
            has_xyz = md.landmarks.get(lm_name) is not None

            # Find all cams that have a pixel for this landmark
            observers = []
            for cam_name, pxs in md.pixels.items():
                if lm_name in pxs:
                    observers.append(cam_name)

            # Other observers = those with pixels who are NOT in sources
            others = [c for c in observers if c not in sources]

            self.send_json({
                'lm': lm_name,
                'sources': sorted(sources),
                'others': sorted(others),
                'n_sources': len(sources),
                'n_others': len(others),
                'n_total_observers': len(observers),
                'error_m': error_m,
                'has_xyz': has_xyz,
            })

'''

    INSERTION_MARKER = "        elif path == '/api/cam_health':"
    if INSERTION_MARKER in server_content:
        server_content = server_content.replace(
            INSERTION_MARKER,
            ENDPOINT + INSERTION_MARKER
        )
        with open(SERVER_PATH, 'w') as f:
            f.write(server_content)
        print("✓ Added /api/lm_info endpoint")
    else:
        print("✗ Could not find insertion marker (cam_health endpoint)")

# ── Frontend: add panel + JS ──────────────────────────────────────────────────

with open(HTML_PATH) as f:
    html_content = f.read()

if 'lm-info-panel' in html_content:
    print("• calib.html already has lm-info-panel")
else:
    # CSS
    NEW_CSS = """
/* Landmark info panel */
.lm-info-panel{padding:9px 13px;border-bottom:1px solid var(--border);background:var(--surface2);display:none}
.lm-info-panel.show{display:block}
.lm-info-name{font-family:var(--mono);font-size:11px;font-weight:700;color:var(--text);margin-bottom:6px;display:flex;align-items:center;gap:6px}
.lm-info-warn{font-family:var(--mono);font-size:9px;color:var(--red);font-weight:600}
.lm-info-row{font-family:var(--mono);font-size:10px;color:var(--mid);margin-bottom:3px;line-height:1.4}
.lm-info-row .lbl{color:var(--dim);text-transform:uppercase;letter-spacing:.05em;font-size:9px}
.lm-info-row .val{color:var(--text)}
.lm-info-cam{display:inline-block;padding:1px 5px;margin:1px 2px 1px 0;background:var(--surface);border:1px solid var(--border);border-radius:3px;font-size:9px;cursor:pointer}
.lm-info-cam:hover{border-color:var(--blue);color:var(--blue)}
.lm-info-cam.source{border-color:var(--green);color:var(--green)}
.lm-info-cam.current{background:var(--blue);color:#000;border-color:var(--blue)}
.lm-info-close{margin-left:auto;color:var(--dim);cursor:pointer;font-family:var(--mono);font-size:11px}
.lm-info-close:hover{color:var(--red)}
"""
    html_content = html_content.replace('</style>', NEW_CSS + '</style>', 1)

    # Insert panel HTML right before the Landmarks section
    PANEL_HTML = '''
    <div class="lm-info-panel" id="lm-info-panel">
      <div class="lm-info-name">
        <span id="lm-info-name-text">—</span>
        <span class="lm-info-close" id="lm-info-close">✕</span>
      </div>
      <div class="lm-info-row" id="lm-info-status"></div>
      <div class="lm-info-row" id="lm-info-sources"></div>
      <div class="lm-info-row" id="lm-info-others"></div>
    </div>
'''

    LANDMARKS_ANCHOR = '<div class="sb-title" style="margin:0">Landmarks'
    # Find the parent .sb-sec of this anchor
    import re
    # Insert PANEL_HTML right before the .sb-sec containing Landmarks title
    # Use a more reliable anchor based on the structure
    LM_SEC_PATTERN = re.compile(
        r'(<div class="sb-sec"[^>]*>\s*<div class="sb-title" style="margin:0">Landmarks)'
    )
    m = LM_SEC_PATTERN.search(html_content)
    if m:
        html_content = html_content[:m.start()] + PANEL_HTML + html_content[m.start():]
        print("✓ Inserted lm-info-panel before Landmarks section")
    else:
        print("✗ Could not find Landmarks section anchor")

    # JS handler — wire up the panel to landmark clicks
    NEW_JS = """
// ── Landmark info panel ────────────────────────────────────────────────────
const lmInfoPanel    = document.getElementById('lm-info-panel');
const lmInfoNameText = document.getElementById('lm-info-name-text');
const lmInfoStatus   = document.getElementById('lm-info-status');
const lmInfoSources  = document.getElementById('lm-info-sources');
const lmInfoOthers   = document.getElementById('lm-info-others');
const lmInfoClose    = document.getElementById('lm-info-close');

function renderLmInfoCam(name) {
  const safeName = name.replace(/"/g, '&quot;');
  const isCurrent = name === currentCam;
  const cls = 'lm-info-cam' + (isCurrent ? ' current' : '');
  return `<span class="${cls}" data-cam="${safeName}">${name}</span>`;
}

async function showLmInfo(lmName) {
  if (!lmName) { lmInfoPanel.classList.remove('show'); return; }
  try {
    const r = await fetch('/api/lm_info?lm=' + encodeURIComponent(lmName));
    if (!r.ok) { lmInfoPanel.classList.remove('show'); return; }
    const info = await r.json();
    if (info.error) { lmInfoPanel.classList.remove('show'); return; }

    lmInfoNameText.textContent = info.lm;
    // Status row
    const statusBits = [];
    if (!info.has_xyz) statusBits.push('<span class="lm-info-warn">⚠ no xyz (untriangulated)</span>');
    if (info.error_m != null) statusBits.push(`<span class="lbl">err</span> <span class="val">${info.error_m.toFixed(1)}m</span>`);
    statusBits.push(`<span class="lbl">obs</span> <span class="val">${info.n_total_observers}</span>`);
    lmInfoStatus.innerHTML = statusBits.join(' · ');

    // Sources row
    if (info.sources.length === 0) {
      lmInfoSources.innerHTML = '<span class="lbl">sources</span> <span class="val" style="color:var(--red)">none — fixed-position landmark or unsourced</span>';
    } else {
      lmInfoSources.innerHTML = '<span class="lbl">sources (★)</span> ' +
        info.sources.map(c => renderLmInfoCam(c).replace('lm-info-cam', 'lm-info-cam source')).join('');
    }

    // Others row
    if (info.others.length === 0) {
      lmInfoOthers.innerHTML = '<span class="lbl">other observers</span> <span class="val" style="color:var(--dim)">none</span>';
    } else {
      lmInfoOthers.innerHTML = `<span class="lbl">also observed by (${info.others.length})</span> ` +
        info.others.map(renderLmInfoCam).join('');
    }

    lmInfoPanel.classList.add('show');
  } catch (e) {
    console.error('lm_info failed:', e);
    lmInfoPanel.classList.remove('show');
  }
}

lmInfoClose.addEventListener('click', () => {
  selectedLm = null;
  renderLmList();
  draw();
  lmInfoPanel.classList.remove('show');
});

// Click a cam pill to navigate to it
lmInfoPanel.addEventListener('click', e => {
  const camEl = e.target.closest('.lm-info-cam[data-cam]');
  if (!camEl) return;
  const camName = camEl.dataset.cam;
  if (camName === currentCam) return;
  // Navigate via the hidden select (so cam picker stays in sync)
  camSel.value = camName;
  const camSearch = document.getElementById('cam-search');
  if (camSearch) camSearch.value = camName;
  camSel.dispatchEvent(new Event('change'));
});
"""
    html_content = html_content.replace('</script>', NEW_JS + '</script>', 1)
    print("✓ Added landmark info panel JS")

    # Hook into landmark click — find the click handler and add showLmInfo call
    OLD_CLICK = """    div.addEventListener('click', () => { selectedLm = selectedLm === lm.name ? null : lm.name; renderLmList(); draw(); });"""
    NEW_CLICK = """    div.addEventListener('click', () => { selectedLm = selectedLm === lm.name ? null : lm.name; renderLmList(); draw(); showLmInfo(selectedLm); });"""
    if OLD_CLICK in html_content:
        html_content = html_content.replace(OLD_CLICK, NEW_CLICK)
        print("✓ Hooked landmark click to show panel")
    else:
        print("✗ Could not find landmark click handler")

with open(HTML_PATH, 'w') as f:
    f.write(html_content)

print("\nNext steps:")
print("  1. Restart server: lsof -ti :8765 | xargs kill -9; python3 tools/server.py")
print("  2. Hard reload calib.html (Cmd+Shift+R)")
print("  3. Click a landmark in the sidebar → panel shows sources + other observers")
print("  4. Click a cam pill in the panel → navigate to that cam")
