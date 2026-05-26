#!/usr/bin/env python3
"""
build_cam_health.py — Generate tools/cam_health.html from live data.

Auto-positions cams by projecting world (x, y) onto canvas.
Auto-generates edges from landmarks.json source_cameras.
Includes only cams with xyz + leak cams that are referenced as parents.
Style matches calib.html dark UI.
"""

import os
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / 'gtamapdata'
TOOLS = REPO / 'tools'
TIERS_JSON = TOOLS / 'generated' / 'confidence_tiers.json'

WORLD_X_MIN, WORLD_X_MAX = -7000, 2500
WORLD_Y_MIN, WORLD_Y_MAX = -7700, 6400
CANVAS_W = 2000
CANVAS_H = 1600
PAD = 90
MIN_SEP = 38  # minimum px between any two nodes after anti-overlap

CLUSTER_DEFS = {
    'lm_vc':       ('Vice City\nlandmarks',      'vice',          (1200, 800)),
    'lm_ambrosia': ('Ambrosia\nlandmarks',       'ambrosia',      (-2100, 4200)),
    'lm_keys':     ('Keys\nlandmarks',           'keys',          (-3500, -6300)),
    'lm_gv':       ('Grassrivers\nlandmarks',    'grassrivers',   (-4500, -3100)),
    'lm_pgh':      ('Port Gellhorn\nlandmarks',  'port_gellhorn', (-5600, 4500)),
}

# Map full cam name -> thumbnail filename (without .jpg extension)
# Thumbnails live in docs/thumbs/, served via /thumbs/<name>.jpg
THUMB_MAP = {
    'Leonida Keys 01 (Airplane) (X)': 'LK Airplane (X)',
    'Leonida Keys Postcard (X)': 'LK Postcard (X)',
    'Leonida Keys 05 (Boats)': 'LK 05 (Boats)',
    'Key Lento': 'Key Lento',
    'Keys': 'Keys',
    'Grassrivers 02 (Watson Bay)': 'Grassrivers 02 (Watson Bay)',
    'Prison': 'Prison',
    'Vice Beach (A)': 'Vice Beach (A)',
    'Vice Beach (B)': 'Vice Beach (B)',
    'Rooftop Party': 'Rooftop Party',
    'Venetian Islands': 'Venetian Islands',
    'Beach': 'Beach',
    'Skyline': 'Skyline',
    'Vice City 03 (Basketball)': 'VC 03 (Basketball)',
    'Vice City Postcard': 'Vice City Postcard',
    'Motorboats (A)': 'Motorboats (A-B)',
    'Motorboats (B)': 'Motorboats (A-B)',
    'Vice City 08 (Ferris Wheel)': 'VC 08 (Ferris Wheel)',
    'Convertible': 'Convertible',
    'Raul Bautista 03 (Motorboat)': 'Raul Bautista 03 (Motorboat)',
    'Highway (Peacock Bay) (A)': 'Peacock Bay (A)',
    'Highway (Peacock Bay) (B)': 'Peacock Bay (B)',
    'Ambrosia 01 (Bikers)': 'Ambrosia 01 (Bikers)',
    'Ambrosia 02 (Panorama)': 'Ambrosia 02 (Panorama)',
    'Ambrosia 04 (Fires)': 'Ambrosia 04 (Fires)',
    'Ambrosia Postcard (X)': 'Ambrosia Postcard (X)',
    'Chase (2) (A)': 'Chase (2) (A)',
    'Chase (2) (B)': 'Chase (2) (B)',
    'Port Gellhorn Postcard (X)': 'PGH Postcard (X)',
    'Port Gellhorn 04 (Delights) (X)': 'PGH 04 (Delights) (X)',
    'Mount Kalaga National Park 04 (Mountain Pass) (X)': 'MK NP 04 (Mountain Pass) (X)',
    'Jason Duval 05 (Machine Gun)': 'Jason Duval 05 (Machine Gun)',
}


