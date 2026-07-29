# TERRAIN_PIPELINE — modéliser un terrain en 3D, adéquatement

Le kit complet, né des chantiers Ambrosia Hill + Canyon Kalaga (2026-07-26→29).
Doctrine: **données** (traces d'Alexandre, ancres triangulées) et **hypothèses**
(pentes, profils) toujours séparées et déclarées; toute hypothèse a un chemin
vers la mesure.

## Étape 1 — 2D: les lignes (la source de vérité)

1. Générer le rendu des lignes courantes (ex. `canyon_lines.py`).
2. **Alexandre annote DIRECTEMENT le PNG généré** dans `tools/generated/`
   (traits de couleur). Pas de screenshots recopiés — jamais.
3. Extraction pixel-exact par diff (copie annotée vs rendu propre régénéré +
   segmentation couleur) → `tools/data/*_corrections.json`.
4. Itérer jusqu'à validation. Les lignes corrigées se dessinent en TRACE
   EXACTE (aucun algo ne les retouche).

Extracteurs disponibles: DP skyline (`hill_mesh.py`, occluders/fils/arbres
gérés), lignes multi-types (`canyon_lines.py`: rims/route/pont, clics calib UI
en override ±8 px).

## Étape 2 — 3D: le registre + l'orchestrateur

- `tools/data/terrains.json` — registre déclaratif: moteur, paramètres
  validés, **provenance de chaque hypothèse** (mesuré vs déclaré).
- `tools/terrain.py --all` — régénère tous les meshs UI. `--only <nom>`,
  `--list` (montre les provenances).

Moteurs: `hill_mesh.py` (crête + volume à pente déclarée), `canyon_mesh.py`
(échafaudage route, parois, surfaces balayées avec terminaisons physiques:
rebord exact du cadre + ligne des arbres par luminance).

Règles UI: seuls NOS modèles validés entrent dans
`building_meshes_procedural.json`. Les références externes (rlx) vivent dans
`tools/data/rlx_mountains_meshes.json`.

## Étape 3 — Mesure: transformer les hypothèses en chiffres

- `anchor_harvest.py` — triangule en masse tout landmark 2+ cams posées
  jamais positionné (gates: angle ≥2.5°, perp ≤1.2%, bornes; blacklist des
  paires circulaires; V2 TODO: gate forwardness t>0).
- `crossclick_guide.py` — guides épipolaires: le rayon d'un mark projeté
  dans une autre frame avec graduations; Alexandre clique SUR la ligne
  (même nom) → ancre immédiate. C'est l'outil de densification ciblée.
- `depth_terrain.py` — Depth Anything V2 calibré métrique sur les ancres de
  la frame (LOO imprimé). Le réseau = la forme; les ancres = l'échelle.
  Précision ∝ densité d'ancres (Bikers 9.9%, canyon 21%).
- `hill_stereo.py` — stéréo de silhouettes (analyse; fiable au sommet
  seulement).

## Étape 4 — La boucle

Nouvelle mesure (clic croisé, harvest, triangulation) → mettre à jour le
paramètre correspondant dans `terrains.json` (et sa provenance) →
`terrain.py --all` → CI (`ci_healthcheck.py`).

Exemple vécu: la profondeur d'Ambrosia Hill est passée de « fov EL 50
déclarée » (d 2246) à « mesurée multi-vues » (d 2062, gaps 6-27 m) — un
seul champ du registre a changé, tout s'est régénéré.

## Pièges connus (payés cash)

- `ml.get_camera()` rend la MÊME instance → re-set l'état avant CHAQUE usage.
- Paires circulaires: une pose fittée sur un clic interdit de « trianguler »
  ce clic (fausses ancres).
- Features d'eau à rayons rasants sur z=0: intriangulables (spreads ~1 km).
- Respecter `z_constraint` et les plans de `structures.json` à l'écriture
  (les invariants CI les défendent).
- La médiane CI monte mécaniquement quand la couverture augmente:
  re-baseline documenté SEULEMENT si 0 landmark pré-existant n'a bougé.
