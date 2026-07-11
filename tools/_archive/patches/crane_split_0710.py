#!/usr/bin/env python3
# crane_split_0710.py -- split temporel de la grue Asia Brickell Key (CC2).
# DIAGNOSTIC: les 3 obs exclues (Vice Beach B, PVC A, PVC B) ne collaient a
# AUCUNE des deux grues (test croise anti-swap negatif), mais convergeaient
# proprement ENTRE ELLES (2.6-6.3') sur une position a 15m (dz+3.3m) du
# groupe vivant: la FLECHE de la grue TOURNE entre les captures (2021->2026,
# et meme entre frames d'une meme scene). Les "menteurs" marquaient
# honnetement un objet MOBILE. Fix: pattern split de nom applique au
# temporel — les 3 obs deviennent (CC2B), exclusions retirees, chaque
# position triangulee proprement. Idempotent.
import json, sys
sys.path.insert(0, 'tools'); sys.path.insert(0, '.')
from common import log_event

OLD, NEW = 'Asia Brickell Key (CC2)', 'Asia Brickell Key (CC2B)'
MOVE = ['Vice Beach (B)', 'Port Vice City (A)', 'Port Vice City (B)']

px = json.load(open('gtamapdata/pixels.json'))
if all(NEW in px.get(c, {}) for c in MOVE):
    print('ok  split deja fait'); sys.exit(0)
for c in MOVE:
    assert OLD in px[c], f'{c}: marking {OLD} introuvable'
    px[c][NEW] = px[c].pop(OLD)
with open('gtamapdata/pixels.json', 'w') as f:
    json.dump(px, f, indent=2, ensure_ascii=True); f.write('\n')

lms = json.load(open('gtamapdata/landmarks.json'))
if NEW not in lms:
    lms[NEW] = {'xyz': None, 'source_cameras': [], 'error_m': None,
                'zone': lms[OLD].get('zone', 'unknown')}
    with open('gtamapdata/landmarks.json', 'w') as f:
        json.dump(lms, f, indent=2, ensure_ascii=True); f.write('\n')

e = json.load(open('gtamapdata/excluded_markings.json'))
for c in MOVE:
    if c in e:
        e[c] = [l for l in e[c] if l != OLD]
        if not e[c]:
            del e[c]
with open('gtamapdata/excluded_markings.json', 'w') as f:
    json.dump(e, f, indent=2, ensure_ascii=True, sort_keys=True); f.write('\n')

log_event('crane_split', 'rename_markings', lm=NEW, cams=MOVE,
          reason='fleche de grue mobile: 2 positions coherentes a 15m (dz+3.3m), split temporel CC2/CC2B, exclusions retirees')
print('split fait: 3 markings -> (CC2B), skeleton cree, 3 exclusions retirees')
print('Suite: triangulate les deux, puis cycle.')