def infer_zone(xyz):
    """Infer zone from xyz. Based on real bounds:
       PGH:    X -6551..-4750, Y 3248..6000   (far northwest)
       Ambrosia: X -2744..-1409, Y 3351..5134  (north-central)
       Keys:   X -6468..-1682, Y -7599..-5148 (far south)
       Grassrivers: X -5283..-3359, Y -3370..-2761 (west-central)
       Vice:   X -21..2354, Y -426..1952       (east-central)
    """
    if not xyz: return 'unknown'
    x, y = xyz[0], xyz[1]
    # Far south = Keys
    if y < -4500: return 'keys'
    # West-central with negative Y = Grassrivers
    if x < -3000 and -4000 < y < -1000: return 'grassrivers'
    # Far northwest = Port Gellhorn
    if x < -3500 and y > 2500: return 'port_gellhorn'
    # North-central = Ambrosia
    if -3500 < x < -800 and y > 2500: return 'ambrosia'
    # Vice City: east of x=-1500, y between -1000 and 2500
    if x > -1500 and -1500 < y < 2500: return 'vice'
    # Default fallback
    return 'vice'


ZONE_OVERRIDE = {
    'Leonida Keys 01 (Airplane) (X)': 'keys',
    'Leonida Keys Postcard (X)': 'keys',
    'Leonida Keys 05 (Boats)': 'keys',
    'Leonida Keys 02 (Sidewalk)': 'keys',
    'Key Lento': 'keys',
    'Keys': 'keys',
    'Grassrivers 02 (Watson Bay)': 'grassrivers',
    'Grassrivers Postcard (X)': 'grassrivers',
    'Prison': 'grassrivers',
    'Prison Tower': 'grassrivers',
    'Ambrosia 01 (Bikers)': 'ambrosia',
    'Ambrosia 02 (Panorama)': 'ambrosia',
    'Ambrosia 04 (Fires)': 'ambrosia',
    'Ambrosia Postcard (X)': 'ambrosia',
    'Chase (2) (A)': 'ambrosia',
    'Chase (2) (B)': 'ambrosia',
    'Port Gellhorn Postcard (X)': 'port_gellhorn',
    'Port Gellhorn 04 (Delights) (X)': 'port_gellhorn',
    'Port Gellhorn 01 (Starlet Motel)': 'port_gellhorn',
    'Port Gellhorn 05 (Fire)': 'port_gellhorn',
    'Mount Kalaga National Park 02 (Helicopter) (X)': 'port_gellhorn',
    'Mount Kalaga National Park 04 (Mountain Pass) (X)': 'port_gellhorn',
}

ZONE_TO_CLUSTER = {
    'vice': 'lm_vc',
    'ambrosia': 'lm_ambrosia',
    'keys': 'lm_keys',
    'grassrivers': 'lm_gv',
    'port_gellhorn': 'lm_pgh',
}


def world_to_canvas(xyz):
    x, y = xyz[0], xyz[1]
    nx = (x - WORLD_X_MIN) / (WORLD_X_MAX - WORLD_X_MIN)
    ny = (y - WORLD_Y_MIN) / (WORLD_Y_MAX - WORLD_Y_MIN)
    cx = PAD + nx * (CANVAS_W - 2 * PAD)
    cy = PAD + (1 - ny) * (CANVAS_H - 2 * PAD)
    return round(cx, 1), round(cy, 1)


sys.path.insert(0, str(TOOLS))
from leak_cam_audit import (
    get_class,
    is_triangulation_trusted,
)


def apply_anti_overlap(nodes, iterations=200):
    """Push overlapping nodes apart while keeping them near their original world position."""
    import math
    # Track original positions to apply spring-back
    orig = [(n['x'], n['y']) for n in nodes]

    for it in range(iterations):
        moved = 0
        # Pairwise repulsion
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                dx = b['x'] - a['x']
                dy = b['y'] - a['y']
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < MIN_SEP and dist > 0.01:
                    # Push apart
                    overlap = MIN_SEP - dist
                    push = overlap * 0.5
                    ux, uy = dx / dist, dy / dist
                    a['x'] -= ux * push
                    a['y'] -= uy * push
                    b['x'] += ux * push
                    b['y'] += uy * push
                    moved += 1
                elif dist < 0.01:
                    # Coincident — random nudge
                    a['x'] -= 5
                    b['x'] += 5
                    moved += 1
        # Spring back toward original (weak)
        for i, n in enumerate(nodes):
            ox, oy = orig[i]
            n['x'] += (ox - n['x']) * 0.02
            n['y'] += (oy - n['y']) * 0.02
        # Clamp to canvas
        for n in nodes:
            n['x'] = max(PAD, min(CANVAS_W - PAD, n['x']))
            n['y'] = max(PAD, min(CANVAS_H - PAD, n['y']))
        if moved == 0:
            print(f"  Converged after {it+1} iterations")
            break
    else:
        print(f"  Stopped at {iterations} iterations (still moving)")

    # Round to integers
    for n in nodes:
        n['x'] = round(n['x'], 1)
        n['y'] = round(n['y'], 1)


