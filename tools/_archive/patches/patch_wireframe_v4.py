"""[PORTOFINO-WIREFRAME-V4] Update edges for new z-level labels."""
import sys, shutil, re

PATH = 'tools/calib.html'
SENTINEL = '[PORTOFINO-WIREFRAME-V4]'

edges = []
branches = ['NW', 'NE', 'S']
levels = ['B', 'K', 'L', 'P']  # ground, base_top, break_top (pent_base), pent_top
corners = ['frontL', 'frontR', 'innerL', 'innerR']

# Pentagon vertical edges
for br in branches:
    for c in corners:
        for i in range(len(levels)-1):
            edges.append((f'Portofino Tower ({levels[i]}-{c}-{br})',
                          f'Portofino Tower ({levels[i+1]}-{c}-{br})'))

# Pentagon horizontal at each level
for br in branches:
    for lvl in levels:
        edges.append((f'Portofino Tower ({lvl}-frontL-{br})', f'Portofino Tower ({lvl}-innerL-{br})'))
        edges.append((f'Portofino Tower ({lvl}-innerL-{br})', f'Portofino Tower ({lvl}-innerR-{br})'))
        edges.append((f'Portofino Tower ({lvl}-innerR-{br})', f'Portofino Tower ({lvl}-frontR-{br})'))
        edges.append((f'Portofino Tower ({lvl}-frontR-{br})', f'Portofino Tower ({lvl}-frontL-{br})'))

# At pent_top (P level), connect frontL → peak → frontR (peak = NW/NE/S)
# But peaks are at z=143, not z=125 (P level), so we skip this connection
# Instead: at PB-level (base of peak box, z=125) the box base sits on the pentagon top
# So connect each peak box corner at PB to the pentagon top corners
# Actually it's cleaner to leave peaks isolated at z=143 and box connects them

# Peak boxes: PB (z=125, base) to PT (z=143, top)
peak_box_corners = ['pbOL', 'pbOR', 'pbIL', 'pbIR']
for br in branches:
    for c in peak_box_corners:
        edges.append((f'Portofino Tower (PB-{c}-{br})', f'Portofino Tower (PT-{c}-{br})'))
    for lvl in ['PB', 'PT']:
        edges.append((f'Portofino Tower ({lvl}-pbOL-{br})', f'Portofino Tower ({lvl}-pbOR-{br})'))
        edges.append((f'Portofino Tower ({lvl}-pbOR-{br})', f'Portofino Tower ({lvl}-pbIR-{br})'))
        edges.append((f'Portofino Tower ({lvl}-pbIR-{br})', f'Portofino Tower ({lvl}-pbIL-{br})'))
        edges.append((f'Portofino Tower ({lvl}-pbIL-{br})', f'Portofino Tower ({lvl}-pbOL-{br})'))
    # Connect peak boxes top center to NW/NE/S anchor
    edges.append((f'Portofino Tower (PT-pbOL-{br})', f'Portofino Tower ({br})'))
    edges.append((f'Portofino Tower (PT-pbOR-{br})', f'Portofino Tower ({br})'))

# Cylinder: vertical edges + horizontal octagon at each level
cyl_levels = ['B', 'K', 'L', 'P', 'CT']
for i in range(8):
    for j in range(len(cyl_levels)-1):
        edges.append((f'Portofino Tower (cyl-{cyl_levels[j]}-cyl{i})',
                      f'Portofino Tower (cyl-{cyl_levels[j+1]}-cyl{i})'))
for lvl in cyl_levels:
    for i in range(8):
        edges.append((f'Portofino Tower (cyl-{lvl}-cyl{i})',
                      f'Portofino Tower (cyl-{lvl}-cyl{(i+1)%8})'))

js_edges = ',\n'.join([f'  [{repr(a)}, {repr(b)}]' for a, b in edges])

NEW_BLOCK = f'''// [PORTOFINO-WIREFRAME-V4] Building wireframe overlay
let showWireframes = true;
const PORTOFINO_EDGES = [
{js_edges}
];

const BUILDING_WIREFRAMES = [
  {{ name: 'Portofino Tower', edges: PORTOFINO_EDGES, color: '#ff9d3d' }},
];'''

OLD_PATTERN = re.compile(
    r'// \[PORTOFINO-WIREFRAME-V[23]\] Building wireframe overlay.*?const BUILDING_WIREFRAMES = \[.*?\];',
    re.DOTALL,
)

with open(PATH) as f: content = f.read()
if SENTINEL in content:
    print('Already applied'); sys.exit(0)
m = OLD_PATTERN.search(content)
if not m:
    print('OLD V2/V3 pattern not found'); sys.exit(1)

new_content = content[:m.start()] + NEW_BLOCK + content[m.end():]
apply = '--apply' in sys.argv
if not apply:
    print(f'DRY-RUN. {len(edges)} edges. Old block: {m.end()-m.start()} chars. New: {len(NEW_BLOCK)} chars.')
    sys.exit(0)

shutil.copy(PATH, PATH + '.bak_wireframe_v4')
with open(PATH, 'w') as f: f.write(new_content)
print(f'Applied. {len(edges)} edges.')
