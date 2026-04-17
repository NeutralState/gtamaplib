import gtamaplib as ml
import gtamapdata as md
from find_camera_optimizer import find_camera_with_refinement

cam_name = "Ambrosia 01 (Bikers)"
lm_names = md.get_independent_landmarks(cam_name)
# Filter to only those visible in this camera
lm_names = [lm for lm in lm_names if lm in md.pixels.get(cam_name, {})]
print(f"Independent landmarks visible in {cam_name}: {lm_names}")

find_camera_with_refinement(
    cam_name=cam_name,
    lm_names=lm_names,
    rays=[],
    line=((-2742.894, 3731.02), (-2742.894, 3731.02)),
    radius=50,
    step=5,
    z_limits=(2, 15),
    pitch_range=(-5.0, 5.0, 0.5),
    hfov_range=(38.0, 55.0, 1.0),
    map_name="yanis",
    map_scale=1.0,
    map_area=(-3500, 3000, -2000, 5000),
    projection_area=None,
    basename="renders/Ambrosia01",
    refine=True
)