def main():
    cams = json.loads((DATA / 'cameras.json').read_text())
    lms = json.loads((DATA / 'landmarks.json').read_text())
    pixels = json.loads((DATA / 'pixels.json').read_text())
    tiers = json.loads(TIERS_JSON.read_text())

    parents_of = {}
    for child, pix in pixels.items():
        if child not in cams: continue
        if not cams[child].get('xyz'): continue
        # Skip cams whose xyz is HUD-locked — they have no "parents" in the
        # calibration dependency graph (their pose comes from the HUD, not
        # from other cams).
        if is_triangulation_trusted(child, cameras=cams): continue
        parents = set()
        for lm_name in pix:
            lm = lms.get(lm_name)
            if not isinstance(lm, dict): continue
            for src in (lm.get('source_cameras') or []):
                if src == child: continue
                if src in cams: parents.add(src)
        parents_of[child] = parents

    include = set()
    for name, cam in cams.items():
        if cam.get('xyz') and not is_triangulation_trusted(name, cameras=cams):
            include.add(name)
    # Only include HUD-locked cams that are referenced as parents (= they
    # actually contribute to at least one community cam's calibration).
    referenced_locked = set()
    for child, parents in parents_of.items():
        for p in parents:
            if is_triangulation_trusted(p, cameras=cams):
                referenced_locked.add(p)
    include |= referenced_locked
    total_locked = sum(1 for n in cams if is_triangulation_trusted(n, cameras=cams))
    print(f"Filtered: kept {len(referenced_locked)} useful HUD-locked cams "
          f"(dropped {total_locked - len(referenced_locked)} unused)")

    edges = []
    clusters_used = set()
    for child, parents in parents_of.items():
        if child not in include: continue
        by_zone = {}
        for p in parents:
            zone = ZONE_OVERRIDE.get(p) or infer_zone(cams[p].get('xyz'))
            by_zone.setdefault(zone, []).append(p)
        for zone, ps in by_zone.items():
            cluster_id = ZONE_TO_CLUSTER.get(zone)
            if cluster_id and len(ps) >= 2:
                clusters_used.add(cluster_id)
                edges.append([cluster_id, child, 'calib'])
                for p in ps:
                    edges.append([p, cluster_id, 'lm'])
            else:
                for p in ps:
                    edges.append([p, child, 'calib'])

    seen = set()
    edges_dedup = []
    for e in edges:
        key = tuple(e)
        if key in seen: continue
        seen.add(key)
        edges_dedup.append(e)
    edges = edges_dedup

    nodes = []
    for name in include:
        cam = cams[name]
        xyz = cam.get('xyz')
        ypr = cam.get('ypr')
        fov = cam.get('fov') or [None, None]
        source = cam.get('source', '') or ''
        cls = get_class(name, cameras=cams)
        is_locked_xyz = is_triangulation_trusted(name, cameras=cams)
        tier_info = tiers['cameras'].get(name, {})
        tier = tier_info.get('tier', 'unknown')
        zone = ZONE_OVERRIDE.get(name) or infer_zone(xyz)

        # Node type for the dashboard. 'leak' is retained as the visual
        # bucket for HUD-locked cams (preserves the existing dashboard CSS).
        # Future: the dashboard could split this into per-class buckets
        # (anchor_full / anchor_pos_fov / anchor_pos) for finer color-coding.
        if is_locked_xyz:
            ntype = 'leak'
        elif tier == 'anchor':
            ntype = 'anchor'
        elif tier == 'high':
            ntype = 'high'
        elif tier == 'medium':
            ntype = 'medium'
        elif tier == 'low':
            ntype = 'low'
        else:
            ntype = 'unverified'

        if xyz:
            x, y = world_to_canvas(xyz)
        else:
            x, y = CANVAS_W / 2, CANVAS_H / 2

        # Thumb resolution: explicit map (for renamed files), else cam_name itself
        thumb_name = THUMB_MAP.get(name)
        if thumb_name is None:
            # Try cam name directly (most new thumbs are saved as cam_name.jpg)
            potential_thumb = REPO / 'docs' / 'thumbs' / f'{name}.jpg'
            if potential_thumb.exists():
                thumb_name = name

        nodes.append({
            'id': name,
            'label': name,
            'type': ntype,
            'constraint_class': cls,  # V2: expose raw class for richer dashboard UI
            'zone': zone,
            'x': x,
            'y': y,
            'xyz': xyz,
            'ypr': ypr,
            'fov': fov,
            'tier': tier,
            'source': source,
            'thumb': thumb_name,
        })

    for cluster_id in clusters_used:
        label, zone, world_pos = CLUSTER_DEFS[cluster_id]
        x, y = world_to_canvas(list(world_pos))
        nodes.append({
            'id': cluster_id,
            'label': label,
            'type': 'lm_cluster',
            'zone': zone,
            'x': x,
            'y': y,
        })

    # Anti-overlap: spread out nodes that are too close
    print(f"Running anti-overlap (target {MIN_SEP}px min separation)...")
    apply_anti_overlap(nodes, iterations=200)

    by_type = {}
    for n in nodes:
        by_type[n['type']] = by_type.get(n['type'], 0) + 1
    print(f"Nodes: {len(nodes)}")
    for t, c in sorted(by_type.items()):
        print(f"  {t}: {c}")
    print(f"Edges: {len(edges)}")

    html = build_html(nodes, edges)
    out = TOOLS / 'cam_health.html'
    out.write_text(html)
    print(f"\u2713 Wrote {out}")
    print(f"  Visit: http://localhost:8765/cam_health.html")


