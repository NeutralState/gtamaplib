#!/usr/bin/env python3
"""
patch_calib_dashboard_link.py — Adds a "→ Dashboard" link to the calib.html header.

Run from gtamaplib-main/:
    python3 tools/patch_calib_dashboard_link.py
"""
import os

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'tools' \
    else os.path.dirname(os.path.abspath(__file__))

HTML_PATH = os.path.join(GTAMAP_DIR, 'tools', 'calib.html')

with open(HTML_PATH) as f:
    content = f.read()

# Add nav-link CSS if not present
NAV_CSS = """.nav-link{font-family:var(--mono);font-size:11px;color:var(--blue);text-decoration:none;padding:5px 10px;border:1px solid var(--border);border-radius:5px;transition:all .15s;margin-right:6px}
.nav-link:hover{background:var(--surface2);border-color:var(--blue)}"""

if 'nav-link' not in content:
    # Insert CSS before the .saved style or any other reasonable anchor
    if '.saved{' in content:
        content = content.replace('.saved{', NAV_CSS + '\n.saved{')
        print("✓ Added .nav-link CSS")
    else:
        print("✗ Could not find anchor for CSS — skipping")
else:
    print("• .nav-link CSS already present")

# Add the link in the header. Find the .logo div and append the link right after.
# Look for the pattern: <div class="logo">...</div>
import re
logo_match = re.search(r'(<div class="logo">[^<]+</div>)', content)
if logo_match and 'cam_health.html' not in content:
    new_logo = logo_match.group(1) + '\n<a href="/cam_health.html" class="nav-link">→ Dashboard</a>'
    content = content.replace(logo_match.group(1), new_logo)
    print("✓ Added Dashboard link to header")
elif 'cam_health.html' in content:
    print("• Dashboard link already present")
else:
    print("✗ Could not find .logo div — manual patch needed")

with open(HTML_PATH, 'w') as f:
    f.write(content)

print(f"\n✓ Done. Hard reload calib.html in browser (Cmd+Shift+R) to see the link.")
