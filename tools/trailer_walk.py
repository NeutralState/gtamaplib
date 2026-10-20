#!/usr/bin/env python3
"""trailer_walk.py — shareable "trailer walk" page: each solved trailer/screenshot frame over the 3D model. [WALK-V1 2026-10-19]

Alexandre (idea 4): a public page where the community can step from one official trailer / screenshot camera to the
next and see the frame blended over the city model at its solved pose, with a mini map of where the shot was taken.

Selection (curated, official media only):
  - id starts with T (trailers) or S (screenshots): leak (L1) and Cyberleak (CL) cameras are left out on purpose;
  - pose_verified set, or confidence tier high/anchor (tools/generated/confidence_tiers.json);
  - not PROVISIONAL (notes), and a thumbnail exists in docs/thumbs (frames/ is never read).
Per camera the page gets: pose (xyz/ypr/fov), the 4 image-corner rays computed BY THE LIB (get_pixel_direction, same as
/api/scene3d -> view3d POV, zero convention risk in JS), the docs/thumbs JPEG inlined, and every marked landmark with
its clicked pixel and its reprojection (cam.get_pixel), normalized to [0,1].
Geometry: building volumes from tools/threejs/_mesh_solids.json (tools/mesh_solids.py --publish) + wireframe of the
meshes without a volume (bridges, cranes, ferris wheel...) from gtamapdata/building_meshes_procedural.json, packed as
base64 Int32 (5 cm) + Uint16 indices. No terrain, no map tiles: the heightmap and the basemap tiles are not ours to ship.
Output (ignored by git): tools/generated/trailer_walk.html — one self-contained file, page code in
tools/trailer_walk_template.html (three.js from jsdelivr).
Usage: .venv/bin/python tools/trailer_walk.py [--out f.html] [--include-leak]
"""
import argparse, base64, datetime, json, os, re, struct, sys

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS); sys.path.insert(0, REPO)
from common import get_cam
import gtamapdata as md

THUMBS = os.path.join(REPO, 'docs', 'thumbs')
TEMPLATE = os.path.join(THIS, 'trailer_walk_template.html')
OUT = os.path.join(THIS, 'generated', 'trailer_walk.html')
GOOD_TIERS = ('anchor', 'high')
Q = 20.0   # wire vertices quantized at 5 cm


def source_label(cd):
    """'Trailer 2 [4665]' -> ('Trailer 2', 'frame 4665'); 'Screenshot 1 — Ambrosia 02 [1]' -> ('Screenshot 1', '')."""
    s = cd.get('source') or ''
    m = re.search(r'\[(\d+)\]', s)
    frame = f'frame {m.group(1)}' if m and not s.startswith('Screenshot') else ''
    m = re.search(r't=(\d+(?:\.\d+)?)', s)
    if m and not frame:
        t = float(m.group(1)); frame = f'{int(t // 60)}:{t % 60:04.1f}'
    head = re.split(r' — | - | \[| \(', s, maxsplit=1)[0].strip()
    if head.startswith('Trailer 3'): head = 'Trailer 3 (Extended Look)'
    if head.startswith('Trailer 4'): head = 'Trailer 4'
    return head, frame


def status_label(pv):
    if not pv: return None
    m = re.match(r'(VERIFIED|SOLVED|LOCKED)\s+(\d{4}-\d{2}-\d{2})', pv)
    return f'{m.group(1).capitalize()} {m.group(2)}' if m else 'Verified'


def r1(v): return round(float(v), 1)


def select(include_leak):
    tiers = json.load(open(os.path.join(REPO, 'tools', 'generated', 'confidence_tiers.json')))['cameras']
    out = []
    for name, cd in md.cameras.items():
        cid = cd.get('id') or ''
        if not cd.get('xyz') or not cd.get('ypr') or not cd.get('fov') or not cd.get('size'): continue
        if not include_leak and cid[:1] not in ('T', 'S'): continue
        if 'PROVISIONAL' in json.dumps(cd.get('notes', '')) + json.dumps(cd.get('pose_verified', '')): continue
        tier = (tiers.get(name) or {}).get('tier') or 'unverified'
        if not (cd.get('pose_verified') or tier in GOOD_TIERS): continue
        if not os.path.exists(os.path.join(THUMBS, name + '.jpg')): continue
        out.append((name, cd, tier))
    def key(t):   # trailer order: T1..T4 then S2..S4, by frame number
        m = re.match(r'([A-Z]+)(\d+)/(\d+)', t[1]['id'] or '')
        return ((0 if m.group(1) == 'T' else 1), int(m.group(2)), int(m.group(3)), t[0]) if m else (9, 0, 0, t[0])
    return sorted(out, key=key)