def build_html(nodes, edges):
    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)

    template = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>gtamaplib --- Dependency Graph</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=DM+Sans:wght@300;400;500&display=swap');
:root {
  --bg:#0a0a0c; --surface:#13131a; --surface2:#1c1c26; --border:#252535;
  --green:#4ade80; --yellow:#f59e0b; --red:#f87171; --blue:#60a5fa; --violet:#c084fc;
  --text:#e2e2f0; --dim:#5a5a7a; --mid:#9090b0;
  --mono:'JetBrains Mono',monospace; --sans:'DM Sans',sans-serif;
}
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:var(--sans); background:var(--bg); color:var(--text); min-height:100vh; padding:20px; font-size:13px; }
header { display:flex; align-items:center; gap:14px; margin-bottom:16px; flex-wrap:wrap; }
.logo { font-family:var(--mono); font-size:13px; font-weight:700; color:var(--green); }
.title { font-family:var(--mono); font-size:11px; color:var(--mid); letter-spacing:.1em; text-transform:uppercase; }
.spacer { flex:1; }
.nav-link { font-family:var(--mono); font-size:11px; color:var(--blue); text-decoration:none; padding:5px 10px; border:1px solid var(--border); border-radius:5px; transition:all .15s; }
.nav-link:hover { background:var(--surface2); border-color:var(--blue); }
.summary { display:flex; gap:8px; margin-bottom:14px; flex-wrap:wrap; }
.stat { background:var(--surface); border:1px solid var(--border); border-radius:6px; padding:9px 13px; min-width:90px; }
.stat-lbl { font-family:var(--mono); font-size:9px; color:var(--dim); letter-spacing:.1em; text-transform:uppercase; margin-bottom:3px; }
.stat-val { font-family:var(--mono); font-size:18px; font-weight:700; color:var(--text); }
.stat.leak .stat-val { color:var(--violet); }
.stat.anchor .stat-val { color:var(--violet); }
.stat.high .stat-val { color:var(--green); }
.stat.medium .stat-val { color:var(--blue); }
.stat.low .stat-val { color:var(--yellow); }
.stat.unverified .stat-val { color:var(--mid); }
.filters { display:flex; gap:8px; align-items:center; margin-bottom:14px; padding:9px 13px; background:var(--surface); border:1px solid var(--border); border-radius:6px; flex-wrap:wrap; }
.filter-lbl { font-family:var(--mono); font-size:10px; color:var(--dim); letter-spacing:.08em; text-transform:uppercase; margin-right:6px; }
.chip-btn { font-family:var(--mono); font-size:10px; font-weight:600; padding:5px 10px; border-radius:11px; background:var(--surface2); border:1px solid var(--border); color:var(--mid); cursor:pointer; transition:all .15s; user-select:none; }
.chip-btn:hover { color:var(--text); border-color:var(--mid); }
.chip-btn.active { background:rgba(96,165,250,.12); border-color:var(--blue); color:var(--blue); }
.canvas-wrap { border:1px solid var(--border); border-radius:8px; background:var(--surface); overflow:auto; position:relative; }
canvas { display:block; cursor:default; background:var(--surface); }
.legend { display:flex; gap:18px; flex-wrap:wrap; margin-top:12px; padding:10px 14px; background:var(--surface); border:1px solid var(--border); border-radius:6px; }
.legend-item { display:flex; align-items:center; gap:7px; font-size:10px; font-family:var(--mono); color:var(--mid); }
.dot { width:11px; height:11px; border-radius:50%; flex-shrink:0; }
#tooltip { position:fixed; background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:12px 14px; font-size:12px; pointer-events:none; display:none; z-index:999; width:480px; line-height:1.4; box-shadow:0 6px 24px rgba(0,0,0,.5); transform:translateY(-50%); }
#tooltip strong { display:block; font-size:13px; font-weight:600; margin-bottom:8px; color:var(--text); }
#tooltip .top-grid { display:flex; gap:14px; }
#tooltip .top-grid .info { flex:1; min-width:0; }
#tooltip .top-grid .thumb-wrap { width:200px; flex-shrink:0; }
#tooltip img.thumb { width:200px; height:130px; object-fit:cover; border-radius:5px; display:block; }
#tooltip .row { font-family:var(--mono); margin-top:5px; }
#tooltip .label { display:block; color:var(--dim); font-size:9px; letter-spacing:.08em; text-transform:uppercase; margin-bottom:2px; }
#tooltip .value { display:block; color:var(--text); font-size:10.5px; word-break:break-word; line-height:1.5; }
#tooltip .row.inline { display:flex; gap:8px; align-items:baseline; margin-top:3px; }
#tooltip .row.inline .label { display:inline; font-size:9px; margin:0; min-width:34px; }
#tooltip .row.inline .value { display:inline; font-size:10.5px; }
#tooltip .badge { display:inline-block; font-size:9px; padding:2px 7px; border-radius:9px; font-weight:700; letter-spacing:.04em; text-transform:uppercase; margin-right:4px; margin-bottom:4px; }
#tooltip .below { margin-top:10px; }
.hint { font-size:10px; font-family:var(--mono); color:var(--dim); margin-top:8px; }
</style>
</head>
<body>
<header>
  <div class="logo">gtamaplib</div>
  <div class="title">Camera Dependency Graph</div>
  <div class="spacer"></div>
  <a href="/calib.html" class="nav-link">to Calibration Tool</a>
