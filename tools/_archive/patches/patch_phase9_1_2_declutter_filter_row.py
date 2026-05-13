#!/usr/bin/env python3
"""
patch_phase9_1_2_declutter_filter_row.py — drop Bad filter + move +Add

Phase 9.1 added a sort dropdown to the lm-list filter row, making it too
crowded ("All / Indep / Bad / +Add / sort original"). This patch:

  1. Drops the "Bad" filter button. Use sort by "error ↓" instead — same
     functional outcome (worst residuals at top), without a separate filter.
  2. Moves the "+Add" button to the lm-list header row, next to the
     "Landmarks (N)" count. It's not really a filter, it's an action.

Result: filter row becomes cleaner — "All / Indep / sort: original".

Idempotent. Builds on Phase 9.1.1.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_phase9_1_2'

SENTINEL = '/* Phase 9.1.2: declutter filter row */'
PHASE9_1_1_SENTINEL = '/* Phase 9.1.1: fix window.currentCam ref */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — Drop the Bad filter and move +Add to the lm-list header.
# Anchor: the entire .lm-filters block including its parent's title row.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
      <div class="sb-title" style="margin:0">Landmarks (<span id="lm-count">0</span>)</div>
      <div class="lm-filters">
        <button class="f-btn on" onclick="setFilter('all',this)">All</button>
        <button class="f-btn" onclick="setFilter('indep',this)">Indep</button>
        <button class="f-btn" onclick="setFilter('bad',this)">Bad</button>
        <button class="f-btn" id="btn-add-px" onclick="openAddPixel()" style="color:var(--green);border-color:var(--green)">+ Add</button>
        <span class="lm-sort-wrap">
          <span class="sort-lbl">sort</span>
          <select id="lm-sort" onchange="setLmSort(this.value)">
            <option value="original">original</option>
            <option value="name">name</option>
            <option value="error">error ↓</option>
            <option value="indep">indep first</option>
          </select>
        </span>
      </div>"""

HUNK_1_NEW = """\
      <div class="sb-title" style="margin:0;display:flex;align-items:center;gap:8px;flex:1">
        <span>Landmarks (<span id="lm-count">0</span>)</span>
        <button class="f-btn" id="btn-add-px" onclick="openAddPixel()" style="color:var(--green);border-color:var(--green);font-size:10px;padding:2px 6px">+ Add</button>
      </div>
      <!-- Phase 9.1.2: dropped Bad filter (sort by error ↓ does the same) -->
      <div class="lm-filters">
        <button class="f-btn on" onclick="setFilter('all',this)">All</button>
        <button class="f-btn" onclick="setFilter('indep',this)">Indep</button>
        <span class="lm-sort-wrap">
          <span class="sort-lbl">sort</span>
          <select id="lm-sort" onchange="setLmSort(this.value)">
            <option value="original">original</option>
            <option value="name">name</option>
            <option value="error">error ↓</option>
            <option value="indep">indep first</option>
          </select>
        </span>
      </div>"""


HUNKS = [
    ('HTML — drop Bad filter + move +Add to header', HUNK_1_OLD, HUNK_1_NEW),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--revert', action='store_true')
    args = ap.parse_args()

    if not os.path.exists(CALIB_HTML):
        print(f'ERROR: {CALIB_HTML} not found.')
        sys.exit(1)

    if args.revert:
        if not os.path.exists(BACKUP):
            print(f'ERROR: no backup at {BACKUP}.')
            sys.exit(1)
        if args.apply:
            shutil.copy(BACKUP, CALIB_HTML)
            print(f'✓ Restored.')
        else:
            print('(dry-run) would restore.')
        return

    with open(CALIB_HTML, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print('✓ Already patched.')
        return
    if PHASE9_1_1_SENTINEL not in src:
        print('ERROR: Phase 9.1.1 sentinel not found.')
        sys.exit(1)

    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} (need 1).')
            sys.exit(1)

    new_src = src
    for _label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)
    new_src = new_src.replace(PHASE9_1_1_SENTINEL,
                              PHASE9_1_1_SENTINEL + '\n' + SENTINEL, 1)

    delta = new_src.count('\n') - src.count('\n')
    print(f'Will modify {CALIB_HTML} ({delta:+d} lines)')
    print(f'  hunks applied: {len(HUNKS)}')

    if not args.apply:
        print('\n(dry-run — re-run with --apply)')
        return

    shutil.copy(CALIB_HTML, BACKUP)
    print(f'\n✓ Backup: {BACKUP}')
    tmp = CALIB_HTML + '.tmp'
    with open(tmp, 'w') as f:
        f.write(new_src)
    os.replace(tmp, CALIB_HTML)
    print(f'✓ Patched {CALIB_HTML}')
    print()
    print('Test: hard reload. Filter row now: "All / Indep / sort: original"')
    print('+Add moved next to "Landmarks (N)" header.')


if __name__ == '__main__':
    main()
