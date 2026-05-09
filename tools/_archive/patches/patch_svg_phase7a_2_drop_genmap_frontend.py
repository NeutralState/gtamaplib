#!/usr/bin/env python3
"""
patch_svg_phase7a_2_drop_genmap_frontend.py — drop "Generate Map" UI from calib.html

Phase 7a.2 removes the "Generate Map" button and its modal from the
Camera-view sidebar. The Map view (Phase 3+4 onward) replaces it
entirely — no need for a server-rendered top-down PNG anymore.

Removed in this patch:
  - HTML: <button id="btn-genmap"> (in .sidebar)
  - HTML: <div id="genmap-modal">…</div> (modal that displayed the PNG)
  - CSS: #btn-genmap rules + all .genmap-* rules
  - JS: the entire "// ── Generate Map ──" block (handler + modal logic)

What stays untouched:
  - The /api/generate_map and /api/generated_map endpoints in server.py
    are removed by Phase 7a.3 (the next patch). We drop the frontend
    FIRST so the now-orphaned endpoints can't accidentally be hit.
  - The ray-map-modal (showRayMap / triangulateLandmark) is unrelated
    and stays — it visualizes triangulation results post-optimization.

Idempotent. Builds on Phase 7a.1.1.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase7a_2'

SENTINEL = '/* Phase 7a.2: Generate Map UI removed */'
PHASE7A_1_1_SENTINEL = '/* Phase 7a.1.1: minimap grayscale + cam preview click + PNG preload */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: remove all #btn-genmap and .genmap-* rules.
# Anchor: the existing block of these rules together.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
/* Generate Map button + modal */
#btn-genmap{font-family:var(--mono);font-size:11px;font-weight:700;padding:6px 10px;border-radius:5px;border:1px solid var(--border);background:var(--surface2);color:var(--blue);cursor:pointer;width:100%;margin-top:8px}
#btn-genmap:hover{background:var(--surface);border-color:var(--blue)}
#btn-genmap:disabled{opacity:.4;cursor:default}
#genmap-modal{position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:1000;display:none;align-items:center;justify-content:center;padding:20px}
#genmap-modal.open{display:flex}
.genmap-content{background:var(--surface);border:1px solid var(--border);border-radius:8px;max-width:95vw;max-height:95vh;display:flex;flex-direction:column;overflow:hidden}
.genmap-header{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--border)}
.genmap-title{font-family:var(--mono);font-size:11px;color:var(--text);flex:1}
.genmap-close{font-family:var(--mono);font-size:14px;color:var(--mid);background:none;border:none;cursor:pointer;padding:4px 8px}
.genmap-close:hover{color:var(--red)}
.genmap-img{max-width:90vw;max-height:80vh;object-fit:contain;display:block}
.genmap-legend{display:flex;gap:14px;padding:8px 14px;border-top:1px solid var(--border);font-family:var(--mono);font-size:10px;color:var(--mid)}
.genmap-legend-item{display:flex;align-items:center;gap:5px}
.genmap-legend-dot{width:10px;height:10px;border-radius:2px}"""

HUNK_1_NEW = """\
/* Phase 7a.2: Generate Map button + modal CSS removed
   (replaced by the always-on Map view; no server-rendered PNG needed). */"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — HTML: remove the Generate Map button from the right sidebar.
# Anchor: the exact <button> line. Note the surrounding whitespace.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
  <div class="sidebar">
<button id="btn-genmap" disabled>🗺 Generate Map</button>

    <div class="sb-sec">"""

HUNK_2_NEW = """\
  <div class="sidebar">
    <!-- Phase 7a.2: Generate Map button removed (replaced by Map view) -->
    <div class="sb-sec">"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — HTML: remove the genmap-modal block.
# Anchor: from `<div id="genmap-modal">` through its closing `</div>` block.
# We capture the entire modal including the legend section, but stop
# before the `<script>` tag that follows.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
<div id="genmap-modal">
  <div class="genmap-content">
    <div class="genmap-header">
      <div class="genmap-title" id="genmap-title">Map</div>
      <button class="genmap-close" id="genmap-close">✕</button>
    </div>
    <img id="genmap-img" class="genmap-img" />
    <div class="genmap-legend">
      <div class="genmap-legend-item"><div class="genmap-legend-dot" style="background:#4ade80"></div>&lt;3' (good)</div>
      <div class="genmap-legend-item"><div class="genmap-legend-dot" style="background:#f59e0b"></div>3-10' (suspicious)</div>
      <div class="genmap-legend-item"><div class="genmap-legend-dot" style="background:#f87171"></div>&gt;10' (outlier)</div>
      <div class="genmap-legend-item"><div class="genmap-legend-dot" style="background:#8c8c8c"></div>unprojectable</div>
    </div>

<script>"""

