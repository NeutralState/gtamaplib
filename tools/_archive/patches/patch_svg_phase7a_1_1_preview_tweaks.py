#!/usr/bin/env python3
"""
patch_svg_phase7a_1_1_preview_tweaks.py — minimap grayscale + cam preview click + PNG preload

Three small tweaks to Phase 7a.1 based on first-look feedback:

  1. The minimap shows the raw colored /yanis.png. Map view applies a
     `grayscale(1) brightness(1.05) contrast(1.1)` filter to its <img>
     so the map reads black-and-white. Phase 7a.1 didn't apply that
     filter to #minimap-img-sb (a <div> with background-image, different
     selector). Fix: add the same filter rule for the sidebar minimap.
  2. Clicking the minimap switches to Map view; clicking the cam preview
     should mirror that and switch BACK to Camera view. Adds a click
     listener on #cam-preview-wrap that calls setView('camera').
  3. The first cam selection has a 3-5s delay because the browser
     hasn't downloaded /yanis.png yet (only happens on first Map view
     visit otherwise). Add a hidden <img src="/yanis.png"> in <head>
     so the browser cache primes during page load — by the time the
     user picks a cam, the PNG is ready.

Idempotent. Builds on Phase 7a.1.
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_HTML = os.path.join(THIS_DIR, 'calib.html')
BACKUP = CALIB_HTML + '.bak_svg_phase7a_1_1'

SENTINEL = '/* Phase 7a.1.1: minimap grayscale + cam preview click + PNG preload */'
PHASE7A_1_SENTINEL = '/* Phase 7a.1: sidebar preview slot (minimap CSS-only + cam preview) */'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — CSS: apply grayscale filter to #minimap-img-sb (matches Map view).
# Anchor: the existing #minimap-img-sb rule.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
#minimap-img-sb{position:absolute;inset:0;
  background-image:url('/yanis.png');
  background-repeat:no-repeat;
  /* JS sets background-position and background-size per cam */
  background-color:#222}"""

HUNK_1_NEW = """\
#minimap-img-sb{position:absolute;inset:0;
  background-image:url('/yanis.png');
  background-repeat:no-repeat;
  /* JS sets background-position and background-size per cam */
  background-color:#222;
  /* Phase 7a.1.1: match Map view's grayscale treatment so the
     minimap matches the main map visually. */
  filter:grayscale(1) brightness(1.05) contrast(1.1)}"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — JS: add click listener on #cam-preview-wrap to setView('camera').
# Anchor: the existing minimapWrap.addEventListener('click', ...) block.
# We insert the new listener right after it for tight grouping.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
// Click on the minimap → switch to Map view (matches rlx reference UI).
minimapWrap.addEventListener('click', () => {
  if (typeof window.setView === 'function') window.setView('map');
});"""

HUNK_2_NEW = """\
// Click on the minimap → switch to Map view (matches rlx reference UI).
minimapWrap.addEventListener('click', () => {
  if (typeof window.setView === 'function') window.setView('map');
});

// Phase 7a.1.1: click on cam preview (Map view) → switch back to Camera view.
const _camPreviewWrap = document.getElementById('cam-preview-wrap');
if (_camPreviewWrap) {
  _camPreviewWrap.style.cursor = 'pointer';
  _camPreviewWrap.title = 'Click to switch to Camera view';
  _camPreviewWrap.addEventListener('click', () => {
    if (typeof window.setView === 'function') window.setView('camera');
  });
}"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 3 — HTML: hidden <img src="/yanis.png"> in <head> to prime the
# browser cache. Anchor: the existing closing </style> right before <body>.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_3_OLD = """\
.lm-info-close{margin-left:auto;color:var(--dim);cursor:pointer;font-family:var(--mono);font-size:11px}
.lm-info-close:hover{color:var(--red)}
</style>
</head>
<body>"""

HUNK_3_NEW = """\
.lm-info-close{margin-left:auto;color:var(--dim);cursor:pointer;font-family:var(--mono);font-size:11px}
.lm-info-close:hover{color:var(--red)}
</style>
<!-- Phase 7a.1.1: preload /yanis.png so the sidebar minimap is ready
     by the time the user picks a cam. The browser fetches it in
     parallel with the rest of the page; same response is reused by
     the Map view <img>, the minimap background-image, etc. -->
<link rel="preload" as="image" href="/yanis.png">
</head>
<body>"""


HUNKS = [
    ('CSS — grayscale filter on minimap-img-sb', HUNK_1_OLD, HUNK_1_NEW),
    ('JS — cam preview click → setView camera',  HUNK_2_OLD, HUNK_2_NEW),
    ('HTML — preload /yanis.png in <head>',      HUNK_3_OLD, HUNK_3_NEW),
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

    if PHASE7A_1_SENTINEL not in src:
        print('ERROR: Phase 7a.1 sentinel not found. Apply Phase 7a.1 first.')
        sys.exit(1)

    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} times (need exactly 1).')
            sys.exit(1)

    new_src = src
    for _label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    # Embed the sentinel once, near the Phase 7a.1 sentinel so future
    # patches can pre-flight on it.
    SENTINEL_ANCHOR = PHASE7A_1_SENTINEL
    new_src = new_src.replace(SENTINEL_ANCHOR,
                              SENTINEL_ANCHOR + '\n' + SENTINEL,
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
    print('Test: hard reload (Cmd+Shift+R), select a cam.')
    print('  - Minimap should appear ~immediately (PNG preloaded)')
    print('  - Minimap visually matches Map view (grayscale)')
    print('  - In Map view, click cam preview to switch back to Camera')


if __name__ == '__main__':
    main()
