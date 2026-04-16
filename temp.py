import gtamaplib as ml
import gtamapdata as md

cam_tennis = ml.get_camera('Tennis Court (NE)')
cam_waning = ml.get_camera('Waning Sands (A) (X)')

ray_tennis = (cam_tennis.xyz, cam_tennis.get_pixel_direction((1341, 262)))
ray_waning = (cam_waning.xyz, cam_waning.get_pixel_direction((2140, 861)))

point, pt_a, pt_b, distance, angle = ml.intersect_ray_and_ray(ray_tennis, ray_waning)
print(f'Sailboat Cay estimate: {point}')
print(f'Distance between rays: {distance:.3f} m')
print(f'Angle: {angle:.3f} deg')
