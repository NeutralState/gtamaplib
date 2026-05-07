#!/usr/bin/env python3
"""
patch_svg_phase2.py — SVG Map Refactor Phase 2: left sidebar (cam picker)

Moves the camera picker from the header into a permanent collapsible left
sidebar. Functionally a no-op for everything else: the hidden <select id="cam-sel">
remains the source of truth, all camSel.value/dispatchEvent('change') calls
keep working, the dropdown DOM (#cam-dropdown) is repurposed as a permanent
list inside the sidebar, and search + filter chips behave identically.

Bonus: defines --purple in :root (the existing CSS rule on the SS chip
references it, but it was never declared — silent inheritance bug fix).
Also drops the orphaned .cam-picker CSS rule (no longer used after move).

The patch is split into 5 hunks. Each hunk has its own anchor and is checked
for uniqueness before replacing. If any hunk fails, NOTHING is written.

Idempotent: re-running this patch is a no-op (detects the global sentinel).
Dry-run by default. Use --apply to actually write changes.
A backup is created at calib.html.bak_svg_phase2 before any write.

Usage:
  python3 tools/patch_svg_phase2.py            # dry-run
  python3 tools/patch_svg_phase2.py --apply    # apply changes
  python3 tools/patch_svg_phase2.py --revert --apply   # restore from backup
"""

import argparse
import os
import shutil
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase2'

# Global sentinel — present in HUNK_1_NEW (the CSS comment block).
# If found in the file, we consider it already patched.
SENTINEL = '/* ── SVG Map Refactor Phase 2: left sidebar styles ── */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS:
#   - Add --purple to :root (silent bug fix: existing rule references it).
#   - Add styles for left sidebar (.left-sidebar, .ls-header, .ls-list, etc.)
#   - Override .cam-dropdown to render as permanent list (no absolute, no .open).
# Anchor is the existing :root block (matches once).
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
:root {
  --bg:#0a0a0c; --surface:#13131a; --surface2:#1c1c26; --border:#252535;
  --green:#4ade80; --yellow:#f59e0b; --red:#f87171; --blue:#60a5fa;
  --text:#e2e2f0; --dim:#5a5a7a; --mid:#9090b0;
  --mono:'JetBrains Mono',monospace; --sans:'DM Sans',sans-serif;
}"""

HUNK_1_NEW = """\
:root {
  --bg:#0a0a0c; --surface:#13131a; --surface2:#1c1c26; --border:#252535;
  --green:#4ade80; --yellow:#f59e0b; --red:#f87171; --blue:#60a5fa;
  --purple:#a78bfa;
  --text:#e2e2f0; --dim:#5a5a7a; --mid:#9090b0;
  --mono:'JetBrains Mono',monospace; --sans:'DM Sans',sans-serif;
}

/* ── SVG Map Refactor Phase 2: left sidebar styles ── */
.cam-toggle-btn{font-family:var(--mono);font-size:14px;padding:4px 9px;border-radius:5px;border:1px solid var(--border);background:var(--surface2);color:var(--mid);cursor:pointer;line-height:1;user-select:none}
.cam-toggle-btn:hover{color:var(--text);border-color:var(--mid)}
.left-sidebar{width:260px;flex-shrink:0;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;transition:width .18s ease-out}
.left-sidebar.collapsed{width:0;border-right:none}
.ls-header{padding:10px 12px;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:8px;flex-shrink:0}
.ls-header #cam-search{font-family:var(--mono);font-size:11px;background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 9px;border-radius:5px;width:100%}
.ls-header #cam-search:focus{outline:none;border-color:var(--green)}
.ls-filter-chips{display:flex;flex-wrap:wrap;gap:4px}
.ls-list{flex:1;overflow-y:auto;background:var(--surface)}
.ls-list::-webkit-scrollbar{width:3px}
.ls-list::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
/* The .cam-dropdown rule below was originally absolute-positioned + hidden
   by default. Phase 2 repurposes it as a permanent list inside .ls-list,
   so we override position and display via the wrapping .left-sidebar. */
