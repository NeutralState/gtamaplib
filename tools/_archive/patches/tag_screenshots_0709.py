#!/usr/bin/env python3
# tag_screenshots_0709.py -- prefixe les sources des cams screenshot par vague:
# "Screenshot 1 — <galerie>" (2025) / "Screenshot 2 — <galerie>" (2026), par
# symetrie avec la convention "Trailer 1/2 [frame]". Le champ source est de la
# METADONNEE pure (pas une cle; leak_cam_audit n'y matche que des dates) —
# zero reference cassee, reversible par git. Dry-run par defaut, --apply pour
# ecrire. LES LISTES CI-DESSOUS SONT UNE HYPOTHESE (2025 = lancement du site
# avec Trailer 2; 2026 = vague merch/editions/vehicules) — EDITE-LES si le
# decoupage reel differe.
import json, re, sys

SCREENSHOT_1 = [   # vague 2025
    'Jason Duval 02', 'Jason Duval 03', 'Jason Duval 05',
    'Lucia Caminas 02 (Pool)', 'Raul Batista 03',
    'Vice City 01', 'Vice City 02', 'Vice City 03', 'Vice City 05',
    'Vice City 06', 'Vice City 08', 'Vice City 09',
    'Leonida Keys 01', 'Leonida Keys 02', 'Leonida Keys 05',
    'Port Gellhorn 01', 'Port Gellhorn 04', 'Port Gellhorn 05',
    'Ambrosia 01', 'Ambrosia 02', 'Ambrosia 04',
    'Grassrivers 02', 'Mount Kalaga National Park 02',
    'Mount Kalaga National Park 04', 'Port Vice City',
    'Vice City Postcard', 'Leonida Keys Postcard', 'Port Gellhorn Postcard',
    'Ambrosia Postcard', 'Grassrivers Postcard',
]
SCREENSHOT_2 = [   # vague 2026
    "'95 Grotti Cheetah 04", 'Crest Kayak', 'Green Sports Car',
    "Jason's Safehouse Vehicles", 'Shitzu Squalo 01',
    'Stock 305 Clothing Store 01', 'Ultimate Edition 02',
    'Vintage Vice City Outfits and Hairstyles 04', 'Vintage Vice City Pack 02',
]

apply = '--apply' in sys.argv
cams = json.load(open('gtamapdata/cameras.json'))
n1 = n2 = 0
for name, m in cams.items():
    s = m.get('source', '') or ''
    if re.match(r'^20\d\d-', s) or s.startswith('Trailer') or s.startswith('Screenshot'):
        continue
    gal = re.sub(r'\s*\[.*$', '', s)
    if gal in SCREENSHOT_1:
        m['source'] = 'Screenshot 1 — ' + s; n1 += 1
    elif gal in SCREENSHOT_2:
        m['source'] = 'Screenshot 2 — ' + s; n2 += 1
    else:
        print(f'NON CLASSE (ajoute-le a une liste): {gal}  (cam {name})')
        continue
    print(f'  {m["source"]:60s} <- {name}')
print(f'\nScreenshot 1: {n1} | Screenshot 2: {n2}')
if apply:
    import shutil
    shutil.copy('gtamapdata/cameras.json', 'gtamapdata/cameras.json.bak_screenshots')
    with open('gtamapdata/cameras.json', 'w') as f:
        json.dump(cams, f, indent=2, ensure_ascii=True); f.write('\n')
    print('APPLIQUE (backup .bak_screenshots)')
else:
    print('DRY-RUN — verifie le tri, edite les listes au besoin, puis --apply')
