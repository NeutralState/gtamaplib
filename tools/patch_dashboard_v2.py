#!/usr/bin/env python3
"""
patch_dashboard_v2.py — Updates the cam health dashboard with:
  1. Split Trailer 1 / Trailer 2 (was just "TRAILER")
  2. Rename "community" → "screenshots"
  3. Updated chip colors and badge styles

Idempotent: safe to run multiple times.

Run from gtamaplib-main/:
    python3 patch_dashboard_v2.py
"""
import os
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'tools' \
    else os.path.dirname(os.path.abspath(__file__))

SERVER_PATH = os.path.join(GTAMAP_DIR, 'tools', 'server.py')
HTML_PATH = os.path.join(GTAMAP_DIR, 'tools', 'cam_health.html')

# ── Patch server.py ───────────────────────────────────────────────────────────

with open(SERVER_PATH) as f:
    server_content = f.read()

OLD_LOGIC = """                is_leak = bool(_re_local.match(r'\\d{4}-\\d{2}-\\d{2}', source))
                is_trailer = source.startswith('Trailer')
                source_type = 'LEAK' if is_leak else ('TRAILER' if is_trailer else 'community')"""

NEW_LOGIC = """                is_leak = bool(_re_local.match(r'\\d{4}-\\d{2}-\\d{2}', source))
                if is_leak:
                    source_type = 'LEAK'
                elif source.startswith('Trailer 1'):
                    source_type = 'Trailer 1'
                elif source.startswith('Trailer 2') or source == 'Trailer 2':
                    source_type = 'Trailer 2'
                elif source.startswith('Trailer'):
                    source_type = 'Trailer'
                else:
                    source_type = 'screenshots'"""

if OLD_LOGIC in server_content:
    server_content = server_content.replace(OLD_LOGIC, NEW_LOGIC)
    with open(SERVER_PATH, 'w') as f:
        f.write(server_content)
    print("✓ Patched server.py with new source_type logic")
elif NEW_LOGIC in server_content:
    print("• server.py already has new logic")
else:
    print("✗ Could not find old logic in server.py — check manually")

# ── Patch cam_health.html ─────────────────────────────────────────────────────

with open(HTML_PATH) as f:
    html_content = f.read()

# Replace badge CSS
OLD_CSS = """.badge.LEAK{background:rgba(160,160,180,.15);color:var(--mid)}
.badge.TRAILER{background:rgba(96,165,250,.15);color:var(--blue)}
.badge.community{background:rgba(167,139,250,.15);color:var(--purple)}"""

NEW_CSS = """.badge.LEAK{background:rgba(160,160,180,.15);color:var(--mid)}
.badge[class*="Trailer-1"], .badge.Trailer-1{background:rgba(96,165,250,.15);color:var(--blue)}
.badge[class*="Trailer-2"], .badge.Trailer-2{background:rgba(74,222,128,.15);color:var(--green)}
.badge.Trailer{background:rgba(96,165,250,.15);color:var(--blue)}
.badge.screenshots{background:rgba(167,139,250,.15);color:var(--purple)}"""

if OLD_CSS in html_content:
    html_content = html_content.replace(OLD_CSS, NEW_CSS)
    print("✓ Patched HTML badge CSS")
elif NEW_CSS in html_content:
    print("• HTML badge CSS already updated")

# Replace chip CSS
OLD_CHIP_CSS = """.chip-btn[data-source=LEAK].on{border-color:var(--mid);color:var(--text)}
.chip-btn[data-source=TRAILER].on{border-color:var(--blue);color:var(--blue)}
.chip-btn[data-source=community].on{border-color:var(--purple);color:var(--purple)}"""

NEW_CHIP_CSS = """.chip-btn[data-source=LEAK].on{border-color:var(--mid);color:var(--text)}
.chip-btn[data-source="Trailer 1"].on{border-color:var(--blue);color:var(--blue)}
.chip-btn[data-source="Trailer 2"].on{border-color:var(--green);color:var(--green)}
.chip-btn[data-source=screenshots].on{border-color:var(--purple);color:var(--purple)}"""

if OLD_CHIP_CSS in html_content:
    html_content = html_content.replace(OLD_CHIP_CSS, NEW_CHIP_CSS)
    print("✓ Patched HTML chip CSS")
elif NEW_CHIP_CSS in html_content:
    print("• HTML chip CSS already updated")

# Replace chip buttons
OLD_CHIPS = """    <button class="chip-btn on" data-source="LEAK">LEAK</button>
    <button class="chip-btn on" data-source="TRAILER">TRAILER</button>
    <button class="chip-btn on" data-source="community">community</button>"""

NEW_CHIPS = """    <button class="chip-btn on" data-source="LEAK">LEAK</button>
    <button class="chip-btn on" data-source="Trailer 1">Trailer 1</button>
    <button class="chip-btn on" data-source="Trailer 2">Trailer 2</button>
    <button class="chip-btn on" data-source="screenshots">screenshots</button>"""

if OLD_CHIPS in html_content:
    html_content = html_content.replace(OLD_CHIPS, NEW_CHIPS)
    print("✓ Patched HTML chip buttons")
elif NEW_CHIPS in html_content:
    print("• HTML chip buttons already updated")

# Replace filters object
OLD_FILTERS = """  source: { LEAK: true, TRAILER: true, community: true },"""
NEW_FILTERS = """  source: { LEAK: true, 'Trailer 1': true, 'Trailer 2': true, Trailer: true, screenshots: true },"""

if OLD_FILTERS in html_content:
    html_content = html_content.replace(OLD_FILTERS, NEW_FILTERS)
    print("✓ Patched HTML filters object")
elif NEW_FILTERS in html_content:
    print("• HTML filters already updated")

# The badge class needs to handle spaces in source_type — replace dots in class names
# Find: <span class="badge ${c.source_type}">${c.source_type}</span>
# Replace with version that converts space to dash for CSS class
OLD_BADGE_RENDER = '<span class="badge ${c.source_type}">${c.source_type}</span>'
NEW_BADGE_RENDER = '<span class="badge ${c.source_type.replace(/ /g, "-")}">${c.source_type}</span>'

if OLD_BADGE_RENDER in html_content:
    html_content = html_content.replace(OLD_BADGE_RENDER, NEW_BADGE_RENDER)
    print("✓ Patched badge render to handle spaces")
elif NEW_BADGE_RENDER in html_content:
    print("• Badge render already updated")

with open(HTML_PATH, 'w') as f:
    f.write(html_content)

print(f"\n✓ All patches applied")
print(f"\nNext steps:")
print(f"  1. Restart server: lsof -ti :8765 | xargs kill -9; python3 tools/server.py")
print(f"  2. Hard reload browser (Cmd+Shift+R) on http://localhost:8765/cam_health.html")
