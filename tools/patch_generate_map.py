#!/usr/bin/env python3
"""
patch_generate_map.py — Adds the "Generate Map" feature to the calib tool:

Backend:
  - /api/generate_map?cam=NAME: renders top-down map with rays from cam to
    each landmark, colored by angular residual (green <3', yellow 3-10', red >10').
  - /api/generated_map?cam=NAME: serves the generated PNG.

Frontend:
  - Adds a "🗺 Generate Map" button in the calib.html sidebar.
  - On click: calls /api/generate_map, then displays the result in a modal overlay.

Run from gtamaplib-main/:
    python3 tools/patch_generate_map.py
"""
import os
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'tools' \
    else os.path.dirname(os.path.abspath(__file__))

SERVER_PATH = os.path.join(GTAMAP_DIR, 'tools', 'server.py')
HTML_PATH = os.path.join(GTAMAP_DIR, 'tools', 'calib.html')

# ── Patch server.py ───────────────────────────────────────────────────────────

with open(SERVER_PATH) as f:
    server_content = f.read()

if '/api/generate_map' in server_content:
    print("• server.py already has generate_map endpoint")
else:
    # Insert the generate_map endpoint right before /api/cam_health
    GEN_MAP_ENDPOINT = '''
        elif path == '/api/generate_map':
            # Generates a top-down map showing rays from a camera to each
            # of its observed landmarks, colored by angular residual.
            cam_name = unquote(qs.get('cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400)
                return
            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return

            cam_pixels = md.pixels.get(cam_name, {})
            if not cam_pixels:
                self.send_json({'error': 'no pixels for this cam'}, 400)
                return

            # Build (lm_xyz, color) list based on angular residual
            cam_xyz = list(cam.xyz)
            rays = []
            for lm_name, marked_pixel in cam_pixels.items():
                lm_xyz = md.landmarks.get(lm_name)
                if lm_xyz is None:
                    continue
                # Angular residual
                try:
                    proj = cam.get_pixel(lm_xyz)
                    if proj is None:
                        color = (140, 140, 140)  # grey for unprojectable
                    else:
                        dx = (float(proj[0]) - marked_pixel[0]) * cam.hfov / cam.w * 60
                        dy = (float(proj[1]) - marked_pixel[1]) * cam.vfov / cam.h * 60
                        err = math.hypot(dx, dy)
                        if err < 3:
                            color = (74, 222, 128)   # green
                        elif err < 10:
                            color = (245, 158, 11)   # yellow/amber
                        else:
                            color = (248, 113, 113)  # red
                except Exception:
                    color = (140, 140, 140)
                rays.append((list(lm_xyz), color, lm_name))

            # Compute crop area to fit cam + all landmarks with padding
            xs = [cam_xyz[0]] + [r[0][0] for r in rays]
            ys = [cam_xyz[1]] + [r[0][1] for r in rays]
            pad = 200
            x_min, x_max = min(xs) - pad, max(xs) + pad
            y_min, y_max = min(ys) - pad, max(ys) + pad
            area = (x_min, y_min, x_max, y_max)

            # Choose scale to keep image at reasonable size
            world_w = x_max - x_min
            world_h = y_max - y_min
            target_px = 1400
            scale = target_px / max(world_w, world_h)
            scale = max(0.05, min(0.5, scale))

            try:
                m = ml.get_map('yanis')
                m.open(scale=scale, add_padding=False)
                # Draw rays
                for lm_xyz, color, lm_name in rays:
                    line = [(cam_xyz[0], cam_xyz[1]), (lm_xyz[0], lm_xyz[1])]
                    m.draw_line(line, fill=color, width=2)
                # Draw landmark markers (small)
                for lm_xyz, color, lm_name in rays:
                    try:
                        m.draw_landmark(lm_name, r=5)
                    except Exception:
                        pass
                # Draw cam
                m.draw_camera(cam, r=10, d=100)

                # Save
                out_dir = os.path.join(TOOL_DIR, 'generated')
                os.makedirs(out_dir, exist_ok=True)
                # Sanitize filename
                safe_name = ''.join(c if c.isalnum() else '_' for c in cam_name)
                out_path = os.path.join(out_dir, f'{safe_name}_map.png')
                m.save(out_path, crop=area)

                self.send_json({
                    'ok': True,
                    'url': f'/api/generated_map?cam={cam_name}',
                    'n_rays': len(rays),
                })
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'error': f'render failed: {e}'}, 500)

        elif path == '/api/generated_map':
            cam_name = unquote(qs.get('cam', [''])[0])
            safe_name = ''.join(c if c.isalnum() else '_' for c in cam_name)
            out_path = os.path.join(TOOL_DIR, 'generated', f'{safe_name}_map.png')
            if os.path.exists(out_path):
                self.send_file(out_path, 'image/png')
            else:
                self.send_response(404)
                self.end_headers()

'''

    INSERTION_MARKER = "        elif path == '/api/cam_health':"
    if INSERTION_MARKER in server_content:
        server_content = server_content.replace(INSERTION_MARKER, GEN_MAP_ENDPOINT + INSERTION_MARKER)
        with open(SERVER_PATH, 'w') as f:
            f.write(server_content)
        print("✓ Added /api/generate_map and /api/generated_map endpoints")
    else:
        print("✗ Could not find insertion point. Manual patch needed.")
        sys.exit(1)

