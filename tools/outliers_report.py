#!/usr/bin/env python3
"""
outliers_report.py — Generate an HTML review report from bundle_adjust_result.json

Reads tools/bundle_adjust_result.json (full ranking computed by bundle_adjust.py)
and writes tools/outliers_report.html — an interactive page to systematically
review the worst observations after bundle adjustment.

The report groups outliers two ways:
  - By landmark   (a single bad landmark pollutes many observations — fix once,
                   resolve many)
  - By camera     (a miscalibrated camera contaminates everything it sees)

Each row is clickable and opens the calib tool at localhost:8765 with the
relevant camera + landmark pre-selected. Run your calib server in the
background and keep this report open in another tab.

Run from gtamaplib-main/:
    python3 tools/outliers_report.py
"""

import json
import os
import sys
from collections import defaultdict
from html import escape

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR  = os.path.dirname(os.path.abspath(__file__))

RESULT_PATH = os.path.join(TOOLS_DIR, 'bundle_adjust_result.json')
REPORT_PATH = os.path.join(TOOLS_DIR, 'outliers_report.html')

CALIB_BASE = "http://localhost:8765"

# Threshold below which an obs is considered "clean" and ignored in the report
MIN_ERROR_ARCMIN = 5.0

if not os.path.exists(RESULT_PATH):
    print(f"ERROR: {RESULT_PATH} not found. Run bundle_adjust.py first.")
    sys.exit(1)

with open(RESULT_PATH) as f:
    result = json.load(f)

outliers = result.get('outliers', [])
dist     = result.get('distribution_arcmin', {})

if not outliers:
    print("No outliers in result.json — was bundle_adjust.py used to generate it?")
    sys.exit(1)

# ── Group by landmark and by camera ───────────────────────────────────────────

by_lm  = defaultdict(list)
by_cam = defaultdict(list)
for entry in outliers:
    if entry['error_arcmin'] < MIN_ERROR_ARCMIN:
        continue
    by_lm [entry['landmark']].append(entry)
    by_cam[entry['cam']     ].append(entry)

# Rank groups by total error contribution (sum of squared errors — same metric
# as the bundle adjustment cost, so the top groups are literally the ones
# contributing most to the residual cost).
def group_score(entries):
    return sum(e['error_arcmin']**2 for e in entries)

ranked_lms  = sorted(by_lm.items(),  key=lambda kv: group_score(kv[1]), reverse=True)
ranked_cams = sorted(by_cam.items(), key=lambda kv: group_score(kv[1]), reverse=True)

# ── HTML rendering ────────────────────────────────────────────────────────────

def severity_class(err):
    if err >= 100: return 'sev-extreme'
    if err >= 50:  return 'sev-high'
    if err >= 20:  return 'sev-mid'
    return 'sev-low'

def fmt_obs_row(entry, idx_in_group):
    cam, lm = entry['cam'], entry['landmark']
    err = entry['error_arcmin']
    flags = []
    if not entry.get('cam_optimized'): flags.append('LEAK CAM')
    if not entry.get('lm_optimized'):  flags.append('FIXED LM')
    flag_html = ' '.join(f'<span class="flag">{f}</span>' for f in flags)

    # Link opens calib tool; user has to manually pick the landmark there but
    # at least the camera is pre-selected via URL hash.
    cam_url = f"{CALIB_BASE}/#cam={escape(cam, quote=True)}"

    return f'''<tr class="{severity_class(err)}">
      <td class="num">{idx_in_group}</td>
      <td class="err">{err:.1f}'</td>
      <td><a href="{cam_url}" target="_blank">{escape(cam)}</a></td>
      <td>{escape(lm)}</td>
      <td class="px">[{entry['marked_pixel'][0]:.0f}, {entry['marked_pixel'][1]:.0f}]</td>
      <td class="flags">{flag_html}</td>
    </tr>'''

def fmt_group_section(title, key, entries, score, group_type):
    rows = '\n'.join(fmt_obs_row(e, i+1) for i, e in enumerate(entries[:10]))
    n_more = len(entries) - 10
    more_note = f'<div class="more">… and {n_more} more in this group</div>' if n_more > 0 else ''
    worst = max(e['error_arcmin'] for e in entries)
    return f'''
    <div class="group">
      <div class="group-header">
        <h3>{escape(key)}</h3>
        <div class="group-stats">
          <span><b>{len(entries)}</b> obs</span>
          <span>worst <b>{worst:.0f}'</b></span>
          <span>cost contribution <b>{score:.0f}</b></span>
        </div>
      </div>
      <table>
        <thead>
          <tr><th>#</th><th>error</th><th>{'landmark' if group_type=='cam' else 'camera'}</th><th>{'camera' if group_type=='cam' else 'landmark'}</th><th>marked px</th><th></th></tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      {more_note}
    </div>'''

