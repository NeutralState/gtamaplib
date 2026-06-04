"""
Building meshes wiring patch.

1. Copy gtamapdata/building_meshes.json into place
2. Server: add /api/building_meshes endpoint that reads the JSON and
   expands edges from suffixes to full LM names with xyz coords
3. Frontend: replace hardcoded BUILDING_WIREFRAMES with fetch from /api/building_meshes
   on load. Portofino kept hardcoded (it uses PORTOFINO_EDGES which is
   procedurally generated) but joined with the fetched data.

Idempotent: marker [MESH-FRONTEND-V1].
"""

import os
import sys
import shutil

REPO = os.path.expanduser('~/Downloads/gtamaplib-main')
SERVER = os.path.join(REPO, 'tools', 'server.py')
CALIB = os.path.join(REPO, 'tools', 'calib.html')
MESH_JSON_SRC = os.path.expanduser('~/Downloads/building_meshes.json')
MESH_JSON_DST = os.path.join(REPO, 'gtamapdata', 'building_meshes.json')

with open(SERVER) as f: s = f.read()
with open(CALIB) as f: c = f.read()

if '[MESH-FRONTEND-V1]' in c:
    print('Already patched.')
    sys.exit(0)

# Backups
with open(SERVER + '.bak_mesh_v1', 'w') as f: f.write(s)
with open(CALIB + '.bak_mesh_v1', 'w') as f: f.write(c)
print('Backups created')

# ── Step 1: Copy JSON file ─────────────────────────────────────────────
if os.path.exists(MESH_JSON_SRC):
    shutil.copy(MESH_JSON_SRC, MESH_JSON_DST)
    print(f'JSON copied to {MESH_JSON_DST}')
elif os.path.exists(MESH_JSON_DST):
    print(f'JSON already exists at destination')
else:
    print(f'WARN: building_meshes.json not found in ~/Downloads/, you need to place it manually at {MESH_JSON_DST}')

# ── Step 2: Add server endpoint ────────────────────────────────────────
# Insert right before the /api/cameras endpoint
endpoint_anchor = "        elif path == '/api/cameras':"

endpoint_code = '''        elif path == '/api/building_meshes':
            # [MESH-FRONTEND-V1] Return building wireframe meshes.
            # Reads gtamapdata/building_meshes.json and expands edges from
            # LM suffixes to full LM names. Skips edges with missing LMs.
            import json as _json
            mesh_path = os.path.join(GTAMAP_DIR, 'gtamapdata', 'building_meshes.json')
            if not os.path.exists(mesh_path):
                self.send_json({'meshes': {}})
                return
            try:
                with open(mesh_path) as _f:
                    meshes = _json.load(_f)
            except Exception as e:
                self.send_json({'error': f'failed to load: {e}'}, 500)
                return
            result = {}
            for building_name, mesh_data in meshes.items():
                if building_name.startswith('_'): continue  # skip _comment
                edges = mesh_data.get('edges')
                if not edges: continue  # no edges defined (e.g. Portofino procedural)
                color = mesh_data.get('color', '#ff9d3d')
                expanded_edges = []
                for a, b in edges:
                    full_a = f'{building_name} ({a})'
                    full_b = f'{building_name} ({b})'
                    if full_a in md.landmarks and full_b in md.landmarks:
                        expanded_edges.append([full_a, full_b])
                if expanded_edges:
                    result[building_name] = {
                        'color': color,
                        'edges': expanded_edges,
                    }
            self.send_json({'meshes': result})

        elif path == '/api/cameras':'''

if endpoint_anchor in s:
    s = s.replace(endpoint_anchor, endpoint_code, 1)
    print('Server: /api/building_meshes endpoint added')
else:
    print('WARN: anchor /api/cameras not found')

# Ensure GTAMAP_DIR is defined; check around the imports
if 'GTAMAP_DIR =' not in s:
    print('WARN: GTAMAP_DIR not defined in server.py. Using __file__ fallback.')
    # Add a definition near the top
    fallback = 'GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
    # Insert after imports
    import_end = s.find('\n\n', s.find('import '))
    s = s[:import_end] + '\n' + fallback + s[import_end:]
    print('Server: GTAMAP_DIR fallback added')

with open(SERVER, 'w') as f: f.write(s)

# ── Step 3: Frontend — fetch building meshes on load ───────────────────
# Find the BUILDING_WIREFRAMES const and wrap the draw function to use fetched data
old_wireframes = '''const BUILDING_WIREFRAMES = [
  { name: 'Portofino Tower', edges: PORTOFINO_EDGES, color: '#ff9d3d' },
];'''

new_wireframes = '''const BUILDING_WIREFRAMES = [
  { name: 'Portofino Tower', edges: PORTOFINO_EDGES, color: '#ff9d3d' },
];

// [MESH-FRONTEND-V1] Fetch building meshes from server and append to wireframes list
(async function loadBuildingMeshes() {
  try {
    const res = await fetch('/api/building_meshes');
    if (!res.ok) return;
    const data = await res.json();
    if (!data.meshes) return;
    for (const [bldName, meshInfo] of Object.entries(data.meshes)) {
      // Skip if already in the hardcoded list (e.g. Portofino)
      if (BUILDING_WIREFRAMES.some(b => b.name === bldName)) continue;
      // Server returns edges as [[full_name1, full_name2], ...]
      BUILDING_WIREFRAMES.push({
        name: bldName,
        edges: meshInfo.edges,
        color: meshInfo.color || '#ff9d3d',
      });
    }
    console.log('[MESH-FRONTEND-V1] loaded', BUILDING_WIREFRAMES.length, 'building meshes');
    // Re-render if we're already showing wireframes
    if (typeof draw === 'function') draw();
  } catch (e) {
    console.warn('[MESH-FRONTEND-V1] mesh fetch failed:', e);
  }
})();'''

if old_wireframes in c:
    c = c.replace(old_wireframes, new_wireframes, 1)
    print('Frontend: BUILDING_WIREFRAMES extended with fetch loader')
else:
    print('ERROR: BUILDING_WIREFRAMES anchor not found')

with open(CALIB, 'w') as f: f.write(c)
print('\nDone. Restart server, hard refresh, view Four Seasons or Sunshine Skyway from any cam that sees them.')
