#!/usr/bin/env python3
"""gen_vc_bridges.py — meshes des ponts de Vice City. [VC-BRIDGES-V1 2026-09-30]

Plan = V16: tronçons de chaussee (gris route) avec de l'eau des DEUX cotes (tests a 14/26/40 m, 4 directions),
composantes connexes >= 600 m2 et >= 45 m de long dans la zone Vice City; axe = polyligne (moyenne transverse par
pas de 10 m le long de l'axe principal), largeur = bande V16 (5e-95e centile).
Hauteur: sommet du tablier ESTIME par classe de longueur (IRL: ponts hauts des causeways ~20 m, moyens ~10 m,
petits ~5 m) sauf CREST (mesures / landmarks); profil parabolique vers les culees (+1.5 m).
Usage: PYTHONPATH=. python3 tools/gen_vc_bridges.py [--list] [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from gen_keys_bridges import Bridge
D = lambda f: os.path.join(ROOT, 'gtamapdata', f)
X0, X1, Y0, Y1 = -1700, 2000, 3300, -2300        # zone Vice City (monde)
# noms par centre approximatif (x, y) -> nom; le plus proche a < 120 m
NAMES = [((-98, 1080), 'Rialto Causeway Bridge (W)'), ((1250, 1460), 'Rialto Causeway Bridge (E)'),
         ((-32, 540), 'I-404 Causeway Bridge (Downtown)'), ((610, 97), 'I-404 Causeway Bridge (Watson)'),
         ((684, 194), 'Starfish Island Bridge'), ((993, 39), 'I-404 Causeway Bridge (Fisher W)'),
         ((1196, 96), 'I-404 Causeway Bridge (Fisher E)'), ((1351, 150), 'I-404 Causeway Bridge (Vice Beach)'),
         ((-74, -473), 'I-397 Port Bridge'), ((833, -952), 'I-397 Catalan Bay Bridge'), ((-459, -1080), 'Tequesta Retreat Bridge'),
         ((-679, -1692), 'Catalan Causeway Bridge (N)'), ((-672, -1666), 'Catalan Causeway Bridge (S)'),
         ((187, -2032), 'Gloriana Key Bridge'), ((262, -1511), 'Gloriana Key Bridge (N)'),
         ((473, 1976), 'Nautilus Causeway Bridge (W)'), ((1379, 1798), 'Nautilus Causeway Bridge (E)'),
         ((1142, 2677), 'Leaf Links Bridge (E)'), ((1068, 2450), 'Leaf Links Bridge (SE)'), ((1226, 2837), 'Leaf Links Bridge (NE)'),
         ((401, 3007), 'Leaf Links Bridge (W)'), ((-1191, 1604), 'Vice River Bridge (N)'), ((-1234, -281), 'Little Cuba Bridge'),
         ((-494, -671), 'Vice River Bridge (Mouth)'), ((-1070, -604), 'Vice River Bridge (Salton)')]
CREST = {'I-404 Causeway Bridge (Downtown)': 20.6}   # nom -> haut du tablier MESURE (m): dessous 17-19 m sur 3 piles dans Shoreline [Gameinformer]
FLAT = ('I-404 Causeway Bridge (Downtown)', 'I-404 Causeway Bridge (Watson)', 'I-397')
# [VC-BRIDGES-V2 2026-09-30] hauteurs ESTIMEES d'apres le pont IRL correspondant (aucune cam ne voit ces ponts de pres:
# verifie dans 12 cams candidates, tous occultes ou trop loin): haut du tablier au milieu (m)
IRL = {'Rialto Causeway Bridge': 6.0,          # Venetian Causeway: ponts bas + basculants
       'I-404 Causeway Bridge (Fisher': 10.0,   # MacArthur Causeway, troncons est (bas)
       'I-404 Causeway Bridge (Vice Beach)': 10.0,
       'Nautilus Causeway Bridge (W)': 18.0,    # Julia Tuttle Causeway: pont haut cote ouest
       'Nautilus Causeway Bridge (E)': 8.0,
       'Catalan Causeway Bridge': 24.0,         # Rickenbacker: William Powell Bridge
       'Gloriana Key Bridge': 8.0,              # Bear Cut
       'Tequesta Retreat Bridge': 5.0,          # Brickell Key bridge
       'Starfish Island Bridge': 4.0,           # Star Island
       'Leaf Links Bridge': 5.0,                # Indian Creek
       'Vice River Bridge': 6.0, 'Little Cuba Bridge': 6.0}   # Miami River: basculants bas
PIERS_XY = {'I-404 Causeway Bridge (Downtown)': [(-42.9, 551.3), (-94.2, 558.5), (-158.1, 562.3)]}   # piles mesurees (Shoreline, rayon x z=0)   # autoroutes: viaducs en hauteur sur toute la traversee (vu dans Shoreline), pas de rampe dans le troncon V16
EST = [(250, 20.0), (120, 10.0), (0, 5.0)]      # longueur min -> haut du tablier ESTIME


def extract():
    Image.MAX_IMAGE_PIXELS = None
    V = np.asarray(Image.open(os.path.join(ROOT, 'maps', 'yanis,16svg.png')).crop((X0 + 16991, 11008 - Y0, X1 + 16991, 11008 - Y1)).convert('RGB')).astype(np.int16)
    R, G, B = V[..., 0], V[..., 1], V[..., 2]
    water = ndimage.binary_opening((B > R + 40) & (B > 120), iterations=1)
    road = (np.abs(R - G) < 14) & (np.abs(G - B) < 14) & (R < 175) & (R > 45)
    wd = ndimage.binary_dilation(water, iterations=2)
    sh = lambda m, dy, dx: np.roll(np.roll(m, dy, 0), dx, 1)
    over = np.zeros_like(road)
    for k in (14, 26, 40):
        j = int(k * 0.707)
        for a, b in (((k, 0), (-k, 0)), ((0, k), (0, -k)), ((j, j), (-j, -j)), ((j, -j), (-j, j))): over |= sh(wd, *a) & sh(wd, *b)
    br = ndimage.binary_closing(road & over, iterations=4) & ndimage.binary_dilation(road, iterations=3)
    br = ndimage.binary_opening(br, iterations=1)
    lab, n = ndimage.label(br); sizes = ndimage.sum(br, lab, range(1, n + 1)); out = []
    for i in range(1, n + 1):
        if sizes[i - 1] < 600: continue
        ys, xs = np.nonzero(lab == i); P = np.c_[xs + X0, Y0 - ys].astype(float)
        c = P.mean(0); u = np.linalg.svd(P - c, full_matrices=False)[2][0]; nn = np.array([-u[1], u[0]])
        s = (P - c) @ u; w = (P - c) @ nn
        if s.max() - s.min() < 45: continue
        # axe = courbe lisse w(s) (polynome deg 1-3 selon la longueur, ajuste en robuste sur les medianes par pas de 10 m):
        # la mediane brute serpentait (bretelles, 2 chaussees) -> tablier "explose" (Alexandre 2026-09-30)
        bs, bw = [], []
        for s0 in np.arange(s.min(), s.max() + 0.1, 10.0):
            m = np.abs(s - s0) < 6
            if m.sum() > 5: bs.append(s0); bw.append(float(np.median(w[m])))
        bs, bw = np.array(bs), np.array(bw); Lg = s.max() - s.min()
        deg = 1 if Lg < 150 else (2 if Lg < 350 else 3)
        keep = np.ones(len(bs), bool)
        for _ in range(3):                                    # rejet des bins aberrants (> 2.5 m du fit)
            co = np.polyfit(bs[keep], bw[keep], min(deg, max(0, keep.sum() - 1)))
            r = np.abs(np.polyval(co, bs) - bw); keep = r < max(2.5, np.percentile(r, 60))
        axis = [c + u * s0 + nn * float(np.polyval(co, s0)) for s0 in np.arange(s.min(), s.max() + 0.1, 10.0)]
        axis = [axis[0] - (axis[1] - axis[0]) / np.linalg.norm(axis[1] - axis[0]) * 3] + axis + \
               [axis[-1] + (axis[-1] - axis[-2]) / np.linalg.norm(axis[-1] - axis[-2]) * 3]
        wres = w - np.polyval(co, s); width = float(np.percentile(wres, 93) - np.percentile(wres, 7))
        out.append({'c': c.tolist(), 'axis': [a.tolist() for a in axis], 'width': width, 'length': float(s.max() - s.min() + 6), 'area': int(sizes[i - 1])})
    return out


def name_of(c, used):
    best = min(NAMES, key=lambda nm: np.hypot(c[0] - nm[0][0], c[1] - nm[0][1]))
    if np.hypot(c[0] - best[0][0], c[1] - best[0][1]) < 120 and best[1] not in used: return best[1]
    return 'Vice City Bridge (%d, %d)' % (round(c[0], -1), round(c[1], -1))


def build():
    out, used = {}, set()
    for b in sorted(extract(), key=lambda b: -b['area']):
        nm = name_of(b['c'], used); used.add(nm)
        Lg = b['length']; hw = min(b['width'], 40) / 2
        irl = next((h for key, h in IRL.items() if nm.startswith(key)), None)
        crest = CREST.get(nm) or (CREST['I-404 Causeway Bridge (Downtown)'] if nm.startswith(FLAT) else (irl or next(h for lmin, h in EST if Lg >= lmin)))
        br = Bridge(poly=b['axis']); S = br.S[-1]
        if nm.startswith(FLAT): zb = lambda s, crest=crest: crest - 1.8
        else: zb = lambda s, crest=crest, S=S: 1.5 + (crest - 1.5) * (1 - (2 * s / S - 1) ** 2) - 1.8   # dessous du tablier
        br.deck(0.0, S, zb, -hw, hw, depth=1.8, parapet=1.0)
        span = 55.0 if nm.startswith(FLAT) else (30.0 if crest >= 15 else 20.0)
        s0 = span / 2
        if nm in PIERS_XY:     # phase des piles calee sur les piles mesurees
            A_ = np.array(b['axis']); SS = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(A_, axis=0), axis=1))])
            sp = [SS[int(np.argmin(np.linalg.norm(A_ - np.array(q), axis=1)))] for q in PIERS_XY[nm]]
            span = float(np.median(np.diff(sorted(sp)))) if len(sp) > 1 else span; s0 = min(sp) % span
        for s in np.arange(s0, S - 3, span):
            if zb(s) > 2.0: br.bent(s, zb, -hw + 0.5, hw - 0.5, ncol=max(2, int(hw * 2 // 9)), col=1.4)
        out[nm] = {'color': '#cbd5e1', 'world_edges': br.E, '_credit': 'Alexandre Leblanc (V16) + Claude Opus 5.5',
                   'note': 'VC-BRIDGES-V1 2026-09-30: plan V16 (troncon de chaussee au-dessus de l eau, axe polyligne, largeur %.0f m, '
                           'longueur %.0f m); haut du tablier %s %.0f m %s.'
                           % (2 * hw, Lg, 'MESURE' if nm in CREST else ('repris du pont I-404 mesure' if nm.startswith(FLAT) else ('ESTIME d apres le pont IRL' if irl else 'ESTIME (classe de longueur)')), crest,
                              'constant (viaduc autoroutier)' if nm.startswith(FLAT) else 'au milieu, 1.5 m aux culees (profil parabolique)')}
    return out


if __name__ == '__main__':
    out = build()
    for k, v in out.items(): print('%-42s %5d aretes  %s' % (k, len(v['world_edges']), v['note'][60:140]))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = D('building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_vcbridges_0930')
        M = json.load(open(mp)); M.update(out)
        json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique', len(out))
