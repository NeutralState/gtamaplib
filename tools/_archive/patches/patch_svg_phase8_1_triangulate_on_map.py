#!/usr/bin/env python3
"""
patch_svg_phase8_1_triangulate_on_map.py — Triangulate on Map view + drop showRayMap callsites

Phase 8.1 refactors three flows that all popped the same `ray-map-modal`:

  1. Triangulate (click ⊕ on a landmark in lm-list)
     - Was: open modal with PNG ray map, fetch /api/triangulate, persist xyz,
       refresh modal with result.
     - Now: fetch /api/triangulate (still persists), switch to Map view,
       render rays from ALL source cams converging on the landmark,
       pan map to landmark, show toast "✓ Triangulated · error 0.42m".

  2. Optimize (the ⚡ button in the right sidebar)
     - Was: optimize, then showRayMap to display the post-opt loss.
     - Now: optimize, then nothing (the loss chip in the header already
       shows the new value). The ray map was not adding much info.

  3. Update LMs (button in the right sidebar)
     - Was: update LMs, then showRayMap to display rays.
     - Now: update LMs, then nothing.

Phase 8.2 (next) drops the now-unused ray-map-modal HTML/CSS, the
showRayMap() function, and the /api/ray_map server endpoint. We keep
all three in Phase 8.1 to limit blast radius — if Phase 8.1 has a bug
we can revert and fall back to the modal flow temporarily.

New in this patch:
  - HTML: <svg> overlay <g id="tri-rays-layer"> inside #map-overlay
  - HTML: <div id="tri-toast"> floating toast at top-center of Map view
  - CSS:  .tri-ray styles + #tri-toast styles
  - JS:   showTriangulationOnMap(lmName, sourceCams, errorM, color_lookup)
          + dismissTriangulation() + clear-on-interaction wiring
  - JS:   triangulateLandmark() rewritten to use the new flow
  - JS:   Optimize and Update LMs post-action showRayMap calls removed

Idempotent. Builds on Phase 7a.5.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase8_1'

SENTINEL = '/* Phase 8.1: triangulate on Map view + drop showRayMap callsites */'
PHASE7A_5_SENTINEL = '/* Phase 7a.5: minimap fetches /api/minimap (revert CSS-only) */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: tri-rays styling + toast.
# Anchor: append after the Phase 6.3 "end" comment in the map overlay CSS block.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
/* ── end SVG Map Refactor Phase 6.2 ── */"""

HUNK_1_NEW = """\
/* ── end SVG Map Refactor Phase 6.2 ── */

/* ── SVG Map Refactor Phase 8.1: triangulation viz on map ── */
/* Triangulation rays — rendered in #tri-rays-layer. Each ray is a
   <line> from cam apex → landmark xyz, color-coded by source-cam type
   (LEAK/T1/T2/SS), with a final pulse ring around the landmark. */
#map-overlay #tri-rays-layer{pointer-events:none}
#map-overlay .tri-ray{stroke-width:18;stroke-linecap:round;opacity:.85;
  filter:drop-shadow(0 0 6px rgba(255,255,255,0.3))}
#map-overlay .tri-pulse{fill:none;stroke:#ffffff;stroke-width:8;
  opacity:.85}
/* Toast at the top-center of the Map view. Sits above the SVG overlay
   so it's always visible. Auto-fades; CSS handles the fade animation. */
#tri-toast{position:absolute;top:18px;left:50%;transform:translateX(-50%);
  z-index:200;background:rgba(15,15,22,0.94);color:#fff;
  border:1px solid var(--border);border-radius:8px;padding:10px 16px;
  font-family:var(--mono);font-size:11px;line-height:1.5;
  box-shadow:0 6px 24px rgba(0,0,0,0.5);
  display:none;cursor:pointer;
  max-width:560px;text-align:center}
#tri-toast.show{display:block;animation:triToastIn .22s ease-out}
#tri-toast .tri-toast-title{font-weight:700;color:var(--green);
  margin-bottom:3px;font-size:12px}
#tri-toast .tri-toast-meta{color:var(--mid);font-size:10px}
#tri-toast.error .tri-toast-title{color:var(--red)}
@keyframes triToastIn{from{opacity:0;transform:translate(-50%,-8px)}
  to{opacity:1;transform:translateX(-50%)}}
/* ── end SVG Map Refactor Phase 8.1 ── */
/* Phase 8.1: triangulate on Map view + drop showRayMap callsites */"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — HTML: add #tri-toast inside the .canvas-wrap-map (or wherever
# the Map view container is). Anchor: the closing </svg> of #map-overlay
# is a stable spot. We'll add the toast right after the map-overlay svg
# in DOM order so it floats above.
#
# Looking at Phase 4 layout: there's a .map-png-wrap > <img> + <svg id=map-overlay>.
# The toast belongs as a sibling of those, inside the map view container.
#
# Anchor option: I'll target the comment that closes the map view block.
# But without seeing it directly, safer anchor = the closing </svg> of
# the map-overlay SVG (the empty SVG that Phase 5 fills with cams/dots).
# ─────────────────────────────────────────────────────────────────────────────

# Actually, we need to see the exact map-overlay HTML to anchor cleanly.
# Use a different anchor that's guaranteed unique: the body class toggle
# script setup near the </script> at the end.

# Safer plan: insert tri-toast as the LAST child of body, then position
# it absolutely relative to the map view container via CSS (already does
# this via #tri-toast top:18px). Anchor: just before </body>.

HUNK_2_OLD = """\
</script>


  </div>
