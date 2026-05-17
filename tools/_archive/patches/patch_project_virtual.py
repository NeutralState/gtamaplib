"""[VIRTUAL-LMS-V1] Include virtual (unmarked) LMs in /api/project for wireframes."""
import sys, shutil

PATH = 'tools/server.py'
SENTINEL = '[VIRTUAL-LMS-V1]'

OLD = '''def compute_projections(cam_name, xyz=None, ypr=None, hfov=None):
    if cam_name not in md.cameras:
        return [], {}

    cam = get_cam(cam_name, xyz, ypr, hfov)
    cam_pixels = md.pixels.get(cam_name, {})
    result = []

    for lm_name, marked_pixel in cam_pixels.items():'''

NEW = '''def compute_projections(cam_name, xyz=None, ypr=None, hfov=None):
    if cam_name not in md.cameras:
        return [], {}

    cam = get_cam(cam_name, xyz, ypr, hfov)
    cam_pixels = md.pixels.get(cam_name, {})
    result = []

    # [VIRTUAL-LMS-V1] Include virtual LMs (no marker, e.g. building wireframes)
    # for known prefixes. They get projected but no marked_pixel/delta.
    VIRTUAL_PREFIXES = ('Portofino Tower (',)
    virtual_lms_to_include = []
    for lm_name in md.landmarks:
        if lm_name in cam_pixels:
            continue
        if any(lm_name.startswith(p) for p in VIRTUAL_PREFIXES):
            virtual_lms_to_include.append(lm_name)

    for lm_name, marked_pixel in cam_pixels.items():'''

# Also add virtual LM block right after the cam_pixels loop
OLD2 = '''        result.append({
            'name': lm_name,
            'marked_pixel': list(marked_pixel),
            'projected': proj,
            'delta': round(delta, 3) if delta is not None else None,
            'has_xyz': lm_xyz is not None,
            'is_circular': is_circular,
            'error_m': err_m,
        })

    all_d = [r['delta'] for r in result if r['delta'] is not None]'''

NEW2 = '''        result.append({
            'name': lm_name,
            'marked_pixel': list(marked_pixel),
            'projected': proj,
            'delta': round(delta, 3) if delta is not None else None,
            'has_xyz': lm_xyz is not None,
            'is_circular': is_circular,
            'error_m': err_m,
        })

    # [VIRTUAL-LMS-V1] Add virtual LMs (no marker, only projection)
    for lm_name in virtual_lms_to_include:
        lm_xyz = md.landmarks.get(lm_name)
        proj = None
        if lm_xyz:
            try:
                p = cam.get_pixel(lm_xyz)
                if p is not None:
                    proj = [round(float(p[0]), 2), round(float(p[1]), 2)]
            except Exception:
                pass
        if proj is None:
            continue  # behind camera or projection failed
        result.append({
            'name': lm_name,
            'marked_pixel': None,
            'projected': proj,
            'delta': None,
            'has_xyz': True,
            'is_circular': False,
            'error_m': 0.0,
            'is_virtual': True,
        })

    all_d = [r['delta'] for r in result if r['delta'] is not None]'''

apply = '--apply' in sys.argv
with open(PATH) as f: content = f.read()
if SENTINEL in content:
    print('Already applied'); sys.exit(0)
if OLD not in content or OLD2 not in content:
    print('ERROR: anchors not found'); sys.exit(1)
new_content = content.replace(OLD, NEW, 1).replace(OLD2, NEW2, 1)
if not apply:
    print('DRY-RUN OK'); sys.exit(0)
shutil.copy(PATH, PATH + '.bak_virtual_lms')
with open(PATH, 'w') as f: f.write(new_content)
print('Applied')
