"""[PORTOFINO-WIREFRAME-V2] Replace edges with full 115-LM mesh."""
import sys, shutil, re

PATH = 'tools/calib.html'
SENTINEL = '[PORTOFINO-WIREFRAME-V2]'

# Build edges programmatically
edges = []

branches = ['NW', 'NE', 'S']
levels = ['B', 'K', 'P', 'T']  # ground, break_top, pent_base, pent_top
corners = ['frontL', 'frontR', 'innerL', 'innerR']

# Pentagons: vertical edges (each corner descends through all 4 levels)
for br in branches:
    for c in corners:
        # Vertical edges between consecutive z levels
        for i in range(len(levels)-1):
            edges.append((f'Portofino Tower ({levels[i]}-{c}-{br})',
                          f'Portofino Tower ({levels[i+1]}-{c}-{br})'))

# Pentagon horizontal connections at each level: peak (T-level) connects frontL/frontR
# Actually pentagons have a 5-corner shape but we removed peaks except top NW/NE/S
# So at T level the pentagon top = frontL → peak → frontR connection (via the existing NW/NE/S)
# At lower levels we just connect frontL-innerL-innerR-frontR via the 4 sides

for br in branches:
    for lvl in levels:
        # Pentagon outline at this level (frontL → innerL → innerR → frontR → back to frontL... but no peak)
        edges.append((f'Portofino Tower ({lvl}-frontL-{br})', f'Portofino Tower ({lvl}-innerL-{br})'))
        edges.append((f'Portofino Tower ({lvl}-innerL-{br})', f'Portofino Tower ({lvl}-innerR-{br})'))
        edges.append((f'Portofino Tower ({lvl}-innerR-{br})', f'Portofino Tower ({lvl}-frontR-{br})'))
        edges.append((f'Portofino Tower ({lvl}-frontR-{br})', f'Portofino Tower ({lvl}-frontL-{br})'))

# Top of pentagon (T level) connects to peak via frontL-peak-frontR
for br in branches:
    edges.append((f'Portofino Tower (T-frontL-{br})', f'Portofino Tower ({br})'))
    edges.append((f'Portofino Tower ({br})', f'Portofino Tower (T-frontR-{br})'))

# Peak boxes: top + base
peak_box_corners = ['pbOL', 'pbOR', 'pbIL', 'pbIR']
for br in branches:
    # Vertical edges (each corner from PB-level=z116 to PT-level=z143)
    for c in peak_box_corners:
        edges.append((f'Portofino Tower (PB-{c}-{br})', f'Portofino Tower (PT-{c}-{br})'))
    # Horizontal: square outline at each level
    for lvl in ['PB', 'PT']:
        edges.append((f'Portofino Tower ({lvl}-pbOL-{br})', f'Portofino Tower ({lvl}-pbOR-{br})'))
        edges.append((f'Portofino Tower ({lvl}-pbOR-{br})', f'Portofino Tower ({lvl}-pbIR-{br})'))
        edges.append((f'Portofino Tower ({lvl}-pbIR-{br})', f'Portofino Tower ({lvl}-pbIL-{br})'))
        edges.append((f'Portofino Tower ({lvl}-pbIL-{br})', f'Portofino Tower ({lvl}-pbOL-{br})'))

# Cylinder: vertical edges + horizontal octagon at each level
cyl_levels = ['B', 'K', 'P', 'T', 'CT']
for i in range(8):
    for j in range(len(cyl_levels)-1):
        edges.append((f'Portofino Tower (cyl-{cyl_levels[j]}-cyl{i})',
                      f'Portofino Tower (cyl-{cyl_levels[j+1]}-cyl{i})'))
for lvl in cyl_levels:
    for i in range(8):
        edges.append((f'Portofino Tower (cyl-{lvl}-cyl{i})',
                      f'Portofino Tower (cyl-{lvl}-cyl{(i+1)%8})'))

# Generate JS array
js_edges = ',\n'.join([f'  [{repr(a)}, {repr(b)}]' for a, b in edges])

NEW_EDGES_BLOCK = f'''// [PORTOFINO-WIREFRAME-V2] Building wireframe overlay
let showWireframes = true;
const PORTOFINO_EDGES = [
{js_edges}
];

const BUILDING_WIREFRAMES = [
  {{ name: 'Portofino Tower', edges: PORTOFINO_EDGES, color: '#ff9d3d' }},
];'''

# Match the V1 block
OLD_PATTERN = re.compile(
    r'// \[PORTOFINO-WIREFRAME-V1\] Building wireframe overlay.*?const BUILDING_WIREFRAMES = \[.*?\];',
    re.DOTALL,
)

with open(PATH) as f: content = f.read()

if SENTINEL in content:
    print('Already applied'); sys.exit(0)

m = OLD_PATTERN.search(content)
if not m:
    print('OLD V1 pattern not found'); sys.exit(1)

new_content = content[:m.start()] + NEW_EDGES_BLOCK + content[m.end():]

apply = '--apply' in sys.argv
if not apply:
    print(f'DRY-RUN. Will replace {m.end()-m.start()} chars with {len(NEW_EDGES_BLOCK)} chars.')
    print(f'Total edges: {len(edges)}')
    sys.exit(0)

shutil.copy(PATH, PATH + '.bak_wireframe_v2')
with open(PATH, 'w') as f: f.write(new_content)
print(f'Applied. {len(edges)} edges.')
