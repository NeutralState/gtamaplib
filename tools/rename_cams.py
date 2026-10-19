#!/usr/bin/env python3
"""rename_cams.py — rename cameras everywhere they are referenced. [RENAME-CAMS-V1 2026-10-18]

Alexandre: the category (Extended Look, T4, T2...) is already given by the camera ID / source, it does not belong in the
camera name. This tool drops a trailing category tag from the names (or applies an explicit old->new map) and rewrites
every exact "name" string in the data files (dict keys and values: cameras, pixels, landmark source lists, exclusions,
mesh notes, 3D-view metadata), then renames the frames and thumbnails (variants such as "[editee]" / "[z14.5]" follow).
Refuses to run if a new name already exists.
Usage: python3 tools/rename_cams.py [--apply]
"""
import json, os, re, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAGS = (' (Extended Look)', ' (T4)', ' (T2)')
FILES = ['gtamapdata/cameras.json', 'gtamapdata/pixels.json', 'gtamapdata/landmarks.json', 'gtamapdata/excluded_markings.json',
         'gtamapdata/building_meshes_procedural.json', 'tools/data/yanis_frames_match.json', 'tools/threejs/_fp_meta.json',
         'tools/threejs/_facade_tex.json']
DIRS = ['frames', 'docs/thumbs']


def plan():
    C = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    m = {}
    for n in C:
        for t in TAGS:
            if n.endswith(t): m[n] = n[:-len(t)]
    clash = [(a, b) for a, b in m.items() if b in C or list(m.values()).count(b) > 1]
    if clash: raise SystemExit('name clash: %s' % clash)
    return m


def main():
    m = plan(); apply = '--apply' in sys.argv
    for a, b in m.items(): print('  %s  ->  %s' % (a, b))
    for f in FILES:
        p = os.path.join(REPO, f)
        if not os.path.exists(p): continue
        s = open(p, encoding='utf-8').read(); n0 = 0
        for a, b in m.items():
            q = json.dumps(a, ensure_ascii=True)[1:-1]
            for form in (a, q) if q != a else (a,):
                k = s.count('"%s"' % form); n0 += k
                s = s.replace('"%s"' % form, '"%s"' % (json.dumps(b, ensure_ascii=True)[1:-1] if form == q else b))
        print('%-45s %d refs' % (f, n0))
        if apply and n0:
            fd, t = tempfile.mkstemp(dir=os.path.dirname(p))
            with os.fdopen(fd, 'w', encoding='utf-8') as fh: fh.write(s)
            os.replace(t, p)
    for d in DIRS:
        dp = os.path.join(REPO, d)
        if not os.path.isdir(dp): continue
        for fn in sorted(os.listdir(dp)):
            stem, ext = os.path.splitext(fn)
            for a, b in m.items():
                if stem == a or stem.startswith(a + ' ['):
                    new = b + stem[len(a):] + ext
                    print('  %s/%s -> %s' % (d, fn, new))
                    if apply: os.replace(os.path.join(dp, fn), os.path.join(dp, new))
    print('applied' if apply else 'dry run')


if __name__ == '__main__':
    main()
