#!/usr/bin/env python3
"""gen_tiered_mesh.py — meshes a gradins depuis les VOLUMES V16 (tools/v16_tiers.py). [TIERED-MESH-V1 2026-09-30]

Pour chaque batiment de SPEC: polygone V16 -> regions (traits interieurs) -> hauteur par region (groupes nommes).
Geometrie: fut = contour exterieur (union) du sol jusqu'au plus bas des toits de gradins (anneaux d'etages tous les
~12 m), puis chaque region: anneau de toit a sa hauteur + aretes verticales depuis le haut du fut (parapet 1.2 m).
Elements de toit optionnels: 'drum' = region(s) couronne extrudee(s) de +h.
Usage: PYTHONPATH=. python3 tools/gen_tiered_mesh.py [nom ...] [--out f.json] [--apply]
"""
import json, os, sys, shutil
import numpy as np
import cv2

THIS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(THIS); sys.path.insert(0, THIS)
D = lambda f: os.path.join(ROOT, 'gtamapdata', f)
import v16_tiers as VT

# Jade Ocean: V16 3584 = lame centrale (7,10,13,14,9,12,15) + ailes (3,8,11,16) + gradins aux deux bouts. Sommet 203 m
# (LMs Jade Ocean / (SW), 202.7-202.9). Les vues de nuit (Biplane Night) montrent un seul fut a bouts arrondis dont le
# sommet est chanfreine aux extremites (couronne de LED rouges): gradins ESTIMES a -6 m (anneau interieur) et -12 m
# (anneau exterieur); la couronne ronde de la V16 (regions 9,10,12,13,14 = cercle) en tambour de +4 m (ESTIME).
SPEC = {
    # --- VICE BEACH 2026-10-07: tours dans des parcelles V16 plus larges; hauteurs = landmarks triangules (>= 2 cams), regions V16
    # choisies par les aretes de silhouette dans les cams (Sidewalk (Jason) (E), Venetian Islands, Rooftop Party, Megamundo, Vice Beach A/B)
    'Loews Miami Beach': {'poly': 3340, 'color': '#fde68a', 'groups': [([1, 2, 3], 87.1), ([0, 4], 25.0)],
        'src': 'tour = regions V16 1+2+3 (contiennent le LM 87.1, 4 cams); aretes 9.4 -> 5.8 px, sommet 16.9 -> ~0 px; ailes basses (regions 0+4) 25 m ESTIMEES (sommets coherents entre 20 et 35 m)'},
    'W South Beach': {'poly': 3556, 'color': '#e5e7eb', 'groups': [([44, 51, 60], 76.7), ([i for i in range(61) if i not in (44, 51, 60)], 27.4)],
        'src': 'tour = region V16 44 (+51, 60) au LM (SE) 76.7 (2 cams); podium 27.4 = LM (BNW) (2 cams); sommet 10.5 -> -0.8 px; les deux aretes de la tour restent 6-13 px a gauche dans 2 cams (tour en retrait de la parcelle, non corrige)'},
    'Royal Palm South Beach': {'poly': 3336, 'color': '#fef3c7', 'groups': [([0, 1, 2], 67.9), ([5, 7], 67.0), ([3, 4, 6, 8], 15.0)],
        'src': 'tour N (regions 0+1+2) aux LMs (N) 67.9 (3-4 cams), tour S (5+7) au LM (S) 67.0 (3 cams); aretes 12.9 -> 8.1 px; ailes basses 15 m ESTIMEES'},
    # --- MESH-FIT 2026-10-06 (pose audit): parcelles V16 extrudees a pleine hauteur = trop larges dans plusieurs cams;
    # la tour = les regions V16 choisies par les aretes de silhouette (tools/mesh_pose_audit.py, banc d'essai par variantes).
    'Wells Fargo Center': {'poly': 2269, 'color': '#94a3b8', 'groups': [([3, 0, 4], 186.6), ([1, 2], 35.0)],
        'src': 'tour = carre central V16 + ses deux bandes (regions 3+0+4), toit 186.6 (coin N); choisie par les aretes de silhouette: erreur 11.3 -> 1.8 px sur 9 aretes '
               '(Skyline, Basketball, Postcard, Port Vice City A/B, Shitzu Squalo 01, Grassrivers 05, Parachute Jump, Effluvia 3); podium/garage (regions 1+2) 35 m ESTIME'},
    'Infinity at Brickell': {'poly': 1929, 'color': '#a5b4fc', 'groups': [([6, 4], 177.2), ([0, 1, 2, 3, 5, 7, 8, 9, 10], 30.0)],
        'src': 'tour = fut nord + couronne ronde (regions 6+4), toit 177.2 (coins); choisie par les aretes de silhouette: erreur 8.2 -> 3.4 px (Prison, Highway (Peacock Bay) B, '
               'Grassrivers 05, Shoreline); volumes bas 30 m ESTIMES; helipad V16 1930 a 181 conserve'},
    'The Crimson': {'poly': 2729, 'color': '#fca5a5', 'shift': (-10.3, -19.2), 'core_scale': ([1], 0.9), 'groups': [([1], 92.0), ([0, 2], 30.0)],
        'src': 'tour = barre V16 (region 1) reduite x0.9, decalee (-10.3, -19.2) m (MESH-SHIFT-V1), toit 92 m LU (Postcard, Basketball, Water Tower); aretes <= 3.5 px dans 5 cams de jour '
               '(Vice Beach A/B, Basketball, Postcard, Parachute Jump); bloc NE + bande (regions 0+2) 30 m ESTIMES'},
    'Jade Ocean Condos': {'poly': 3584, 'color': '#34d399', 'shift': (-12.0, -8.0), 'groups': [
        ([3, 7, 8, 11, 15, 16, 9, 10, 12, 13, 14], 202.9), ([1, 4, 6, 2, 17, 19, 20, 21], 196.9), ([0, 5, 18, 22], 190.9)],
        'drum': ([9, 10, 12, 13, 14], 4.0),
        'src': 'sommet LM 202.9 (2 LMs); gradins -6/-12 m et tambour +4 m ESTIMES d apres le chanfrein de la couronne vu dans Biplane Night. '
               'Largeur du fut verifiee dans Beach et Biplane Night (93 vs 90 px, 132 vs 130 px); DISCORDANCE: les deux vues placent la tour '
               '13 m a l ouest / 4 m au sud du polygone V16 (residu 2 px); sur la silhouette V16 (VB-WATER 2026-10-04, Alexandre)'},
    # 1500 Ocean Dr (V16 3335): tour courbe a bout arrondi (region 4) sur podium a facade a persiennes (region 1),
    # lame rose a bow-windows octogonaux (region 2), immeuble ouest (0) + tourelle hexagonale (3). Comme l'IRL.
    '1500 Ocean Dr': {'poly': 3335, 'color': '#f9a8d4', 'shift': (-36.0, 8.0), 'groups': [([4], 63.8), ([2], 62.3), ([1], 21.0), ([0], 34.0), ([3], 36.0)],
        'src': 'tour 63.8 (LM) et lame rose 62.3 (3 LMs S/SE/NW/SW); podium 21 m LU dans Vice Beach (B) (echelles aux coins); '
               'immeuble ouest 34 m LU (toit a gradins blanc derriere la lame, Vice Beach (B)), tourelle hexagonale 36 m ESTIMEE. Note: Vice Beach (B) montre tout le complexe ~10-15 m au NO de la V16 (pose de la cam non verifiee, la tour Jade Ocean est decalee dans une autre direction -> pas un decalage V16)'},
    # --- Vice Beach, plus hautes tours (2026-09-30, demande Alexandre). Hauteur de la region qui contient le LM = LM;
    # les autres volumes ESTIMES (proportions IRL); les traits V16 donnent la forme (arrondis, ailes, gradins).
    # CORRIGE (Alexandre): la tour = le carre a verriere pyramidale (X de la V16) + ses ailes; le grand polygone = le podium bas
    'Blue Diamond': {'poly': 3575, 'color': '#60a5fa', 'shift': (-40.0, -20.0), 'groups': [([2, 3, 5, 7], 126.0), ([0], 40.0), ([1], 40.0), ([6], 40.0), ([4], 14.0)], 'core_scale': ([2, 3, 5, 7], 1.35),
        'pyramid': ([2, 3, 5, 7], 14.0), 'src': 'tour = carre a X de la V16 elargi x1.35 (largeur lue dans Venetian Islands: 63 px), toit 126 m + pyramide 14 m LUS dans Venetian Islands (le LM 146 = pointe lumineuse, 6 m au-dessus de la pyramide lue); tour ~30 px a l est de la V16 dans cette vue (garde sur la V16), ailes basses 40 m ESTIMEES (Venetian Islands: fut etroit), verriere pyramidale +14 m (vue dans Biplane Night (Video) Last); podium (region 4) 14 m ESTIME'},
    'Green Diamond': {'poly': 3576, 'color': '#4ade80', 'groups': [([2, 3, 4, 6], 126.0), ([0], 40.0), ([1], 40.0), ([5], 40.0), ([7], 14.0)], 'core_scale': ([2, 3, 4, 6], 1.35),
        'pyramid': ([2, 3, 4, 6], 14.0), 'src': 'tour = carre a X de la V16 elargi x1.35 (largeur lue dans Venetian Islands: 60 px), toit 126 m + pyramide 14 m LUS dans Venetian Islands (LM 145 = pointe); tour ~30 px a l est de la V16 dans cette vue (garde sur la V16), ailes basses 40 m ESTIMEES (Venetian Islands: fut etroit), verriere pyramidale +14 m (vue dans Biplane Night (Video) Last); podium (region 7) 14 m ESTIME'},
    # [EFFLUVIA 2026-10-02] relus dans Speaking with Brian at Effluvia (3): region 0 = PARCELLE (podium), pas la tour
    # [VB-WATER 2026-10-04, Alexandre] TOUTES les tours de Vice Beach (Icon, Murano, Jade Ocean, puis 1500 Ocean Dr, Diamonds, Tresor,
    # Apogee, V16 3274/3258): decalage VB-SETBACK RETIRE
    # [SIL-SCAN 2026-10-04, valide Alexandre] puis decalage REMIS, MESURE par les silhouettes (bords/sommet vs bord du ciel, toutes les cams,
    # sans clics) pour Blue Diamond (-40,-20; 9.7->3.7 px, 8 cams), Tresor (-28,-12; 10.9->5.1, 6), 1500 Ocean Dr (-36,+8; 8.7->5.7, 8),
    # Jade Ocean (-12,-8; 5.2->3.4, 10): concorde avec VB-SETBACK. Icon/Green Diamond/Apogee/Murano: minimum plat -> V16 (coupe au trait de cote). (le decalage de ~29 m vers l'ouest
    # mettait Icon/Murano dans la baie) -> remis sur les silhouettes V16 (« met sur les silhouettes v16 »); hauteurs inchangees.
    # MESH-SHIFT-V1 2026-10-06: tout le plan decale (-17.6, -0.9) m, mesure par les aretes de silhouette (Vice Beach A/B, Effluvia (3), Biplane v2580)
    'Icon at South Beach': {'poly': 3251, 'color': '#f472b6', 'shift': (-17.6, -0.9), 'groups': [([1], 140.0), ([2], 113.4), ([0], 12.0)],
        'src': 'lame courbe V16 (regions 1+2): partie haute 140 m (LM 142) et aile basse 113 m LUES dans Effluvia (3); podium 12 m ESTIME; sur la silhouette V16 (VB-WATER 2026-10-04, Alexandre: le decalage 28.7 m O le mettait dans la baie)'},
    'Murano Grande': {'poly': 3233, 'color': '#fb923c', 'groups': [([1], 139.0), ([2], 133.0), ([4], 127.0), ([3], 12.0), ([0], 30.0)],
        'src': 'tour courbe en 3 segments V16 (1,2,4): 139 (LM) puis gradins 133/127 ESTIMES; podium 12 et bloc 0 30 m ESTIMES; sur la silhouette V16 (VB-WATER 2026-10-04: decalage retire, il le mettait dans la baie)'},
    'Tresor Tower': {'poly': 3573, 'color': '#c084fc', 'shift': (-28.0, -12.0), 'groups': [([3, 1], 120.0), ([2], 100.0), ([0], 12.0)],
        'src': 'fut rond + lame (regions 3,1) = LM 120; aile est 100 m et podium 12 m ESTIMES'},
    'Flamingo South Beach': {'poly': 3400, 'color': '#fda4af', 'groups': [([2], 111.0), ([0], 51.0), ([1], 52.0), ([3], 62.0)],
        'src': 'hauteurs par region = LMs contenus (T* 111, NENE/NERNE 51-55, NWNE 52, SDS/SRSW 59-64): toutes MESUREES'},
    'The Waverly South Beach': {'poly': 3302, 'color': '#fde68a', 'groups': [([0], 113.0), ([1], 107.0)],
        'src': 'lame sud = LM (SE) 113; lame nord 107 = LM (NW) (35 m hors empreinte: attribution ESTIMEE)'},
    'The Ritz-Carlton Bal Harbour': {'poly': 3588, 'color': '#e5e7eb', 'groups': [([0, 1, 3], 104.0), ([2], 108.0), ([4, 5], 30.0)],
        'src': 'lame courbe (regions 0,1,3) = LM 104; edicule 108 et ailes basses courbes 30 m ESTIMES'},
    'Apogee Condominium': {'poly': 3228, 'color': '#a5b4fc', 'groups': [([0], 92.1), ([1], 15.0)],
        'src': 'tour (region 0) = LM 93; podium (region 1) 15 m ESTIME'},
    'Akoya Condominium': {'poly': 3586, 'color': '#99f6e4', 'groups': [([0], 145.0)],
        'src': 'plan cruciforme V16 = LM 145'},
    # nouvelles tours vues dans Effluvia (3) (largeurs/toits lus; decalage lateral lu; noms inconnus -> numero V16)
    'Vice Beach Tower (V16 3274)': {'poly': 3274, 'color': '#e2e8f0', 'groups': [([0], 80.8)],
        'src': 'tour blanche vue dans Effluvia (3): toit 80.8 m et position laterale LUS (largeur 117 px vs 104 V16)'},
    'Vice Beach Tower (V16 3258)': {'poly': 3258, 'color': '#e2e8f0', 'groups': [([0], 85.4)],
        'src': 'tour vue dans Effluvia (3): toit 85.4 m et position laterale LUS (largeur 114 vs 117 px)'},
    # [JD05-LEFT 2026-10-03] Bentley Bay South (clic Jason 05 'The Bentley Bay Condominium South (SW)'): parcelle V16 3257 au bord de
    # la baie, plus large que le batiment. Emprise = parcelle restreinte aux secteurs vus dans Vice Beach (B) (vue de l'est, x 702.5-885)
    # et Jason 05 (vue de l'ouest, bord SW x 302; 123 deg d'ecart). VB A donne le meme bord nord a ~20 m pres (non utilise: incoherent).
    'The Bentley Bay South': {'poly': 3257, 'color': '#f1f5f9', 'wedge': [('Vice Beach (B)', 702.5, 885), ('Jason Duval 05 (Machine Gun)', 150, 302)],
        'cut': [(1, (1372.5, 255.7), (0.47, -0.88), 9)],
        'groups': [([1], 80.0), ([9], 69.0), ([2, 3], 80.0)],
        'src': 'emprise = secteurs VB (B) x Jason 05 (largeur VB B 189-559 vs 205-570 px x2; bord SW Jason 05 297 vs 300 px); lame 80 m et aile sud 69 m LUES dans '
               'Vice Beach (A) et (B) (echelle z=0/z=80 de la V16); gradin = rayon VB B x 772 sur l axe (1372.5, 255.7); lame cote baie (regions 2,3) 80 m ESTIMEE '
               '(cachee derriere la region 1 depuis l est; Jason 05 montre un sommet ~80 m continu, flou); sommet Jason 05 697 vs 692-700 px'},
    # [JD05-LEFT 2026-10-03, corrige] C. Clyde Atkins U.S. Courthouse (V16 2583): batiment BAS a heliport. Mesure dans Biplane (Video) v2811
    # (pose sur 4 tooltips d'intersections d'Alexandre): toit 19.3 m au coin SW (position V16 confirmee). Le bloc sombre de Jason 05 et
    # Port VC (A) cliques 'Courthouse' = la tour a cylindres V16 2582 (renommee). Le 40 m de la v1 (VC10/Highway Pano S) etait faux.
    'C. Clyde Atkins U.S. Courthouse': {'poly': 2583, 'color': '#cbd5e1', 'groups': [([3, 1, 2, 5, 6, 7], 22.7), ([0, 4], 27.2)],
        'src': 'plan V16 2583; toit 19.3 m au-dessus du sol (sol 3.4 -> z 22.7) MESURE dans Biplane (Video) v2811 (coin SW: pied et toit sur la meme verticale); edicule sombre '
               '(regions 0,4) +4.5 m ESTIME (un etage au-dessus du toit, vu dans v2811); heliport sur le toit ouest (non modelise)'},
    # Tour a cylindres jumeaux (V16 2582, nom IRL incertain): fut a deux cylindres + coursives. Mesures Biplane (Video) v2811: cylindre ouest
    # 48.2 m, cylindre est 52.6 m. Explique le bloc sombre de Jason 05 (sommet ~50 m sur la ligne cliquee) et Port VC (A).
    'Twin Cylinder Tower (V16 2582)': {'poly': 2582, 'color': '#94a3b8', 'groups': [([3, 1], 51.2), ([2, 5], 55.6), ([4], 18.0), ([0], 13.0)],
        'src': 'plan V16 2582; cylindre ouest 48.2 m et est 52.6 m AU-DESSUS DU SOL (sol 3.0 -> z 51.2 / 55.6) MESURES dans Biplane (Video) v2811 (pied/sommet sur la meme verticale); LM (SE) z 51.1 concorde; '
               'attribution des regions aux cylindres ESTIMEE (la V16 dessine un octogone ouest + pointe sud); annexe est (4) 15 m et aile nord (0) 10 m ESTIMEES; '
               'Jason 05: sommet predit 751 px a ~50 m = clics (749-753 px)'},
    # [RIALTO-V4 2026-10-04] 1800 Club lu dans Rialto Causeway with Raul (1) (pose V4): dalle principale (regions 0,1) a toit cintre
    # (rives 152, faite 159.5 = LM), tour ronde sud (region 3) 150 + edicule 157, aile sud (region 2) 157.
    '1800 Club': {'poly': 2718, 'color': '#93c5fd', 'groups': [([0, 1], 152.0), ([2], 157.0), ([3], 150.0)], 'vault': ([0, 1], 6.3, (0.29, -0.96)), 'drum': ([3], 6.5),
        'src': 'plan V16 2718 (4 volumes); hauteurs LUES dans Rialto Causeway with Raul (1) (pose V4, 4.3 px/m): toit cintre de la dalle 152 -> 159.5 (LM 1800 Club 159.5), '
               'tour ronde 150 + edicule 156.5, aile sud 157'},
    'The Floridian': {'poly': 3606, 'color': '#fcd34d', 'wedge': ('Speaking with Brian at Effluvia (3)', 1514, 1640), 'groups': [([0], 98.5)],
        'src': 'tour = parcelle V16 3606 restreinte au secteur vu dans Effluvia (3) (x 1514-1640); toit 98.5 m LU (LM The Floridian 96.5)'},
}


