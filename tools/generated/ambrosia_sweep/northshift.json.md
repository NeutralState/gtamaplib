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

# AMB-DEGEN (2026-07-24) — l'axe de degenerescence de rlx, teste

rlx: "it's around 25 m north per meter of elevation" — le nord-sud et
l'altitude ne sont pas deux debats, c'est UN seul axe. Verifie sur ses
propres chiffres: notre monde -> son "latest gtamaplib" = dy +242 / dz
+7.7 = 31.2 m de nord par m d'altitude. Meme axe.

Sweep le long de cet axe (t=0 notre monde, t=1 son latest), ancres fixes,
solve joint complet par pas:

    t      dy     dz    cout   vs t=0   piliers Skyway vus par Fires
  -0.50   -121   -3.9  219.57           71.5'   75.7'
  -0.25    -60   -1.9  209.54           32.6'   35.7'
   0.00     +0   +0.0  163.94    0.00    1.6'    1.0'   <- notre monde
  +0.25    +60   +1.9  198.68  +34.74   26.6'   26.2'
  +0.50   +121   +3.9  217.04  +53.10   69.8'   70.7'
  +0.75   +182   +5.8  229.88  +65.94  109.8'  111.8'
  +1.00   +242   +7.7  236.55  +72.61  147.4'  150.7'   <- son latest
  +1.25   +302   +9.6  241.44  +77.50  185.4'  189.8'

CORRECTION de ce qu'on avait dit: le sweep dz PUR etait plat (les cams
re-pitchent), d'ou "nos ancres ne peuvent pas trancher 5-vs-15". FAUX le
long de l'axe reel: un decalage vertical dans la construction du silo
traine +25-31 m de nord par metre, et CA le pont le voit (61'/100m ->
~15-19' par metre d'altitude, contre 1-2' de residus dans notre monde).

Repose entierement sur l'identification des 2 piliers dans Fires.
