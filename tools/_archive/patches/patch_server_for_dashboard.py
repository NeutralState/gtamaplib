#!/usr/bin/env python3
"""
patch_server_for_dashboard.py — adds the /api/cam_health endpoint to
tools/server.py and a route for /cam_health.html.

Run from gtamaplib-main/:
    python3 patch_server_for_dashboard.py

Idempotent: skips if the endpoint already exists.
"""
import os
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_PATH = os.path.join(GTAMAP_DIR, 'tools', 'server.py')

with open(SERVER_PATH) as f:
    content = f.read()

# ── Patch 1: Add the route for cam_health.html ────────────────────────────────
ROUTE_OLD = "        if path in ('/', '/index.html', '/calib.html'):\n            self.send_file(os.path.join(TOOL_DIR, 'calib.html'), 'text/html')"
ROUTE_NEW = """        if path in ('/', '/index.html', '/calib.html'):
            self.send_file(os.path.join(TOOL_DIR, 'calib.html'), 'text/html')

        elif path == '/cam_health.html':
            self.send_file(os.path.join(TOOL_DIR, 'cam_health.html'), 'text/html')"""

if "/cam_health.html" not in content:
    content = content.replace(ROUTE_OLD, ROUTE_NEW)
    print("✓ Added /cam_health.html route")
else:
    print("• /cam_health.html route already exists")

# ── Patch 2: Add /api/cam_health endpoint ─────────────────────────────────────
ENDPOINT = '''
        elif path == '/api/cam_health':
            # Per-cam health metrics. Reuses compute_projections to get
            # angular residuals from the current calibration state.
            import statistics
            import re as _re_local
            result = []
            for name in sorted(md.cameras):
                if not md.cameras[name].get('xyz'):
                    continue
                try:
                    projs, losses = compute_projections(name)
                except Exception:
                    continue

                errs = [p['delta'] for p in projs if p['delta'] is not None]
                indep_errs = [p['delta'] for p in projs
                              if p['delta'] is not None and not p['is_circular']]

                if not errs:
                    continue

                cam_data = md.cameras[name]
                source = cam_data.get('source') or ''
                is_leak = bool(_re_local.match(r'\\d{4}-\\d{2}-\\d{2}', source))
                is_trailer = source.startswith('Trailer')
                source_type = 'LEAK' if is_leak else ('TRAILER' if is_trailer else 'community')

                loss_val = losses['independent'] if losses['independent'] is not None else losses['total']
                loss = round(loss_val or 0, 2)
                median_err = round(statistics.median(errs), 2)
                max_err = round(max(errs), 2)
                worst_lm = max(projs, key=lambda p: p['delta'] if p['delta'] is not None else -1)['name']

                if loss > 15 or max_err > 60:
                    status = 'broken'
                elif loss > 5 or median_err > 4 or len(indep_errs) < 4:
                    status = 'suspicious'
                else:
                    status = 'healthy'

                result.append({
                    'name': name,
                    'source_type': source_type,
                    'loss': loss,
                    'median_err': median_err,
                    'max_err': max_err,
                    'worst_lm': worst_lm,
                    'n_pixels': len(projs),
                    'n_indep': len(indep_errs),
                    'status': status,
                })

            status_order = {'broken': 0, 'suspicious': 1, 'healthy': 2}
            result.sort(key=lambda r: (status_order[r['status']], -r['loss']))

            total_pixels = sum(r['n_pixels'] for r in result)
            global_rms = (sum(r['loss']**2 * r['n_pixels'] for r in result) /
                          max(1, total_pixels)) ** 0.5 if result else 0

            summary = {
                'total': len(result),
                'broken': sum(1 for r in result if r['status'] == 'broken'),
                'suspicious': sum(1 for r in result if r['status'] == 'suspicious'),
                'healthy': sum(1 for r in result if r['status'] == 'healthy'),
                'global_rms': round(global_rms, 3),
            }

            self.send_json({'cams': result, 'summary': summary})
'''

# Insert after /api/cameras endpoint (find its closing self.send_json(result))
INSERTION_MARKER = "                })\n            self.send_json(result)\n\n        elif path == '/api/project':"

if "/api/cam_health" not in content:
    if INSERTION_MARKER in content:
        new_marker = INSERTION_MARKER.replace(
            "            self.send_json(result)\n\n        elif path == '/api/project':",
            "            self.send_json(result)\n" + ENDPOINT + "\n        elif path == '/api/project':"
        )
        content = content.replace(INSERTION_MARKER, new_marker)
        print("✓ Added /api/cam_health endpoint")
    else:
        print("✗ Could not find insertion point. Manual patch needed.")
        sys.exit(1)
else:
    print("• /api/cam_health endpoint already exists")

with open(SERVER_PATH, 'w') as f:
    f.write(content)

print(f"\n✓ Patched {SERVER_PATH}")
print(f"\nNext steps:")
print(f"  1. Make sure cam_health.html is in tools/")
print(f"  2. Restart server: lsof -ti :8765 | xargs kill -9; python3 tools/server.py")
print(f"  3. Open http://localhost:8765/cam_health.html")
