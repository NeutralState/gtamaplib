#!/usr/bin/env python3
"""
regen_index_camdata.py — Regenerate the `const camData = {...}` block in
docs/index.html with current data from cameras.json / landmarks.json /
pixels.json.

For each camera:
  - label: cam name
  - lms: list of self-source landmarks (this cam triangulated them)
  - rays: list of "OtherCam → Landmark" indep observations
          (other cams that mark a landmark this cam also marks)
  - author: 'leak' | 'trailer' | 'neutral_state'
  - loss: adaptive metric (median anchored or indep arcmin), or null
  - params: 'xyz=(...) · ypr=(...) · hfov=...'

Camera keys in camData are normalized short codes (lka, lkp, kl, gw, prison,
vb_a, vb_b, etc.). We reuse the existing keys when possible by parsing the
current index.html, otherwise derive a slug.

Run from gtamaplib-main/:
    python3 tools/regen_index_camdata.py        # dry run -> outputs the JS
    python3 tools/regen_index_camdata.py --apply
"""

import argparse
import json
import math
import os
import re
import shutil
import statistics
import sys

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GTAMAP_DIR)
import gtamaplib_setup  # noqa: F401  [vendor-hijack-V1]
import gtamaplib as ml
import gtamapdata as md

INDEX_PATH = os.path.join(GTAMAP_DIR, "docs", "index.html")
BACKUP_PATH = INDEX_PATH + ".bak_regen"

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
parser.add_argument('--print-only', action='store_true', help='Just print the JS, no file')
args = parser.parse_args()


def is_leak(cn):
    s = md.cameras.get(cn, {}).get('source', '')
    return bool(re.match(r'\d{4}-\d{2}-\d{2}', s))

def is_trailer(cn):
    s = md.cameras.get(cn, {}).get('source', '')
    return s.startswith('Trailer')

def is_optimizable(cn):
    return not (is_leak(cn) or is_trailer(cn))


def slug(name):
    """Generate a short stable key for a cam."""
    s = name.lower()
    s = re.sub(r'\(.*?\)', '', s).strip()
    s = re.sub(r'[^a-z0-9]+', '_', s).strip('_')
    return s


# ── Read existing keys from index.html so we keep stable IDs ────────────────
existing_keys = {}
if os.path.exists(INDEX_PATH):
    with open(INDEX_PATH) as f:
        idx_src = f.read()
    # Parse blocks like "  'key': { label: 'X (Y)', ..."
    for m in re.finditer(r"  '([a-z0-9_]+)':\s*\{\s*label:\s*'([^']+)'", idx_src):
        existing_keys[m.group(2)] = m.group(1)


def get_key(cam_name):
    if cam_name in existing_keys:
        return existing_keys[cam_name]
    return slug(cam_name)


# ── Build camData ───────────────────────────────────────────────────────────
def calc_residual_arcmin(cam_name, lm_name):
    """Return arcmin error of a landmark projection in this cam, or None."""
    cam = ml.get_camera(cam_name)
    lm_xyz = md.landmarks.get(lm_name)
    if lm_xyz is None: return None
    pixel = md.pixels[cam_name][lm_name]
    proj = cam.get_pixel(lm_xyz)
    if proj is None: return None
    dx = (proj[0] - pixel[0]) * cam.hfov / cam.w * 60
    dy = (proj[1] - pixel[1]) * cam.vfov / cam.h * 60
    return math.sqrt(dx*dx + dy*dy)


def loss_for_cam(cam_name):
    """
    Adaptive loss:
      - LEAK or TRAILER: None (ground truth)
      - >=3 anchored landmarks: median anchored arcmin
      - >=1 indep: median indep arcmin
      - else: None
    """
    if not is_optimizable(cam_name): return None
    pxs = md.pixels.get(cam_name, {})
    if not pxs: return None
    anchored, indep = [], []
    for lm_name in pxs:
        if lm_name not in md.landmarks or md.landmarks[lm_name] is None: continue
        src = md.landmarks_meta.get(lm_name, {}).get('source_cameras', [])
        if cam_name in src or not src: continue  # self-source or no src
        err = calc_residual_arcmin(cam_name, lm_name)
        if err is None: continue
        is_anchor = all(not is_optimizable(c) for c in src)
        (anchored if is_anchor else indep).append(err)
    if len(anchored) >= 3: return statistics.median(anchored)
    if indep: return statistics.median(indep)
    if anchored: return statistics.median(anchored)
    return None


def author_for_cam(cam_name):
    if is_leak(cam_name): return 'leak'
    if is_trailer(cam_name): return 'trailer'
    return 'neutral_state'


def self_source_landmarks(cam_name):
    """Landmarks where cam_name is one of the source_cameras."""
    out = []
    for lm_name in md.pixels.get(cam_name, {}):
        meta = md.landmarks_meta.get(lm_name, {})
        if cam_name in meta.get('source_cameras', []):
            out.append(lm_name)
    return out


