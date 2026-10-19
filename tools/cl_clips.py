#!/usr/bin/env python3
"""cl_clips.py — group the cyberleak (build 2026) cameras into clips. [CL-CLIPS-V1 2026-10-18]

Alexandre: the long cyberleak clips (biplane, prison...) gave one camera per frame, which floods the list and the map.
Each frame stays its own camera (own pose + markings = independent constraints), but they now share a clip:
  id = "CL/<clip>-<frame>" (e.g. CL/1-v0770), "CL/<clip>" for single-frame clips; "clip" = "CL/<clip>",
  "clip_title", "clip_order" (time in the video). The calibration tool shows one row per clip (frames inside) and the map /
  3D view draw one path per clip with the frustum of the selected frame only. Frames without markings are hidden by default.
Usage: python3 tools/cl_clips.py [--apply]
"""
import json, os, re, sys, tempfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = os.path.join(REPO, 'gtamapdata', 'cameras.json')
CLIPS = [  # clip, title, [(camera, frame tag, order)]
    (1, 'Biplane (Video)', [('Biplane (Video) v%s' % v, 'v' + v, float(v) / 30) for v in ('0770', '0820', '0900', '1080', '1380', '1980', '2370', '2580', '2811', '3000')]),
    (2, 'Prison (Video)', [('Prison (Aerial) (Biplane)', 'aerial', 0.0), ('Prison (Video) v091 (Wing)', 'v091', 3.03), ('Prison (Video) v160', 'v160', 5.3), ('Prison (Video) v250', 'v250', 8.33),
                           ('Prison (Video) v310', 'v310', 10.3), ('Prison (Video) f100', 'f100', 10.83), ('Prison (Video) f140', 'f140', 12.17), ('Prison (Video) f180', 'f180', 13.5),
                           ('Prison (Video) v500', 'v500', 16.7), ('Prison (Video) v600', 'v600', 20.0), ('Prison (Video) v680', 'v680', 22.7)]),
    (3, 'Biplane Night (Video)', [('Biplane Night (Video) v084', 'v084', 84.0), ('Biplane Night (Video) v086', 'v086', 86.0), ('Biplane Night (Vice Beach)', 'vicebeach', 100.0),
                                  ('Biplane Night (Video) Last', 'last', 109.0)]),
    (4, 'VCIA Night (Runway)', [('VCIA Night (Runway)', None, 0.0)]),
    (5, 'The Moose Trap (Roller Coaster)', [('The Moose Trap (Roller Coaster) (2026)', None, 0.0)]),
    (6, 'Pier Sixty-Six TV ad (Gamestore)', [('Pier Sixty-Six TV ad (Gamestore)', None, 0.0)])]


def main():
    C = json.load(open(P)); n = 0
    for k, title, frames in CLIPS:
        for cam, tag, order in frames:
            c = C[cam]; old = c['id']; new = 'CL/%d' % k + ('-' + tag if tag else '')
            if old != new:
                c['notes'] = 'CL-CLIPS-V1 2026-10-18: id %s -> %s (cyberleak clip CL/%d "%s"). | ' % (old, new, k, title) + (c.get('notes') or '')
            c['id'] = new; c['clip'] = 'CL/%d' % k; c['clip_title'] = title; c['clip_order'] = order; n += 1
            print('  %-42s %s -> %s' % (cam, old, new))
    left = [x for x, c in C.items() if isinstance(c, dict) and str(c.get('id', '')).startswith('B26')]
    assert not left, left
    print(n, 'cameras')
    if '--apply' in sys.argv:
        fd, t = tempfile.mkstemp(dir=os.path.dirname(P))
        with os.fdopen(fd, 'w') as f: f.write(json.dumps(C, indent=1, ensure_ascii=True))
        os.replace(t, P); print('applied')


if __name__ == '__main__':
    main()
