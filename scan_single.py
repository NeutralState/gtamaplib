import gtamapdata as md

calibrated = {name for name, data in md.cameras.items() if data.get('xyz') is not None}
cam_list = [c for c in md.pixels.keys() if c in calibrated]

overlaps = []
for i, cam_a in enumerate(cam_list):
    for cam_b in cam_list[i+1:]:
        shared = set(md.pixels[cam_a].keys()) & set(md.pixels[cam_b].keys())
        not_world = [lm for lm in shared if lm not in md.landmarks and 'Minimap' not in lm and 'Player' not in lm]
        if len(not_world) == 1:
            overlaps.append((cam_a, cam_b, not_world[0]))

print(f"Pairs with exactly 1 untriangulated landmark: {len(overlaps)}")
for a, b, lm in sorted(overlaps, key=lambda x: x[2])[:30]:
    print(f"  {lm}  —  {a} + {b}")