_WATER = {}


def _clip_land(ring, K=5.0):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    A = np.array(ring); x0, y0 = A.min(0) - 80; x1, y1 = A.max(0) + 80
    key = (int(x0), int(y1))
    V = np.asarray(Image.open(os.path.join(ROOT, 'maps', 'yanis,16svg.png')).crop((16991 + int(x0), 11008 - int(y1) - 1, 16991 + int(x1) + 1, 11008 - int(y0))).convert('RGB')).astype(int)
    wat = ((V[..., 2] > V[..., 0] + 40) & (V[..., 2] > 120)).astype(np.uint8)
    wat = cv2.morphologyEx(wat, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))   # avale les pontons/quais fins
    n, lab, stt, _ = cv2.connectedComponentsWithStats(wat)                                                  # piscines (bleu V16) ignorees: seule l'eau > 1500 m2
    wat = np.isin(lab, [i for i in range(1, n) if stt[i, cv2.CC_STAT_AREA] > 1500]).astype(np.uint8)
    wat = cv2.resize(wat, (wat.shape[1] * int(K), wat.shape[0] * int(K)), interpolation=cv2.INTER_NEAREST)
    x0, y1 = int(x0), int(y1) + 1
    m = np.zeros(wat.shape, np.uint8)
    cv2.fillPoly(m, [np.array([[(x - x0) * K, (y1 - y) * K] for x, y in ring], np.int32)], 1)
    m[wat > 0] = 0
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs or cv2.contourArea(max(cs, key=cv2.contourArea)) < 4 * K * K: return None
    c = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 0.4 * K, True).reshape(-1, 2)
    return [[x0 + px / K, y1 - py / K] for px, py in c]


