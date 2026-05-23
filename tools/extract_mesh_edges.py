#!/usr/bin/env python3
"""
Extract wireframe edges from gtamaplib's procedural Landmark classes
(FourSeasons, SunshineSkywayBridge) and dump as JSON for the frontend.

The classes have a `render_on_camera(cam)` method that calls
`cam.render_line(...)` many times to draw their wireframe. We hijack
that by passing a fake "cam" object whose render_line just stores the
endpoint pair instead of drawing.

Output: gtamapdata/building_meshes_procedural.json with structure:
  {
    "Four Seasons Hotel Miami": {
      "color": "#60a5fa",
      "world_edges": [
        [[x1,y1,z1], [x2,y2,z2]],
        ...
      ]
    },
    "Sunshine Skyway Bridge": { ... }
  }

Then the frontend can iterate these edges, project each endpoint via
cam.get_pixel(xyz), and draw lines in pixel space — same as Portofino.
"""

import json
import os
import sys

REPO = os.path.expanduser('~/Downloads/gtamaplib-main')
sys.path.insert(0, REPO)

import gtamaplib as ml
import gtamapdata as md
from OneThousandVenetian import OneThousandVenetian


class FakeCam:
    """Recording proxy: every render_line call appends to self.edges.
    Provides .xy attribute that some Landmark classes use to determine
    which faces to hide."""
    def __init__(self, xy=(99999, 99999)):
        self.edges = []
        self.xy = xy  # far-away viewpoint so no face is hidden

    def render_line(self, pair, fill=None, width=1, color=None, **kwargs):
        # `pair` is (xyz1, xyz2) — two 3-tuples
        try:
            a = [float(x) for x in pair[0]]
            b = [float(x) for x in pair[1]]
            self.edges.append([a, b])
        except (TypeError, ValueError) as e:
            print(f'  skipped edge (bad coords): {e}')


def extract_for_class(cls, color, **kwargs):
    """Instantiate, call render_on_camera with FakeCam, return edges."""
    instance = cls(**kwargs)
    fake = FakeCam()
    try:
        instance.render_on_camera(fake)
    except AttributeError as e:
        print(f'  render_on_camera missing or failed for {cls.__name__}: {e}')
        # Try alternative method names
        for method_name in ['render', 'draw_on_camera', 'render_lines']:
            if hasattr(instance, method_name):
                getattr(instance, method_name)(fake)
                break
    return fake.edges


print('Extracting Four Seasons edges (4 viewpoint passes for full coverage)...')
fs_edges = []
fs_seen = set()
try:
    # 4 viewpoints (NE, NW, SE, SW corners far away) to ensure all faces visible
    for vp_name, vp in [('NE', (99999, 99999)), ('NW', (-99999, 99999)),
                        ('SW', (-99999, -99999)), ('SE', (99999, -99999))]:
        instance = ml.FourSeasons()
        fake = FakeCam(xy=vp)
        try:
            instance.render_on_camera(fake)
        except Exception as e:
            print(f'  pass {vp_name} failed: {e}')
            continue
        added = 0
        for edge in fake.edges:
            # Dedupe by sorted tuple of endpoints
            key = tuple(sorted([tuple(edge[0]), tuple(edge[1])]))
            if key not in fs_seen:
                fs_seen.add(key)
                fs_edges.append(edge)
                added += 1
        print(f'  pass {vp_name}: +{added} edges (total {len(fs_edges)})')
except Exception as e:
    print(f'  FAILED: {e}')
    import traceback
    traceback.print_exc()
print(f'  → {len(fs_edges)} total unique edges')

print('Extracting Sunshine Skyway Bridge edges...')
try:
    ssb_edges = extract_for_class(ml.SunshineSkywayBridge, '#4ade80')
    print(f'  → {len(ssb_edges)} edges')
except Exception as e:
    print(f'  FAILED: {e}')
    import traceback
    traceback.print_exc()
    ssb_edges = []

# Optionally: HanksWaffles too
print('Extracting HanksWaffles edges...')
try:
    hw_edges = extract_for_class(ml.HanksWaffles, '#fbbf24')
    print(f'  → {len(hw_edges)} edges')
except Exception as e:
    print(f'  SKIP: {e}')
    hw_edges = []

print('Extracting OneThousandVenetian edges...')
try:
    instance = OneThousandVenetian(md, ml)
    fake = FakeCam()
    instance.render_on_camera(fake)
    otv_edges = fake.edges
    print(f'  → {len(otv_edges)} edges')
except Exception as e:
    print(f'  FAILED: {e}')
    import traceback
    traceback.print_exc()
    otv_edges = []

result = {}
if fs_edges:
    result['Four Seasons Hotel Miami'] = {
        'color': '#60a5fa',
        'world_edges': fs_edges,
    }
if ssb_edges:
    result['Sunshine Skyway Bridge'] = {
        'color': '#4ade80',
        'world_edges': ssb_edges,
    }
if hw_edges:
    result['HanksWaffles'] = {
        'color': '#fbbf24',
        'world_edges': hw_edges,
    }
if otv_edges:
    result['1000 Venetian Way'] = {
        'color': '#f472b6',
        'world_edges': otv_edges,
    }

out_path = os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')
with open(out_path, 'w') as f:
    json.dump(result, f, indent=2)

print(f'\n✓ Wrote {out_path}')
print(f'  Buildings: {list(result.keys())}')
total = sum(len(v['world_edges']) for v in result.values())
print(f'  Total edges: {total}')
