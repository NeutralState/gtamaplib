#!/usr/bin/env python3
"""
patch_phase9_1_url_hash_and_sort.py — URL hash state + landmark sort

Two small features:

  1. URL hash state — persists cam selected, view mode (camera/map), and
     sort selection in location.hash so reloads restore context. Format:
       #cam=<encoded>&view=map&sort=error
     Read on page load; updated on cam-change, view-change, sort-change.

  2. Landmark sort — sort dropdown in the lm-list filter row:
       - "original" (default, current behavior)
       - "name"     (alphabetical)
       - "error"    (highest error first, untriangulated last)
       - "indep"    (indep landmarks first, then by error)

Idempotent. Builds on Phase 8.2.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_phase9_1'

SENTINEL = '/* Phase 9.1: URL hash state + landmark sort */'
PHASE8_2_SENTINEL = '<!-- Phase 8.2: #ray-map-modal removed'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS for the sort dropdown. Inject after the lm-filters CSS block.
# Anchor on a stable existing rule.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """.lm-list{flex:1;overflow-y:auto}"""

HUNK_1_NEW = """.lm-list{flex:1;overflow-y:auto}
/* Phase 9.1: sort dropdown styling */
.lm-sort-wrap{display:inline-flex;align-items:center;gap:4px;margin-left:6px}
.lm-sort-wrap select{font-family:var(--mono);font-size:10px;
  background:var(--surface2);color:var(--text);
  border:1px solid var(--border);border-radius:4px;
  padding:2px 4px;outline:none;cursor:pointer}