</header>
<div class="summary" id="summary"></div>
<div class="filters">
  <span class="filter-lbl">Tier</span>
  <button class="chip-btn active" data-filter="all">All</button>
  <button class="chip-btn" data-filter="leak">Leak</button>
  <button class="chip-btn" data-filter="anchor">Anchor</button>
  <button class="chip-btn" data-filter="high">High</button>
  <button class="chip-btn" data-filter="medium">Medium</button>
  <button class="chip-btn" data-filter="low">Low</button>
  <button class="chip-btn" data-filter="unverified">Unverified</button>
  <span class="filter-lbl" style="margin-left:14px">Zone</span>
  <button class="chip-btn active" data-zone="all">All</button>
  <button class="chip-btn" data-zone="vice">Vice</button>
  <button class="chip-btn" data-zone="ambrosia">Ambrosia</button>
  <button class="chip-btn" data-zone="keys">Keys</button>
  <button class="chip-btn" data-zone="grassrivers">Grassrivers</button>
  <button class="chip-btn" data-zone="port_gellhorn">Port Gellhorn</button>
</div>
<div class="canvas-wrap">
  <canvas id="dag" width="__W__" height="__H__"></canvas>
</div>
<div class="legend">
  <div class="legend-item"><div class="dot" style="background:#c084fc"></div>Leak / Anchor</div>
  <div class="legend-item"><div class="dot" style="background:#4ade80"></div>High</div>
  <div class="legend-item"><div class="dot" style="background:#60a5fa"></div>Medium</div>
  <div class="legend-item"><div class="dot" style="background:#f59e0b"></div>Low</div>
  <div class="legend-item"><div class="dot" style="background:#5a5a7a"></div>Unverified</div>
  <div class="legend-item"><div class="dot" style="background:#f87171"></div>LM cluster</div>
