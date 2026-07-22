#!/usr/bin/env python3
"""rename_explosion_hill.py — 2026-07-21. Verdict de la resection pose-libre
(scratchpad explosion_resection.py / explosion_loo.py, ~1200 departs Powell):

La 'Ambrosia Hill' d'Explosion N'EST PAS la colline du cluster Ambrosia.
Preuve: pose d'Explosion 100% libre + profondeurs libres le long des rayons
partenaires -> aucune pose plausible ne reconcilie la colline avec le
billboard (Interchange, cam resolue) NI avec Rohde (87'/37' irreductibles,
poses aux bornes fov 25); billboard+Rohde seuls = 0.0' a 300m de la pose
devinee. Le marqueur d'origine avait lui-meme clique 'Ambrosia Hill (TW)'
au pixel exact de 'Mount Leonida' -> la crete d'Explosion = Mount Leonida.

Actions:
- Explosion 'Ambrosia Hill (TW)' [137,252]: SUPPRIME (dup exact du marquage
  'Mount Leonida' de la meme frame — zero perte d'info).
- Explosion 'Ambrosia Hill (BW)' [310,290]: SUPPRIME (dup exact de
  'Ambrosia Hill' de la meme frame).
- Explosion 'Ambrosia Hill' [310,290]: RENOMME 'Mount Leonida Ridge
  (Explosion)' — identite Leonida probable (meme crete que le pixel TW),
  nom a provenance explicite qui ne peut plus s'apparier avec le cluster.
"""
import json
import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
PX = os.path.join(REPO, 'gtamapdata', 'pixels.json')
LM = os.path.join(REPO, 'gtamapdata', 'landmarks.json')

NEW = 'Mount Leonida Ridge (Explosion)'


def atomic(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    px = json.load(open(PX))
    lms = json.load(open(LM))
    exp = px['Explosion']

    assert exp['Ambrosia Hill (TW)'] == exp['Mount Leonida'], exp
    assert exp['Ambrosia Hill (BW)'] == exp['Ambrosia Hill'], exp

    del exp['Ambrosia Hill (TW)']
    del exp['Ambrosia Hill (BW)']
    exp[NEW] = exp.pop('Ambrosia Hill')
    print(f'Explosion: -Ambrosia Hill (TW) -Ambrosia Hill (BW), '
          f'Ambrosia Hill -> {NEW} {exp[NEW]}')

    if NEW not in lms:
        lms[NEW] = {
            'xyz': None, 'source_cameras': [], 'error_m': None,
            'zone': None,
            'note': ("ex-'Ambrosia Hill' d'Explosion. Resection pose-libre "
                     "2026-07-21: incompatible avec la colline du cluster "
                     "Ambrosia (aucune pose plausible, 37-102' irreductibles"
                     "); crete de Mount Leonida (le pixel TW etait un dup "
                     "exact du marquage Mount Leonida)."),
        }
        print(f'landmarks: +{NEW}')

    atomic(PX, px)
    atomic(LM, lms)
    print('OK ecrit.')


if __name__ == '__main__':
    main()
