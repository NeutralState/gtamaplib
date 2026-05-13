#!/usr/bin/env python3
"""
patch_svg_phase8_2_drop_ray_map.py — drop ray-map-modal + /api/ray_map

Phase 8.1 moved triangulation viz onto the Map view and removed all
showRayMap callsites. Phase 8.2 finishes the cleanup:

  - calib.html: drop the #ray-map-modal HTML block
  - server.py:  drop the /api/ray_map handler

The showRayMap() JS function is intentionally left in place as dead
code — it's never called now (Phase 8.1 removed all callsites) and
removing it requires anchoring on its full body which we can't see
without re-grepping. A future cleanup can drop it. If anyone calls it
by mistake, it will fail gracefully (the modal element is gone).

Idempotent. Builds on Phase 8.1.1.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
SERVER_PY = os.path.join(THIS_DIR, 'server.py')
BACKUP_HTML = CALIB_HTML + '.bak_svg_phase8_2'
BACKUP_PY = SERVER_PY + '.bak_svg_phase8_2'

SENTINEL_HTML = '<!-- Phase 8.2: #ray-map-modal removed -->'
SENTINEL_PY = '# Phase 8.2: /api/ray_map removed'
PHASE8_1_SENTINEL = '/* Phase 8.1: triangulate on Map view + drop showRayMap callsites */'


HUNK_HTML_1_OLD = """\
<div id="ray-map-modal" style="display:none;position:fixed;inset:0;background:#000d;z-index:350;align-items:center;justify-content:center">
  <div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:0;width:700px;max-width:95vw;overflow:hidden">
    <div style="display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid var(--border)">
      <div style="font-family:var(--mono);font-size:12px;font-weight:700;color:var(--green);flex:1" id="ray-map-title">Ray Visualization</div>
      <button onclick="document.getElementById('ray-map-modal').style.display='none'" style="background:transparent;border:none;color:var(--dim);font-size:18px;cursor:pointer">✕</button>
    </div>
    <div id="ray-map-body" style="padding:16px;text-align:center">
      <div style="font-family:var(--mono);font-size:11px;color:var(--dim)">Loading map...</div>
    </div>
    <div style="padding:10px 16px;border-top:1px solid var(--border);font-family:var(--mono);font-size:10px;color:var(--dim)" id="ray-map-info">—</div>
  </div>
</div>"""

HUNK_HTML_1_NEW = """\
<!-- Phase 8.2: #ray-map-modal removed (replaced by Phase 8.1 Map view tri-rays). -->"""


HUNK_PY_1_OLD = """        elif path == '/api/ray_map':
            # Generate map image with rays from specified cameras
            import subprocess, tempfile, base64
            cam_names = qs.get('cams', [''])[0].split(',')
            cam_names = [unquote(c) for c in cam_names if c]
            lm_name = unquote(qs.get('lm', [''])[0]) if 'lm' in qs else None

            script = f\"\"\"
import sys
sys.path.insert(0, '{GTAMAP_DIR}')
import gtamaplib as ml
import gtamapdata as md

cam_names = {cam_names!r}
lm_name = {lm_name!r}

xs, ys = [], []
for cn in cam_names:
    try:
        cam = ml.get_camera(cn)
        xs.append(cam.xyz[0])
        ys.append(cam.xyz[1])
    except: pass

if lm_name:
    lm_xyz = md.landmarks.get(lm_name)
    if lm_xyz:
        xs.append(lm_xyz[0])
        ys.append(lm_xyz[1])

cx = sum(xs)/len(xs) if xs else 0
cy = sum(ys)/len(ys) if ys else 0
padding = 3000
area = (int(cx-padding), int(cy-padding), int(cx+padding), int(cy+padding))

m = ml.get_map('yanis').open(scale=1.0, add_padding=True)

# Build per-landmark color palette using HSV-distributed RGB
import colorsys
def landmark_color(idx, total):
    h = (idx * 0.618033988749895) % 1.0  # golden ratio for max separation
    r, g, b = colorsys.hsv_to_rgb(h, 0.85, 1.0)
    return (int(r*255), int(g*255), int(b*255))

# Collect all unique landmarks across all cams to assign stable colors
all_lms = set()
for cn in cam_names:
    all_lms.update(md.pixels.get(cn, {{}}).keys())
lm_to_color = {{ln: landmark_color(i, len(all_lms)) for i, ln in enumerate(sorted(all_lms))}}

# First pass: draw all landmark rays
for cn in cam_names:
    try:
        cam = ml.get_camera(cn)
        cam_pixels = md.pixels.get(cn, {{}})
        for ln in cam_pixels:
            try:
                d = cam.get_landmark_direction(ln)
                if d is None: continue
                target_xy = ml.get_point(cam.xyz, d, 30000)[:2]
                color = lm_to_color.get(ln, (200, 200, 200))
                width = 4 if (lm_name and ln == lm_name) else 2
                m.draw_line((cam.xy, target_xy), color, width)
            except: pass
    except Exception as e:
        print(f'Error rays {{cn}}: {{e}}')

# Second pass: draw camera frustum on top in BLACK (thicker, more visible)
for cn in cam_names:
    try:
        cam = ml.get_camera(cn)
        # frustum edges (black, width 4) — manually drawn since draw_camera uses white
        for x in (0, cam.w):
            edge_dir = cam.get_pixel_direction((x, cam.h / 2))
            target_xy = ml.get_point(cam.xyz, edge_dir, 30000)[:2]
            m.draw_line((cam.xy, target_xy), (0, 0, 0), 4)
        # cam marker
        m.draw_circle(cam.xy, 8, (255, 255, 255), cam.color, 2, cam.name[0])
    except Exception as e:
        print(f'Error frustum {{cn}}: {{e}}')

if lm_name and md.landmarks.get(lm_name):
    m.draw_landmark(lm_name)

m.save('/tmp/ray_map.png', area)
\"\"\"
            try:
                import subprocess
                result = subprocess.run(['python3', '-c', script],
                    capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    self.send_json({'error': result.stderr[:200]}, 500)
                    return
                with open('/tmp/ray_map.png', 'rb') as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                self.send_json({'image': img_b64})
            except Exception as e:
                self.send_json({'error': str(e)}, 500)

        elif path == '/api/delete_pixel':"""

