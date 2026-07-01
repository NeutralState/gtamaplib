#!/usr/bin/env python3
"""
map_validate.py — Map-proof at scale: generate a contact sheet of map crops
(one per landmark, crosshair at current xyz) for rapid visual validation
against the yanis V13 map, and import the verdicts.

Motivation: la "preuve map" (Amphitheater, CC9, Stephen P. Clark...) etait
artisanale — un LM a la fois, verdict nulle part dans les donnees. Cet outil
l'industrialise: valider 50 LM en 20 minutes, verdicts persistes dans
gtamapdata/map_validated.json, et les solvers traitent les LM valides comme
FROZEN (leurs rays deviennent des ancres).

Usage:
  # Generer le contact sheet (defaut: tiers low+medium avec xyz, pas deja juges)
  python3 tools/map_validate.py
  python3 tools/map_validate.py --tier low --zone vice_city
  python3 tools/map_validate.py --lms "Palazzo del Sol,Cruise Terminal D"
  # -> tools/generated/map_validate_sheet.html  (ouvrir dans le navigateur,
  #    cliquer les cartes: gris=?, vert=valide, rouge=rejete; Export -> JSON)

  # Importer les verdicts exportes
  python3 tools/map_validate.py --import /path/to/verdicts.json          # dry-run
  python3 tools/map_validate.py --import /path/to/verdicts.json --apply

Storage: gtamapdata/map_validated.json  {lm_name: {"status": "validated"|"rejected",
"date": "YYYY-MM-DD"}}. Meme pattern qu'excluded_markings.json.

Semantique solveurs (bundle_adjust_weighted --cleanup):
  validated -> FROZEN (xyz constant, rays gardes comme ancres)
  rejected  -> EXCLU du bundle (xyz connu-faux; a retrianguler/investiguer)

Tiles: vendor/gtadb.org/maps/tiles/6/yanis,13/ si present (machine locale),
sinon telechargement gtadb.org avec cache tools/generated/tile_cache/.
Geo: MAP_W=32768, zero=(16384,16384), z=6 -> 0.5 m/px (verbatim rlx map.js).
"""
import argparse
import base64
import io
import json
import os
import sys
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'tools'))

LANDMARKS_JSON = os.path.join(REPO, 'gtamapdata', 'landmarks.json')
TIERS_JSON = os.path.join(REPO, 'tools', 'generated', 'confidence_tiers.json')
VALIDATED_JSON = os.path.join(REPO, 'gtamapdata', 'map_validated.json')
TILES_DIR_LOCAL = os.path.join(REPO, 'vendor', 'gtadb.org', 'maps', 'tiles', '6', 'yanis,13')
TILE_CACHE = os.path.join(REPO, 'tools', 'generated', 'tile_cache')
TILE_URL = 'https://gtadb.org/maps/tiles/6/yanis,13/{z}/{z},{y},{x}.jpg'
OUT_HTML = os.path.join(REPO, 'tools', 'generated', 'map_validate_sheet.html')

Z = 6
MPPX = 32768 / (1024 * 2 ** Z)      # 0.5 m/px
ZX = ZY = 16384
TS = 256
RANGE = [[0, 34], [155, 190]]        # [[x0,y0],[x1,y1]] valid tiles at z=6


def load_validated():
    if os.path.exists(VALIDATED_JSON):
        with open(VALIDATED_JSON) as f:
            d = json.load(f)
        return {k: v for k, v in d.items() if not k.startswith('_')}
    return {}


def save_validated(d):
    out = {'_comment': ('Verdicts de preuve map (yanis V13) par LM. validated = '
                        'xyz confirme sur la map -> FROZEN dans les solveurs. '
                        'rejected = xyz contredit par la map -> exclu du bundle, '
                        'a retrianguler. Genere/importe par tools/map_validate.py.')}
    for k in sorted(d):
        out[k] = d[k]
    with open(VALIDATED_JSON, 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=True)
        f.write('\n')


def get_tile(ty, tx):
    """Return local path to tile jpg, downloading to cache if needed."""
    p = os.path.join(TILES_DIR_LOCAL, str(Z), f'{Z},{ty},{tx}.jpg')
    if os.path.exists(p):
        return p
    os.makedirs(TILE_CACHE, exist_ok=True)
    p = os.path.join(TILE_CACHE, f'{Z}_{ty}_{tx}.jpg')
    if os.path.exists(p):
        return p
    import urllib.request
    try:
        urllib.request.urlretrieve(TILE_URL.format(z=Z, y=ty, x=tx), p)
        return p
    except Exception:
        if os.path.exists(p):
            os.remove(p)
        return None