def union_ring(regs):
    A = np.vstack([np.array(r['ring']) for r in regs]); x0, y0 = A.min(0) - 2; x1, y1 = A.max(0) + 2; K = 5.0
    m = np.zeros((int((y1 - y0) * K) + 1, int((x1 - x0) * K) + 1), np.uint8)
    for r in regs: cv2.fillPoly(m, [np.array([[(x - x0) * K, (y1 - y) * K] for x, y in r['ring']], np.int32)], 255)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); c = max(cs, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, 0.4 * K, True).reshape(-1, 2)
    return [[x0 + px / K, y1 - py / K] for px, py in c]


def build(names=None):
    import v16_resect as RR
    out = {}
    for name, S in SPEC.items():
        if names and name not in names: continue
        R = {r['id']: r for r in VT.regions(S['poly'])}; E = []
        if S.get('shift'):   # [VB-SETBACK 2026-10-01] V16 Vice Beach = parcelle (terrasse/piscine cote plage): tour recalee sur les images
            sh = np.array(S['shift']); ids = S.get('shift_ids', list(R))   # [VB-WATER 2026-10-04] seules les regions de la TOUR sont decalees (podium = parcelle V16)
            R = {i: (dict(r, ring=[list(np.array(p) + sh) for p in r['ring']], centroid=list(np.array(r['centroid']) + sh)) if i in ids else r) for i, r in R.items()}
        if S.get('wedge'):    # restreindre les regions au(x) secteur(s) angulaire(s) vu(s) dans des cams (tour plus etroite que la parcelle)
            import common
            W = S['wedge'] if isinstance(S['wedge'], list) else [S['wedge']]
            def clip(ring):
                K = 5.0; A = np.array(ring); x0, y0 = A.min(0) - 5; x1, y1 = A.max(0) + 5
                m = np.zeros((int((y1 - y0) * K) + 1, int((x1 - x0) * K) + 1), np.uint8)
                cv2.fillPoly(m, [np.array([[(x - x0) * K, (y1 - y) * K] for x, y in ring], np.int32)], 1)
                yy, xx = np.mgrid[0:m.shape[0], 0:m.shape[1]]; X = x0 + xx / K; Y = y1 - yy / K
                for wc, u0, u1 in W:
                    cmw = common.get_cam(wc); ow = np.array(cmw.xyz[:2], float)
                    azf = lambda u: np.degrees(np.arctan2(*np.array(cmw.get_pixel_direction((u, 1000)), float)[:2]))
                    a0, a1 = sorted([azf(u0), azf(u1)])
                    az = np.degrees(np.arctan2(X - ow[0], Y - ow[1])); m[(az < a0) | (az > a1)] = 0
                cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not cs or cv2.contourArea(max(cs, key=cv2.contourArea)) < 2 * K * K: return None
                c = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 0.4 * K, True).reshape(-1, 2)
                return [[x0 + px / K, y1 - py / K] for px, py in c]
            R = {i: dict(r, ring=clip(r['ring'])) for i, r in R.items()}
            R = {i: dict(r, centroid=list(np.mean(r['ring'], 0))) for i, r in R.items() if r['ring']}
        for rid, p, n, nid in S.get('cut', []):   # couper une region V16 par une droite (gradin lu dans les images): cote (x-p).n>0 -> region nid
            K = 5.0; A = np.array(R[rid]['ring']); x0, y0 = A.min(0) - 5; x1, y1 = A.max(0) + 5
            m = np.zeros((int((y1 - y0) * K) + 1, int((x1 - x0) * K) + 1), np.uint8)
            cv2.fillPoly(m, [np.array([[(x - x0) * K, (y1 - y) * K] for x, y in A], np.int32)], 1)
            yy, xx = np.mgrid[0:m.shape[0], 0:m.shape[1]]; side = ((x0 + xx / K - p[0]) * n[0] + (y1 - yy / K - p[1]) * n[1]) > 0
            def vec(mk):
                cs, _ = cv2.findContours(mk.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); c = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 0.4 * K, True).reshape(-1, 2)
                return [[x0 + px / K, y1 - py / K] for px, py in c]
            R[nid] = dict(R[rid], id=nid, ring=vec(m * side)); R[rid] = dict(R[rid], ring=vec(m * ~side))
            for i in (rid, nid): R[i]['centroid'] = list(np.mean(R[i]['ring'], 0))
        if S.get('shift'):    # [VB-WATER 2026-10-04] jamais de batiment dans l'eau: regions coupees au trait de cote V16 (= leak ici)
            R = {i: dict(r, ring=_clip_land(r['ring'])) for i, r in R.items()}
            R = {i: dict(r, centroid=list(np.mean(r['ring'], 0))) for i, r in R.items() if r['ring']}
        if S.get('core_scale'):
            ids, sc = S['core_scale']; cc = np.mean(np.vstack([np.array(R[i]['ring']) for i in ids]), 0)
            for i in ids: R[i] = dict(R[i], ring=[list(cc + (np.array(p) - cc) * sc) for p in R[i]['ring']])
        def seg(a, b): E.append([[round(float(v), 2) for v in a], [round(float(v), 2) for v in b]])
        def ring(pts, z):
            for i in range(len(pts)): seg([*pts[i], z], [*pts[(i + 1) % len(pts)], z])
        H = {}
        for ids, z in S['groups']:
            for i in ids: H[i] = z
        used = [R[i] for i in H if i in R]
        g = RR.ground(*np.mean([r['centroid'] for r in used], 0)); zmin = min(H.values())
        U = union_ring(used)
        for z in [g] + list(np.arange(g + 12, zmin - 1, 12.0)) + [zmin]: ring(U, z)
        for p in U: seg([*p, g], [*p, zmin])
        for i, z in H.items():
            if i not in R: continue
            rr = R[i]['ring']; ring(rr, z); ring(rr, z + 1.2)
            if z > zmin:
                for p in rr: seg([*p, zmin], [*p, z + 1.2])
        if S.get('pyramid'):
            ids, ah = S['pyramid']; ids = [i for i in ids if i in R]; zb = max(H[i] for i in ids); Up = union_ring([R[i] for i in ids]); ap = np.mean(Up, 0)
            for p in Up: seg([*p, zb], [*ap, zb + ah])
        if S.get('vault'):   # toit cintre: arc le long du grand axe des regions (faite au milieu)
            ids, rise = S['vault'][:2]; zb = max(H[i] for i in ids); Uv = np.array(union_ring([R[i] for i in ids]))
            cv_ = Uv.mean(0); ax = np.array(S['vault'][2], float) if len(S['vault']) > 2 else np.linalg.svd(Uv - cv_)[2][0]; ax = ax / np.linalg.norm(ax); nx = np.array([-ax[1], ax[0]])
            sa = (Uv - cv_) @ ax; sn = (Uv - cv_) @ nx; a0, a1, n0, n1 = sa.min(), sa.max(), sn.min(), sn.max()
            ts = np.linspace(0, 1, 13); zt = lambda t: zb + 1.2 + rise * (1 - (2 * t - 1) ** 2)
            for nn in (n0, n1):
                pts = [[*(cv_ + ax * (a0 + (a1 - a0) * t) + nx * nn), zt(t)] for t in ts]
                for pa, pb in zip(pts[:-1], pts[1:]): seg(pa, pb)
            for t in ts[::2]:
                seg([*(cv_ + ax * (a0 + (a1 - a0) * t) + nx * n0), zt(t)], [*(cv_ + ax * (a0 + (a1 - a0) * t) + nx * n1), zt(t)])
        if S.get('drum'):
            ids, dh = S['drum']; ids = [i for i in ids if i in R]; ztop = max(H[i] for i in ids)
            Ud = union_ring([R[i] for i in ids]); ring(Ud, ztop + dh)
            for p in Ud: seg([*p, ztop], [*p, ztop + dh])
        out[name] = {'color': S['color'], 'world_edges': E, '_credit': 'Alexandre Leblanc (V16 + landmarks) + Claude Opus 5.5',
                     'note': 'TIERED-MESH-V1 2026-09-30: volumes = traits interieurs du polygone V16 %d (%d regions, tools/v16_tiers.py); %s.%s'
                             % (S['poly'], len(R), S['src'], (' DECALE de (%.1f, %.1f) m par rapport a la V16 (VB-SETBACK, valide Alexandre 2026-10-01: la V16 de Vice Beach dessine la parcelle, la tour est en retrait; decalage lu dans les images)' % tuple(S['shift'])) if S.get('shift') else '')}
    return out


if __name__ == '__main__':
    names = [a for a in sys.argv[1:] if not a.startswith('--') and not a.endswith('.json')]
    out = build(names or None)
    for k, v in out.items(): print(k, len(v['world_edges']))
    if '--out' in sys.argv: json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'))
    if '--apply' in sys.argv:
        mp = D('building_meshes_procedural.json'); shutil.copy(mp, mp + '.bak_tiered_0930')
        M = json.load(open(mp)); M.update(out); json.dump(M, open(mp, 'w'), indent=1, ensure_ascii=True); print('applique')
