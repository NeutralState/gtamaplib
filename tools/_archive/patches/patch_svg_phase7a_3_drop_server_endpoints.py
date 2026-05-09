#!/usr/bin/env python3
"""
patch_svg_phase7a_3_drop_server_endpoints.py — drop now-orphaned server endpoints

Phase 7a.3 removes three endpoints that no longer have any frontend
callers:

  - /api/minimap         (Phase 7a.1 replaced with CSS-only crop)
  - /api/generate_map    (Phase 7a.2 removed the button + modal)
  - /api/generated_map   (only served PNGs that /api/generate_map wrote)

The Map view (Phase 3+4 onwards) replaces both the per-cam top-down PNG
and the GTA-style server-side minimap with client-side rendering.

Idempotent. Builds on Phase 7a.2.

Note: the generated PNG cache directory `tools/generated/` is NOT
touched — leaving it as-is is harmless. Manual cleanup is up to Alex
(`rm -rf tools/generated/`).
"""

import argparse, os, shutil, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_PY = os.path.join(THIS_DIR, 'server.py')
BACKUP = SERVER_PY + '.bak_svg_phase7a_3'

SENTINEL = '# Phase 7a.3: /api/minimap + /api/generate_map + /api/generated_map removed'


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 1 — drop /api/generate_map + /api/generated_map (consecutive blocks).
# Anchor stops just before `elif path == '/api/lm_info':` so the elif chain
# stays intact.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_1_OLD = """\
        elif path == '/api/generate_map':
            # Generates a top-down map showing rays from a camera to each
            # of its observed landmarks, colored by angular residual.
            cam_name = unquote(qs.get('cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400)
                return
            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return

            cam_pixels = md.pixels.get(cam_name, {})
            if not cam_pixels:
                self.send_json({'error': 'no pixels for this cam'}, 400)
                return

            # Build (lm_xyz, color) list based on angular residual
            cam_xyz = list(cam.xyz)
            rays = []
            for lm_name, marked_pixel in cam_pixels.items():
                lm_xyz = md.landmarks.get(lm_name)
                if lm_xyz is None:
                    continue
                # Angular residual
                try:
                    proj = cam.get_pixel(lm_xyz)
                    if proj is None:
                        color = (140, 140, 140)  # grey for unprojectable
                    else:
                        dx = (float(proj[0]) - marked_pixel[0]) * cam.hfov / cam.w * 60
                        dy = (float(proj[1]) - marked_pixel[1]) * cam.vfov / cam.h * 60
                        err = math.hypot(dx, dy)
                        if err < 3:
                            color = (74, 222, 128)   # green
                        elif err < 10:
                            color = (245, 158, 11)   # yellow/amber
                        else:
                            color = (248, 113, 113)  # red
                except Exception:
                    color = (140, 140, 140)
                rays.append((list(lm_xyz), color, lm_name))

            # Compute crop area: clip to a sensible radius around the cam
            # so a single distant landmark doesn't blow up the whole view.
            # Use median distance × 2.5, capped at MAX_RADIUS.
            import math as _math3
            MAX_RADIUS = 3750.0  # max half-size of view, in meters
            MIN_RADIUS = 800.0   # min, so very local cams still get context
            distances = [_math3.hypot(r[0][0] - cam_xyz[0], r[0][1] - cam_xyz[1])
                         for r in rays]
            if distances:
                distances.sort()
                # Use 75th percentile × 1.5 so we cover most rays comfortably
                # but ignore the 1-2 outlier-distance landmarks that wreck framing.
                p75 = distances[int(len(distances) * 0.75)]
                radius = max(MIN_RADIUS, min(MAX_RADIUS, p75 * 1.2))
            else:
                radius = MIN_RADIUS
            world_size = radius * 2
            cx, cy = cam_xyz[0], cam_xyz[1]
            x_min, x_max = cx - radius, cx + radius
            y_min, y_max = cy - radius, cy + radius
            area = (x_min, y_min, x_max, y_max)

            # Scale for ~1400 px on largest dimension
            target_px = 1400
            scale = target_px / world_size
            scale = max(0.05, min(0.5, scale))

            try:
                m = ml.get_map('yanis')
                m.open(scale=scale, add_padding=False)

                # Draw cam frustum bounds (FOV edges in blue)
                import math as _math
                frust_color = (96, 165, 250)  # blue, matches UI accent
                yaw_rad = _math.radians(cam.ypr[0])
                half_fov = _math.radians(cam.hfov / 2)
                # Match longest ray to landmark
                import math as _math2
                max_dist = max(
                    _math2.hypot(r[0][0] - cam_xyz[0], r[0][1] - cam_xyz[1])
                    for r in rays
                ) if rays else world_size * 0.4
                ray_len = max_dist
                for offset in [-half_fov, half_fov]:
                    ang = yaw_rad + offset
                    end_x = cam_xyz[0] - ray_len * _math.sin(ang)
                    end_y = cam_xyz[1] + ray_len * _math.cos(ang)
                    m.draw_line([(cam_xyz[0], cam_xyz[1]), (end_x, end_y)],
                                fill=frust_color, width=2)

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
                m.draw_camera(cam, r=8, d=80)

                # Save
                out_dir = os.path.join(TOOL_DIR, 'generated')
                os.makedirs(out_dir, exist_ok=True)
                # Sanitize filename
                safe_name = ''.join(c if c.isalnum() else '_' for c in cam_name)
                out_path = os.path.join(out_dir, f'{safe_name}_map.png')
                m.save(out_path, crop=area)

                self.send_json({
                    'ok': True,
                    'url': f'/api/generated_map?cam={cam_name}',
                    'n_rays': len(rays),
                })
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'error': f'render failed: {e}'}, 500)

        elif path == '/api/generated_map':
            cam_name = unquote(qs.get('cam', [''])[0])
            safe_name = ''.join(c if c.isalnum() else '_' for c in cam_name)
            out_path = os.path.join(TOOL_DIR, 'generated', f'{safe_name}_map.png')
            if os.path.exists(out_path):
                self.send_file(out_path, 'image/png')
            else:
                self.send_response(404)
                self.end_headers()


        elif path == '/api/lm_info':"""

HUNK_1_NEW = """\
        # Phase 7a.3: /api/generate_map and /api/generated_map removed.
        # The Map view (Phase 3+4 onwards) replaces this server-rendered
        # top-down PNG entirely. The Generate Map button was removed
        # from the frontend in Phase 7a.2.

        elif path == '/api/lm_info':"""


# ─────────────────────────────────────────────────────────────────────────────
# HUNK 2 — drop /api/minimap. Anchor goes from the elif opener through
# the closing `})` of the success-path send_json. Stops just before
# `elif path == '/api/other_cams_overlay':` to keep the elif chain.
# ─────────────────────────────────────────────────────────────────────────────

HUNK_2_OLD = """\
        elif path == '/api/minimap':
            # GTA-style minimap: rectangular crop of the yanis map centered
            # on a cam. Frontend rotates the image based on cam yaw.
            # Uses the same render pattern as /api/generate_map.
            cam_name = unquote(qs.get('cam', [''])[0])
            if cam_name not in md.cameras:
                self.send_json({'error': 'invalid cam'}, 400)
                return
            try:
                cam = ml.get_camera(cam_name)
            except Exception as e:
                self.send_json({'error': f'cam load failed: {e}'}, 400)
                return

            try:
                radius = float(qs.get('radius', ['200'])[0])
            except ValueError:
                radius = 200.0
            try:
                target_px = int(qs.get('size', ['480'])[0])
            except ValueError:
                target_px = 480

            cx, cy = float(cam.xyz[0]), float(cam.xyz[1])
            x_min, x_max = cx - radius, cx + radius
            y_min, y_max = cy - radius, cy + radius
            area = (x_min, y_min, x_max, y_max)

            try:
                # Open map at NATIVE scale (no global resize — that would
                # take seconds and 24000x24000 px of memory). Crop the small
                # area we want, then resize just the crop to target_px.
                m = ml.get_map('yanis')
                m.open(add_padding=False)  # no scale arg = native scale

                # m.crop returns a PIL Image of just the cropped area
                cropped = m.crop(area)
                # Resize the small crop to target size
                cropped = cropped.resize((target_px, target_px), 1)  # 1=LANCZOS

                import io, base64
                buf = io.BytesIO()
                cropped.save(buf, format='PNG')
                img_b64 = base64.b64encode(buf.getvalue()).decode('ascii')
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'error': f'minimap render failed: {e}'}, 500)
                return

            self.send_json({
                'cam': cam_name,
                'image_b64': img_b64,
                'yaw': float(cam.ypr[0]),
                'radius_m': radius,
                'image_size_px': target_px,
            })

        elif path == '/api/other_cams_overlay':"""

HUNK_2_NEW = """\
        # Phase 7a.3: /api/minimap removed. The minimap is now CSS-only
        # in the frontend (Phase 7a.1) — a background-image crop of
        # the cached /yanis.png.

        elif path == '/api/other_cams_overlay':"""


HUNKS = [
    ('SERVER — drop /api/generate_map + /api/generated_map', HUNK_1_OLD, HUNK_1_NEW),
    ('SERVER — drop /api/minimap',                            HUNK_2_OLD, HUNK_2_NEW),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--revert', action='store_true')
    args = ap.parse_args()

    if not os.path.exists(SERVER_PY):
        print(f'ERROR: {SERVER_PY} not found.')
        sys.exit(1)

    if args.revert:
        if not os.path.exists(BACKUP):
            print(f'ERROR: no backup at {BACKUP}.')
            sys.exit(1)
        if args.apply:
            shutil.copy(BACKUP, SERVER_PY)
            print(f'✓ Restored {SERVER_PY} from {BACKUP}.')
        else:
            print(f'(dry-run) would restore from {BACKUP}.')
        return

    with open(SERVER_PY, 'r') as f:
        src = f.read()

    if SENTINEL in src:
        print('✓ Already patched.')
        return

    for label, old, _new in HUNKS:
        n = src.count(old)
        if n != 1:
            print(f'ERROR: hunk "{label}" anchor matches {n} times (need exactly 1).')
            sys.exit(1)

    new_src = src
    for _label, old, new in HUNKS:
        new_src = new_src.replace(old, new, 1)

    # Embed sentinel near the first removed block for downstream pre-flight.
    SENTINEL_ANCHOR = "        elif path == '/api/lm_info':"
    new_src = new_src.replace(
        SENTINEL_ANCHOR,
        f'        {SENTINEL}\n\n{SENTINEL_ANCHOR}',
        1,
    )

    delta = new_src.count('\n') - src.count('\n')
    print(f'Will modify {SERVER_PY} ({delta:+d} lines)')
    print(f'  hunks applied: {len(HUNKS)}')

    if not args.apply:
        print('\n(dry-run — re-run with --apply)')
        return

    shutil.copy(SERVER_PY, BACKUP)
    print(f'\n✓ Backup: {BACKUP}')
    tmp = SERVER_PY + '.tmp'
    with open(tmp, 'w') as f:
        f.write(new_src)
    os.replace(tmp, SERVER_PY)
    print(f'✓ Patched {SERVER_PY}')
    print()
    print('Restart the server: lsof -ti:8765 | xargs kill -9 ; python3 tools/server.py')
    print()
    print('Test: hard reload, the tool still works (Camera + Map views).')
    print('No callers of /api/minimap, /api/generate_map, /api/generated_map remain.')
    print()
    print('Optional cleanup: rm -rf tools/generated/')


if __name__ == '__main__':
    main()
