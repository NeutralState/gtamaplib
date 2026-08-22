#!/usr/bin/env python3
"""place_lm_leakmap.py — creer/mettre a jour un landmark depuis la leak map.

[LEAKMAP-ANCHOR-V1] Le pipeline moderne: x,y releves par Alexandre sur la
leak map (tooltip de l'UI = coordonnees monde), z echantillonne dans la
height map (source de verite, 0.18 m median sur les players HUD). Chaque
point devient une ancre ABSOLUE — zero dependance au reseau de cams, zero
circularite. C'est ce qui remplace la triangulation pour tout ce qui est
identifiable sur la carte.

Usage (une ou plusieurs paires nom=x,y):
  python3 tools/place_lm_leakmap.py --set 'Highway Bridge (A)=-3120.5,5480.2' \
      --set 'Route 50 (B)=-2890.0,5122.7' [--z-offset 'Highway Bridge (A)=8'] \
      [--dry-run]

--z-offset: pour un point qui N'EST PAS au sol (tablier de pont, toit):
  z = sol_height_map + offset. Par defaut offset 0 (point au sol).
"""
import argparse
import json
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(THIS)
sys.path.insert(0, THIS)
sys.path.insert(0, REPO)

from horizon_resect import ground  # meme source, meme transform


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', action='append', required=True,
                    metavar='NOM=X,Y', help='landmark et son x,y leak map')
    ap.add_argument('--z-offset', action='append', default=[],
                    metavar='NOM=DZ', help='hauteur au-dessus du sol (tablier, toit)')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    offs = {}
    for s in args.z_offset:
        n, v = s.rsplit('=', 1)
        offs[n] = float(v)

    p = os.path.join(REPO, 'gtamapdata', 'landmarks.json')
    lms = json.load(open(p))
    for s in args.set:
        name, xy = s.rsplit('=', 1)
        x, y = (float(v) for v in xy.split(','))
        g = float(ground(x, y))
        dz = offs.get(name, 0.0)
        z = round(g + dz, 2)
        e = lms.get(name)
        if not isinstance(e, dict):
            e = {}
            lms[name] = e
        old = e.get('xyz')
        e['xyz'] = [round(x, 2), round(y, 2), z]
        e['error_m'] = None
        e['note'] = ('ancre absolue: x,y releves sur la leak map (Alexandre), '
                     f'z = sol height map {g:.1f}'
                     + (f' + {dz:g} m (structure)' if dz else '')
                     + ' [LEAKMAP-ANCHOR-V1]')
        print(f'{name}: ({x:.1f}, {y:.1f}, {z:.1f})  sol={g:.1f}'
              + (f'  offset+{dz:g}' if dz else '')
              + (f'  (remplace {old})' if old else '  (nouveau)'))
    if args.dry_run:
        print('\nDRY-RUN, rien ecrit.')
        return
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(lms, f, indent=1, ensure_ascii=True)
    os.replace(tmp, p)
    print(f'\necrit: {len(args.set)} landmark(s) dans landmarks.json')


if __name__ == '__main__':
    main()
