#!/usr/bin/env python3
"""[PORTOFINO-WIREFRAME-V1] Add Portofino building wireframe overlay in calib.html."""
import sys, shutil

PATH = 'tools/calib.html'
SENTINEL = '[PORTOFINO-WIREFRAME-V1]'

# Anchor: the line right after `if (!projections.length) return;` in draw()
OLD = '''  if (!projections.length) return;

  projections.forEach(lm => {'''

NEW = '''  if (!projections.length) return;

  // [PORTOFINO-WIREFRAME-V1] Draw building wireframes before markers
  drawBuildingWireframes();

  projections.forEach(lm => {'''


# Add the wireframe function + edges definition + toggle state + button
# Insert just before `function draw() {` so they're defined before draw runs.
ANCHOR2 = '''function draw() {'''
NEW2 = '''// [PORTOFINO-WIREFRAME-V1] Building wireframe overlay
let showWireframes = true;
const PORTOFINO_EDGES = [
  // Top triangle (3 peaks)
  ['Portofino Tower (NW)', 'Portofino Tower (NE)'],
  ['Portofino Tower (NE)', 'Portofino Tower (S)'],
  ['Portofino Tower (S)',  'Portofino Tower (NW)'],
  // Vertical edges from each peak down through H-L, M-L, P-L, B-L (left side)
  ['Portofino Tower (NW)',    'Portofino Tower (HL-NW)'],
  ['Portofino Tower (HL-NW)', 'Portofino Tower (ML-NW)'],
  ['Portofino Tower (ML-NW)', 'Portofino Tower (PL-NW)'],
  ['Portofino Tower (PL-NW)', 'Portofino Tower (BL-NW)'],
  ['Portofino Tower (NE)',    'Portofino Tower (HL-NE)'],
  ['Portofino Tower (HL-NE)', 'Portofino Tower (ML-NE)'],
  ['Portofino Tower (ML-NE)', 'Portofino Tower (PL-NE)'],
  ['Portofino Tower (PL-NE)', 'Portofino Tower (BL-NE)'],
  ['Portofino Tower (S)',     'Portofino Tower (HL-S)'],
  ['Portofino Tower (HL-S)',  'Portofino Tower (ML-S)'],
  ['Portofino Tower (ML-S)',  'Portofino Tower (PL-S)'],
  ['Portofino Tower (PL-S)',  'Portofino Tower (BL-S)'],
  // Right-side vertical edges (R-)
  ['Portofino Tower (NW)',    'Portofino Tower (HR-NW)'],
  ['Portofino Tower (HR-NW)', 'Portofino Tower (MR-NW)'],
  ['Portofino Tower (MR-NW)', 'Portofino Tower (PR-NW)'],
  ['Portofino Tower (PR-NW)', 'Portofino Tower (BR-NW)'],
  ['Portofino Tower (NE)',    'Portofino Tower (HR-NE)'],
  ['Portofino Tower (HR-NE)', 'Portofino Tower (MR-NE)'],
  ['Portofino Tower (MR-NE)', 'Portofino Tower (PR-NE)'],
  ['Portofino Tower (PR-NE)', 'Portofino Tower (BR-NE)'],
  ['Portofino Tower (S)',     'Portofino Tower (HR-S)'],
  ['Portofino Tower (HR-S)',  'Portofino Tower (MR-S)'],
  ['Portofino Tower (MR-S)',  'Portofino Tower (PR-S)'],
  ['Portofino Tower (PR-S)',  'Portofino Tower (BR-S)'],
  // Horizontal connectors at each level (L-R per branch)
  ['Portofino Tower (HL-NW)', 'Portofino Tower (HR-NW)'],
  ['Portofino Tower (HL-NE)', 'Portofino Tower (HR-NE)'],
  ['Portofino Tower (HL-S)',  'Portofino Tower (HR-S)'],
  ['Portofino Tower (ML-NW)', 'Portofino Tower (MR-NW)'],
  ['Portofino Tower (ML-NE)', 'Portofino Tower (MR-NE)'],
  ['Portofino Tower (ML-S)',  'Portofino Tower (MR-S)'],
  ['Portofino Tower (PL-NW)', 'Portofino Tower (PR-NW)'],
  ['Portofino Tower (PL-NE)', 'Portofino Tower (PR-NE)'],
  ['Portofino Tower (PL-S)',  'Portofino Tower (PR-S)'],
  ['Portofino Tower (BL-NW)', 'Portofino Tower (BR-NW)'],
  ['Portofino Tower (BL-NE)', 'Portofino Tower (BR-NE)'],
  ['Portofino Tower (BL-S)',  'Portofino Tower (BR-S)'],
  // Base outline (3 outer connectors between branches)
  ['Portofino Tower (BR-NW)', 'Portofino Tower (BL-NE)'],
  ['Portofino Tower (BR-NE)', 'Portofino Tower (BL-S)'],
  ['Portofino Tower (BR-S)',  'Portofino Tower (BL-NW)'],
];

const BUILDING_WIREFRAMES = [
  { name: 'Portofino Tower', edges: PORTOFINO_EDGES, color: '#ff9d3d' },
];

function drawBuildingWireframes() {
  if (!showWireframes) return;
  if (!projections.length) return;

  const projMap = {};
  for (const p of projections) {
    if (p.projected) projMap[p.name] = p.projected;
  }

  for (const bld of BUILDING_WIREFRAMES) {
    ctx.strokeStyle = bld.color;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.65;
    ctx.beginPath();
    for (const [a, b] of bld.edges) {
      const pa = projMap[a], pb = projMap[b];
      if (!pa || !pb) continue;
      const [x1, y1] = toCanvas(pa[0], pa[1]);
      const [x2, y2] = toCanvas(pb[0], pb[1]);
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
    }
    ctx.stroke();
    ctx.globalAlpha = 1;
  }
}

function draw() {'''


def main():
    apply = '--apply' in sys.argv
    with open(PATH) as f:
        content = f.read()

    if SENTINEL in content:
        print(f'{SENTINEL} already applied')
        return

    if OLD not in content:
        print('ERROR: OLD block not found'); sys.exit(1)
    if ANCHOR2 not in content:
        print('ERROR: ANCHOR2 not found'); sys.exit(1)

    new_content = content.replace(ANCHOR2, NEW2, 1).replace(OLD, NEW, 1)

    if not apply:
        print('DRY-RUN OK. Run with --apply')
        return

    shutil.copy(PATH, PATH + '.bak_portofino_wireframe')
    with open(PATH, 'w') as f: f.write(new_content)
    print(f'Applied. Backup: {PATH}.bak_portofino_wireframe')


if __name__ == '__main__':
    main()
