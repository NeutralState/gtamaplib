#!/usr/bin/env python3
"""Polish Generate Map endpoint:
1. Extended view: don't auto-crop to landmarks bounding box; use a wider area
2. Thinner rays (width=1)
3. Add cam frustum bounds in black (the field-of-view edges)
"""
import os
GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'tools' \
    else os.path.dirname(os.path.abspath(__file__))
SERVER_PATH = os.path.join(GTAMAP_DIR, 'tools', 'server.py')

with open(SERVER_PATH) as f:
    content = f.read()

# Find the generate_map endpoint block to replace
import re

# We want to replace the area computation + drawing part
OLD = '''            # Compute crop area to fit cam + all landmarks with padding
            xs = [cam_xyz[0]] + [r[0][0] for r in rays]
            ys = [cam_xyz[1]] + [r[0][1] for r in rays]
            pad = 200
            x_min, x_max = min(xs) - pad, max(xs) + pad
            y_min, y_max = min(ys) - pad, max(ys) + pad
            area = (x_min, y_min, x_max, y_max)

            # Choose scale to keep image at reasonable size
            world_w = x_max - x_min
            world_h = y_max - y_min
            target_px = 1400
            scale = target_px / max(world_w, world_h)
            scale = max(0.05, min(0.5, scale))

            try:
                m = ml.get_map('yanis')
                m.open(scale=scale, add_padding=False)
                # Draw rays
                for lm_xyz, color, lm_name in rays:
                    line = [(cam_xyz[0], cam_xyz[1]), (lm_xyz[0], lm_xyz[1])]
                    m.draw_line(line, fill=color, width=2)
                # Draw landmark markers (small)
                for lm_xyz, color, lm_name in rays:
                    try:
                        m.draw_landmark(lm_name, r=5)
                    except Exception:
                        pass
                # Draw cam
                m.draw_camera(cam, r=10, d=100)'''

NEW = '''            # Compute crop area: include cam + all landmarks, then expand 30%
            # for context. Wider view shows neighborhood, makes geometry clearer.
            xs = [cam_xyz[0]] + [r[0][0] for r in rays]
            ys = [cam_xyz[1]] + [r[0][1] for r in rays]
            x_min_t, x_max_t = min(xs), max(xs)
            y_min_t, y_max_t = min(ys), max(ys)
            world_w_t = x_max_t - x_min_t
            world_h_t = y_max_t - y_min_t
            # Make square-ish area to avoid extreme aspect ratios
            world_size = max(world_w_t, world_h_t) * 1.3
            cx = (x_min_t + x_max_t) / 2
            cy = (y_min_t + y_max_t) / 2
            x_min, x_max = cx - world_size / 2, cx + world_size / 2
            y_min, y_max = cy - world_size / 2, cy + world_size / 2
            area = (x_min, y_min, x_max, y_max)

            # Scale for ~1400 px on largest dimension
            target_px = 1400
            scale = target_px / world_size
            scale = max(0.05, min(0.5, scale))

            try:
                m = ml.get_map('yanis')
                m.open(scale=scale, add_padding=False)

                # Draw cam frustum bounds (black lines for FOV edges)
                # The cam looks in direction yaw, with hfov spread
                import math as _math
                yaw_rad = _math.radians(cam.ypr[0])
                half_fov = _math.radians(cam.hfov / 2)
                ray_len = world_size * 0.7  # extends beyond view
                for offset in [-half_fov, half_fov]:
                    ang = yaw_rad + offset
                    end_x = cam_xyz[0] + ray_len * _math.sin(ang)
                    end_y = cam_xyz[1] + ray_len * _math.cos(ang)
                    m.draw_line([(cam_xyz[0], cam_xyz[1]), (end_x, end_y)],
                                fill=(0, 0, 0), width=1)

                # Draw rays to landmarks (thinner now)
                for lm_xyz, color, lm_name in rays:
                    line = [(cam_xyz[0], cam_xyz[1]), (lm_xyz[0], lm_xyz[1])]
                    m.draw_line(line, fill=color, width=1)
                # Draw landmark markers (small)
                for lm_xyz, color, lm_name in rays:
                    try:
                        m.draw_landmark(lm_name, r=4)
                    except Exception:
                        pass
                # Draw cam (slightly smaller marker)
                m.draw_camera(cam, r=8, d=80)'''

if OLD in content:
    content = content.replace(OLD, NEW)
    with open(SERVER_PATH, 'w') as f:
        f.write(content)
    print("✓ Patched generate_map: extended view, thinner rays, frustum bounds")
elif NEW in content:
    print("• Already patched")
else:
    print("✗ Could not find old block")
