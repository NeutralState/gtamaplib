#!/usr/bin/env python3
"""
patch_update_lms_safety.py — Adds safety check to "Update LMs":

Backend: refuses /api/update_landmarks if cam loss (independent) > 10 arcmin.
Frontend: disables the Update LMs button when loss > 10' is displayed.

Prevents the failure mode where a cam in a bad local minimum
(e.g. Grassrivers 02 at loss=378) propagates garbage to its observed landmarks.

Run from gtamaplib-main/:
    python3 tools/patch_update_lms_safety.py
"""
import os

GTAMAP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'tools' \
    else os.path.dirname(os.path.abspath(__file__))

SERVER_PATH = os.path.join(GTAMAP_DIR, 'tools', 'server.py')
HTML_PATH = os.path.join(GTAMAP_DIR, 'tools', 'calib.html')

LOSS_THRESHOLD = 10.0

# ── Patch server.py ───────────────────────────────────────────────────────────

with open(SERVER_PATH) as f:
    content = f.read()

if 'UPDATE_LMS_LOSS_THRESHOLD' in content:
    print("• server.py already patched")
else:
    # Insert safety check right after parsing the args
    OLD = """        elif path == '/api/update_landmarks':
            cam_name = unquote(qs.get('cam', [''])[0])
            xyz = [float(qs['x'][0]), float(qs['y'][0]), float(qs['z'][0])]
            ypr = [float(qs['yaw'][0]), float(qs['pitch'][0]), 0.0]
            hfov_val = float(qs['hfov'][0])

            cam = get_cam(cam_name, xyz, ypr, hfov_val)"""

    NEW = """        elif path == '/api/update_landmarks':
            UPDATE_LMS_LOSS_THRESHOLD = 10.0  # arcmin — refuse if cam loss exceeds this
            cam_name = unquote(qs.get('cam', [''])[0])
            xyz = [float(qs['x'][0]), float(qs['y'][0]), float(qs['z'][0])]
            ypr = [float(qs['yaw'][0]), float(qs['pitch'][0]), 0.0]
            hfov_val = float(qs['hfov'][0])

            # Safety: refuse if cam loss is too high. A high-loss cam in a bad
            # local minimum will propagate garbage to its observed landmarks.
            try:
                _projs, _losses = compute_projections(cam_name, xyz, ypr, hfov_val)
                _check_loss = _losses.get('independent') if _losses.get('independent') is not None else _losses.get('total')
                if _check_loss is not None and _check_loss > UPDATE_LMS_LOSS_THRESHOLD:
                    self.send_json({
                        'error': f"Cam loss too high ({_check_loss:.2f}' > {UPDATE_LMS_LOSS_THRESHOLD}'). "
                                 f"Refine the cam first or use bundle adjust to avoid propagating errors to landmarks.",
                        'loss': _check_loss,
                        'threshold': UPDATE_LMS_LOSS_THRESHOLD,
                    }, 400)
                    return
            except Exception as _e:
                print(f"Warning: could not check loss before update: {_e}")

            cam = get_cam(cam_name, xyz, ypr, hfov_val)"""

    if OLD in content:
        content = content.replace(OLD, NEW)
        with open(SERVER_PATH, 'w') as f:
            f.write(content)
        print(f"✓ Patched server.py: refuse update_landmarks if loss > {LOSS_THRESHOLD}'")
    else:
        print("✗ Could not find /api/update_landmarks block in server.py")

# ── Patch calib.html ──────────────────────────────────────────────────────────

with open(HTML_PATH) as f:
    content = f.read()

if 'UPDATE_LMS_LOSS_THRESHOLD' in content:
    print("• calib.html already patched")
else:
    # The losses are set at line ~603-604:
    # lossAll.textContent   = losses.total      != null ? ...
    # lossIndep.textContent = losses.independent != null ? ...
    # We want to add a button enable/disable based on losses.independent.

    OLD = """  lossAll.textContent   = losses.total      != null ? losses.total.toFixed(3)      : '—';
  lossIndep.textContent = losses.independent != null ? losses.independent.toFixed(3) : '—';"""

    NEW = f"""  lossAll.textContent   = losses.total      != null ? losses.total.toFixed(3)      : '—';
  lossIndep.textContent = losses.independent != null ? losses.independent.toFixed(3) : '—';

  // Safety: disable Update LMs if cam loss too high (would propagate errors)
  const UPDATE_LMS_LOSS_THRESHOLD = {LOSS_THRESHOLD};
  const _checkLoss = losses.independent != null ? losses.independent : losses.total;
  if (_checkLoss != null && _checkLoss > UPDATE_LMS_LOSS_THRESHOLD) {{
    btnUpdate.disabled = true;
    btnUpdate.title = `Cam loss ${{_checkLoss.toFixed(2)}}' > ${{UPDATE_LMS_LOSS_THRESHOLD}}' — refine cam first to avoid propagating errors`;
  }} else {{
    btnUpdate.title = '';
  }}"""

    if OLD in content:
        content = content.replace(OLD, NEW)
        with open(HTML_PATH, 'w') as f:
            f.write(content)
        print(f"✓ Patched calib.html: disable Update LMs if loss > {LOSS_THRESHOLD}'")
    else:
        print("✗ Could not find loss display block in calib.html")

print("\nNext steps:")
print("  1. Restart server: lsof -ti :8765 | xargs kill -9; python3 tools/server.py")
print("  2. Hard reload calib.html (Cmd+Shift+R)")
print(f"  3. Test: open a cam with loss > {LOSS_THRESHOLD}', verify Update LMs is grayed out")