def indep_rays(cam_name):
    """List of 'OtherCam → Landmark' for landmarks this cam observes that
    were triangulated by other cams."""
    out = []
    for lm_name in md.pixels.get(cam_name, {}):
        meta = md.landmarks_meta.get(lm_name, {})
        srcs = meta.get('source_cameras', [])
        if cam_name in srcs or not srcs: continue
        # Each source cam → this landmark is a "ray"
        for sc in srcs:
            if sc != cam_name:
                out.append(f"{sc} → {lm_name}")
    return out


def params_str(cam_name):
    c = md.cameras.get(cam_name, {})
    xyz = c.get('xyz')
    ypr = c.get('ypr')
    fov = c.get('fov')
    if not xyz: return ''
    parts = [f"xyz=({xyz[0]:.1f}, {xyz[1]:.1f}, {xyz[2]:.3f})"]
    if ypr:
        parts.append(f"ypr=({ypr[0]:.3f}, {ypr[1]:.3f}, {ypr[2]:.3f})")
    if fov and fov[0] is not None:
        parts.append(f"hfov={fov[0]:.3f}")
    return " · ".join(parts)


cam_data = {}
for cam_name in sorted(md.cameras):
    if not md.cameras[cam_name].get('xyz'): continue
    key = get_key(cam_name)
    if key in cam_data:
        # Collision: append a number
        i = 2
        while f"{key}_{i}" in cam_data: i += 1
        key = f"{key}_{i}"
    entry = {
        'label': cam_name,
        'lms': self_source_landmarks(cam_name),
        'rays': indep_rays(cam_name)[:30],   # cap at 30 for readability
        'author': author_for_cam(cam_name),
        'loss': loss_for_cam(cam_name),
        'params': params_str(cam_name),
    }
    cam_data[key] = entry


# ── Format JS output ────────────────────────────────────────────────────────
def js_str(s):
    s = s.replace('\\', '\\\\').replace("'", "\\'")
    return f"'{s}'"

def fmt_list(lst):
    items = [js_str(x) for x in lst]
    if not items: return '[]'
    return '[' + ', '.join(items) + ']'

lines = ['const camData = {']
for key, e in cam_data.items():
    loss = 'null' if e['loss'] is None else f"{e['loss']:.3f}"
    lines.append(f"  '{key}': {{")
    lines.append(f"    label: {js_str(e['label'])},")
    lines.append(f"    lms: {fmt_list(e['lms'])},")
    lines.append(f"    rays: {fmt_list(e['rays'])},")
    lines.append(f"    author: {js_str(e['author'])}, loss: {loss},")
    if e['params']:
        lines.append(f"    params: {js_str(e['params'])}")
    lines.append("  },")
lines.append('};')
new_js = '\n'.join(lines)


# ── Output ──────────────────────────────────────────────────────────────────
print(f"Generated camData with {len(cam_data)} cameras")
print(f"  leak:        {sum(1 for e in cam_data.values() if e['author']=='leak')}")
print(f"  trailer:     {sum(1 for e in cam_data.values() if e['author']=='trailer')}")
print(f"  optimizable: {sum(1 for e in cam_data.values() if e['author']=='neutral_state')}")
print()

if args.print_only:
    print(new_js)
    sys.exit(0)

if not os.path.exists(INDEX_PATH):
    print(f"ERROR: {INDEX_PATH} not found"); sys.exit(1)

with open(INDEX_PATH) as f:
    src = f.read()

# Find the existing camData block and replace it
m = re.search(r'const camData = \{', src)
if not m:
    print("ERROR: 'const camData = {' not found in index.html"); sys.exit(1)

# Find matching closing brace at top level
start = m.start()
i = m.end()
depth = 1
while i < len(src) and depth > 0:
    if src[i] == '{': depth += 1
    elif src[i] == '}': depth -= 1
    i += 1
# i is now after the closing '}', look for trailing ';'
while i < len(src) and src[i] in ' \t': i += 1
if i < len(src) and src[i] == ';': i += 1

old_block = src[start:i]
print(f"Old camData block: {len(old_block)} chars, {old_block.count(chr(10))} lines")
print(f"New camData block: {len(new_js)} chars, {new_js.count(chr(10))} lines")

if not args.apply:
    print("\n(dry run — re-run with --apply to write changes)")
    sys.exit(0)

shutil.copy(INDEX_PATH, BACKUP_PATH)
print(f"\n✓ Backup: {BACKUP_PATH}")

new_src = src[:start] + new_js + src[i:]
with open(INDEX_PATH, 'w') as f:
    f.write(new_src)
print(f"✓ Updated: {INDEX_PATH}")
print()
print("Commit + push to deploy:")
print("  git add docs/index.html")
print("  git commit -m 'regen index camData with current calibration state'")
print("  git push")