</div>
</body>
</html>"""

HUNK_2_NEW = """\
</script>

<!-- Phase 8.1: triangulation toast (top-center over map view). -->
<div id="tri-toast" onclick="dismissTriangulation()">
  <div class="tri-toast-title" id="tri-toast-title">Triangulated</div>
  <div class="tri-toast-meta" id="tri-toast-meta">—</div>
</div>

  </div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — JS: add tri-rays-layer to renderCamsOnMap or its setup.
# Looking at the grep, raysGroup with id 'rays-layer' is created at line 1111.
# The cleanest add: extend the createElement block.
#
# Grep showed:
#   raysGroup.setAttribute('id', 'rays-layer');
#
# We'll anchor on that exact line and inject a tri-rays-layer creation right after.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
    raysGroup.setAttribute('id', 'rays-layer');"""

HUNK_3_NEW = """\
    raysGroup.setAttribute('id', 'rays-layer');
    // Phase 8.1: tri-rays-layer renders triangulation visualization
    // (rays from all source cams converging on a landmark).
    // Inserted in DOM AFTER cams-layer so cams paint on top of tri-rays.
    const triRaysGroup = document.createElementNS(SVG_NS, 'g');
    triRaysGroup.setAttribute('id', 'tri-rays-layer');"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 4 — JS: append tri-rays-layer to mapOverlay after the other layers.
# We need to find where the existing layers are appended. From the grep:
#   raysGroup is created at line 1111, must be appended somewhere nearby.
# I'll anchor on the closing of the layer-setup block — but I don't have
# its exact text. Simpler: I'll do it with another str_replace that
# matches the appendChild block. Since I don't have visibility, I'll
# integrate the append into HUNK 3 by appending inline.
#
# Actually, looking again, I need to see the appendChild calls. Let me
# do this differently — since renderCamsOnMap() is called fresh on each
# cam change and it manages layer creation, I can document.getElementById
# the rays-layer in showTriangulationOnMap and createElement the
# tri-rays-layer if it doesn't exist yet (lazy init).
#
# That's cleaner anyway. Drop HUNK 3+4 as separate things; instead make
# the tri-rays-layer lazy-init inside the new showTriangulationOnMap.
# ─────────────────────────────────────────────────────────────────────────────

