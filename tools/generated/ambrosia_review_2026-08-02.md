# Relecture du bounty #23 rouvert — 2026-08-02

rlx a rouvert le bounty le 31 juillet et demande une relecture avant de
refermer. Trois vérifications faites de notre côté. **Une seule donne quelque
chose d'utilisable**, et il faut dire lesquelles ne donnent rien.

---

## 1. Arbitrer ses 5 candidats — IMPOSSIBLE de notre côté

Ses candidats, en (hfov panorama, hfov postcard):

| | A | B | C | D | E | H (le nôtre aujourd'hui) |
|---|---|---|---|---|---|---|
| panorama | 48.6 | 49.1 | 49.5 | 49.9 | 50.3 | 50.91 |
| postcard | 48.1 | 48.4 | 48.6 | 48.7 | 48.9 | 51.76 |

Premier passage, sur les ancres visibles dont le `xyz` ne vient pas de la
caméra testée — 36 pour le panorama, 32 pour le postcard. Le classement sort
**monotone sur les deux caméras**: A le pire, E le meilleur des cinq, H
meilleur que tous.

    panorama   A 1.8'   B 1.2'   C 1.2'   D 0.8'   E 0.4'   H 0.3'
    postcard   A 10.2'  B 9.2'   C 8.3'   D 7.7'   E 7.7'   H 1.0'

**Ce résultat ne vaut rien, et voici pourquoi.** En resserrant au juge
strict — ancres avec au moins deux caméras sources connues, aucune dans la
zone Ambrosia — il reste **2 ancres pour le panorama et 0 pour le postcard**.
Les 33 autres ont un `source_cameras` vide: provenance inconnue,
invérifiable. Le classement favorable à H reflète très probablement le fait
que ces points ont été dérivés dans un monde où H était appliqué.

Les deux ancres réellement neutres (FAA Miami ATCT, MIA North Terminal Tower,
triangulées depuis les Keys / Vice Beach / Port Vice City) sont à 5.9 et
6.1 km, quasi au même azimut. Tous les candidats y passent entre 0.1' et
3.4' — elles ne discriminent rien.

**Conclusion: nous n'avons pas de témoin capable de départager ses cinq
candidats.** Mieux vaut le dire que fabriquer un vote.

---

## 2. Round Water Tower — les deux paires sont défendables, la sienne est
mieux conditionnée

Il a posté `(-2233.349, 483.818, 75.755)`, dérivé de *Ambrosia 02 (Panorama)
× Port Vice City (A)*. Le nôtre est à `(-2160.8, 519.0, 69.3)`, soit **81 m**
d'écart.

|  | sa paire | notre paire |
|---|---|---|
| caméras | Panorama × PVC (A) | Vice City Postcard × PVC (A) |
| parallaxe | **77.0°** | 38.8° |
| distance | 4259 m | 3247 m |
| résidu perpendiculaire | 5.09 m | **0.23 m** |
| 1 px de clic vaut | **0.7 m** | 2.3 m |

Sa paire est **mieux conditionnée** (deux fois plus de parallaxe, trois fois
plus de sensibilité). La nôtre croise mieux, mais 0.23 m à 38.8° veut dire
que les deux clics s'accordent à 0.1 px — c'est trop beau, et ça suggère que
ces deux caméras ne sont pas indépendantes sur ce point.

Nous avions exclu le clic du panorama (commit b4cb2ed) pour « vallée N-S
molle, sigma 39 m, tour à 4.6 km ». Ce raisonnement portait sur une pose du
panorama qui n'est plus la sienne. **À revoir plutôt qu'à opposer.**

---

## 3. Son code contre le nôtre — UNE INCOHÉRENCE INTERNE À SIGNALER

Il a posté `ambrosia.py`, `ambrosia_loss.py`, `ambrosia_map.py` le 25 juillet
(archivés dans `tools/_archive/rlx_originals/ambrosia_2026-07-25/`).

Son solveur fixe **`silo_ratio = 3.2`** en dur (lignes 25, 346, 506) et s'en
sert dans `get_silo()` pour poser l'échelle de la scène — c'est lui-même qui
écrit que « le silo, les ouvriers et les bisons déterminent l'échelle ».

Or, en triangulant le silo **avec ses propres caméras** (le `(L)` vient de
*Ambrosia Postcard (X)* × *Ambrosia 02 (Panorama)*):

    largeur (L)-(R)     16.44 m
    hauteur (L,R)-(B)   36.73 m
    RATIO                2.23        son code suppose 3.20

À 3.20, la hauteur devrait être 52.6 m au lieu de 36.7 — **un facteur 1.43
sur l'échelle verticale**.

Ce n'est PAS une réfutation externe: notre triangulation du silo dépend
entièrement de ses deux caméras, donc de sa solution. C'est une
**incohérence interne** — les poses que son solveur produit impliquent un
silo de ratio ~2.2, alors que la constante qu'il injecte en entrée vaut 3.2.

Et c'est exactement le levier qui gouverne son problème actuel: le silo fixe
l'échelle, l'échelle décide de la taille du lollipop et du pont, et il est
précisément coincé entre « pont trop petit » et « château d'eau trop grand ».

**C'est la seule des trois vérifications qui mérite de lui être remontée.**

---

## Conséquence pour nos données, à ne pas appliquer tant qu'il n'a pas figé

Ses nouvelles altitudes du 1er août: `lake_z=15.511`, `silo_z=20.373`,
`bison_z=20.661`, `bobcat_z=19.585`, `boxville_z=16.011`.

Nous avons **26 landmarks à z=14.486** (tout le contour de Lake Leonida,
méthode LAKE-V1) — son ancienne valeur. Un mètre d'écart sur tout le contour,
conditionné à un candidat qui n'est pas arrêté.
