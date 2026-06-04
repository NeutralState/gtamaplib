"""
Multi-cam Step 2+3 — projected LM overlays.

Server side (tools/server.py):
  /api/lm_projections?cam=<cam_name>
    Returns all LMs that should appear as ghost markers on this cam's
    image plane:
    - type='point' for triangulated LMs (lm.xyz known) → exact pixel
    - type='epipolar' for LMs with exactly 1 source cam → line on this cam
    - skipped: LMs already marked on this cam (no ghost needed), LMs out of view

Frontend side (tools/calib.html):
  - Two new <svg> overlays inside #canvas-wrap and #pane-2 (drawn on top
    of the frames, below cursors/markers)
  - When dual mode toggles on OR cam selection changes on either pane,
    fetch /api/lm_projections for the OTHER pane and draw ghost markers
  - Pulse + label on hover
  - Hidden by default in single-pane mode (only visible when body.dual-cam)

The endpoint deliberately uses gtamaplib's own get_pixel() math — same
math the bundle adjust uses, so projections will look exactly like the
"after-optimize" position.

Idempotent: marker [MULTICAM-STEP23] makes re-runs no-op.
"""

import os
import sys

SERVER = os.path.expanduser('~/Downloads/gtamaplib-main/tools/server.py')
CALIB = os.path.expanduser('~/Downloads/gtamaplib-main/tools/calib.html')

# ── PATCH SERVER ──────────────────────────────────────────────────────
with open(SERVER) as f:
    s = f.read()

if '[MULTICAM-STEP23]' in s:
    print('Server already patched — skipping server side.')
else:
    bak = SERVER + '.bak_multicam_step23'
    with open(bak, 'w') as f: f.write(s)
    print(f'Server backup: {bak}')

    # Find a good insertion point — after /api/render_loss block, before /api/save.
    # Use the /api/save anchor.
    anchor = "        elif path == '/api/save':"
    new = '''        elif path == '/api/lm_projections':
            # [MULTICAM-STEP23] Return all LMs that should appear as ghost
            # markers on this cam's image. For each LM:
            #   - 'point' if lm.xyz is known (triangulated): exact pixel
            #   - 'epipolar' if lm has exactly 1 source cam: line on this cam
            #   - skipped if already pixel-marked on this cam, or out of view
            cam_name = unquote(qs.get('cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400)
                return
            try:
                target_cam = ml.get_camera(cam_name)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return
            if target_cam.xyz is None or target_cam.q is None:
                self.send_json({'error': 'cam not calibrated'}, 400)
                return
            target_w, target_h = target_cam.w, target_cam.h
            target_pixels = md.pixels.get(cam_name, {})  # LMs already marked on this cam

            projections = []
            VIRTUAL_PREFIXES = ('Portofino Tower (',)
            for lm_name, lm in md.landmarks.items():
                # Skip the few synthetic / virtual LMs
                if any(lm_name.startswith(p) for p in VIRTUAL_PREFIXES):
                    continue
                # Skip if already marked on the target cam (no ghost needed)
                if lm_name in target_pixels:
                    continue
                lm_xyz = lm.get('xyz') if isinstance(lm, dict) else getattr(lm, 'xyz', None)
                src_cams = lm.get('source_cameras', []) if isinstance(lm, dict) else getattr(lm, 'source_cameras', [])

                if lm_xyz is not None:
                    # Triangulated -> project as a point
                    try:
                        px = target_cam.get_pixel(lm_xyz)
                    except Exception:
                        continue
                    if px is None:
                        continue
                    x, y = float(px[0]), float(px[1])
                    # Skip if out of frame (with small margin for labels)
                    if x < -50 or x > target_w + 50 or y < -50 or y > target_h + 50:
                        continue
                    projections.append({
                        'name': lm_name,
                        'type': 'point',
                        'pixel': [x, y],
                    })
                elif len(src_cams) == 1:
                    # 1 source only -> epipolar line on the target cam
                    src_cam_name = src_cams[0]
                    if src_cam_name == cam_name:
                        continue
                    if src_cam_name not in md.cameras:
                        continue
                    src_pixels = md.pixels.get(src_cam_name, {})
                    if lm_name not in src_pixels:
                        continue
                    try:
                        src_cam = ml.get_camera(src_cam_name)
                        src_pix = src_pixels[lm_name]
                        # Ray from src_cam through this pixel
                        d = src_cam.get_pixel_direction((float(src_pix[0]), float(src_pix[1])))
                        # Sample 2 points along the ray at near + far distances
                        # and project on target_cam.
                        import numpy as _np
                        src_xyz = _np.asarray(src_cam.xyz, dtype=float)
                        d = _np.asarray(d, dtype=float)
                        near_pt = (src_xyz + 50.0 * d).tolist()
                        far_pt  = (src_xyz + 5000.0 * d).tolist()
                        px_near = target_cam.get_pixel(near_pt)
                        px_far  = target_cam.get_pixel(far_pt)
                        if px_near is None or px_far is None:
                            continue
                        x1, y1 = float(px_near[0]), float(px_near[1])
                        x2, y2 = float(px_far[0]), float(px_far[1])
                        # If both endpoints are way outside the frame, skip
                        outside = (
                            (max(x1, x2) < -50 or min(x1, x2) > target_w + 50) or
                            (max(y1, y2) < -50 or min(y1, y2) > target_h + 50)
                        )
                        if outside:
                            continue
                        projections.append({
                            'name': lm_name,
                            'type': 'epipolar',
                            'line': [[x1, y1], [x2, y2]],
                            'source_cam': src_cam_name,
                        })
                    except Exception:
                        continue

            self.send_json({
                'cam': cam_name,
                'cam_size': [target_w, target_h],
                'projections': projections,
            })

''' + anchor

    if anchor not in s:
        print('ERROR: server anchor not found')
        sys.exit(1)
    s = s.replace(anchor, new, 1)
    with open(SERVER, 'w') as f: f.write(s)
    print('Server patched: /api/lm_projections endpoint added')


