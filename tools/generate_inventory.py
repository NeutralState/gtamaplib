#!/usr/bin/env python3
"""
Generate TOOLS_INVENTORY.md — a comprehensive map of everything available
in gtamaplib. Scans:
  - tools/*.py for CLI scripts (extracts docstring + Usage section)
  - tools/server.py for /api/* endpoints
  - tools/calib.html for buttons + shortcuts
  - tools/cam_health.html

Output: tools/TOOLS_INVENTORY.md — bookmark this when you forget what
exists.

Run periodically (or after adding new tools) to keep it in sync.
"""

import os
import re
import sys
from pathlib import Path

# [QUICKREF-2026-07] script-relative path (portable, no more hardcode)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, 'tools')
OUT = os.path.join(TOOLS, 'TOOLS_INVENTORY.md')


def extract_docstring(path):
    """Extract module-level docstring from a Python file."""
    try:
        with open(path) as f:
            content = f.read()
        # Skip shebang and any module-level imports before the docstring
        # Use a regex to find the first triple-quoted string at module level
        m = re.search(r'^(?:#![^\n]*\n)?(?:\s*\n)*"""(.*?)"""', content, re.DOTALL)
        if m:
            return m.group(1).strip()
    except Exception as e:
        return f"(error reading: {e})"
    return None


def summary_line(docstring):
    """First line of docstring."""
    if not docstring:
        return ""
    lines = docstring.split('\n')
    for line in lines:
        line = line.strip()
        if line:
            # Strip leading "name.py — " prefix if present
            line = re.sub(r'^\S+\.py\s*[—-]\s*', '', line)
            return line
    return ""


