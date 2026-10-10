# Broken cameras repair (2026-10-09)

Cameras whose landmark residuals exceeded 25 sigma at their pose (MVS-V1 "broken" list). Each outlier marking was judged against the OTHER cameras that see the same landmark: fine elsewhere = bad click/label in this camera; bad everywhere = bad landmark. Excluded markings stay in pixels.json (UI) and are ignored by cam_rms / triangulation (gtamapdata/excluded_markings.json).

## Excluded markings

### Biplane Night (Video) v086
- Venetian (4) (1832.3') - only this cam

### Crest Kayak
- 104000 Overseas Hwy (270.2') - LANDMARK bad

### Diner (E)
- Billboard (Hank's Waffles) (B) (inf') - LANDMARK bad

### Diner (SE) (A)
- Domed Hills Sign (TW) (689.3') - CLICK/LABEL in this cam
- Quarry (461.1') - only this cam
- Traffic Sign (449.8') - LANDMARK bad
- Easy Hill (121.8') - LANDMARK bad

### Hank's Waffle (Bocamar Bridge)
- Bocamar Bridge (N) (152.9') - LANDMARK bad

### Jason Duval 03 (Boat)
- Roof (Key Lento) (840.6') - LANDMARK bad

### Key Lento
- Radio Tower (Key Lento) (inf') - LANDMARK bad
- Old Bahia Honda Bridge (21B) (53.2') - CLICK/LABEL in this cam
- New Bahia Honda Bridge (E) (33.6') - LANDMARK bad
- Blimp (R) (33.6') - LANDMARK bad

### Port Gellhorn 01 (Starlet Motel)
- Billboard near Intersection (BN) (inf') - only this cam
- Billboard near Intersection (BC) (inf') - only this cam
- Billboard near Intersection (TN) (511.1') - CLICK/LABEL in this cam
- Lamppost near Starlet Motel (60.7') - LANDMARK bad
- Starlet Motel Pool (A) (36.0') - LANDMARK bad
- Starlet Motel Pool (B) (33.5') - LANDMARK bad

### Port Gellhorn Postcard (X)
- Juice Fruit Sign (B) (800.0') - CLICK/LABEL in this cam
- Juice Fruit Sign (E) (777.6') - CLICK/LABEL in this cam
- Juice Fruit Sign (706.9') - CLICK/LABEL in this cam
- Juice Fruit Sign (W) (693.2') - CLICK/LABEL in this cam
- New Foundation Church (158.3') - LANDMARK bad
- Port of Tampa Container Crane (1) (96.1') - LANDMARK bad
- Port of Tampa Container Crane (2) (82.5') - LANDMARK bad
- Port of Tampa Container Crane (3) (44.6') - LANDMARK bad

### Vice City Sign
- Caribbean Airlines Cargo (W) (174.5') - LANDMARK bad
- Caribbean Airlines Cargo (E) (153.3') - LANDMARK bad
- Latitude on the River (S) (SW) (36.5') - CLICK/LABEL in this cam

### Added after the pose refits
- Crest Kayak: Island A (W) - fine in Leonida Keys 01 / Postcard (0.3-0.4'), behind the camera here (bad click/label)
- U-Turn (NE): 1703 E 5th St (Shack) (SW), (Shack) (SE), (Warehouse) (NW) - behind the camera at the pose that fits both billboards exactly; a PnP on all 5 points moved the camera 175 m and still left 18-81' -> the three labels are the suspects (UNCERTAIN, to check on the frame)
- Biplane Night (Video) v086: Venetian (1), (3), (5), (6) - single-camera landmarks inconsistent with the other Venetian points under any pose (49-68')

## Pose refits

- Hank's Waffle (Bocamar Bridge): refit with METRIC residuals (angle x distance). Its landmarks are 3-8 m away (roofline, red poles, arches, triangulated from the Diner cameras to ~0.5-1 m), so arcminute residuals exploded (median 114') although the pose was close. Metric median 0.37 -> 0.19 m; Bocamar Bridge (500-600 m) 156 / 44 / 16' -> 0.8 / 4.1 / 6.2'. Move +0.8 m, yaw +1.4 deg, fov -4.8 deg.
- Crest Kayak: orientation/fov refit on its two consistent points (1.1' each; self-consistent only).

## Result

10 of the 12 cameras are no longer broken (landmark rms <= 25 sigma at >= 25 m): Key Lento 0.4, Vice City Sign 3.3, Port Gellhorn Postcard 7.7, Port Gellhorn 01 11.9, Hank's Waffle 1.1, Diner (E) 2.4, Biplane Night v086 2.3, Crest Kayak 0.3, U-Turn (NE) 0.0, Jason Duval 03 5.7 sigma. Diner (SE) (A) has no usable landmark left (HUD-locked, exact pose).
Global healthcheck median 6.13' -> 5.99', mean 60.9' -> 50.4', metres median 0.615 -> 0.600 m.

## Still open

- Truck (2): its three One Biscayne Tower corners are mutually inconsistent under any orientation (NE fits, SE 34', SW 102' after refit) -> probably swapped/mislabelled corners; needs a look at the frame.
- U-Turn (NE): confirm on the frame which buildings the three 1703 E 5th St markings really are.
