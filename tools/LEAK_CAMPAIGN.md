# Campagne de saturation des leaks — 2026-07-16

**Constat**: 94 cams leak (vérité HUD absolue, la seule source non-circulaire),
588 markings au total, 45 cams à ≤2 markings, 14 à zéro. Chaque marking sur une
leak injecte un rayon d'ancrage en coordonnées jeu: upgrade de triangulation,
contrainte sur les cams voisines, cassage de cycles auto-référentiels, et
arbitrages nous-vs-rlx **décidables** (leçon du 2026-07-14: l'arbitrage Keys
est mort faute de densité leak, pas faute de leaks).

**Score** = 3×(LMs mono-obs in-frame) + 2×(2-obs) + 1×(3+obs) + bonus Keys.
C'est une **borne supérieure géométrique**: l'occlusion n'est pas modélisée —
ouvre la frame, si c'est un mur, skip (5 secondes). Ghosts assist = la réalité.
Ranking complet: `tools/generated/leak_campaign.json` (régénérable).

## Protocole par batch

1. Alexandre marque dans le UI (assist ON, verdict au clic: un rouge = régler
   tout de suite). Ancres d'abord (Four Seasons, Portofino, tours connues),
   puis features locales.
2. Claude roule `cycle --harvest --scan`, rapporte le gain (médiane, tiers
   promus, per-cam), committe le batch.
3. Après le batch Keys: retenter les arbitrages parkés au leak-judge
   (Key Lento, îles J/G, pins séries A/D, B01L).

## Batch 1 — KEYS (l'arbitre manquant de mardi)

| cam | classe | déjà | potentiel (1/2/3+ obs) |
|---|---|---|---|
| **Farm** | **A (pose HUD complète)** | **0** | **148 / 85 / 44** |
| Police Chase (B) | C | 4 | 49 / 100 / 23 |
| Police Chase (H,J,I,G,F,E,A) | C | 4 ch. | ~25 / ~100 / 22 ch. |
| Police Chase (D,C) | C | 4 ch. | 21 / 51 / 15 |
| Ocean near Keys (E) | C | 2 | 3 / 0 / 0 |

## Batch 2 — Les géants (vues skyline, occlusion à trier à l'œil)

| cam | classe | déjà | potentiel |
|---|---|---|---|
| Diner (SE) (B) | C | 2 | 176 / 217 / 199 |
| Diner (SE) (A) | C | 3 | 169 / 216 / 197 |
| Pool | C | 2 | 142 / 162 / 151 |
| Bar | C | 1 | 173 / 113 / 115 |
| Easy Inn | C | 4 | 163 / 144 / 49 |
| Hotel (W) | C | 5 | 155 / 98 / 79 |
| Alley (W) | **A** | 3 | 155 / 101 / 69 |
| Bedroom | C | 1 | 113 / 140 / 108 |
| Diner (S) | C | 3 | 131 / 118 / 29 |
| Shootout (S) | C | 0 | 109 / 133 / 63 |

## Batch 3 — Zéros à bootstrapper (classe C: marquer 3+ features → refine_cam_ypr)

Auto Shop (NW: classe A!, SE, SW), Hangar (B, C: classe A), Shootout (W),
Loading Zone near Prison (N), Pawn Shop (S), Intersection (SE), Hedge (D),
Tennis Court (SW), Highway (E: classe A), Motel, Intersection (N)…

## Hors campagne

- Classe D (Sidewalk (Jason) (S), Strip Club (Lucia), Street (Lucia/Jason)):
  frames leak mais **xyz non verrouillé** — utiles mais pas des injecteurs de
  vérité; traiter comme cams communautaires.
- Score 0 (Welcome Center, Tarmac, Store (Lucia)…): aucun LM connu in-frame —
  redevient intéressant quand de nouveaux LMs naissent dans leur champ.

## Après la campagne

Densité leaks ↑ → arbitrages parkés tranchés → covariances régénérées sur
réseau densément ancré → flip SIGMA-TRI-V1 (voir dual_metric_bench --ab
weighted). L'ordre vertueux: la vérité en amont du solveur.
