#!/usr/bin/env python3
"""yanis_ids.py — follow Yanis's frame numbering everywhere + add the 16 frames that had no camera. [YANIS-IDS-V1 2026-10-18]

Source of truth: the "Frames reference" panel drawn on the Yanis V17 map (260 thumbnails with ID + grid cell), matched to our
frames by SIFT + RANSAC (tools/data/yanis_frames_match.json). Rules:
  1. a camera whose frame matches a Yanis thumbnail takes his ID; its siblings (same old ID = same shot) follow;
  2. Build 2026 / cyberleak cameras leave the S3 series (Yanis S3 = pre-order + magazine screenshots) for B26/<same number>;
  3. any other camera whose ID is used by Yanis for a different frame gets a free number above his maximum in that series;
  4. IDs are written unpadded (T4/7, not T4/07), as everywhere else in cameras.json.
New cameras (frame in frames/, no camera yet): PROVISIONAL pose read on Yanis's marker (dot = position, V = heading + FOV),
z = game heightmap + 1.7 m; to be marked and solved.
Usage: python3 tools/yanis_ids.py [--apply]
"""
import json, os, re, sys, tempfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMS = os.path.join(REPO, 'gtamapdata', 'cameras.json'); MATCH = os.path.join(REPO, 'tools', 'data', 'yanis_frames_match.json')
TAG = 'YANIS-IDS-V1 2026-10-18'


def norm(i):
    a, b = i.split('/'); m = re.match(r'0*(\d+)(.*)', b); return '%s/%s%s' % (a, int(m.group(1)), m.group(2))


def main():
    C = json.load(open(CAMS)); M = json.load(open(MATCH))
    yids = {norm(y) for y in M['yanis_ids']}
    match = {n: norm(y) for n, y in M['matched'].items()}
    groups = {}
    for n, c in C.items():
        if isinstance(c, dict) and c.get('id'): groups.setdefault(c['id'], []).append(n)
    new = {}
    for n, y in match.items():
        for s in groups.get(C[n]['id'], []):
            if s not in match: new[s] = y
    new.update(match)
    for n, c in C.items():                                   # rule 2
        if isinstance(c, dict) and c.get('id', '').startswith('S3/') and str(c.get('source', '')).startswith('Build 2026'): new[n] = 'B26/' + c['id'].split('/')[1]
    used = set(new.values()) | {norm(c['id']) for n, c in C.items() if isinstance(c, dict) and c.get('id') and n not in new}
    for n, i in M.get('reassign', {}).items(): new[n] = i     # rule 3 (decided by hand after visual checks)
    changes = []
    for n, c in C.items():
        if not isinstance(c, dict) or not c.get('id'): continue
        old = c['id']; nid = new.get(n, norm(old))
        if nid != old:
            changes.append((n, old, nid)); c['id'] = nid
            c['notes'] = ('%s: id %s -> %s (Yanis V17 frame numbering). | ' % (TAG, old, nid)) + (c.get('notes') or '')
    # collisions left?
    seen = {}
    for n, c in C.items():
        if isinstance(c, dict) and c.get('id'): seen.setdefault(c['id'], []).append(n)
    for n, e in M['new'].items():
        assert n not in C, n
        C[n] = e
    print('%d id changes, %d new cameras' % (len(changes), len(M['new'])))
    for n, a, b in sorted(changes, key=lambda t: t[2]): print('  %-48s %s -> %s' % (n[:48], a, b))
    for n in M['new']: print('  NEW %-44s %s' % (n[:44], M['new'][n]['id']))
    if '--apply' in sys.argv:
        fd, t = tempfile.mkstemp(dir=os.path.dirname(CAMS))
        with os.fdopen(fd, 'w') as f: f.write(json.dumps(C, indent=1, ensure_ascii=True))
        os.replace(t, CAMS); print('applied')


if __name__ == '__main__':
    main()