def cam_entry(name, cd, tier):
    from common import cam_rms
    cam = get_cam(name)
    w, h = cd['size']
    corners = [[round(float(v), 6) for v in cam.get_pixel_direction(px)]
               for px in ((0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1))]
    obs = []
    for ln, px in sorted((md.pixels.get(name) or {}).items()):
        xyz = md.landmarks.get(ln)
        if px is None or xyz is None: continue
        try: pp = cam.get_pixel(tuple(xyz))
        except Exception: pp = None
        o = [ln, round(px[0] / w, 4), round(px[1] / h, 4)]
        if pp is not None and all(abs(float(v)) < 1e6 for v in pp):
            o += [round(float(pp[0]) / w, 4), round(float(pp[1]) / h, 4)]
        obs.append(o)
    with open(os.path.join(THUMBS, name + '.jpg'), 'rb') as f:
        thumb = 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode()
    src, frame = source_label(cd)
    rms = cam_rms(name)
    return {'name': name, 'id': cd.get('id'), 'tier': tier, 'status': status_label(cd.get('pose_verified')),
            'rms': round(rms, 2) if rms is not None else None, 'src': src, 'frame': frame,
            'xyz': [r1(v) for v in cd['xyz']], 'ypr': [round(float(v), 3) for v in cd['ypr']],
            'hfov': cd['fov'][0], 'size': cd['size'], 'corners': corners, 'obs': obs, 'thumb': thumb}


def pack_solids():
    S = json.load(open(os.path.join(THIS, 'threejs', '_mesh_solids.json')))
    out = {}
    for n, s in S.items():
        e = {'c': s.get('color') or '#9ca3af',
             'L': [[r1(L['z0']), r1(L['z1']), [[[c for p in ring for c in (r1(p[0]), r1(p[1]))]
                                                 for ring in [P['outer']] + list(P.get('holes') or [])]
                                                for P in L['polys']]] for L in s.get('layers') or []]}
        if s.get('fv') and s.get('ff'):
            e['fv'] = [r1(v) for v in s['fv']]; e['ff'] = s['ff']
        if e['L'] or e.get('fv'): out[n] = e
    return out


def pack_wire(solid_names):
    M = json.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json')))
    verts, vid, idx, meshes = [], {}, [], []
    for n, m in M.items():
        if n in solid_names and solid_names[n].get('L'): continue
        edges = m.get('world_edges') if isinstance(m, dict) else m
        if not edges: continue
        i0 = len(idx)
        for a, b in edges:
            for p in (a, b):
                k = tuple(int(round(float(v) * Q)) for v in p)
                if k not in vid: vid[k] = len(verts); verts.append(k)
                idx.append(vid[k])
        meshes.append([n, m.get('color', '#9ca3af') if isinstance(m, dict) else '#9ca3af', i0, len(idx) - i0])
    assert len(verts) < 65536, 'wire: too many vertices for Uint16 indices'
    pos = base64.b64encode(struct.pack('<%di' % (3 * len(verts)), *[c for v in verts for c in v])).decode()
    ind = base64.b64encode(struct.pack('<%dH' % len(idx), *idx)).decode()
    return {'q': Q, 'pos': pos, 'idx': ind, 'meshes': meshes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--include-leak', action='store_true', help='also L1/CL cameras (not for the public page)')
    a = ap.parse_args()
    sel = select(a.include_leak)
    cams = [cam_entry(*t) for t in sel]
    solids = pack_solids()
    wire = pack_wire(solids)
    lms = [[r1(x[0]), r1(x[1]), r1(x[2])] for x in md.landmarks.values() if x is not None]
    data = {'generated': datetime.date.today().isoformat(), 'cams': cams, 'solids': solids, 'wire': wire,
            'landmarks': lms, 'lm_xyz': {o[0]: [r1(v) for v in md.landmarks[o[0]]] for c in cams for o in c['obs']}}
    blob = json.dumps(data, separators=(',', ':'), ensure_ascii=False).replace('</', '<\\/')
    html = open(TEMPLATE, encoding='utf-8').read().replace('/*__WALK_DATA__*/null', blob)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f: f.write(html)
    sz = lambda o: len(json.dumps(o, separators=(',', ':'))) // 1024
    print(f'{len(cams)} cameras -> {a.out} ({os.path.getsize(a.out) // 1024} KB: thumbs '
          f'{sum(len(c["thumb"]) for c in cams) // 1024} KB, solids {sz(solids)} KB, wire {sz(wire)} KB, '
          f'landmarks {sz(lms)} KB)')
    for c in cams: print(f'  {c["id"]:<8} {c["tier"]:<10} {str(c["rms"]):>6}\'  {len(c["obs"]):>3} obs  {c["name"]}')


if __name__ == '__main__':
    main()