# Re-shape rows depending on group axis (so the right column is the "other" entity)
def fmt_lm_row(entry, idx):
    cam, lm = entry['cam'], entry['landmark']
    err = entry['error_arcmin']
    flags = []
    if not entry.get('cam_optimized'): flags.append('LEAK CAM')
    if not entry.get('lm_optimized'):  flags.append('FIXED LM')
    flag_html = ' '.join(f'<span class="flag">{f}</span>' for f in flags)
    cam_url = f"{CALIB_BASE}/#cam={escape(cam, quote=True)}"
    return f'''<tr class="{severity_class(err)}">
      <td class="num">{idx}</td>
      <td class="err">{err:.1f}'</td>
      <td><a href="{cam_url}" target="_blank">{escape(cam)}</a></td>
      <td class="px">[{entry['marked_pixel'][0]:.0f}, {entry['marked_pixel'][1]:.0f}]</td>
      <td class="flags">{flag_html}</td>
    </tr>'''

def fmt_cam_row(entry, idx):
    cam, lm = entry['cam'], entry['landmark']
    err = entry['error_arcmin']
    flags = []
    if not entry.get('cam_optimized'): flags.append('LEAK CAM')
    if not entry.get('lm_optimized'):  flags.append('FIXED LM')
    flag_html = ' '.join(f'<span class="flag">{f}</span>' for f in flags)
    return f'''<tr class="{severity_class(err)}">
      <td class="num">{idx}</td>
      <td class="err">{err:.1f}'</td>
      <td>{escape(lm)}</td>
      <td class="px">[{entry['marked_pixel'][0]:.0f}, {entry['marked_pixel'][1]:.0f}]</td>
      <td class="flags">{flag_html}</td>
    </tr>'''

def fmt_lm_group(lm_name, entries, score):
    rows = '\n'.join(fmt_lm_row(e, i+1) for i, e in enumerate(entries[:10]))
    n_more = len(entries) - 10
    more_note = f'<div class="more">… and {n_more} more</div>' if n_more > 0 else ''
    worst = max(e['error_arcmin'] for e in entries)
    fixed = not entries[0].get('lm_optimized')
    fixed_badge = ' <span class="flag">FIXED LM</span>' if fixed else ''
    return f'''
    <div class="group">
      <div class="group-header">
        <h3>📍 {escape(lm_name)}{fixed_badge}</h3>
        <div class="group-stats">
          <span><b>{len(entries)}</b> obs</span>
          <span>worst <b>{worst:.0f}'</b></span>
          <span>cost <b>{score:.0f}</b></span>
        </div>
      </div>
      <table>
        <thead><tr><th>#</th><th>error</th><th>camera</th><th>marked px</th><th></th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      {more_note}
    </div>'''

def fmt_cam_group(cam_name, entries, score):
    rows = '\n'.join(fmt_cam_row(e, i+1) for i, e in enumerate(entries[:10]))
    n_more = len(entries) - 10
    more_note = f'<div class="more">… and {n_more} more</div>' if n_more > 0 else ''
    worst = max(e['error_arcmin'] for e in entries)
    leak = not entries[0].get('cam_optimized')
    leak_badge = ' <span class="flag">LEAK CAM</span>' if leak else ''
    cam_url = f"{CALIB_BASE}/#cam={escape(cam_name, quote=True)}"
    return f'''
    <div class="group">
      <div class="group-header">
        <h3>📷 <a href="{cam_url}" target="_blank">{escape(cam_name)}</a>{leak_badge}</h3>
        <div class="group-stats">
          <span><b>{len(entries)}</b> obs</span>
          <span>worst <b>{worst:.0f}'</b></span>
          <span>cost <b>{score:.0f}</b></span>
        </div>
      </div>
      <table>
        <thead><tr><th>#</th><th>error</th><th>landmark</th><th>marked px</th><th></th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      {more_note}
    </div>'''

# ── Build full page ───────────────────────────────────────────────────────────

lm_groups_html  = '\n'.join(fmt_lm_group (k, v, group_score(v)) for k, v in ranked_lms[:30])
cam_groups_html = '\n'.join(fmt_cam_group(k, v, group_score(v)) for k, v in ranked_cams[:30])

