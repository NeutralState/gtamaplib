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