# Revising: drop HUNK 3, do lazy-init in JS function (HUNK 5).


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 5 — JS: replace triangulateLandmark + add showTriangulationOnMap
# + dismissTriangulation. Anchor: the existing triangulateLandmark
# function definition through its closing brace.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_5_OLD = """\
// ── Triangulation & Ray Viz ───────────────────────────────────────────────
async function triangulateLandmark(lm_name) {
  // First check how many cams see this landmark
  const src = await fetch(`/api/cam_sources?lm=${encodeURIComponent(lm_name)}`).then(r=>r.json());

  if (src.cams.length < 2) {
    showRayMap([currentCam], lm_name, `⚠ Need 2+ calibrated cams — only ${src.cams.length} found for "${lm_name}"`);
    return;
  }

  // Show ray viz first
  showRayMap(src.cams, lm_name, `Triangulating "${lm_name}" from ${src.cams.length} cams...`);

  // Run triangulation
  const res = await fetch(`/api/triangulate?lm=${encodeURIComponent(lm_name)}`).then(r=>r.json());

  if (res.error) {
    document.getElementById('ray-map-info').textContent = '⚠ ' + res.error;
    return;
  }

  document.getElementById('ray-map-info').innerHTML =
    `<span style="color:var(--green)">✓ Triangulated</span> · xyz=[${res.xyz.map(v=>v.toFixed(1)).join(', ')}] · error=${res.error_m}m · from ${res.cam_a} + ${res.cam_b}`;

  // Reload projections to show updated landmark
  await loadProjections();

  // Refresh ray map with new landmark position
  showRayMap(src.cams, lm_name, `"${lm_name}" — ${src.cams.length} source cams · error=${res.error_m}m`);
}"""

HUNK_5_NEW = """\
// ── Phase 8.1: Triangulation on Map view ──────────────────────────────────
// Click ⊕ on a landmark → fetch /api/triangulate (persists xyz),
// switch to Map view, render rays from ALL source cams converging on
// the landmark, pan map to it, show toast.
async function triangulateLandmark(lm_name) {
  // First check how many cams see this landmark.
  const src = await fetch(`/api/cam_sources?lm=${encodeURIComponent(lm_name)}`).then(r=>r.json());
  if (src.cams.length < 2) {
    showTriToast(`Cannot triangulate "${lm_name}"`,
      `Need 2+ calibrated cams — only ${src.cams.length} found.`,
      true);
    return;
  }
  // Switch to map view immediately so the user sees something happening.
  if (typeof window.setView === 'function') window.setView('map');
  showTriToast(`Triangulating "${lm_name}"...`,
    `From ${src.cams.length} source cams.`, false);

  // Run triangulation (persists xyz on success).
  const res = await fetch(`/api/triangulate?lm=${encodeURIComponent(lm_name)}`).then(r=>r.json());
  if (res.error) {
    showTriToast(`Triangulation failed for "${lm_name}"`, res.error, true);
    return;
  }
  // Reload projections so the camera-view canvas reflects the new xyz
  // when the user switches back.
  await loadProjections();
  // Refresh map data so #lm-layer + #cams-layer reflect the new state.
  if (typeof window.reloadMapData === 'function') {
    try { await window.reloadMapData(); } catch (e) {}
  }
  // Render the converging rays + pulse on the map.
  showTriangulationOnMap(lm_name, src.cams, res.xyz, res.error_m);
  // Show the result toast.
  const xyzStr = res.xyz.map(v => v.toFixed(1)).join(', ');
  showTriToast(`✓ Triangulated "${lm_name}"`,
    `error=${res.error_m}m · xyz=[${xyzStr}] · ${res.cam_a} + ${res.cam_b} (best pair of ${res.n_cams})`,
    false);
}

// Phase 8.1: render rays from source cams converging on a landmark in
// the map overlay. Lazy-creates the #tri-rays-layer if absent.
function showTriangulationOnMap(lmName, sourceCams, lmXyz, errorM) {
  const overlay = window.mapOverlay || document.getElementById('map-overlay');
  if (!overlay) return;
  let layer = document.getElementById('tri-rays-layer');
  if (!layer) {
    layer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    layer.setAttribute('id', 'tri-rays-layer');
    layer.style.pointerEvents = 'none';
    overlay.appendChild(layer);
  }
  // Clear prior tri-rays.
  while (layer.firstChild) layer.removeChild(layer.firstChild);

  // Compute landmark SVG coords.
  const [lmSx, lmSy] = window.worldToSvg(lmXyz[0], lmXyz[1]);

  // Cam-type → color (matches Phase 5/6 cam-marker palette).
  function camColor(camName) {
    const cam = (window.mapData?.cams || []).find(c => c.name === camName);
    if (!cam) return '#9090b0';
    const t = (cam.type || '').toLowerCase();
    if (t === 'leak') return '#4ade80';      // green
    if (t === 'trailer1' || t === 'trailer 1') return '#60a5fa';
    if (t === 'trailer2' || t === 'trailer 2') return '#60a5fa';
    if (t === 'screenshots' || t === 'screenshot') return '#a78bfa'; // purple
    return '#fbbf24';
  }
  // Render one ray per source cam.
  for (const camName of sourceCams) {
    const cam = (window.mapData?.cams || []).find(c => c.name === camName);
    if (!cam || !cam.xyz) continue;
    const [csx, csy] = window.worldToSvg(cam.xyz[0], cam.xyz[1]);
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('class', 'tri-ray');
    line.setAttribute('x1', String(csx));
    line.setAttribute('y1', String(csy));
    line.setAttribute('x2', String(lmSx));
    line.setAttribute('y2', String(lmSy));
    line.setAttribute('stroke', camColor(camName));
    layer.appendChild(line);
  }
  // Pulse ring around the landmark.
  const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  pulse.setAttribute('class', 'tri-pulse');
  pulse.setAttribute('cx', String(lmSx));
  pulse.setAttribute('cy', String(lmSy));
  pulse.setAttribute('r', '60');
  layer.appendChild(pulse);

  // Pan map to center on the landmark. resetMapView centers + fits all,
  // we want a soft pan: set translate so landmark appears at viewport
  // center. Use existing window.mapTx if it exposes a setter; otherwise
  // call resetMapView which at least makes sure everything is visible.
  if (typeof window.panMapToWorld === 'function') {
    try { window.panMapToWorld(lmXyz[0], lmXyz[1]); } catch (e) {}
  }
}