def extract_usage(docstring):
    """Extract 'Usage:' block from docstring if present."""
    if not docstring:
        return None
    m = re.search(r'Usage:\s*\n(.*?)(?:\n\n|\Z)', docstring, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def extract_workflow(docstring):
    """Extract 'Workflow:' block if present."""
    if not docstring:
        return None
    m = re.search(r'Workflow:\s*\n(.*?)(?:\n\n|\Z)', docstring, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


# ── Scan tools/*.py ────────────────────────────────────────────────
print('Scanning tools/*.py...')
cli_scripts = []
for f in sorted(os.listdir(TOOLS)):
    if not f.endswith('.py'): continue
    if f == 'server.py': continue  # handle separately
    path = os.path.join(TOOLS, f)
    doc = extract_docstring(path)
    cli_scripts.append({
        'name': f,
        'summary': summary_line(doc),
        'usage': extract_usage(doc),
        'workflow': extract_workflow(doc),
        'docstring': doc,
    })

# Scan tools/audit/*.py (READ-ONLY diagnostic tools)
print('Scanning tools/audit/*.py...')
audit_scripts = []
AUDIT = os.path.join(TOOLS, 'audit')
if os.path.isdir(AUDIT):
    for f in sorted(os.listdir(AUDIT)):
        if not f.endswith('.py'): continue
        path = os.path.join(AUDIT, f)
        doc = extract_docstring(path)
        audit_scripts.append({
            'name': f,
            'summary': summary_line(doc),
            'usage': extract_usage(doc),
            'docstring': doc,
        })

# ── Scan tools/server.py for endpoints ─────────────────────────────
print('Scanning server.py endpoints...')
endpoints = []
server_path = os.path.join(TOOLS, 'server.py')
with open(server_path) as f:
    server_content = f.read()

# Find all `elif path == '/api/...'` lines + the line right above as comment
ep_pattern = re.compile(r"elif path == '(/api/[^']+)':")
for m in ep_pattern.finditer(server_content):
    endpoint = m.group(1)
    line_no = server_content[:m.start()].count('\n') + 1
    after = server_content[m.end():m.end()+800]
    # Pull all comments in the next 800 chars, skip boilerplate markers
    comments = re.findall(r'^\s*#\s*(.+?)$', after, re.MULTILINE)
    note = ''
    for cm in comments:
        cm = cm.strip()
        # Skip patch/marker comments that aren't describing the endpoint
        if re.match(r'^[\[\u2500]', cm): continue        # [TAG-V1] or ──
        if cm.startswith('──'): continue
        if 'V1-ROLL' in cm and 'parse' in cm: continue    # boilerplate
        if cm.lower().startswith('phase'): continue       # phase markers
        if len(cm) < 8: continue                          # too short
        note = cm[:100]
        break
    endpoints.append({'path': endpoint, 'line': line_no, 'note': note})

# Also pick up frame and tile routes
for path_match in re.finditer(r"elif path(?:\.startswith)?\(?\s*[=]+\s*['\"]([^'\"]+)['\"]\)?:", server_content):
    p = path_match.group(1)
    if p.startswith('/api/'): continue  # already captured
    if p in ('/cam_health.html', '/'):  # skip these
        continue
    line_no = server_content[:path_match.start()].count('\n') + 1
    endpoints.append({'path': p, 'line': line_no, 'note': ''})

# ── Scan calib.html for buttons ────────────────────────────────────
print('Scanning calib.html buttons...')
calib_path = os.path.join(TOOLS, 'calib.html')
with open(calib_path) as f:
    calib_content = f.read()

buttons = []
# Find all <button ...>...</button> blocks (handles multi-line)
btn_tag_pattern = re.compile(r'<button\b([^>]*)>(.*?)</button>', re.DOTALL)
seen = set()
for m in btn_tag_pattern.finditer(calib_content):
    attrs = m.group(1)
    inner = (m.group(2) or '').strip()
    inner = re.sub(r'<[^>]+>', '', inner).strip()  # strip nested tags
    inner = re.sub(r'\s+', ' ', inner)[:80]
    # Pull attributes individually
    bid_m = re.search(r'\bid\s*=\s*["\']([^"\']+)["\']', attrs)
    title_m = re.search(r'\btitle\s*=\s*["\']([^"\']+)["\']', attrs)
    class_m = re.search(r'\bclass\s*=\s*["\']([^"\']+)["\']', attrs)
    bid = bid_m.group(1) if bid_m else ''
    title = title_m.group(1) if title_m else ''
    bclass = class_m.group(1) if class_m else ''
    if not bid and not title and not inner: continue
    key = bid or (title + '|' + inner)
    if key in seen: continue
    seen.add(key)
    buttons.append({'id': bid or '(no id)', 'class': bclass, 'title': title, 'text': inner})

# ── Extract keyboard shortcuts ──────────────────────────────────────
print('Extracting keyboard shortcuts...')
shortcuts = []
shortcut_blocks = re.findall(
    r"document\.addEventListener\('keydown',\s*e\s*=>\s*\{(.*?)\n\}\)",
    calib_content,
    re.DOTALL
)
for block in shortcut_blocks:
    # Look for patterns like e.key === 'X' or e.code === 'KeyX'
    for m in re.finditer(r"e\.(?:key|code)\s*===?\s*['\"]([^'\"]+)['\"]", block):
        key = m.group(1)
        idx = m.end()
        # Find the immediate next 250 chars (the if-body)
        after = block[idx:idx+250]
        action = None
        # Try multiple patterns in order of preference
        for pattern in [
            r'//\s*(.+?)(?:\n|$)',                        # comment
            r'btn(\w+)\.click',                           # btn click
            r'set(?:View|Filter)\(["\']([^"\']+)["\']',  # setView/setFilter
            r'(\w+)\.classList\.toggle\(["\']([^"\']+)',  # classList.toggle
            r'(\w+)\(\)',                                # function call
        ]:
            m2 = re.search(pattern, after)
            if m2:
                groups = [g for g in m2.groups() if g]
                action = ' '.join(groups).strip()
                break
        if not action:
            action = '(see source)'
        shortcuts.append({'key': key, 'action': action[:60]})

# Dedupe shortcuts
seen_keys = set()
unique_shortcuts = []
for s in shortcuts:
    k = s['key']
    if k in seen_keys: continue
    seen_keys.add(k)
    unique_shortcuts.append(s)

# ── Generate the markdown ──────────────────────────────────────────
print('Generating markdown...')

md = []
md.append('# gtamaplib — Tools & Features Inventory\n')
md.append('Auto-generated. Run `python3 tools/generate_inventory.py` to refresh.\n')
md.append('Bookmark this file when you forget what tools exist.\n\n')

md.append('## Quick reference — "Where do I start?"\n\n')
md.append('### Adding a new T3 cam (cold-start workflow)\n')
md.append('```\n')
md.append('1. Place frame in frames/{Cam Name}.png\n')
md.append('2. Run: python3 tools/compute_confidence_tiers.py\n')
md.append('3. Add cam entry to gtamapdata/cameras.json with dummy xyz/ypr/hfov\n')
md.append('4. Mark 3+ landmarks in the calib UI (http://localhost:8765)\n')
md.append('   -> Assist mode: P1/P2 prioritized ghosts, click = arm the marking\n')
md.append('5. Run: python3 tools/intake_camera.py "Cam Name"\n')
md.append('   -> see verdict (commit/review/reject) before applying\n')
md.append('6. If verdict OK: python3 tools/refine_cam_full.py "Cam Name" --apply\n')
md.append('   (the UI Optimize/Update LMs buttons are DECOMMISSIONED)\n')
md.append('7. Re-run compute_confidence_tiers.py to update tiers\n')
md.append('8. Global: bundle_adjust_weighted.py --cleanup, then guarded_apply\n')
md.append('   (NEVER bundle_adjust_apply.py — blind wholesale apply is forbidden)\n')
md.append('```\n\n')

md.append('### The global cycle (guarded apply)\n')
md.append('```\n')
md.append('python3 tools/compute_confidence_tiers.py\n')
md.append('python3 tools/bundle_adjust_weighted.py --cleanup --max-iter 30\n')
md.append('python3 tools/refine/guarded_apply.py            # dry-run, review\n')
md.append('python3 tools/refine/guarded_apply.py --apply\n')
md.append('python3 tools/audit/rms_snapshot.py --tag <name>\n')
md.append('PYTHONPATH=. python3 tools/ci_healthcheck.py --update-baseline  # if improved\n')
md.append('```\n\n')

md.append("### Triage — \"Where is the pain?\"\n")
md.append('```\n')
md.append("UI: Triage button (categorizes cams >5' + one-click actions)\n")
md.append('CLI: python3 tools/outliers_report.py\n')
md.append('     python3 tools/calibration_order.py --tier unverified\n')
md.append('```\n\n')

md.append('### Map evidence — "Is the position real?"\n')
md.append('```\n')
md.append('UI: LM inspector -> yanis crop + "propose retriangulation" + verdict\n')
md.append('CLI: python3 tools/map_validate.py (HTML contact sheet)\n')
md.append('Semantics: validated = map prior (5m budget), NOT frozen; rejected = excluded\n')
md.append('```\n\n')

md.append('### CI — guardrail on every push\n')
md.append('```\n')
md.append('PYTHONPATH=. python3 tools/ci_healthcheck.py   # locally before commit\n')
md.append('Baseline: tools/ci_baseline.json (--update-baseline after an improvement)\n')
md.append('```\n\n')

md.append('---\n\n')

# ── CLI Scripts section ────────────────────────────────────────────
md.append('## CLI Scripts (tools/*.py)\n\n')
md.append(f'Total: {len(cli_scripts)} scripts\n\n')

for s in cli_scripts:
    md.append(f'### `{s["name"]}`\n')
    if s['summary']:
        md.append(f'{s["summary"]}\n\n')
    if s['usage']:
        md.append('**Usage:**\n```\n')
        md.append(s['usage'] + '\n')
        md.append('```\n\n')
    if s['workflow']:
        md.append('**Workflow:**\n```\n')
        md.append(s['workflow'] + '\n')
        md.append('```\n\n')

md.append('---\n\n')

# ── Server endpoints ───────────────────────────────────────────────
md.append('## Audit Tools (tools/audit/*.py) — READ-ONLY\n\n')
md.append('Diagnostic tools that NEVER modify data. Run periodically to check network health.\n\n')
md.append(f'Total: {len(audit_scripts)} audit scripts\n\n')
for sc in audit_scripts:
    md.append(f"### `audit/{sc['name']}`\n")
    if sc['summary']:
        md.append(f"{sc['summary']}\n")
    if sc.get('usage'):
        md.append('\n**Usage:**\n```\n' + sc['usage'] + '\n```\n')
    md.append('\n')

md.append('## Server Endpoints (tools/server.py)\n\n')
md.append(f'Total: {len(endpoints)} endpoints\n\n')
md.append('| Endpoint | Note |\n|---|---|\n')
for ep in endpoints:
    note = ep['note'][:80] if ep['note'] else ''
    md.append(f'| `{ep["path"]}` | {note} |\n')
md.append('\n---\n\n')

# ── UI Buttons ─────────────────────────────────────────────────────
md.append('## Calib UI Buttons (calib.html)\n\n')
md.append(f'Total: {len(buttons)} buttons\n\n')
md.append('| ID | Title / Description |\n|---|---|\n')
for b in buttons:
    desc = b['title'] or b['text'] or '(no description)'
    md.append(f'| `{b["id"]}` | {desc} |\n')
md.append('\n---\n\n')

# ── Keyboard shortcuts ─────────────────────────────────────────────
if unique_shortcuts:
    md.append('## Keyboard Shortcuts\n\n')
    md.append('| Key | Action |\n|---|---|\n')
    for s in unique_shortcuts:
        md.append(f'| `{s["key"]}` | {s["action"]} |\n')
    md.append('\n')

md.append('---\n\n')
md.append('_Generated by `tools/generate_inventory.py`_\n')

with open(OUT, 'w') as f:
    f.write(''.join(md))

print(f'\n✓ Inventory written to {OUT}')
print(f'  - {len(cli_scripts)} CLI scripts')
print(f'  - {len(endpoints)} server endpoints')
print(f'  - {len(buttons)} UI buttons')
print(f'  - {len(unique_shortcuts)} keyboard shortcuts')