# ── Patch calib.html ──────────────────────────────────────────────────────────

with open(HTML_PATH) as f:
    html_content = f.read()

if 'btn-genmap' in html_content:
    print("• calib.html already has Generate Map button")
else:
    # Add CSS for the button + modal
    NEW_CSS = """
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
.genmap-legend-dot{width:10px;height:10px;border-radius:2px}
"""

    # Insert CSS before closing </style>
    html_content = html_content.replace('</style>', NEW_CSS + '</style>', 1)
    print("✓ Added CSS")

    # Add the button in the sidebar (insert before opt-result or similar)
    # Find the .opt-bar section and add the button right after it
    OPT_BAR_END = '<div id="opt-result"'
    BUTTON_HTML = '<button id="btn-genmap" disabled>🗺 Generate Map</button>\n'

    # Find a reasonable place - after the optimize button block
    # Look for the opt-bar div ending
    import re
    # Insert right before "<!-- Position -->" or wherever is a clean spot
    # Use a more reliable anchor: the .sb-sec containing position
    POS_ANCHOR = '<div class="sb-sec">\n  <div class="sb-title">Position</div>'
    if POS_ANCHOR in html_content:
        html_content = html_content.replace(
            POS_ANCHOR,
            BUTTON_HTML + POS_ANCHOR
        )
        print("✓ Added button before Position section")
    else:
        # Fallback: just find sidebar div
        SIDEBAR_ANCHOR = '<div class="sidebar">'
        html_content = html_content.replace(
            SIDEBAR_ANCHOR,
            SIDEBAR_ANCHOR + '\n' + BUTTON_HTML
        )
        print("✓ Added button at top of sidebar (fallback)")

    # Add modal HTML right before closing </body>
    MODAL_HTML = """
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
  </div>
</div>
"""
    html_content = html_content.replace('</body>', MODAL_HTML + '</body>', 1)
    print("✓ Added modal HTML")

    # Add JS handler before </script>
    JS_HANDLER = """
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
const _origCamChange = document.getElementById('cam-sel').onchange;
document.getElementById('cam-sel').addEventListener('change', () => {
  setTimeout(() => {
    btnGenmap.disabled = !currentCam;
  }, 100);
});
"""
    html_content = html_content.replace('</script>', JS_HANDLER + '</script>', 1)
    print("✓ Added JS handler")

with open(HTML_PATH, 'w') as f:
    f.write(html_content)

print(f"\n✓ All patches applied")
print(f"\nNext steps:")
print(f"  1. Restart server: lsof -ti :8765 | xargs kill -9; python3 tools/server.py")
print(f"  2. Hard reload calib.html (Cmd+Shift+R)")
print(f"  3. Select a cam, click '🗺 Generate Map'")
