#!/usr/bin/env python3
"""led_facades.py — ecrans LED de facade VUS dans le jeu, redresses depuis les frames (couche VISUELLE). [LED-FACADE-V1 2026-10-05]

Un ecran geant est un contenu: la meilleure fidelite est d'afficher l'image du jeu elle-meme. Pour chaque entree (batiment,
cam, face du volume mesh_solids): pixels allumes satures de la frame dans la projection de la face -> rayon ∩ plan de la face
= etendue reelle de l'ecran (s le long de la face, z), puis echantillonnage du plan sur une grille (0.25 m) projetee dans la
frame -> texture redressee. Sorties (derivees des frames, IGNOREES par git): tools/threejs/_led_<id>.png + _led_facades.json
{id: {a, b, s0, s1, z0, z1, img, cam, building}}.
Usage: python3 tools/led_facades.py
"""
import json, os, sys, math
import numpy as np
import cv2
from PIL import Image

THIS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(THIS); sys.path.insert(0, THIS); sys.path.insert(0, REPO)
import common
import mesh_solids as MSO
from facade_colors import basis

OUTD = os.path.join(THIS, 'threejs')
# verifie a l'oeil: InterContinental Miami, ecran LED de la face est (embleme rouge rond + bandeau vert) sur Port Vice City (A)
ENTRIES = [('intercontinental', 'InterContinental Miami', 'Port Vice City (A)', 8)]


def main():
    S = MSO.build(); C = json.load(open(os.path.join(REPO, 'gtamapdata', 'cameras.json'))); out = {}
    for lid, bname, cam, face in ENTRIES:
        so = S[bname]; O = np.array(so['layers'][0]['polys'][0]['outer'], float)
        zb, zt = so['layers'][0]['z0'], so['layers'][-1]['z1']
        a, b = O[face], O[(face + 1) % len(O)]; L = float(np.hypot(*(b - a))); t = (b - a) / L
        o, f, r, u, fpx, W, H = basis(common.get_cam(cam), {'fov': C[cam]['fov']})
        img = np.asarray(Image.open(os.path.join(REPO, 'frames', cam + '.png')).convert('RGB'))
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        lit = (hsv[..., 2] > 140) & (hsv[..., 1] > 110)
        def proj(s, z):
            X = np.array([a[0] + t[0] * s, a[1] + t[1] * s, z]); D = X - o; zz = D @ f
            return W / 2 + fpx * (D @ r) / zz, H / 2 - fpx * (D @ u) / zz
        # etendue de l'ecran: cellules (0.5 m) du plan dont le pixel projete est allume
        ss = np.arange(0, L, 0.5); zs = np.arange(zb, zt, 0.5); hits = []
        for z in zs:
            for s in ss:
                x, y = proj(s, z)
                if 0 <= x < W and 0 <= y < H and lit[int(y), int(x)]: hits.append((s, z))
        if len(hits) < 20: print(lid, 'pas assez de pixels allumes', len(hits)); continue
        hs = np.array(hits)
        s0, s1 = np.percentile(hs[:, 0], 3), np.percentile(hs[:, 0], 97); z0, z1 = np.percentile(hs[:, 1], 3), np.percentile(hs[:, 1], 97)
        s0, s1 = max(0, s0 - 0.5), min(L, s1 + 0.5); z0, z1 = max(zb, z0 - 0.5), min(zt, z1 + 0.5)
        # texture redressee: grille de 0.25 m projetee dans la frame (echantillonnage bilineaire)
        gs = np.arange(s0, s1, 0.25); gz = np.arange(z1, z0, -0.25)
        mapx = np.zeros((len(gz), len(gs)), np.float32); mapy = np.zeros_like(mapx)
        for j, z in enumerate(gz):
            for i, s in enumerate(gs): mapx[j, i], mapy[j, i] = proj(s, z)
        tex = cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR)
        fn = '_led_%s.png' % lid; Image.fromarray(tex).save(os.path.join(OUTD, fn))
        out[lid] = {'building': bname, 'cam': cam, 'a': a.round(2).tolist(), 'b': b.round(2).tolist(), 's0': round(float(s0), 2), 's1': round(float(s1), 2),
                    'z0': round(float(z0), 2), 'z1': round(float(z1), 2), 'img': fn, 'px': [int(tex.shape[1]), int(tex.shape[0])]}
        print(lid, 'ecran s %.1f-%.1f m (face %.1f m), z %.1f-%.1f m, texture %dx%d' % (s0, s1, L, z0, z1, tex.shape[1], tex.shape[0]))
    json.dump(out, open(os.path.join(OUTD, '_led_facades.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