def crop_at(wx, wy, half_m):
    from PIL import Image, ImageDraw
    cpx, cpy = (wx + ZX) / MPPX, (ZY - wy) / MPPX
    h = half_m / MPPX
    l, t, r, b = cpx - h, cpy - h, cpx + h, cpy + h
    txs = list(range(int(l // TS), int((r - 1) // TS) + 1))
    tys = list(range(int(t // TS), int((b - 1) // TS) + 1))
    ox, oy = txs[0] * TS, tys[0] * TS
    comp = Image.new('RGB', (len(txs) * TS, len(tys) * TS), (10, 10, 12))
    n_ok = 0
    for ty in tys:
        for tx in txs:
            if tx < RANGE[0][0] or tx > RANGE[1][0] or ty < RANGE[0][1] or ty > RANGE[1][1]:
                continue
            p = get_tile(ty, tx)
            if p:
                comp.paste(Image.open(p), (tx * TS - ox, ty * TS - oy))
                n_ok += 1
    if n_ok == 0:
        return None
    c = comp.crop((int(l - ox), int(t - oy), int(r - ox), int(b - oy)))
    d = ImageDraw.Draw(c)
    cx, cy = c.width // 2, c.height // 2
    g, L = 12, 32
    for seg in [((cx - L, cy), (cx - g, cy)), ((cx + g, cy), (cx + L, cy)),
                ((cx, cy - L), (cx, cy - g)), ((cx, cy + g), (cx, cy + L))]:
        d.line(seg, fill=(0, 230, 255), width=2)
    return c


def b64_jpg(img, size=300):
    img = img.resize((size, size))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=78)
    return base64.b64encode(buf.getvalue()).decode('ascii')


HTML_HEAD = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Map validation — yanis V13</title>
<style>
body{background:#111;color:#ddd;font-family:system-ui,sans-serif;margin:16px}
h1{font-size:18px} .hint{color:#888;font-size:13px}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:12px;margin-top:12px}
.card{border:3px solid #444;border-radius:8px;overflow:hidden;cursor:pointer;background:#1a1a1a}
.card img{display:block;width:100%}
.card .lbl{padding:6px 8px;font-size:12.5px;line-height:1.35}
.card .meta{color:#888;font-size:11px}
.card.validated{border-color:#2ecc71} .card.rejected{border-color:#e74c3c}
.card.validated .lbl::before{content:"\\2713 ";color:#2ecc71;font-weight:bold}
.card.rejected .lbl::before{content:"\\2717 ";color:#e74c3c;font-weight:bold}
#bar{position:sticky;top:0;background:#111;padding:8px 0;z-index:5;border-bottom:1px solid #333}
button{background:#2a6;border:0;color:#fff;padding:8px 14px;border-radius:6px;cursor:pointer;font-size:14px}
#counts{margin-left:12px;color:#aaa} textarea{width:100%;height:120px;background:#181818;color:#ccc;border:1px solid #333;margin-top:8px}
</style></head><body>
<h1>Map validation — yanis V13 (crosshair = xyz actuel du LM)</h1>
<div class="hint">Clic sur une carte: gris (?) &rarr; vert (valide: le crosshair est au bon endroit sur la map)
&rarr; rouge (rejete: la map contredit la position) &rarr; gris. Ensuite Export, copier le JSON, puis
<code>python3 tools/map_validate.py --import verdicts.json --apply</code></div>
<div id="bar"><button onclick="doExport()">Export JSON</button><span id="counts"></span>
<textarea id="out" placeholder="JSON des verdicts apparait ici apres Export"></textarea></div>
<div id="grid">
"""

HTML_TAIL = """</div>
<script>
const states = ['unknown','validated','rejected'];
document.querySelectorAll('.card').forEach(c => c.addEventListener('click', () => {
  const i = states.indexOf(c.dataset.state || 'unknown');
  const n = states[(i + 1) % 3];
  c.dataset.state = n;
  c.classList.remove('validated','rejected');
  if (n !== 'unknown') c.classList.add(n);
  updateCounts();
}));
function updateCounts(){
  const cs = [...document.querySelectorAll('.card')];
  const v = cs.filter(c => c.dataset.state === 'validated').length;
  const r = cs.filter(c => c.dataset.state === 'rejected').length;
  document.getElementById('counts').textContent = `${v} valides / ${r} rejetes / ${cs.length - v - r} restants`;
}
function doExport(){
  const res = {validated: [], rejected: []};
  document.querySelectorAll('.card').forEach(c => {
    if (c.dataset.state === 'validated') res.validated.push(c.dataset.name);
    if (c.dataset.state === 'rejected') res.rejected.push(c.dataset.name);
  });
  document.getElementById('out').value = JSON.stringify(res, null, 2);
  document.getElementById('out').select();
  try { document.execCommand('copy'); } catch(e) {}
}
updateCounts();
</script></body></html>
"""


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def cmd_generate(args):
    with open(LANDMARKS_JSON) as f:
        lms = json.load(f)
    lm_meta = {}
    if os.path.exists(TIERS_JSON):
        with open(TIERS_JSON) as f:
            lm_meta = json.load(f)['landmarks']
    already = load_validated()

    if args.lms:
        names = [n.strip() for n in args.lms.split(',') if n.strip()]
        missing = [n for n in names if n not in lms]
        if missing:
            print(f'WARNING: LM introuvables: {missing}')
        names = [n for n in names if n in lms]
    else:
        tiers_wanted = set(args.tier.split(','))
        names = []
        for n, d in lms.items():
            if not d.get('xyz'):
                continue
            if args.zone and d.get('zone') != args.zone:
                continue
            t = (lm_meta.get(n) or {}).get('tier', 'unverified')
            if t not in tiers_wanted:
                continue
            if n in already and not args.redo:
                continue
            names.append(n)

    # Tri spatial grossier: zone, puis bandes de 400m, puis y — les LM voisins
    # se suivent dans la grille (contexte visuel partage).
    def key(n):
        d = lms[n]
        x, y = d['xyz'][0], d['xyz'][1]
        return (d.get('zone') or '', round(x / 400), -y)
    names.sort(key=key)

    if not names:
        print('Aucun LM candidat (deja tous juges? essayer --redo ou --tier).')
        return 0
    print(f'{len(names)} LM a rendre (half={args.half_m}m, z={Z}, {MPPX} m/px)')

    cards = []
    skipped = 0
    for i, n in enumerate(names):
        d = lms[n]
        x, y = d['xyz'][0], d['xyz'][1]
        img = crop_at(x, y, args.half_m)
        if img is None:
            skipped += 1
            continue
        m = lm_meta.get(n, {})
        meta = (f"tier {m.get('tier','?')} &middot; {m.get('n_sources','?')} src &middot; "
                f"median {m.get('median_res','?')}' &middot; xy ({x:.0f}, {y:.0f})")
        cards.append(
            f'<div class="card" data-name="{esc(n)}">'
            f'<img src="data:image/jpeg;base64,{b64_jpg(img)}">'
            f'<div class="lbl">{esc(n)}<div class="meta">{meta}</div></div></div>'
        )
        if (i + 1) % 25 == 0:
            print(f'  {i + 1}/{len(names)}...')

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        f.write(HTML_HEAD)
        f.write('\n'.join(cards))
        f.write(HTML_TAIL)
    print(f'\n{len(cards)} cartes ({skipped} hors map/skip)')
    print(f'-> {args.out}')
    print('Ouvrir dans le navigateur, juger, Export, puis --import verdicts.json --apply')
    return 0


def cmd_import(args):
    with open(args.import_file) as f:
        verdicts = json.load(f)
    v = verdicts.get('validated', [])
    r = verdicts.get('rejected', [])
    with open(LANDMARKS_JSON) as f:
        lms = json.load(f)
    unknown = [n for n in v + r if n not in lms]
    if unknown:
        print(f'WARNING: LM inconnus ignores: {unknown}')
        v = [n for n in v if n in lms]
        r = [n for n in r if n in lms]
    cur = load_validated()
    today = date.today().isoformat()
    changes = []
    for n in v:
        if cur.get(n, {}).get('status') != 'validated':
            changes.append((n, cur.get(n, {}).get('status'), 'validated'))
        cur[n] = {'status': 'validated', 'date': today}
    for n in r:
        if cur.get(n, {}).get('status') != 'rejected':
            changes.append((n, cur.get(n, {}).get('status'), 'rejected'))
        cur[n] = {'status': 'rejected', 'date': today}
    print(f'{len(v)} validated + {len(r)} rejected ({len(changes)} changements):')
    for n, old, new in changes:
        print(f'  {n}: {old or "-"} -> {new}')
    if not args.apply:
        print('\nDRY-RUN: rien ecrit. --apply pour ecrire gtamapdata/map_validated.json')
        return 0
    save_validated(cur)
    total = len(cur)
    print(f'\nECRIT: {VALIDATED_JSON} ({total} verdicts au total)')
    print('Regenerer les tiers puis dry-run du bundle pour voir l effet.')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tier', default='low,medium',
                    help='tiers a inclure, separes par virgule (defaut: low,medium)')
    ap.add_argument('--zone', default=None, help='filtrer par zone (ex: vice_city)')
    ap.add_argument('--lms', default=None, help='liste explicite de LM, separes par virgule')
    ap.add_argument('--half-m', type=float, default=80.0,
                    help='demi-fenetre du crop en metres (defaut 80 -> 160m de large)')
    ap.add_argument('--redo', action='store_true',
                    help='inclure les LM deja juges (pour re-verifier)')
    ap.add_argument('--out', default=OUT_HTML)
    ap.add_argument('--import', dest='import_file', default=None,
                    help='importer un JSON de verdicts exporte par le sheet')
    ap.add_argument('--apply', action='store_true',
                    help='(avec --import) ecrire map_validated.json')
    args = ap.parse_args()
    if args.import_file:
        return cmd_import(args)
    return cmd_generate(args)


if __name__ == '__main__':
    sys.exit(main())
