# Orthophoto depuis la video biplan (cyberleak 2026)

Pipeline scratchpad versionne tel quel (2026-09-25). Chemins absolus vers le repo et vers `vid/v%04d.jpg` (frames 30 fps extraites de `GTA_6_plane_video_POLL_upload.ee_mirror_1.MP4`, non versionnees).

- `hud_track.py` : suivi par template des elements du HUD (mascotte, QR, textes) qui changent de disposition (frames 0, 450, 30 s...). `hud_track.json` = resultat.
- `solve_cam.py <cam> [fixfov] [zprior]` : pose + fov libre sur les clics d'Alexandre (prior roulis 0). Les frames POV aile ont le meme fov (106.7) que `Prison (Video) v091 (Wing)`; la chase-cam zoome en continu (70-93 selon l'instant): toujours fov libre si >= 3 grappes de points.
- `vo.py <start> <end> <step> <out.json>` (env `START_JSON`) : odometrie visuelle ancree terrain (LK + PnP + raffinement avec priors roulis/altitude/continuite de fov), masques HUD/avion/aile. Les poses = `[xyz, ypr, inliers, rms, hfov(, dmax)]`.
- Fondus entre chaines ancrees : interpolation lineaire des positions et du fov, angles par le plus court arc (piege du 0/360 a la frame 258).
- `ortho_video.py <res> <step> <dmax> <out.png> poses*.json` : reprojection sur le heightmap (+ DSM batiments), z-buffer avec tolerance rasante, masque par frame (HUD suivi: mascotte/QR masques, textes en poids 0.15), fondu aux bords (`FEATHER`), meilleure vue dominante (`WPOW`, `KEEP`), dmax par frame (6e element), `BBOX` pour tests rapides, `DSM`/`DSM_V16`/`DSM_DEFAULT_H`.
- `dsm.py` : DSM depuis nos meshs (niveaux -> enveloppes convexes) et depuis les silhouettes V16 (gris exact 176,176,176), hauteurs = landmarks dans la silhouette, murs = occulteurs.
- `grade.py`, `onmap.py` : etalonnage couleur et composition opaque sur la V16.
- `dt_overlay.py`, `dt_grid.py` : superposition des meshs/landmarks sur une frame pour identifier les tours.

Resultats livres dans `~/Downloads/ortho_biplan_v*`. Voir la memoire `ortho-airplane-video`.

## Bundle global (2026-09-25)
- `tracks.py <a> <b> <out.npz>` : pistes KLT par plan (memes masques que vo.py).
- `ba.py <out.json> <poses.json...> --tracks tr*.npz` : ajustement de faisceaux terrain-contraint (poses + fov par frame, points 3D a z libre avec prior sol, ancres = clics des cams video, priors de continuite; frames ancrees quasi figees). Env: `MAXOBS`, `NFEV`, `SIG_PX`, `SIG_A`, `SAT`, `PRI_*`. Robustesse des pistes par saturation tanh (pas la loss scipy, qui affaiblirait les ancres).
- Rendu final recommande : `DSM=1 DSM_DEFAULT_H=0 GRAZ=0.12 WPOW=4 KEEP=0.35 ortho_video.py 0.5 2 1100 out.png ba_all.json` (poids normalises avant la puissance).

## Hauteurs des batiments depuis la video (2026-09-25)
- `heights.py <poses.json> <x0> <x1> <y0> <y1> <out.json> [--debug N]` (env `FRAMES=a,b`, `HMAX`, `DMAX`, `GRAZMIN`, `MINAREA`) : pour chaque silhouette V16 (gris 176) de l'emprise, balaie h et maximise l'energie de contour du toit projete + l'effet de marche des aretes verticales, somme sur les frames qui voient toute l'empreinte hors masque. Valide sur les tours isolees (Infinity 174/176 m, Icon 187/180, Four Seasons 254/262); bruite sur les batiments bas a 400-900 m; echoue quand plusieurs tours se superposent.
- `ortho_video.py` lit `HEIGHTS=fichier.json,...` (+ `HCONF`) via `dsm.build_dsm_est` : toits et murs des batiments estimes.
- Lecon fov (plans POV aile) : sans points au sol PROCHES (< 500 m), altitude/tangage/fov se compensent (106.7, 126 et 143 trouves successivement pour la meme camera); 2 tooltips d'intersections a 250 m ont fixe hfov = 88.8, confirme par une 2e cam (v0820) resolue independamment a 12 m de la VO.

