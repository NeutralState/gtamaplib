#!/usr/bin/env python3
"""building_dossier.py — le dossier complet d'un building. [DOSSIER-V1, READ-ONLY]

La question d'Alexandre (07-19): 'voir toutes les meilleures poses pour un
building, noter ce qu'il manque du mesh et trouver des solutions'. Un seul
rapport qui repond aux trois:

  1. LE JURY: toutes les cams qui voient le building, classees par qualite
     de temoin — nettete MESUREE du crop (variance du laplacien), taille
     apparente, distance, secteur d'azimut, classe (leak A = verite HUD),
     residu actuel sur les coins marques. Crops avec wireframe si mesh.
  2. L'INVENTAIRE: chaque coin — xyz ou pas, combien de temoins valides
     (exclusions comptees a part), residu; les coins morts (0-1 temoin).
  3. LES TROUS: secteurs d'azimut jamais couverts (facades aveugles),
     couverture toit/sol.
  4. LES SOLUTIONS: pour chaque coin faible, les frames candidates du jury
     qui le voient avec le PIXEL PREDIT (projection du xyz ou du mesh) —
     l'equivalent auto des notes 'VC Postcard ~(1767,875)' du journal.

Usage:
  PYTHONPATH=. python3 tools/audit/building_dossier.py "C. Clyde Atkins U.S Courthouse"
  PYTHONPATH=. python3 tools/audit/building_dossier.py "Vizcayne North Condominium"
  -> texte + tools/generated/dossier/<building>/dossier.html
"""
import argparse
import json
import math
import os
import statistics
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(THIS))
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, REPO)

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
import common

MIN_APPARENT_PX = 40
SECTORS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']