</div>
<p class="hint">Positions reflect world coordinates (north up). Hover for live data.</p>
<div id="tooltip"></div>
<script>
const W = __W__, H = __H__;
const canvas = document.getElementById('dag');
const ctx = canvas.getContext('2d');
const COLORS = { leak:'#c084fc', anchor:'#c084fc', high:'#4ade80', medium:'#60a5fa', low:'#f59e0b', unverified:'#5a5a7a', lm_cluster:'#f87171', edge:'#4ade80', edge_lm:'#f87171', text:'#e2e2f0', textSub:'#9090b0' };
const nodes = __NODES__;
const edges = __EDGES__;
let activeFilter = 'all';
let activeZone = 'all';
let hoveredNode = null;

function nodeColor(t) { return COLORS[t] || COLORS.unverified; }
function nodeRadius(n) {
  if (n.type === 'lm_cluster') return 16;
  if (n.type === 'leak' || n.type === 'anchor') return 11;
  return 9;
}
function nodeVisibleCam(n) {
  if (activeFilter !== 'all' && n.type !== activeFilter) return false;
  if (activeZone !== 'all' && n.zone !== activeZone) return false;
  return true;
}
function clusterVisible(c) {
  for (const e of edges) {
    if (e[0] === c.id || e[1] === c.id) {
      const other = e[0] === c.id ? e[1] : e[0];
      const n = nodes.find(x => x.id === other);
      if (n && n.type !== 'lm_cluster' && nodeVisibleCam(n)) return true;
    }
  }
  return false;
}
function isVisible(n) {
  if (n.type === 'lm_cluster') return clusterVisible(n);
  return nodeVisibleCam(n);
}

function drawArrow(x1, y1, x2, y2, color, lw, dashed) {
  const dx = x2 - x1, dy = y2 - y1, len = Math.sqrt(dx*dx + dy*dy);
  if (len < 1) return;
  const ux = dx/len, uy = dy/len;
  const r1 = 11, r2 = 12;
  const sx = x1 + ux * r1, sy = y1 + uy * r1;
  const ex = x2 - ux * (r2 + 6), ey = y2 - uy * (r2 + 6);
  ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ex, ey);
  ctx.strokeStyle = color; ctx.lineWidth = lw;
  ctx.setLineDash(dashed ? [3, 2] : []);
  ctx.stroke();
  ctx.setLineDash([]);
  const ang = Math.atan2(uy, ux);
  ctx.save(); ctx.translate(ex + ux*6, ey + uy*6); ctx.rotate(ang);
  ctx.beginPath();
  ctx.moveTo(-5, -3); ctx.lineTo(0, 0); ctx.lineTo(-5, 3);
  ctx.strokeStyle = color; ctx.lineWidth = 1.1; ctx.stroke();
  ctx.restore();
}