HUNK_PY_1_NEW = """        # Phase 8.2: /api/ray_map removed. Triangulation viz now lives
        # in the Map view (Phase 8.1: showTriangulationOnMap in calib.html).

        elif path == '/api/delete_pixel':"""


HUNKS_HTML = [
    ('HTML — drop #ray-map-modal block', HUNK_HTML_1_OLD, HUNK_HTML_1_NEW),
]
HUNKS_PY = [
    ('PY — drop /api/ray_map handler',   HUNK_PY_1_OLD,   HUNK_PY_1_NEW),
]


def patch_file(path, sentinel, prereq_sentinel, hunks, label):
    if not os.path.exists(path):
        print(f'ERROR: {path} not found.')
        sys.exit(1)
    with open(path, 'r') as f:
        src = f.read()
    if sentinel in src:
        print(f'  ✓ {label} already patched.')
        return src, src, 0
    if prereq_sentinel and prereq_sentinel not in src:
        print(f'ERROR: {label} prereq sentinel not found.')
        print(f'       Expected: {prereq_sentinel!r}')
        sys.exit(1)
    for hlabel, old, _new in hunks:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: {label} hunk "{hlabel}" anchor matches {n} (need 1).')
            sys.exit(1)
    new_src = src
    for _hlabel, old, new in hunks:
        new_src = new_src.replace(old, new, 1)
    delta = new_src.count('\n') - src.count('\n')
    print(f'  Will modify {path} ({delta:+d} lines, {len(hunks)} hunks)')
    return src, new_src, len(hunks)


def write_with_backup(path, backup_path, new_src):
    shutil.copy(path, backup_path)
    print(f'  ✓ Backup: {backup_path}')
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        f.write(new_src)
    os.replace(tmp, path)
    print(f'  ✓ Patched {path}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--revert', action='store_true')
    args = ap.parse_args()

    if args.revert:
        if not os.path.exists(BACKUP_HTML) or not os.path.exists(BACKUP_PY):
            print(f'ERROR: backups missing.')
            sys.exit(1)
        if args.apply:
            shutil.copy(BACKUP_HTML, CALIB_HTML)
            shutil.copy(BACKUP_PY, SERVER_PY)
            print(f'✓ Restored from backups.')
        else:
            print(f'(dry-run) would restore from {BACKUP_HTML} and {BACKUP_PY}.')
        return

    print('═══ Phase 8.2 — drop ray-map-modal + /api/ray_map ═══\n')

    print('calib.html:')
    src_html, new_html, nh = patch_file(
        CALIB_HTML, SENTINEL_HTML, PHASE8_1_SENTINEL, HUNKS_HTML, 'calib.html')

    print('\nserver.py:')
    src_py, new_py, np_ = patch_file(
        SERVER_PY, SENTINEL_PY, None, HUNKS_PY, 'server.py')

    print(f'\nTotal hunks ready: {nh + np_}')

    if not args.apply:
        print('\n(dry-run — re-run with --apply)')
        return

    print('\nApplying:')
    if nh > 0:
        write_with_backup(CALIB_HTML, BACKUP_HTML, new_html)
    if np_ > 0:
        write_with_backup(SERVER_PY, BACKUP_PY, new_py)

    print()
    print('Test:')
    print('  1. Restart server: lsof -ti:8765 | xargs kill -9; python3 tools/server.py')
    print('  2. Hard reload Safari (Cmd+Shift+R).')
    print('  3. Triangulate a landmark — should still work via Map view.')
    print('  4. Click Optimize on a cam — no modal pops, just the loss chip.')
    print()
    print('Note: showRayMap() JS function is intentionally left as dead code.')


if __name__ == '__main__':
    main()