HUNK_3_NEW = """\
<!-- Phase 7a.2: #genmap-modal removed (replaced by Map view) -->

<script>"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 4 — JS: remove the entire "// ── Generate Map ──" block.
# Anchor: from the comment header through the cam-sel change setTimeout.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_4_OLD = """\
// ── Generate Map ────────────────────────────────────────────────────────
const btnGenmap = document.getElementById('btn-genmap');
const genmapModal = document.getElementById('genmap-modal');
const genmapImg = document.getElementById('genmap-img');
const genmapTitle = document.getElementById('genmap-title');
const genmapClose = document.getElementById('genmap-close');

btnGenmap.addEventListener('click', async () => {
  if (!currentCam) return;
  btnGenmap.disabled = true;
  btnGenmap.textContent = 'Generating...';
  try {
    const r = await fetch('/api/generate_map?cam=' + encodeURIComponent(currentCam));
    const data = await r.json();
    if (data.ok) {
      genmapTitle.textContent = `${currentCam} — ${data.n_rays} rays`;
      genmapImg.src = data.url + '&t=' + Date.now(); // cache bust
      genmapModal.classList.add('open');
    } else {
      alert('Failed: ' + (data.error || 'unknown'));
    }
  } catch (e) {
    alert('Error: ' + e.message);
  } finally {
    btnGenmap.disabled = !currentCam;
    btnGenmap.textContent = '🗺 Generate Map';
  }
});

genmapClose.addEventListener('click', () => genmapModal.classList.remove('open'));
genmapModal.addEventListener('click', e => {
  if (e.target === genmapModal) genmapModal.classList.remove('open');
});

// Enable button when a cam is loaded
document.getElementById('cam-sel').addEventListener('change', () => {
  setTimeout(() => { btnGenmap.disabled = !currentCam; }, 200);
});"""

HUNK_4_NEW = """\
// Phase 7a.2: Generate Map button + modal logic removed.
// The Map view (Phase 3+4) replaces this server-rendered PNG entirely.
// The cam-sel change listener that enabled the button is also gone."""


HUNKS = [
    ('CSS — remove #btn-genmap and .genmap-* rules', HUNK_1_OLD, HUNK_1_NEW),
    ('HTML — remove Generate Map button',           HUNK_2_OLD, HUNK_2_NEW),
    ('HTML — remove #genmap-modal block',           HUNK_3_OLD, HUNK_3_NEW),
    ('JS — remove Generate Map block',              HUNK_4_OLD, HUNK_4_NEW),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--revert', action='store_true')
    args = ap.parse_args()

    if not os.path.exists(CALIB_HTML):
        print(f'ERROR: {CALIB_HTML} not found.')
        sys.exit(1)

    if args.revert:
        if not os.path.exists(BACKUP):
            print(f'ERROR: no backup at {BACKUP}.')
            sys.exit(1)
        if args.apply:
            shutil.copy(BACKUP, CALIB_HTML)
            print(f'✓ Restored {CALIB_HTML} from {BACKUP}.')
        else:
            print(f'(dry-run) would restore from {BACKUP}.')
        return

    with open(CALIB_HTML, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print('✓ Already patched.')
        return

    if PHASE7A_1_1_SENTINEL not in src:
        print('ERROR: Phase 7a.1.1 sentinel not found. Apply Phase 7a.1.1 first.')
        sys.exit(1)

    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} times (need exactly 1).')
            sys.exit(1)

    new_src = src
    for _label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    # Add sentinel near the prior 7a.1.1 sentinel for downstream pre-flight.
    new_src = new_src.replace(PHASE7A_1_1_SENTINEL,
                              PHASE7A_1_1_SENTINEL + '\n' + SENTINEL,
                              1)

    delta = new_src.count('\n') - src.count('\n')
    print(f'Will modify {CALIB_HTML} ({delta:+d} lines)')
    print(f'  hunks applied: {len(HUNKS)}')

    if not args.apply:
        print('\n(dry-run — re-run with --apply)')
        return

    shutil.copy(CALIB_HTML, BACKUP)
    print(f'\n✓ Backup: {BACKUP}')
    tmp = CALIB_HTML + '.tmp'
    with open(tmp, 'w') as f:
        f.write(new_src)
    os.replace(tmp, CALIB_HTML)
    print(f'✓ Patched {CALIB_HTML}')
    print()
    print('Test: hard reload, the right sidebar no longer shows the')
    print('Generate Map button. The Map view replaces it.')
    print()
    print('Next: Phase 7a.3 drops the now-orphaned server endpoints.')


if __name__ == '__main__':
    main()
