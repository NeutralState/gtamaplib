#!/usr/bin/env python3
"""
patch_svg_phase1.py — SVG Map Refactor Phase 1: backend endpoints

Adds two new GET routes to tools/server.py:
  - /yanis.svg          : serves tools/assets/yanis_v11.svg as static SVG
  - /api/map_data       : returns JSON dump of cams + landmarks + transform
                          for the new SVG-based map view (replaces eventual
                          /api/generate_map and /api/ray_map in Phase 8).

Idempotent: re-running this patch is a no-op (detects markers).
Dry-run by default. Use --apply to actually write changes.
A backup is created at server.py.bak_svg_phase1 before any write.

Usage:
  python3 tools/patch_svg_phase1.py                # dry-run
  python3 tools/patch_svg_phase1.py --apply        # apply changes
  python3 tools/patch_svg_phase1.py --revert       # restore from backup
"""

import argparse
import os
import shutil
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_PY = os.path.join(THIS_DIR, 'server.py')
BACKUP = SERVER_PY + '.bak_svg_phase1'

# Idempotence sentinel — used by both endpoints we add.
SENTINEL = '# ── SVG Map Refactor (Phase 1) ─────────────────────────────'

# Anchor: we insert the new endpoints right BEFORE this existing line so
# they sit cleanly with the other GET endpoints, near the top of do_GET.
# We pick /api/cameras because it's the first generic "list everything"
# endpoint; our /api/map_data is a richer cousin of it.
INSERT_BEFORE = "        elif path == '/api/cameras':"