def sector(az):
    return SECTORS[int(((az + 22.5) % 360) // 45)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('building')
    ap.add_argument('--top', type=int, default=14, help='taille du jury affiche')
    args = ap.parse_args()
    B = args.building

    lms = json.load(open(os.path.join(REPO, 'gtamapdata', 'landmarks.json')))
    px = json.load(open(os.path.join(REPO, 'gtamapdata', 'pixels.json')))
    cams_json = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json')))
    try:
        mesh = json.load(open(os.path.join(REPO, 'gtamapdata', 'building_meshes_procedural.json'))).get(B)
    except Exception:
        mesh = None

    corners = {n: e for n, e in lms.items()
               if n.startswith(B + ' (') and isinstance(e, dict)}
    if not corners and not mesh:
        sys.exit(f'aucun LM "{B} (…)" et aucun mesh')
    pts_known = {n: np.array(e['xyz'], float) for n, e in corners.items() if e.get('xyz')}
    if mesh:
        allv = np.array([p for ab in mesh['world_edges'] for p in ab])
    elif pts_known:
        allv = np.array(list(pts_known.values()))
    else:
        sys.exit('aucun xyz pour situer le building')
    centroid = allv.mean(axis=0)
    if len(allv) < 4:
        # building maigre (1-3 xyz): emprise virtuelle ±30m / ±25m z pour
        # estimer visibilite et taille apparente dans chaque cam
        cx, cy, cz = centroid
        allv = np.array([[cx + sx * 30, cy + sy * 30, cz + sz * 25]
                         for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])

    # ── inventaire des coins
    obs_by_lm, excl_by_lm = {}, {}
    for c, marks in px.items():
        for lm, p in marks.items():
            if lm in corners and p is not None:
                (excl_by_lm if common.is_excluded_marking(c, lm) else obs_by_lm) \
                    .setdefault(lm, []).append(c)

    # ── le jury: toutes les cams calibrees a frame qui voient le building
    jury = []
    for C, e in cams_json.items():
        fp = os.path.join(REPO, 'frames', f'{C}.png')
        if not os.path.exists(fp):
            continue
        try:
            cam = common.get_cam(C)
            assert cam is not None
        except Exception:
            continue
        proj = [cam.get_pixel(v.tolist()) for v in allv[::max(1, len(allv) // 60)]]
        proj = [p for p in proj if p is not None]
        if len(proj) < 3:
            continue
        P = np.array(proj)
        w = float(P[:, 0].max() - P[:, 0].min()); h = float(P[:, 1].max() - P[:, 1].min())
        apparent = max(w, h)
        if apparent < MIN_APPARENT_PX:
            continue
        img = Image.open(fp).convert('L')
        cx = (P[:, 0].min() + P[:, 0].max()) / 2; cy = (P[:, 1].min() + P[:, 1].max()) / 2
        if not (0 <= cx < img.width and 0 <= cy < img.height):
            continue
        m = 60
        box = (int(max(0, P[:, 0].min() - m)), int(max(0, P[:, 1].min() - m)),
               int(min(img.width, P[:, 0].max() + m)), int(min(img.height, P[:, 1].max() + m)))
        if box[2] - box[0] < 20 or box[3] - box[1] < 20:
            continue
        crop = np.asarray(img.crop(box), float)
        sharp = float(ndimage.laplace(ndimage.gaussian_filter(crop, 1.0)).var())
        d = centroid - np.asarray(cam.xyz)
        dist = float(np.linalg.norm(d))
        az = math.degrees(math.atan2(-d[0], d[1])) % 360
        mine = [lm for lm in obs_by_lm if C in obs_by_lm[lm]]
        res = []
        for lm in mine:
            if not lms[lm].get('xyz'):
                continue
            a, g, _ = common.residual_dual(cam, list(px[C][lm]), lms[lm]['xyz'])
            if a is not None:
                res.append(g)
        cid = str(e.get('id', ''))
        is_leak = cid.startswith('L')
        score = math.log1p(apparent) * math.sqrt(max(sharp, 1.0))
        jury.append(dict(cam=C, dist=dist, az=az, sect=sector(az), apparent=apparent,
                         sharp=sharp, n_marks=len(mine), res=statistics.median(res) if res else None,
                         leak=is_leak, score=score, box=box, fp=fp))
    jury.sort(key=lambda j: -j['score'])

    # ── texte
    print(f'DOSSIER: {B}')
    print(f'  mesh: {"oui (" + str(len(mesh["world_edges"])) + " aretes)" if mesh else "NON"}   '
          f'coins: {len(corners)} declares, {len(pts_known)} avec xyz   jury: {len(jury)} cams')

    print(f'\n── JURY (top {args.top} par nettete x taille):')
    for j in jury[:args.top]:
        tag = 'LEAK' if j['leak'] else '    '
        r = f'res {j["res"]:.1f}m' if j['res'] is not None else 'aucun marking'
        print(f'   {j["cam"][:30]:30} {tag} {j["sect"]:>2} {j["dist"]:6.0f}m  {j["apparent"]:5.0f}px  '
              f'nett {j["sharp"]:6.0f}  {j["n_marks"]} marks ({r})')

    print('\n── INVENTAIRE DES COINS:')
    weak = []
    for n in sorted(corners):
        short = n.replace(B, '..')
        has = corners[n].get('xyz') is not None
        no = len(obs_by_lm.get(n, [])); ne = len(excl_by_lm.get(n, []))
        state = 'OK' if (has and no >= 2) else ('FAIBLE' if has else 'SANS XYZ')
        if state != 'OK':
            weak.append(n)
        ex = f' (+{ne} exclus)' if ne else ''
        print(f'   {short:28} {"xyz" if has else "---":3} {no} temoins{ex}  {state}')

    print('\n── COUVERTURE AZIMUT (jury par secteur):')
    by_sect = {s: [j for j in jury if j['sect'] == s] for s in SECTORS}
    holes = [s for s in SECTORS if not by_sect[s]]
    print('   ' + '  '.join(f'{s}:{len(by_sect[s])}' for s in SECTORS))
    if holes:
        print(f'   facades aveugles (aucune cam): {", ".join(holes)} — il faudra un leak futur de ce cote')

    print('\n── SOLUTIONS:')
    for n in weak:
        short = n.replace(B, '..')
        xyz = corners[n].get('xyz')
        if xyz is not None:
            cands = []
            for j in jury:
                if j['cam'] in obs_by_lm.get(n, []) or j['cam'] in excl_by_lm.get(n, []):
                    continue
                p = common.get_cam(j['cam']).get_pixel(xyz)
                if p is None:
                    continue
                cands.append((j, p))
            need = max(0, 2 - len(obs_by_lm.get(n, [])))
            if cands:
                lst = ', '.join(f'{j["cam"]} ~({p[0]:.0f},{p[1]:.0f})' for j, p in cands[:4])
                print(f'   {short:28} +{need} temoin(s): cliquer dans {lst}')
            else:
                print(f'   {short:28} +{need} temoin(s): AUCUNE frame candidate au jury — attendre un leak')
        else:
            near = ', '.join(j['cam'] for j in jury[:3])
            hint = ' (mesh present: coin derivable par symetrie/structure?)' if mesh else ''
            print(f'   {short:28} sans xyz: 1er temoin a poser (meilleures frames: {near}){hint}')
    if not weak:
        print('   rien a signaler — tous les coins ont >=2 temoins')

    # ── HTML avec crops du jury (wireframe si mesh)
    outdir = os.path.join(REPO, 'tools', 'generated', 'dossier',
                          B.replace(' ', '_').replace('/', '_'))
    os.makedirs(outdir, exist_ok=True)
    cards = []
    for i, j in enumerate(jury[:args.top]):
        img = Image.open(j['fp']).convert('RGB')
        dr = ImageDraw.Draw(img)
        cam = common.get_cam(j['cam'])
        if mesh:
            col = mesh.get('color', '#4ade80')
            for a, bpt in mesh['world_edges']:
                pa, pb = cam.get_pixel(a), cam.get_pixel(bpt)
                if pa is not None and pb is not None:
                    dr.line([tuple(pa), tuple(pb)], fill=col, width=2)
        for n, v in pts_known.items():
            p = cam.get_pixel(v.tolist())
            if p is not None:
                dr.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], outline='#facc15', width=3)
        crop = img.crop(j['box'])
        if crop.width > 900:
            crop = crop.resize((900, int(crop.height * 900 / crop.width)))
        fn = f'{i:02d}_{j["cam"].replace(" ", "_").replace("/", "_")}.png'
        crop.save(os.path.join(outdir, fn))
        r = f'{j["res"]:.1f}m' if j['res'] is not None else '—'
        cards.append(f'<div class=c><img src="{fn}"><p><b>#{i} {j["cam"]}</b>'
                     f'{" · LEAK" if j["leak"] else ""} · {j["sect"]} · {j["dist"]:.0f}m · '
                     f'{j["apparent"]:.0f}px · nettete {j["sharp"]:.0f} · {j["n_marks"]} marks · res {r}</p></div>')
    html = ('<html><head><meta charset="utf-8"><style>body{background:#111;color:#ddd;'
            'font-family:system-ui}div.c{display:inline-block;margin:8px;max-width:920px}'
            'img{max-width:900px;display:block}p{margin:4px 0}</style></head><body>'
            f'<h2>{B} — jury des poses</h2>' + '\n'.join(cards) + '</body></html>')
    open(os.path.join(outdir, 'dossier.html'), 'w').write(html)
    print(f'\n-> {os.path.join(outdir, "dossier.html")}')


if __name__ == '__main__':
    main()
