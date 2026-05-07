#!/usr/bin/env python3
"""Move modal HTML to before script tag so it exists when JS runs."""
import os, re
GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'tools' \
    else os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(GTAMAP_DIR, 'tools', 'calib.html')

with open(HTML_PATH) as f:
    content = f.read()

# Find the modal block (after </script>, before </body>)
modal_match = re.search(
    r'(<div id="genmap-modal">[\s\S]*?</div>\s*</div>)',
    content
)
if not modal_match:
    print("✗ Could not find genmap-modal block")
    exit(1)

modal_html = modal_match.group(1)

# Remove it from current location
content = content.replace(modal_html, '')

# Insert it BEFORE <script> tag
content = content.replace('<script>', modal_html + '\n\n<script>', 1)

with open(HTML_PATH, 'w') as f:
    f.write(content)

print("✓ Modal HTML moved to before <script>")
print("Hard reload calib.html (Cmd+Shift+R)")