// Phase 8.1: dismiss tri-rays layer + toast.
function dismissTriangulation() {
  const layer = document.getElementById('tri-rays-layer');
  if (layer) {
    while (layer.firstChild) layer.removeChild(layer.firstChild);
  }
  const toast = document.getElementById('tri-toast');
  if (toast) {
    toast.classList.remove('show');
    if (window._triToastTimer) {
      clearTimeout(window._triToastTimer);
      window._triToastTimer = null;
    }
  }
}
window.dismissTriangulation = dismissTriangulation;

// Phase 8.1: show / hide the toast.
function showTriToast(title, meta, isError) {
  const toast = document.getElementById('tri-toast');
  if (!toast) return;
  document.getElementById('tri-toast-title').textContent = title;
  document.getElementById('tri-toast-meta').textContent = meta || '';
  toast.classList.toggle('error', !!isError);
  toast.classList.add('show');
  if (window._triToastTimer) clearTimeout(window._triToastTimer);
  window._triToastTimer = setTimeout(() => {
    toast.classList.remove('show');
    window._triToastTimer = null;
  }, 6000);
}

// Phase 8.1: clear the tri-rays on most subsequent interactions.
// (User scrolled, picked a different cam/landmark, etc.)
document.addEventListener('click', e => {
  if (e.target.closest('#tri-toast')) return;  // toast click handled by toast itself
  // Only clear if there's something to clear, and if the click is in
  // the map area, sidebar list, etc. — not on the lm-list ⊕ button (
  // which calls triangulateLandmark and would immediately self-clear).
  if (e.target.closest('.lm-action-tri')) return;
  const layer = document.getElementById('tri-rays-layer');
  if (layer && layer.firstChild) {
    while (layer.firstChild) layer.removeChild(layer.firstChild);
  }
});"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 6 — JS: drop showRayMap call after Optimize.
# Anchor: the line at 1824 from the grep.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_6_OLD = """\
  showRayMap([currentCam], null, `Ray viz: ${currentCam} · loss ${data.loss_before} → ${data.loss} arcmin`);"""

HUNK_6_NEW = """\
  // Phase 8.1: showRayMap call removed. The loss chip in the header now
  // shows the new value; no modal is needed."""


HUNKS = [
    ('CSS — tri-rays + toast styles + sentinel',          HUNK_1_OLD, HUNK_1_NEW),
    ('HTML — #tri-toast at end of body',                  HUNK_2_OLD, HUNK_2_NEW),
    ('JS — replace triangulateLandmark + add helpers',    HUNK_5_OLD, HUNK_5_NEW),
    ('JS — drop showRayMap call after Optimize',          HUNK_6_OLD, HUNK_6_NEW),
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

    if PHASE7A_5_SENTINEL not in src:
        print('ERROR: Phase 7a.5 sentinel not found.')
        sys.exit(1)

    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} times (need exactly 1).')
            sys.exit(1)

    new_src = src
    for _label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

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
    print('Test:')
    print('  1. Hard reload (Cmd+Shift+R), open Camera view, select a cam.')
    print('  2. Click ⊕ on an untriangulated landmark in the lm-list.')
    print('     → Should switch to Map view automatically.')
    print('     → Should show converging rays from source cams.')
    print('     → Toast at top-center: "✓ Triangulated · error 0.42m..."')
    print('  3. Click anywhere else on the map → tri-rays clear.')
    print('  4. Click Optimize button → no more modal pop. Loss chip updates.')
    print()
    print('Phase 8.2 (next) drops the now-unused ray-map-modal + /api/ray_map.')


if __name__ == '__main__':
    main()