.lm-sort-wrap select:hover{border-color:var(--mid)}
.lm-sort-wrap .sort-lbl{font-size:9px;color:var(--dim)}"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — Add sort dropdown HTML to the lm-filters row.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
      <div class="lm-filters">
        <button class="f-btn on" onclick="setFilter('all',this)">All</button>
        <button class="f-btn" onclick="setFilter('indep',this)">Indep</button>
        <button class="f-btn" onclick="setFilter('bad',this)">Bad</button>
        <button class="f-btn" id="btn-add-px" onclick="openAddPixel()" style="color:var(--green);border-color:var(--green)">+ Add</button>
      </div>"""

HUNK_2_NEW = """\
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


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — Add the JS state + helper functions + URL hash machinery.
# Inject after the existing State block (after `let dirty = false, ...`).
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
let dirty = false, optimizing = false, lmFilter = 'all';"""

HUNK_3_NEW = """\
let dirty = false, optimizing = false, lmFilter = 'all';
// Phase 9.1: URL hash state + landmark sort
let lmSort = 'original';
function _readUrlHash() {
  const h = location.hash.replace(/^#/, '');
  if (!h) return {};
  const out = {};
  for (const part of h.split('&')) {
    const [k, v] = part.split('=');
    if (k && v !== undefined) out[k] = decodeURIComponent(v);
  }
  return out;
}
function _writeUrlHash(state) {
  // Only include non-default values to keep URL clean.
  const parts = [];
  if (state.cam) parts.push('cam=' + encodeURIComponent(state.cam));
  if (state.view && state.view !== 'camera') parts.push('view=' + encodeURIComponent(state.view));
  if (state.sort && state.sort !== 'original') parts.push('sort=' + encodeURIComponent(state.sort));
  const h = parts.length ? '#' + parts.join('&') : '';
  if (location.hash !== h) {
    history.replaceState(null, '', location.pathname + location.search + h);
  }
}
function _syncUrlHash() {
  _writeUrlHash({
    cam: window.currentCam || null,
    view: document.body.classList.contains('view-map') ? 'map' : 'camera',
    sort: lmSort
  });
}
function setLmSort(value) {
  lmSort = value || 'original';
  _syncUrlHash();
  // Re-render the lm-list with the new sort.
  if (typeof window.loadProjections === 'function') {
    window.loadProjections();
  }
}
window.setLmSort = setLmSort;
window._syncUrlHash = _syncUrlHash;"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 4 — Hook into setView() to sync URL on view change.
# Anchor: the existing setView function definition.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_4_OLD = """\
  window.setView = setView;"""

HUNK_4_NEW = """\
  window.setView = setView;
  // Phase 9.1: sync URL hash whenever view changes.
  const _origSetView = setView;
  window.setView = function(name) {
    _origSetView(name);
    if (typeof window._syncUrlHash === 'function') window._syncUrlHash();
  };"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 5 — Hook into camSel change handler to sync URL on cam change.
# Anchor: the existing currentCam = camSel.value line in the handler.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_5_OLD = """\
camSel.addEventListener('change', async () => {
  currentCam = camSel.value || null;
  if (!currentCam) return;"""

HUNK_5_NEW = """\
camSel.addEventListener('change', async () => {
  currentCam = camSel.value || null;
  // Phase 9.1: sync URL hash on cam change.
  if (typeof window._syncUrlHash === 'function') window._syncUrlHash();
  if (!currentCam) return;"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 6 — Restore state from URL hash on page load.
# Anchor: end of </script>. We add an init block that fires after main load.
# We place the restore inside a setTimeout to ensure mapData and camSel are
# populated before we try to set the cam.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_6_OLD = """\
<!-- Phase 8.1: triangulation toast (top-center over map view). -->"""

HUNK_6_NEW = """\
<script>
// Phase 9.1: restore state from URL hash on initial load.
window.addEventListener('load', () => {
  setTimeout(() => {
    try {
      const state = (function(){
        const h = location.hash.replace(/^#/, '');
        if (!h) return {};
        const out = {};
        for (const part of h.split('&')) {
          const [k, v] = part.split('=');
          if (k && v !== undefined) out[k] = decodeURIComponent(v);
        }
        return out;
      })();
      // Restore sort first (cheap, doesn't trigger a fetch).
      if (state.sort) {
        const sel = document.getElementById('lm-sort');
        if (sel) {
          sel.value = state.sort;
          if (typeof window.setLmSort === 'function') window.setLmSort(state.sort);
        }
      }
      // Restore cam (will trigger frame load + projections).
      if (state.cam) {
        const camSel = document.getElementById('cam-sel');
        if (camSel) {
          camSel.value = state.cam;
          camSel.dispatchEvent(new Event('change'));
        }
      }
      // Restore view (toggle map view if requested).
      if (state.view === 'map') {
        if (typeof window.setView === 'function') window.setView('map');
      }
    } catch (e) {
      console.warn('[hash-restore] failed:', e);
    }
  }, 200);
});
</script>

<!-- Phase 8.1: triangulation toast (top-center over map view). -->"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 7 — Apply the sort to the lm-list rendering. We need to find where
# the lm-list <div> is populated. Looking at the grep, line 606 is the
# DOM ref, line 508 is the HTML element. The actual render lives in the
# loadProjections function or similar. Since we don't have visibility into
# the render code, we'll do a runtime sort by inserting a sort step after
# the lm-list innerHTML is set.
#
# Simpler approach: hook into the rendering by sorting children of #lm-list
# after each render, via a MutationObserver or by patching the function
# that does the rendering. The cleanest is to add a window-level helper
# that re-orders the existing DOM children based on data-attributes.
#
# Looking at the screenshot showing "Billboard (Delights)  5.60", the
# lm-items have visible error values. We need to find the render function.
# Without seeing it, a pragmatic approach: add a MutationObserver on
# #lm-list that re-sorts whenever children change.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_7_OLD = """\
let dirty = false, optimizing = false, lmFilter = 'all';
// Phase 9.1: URL hash state + landmark sort"""

HUNK_7_NEW = """\
let dirty = false, optimizing = false, lmFilter = 'all';
// Phase 9.1: sort observer — reorders #lm-list children based on lmSort.
// Triggers whenever lm-list children change (the existing render code
// blindly innerHTML='' and rebuilds). We just reorder after the fact.
function _applyLmSort() {
  if (lmSort === 'original') return;
  const list = document.getElementById('lm-list');
  if (!list || !list.children.length) return;
  const items = Array.from(list.children).filter(el => el.classList.contains('lm-item'));
  if (items.length < 2) return;
  // Extract sort key from each item.
  function getKey(el) {
    const name = (el.querySelector('.lm-name')?.textContent || '').trim();
    // Error: parse the visible delta number (e.g. "5.60") from the right side.
    // It's typically the last numeric content node, formatted like "5.60" or "—".
    const errText = (el.querySelector('.lm-err, .lm-delta')?.textContent
      || el.textContent.match(/\\b(\\d+\\.\\d+)\\b\\s*$/)?.[0] || '').trim();
    const err = parseFloat(errText);
    const isIndep = el.classList.contains('lm-indep') ||
                    !!el.querySelector('.lm-indep') ||
                    /indep/i.test(el.className);
    const isUntri = el.classList.contains('untriangulated');
    return { name: name.toLowerCase(), err: isNaN(err) ? Infinity : err, isIndep, isUntri };
  }
  const sorted = items.slice().sort((a, b) => {
    const ka = getKey(a), kb = getKey(b);
    if (lmSort === 'name') return ka.name.localeCompare(kb.name);
    if (lmSort === 'error') {
      // Untriangulated last, then highest error first.
      if (ka.isUntri !== kb.isUntri) return ka.isUntri ? 1 : -1;
      return kb.err - ka.err;
    }
    if (lmSort === 'indep') {
      if (ka.isIndep !== kb.isIndep) return ka.isIndep ? -1 : 1;
      return kb.err - ka.err;
    }
    return 0;
  });
  // Only reorder if the order actually changed (avoid infinite observer loop).
  let changed = false;
  for (let i = 0; i < sorted.length; i++) {
    if (items[i] !== sorted[i]) { changed = true; break; }
  }
  if (!changed) return;
  // Re-append in new order.
  const frag = document.createDocumentFragment();
  for (const el of sorted) frag.appendChild(el);
  list.appendChild(frag);
}
// Hook MutationObserver to re-sort whenever lm-list children change.
window.addEventListener('load', () => {
  const list = document.getElementById('lm-list');
  if (!list) return;
  const obs = new MutationObserver(() => {
    // Defer to next tick to avoid sorting mid-render.
    if (window._lmSortPending) return;
    window._lmSortPending = true;
    setTimeout(() => {
      window._lmSortPending = false;
      _applyLmSort();
    }, 0);
  });
  obs.observe(list, { childList: true });
});
window._applyLmSort = _applyLmSort;
// Phase 9.1: URL hash state + landmark sort"""


HUNKS = [
    ('CSS — sort dropdown styling',                HUNK_1_OLD, HUNK_1_NEW),
    ('HTML — sort dropdown in filter row',         HUNK_2_OLD, HUNK_2_NEW),
    ('JS — state + URL hash helpers',              HUNK_3_OLD, HUNK_3_NEW),
    ('JS — wrap setView for hash sync',            HUNK_4_OLD, HUNK_4_NEW),
    ('JS — wrap camSel change for hash sync',      HUNK_5_OLD, HUNK_5_NEW),
    ('JS — restore state from URL on load',        HUNK_6_OLD, HUNK_6_NEW),
    ('JS — sort observer + apply function',        HUNK_7_OLD, HUNK_7_NEW),
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
            print(f'✓ Restored {CALIB_HTML} from {BACKUP}.')
        else:
            print(f'(dry-run) would restore from {BACKUP}.')
        return

    with open(CALIB_HTML, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print('✓ Already patched.')
        return

    if PHASE8_2_SENTINEL not in src:
        print('ERROR: Phase 8.2 sentinel not found.')
        sys.exit(1)

    # Apply hunks in order. Hunk 7 modifies a chunk that hunk 3 created,
    # so hunk 3 must run first.
    new_src = src
    for label, old, new in HUNKS:
        n = new_src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} (need 1).')
            sys.exit(1)
        new_src = new_src.replace(old, new, 1)

    # Tag with sentinel.
    new_src = new_src.replace(
        '<!-- Phase 8.2: #ray-map-modal removed',
        SENTINEL + '\n<!-- Phase 8.2: #ray-map-modal removed',
        1)

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
    print('Test:')
    print('  1. Hard reload Safari (Cmd+Shift+R).')
    print('  2. Select a cam — URL hash should update to #cam=...')
    print('  3. Switch to Map view — URL hash should add &view=map')
    print('  4. Reload — should restore selection automatically')
    print('  5. Try the new "sort" dropdown in the lm-list filters')
    print('     - "name", "error ↓", "indep first" should reorder visibly')
    print('  6. Sort selection persists in URL hash too')


if __name__ == '__main__':
    main()