## Pistes de pont entre plans (2026-09-25)
- `bridge_tracks.py <ka> <kb> <out.npz>` : SIFT entre la derniere frame d'un plan et la premiere du suivant (masques), inliers F, prolonges par KLT de part et d'autre; ids >= 10^6 (reconnus par ba.py comme pistes de pont, non saturees: `SAT_BRIDGE`).
- Bundle final : `ANC_POS=20 ANC_ANG=0.5 ANC_FOV=0.5 SAT_BRIDGE=80 ba.py ... --tracks tr_*.npz tr_bridge*.npz`. Ancres souples obligatoires: une cam cliquee sans point proche (v0900) est degeneree le long de son axe (16 m/deg de fov a residus quasi constants); figee, elle bloque toute la chaine (doublons de batiments a Southside, 70-100 m). Avec les pistes de pont, l'ecart entre chaines mesure par correlation de phase passe de ~70 m a 0.3 m sans degrader aucune ancre.

## Controle d'accord avec la V16 (2026-09-25)
- `v16fit.py <ortho_graded.png> <meta.json> <out.jpg> <cx> <cy> <half>` : contours V16 dessines sur l'ortho + score (fraction des bords de route/batiment V16 tombant sur un bord fort de l'ortho). A passer sur prison / Southside / Hamlet avant chaque livraison; la V16 est la verite (calquee sur la leak).
- Regle bundle : cams ancrees sur tooltips = DURES; seules les cams degenerees (pas de point < 500 m) passent en `SOFT_FRAMES`. Ancres souples partout (v20) = derive de 6-30 m par rapport a la V16.

## Autoroutes surelevees (2026-09-25 soir)
- Cause des « autoroutes en bouillie » : les viaducs (6-15 m) sont au sol dans le heightmap → decales de 30-60 m et etires en incidence rasante. Identique dans toutes les versions ≤ v21.
- `heights.py` avec `LAYER=114,114,114 CHUNK=40 HMIN=0 HMAX=18 HSTEP=0.5` : hauteur par troncon de 40 m de la couche autoroute V16; `smooth_heights.py` (lissage le long du reseau, lam 0.6, voisins < 60 m); `dsm.build_dsm_est` : toits lisses (`DSM_SMOOTH_M=15`), murs sur le contour exterieur de l'union seulement, sans les 2 m du haut.
- Echangeur 61/82 : accord V16 des bords d'autoroute 0.59 → 0.84. Trous noirs = sol sous/derriere le tablier (jamais vu) : la V16 apparait dans la version sur la map.

- `onmap.py` : `INPAINT_M=14` remplit par inpainting les trous dont la demi-largeur est < 14 m (sol sous les tabliers, slivers) avant la composition; les grands trous restent en V16.

- Letterbox : la video a des bandes noires de 60 px en haut ET en bas (lignes 0-59, 1020-1079). Non masquees en haut, elles se projetaient en bande sombre le long du bord lointain de chaque frame (toutes les versions <= v23). `frame_mask` masque desormais 0-63 et 1016+.
- Fov des cams d aile : 106.7 pour les DEUX ailes (verifie avec les Points 1-4 au sol a 1-1.9 km + intersections + tours). Deux groupes de points ne suffisent pas a fixer un fov: il en faut trois (sol proche, sol moyen/lointain, sommets).

- `robust_solve.py <cam> [fixfov]` : solve multi-depart (yaw x distance x altitude x fov, 216 departs) + retrait iteratif des clics > 25 px. Indispensable pour une cam sans pose initiale credible (v2580 tombait a fov 180 avec un seul depart).

## Mosaique continue (2026-09-26)
- `tallmask.py <patch> <meta> <poses> <out> [HT] [heights,...]` : enleve emprise + trainee projetee de tout batiment >= HT m (landmarks/meshs/hauteurs estimees dans les silhouettes V16).
- `mosaic.py <out.jpg> <marge> a.png a.json [b.png b.json ...]` : mosaique multi-orthos sur la V16, premiere = prioritaire, inpainting des petits trous.
- Downtown : seules les parties basses vues quasi au nadir (GRAZ 0.22, dmax 700, HT 15, eau retiree) sont gardees; le coeur (v1980) et Brickell (v1380) sont entierement hauts -> exclus. Resultat = satmap_v27.
