#!/usr/bin/env python3
"""Quick fix: enable Generate Map button when a cam is selected."""
import os
GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'tools' \
    else os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(GTAMAP_DIR, 'tools', 'calib.html')

with open(HTML_PATH) as f:
    content = f.read()

old = """const _origCamChange = document.getElementById('cam-sel').onchange;
document.getElementById('cam-sel').addEventListener('change', () => {
  setTimeout(() => {
    btnGenmap.disabled = !currentCam;
  }, 100);
});"""

new = """document.getElementById('cam-sel').addEventListener('change', () => {
  btnGenmap.disabled = !document.getElementById('cam-sel').value;
});"""

if old in content:
    content = content.replace(old, new)
    with open(HTML_PATH, 'w') as f:
        f.write(content)
    print('Patched — hard reload calib.html (Cmd+Shift+R)')
else:
    print('Not found in current file')