NEW_BLOCK = '''\
        # ── SVG Map Refactor (Phase 1) ─────────────────────────────
        # Two endpoints powering the new full-screen SVG map view.
        # See tools/CLAUDE_CONTEXT.md > "SVG Map View Refactor" for context.

        elif path == '/yanis.svg':
            # Serves the vector yanis map as a static asset.
            # World→SVG transform: see /api/map_data response.
            svg_path = os.path.join(TOOL_DIR, 'assets', 'yanis_v11.svg')
            if not os.path.exists(svg_path):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'yanis_v11.svg not found in tools/assets/')
                return
            with open(svg_path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'image/svg+xml')
            self.send_header('Content-Length', len(data))
            # Asset is immutable for this session — 1h cache so the browser
            # doesn't re-download ~85MB on every reload during dev.
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            self.wfile.write(data)

        elif path == '/api/map_data':
            # Single dump used by the SVG map view at load time. After this,
            # all interactivity is client-side except for /api/triangulate
            # (which already exists) and a triangulate refresh loop.
            #
            # Transform (world → SVG pixel space):
            #   svg_x = world_x + 16500
            #   svg_y = (-world_y) + 12000     [y_sign = -1]
            # Origin sits at zero=[16500, 12000] in a 20000x20000 viewBox.
            # Y is flipped because SVG pixel-y grows downward while world-y
            # grows northward — confirmed by gtamaputils.find_aiwe() which
            # maps aiwe_top=North and aiwe_bottom=South.
            # TODO(phase1.5): load these from md.maps['yanis'] dynamically
            #   instead of hardcoding (gtamapdata exposes the same values).

            # Cameras: only those with xyz (otherwise they can't be placed
            # on the map). For each we mirror what /api/cameras returns,
            # plus the per-cam color used by /api/other_cams_overlay.
            cams_out = []
            for name, cam_data in md.cameras.items():
                if not cam_data.get('xyz'):
                    continue
                cam_pixels = md.pixels.get(name, {})
                n_indep = sum(
                    1 for lm in cam_pixels
                    if md.landmarks.get(lm) is not None
                    and name not in md.landmarks_meta.get(lm, {}).get('source_cameras', [])
                )
                fov = cam_data.get('fov')
                hfov = float(fov[0]) if fov and fov[0] is not None else None
                # Color: the Camera object owns it (used by other_cams_overlay).
                # get_camera is @lru_cache'd in gtamaplib so this is cheap.
                try:
                    color = [int(v) for v in ml.get_camera(name).color]
                except Exception:
                    color = [200, 200, 200]
                cams_out.append({
                    'name': name,
                    'xyz': [float(v) for v in cam_data['xyz']],
                    'ypr': [float(v) for v in cam_data['ypr']] if cam_data.get('ypr') else None,
                    'hfov': hfov,
                    'size': list(cam_data['size']) if cam_data.get('size') else None,
                    'source': cam_data.get('source'),
                    'type': _classify_cam(name),
                    'color': color,
                    'n_pixels': len(cam_pixels),
                    'n_independent': n_indep,
                })

            # Landmarks: include ALL of them — even those without xyz, since
            # the Map view will offer Triangulate on them. Phase 6 frontend
            # will render unxyz'd LMs differently.
            lms_out = []
            for name, meta in md.landmarks_meta.items():
                xyz = md.landmarks.get(name)
                source_cameras = list(meta.get('source_cameras') or [])
                lms_out.append({
                    'name': name,
                    'xyz': [float(v) for v in xyz] if xyz is not None else None,
                    'source_cameras': source_cameras,
                    'n_sources': len(source_cameras),
                    'error_m': meta.get('error_m'),
                    'zone': meta.get('zone'),
                    'is_leak_anchored': name in LEAK_ANCHORED_LMS,
                    'z_constraint': meta.get('z_constraint'),
                })

            # Sort: stable ordering helps the frontend diff updates and makes
            # the JSON diffable for debugging. Cams by name, lms by name.
            cams_out.sort(key=lambda c: c['name'])
            lms_out.sort(key=lambda l: l['name'])

            self.send_json({
                'transform': {
                    'world_offset': [16500, 12000],
                    'world_scale': 1.0,
                    'y_sign': -1,
                    'svg_size': [20000, 20000],
                    'map_name': 'yanis',
                },
                'cameras': cams_out,
                'landmarks': lms_out,
                'counts': {
                    'cameras': len(cams_out),
                    'landmarks': len(lms_out),
                    'landmarks_with_xyz': sum(1 for l in lms_out if l['xyz'] is not None),
                    'landmarks_leak_anchored': sum(1 for l in lms_out if l['is_leak_anchored']),
                },
            })

        # ── end SVG Map Refactor (Phase 1) ─────────────────────────

'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true',
                    help='actually write changes (default: dry-run)')
    ap.add_argument('--revert', action='store_true',
                    help='restore server.py from .bak_svg_phase1 backup')
    args = ap.parse_args()

    if not os.path.exists(SERVER_PY):
        print(f'ERROR: {SERVER_PY} not found.')
        print('       Run this script from inside the gtamaplib repo (tools/ dir).')
        sys.exit(1)

    if args.revert:
        if not os.path.exists(BACKUP):
            print(f'ERROR: no backup at {BACKUP}.')
            sys.exit(1)
        if args.apply:
            shutil.copy(BACKUP, SERVER_PY)
            print(f'✓ Restored {SERVER_PY} from {BACKUP}.')
        else:
            print(f'(dry-run) would restore {SERVER_PY} from {BACKUP}.')
            print('Re-run with --apply to actually revert.')
        return

    with open(SERVER_PY, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print(f'✓ Already patched (sentinel "{SENTINEL[:40]}..." found).')
        print('  No changes needed. Use --revert if you want to undo.')
        return

    if INSERT_BEFORE not in src:
        print(f'ERROR: anchor not found in {SERVER_PY}:')
        print(f'       {INSERT_BEFORE!r}')
        print('       The file structure may have changed. Aborting.')
        sys.exit(1)

    if src.count(INSERT_BEFORE) > 1:
        print(f'ERROR: anchor appears {src.count(INSERT_BEFORE)} times in {SERVER_PY}.')
        print('       Refusing to patch — anchor is ambiguous.')
        sys.exit(1)

    new_src = src.replace(INSERT_BEFORE, NEW_BLOCK + INSERT_BEFORE)

    if new_src == src:
        print('ERROR: replace was a no-op (this should not happen).')
        sys.exit(1)

    delta_lines = new_src.count('\n') - src.count('\n')
    print(f'Will insert {delta_lines} lines into {SERVER_PY}')
    print(f'  before:  {INSERT_BEFORE.strip()}')
    print(f'  adds:    GET /yanis.svg, GET /api/map_data')

    if not args.apply:
        print('\n(dry-run — re-run with --apply to write changes)')
        return

    # Backup, then write atomically.
    shutil.copy(SERVER_PY, BACKUP)
    print(f'✓ Backup: {BACKUP}')
    tmp = SERVER_PY + '.tmp'
    with open(tmp, 'w') as f:
        f.write(new_src)
    os.replace(tmp, SERVER_PY)
    print(f'✓ Patched {SERVER_PY}')
    print()
    print('Next steps:')
    print('  1. Restart server.py')
    print('  2. Run the curl tests (see plan in chat)')
    print('  3. git add tools/server.py tools/patch_svg_phase1.py')
    print('  4. git commit -m "Phase 1: backend endpoints for SVG map view"')
    print('  5. (after testing) git mv tools/patch_svg_phase1.py tools/_archive/patches/')


if __name__ == '__main__':
    main()
