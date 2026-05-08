#!/usr/bin/env python3
"""
patch_server_threading.py — make server.py multi-threaded

Problem: server.py uses HTTPServer (single-threaded). Every request runs
in series. When a cam switch fires 4 parallel HTTP requests from the
browser (frame, project, other_cams_overlay, minimap), they queue up
and run serially. Total time = sum of all request times.

The /api/minimap endpoint takes ~5s (large bitmap crop+resize), so even
though everything else is fast, the minimap blocks frame loading,
projection updates, etc.

Fix: replace HTTPServer with ThreadingHTTPServer. Each request gets its
own thread. The 4 parallel requests now actually run in parallel, and
total time = max instead of sum. Cam switch lag drops from ~10-12s to
the slowest single request (~5s for minimap, ~1-2s for others).

Bonus: subsequent UI interactions don't block while minimap is still
finishing — you can change cam again without waiting.

Single-line change. Idempotent. Backup created.

Usage:
  python3 tools/patch_server_threading.py            # dry-run
  python3 tools/patch_server_threading.py --apply
  python3 tools/patch_server_threading.py --revert --apply
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_PY = os.path.join(THIS_DIR, 'server.py')
BACKUP = SERVER_PY + '.bak_threading'

SENTINEL = '# Threading fix: parallel request handling'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — change the import to bring in ThreadingHTTPServer
# Anchor: the existing import line.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """from http.server import BaseHTTPRequestHandler, HTTPServer"""
HUNK_1_NEW = """# Threading fix: parallel request handling
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — change HTTPServer instantiation to ThreadingHTTPServer
# Anchor: the server creation line.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """    server = HTTPServer(('localhost', port), Handler)"""
HUNK_2_NEW = """    server = ThreadingHTTPServer(('localhost', port), Handler)"""


HUNKS = [
    ('1 (import ThreadingHTTPServer)', HUNK_1_OLD, HUNK_1_NEW),
    ('2 (instantiate ThreadingHTTPServer instead of HTTPServer)', HUNK_2_OLD, HUNK_2_NEW),
]


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
        return

    with open(SERVER_PY, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print('✓ Already patched.')
        return

    failures = []
    for label, old, new in HUNKS:
        n = src.count(old)
        if n != 1:
            failures.append(f'  hunk {label}: anchor matches {n} times (need exactly 1)')

    if failures:
        print('ERROR: hunk pre-flight failed:')
        print('\n'.join(failures))
        sys.exit(1)

    new_src = src
    for label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    delta = new_src.count('\n') - src.count('\n')
    print(f'Will modify {SERVER_PY} ({delta:+d} lines)')

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
    print('Restart the server (Ctrl+C and relaunch) for the change to take effect.')


if __name__ == '__main__':
    main()