.left-sidebar #cam-dropdown{position:static;display:block;border:none;border-radius:0;max-height:none;margin-top:0;background:transparent}
/* ── end SVG Map Refactor Phase 2 ── */"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — drop orphaned .cam-picker CSS rule:
#   The class is no longer used anywhere in the HTML after the move, so the
#   rule does nothing. Cleaner repo.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
/* Cam search + filter */
.cam-picker{position:relative;display:flex;align-items:center;gap:6px;flex:1;max-width:520px}
"""

HUNK_2_NEW = """\
/* Cam search + filter (Phase 2: .cam-picker rule dropped — moved to left sidebar) */
"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — HEADER HTML:
#   - Remove the cam-picker block + hidden select from <header>.
#   - Add the burger toggle button before .logo.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
<header>
  <div class="logo">gtamaplib</div>
<a href="/cam_health.html" class="nav-link">→ Dashboard</a>
  <div class="cam-picker">
  <input id="cam-search" placeholder="Search camera..." autocomplete="off" />
  <button class="cam-filter-chip on" data-type="LEAK">LEAK</button>
  <button class="cam-filter-chip on" data-type="Trailer 1">T1</button>
  <button class="cam-filter-chip on" data-type="Trailer 2">T2</button>
  <button class="cam-filter-chip on" data-type="screenshots">SS</button>
  <div class="cam-dropdown" id="cam-dropdown"></div>
  <select id="cam-sel"><option value="">— Select camera —</option></select>
</div>
  <span id="cam-meta"></span>"""

HUNK_3_NEW = """\
<header>
  <button class="cam-toggle-btn" id="cam-toggle-btn" title="Toggle camera list">≡</button>
  <div class="logo">gtamaplib</div>
<a href="/cam_health.html" class="nav-link">→ Dashboard</a>
  <span id="cam-meta"></span>"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 4 — MAIN HTML:
#   - Insert the new left sidebar (with cam picker DOM moved inside) at the
#     start of <div class="main">, before <div class="canvas-wrap">.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_4_OLD = """\
<div class="main">
  <div class="canvas-wrap" id="canvas-wrap">"""

HUNK_4_NEW = """\
<div class="main">
  <aside class="left-sidebar" id="left-sidebar">
    <div class="ls-header">
      <input id="cam-search" placeholder="Search camera..." autocomplete="off" />
      <div class="ls-filter-chips">
        <button class="cam-filter-chip on" data-type="LEAK">LEAK</button>
        <button class="cam-filter-chip on" data-type="Trailer 1">T1</button>
        <button class="cam-filter-chip on" data-type="Trailer 2">T2</button>
        <button class="cam-filter-chip on" data-type="screenshots">SS</button>
      </div>
    </div>
    <div class="ls-list">
      <div class="cam-dropdown" id="cam-dropdown"></div>
    </div>
    <select id="cam-sel" hidden><option value="">— Select camera —</option></select>
  </aside>
  <div class="canvas-wrap" id="canvas-wrap">"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 5 — JS init() rewiring:
