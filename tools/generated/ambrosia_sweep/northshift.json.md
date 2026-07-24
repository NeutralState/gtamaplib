# AMB-NORTH-V1 — verdict

Toute la zone translatee vers le nord, ancres absolues fixes, solve joint
borne complet a chaque pas (25 rounds), cout comparable:

    dy (m)   cout ancre    vs dy=0
      -200       229.19     +65.25
      -100       209.21     +45.27
         0       163.94       0.00     <- minimum
      +100       213.61     +49.67
      +200       233.34     +69.40
      +300       243.12     +79.18
      +390       249.19     +85.25     <- position rlx (postcard y=4202)
      +500       257.37     +93.43

Decomposition a +390: ancres 60.1 (vs 4.4 a dy=0), zone 189.1 (vs 159.6).
Les deux piliers du Sunshine Skyway vus par Fires passent de 1.6'/1.0' a
240'/246' — 4 degres d'erreur.

Geometrie: seul le pont contraint cet axe.
  ancre                        vue par     dist    az     d(az) pour +100m
  FAA Miami ATCT (MIA)         Panorama    5875   180.9'         0.9'
  MIA North Terminal Tower     Panorama    5620   180.9'         1.0'
  Sunshine Skyway Bridge (N)   Fires       5489    75.0'        60.8'
  Sunshine Skyway Bridge (S)   Fires       5359    77.3'        62.8'

Les ancres MIA sont plein SUD: un decalage nord-sud glisse le long de leur
azimut (ancres colineaires = axe non contraint). Le Skyway est a l'OUEST:
le decalage lui est perpendiculaire -> 61'/100m. C'est la branche HUD-leak
(trio Diner -> pilier N, coordonnees moteur lues a l'ecran).