html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Bundle adjust outliers — review report</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 1400px;
         margin: 1em auto; padding: 0 1em; background: #f5f5f7; color: #222; }}
  h1 {{ margin: 0.2em 0; }}
  .summary {{ background: #fff; padding: 1em; border-radius: 8px;
              box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 1.5em; }}
  .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1em; margin-top: 0.7em; }}
  .stat {{ font-size: 0.85em; color: #666; }}
  .stat b {{ display: block; font-size: 1.6em; color: #222; margin-top: 0.1em; }}
  .tabs {{ display: flex; gap: 0; margin-bottom: 1em; border-bottom: 2px solid #ddd; }}
  .tab {{ padding: 0.6em 1.2em; cursor: pointer; background: none; border: none;
          font-size: 1em; color: #666; border-bottom: 2px solid transparent; margin-bottom: -2px; }}
  .tab.active {{ color: #0070f3; border-bottom-color: #0070f3; font-weight: 600; }}
  .pane {{ display: none; }}
  .pane.active {{ display: block; }}
  .group {{ background: #fff; border-radius: 8px; padding: 0.8em 1em;
            margin-bottom: 1em; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
  .group-header {{ display: flex; justify-content: space-between; align-items: baseline;
                   margin-bottom: 0.6em; }}
  .group-header h3 {{ margin: 0; font-size: 1.05em; }}
  .group-stats {{ font-size: 0.85em; color: #666; }}
  .group-stats span {{ margin-left: 1em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
  th {{ text-align: left; color: #888; font-weight: 500; padding: 0.4em 0.6em;
        border-bottom: 1px solid #eee; }}
  td {{ padding: 0.4em 0.6em; border-bottom: 1px solid #f5f5f5; }}
  tr:hover td {{ background: #fafafa; }}
  td.num {{ color: #aaa; width: 30px; }}
  td.err {{ font-variant-numeric: tabular-nums; font-weight: 600; width: 60px; }}
  td.px {{ color: #888; font-variant-numeric: tabular-nums; font-size: 0.85em; }}
  td.flags {{ text-align: right; }}
  .flag {{ display: inline-block; font-size: 0.7em; padding: 1px 6px;
           background: #fff3cd; color: #856404; border-radius: 3px; margin-left: 4px; }}
  .sev-extreme td.err {{ color: #c00; }}
  .sev-high    td.err {{ color: #e60; }}
  .sev-mid     td.err {{ color: #b80; }}
  .sev-low     td.err {{ color: #888; }}
  .more {{ font-size: 0.8em; color: #999; padding: 0.3em 0.6em; }}
  a {{ color: #0070f3; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .note {{ font-size: 0.85em; color: #666; margin-bottom: 1em;
           padding: 0.6em 0.8em; background: #fff; border-left: 3px solid #0070f3;
           border-radius: 3px; }}
</style>
</head>
<body>

<h1>Bundle adjust — outliers review</h1>

<div class="summary">
  <div>RMS loss: <b>{result['initial_loss']}'</b> → <b>{result['final_loss']}'</b>
       &nbsp;·&nbsp; improvement <b>{result['improvement_pct']}%</b></div>
  <div class="summary-grid">
    <div class="stat">p50 (median)<b>{dist.get('p50','?')}'</b></div>
    <div class="stat">p90<b>{dist.get('p90','?')}'</b></div>
    <div class="stat">p99<b>{dist.get('p99','?')}'</b></div>
    <div class="stat">max<b>{dist.get('max','?')}'</b></div>
    <div class="stat">obs &gt; 50'<b>{dist.get('count_over_50','?')}</b></div>
    <div class="stat">obs &gt; 20'<b>{dist.get('count_over_20','?')}</b></div>
    <div class="stat">obs &gt; 10'<b>{dist.get('count_over_10','?')}</b></div>
    <div class="stat">obs &lt; 5' (clean)<b>{dist.get('count_under_5','?')} / {dist.get('total','?')}</b></div>
  </div>
</div>

<div class="note">
  <b>Workflow:</b> Start the calib server (<code>python3 tools/server.py</code>),
  then click any camera link to open it in the calib tool. Cross-reference the
  marked pixel against the actual landmark position in the frame.
  Groups are sorted by <b>cost contribution</b> (sum of squared errors) — fixing
  the top items has the biggest impact on the global loss.
  <br><br>
  <b>Triage hints:</b> If many cameras report large errors on the <i>same landmark</i>,
  the landmark is likely mis-positioned (or the bundle adjust hasn't been applied yet).
  If <i>one camera</i> reports large errors across many landmarks, that camera's
  calibration is probably off. <span class="flag">FIXED LM</span> + big error =
  pixel is almost certainly wrong (the lm cannot move to compensate).
  <span class="flag">LEAK CAM</span> + big error = same logic for the camera side.
</div>

<div class="tabs">
  <button class="tab active" onclick="showTab('lms', this)">By landmark ({len(ranked_lms)})</button>
  <button class="tab"        onclick="showTab('cams', this)">By camera ({len(ranked_cams)})</button>
</div>

<div id="pane-lms" class="pane active">
{lm_groups_html}
</div>

<div id="pane-cams" class="pane">
{cam_groups_html}
</div>

<script>
function showTab(name, btn) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('pane-' + name).classList.add('active');
}}
</script>

</body>
</html>
'''

with open(REPORT_PATH, 'w') as f:
    f.write(html)

print(f"Report written: {REPORT_PATH}")
print(f"  Groups by landmark : {len(ranked_lms)} (showing top 30)")
print(f"  Groups by camera   : {len(ranked_cams)} (showing top 30)")
print(f"  Outliers >= {MIN_ERROR_ARCMIN}'  : {sum(len(v) for v in by_lm.values())}")
print(f"\nOpen: file://{REPORT_PATH}")
print("(Run `python3 tools/server.py` separately if you want the calib links to work)")
