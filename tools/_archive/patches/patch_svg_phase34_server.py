#!/usr/bin/env python3
"""
patch_svg_phase34_server.py — switch /yanis.svg endpoint to /yanis.png

Phase 3+4 originally served a vector SVG as the map asset, but with 85 MB
of paths the browser couldn't keep pan/zoom interactive. We pivoted to a
pre-rendered 4K PNG (~4 MB), which loads instantly and is GPU-friendly.

This patch only touches server.py:
  - the endpoint URL changes from /yanis.svg to /yanis.png
  - the served file changes from tools/assets/yanis_v11.svg to .../yanis_v11.png
  - Content-Type changes accordingly

Cache-Control header stays at 1h.

Idempotent. Dry-run by default. Backup created.

Usage:
  python3 tools/patch_svg_phase34_server.py            # dry-run
  python3 tools/patch_svg_phase34_server.py --apply
  python3 tools/patch_svg_phase34_server.py --revert --apply
"""

import argparse
import os
import shutil
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_PY = os.path.join(THIS_DIR, 'server.py')
BACKUP = SERVER_PY + '.bak_phase34_png'

# Sentinel: HUNK_NEW contains a comment that will identify "already patched"
SENTINEL = '# Phase 3+4 PNG: serves the rasterized 4K map'


HUNK_OLD = """\
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
            self.wfile.write(data)"""

HUNK_NEW = """\
        elif path == '/yanis.png':
            # Phase 3+4 PNG: serves the rasterized 4K map (replaces the
            # original /yanis.svg endpoint — the 85MB vector was too heavy
            # for the browser to pan/zoom interactively. The PNG is rendered
            # offline with rsvg-convert from the original SVG and committed
            # to the repo. World→image transform: see /api/map_data response.
            png_path = os.path.join(TOOL_DIR, 'assets', 'yanis_v11.png')
            if not os.path.exists(png_path):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'yanis_v11.png not found in tools/assets/')
                return
            with open(png_path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', len(data))
            # Asset is immutable — 1h cache.
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            self.wfile.write(data)"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--revert', action='store_true')
    args = ap.parse_args()

    if not os.path.exists(SERVER_PY):
        print(f'ERROR: {SERVER_PY} not found.')
        sys.exit(1)

    if args.revert:
        if not os.path.exists(BACKUP):
            print(f'ERROR: no backup at {BACKUP}.')
            sys.exit(1)
        if args.apply:
            shutil.copy(BACKUP, SERVER_PY)
            print(f'✓ Restored {SERVER_PY} from {BACKUP}.')
        else:
            print(f'(dry-run) would restore from {BACKUP}.')
            print('Re-run with --revert --apply.')
        return

    with open(SERVER_PY, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print('✓ Already patched.')
        print('  Use --revert --apply to undo.')
        return

    n = src.count(HUNK_OLD)
    if n != 1:
        print(f'ERROR: anchor matches {n} times (need exactly 1).')
        print('       Phase 1 may have been reverted, or the file structure has drifted.')
        sys.exit(1)

    new_src = src.replace(HUNK_OLD, HUNK_NEW, 1)
    delta = new_src.count('\n') - src.count('\n')
    print(f'Will modify {SERVER_PY}')
    print(f'  net line delta: {delta:+d}')
    print(f'  endpoint: GET /yanis.svg  ->  GET /yanis.png')
    print(f'  asset:    yanis_v11.svg   ->  yanis_v11.png')

    if not args.apply:
        print('\n(dry-run — re-run with --apply)')
        return

    shutil.copy(SERVER_PY, BACKUP)
    print(f'\n✓ Backup: {BACKUP}')
    tmp = SERVER_PY + '.tmp'
    with open(tmp, 'w') as f:
        f.write(new_src)
    os.replace(tmp, SERVER_PY)
    print(f'✓ Patched {SERVER_PY}')
    print()
    print('Test:')
    print('  Restart server.py')
    print('  curl -I http://localhost:8765/yanis.png')
    print('  Should return HTTP 200 with Content-Type: image/png')


if __name__ == '__main__':
    main()
