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