#   - Drop the .open dropdown logic (the list is permanent now).
#   - Add the burger toggle handler.
# Anchor matches the existing 'Wire up cam picker' block.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_5_OLD = """\
  // Wire up cam picker
  const camSearch = document.getElementById('cam-search');
  const camDropdown = document.getElementById('cam-dropdown');
  camSearch.addEventListener('input', e => { camSearchQ = e.target.value; renderCamDropdown(); camDropdown.classList.add('open'); });
  camSearch.addEventListener('focus', () => { renderCamDropdown(); camDropdown.classList.add('open'); });
  document.addEventListener('click', e => {
    if (!e.target.closest('.cam-picker')) camDropdown.classList.remove('open');
  });
  camDropdown.addEventListener('click', e => {
    const opt = e.target.closest('.cam-opt[data-name]');
    if (!opt) return;
    const name = opt.dataset.name;
    camSel.value = name;
    camSearch.value = name;
    camDropdown.classList.remove('open');
    camSel.dispatchEvent(new Event('change'));
  });"""

HUNK_5_NEW = """\
  // Wire up cam picker (Phase 2: permanent list in left sidebar — no .open class)
  const camSearch = document.getElementById('cam-search');
  const camDropdown = document.getElementById('cam-dropdown');
  // Initial render so the list is populated even before user interacts.
  renderCamDropdown();
  camSearch.addEventListener('input', e => { camSearchQ = e.target.value; renderCamDropdown(); });
  camDropdown.addEventListener('click', e => {
    const opt = e.target.closest('.cam-opt[data-name]');
    if (!opt) return;
    const name = opt.dataset.name;
    camSel.value = name;
    camSearch.value = name;
    camSel.dispatchEvent(new Event('change'));
  });
  // Burger toggle for the left sidebar (session-only, no localStorage)
  const leftSidebar = document.getElementById('left-sidebar');
  const camToggleBtn = document.getElementById('cam-toggle-btn');
  if (camToggleBtn && leftSidebar) {
    camToggleBtn.addEventListener('click', () => {
      leftSidebar.classList.toggle('collapsed');
    });
  }"""


HUNKS = [
    ('1 (CSS: --purple, left-sidebar styles)', HUNK_1_OLD, HUNK_1_NEW),
    ('2 (CSS: drop orphaned .cam-picker rule)', HUNK_2_OLD, HUNK_2_NEW),
    ('3 (header: drop cam-picker, add burger)', HUNK_3_OLD, HUNK_3_NEW),
    ('4 (main: insert left sidebar)', HUNK_4_OLD, HUNK_4_NEW),
    ('5 (JS init: rewire picker, add toggle)', HUNK_5_OLD, HUNK_5_NEW),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true',
                    help='actually write changes (default: dry-run)')
    ap.add_argument('--revert', action='store_true',
                    help='restore calib.html from .bak_svg_phase2 backup')
    args = ap.parse_args()

    if not os.path.exists(CALIB_HTML):
        print(f'ERROR: {CALIB_HTML} not found.')
        print('       Run this script from inside the gtamaplib repo (tools/ dir).')
        sys.exit(1)

    if args.revert:
        if not os.path.exists(BACKUP):
            print(f'ERROR: no backup at {BACKUP}.')
            sys.exit(1)
        if args.apply:
            shutil.copy(BACKUP, CALIB_HTML)
            print(f'✓ Restored {CALIB_HTML} from {BACKUP}.')
        else:
            print(f'(dry-run) would restore {CALIB_HTML} from {BACKUP}.')
            print('Re-run with --revert --apply to actually revert.')
        return

    with open(CALIB_HTML, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print(f'✓ Already patched (sentinel found).')
        print('  No changes needed. Use --revert --apply if you want to undo.')
        return

    # Pre-flight: every hunk must match exactly once. If any fails, abort.
    failures = []
    for label, old, new in HUNKS:
        n = src.count(old)
        if n != 1:
            failures.append(f'  hunk {label}: anchor matches {n} times (need exactly 1)')

    if failures:
        print('ERROR: hunk pre-flight failed (file structure may have drifted):')
        print('\n'.join(failures))
        print('\nThe file was NOT modified. Investigate, then either fix the anchors')
        print('in this script or fix the file to match.')
        sys.exit(1)

    # Apply hunks in order to a copy.
    new_src = src
    for label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    if new_src == src:
        print('ERROR: replace was a no-op (this should not happen).')
        sys.exit(1)

    delta_lines = new_src.count('\n') - src.count('\n')
    print(f'Will modify {CALIB_HTML}')
    print(f'  hunks applied: {len(HUNKS)}')
    print(f'  net line delta: {delta_lines:+d}')
    print()
    for label, _, _ in HUNKS:
        print(f'  ✓ hunk {label}')

    if not args.apply:
        print('\n(dry-run — re-run with --apply to write changes)')
        return

    # Backup, then atomic write.
    shutil.copy(CALIB_HTML, BACKUP)
    print(f'\n✓ Backup: {BACKUP}')
    tmp = CALIB_HTML + '.tmp'
    with open(tmp, 'w') as f:
        f.write(new_src)
    os.replace(tmp, CALIB_HTML)
    print(f'✓ Patched {CALIB_HTML}')
    print()
    print('Next steps:')
    print('  1. Reload localhost:8765 in browser (no server restart needed — pure HTML)')
    print('  2. Run the manual test checklist (see chat)')
    print('  3. If anything is broken: python3 tools/patch_svg_phase2.py --revert --apply')
    print('  4. If all good:')
    print('     git add tools/calib.html')
    print('     git commit -m "Phase 2: move cam picker to collapsible left sidebar"')
    print('     mv tools/patch_svg_phase2.py tools/_archive/patches/')
    print('     git add tools/_archive/patches/patch_svg_phase2.py')
    print('     git commit -m "Archive Phase 2 patch"')
    print('     git push')


if __name__ == '__main__':
    main()