function draw() {
  ctx.clearRect(0, 0, W, H);
  for (const [a, b, type] of edges) {
    const na = nodes.find(n => n.id === a);
    const nb = nodes.find(n => n.id === b);
    if (!na || !nb) continue;
    if (!isVisible(na) || !isVisible(nb)) continue;
    const isHov = hoveredNode && (hoveredNode.id === a || hoveredNode.id === b);
    ctx.globalAlpha = isHov ? 0.85 : (hoveredNode ? 0.06 : 0.28);
    const color = type === 'calib' ? COLORS.edge : COLORS.edge_lm;
    const lw = isHov ? 2 : (type === 'calib' ? 1.2 : 0.7);
    drawArrow(na.x, na.y, nb.x, nb.y, color, lw, type === 'lm');
    ctx.globalAlpha = 1;
  }
  for (const n of nodes) {
    if (!isVisible(n)) continue;
    const isHov = hoveredNode && hoveredNode.id === n.id;
    const color = nodeColor(n.type);
    const r = nodeRadius(n);
    ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, Math.PI*2);
    ctx.fillStyle = isHov ? color : color + '22';
    ctx.fill();
    ctx.strokeStyle = color; ctx.lineWidth = isHov ? 2.2 : 1.4;
    ctx.stroke();
    const lines = n.label.split('\\n');
    ctx.font = '9.5px JetBrains Mono';
    ctx.textAlign = 'center';
    ctx.fillStyle = isHov ? COLORS.text : COLORS.textSub;
    const startY = n.y + r + 8;
    lines.forEach((l, i) => ctx.fillText(l, n.x, startY + i * 11));
  }
}

function getNodeAt(mx, my) {
  for (let i = nodes.length - 1; i >= 0; i--) {
    const n = nodes[i];
    if (!isVisible(n)) continue;
    const dx = mx - n.x, dy = my - n.y;
    if (Math.sqrt(dx*dx + dy*dy) < nodeRadius(n) + 3) return n;
  }
  return null;
}

function tierBadge(tier) {
  const colors = { anchor:'#c084fc', high:'#4ade80', medium:'#60a5fa', low:'#f59e0b', unverified:'#9090b0', leak:'#c084fc' };
  const c = colors[tier] || '#9090b0';
  return '<span class="badge" style="background:' + c + '22;color:' + c + '">' + tier + '</span>';
}

function showTooltip(n, x, y) {
  const t = document.getElementById('tooltip');
  if (!n) { t.style.display = 'none'; return; }
  let html = '<strong>' + n.label.replace(/\\n/g, ' ') + '</strong>';
  if (n.type === 'lm_cluster') {
    html += '<div class="row"><span class="label">Type</span><span class="value">LM cluster - ' + n.zone + '</span></div>';
  } else {
    // Top section: title + tier badge + info on left, thumb on right
    let topInfo = '<div style="margin-bottom:5px">' + tierBadge(n.type) + '</div>';
    if (n.xyz) {
      const xyz = n.xyz.map(v => v.toFixed(1)).join(', ');
      topInfo += '<div class="row inline"><span class="label">xyz</span><span class="value">(' + xyz + ')</span></div>';
    }
    if (n.ypr) {
      const ypr = n.ypr.map(v => v.toFixed(2)).join(', ');
      topInfo += '<div class="row inline"><span class="label">ypr</span><span class="value">' + ypr + '</span></div>';
    }
    if (n.fov && n.fov[0]) {
      topInfo += '<div class="row inline"><span class="label">hfov</span><span class="value">' + n.fov[0].toFixed(2) + ' deg</span></div>';
    }
    if (n.source) {
      topInfo += '<div class="row inline"><span class="label">src</span><span class="value">' + n.source + '</span></div>';
    }

    if (n.thumb) {
      html += '<div class="top-grid"><div class="info">' + topInfo + '</div>' +
              '<div class="thumb-wrap"><img class="thumb" src="/thumbs/' + encodeURIComponent(n.thumb) + '.jpg" onerror="this.parentElement.style.display=\\'none\\'"></div></div>';
    } else {
      html += topInfo;
    }

    const parents = edges.filter(e => e[1] === n.id).map(e => e[0]);
    const children = edges.filter(e => e[0] === n.id).map(e => e[1]);
    if (parents.length) {
      const names = parents.map(p => { const pn = nodes.find(x => x.id === p); return pn ? pn.label.replace(/\\n/g, ' ') : p; });
      const sliced = names.slice(0, 6).join(', ');
      const more = names.length > 6 ? ' (+' + (names.length - 6) + ')' : '';
      html += '<div class="row below"><span class="label">Parents</span><span class="value">' + sliced + more + '</span></div>';
    }
    if (children.length) {
      const names = children.map(c => { const cn = nodes.find(x => x.id === c); return cn ? cn.label.replace(/\\n/g, ' ') : c; });
      const sliced = names.slice(0, 6).join(', ');
      const more = names.length > 6 ? ' (+' + (names.length - 6) + ')' : '';
      html += '<div class="row"><span class="label">Children</span><span class="value">' + sliced + more + '</span></div>';
    }
  }
  t.innerHTML = html;
  t.style.display = 'block';
  const rect = t.getBoundingClientRect();
  let tx = x + 18;
  let ty = y;  // center vertically on cursor (CSS translateY(-50%) does the centering)
  if (tx + rect.width > window.innerWidth - 12) tx = x - rect.width - 18;
  // Clamp ty so tooltip doesn't go off-screen vertically
  const halfH = rect.height / 2;
  if (ty - halfH < 12) ty = halfH + 12;
  if (ty + halfH > window.innerHeight - 12) ty = window.innerHeight - halfH - 12;
  t.style.left = tx + 'px';
  t.style.top = ty + 'px';
}

