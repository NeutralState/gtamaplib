import gtamaplib as ml
import gtamapdata as md
from gtamaplib import intersect_ray_and_point

cam = ml.get_camera('Leonida Keys Postcard (X)')
cam.set_xyz((-3808.492, -6794.543, 147.644))
cam.set_ypr((299.963, -11.936, 0.000))
cam.set_fov((47.268, None))
cam.clear_landmark_directions()
results = []
for lm_name, px in md.pixels.get('Leonida Keys Postcard (X)', {}).items():
    if lm_name not in md.landmarks:
        continue
    target = md.landmarks[lm_name]
    ray = (cam.xyz, cam.get_landmark_direction(lm_name))
    angle = intersect_ray_and_point(ray, target)[-1] * 60
    results.append((angle, lm_name))
for angle, lm_name in sorted(results, reverse=True)[:10]:
    print(f'{angle:8.3f} arcmin  {lm_name}')
