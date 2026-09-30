#!/usr/bin/env python3
"""gen_keys_bridges.py — meshes des ponts des Keys. [KEYS-BRIDGES-V1 2026-09-30]

Plan = V16 (axe et largeur des chaussees lus dans la V16 raster, calque de la leak map);
piles = landmarks (xB) quand ils existent (positions le long de l'axe), sinon pas regulier;
hauteur du tablier = profil MESURE (voir chaque pont). Aretes en paires [[x,y,z],[x,y,z]].

Lake Surprise Viaduct: profil du dessous du tablier lu dans Thunderstorm [Gameinformer]
(pose resolue sur les pieds de 14 piles 2B..16B, rms 1.2 px, + cheminees Turkey Point + mat
Key Lento): 7.7 m a 2B (sud) -> 24 m sur la travee de navigation 15B-16B (44 m) -> ~9.5 m au
nord (s 400); piles doubles (une par chaussee), 2 colonnes chacune, chevetre, entretoise a
mi-hauteur si > 12 m, semelle a l'eau.

Usage: PYTHONPATH=. python3 tools/gen_keys_bridges.py [--out brouillon.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda f: os.path.join(ROOT, 'gtamapdata', f)
CREDIT = 'Alexandre Leblanc (V16 + landmarks) + Claude Opus 5.5'


class Bridge:
    """axe = droite (c, u) ou polyligne V16 (poly, s mesure depuis le 1er sommet); w > 0 a gauche du sens de s."""
    def __init__(self, c=None, u=None, poly=None):
        if poly is None:
            u = np.asarray(u, float) / np.linalg.norm(u); poly = [np.asarray(c, float) - u * 5000, np.asarray(c, float) + u * 5000]
            self.s0 = 5000.0
        else: self.s0 = 0.0
        self.A = np.asarray(poly, float); self.S = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(self.A, axis=0), axis=1))])
        self.E = []

    def frame(self, s):
        s = s + self.s0; i = int(np.clip(np.searchsorted(self.S, s), 1, len(self.S) - 1))
        a, b = self.A[i - 1], self.A[i]; u = (b - a) / np.linalg.norm(b - a)
        # normale lissee aux sommets (moyenne des segments voisins) pour eviter les cassures
        if 1 < i < len(self.S) - 1 and s - self.S[i - 1] < 8:
            u0 = (a - self.A[i - 2]) / np.linalg.norm(a - self.A[i - 2]); u = (u + u0) / np.linalg.norm(u + u0)
        return a + (b - a) * (s - self.S[i - 1]) / (self.S[i] - self.S[i - 1]), u, np.array([-u[1], u[0]])

    def P(self, s, w, z):
        p, u, n = self.frame(s); q = p + n * w
        return [round(float(q[0]), 2), round(float(q[1]), 2), round(float(z), 2)]

    def L(self, a, b): self.E.append([a, b])

    def deck(self, s0, s1, zb, w0, w1, depth=1.8, parapet=1.0, step=10.0, frame=20.0):
        """tablier (caisson) de s0 a s1 entre w0 et w1; zb(s) = dessous du tablier."""
        ss = list(np.arange(s0, s1, step)) + [s1]
        for a, b in zip(ss[:-1], ss[1:]):
            za, zb_ = zb(a), zb(b)
            for w in (w0, w1):
                self.L(self.P(a, w, za), self.P(b, w, zb_))                          # dessous
                self.L(self.P(a, w, za + depth), self.P(b, w, zb_ + depth))          # dessus
                self.L(self.P(a, w, za + depth + parapet), self.P(b, w, zb_ + depth + parapet))  # garde-corps
        for s in list(np.arange(s0, s1, frame)) + [s1]:
            z = zb(s); a, b, c, d = self.P(s, w0, z), self.P(s, w1, z), self.P(s, w1, z + depth), self.P(s, w0, z + depth)
            self.L(a, b); self.L(b, c); self.L(c, d); self.L(d, a)
            for w in (w0, w1): self.L(self.P(s, w, z + depth), self.P(s, w, z + depth + parapet))

    def bent(self, s, zb, w0, w1, ncol=2, col=1.2, zw=0.0, cap=1.4, tie=12.0, footing=1.5):
        """pile: ncol colonnes carrees sous une chaussee [w0,w1], chevetre, entretoise, semelle."""
        z = zb(s); ztop = z - 0.0; zcap = ztop - cap
        m = 0.18 * (w1 - w0); ws = np.linspace(w0 + m, w1 - m, ncol); h = col / 2
        for w in ws:
            cs = [(s - h, w - h), (s + h, w - h), (s + h, w + h), (s - h, w + h)]
            for (a, b) in cs: self.L(self.P(a, b, zw + footing), self.P(a, b, zcap))
            for zz in (zw + footing, zcap):
                for i in range(4): self.L(self.P(*cs[i], zz), self.P(*cs[(i + 1) % 4], zz))
        # chevetre
        for zz in (zcap, ztop):
            for dd in (-0.9, 0.9): self.L(self.P(s + dd, w0 + 0.3, zz), self.P(s + dd, w1 - 0.3, zz))
        for w in (w0 + 0.3, w1 - 0.3):
            for dd in (-0.9, 0.9): self.L(self.P(s + dd, w, zcap), self.P(s + dd, w, ztop))
        # entretoise a mi-hauteur
        if zcap - zw > tie:
            zt = zw + footing + 0.55 * (zcap - zw - footing)
            for zz in (zt - 0.5, zt + 0.5): self.L(self.P(s, ws[0], zz), self.P(s, ws[-1], zz))
        # semelle a l'eau
        f0, f1 = w0 + m - 1.8, w1 - m + 1.8
        for zz in (zw - 0.5, zw + footing):
            cs = [(s - 2.2, f0), (s + 2.2, f0), (s + 2.2, f1), (s - 2.2, f1)]
            for i in range(4): self.L(self.P(*cs[i], zz), self.P(*cs[(i + 1) % 4], zz))

    def abutment(self, s, zb, w0, w1, back):
        z = zb(s) + 1.8
        for w in (w0, w1): self.L(self.P(s, w, 0), self.P(s, w, z))
        self.L(self.P(s, w0, 0), self.P(s, w1, 0)); self.L(self.P(s, w0, z), self.P(s, w1, z))
        for w in (w0, w1): self.L(self.P(s, w, z), self.P(s + back, w, max(z - 4, 1)))


def lake_surprise(L):
    ids = (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20)
    Pp = np.array([L['Lake Surprise Viaduct (%dB)' % i]['xyz'][:2] for i in ids])
    c = Pp.mean(0); u = np.linalg.svd(Pp - c)[2][0]; u = u if u[1] > 0 else -u
    br = Bridge(c, u); s_lm = dict(zip(ids, (Pp - c) @ (u / np.linalg.norm(u))))
    # profil mesure (s, dessous du tablier) — Thunderstorm [Gameinformer]
    prof = np.array([(-250, 5.5), (-211, 7.7), (-187, 8.7), (-160, 10.2), (-133, 11.8), (-84, 15.3), (-57, 16.3),
                     (-33.5, 17.5), (18.3, 20.6), (42.3, 21.1), (68.9, 22.3), (93.1, 23.6), (122.6, 24.1), (166.8, 24.0),
                     (195.4, 22.2), (240, 20.7), (280, 18.5), (320, 14.5), (360, 11.5), (400, 9.5), (430, 7.0)])
    co = np.polyfit(prof[:, 0], prof[:, 1], 4)
    zb = lambda s: float(np.polyval(co, s))
    S0, S1 = -252.0, 432.0
    # chaussees V16 (w relatif a l'axe des piles): ouest -14.5..-2.2, est -0.8..12.5
    decks = [(-14.5, -2.2), (-0.8, 12.5)]
    for w0, w1 in decks: br.deck(S0, S1, zb, w0, w1)
    piles = sorted(list(s_lm.values()) + [s_lm[2] - 26.3] + [s_lm[17] + 25.6 * k for k in (1, 2)] +
                   [s_lm[20] + 25.6 * k for k in range(1, 7)])
    for s in piles:
        if S0 + 5 < s < S1 - 5:
            for w0, w1 in decks: br.bent(s, zb, w0, w1)
    br.abutment(S0, zb, decks[0][0], decks[1][1], -25); br.abutment(S1, zb, decks[0][0], decks[1][1], 25)
    note = ('KEYS-BRIDGES-V1 2026-09-30 (demande Alexandre: meshes des ponts des Keys; pont de Thunderstorm [Gameinformer]): '
            'axe = droite des piles 2B..20B (tooltip-ligne Alexandre), chaussees V16 (deux tabliers -14.5..-2.2 / -0.8..12.5 m), '
            'culees s %.0f / %.0f (rives V16). Profil du dessous du tablier MESURE dans Thunderstorm [Gameinformer] (pose resolue sur '
            '14 pieds de piles, rms 1.2 px): 7.7 m (2B) -> 24 m (travee de navigation 15B-16B, 44 m) -> 9.5 m (nord). '
            'Piles: 17 landmarks + pas 25.6 m au nord de 17B/20B (lu dans l image) + 1B.' % (S0, S1))
    return br.E, note, '#94a3b8'


# axe V16 du New Bahia Honda (trace sur la raster V16 yanis,16_keys, lisse, un sommet / 40 m, E -> O)
NBH_AXIS = [[-5107.2, -7162.9], [-5141.9, -7148.2], [-5178.6, -7135.8], [-5216.3, -7123.4], [-5254.4, -7110.7],
            [-5292.8, -7098.0], [-5331.2, -7085.4], [-5369.4, -7072.9], [-5407.6, -7060.5], [-5445.6, -7048.2],
            [-5483.6, -7035.8], [-5521.5, -7023.5], [-5559.4, -7011.0], [-5597.3, -6998.3], [-5635.2, -6985.6],
            [-5673.1, -6972.8], [-5711.1, -6960.2], [-5749.3, -6947.8], [-5787.6, -6935.7], [-5826.1, -6924.1],
            [-5864.8, -6913.2], [-5903.8, -6904.2], [-5943.0, -6899.2], [-5982.6, -6896.9], [-6022.5, -6895.6],
            [-6062.9, -6897.2]]
# piles: pieds cliques dans Keys (KEYS-REPOSE-V2) -> rayon x z=0 -> abscisse le long de l axe (s depuis la rive V16 est)
NBH_PILES = [339.1, 369.9, 393.9, 418.2, 442.4, 465.5, 487.5, 517.8, 538.0, 569.0, 589.0, 619.4, 645.0, 667.8, 689.3,
             719.1, 739.8, 766.8, 792.4, 818.7, 842.6, 865.5, 890.3, 993.6, 1017.6, 1045.1, 1068.3, 1091.2, 1117.4,
             1146.2, 1163.4, 1194.1, 1220.4, 1250.4, 1276.1, 1295.5]
# haut du tablier (bord sud) lu dans Keys: transition ombre/tablier le long de la verticale du bord V16 (+15.5 m)
NBH_TOP = [(330, 8.0), (394, 9.8), (418, 9.8), (466, 10.5), (488, 10.8), (518, 10.2), (538, 11.0), (569, 11.5), (589, 11.5),
           (619, 11.8), (645, 12.0), (668, 12.0), (689, 12.8), (719, 12.5), (740, 12.5), (767, 13.0), (792, 12.8), (819, 12.8),
           (843, 12.5), (994, 13.0), (1018, 12.2), (1045, 12.8), (1068, 12.2), (1091, 12.0), (1117, 12.2), (1146, 13.5),
           (1163, 12.2), (1194, 13.8), (1250, 14.2), (1335, 9.0)]


def new_bahia_honda(L):
    br = Bridge(poly=NBH_AXIS); off = 330.0 - 0.0   # s du 1er sommet de l axe = 330 (rive est V16)
    pr = np.array(NBH_TOP, float); co = np.polyfit(pr[:, 0], pr[:, 1], 4)
    DEPTH, PAR = 1.8, 1.0
    zb = lambda s: float(np.polyval(co, s + off)) - DEPTH - PAR
    S0, S1 = 0.0, br.S[-1]
    br.deck(S0, S1, zb, -15.5, 15.5)
    for s in np.arange(S0, S1, 10.0): br.L(br.P(s, 0, zb(s) + DEPTH + 0.8), br.P(min(s + 10, S1), 0, zb(min(s + 10, S1)) + DEPTH + 0.8))  # glissiere centrale
    piles = list(NBH_PILES)
    for a, b in zip(NBH_PILES[:-1], NBH_PILES[1:]):          # piles cachees par l avion (24B-26B): pas regulier
        k = int(round((b - a) / 25.8))
        piles += [a + (b - a) * j / k for j in range(1, k)]
    for s in sorted(piles):
        s -= off
        if S0 + 3 < s < S1 - 3: br.bent(s, zb, -15.5, 15.5, ncol=4, col=1.3)
    br.abutment(S0, zb, -15.5, 15.5, 25); br.abutment(S1, zb, -15.5, 15.5, -25)
    note = ('KEYS-BRIDGES-V1 2026-09-30: axe V16 trace sur la raster (26 sommets, E->O), tablier unique 31 m (bords V16 +-15.5), '
            'culees aux rives V16 (s 330 / 1335). Piles = pieds cliques dans Keys (pose KEYS-REPOSE-V2) projetes a z=0 '
            '(ecart lateral a la chaussee V16 0.8 m, pas 25.8 m) + 3 piles cachees par l avion (pas regulier). Haut du tablier '
            'lu dans Keys le long du bord sud: 8 m a l est -> 12.5 m -> ~13.5 m a l ouest; zone 22B-26B masquee par l avion: '
            'pas de bosse visible ailleurs, profil lisse par-dessus.')
    return br.E, note, '#a8a29e'


# Old Bahia Honda: tronçon ouest de la ligne V16 (trace raster: (-5520.0,-7231.4) -> (-6034.9,-6986.7), rectiligne a 5 m)
OBH_A, OBH_B = (-5520.0, -7231.4), (-6034.9, -6986.7)
# piles: pieds cliques dans Keys (KEYS-REPOSE-V2) -> z=0 -> abscisse sur l axe (depuis OBH_A, vers l ouest)
OBH_PILES = [-18.6, 29.3, 78.2, 133.0, 180.0, 230.7, 281.2, 301.3, 323.2, 344.3, 364.3, 384.8, 407.3, 429.8, 451.5,
             473.2, 494.0, 518.0, 537.0, 557.5, 587.2]
# haut du tablier lu dans Keys a la verticale des piles (transition treillis sombre -> dalle claire); 1B-3B illisibles
OBH_TOP = [(-25, 20.0), (60, 20.3), (133.0, 20.5), (180.0, 18.0), (230.7, 18.2), (281.2, 18.8), (301.3, 19.8), (323.2, 20.0),
           (344.3, 19.0), (364.3, 17.0), (384.8, 16.0), (407.3, 15.2), (429.8, 14.8), (451.5, 14.0), (473.2, 13.5),
           (494.0, 12.5), (518.0, 12.2), (537.0, 11.5), (557.5, 10.5), (587.2, 11.2)]


def old_bahia_honda(L):
    a, b = np.array(OBH_A), np.array(OBH_B); u = (b - a) / np.linalg.norm(b - a); n = np.array([-u[1], u[0]])
    # axe reel = centre des piles = pieds cliques (coin sud-ouest) - 5 m: 2.2 m au sud de l axe V16 a s 140 -> 9.2 m a s 600
    wof = lambda s: 2.2 + 6.8 * (s - 140) / 460
    br = Bridge(poly=[a - u * 30 + n * wof(-30), a + u * 610 + n * wof(610)]); off = 30.0
    pr = np.array(OBH_TOP, float); co = np.polyfit(pr[:, 0], pr[:, 1], 3)
    top = lambda s: float(np.polyval(co, s - off))
    zb = lambda s: top(s) - 1.8                       # dessous de la dalle
    S0, S1 = 5.0, 630.0; HW = 5.0                     # dalle ancienne route: 2 voies (V16 ~ +-9.5 m avec liseres)
    br.deck(S0, S1, zb, -HW, HW, depth=1.2, parapet=0.6)
    ps = [s + off - 2.5 for s in OBH_PILES]           # centre de la pile = coin clique (face ouest) - 2.5 m
    ZP = 5.5                                          # haut des piles massives (lu dans Keys sur 8B, 14B, 20B)
    for s in ps:                                      # piles: bloc 5 x 12 m, z 0 -> ZP
        for zz in (0.0, ZP):
            cs = [(s - 2.5, -6), (s + 2.5, -6), (s + 2.5, 6), (s - 2.5, 6)]
            for i in range(4): br.L(br.P(*cs[i], zz), br.P(*cs[(i + 1) % 4], zz))
        for (x, w) in [(s - 2.5, -6), (s + 2.5, -6), (s + 2.5, 6), (s - 2.5, 6)]: br.L(br.P(x, w, 0.0), br.P(x, w, ZP))
    # poutres en treillis (Warren) de part et d autre: membrure basse sur les piles, haute sous la dalle
    for w in (-HW + 0.5, HW - 0.5):
        for s0, s1 in zip(ps[:-1], ps[1:]):
            n = max(2, int(round((s1 - s0) / 8.0))); xs = np.linspace(s0, s1, n + 1)
            for i in range(n):
                x0, x1 = xs[i], xs[i + 1]
                br.L(br.P(x0, w, ZP), br.P(x1, w, ZP)); br.L(br.P(x0, w, zb(x0)), br.P(x1, w, zb(x1)))
                br.L(br.P(x0, w, ZP), br.P(x0, w, zb(x0)))
                if i % 2 == 0: br.L(br.P(x0, w, ZP), br.P(x1, w, zb(x1)))
                else: br.L(br.P(x0, w, zb(x0)), br.P(x1, w, ZP))
    note = ('KEYS-BRIDGES-V1 2026-09-30: ancien pont (voie ferree Flagler reconvertie): axe = troncon ouest de la ligne V16 '
            '(trace raster, rectiligne a 5 m) decale sur le centre des piles (2 m au sud a l est -> 9 m a l ouest, dans la bande V16 +-9.5), '
            '21 piles aux pieds cliques dans Keys (KEYS-REPOSE-V2) projetes a z=0 (pas 48 m a l est puis 21 m), piles massives '
            '5x12 m jusqu a 5.5 m (lu), poutres en treillis, dalle 10 m. Hauteur confirmee par calage du contraste dalle/eau. '
            'Haut de dalle lu dans Keys a la verticale des piles: ~20 m a l est (4B-10B) -> 11 m a l ouest (21B). '
            'Troncon est (trou V16 + camelback vers Bahia Honda Key) non modele.')
    return br.E, note, '#78716c'


# Seven Mile: dessous du tablier (bas du bandeau clair) lu dans Leonida Keys 01 (Airplane) (X) a la verticale des piles
SM_BOTTOM = [(-330, 2.5), (-262, 3.5), (-233, 5.0), (-206, 6.8), (-178, 8.2), (-148, 10.2), (-124, 11.8), (-101, 13.5),
             (-76, 14.8), (-51, 16.0), (-25, 17.2), (0, 18.2), (27, 18.8), (54, 19.2), (78, 19.0), (101, 18.5), (152, 16.8),
             (204, 14.2), (391, 5.0)]


def pier_wall(br, s, zb, w, along=3.0, across=7.0, footing=1.5, zw=0.0):
    z = zb(s) - 1.2
    cs = [(s - along / 2, w - across / 2), (s + along / 2, w - across / 2), (s + along / 2, w + across / 2), (s - along / 2, w + across / 2)]
    for zz in (zw + footing, z):
        for i in range(4): br.L(br.P(*cs[i], zz), br.P(*cs[(i + 1) % 4], zz))
    for c in cs: br.L(br.P(*c, zw + footing), br.P(*c, z))
    cap = [(s - 1.6, w - 8.5), (s + 1.6, w - 8.5), (s + 1.6, w + 8.5), (s - 1.6, w + 8.5)]   # chevetre en marteau
    for zz in (z, z + 1.2):
        for i in range(4): br.L(br.P(*cap[i], zz), br.P(*cap[(i + 1) % 4], zz))
    for c in cap: br.L(br.P(*c, z), br.P(*c, z + 1.2))
    ft = [(s - 3.5, w - 6), (s + 3.5, w - 6), (s + 3.5, w + 6), (s - 3.5, w + 6)]
    for zz in (zw - 0.5, zw + footing):
        for i in range(4): br.L(br.P(*ft[i], zz), br.P(*ft[(i + 1) % 4], zz))


def seven_mile(L):
    ids = list(range(1, 22))
    Pp = np.array([L['Seven Mile Bridge (%dB)' % i]['xyz'][:2] for i in ids])
    c = Pp.mean(0); u = np.linalg.svd(Pp - c)[2][0]; u = u if u[0] < 0 else -u; n = np.array([-u[1], u[0]])
    WC = -5.0                                             # centre de la chaussee V16 (bande -14..+4 par rapport a la ligne des piles)
    br = Bridge(c + n * WC, u)
    pr = np.array(SM_BOTTOM, float); co = np.polyfit(pr[:, 0], pr[:, 1], 4)
    zb = lambda s: float(np.polyval(co, s))
    S0, S1 = -335.0, 395.0
    br.deck(S0, S1, zb, -9.5, 9.5)
    sl = sorted((Pp - c) @ u)
    piles = list(sl) + [sl[0] - 27.5 * k for k in (1, 2)] + [sl[-1] + 25.5 * k for k in range(1, 6)]
    for s in piles:
        if S0 + 4 < s < S1 - 4: pier_wall(br, s, zb, 5.0 - 5.0)
    br.abutment(S0, zb, -9.5, 9.5, -25); br.abutment(S1, zb, -9.5, 9.5, 25)
    note = ('KEYS-BRIDGES-V1 2026-09-30: axe = droite des 21 piles (xB) (triangulees Airplane + Keys) decalee au centre de la '
            'chaussee V16 (-5 m; tablier +-9.5 m = bande V16), culees s -335 / 395 (rives V16 -310 / 295 + rampes). Dessous du '
            'tablier lu dans Leonida Keys 01 (Airplane) (X) a la verticale des piles (bas du bandeau clair): 3.5 m (1B, est) -> '
            '19.2 m (bosse 12B-14B, recoupe Seven Mile Bridge (C) 19.3 m) -> 5 m (W). Piles murs + chevetre en marteau.')
    return br.E, note, '#cbd5e1'


def old_seven_mile(L, ZTOP=None, SPAN=None):
    """ancien viaduc a arches (voie Flagler): segments V16 sur l eau, parallele au nouveau pont (w +27..29)."""
    ZTOP = ZTOP or OSM_ZTOP; SPAN = SPAN or OSM_SPAN
    ids = list(range(1, 22))
    Pp = np.array([L['Seven Mile Bridge (%dB)' % i]['xyz'][:2] for i in ids])
    c = Pp.mean(0); u = np.linalg.svd(Pp - c)[2][0]; u = u if u[0] < 0 else -u
    E = []
    for s0, s1, w in OSM_SEGS:
        br = Bridge(c + np.array([-u[1], u[0]]) * w, u)
        zt = lambda s: ZTOP
        br.deck(s0, s1, lambda s: ZTOP - 1.0, -3.2, 3.2, depth=1.0, parapet=0.5, frame=SPAN)
        for x in np.arange(s0, s1 + 0.1, SPAN):          # piles + arches (demi-ellipses) sur les deux faces
            for w_ in (-3.2, 3.2):
                br.L(br.P(x, w_, 0.0), br.P(x, w_, ZTOP - 1.0))
                if x + SPAN <= s1 + 0.1:
                    t = np.linspace(0, np.pi, 9); xs = x + 1.0 + (SPAN - 2.0) * (1 - np.cos(t)) / 2; zs = 1.2 + (ZTOP - 2.6) * np.sin(t)
                    for i in range(8): br.L(br.P(xs[i], w_, zs[i]), br.P(xs[i + 1], w_, zs[i + 1]))
        E += br.E
    note = ('KEYS-BRIDGES-V1 2026-09-30: ancien Seven Mile (viaduc a arches) = segments V16 au-dessus de l eau (w +27..29 par '
            'rapport a la ligne des piles du nouveau pont): s -310..-104, -74..42, 70..295; dalle 6.4 m; hauteur %.1f m et '
            'portee %.0f m lues dans Leonida Keys 01 (Airplane) (X).' % (ZTOP, SPAN))
    return E, note, '#d6d3d1'


OSM_SEGS = [(-310, -104, 29.0), (-74, 42, 29.2), (70, 295, 27.1)]
OSM_ZTOP, OSM_SPAN = 6.0, 10.0

BUILDERS = {'Lake Surprise Viaduct': lake_surprise, 'New Bahia Honda Bridge': new_bahia_honda, 'Old Bahia Honda Bridge': old_bahia_honda,
            'Seven Mile Bridge': seven_mile, 'Old Seven Mile Bridge': old_seven_mile}

if __name__ == '__main__':
    L = json.load(open(D('landmarks.json')))
    out = {}
    for k, f in BUILDERS.items():
        E, note, col = f(L); out[k] = {'color': col, 'world_edges': E, 'note': note, '_credit': CREDIT}
        print(k, len(E), 'aretes')
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = D('building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_keysbridges_0930')
        M = json.load(open(mp)); M.update(out)
        json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique ->', mp)