canvas.addEventListener('mousemove', e => {
  const rect = canvas.getBoundingClientRect();
  const mx = (e.clientX - rect.left) * canvas.width / rect.width;
  const my = (e.clientY - rect.top) * canvas.height / rect.height;
  const n = getNodeAt(mx, my);
  if (n !== hoveredNode) {
    hoveredNode = n;
    canvas.style.cursor = n ? 'pointer' : 'default';
    draw();
  }
  showTooltip(n, e.clientX, e.clientY);
});
canvas.addEventListener('mouseleave', () => {
  hoveredNode = null;
  document.getElementById('tooltip').style.display = 'none';
  draw();
});

document.querySelectorAll('.chip-btn[data-filter]').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.chip-btn[data-filter]').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    activeFilter = b.dataset.filter;
    draw(); renderSummary();
  });
});
document.querySelectorAll('.chip-btn[data-zone]').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.chip-btn[data-zone]').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    activeZone = b.dataset.zone;
    draw(); renderSummary();
  });
});

function renderSummary() {
  const visible = nodes.filter(n => n.type !== 'lm_cluster' && isVisible(n));
  const counts = { leak:0, anchor:0, high:0, medium:0, low:0, unverified:0 };
  for (const n of visible) { counts[n.type] = (counts[n.type] || 0) + 1; }
  const ve = edges.filter(([a,b]) => {
    const na = nodes.find(n=>n.id===a), nb = nodes.find(n=>n.id===b);
    return na && nb && isVisible(na) && isVisible(nb);
  });
  document.getElementById('summary').innerHTML =
    '<div class="stat leak"><div class="stat-lbl">Leak</div><div class="stat-val">' + counts.leak + '</div></div>' +
    '<div class="stat anchor"><div class="stat-lbl">Anchor</div><div class="stat-val">' + counts.anchor + '</div></div>' +
    '<div class="stat high"><div class="stat-lbl">High</div><div class="stat-val">' + counts.high + '</div></div>' +
    '<div class="stat medium"><div class="stat-lbl">Medium</div><div class="stat-val">' + counts.medium + '</div></div>' +
    '<div class="stat low"><div class="stat-lbl">Low</div><div class="stat-val">' + counts.low + '</div></div>' +
    '<div class="stat unverified"><div class="stat-lbl">Unverified</div><div class="stat-val">' + counts.unverified + '</div></div>' +
    '<div class="stat"><div class="stat-lbl">Edges</div><div class="stat-val">' + ve.length + '</div></div>';
}

renderSummary();
draw();
</script>
</body>
</html>
'''
    template = template.replace('__W__', str(CANVAS_W))
    template = template.replace('__H__', str(CANVAS_H))
    template = template.replace('__NODES__', nodes_json)
    template = template.replace('__EDGES__', edges_json)
    return template


if __name__ == '__main__':
    main()