# ── PATCH FRONTEND ────────────────────────────────────────────────────
with open(CALIB) as f:
    c = f.read()

if '[MULTICAM-STEP23]' in c:
    print('Frontend already patched — skipping.')
else:
    bak = CALIB + '.bak_multicam_step23'
    with open(bak, 'w') as f: f.write(c)
    print(f'Frontend backup: {bak}')

    # 1. Add CSS for the SVG projection overlays
    css_anchor = '/* [MULTICAM-STEP1] Dual-pane layout'
    css_new = '''/* [MULTICAM-STEP23] LM projection overlays (point + epipolar line).
   Two SVG layers, one per pane. Each sits ABOVE the frame img but
   BELOW the existing #overlay canvas (which handles cursors / verticals).
   Pointer-events: none so they don't block the canvas underneath. */
.lm-proj-svg{position:absolute;top:0;left:0;width:100%;height:100%;
  pointer-events:none;display:none}
body.dual-cam .lm-proj-svg{display:block}
.lm-proj-svg .lm-proj-point{stroke-width:2;fill:none;opacity:.55;
  stroke-dasharray:4 3;transition:opacity .15s,stroke-width .15s}
.lm-proj-svg .lm-proj-point.hovered{opacity:1;stroke-width:3.5;
  stroke-dasharray:none}
.lm-proj-svg .lm-proj-line{stroke-width:1.6;fill:none;opacity:.45;
  stroke-dasharray:6 4;transition:opacity .15s,stroke-width .15s}
.lm-proj-svg .lm-proj-line.hovered{opacity:.95;stroke-width:2.5}
.lm-proj-svg .lm-proj-label{font-family:JetBrains Mono,monospace;font-size:10px;
  fill:#fff;stroke:#000;stroke-width:2;paint-order:stroke;opacity:0;
  transition:opacity .15s;pointer-events:none}
.lm-proj-svg .lm-proj-label.hovered{opacity:1}
.lm-proj-svg .lm-proj-group{cursor:pointer;pointer-events:auto}
.lm-proj-svg .lm-proj-group:hover .lm-proj-point,
.lm-proj-svg .lm-proj-group:hover .lm-proj-line{opacity:1;stroke-width:3}
.lm-proj-svg .lm-proj-group:hover .lm-proj-label{opacity:1}
/* "Projections" toggle button — visible only when dual mode is on. */
#proj-toggle{display:none}
body.dual-cam #proj-toggle{display:inline-block}
body.dual-cam.proj-off #proj-toggle{background:var(--surface2);color:var(--mid);border-color:var(--border)}
body.dual-cam.proj-off .lm-proj-svg{display:none}

/* [MULTICAM-STEP1] Dual-pane layout'''

    if css_anchor in c:
        c = c.replace(css_anchor, css_new, 1)
        print('Frontend 1/4: CSS added')

    # 2. Add SVG overlays inside both panes + the Projections toggle button
    # SVG in pane 1 (inside #canvas-wrap, right before pane-2)
    pane1_anchor = '''    <!-- [MULTICAM-STEP1] 2nd pane -->'''
    pane1_new = '''    <!-- [MULTICAM-STEP23] LM projection overlay for pane 1 -->
    <svg class="lm-proj-svg" id="proj-svg-1" preserveAspectRatio="none"></svg>
    <!-- [MULTICAM-STEP1] 2nd pane -->'''
    if pane1_anchor in c:
        c = c.replace(pane1_anchor, pane1_new, 1)
        print('Frontend 2a/4: pane 1 SVG added')

    # SVG in pane 2
    pane2_anchor = '''      <img id="frame-img-2" src="" draggable="false">
      <div id="no-img-2">Select a camera</div>'''
    pane2_new = '''      <img id="frame-img-2" src="" draggable="false">
      <!-- [MULTICAM-STEP23] LM projection overlay for pane 2 -->
      <svg class="lm-proj-svg" id="proj-svg-2" preserveAspectRatio="none"></svg>
      <div id="no-img-2">Select a camera</div>'''
    if pane2_anchor in c:
        c = c.replace(pane2_anchor, pane2_new, 1)
        print('Frontend 2b/4: pane 2 SVG added')

    # 3. Add Projections toggle button next to Dual
    btn_anchor = '<button class="rays-toggle" id="dual-toggle" title="Compare two cams side-by-side (D)">Dual</button>'
    btn_new = btn_anchor + '''
  <!-- [MULTICAM-STEP23] Toggle ghost LM projections in dual mode -->
  <button class="rays-toggle" id="proj-toggle" title="Show ghost LM projections on the opposite pane">Projections</button>'''
    if btn_anchor in c:
        c = c.replace(btn_anchor, btn_new, 1)
        print('Frontend 3/4: Projections button added')

    # 4. Add JS — fetch projections + render. Append before the [MULTICAM-STEP1] end marker.
    js_anchor = "// ── end [MULTICAM-STEP1] ──────────────────────────────────────────────"
    js_new = '''// ── end [MULTICAM-STEP1] ──────────────────────────────────────────────

// ── [MULTICAM-STEP23] LM projection overlay rendering ─────────────────
// For each pane in dual mode, fetch /api/lm_projections for the OTHER
// pane's cam and draw ghost markers (point for triangulated, line for
// epipolar). Color matches the source-cam-type palette used elsewhere.
(() => {
  const proj1   = document.getElementById('proj-svg-1');
  const proj2   = document.getElementById('proj-svg-2');
  const btnProj = document.getElementById('proj-toggle');
  if (!proj1 || !proj2 || !btnProj) return;

  const SVG_NS = 'http://www.w3.org/2000/svg';
  // Cache fetched projections per cam to avoid hammering the endpoint
  const cache = new Map();  // cam_name -> {projections, cam_size}

  async function fetchProjections(camName) {
    if (!camName) return null;
    if (cache.has(camName)) return cache.get(camName);
    try {
      const r = await fetch('/api/lm_projections?cam=' + encodeURIComponent(camName));
      const d = await r.json();
      if (d.error) {
        console.warn('[MULTICAM-STEP23] error for', camName, d.error);
        return null;
      }
      cache.set(camName, d);
      return d;
    } catch (e) {
      console.warn('[MULTICAM-STEP23] fetch failed for', camName, e);
      return null;
    }
  }

  function clearSvg(svg) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
  }

  function render(svgEl, data, imgEl) {
    clearSvg(svgEl);
    if (!data || !data.projections || !data.projections.length) return;
    const [iw, ih] = data.cam_size;
    // Set the SVG viewBox to match the image's native pixel size; the SVG
    // is laid out at the image's CSS size, so coords inside the viewBox
    // map 1:1 to image pixels regardless of object-fit:contain scaling.
    svgEl.setAttribute('viewBox', `0 0 ${iw} ${ih}`);
    // Match the <img>'s rendered rect so the SVG aligns with the visible image.
    // Image uses object-fit:contain, so the actual image rect inside its
    // box has letterboxing. We compute the rendered rect and position the SVG
    // to match exactly.
    if (imgEl && imgEl.naturalWidth > 0) {
      const cw = imgEl.clientWidth;
      const ch = imgEl.clientHeight;
      const ar = iw / ih;
      const cr = cw / ch;
      let renderW, renderH, offX, offY;
      if (cr > ar) {
        renderH = ch;
        renderW = ch * ar;
        offX = (cw - renderW) / 2;
        offY = 0;
      } else {
        renderW = cw;
        renderH = cw / ar;
        offX = 0;
        offY = (ch - renderH) / 2;
      }
      svgEl.style.left = offX + 'px';
      svgEl.style.top = offY + 'px';
      svgEl.style.width = renderW + 'px';
      svgEl.style.height = renderH + 'px';
    }

    // Color palette — match the rest of the app's LM color scheme.
    const COLOR_POINT = '#a78bfa';   // violet for triangulated
    const COLOR_LINE  = '#4ade80';   // green for epipolar

    for (const p of data.projections) {
      const g = document.createElementNS(SVG_NS, 'g');
      g.setAttribute('class', 'lm-proj-group');
      g.setAttribute('data-lm-name', p.name);

      if (p.type === 'point') {
        const c = document.createElementNS(SVG_NS, 'circle');
        c.setAttribute('cx', String(p.pixel[0]));
        c.setAttribute('cy', String(p.pixel[1]));
        c.setAttribute('r', '12');
        c.setAttribute('stroke', COLOR_POINT);
        c.setAttribute('class', 'lm-proj-point');
        g.appendChild(c);
        const t = document.createElementNS(SVG_NS, 'text');
        t.setAttribute('x', String(p.pixel[0] + 16));
        t.setAttribute('y', String(p.pixel[1] + 5));
        t.setAttribute('class', 'lm-proj-label');
        t.textContent = p.name;
        g.appendChild(t);
      } else if (p.type === 'epipolar') {
        const l = document.createElementNS(SVG_NS, 'line');
        l.setAttribute('x1', String(p.line[0][0]));
        l.setAttribute('y1', String(p.line[0][1]));
        l.setAttribute('x2', String(p.line[1][0]));
        l.setAttribute('y2', String(p.line[1][1]));
        l.setAttribute('stroke', COLOR_LINE);
        l.setAttribute('class', 'lm-proj-line');
        g.appendChild(l);
        const mx = (p.line[0][0] + p.line[1][0]) / 2;
        const my = (p.line[0][1] + p.line[1][1]) / 2;
        const t = document.createElementNS(SVG_NS, 'text');
        t.setAttribute('x', String(mx + 8));
        t.setAttribute('y', String(my));
        t.setAttribute('class', 'lm-proj-label');
        t.textContent = p.name + ' (epi)';
        g.appendChild(t);
      }
      svgEl.appendChild(g);
    }
  }

  async function refresh() {
    if (!document.body.classList.contains('dual-cam')) {
      clearSvg(proj1);
      clearSvg(proj2);
      return;
    }
    if (document.body.classList.contains('proj-off')) {
      clearSvg(proj1);
      clearSvg(proj2);
      return;
    }
    // Each pane shows the OTHER pane's cam projections (so you see where
    // the other cam's LMs would appear in your view).
    const cam1 = window.currentCam;
    const cam2 = window.currentCam2;
    const img1 = document.getElementById('frame-img');
    const img2 = document.getElementById('frame-img-2');

    if (cam1) {
      // Pane 1 shows LMs from cam2's perspective? No -- we want pane 1 to
      // show ghosts of LMs that cam1 itself does NOT have but other cams do.
      // The endpoint already filters: returns LMs not yet marked on this cam.
      // So pane 1 shows projections for cam1 itself.
      const d = await fetchProjections(cam1);
      render(proj1, d, img1);
    } else {
      clearSvg(proj1);
    }
    if (cam2) {
      const d = await fetchProjections(cam2);
      render(proj2, d, img2);
    } else {
      clearSvg(proj2);
    }
  }

  // Hook into dual toggle + cam selection changes
  const origDualBtn = document.getElementById('dual-toggle');
  if (origDualBtn) {
    origDualBtn.addEventListener('click', () => setTimeout(refresh, 50));
  }
  const sel1 = document.getElementById('cam-sel');
  const sel2 = document.getElementById('cam-sel-2');
  if (sel1) sel1.addEventListener('change', () => setTimeout(refresh, 200));
  if (sel2) sel2.addEventListener('change', () => setTimeout(refresh, 200));

  // Also re-render after frame loads (image dimensions become known)
  const img1 = document.getElementById('frame-img');
  const img2 = document.getElementById('frame-img-2');
  if (img1) img1.addEventListener('load', () => setTimeout(refresh, 50));
  if (img2) img2.addEventListener('load', () => setTimeout(refresh, 50));

  // Re-render on window resize (image rect changes)
  window.addEventListener('resize', () => setTimeout(refresh, 100));

  // Projections toggle
  btnProj.addEventListener('click', () => {
    const off = document.body.classList.toggle('proj-off');
    btnProj.classList.toggle('active', !off);
    if (!off) refresh();
  });
  // Default ON
  btnProj.classList.add('active');

  // Hover sync with the LM sidebar list (highlight ghost when hovering list)
  document.addEventListener('mouseover', (e) => {
    const li = e.target.closest('[data-lm-name]');
    if (!li) return;
    const name = li.getAttribute('data-lm-name');
    for (const svg of [proj1, proj2]) {
      svg.querySelectorAll('.lm-proj-group').forEach(g => {
        const match = g.getAttribute('data-lm-name') === name;
        g.querySelectorAll('.lm-proj-point, .lm-proj-line, .lm-proj-label')
          .forEach(el => el.classList.toggle('hovered', match));
      });
    }
  });

  console.log('[MULTICAM-STEP23] projection overlays wired up');
})();
// ── end [MULTICAM-STEP23] ─────────────────────────────────────────────'''

    if js_anchor in c:
        c = c.replace(js_anchor, js_new, 1)
        print('Frontend 4/4: JS injected')

    with open(CALIB, 'w') as f: f.write(c)

print('\nAll patches applied. Restart server, hard refresh browser.')
print('  pkill -f "tools/server.py" ; sleep 1 ; cd ~/Downloads/gtamaplib-main && python3 tools/server.py')
