#!/usr/bin/env python3
"""
patch_item3_intersect_rays.py — Item 3 of rlx's roadmap.

Replaces the 2-rays best-pair triangulation in /api/triangulate with the
closed-form N-rays solver intersect_rays() that already exists in
gtamaplib.py (line 2735, written by rlx but unused).

Benefits:
  - Uses ALL rays simultaneously instead of testing pairs and picking best
  - Closed-form analytical solution (instant, no iterations)
  - More robust to degenerate cases (co-located cams)
  - Returns per-ray distance error (useful for outlier detection)

Scope: only patches /api/triangulate in server.py. The Nelder-Mead
implementations in tools/refine/batch_retriangulate_aiwe_fixed.py and
retriangulate_landmark.py are kept as-is — those are batch refinement
paths where angular loss is more appropriate for varying cam-to-lm
distances.

Run depuis la racine du repo :
    python3 patch_item3_intersect_rays.py             # dry-run
    python3 patch_item3_intersect_rays.py --apply
"""
import argparse
import os
import shutil
import sys

REPO_ROOT  = os.path.dirname(os.path.abspath(__file__))
SERVER_PATH = os.path.join(REPO_ROOT, 'tools', 'server.py')
CONTEXT_PATH = os.path.join(REPO_ROOT, 'tools', 'CLAUDE_CONTEXT.md')

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()

if not all(os.path.isfile(p) for p in [SERVER_PATH, CONTEXT_PATH]):
    print("✗ Lance depuis la racine de gtamaplib-main/")
    sys.exit(1)


def patch_file(path, replacements, marker_already_applied=None):
    with open(path) as f:
        content = f.read()
    if marker_already_applied and marker_already_applied in content:
        return 'already_patched'
    new_content = content
    for old, new in replacements:
        if old not in new_content:
            return f"error: pattern not found:\n{old[:200]}..."
        if new_content.count(old) > 1:
            return f"error: pattern found multiple times: {old[:100]}..."
        new_content = new_content.replace(old, new)
    if args.apply:
        shutil.copy(path, path + '.bak_item3')
        with open(path, 'w') as f:
            f.write(new_content)
    return 'patched'


# ── Patch server.py /api/triangulate ────────────────────────────────────────

SERVER_OLD_TRIANGULATE = '''        elif path == '/api/triangulate':
            lm_name = unquote(qs.get('lm', [''])[0])
            # Find all cams that see this landmark and are calibrated
            source_cams = []
            for cn, cp in md.pixels.items():
                if lm_name not in cp: continue
                if not md.cameras.get(cn, {}).get('xyz'): continue
                source_cams.append(cn)

            if len(source_cams) < 2:
                self.send_json({'error': f'Need 2+ calibrated cams, found {len(source_cams)}'}, 400)
                return

            # Try all pairs and pick best (lowest distance)
            best = None
            for i in range(len(source_cams)):
                for j in range(i+1, len(source_cams)):
                    try:
                        result = ml.find_landmark(source_cams[i], source_cams[j], lm_name)
                        if result is None: continue
                        pt, _, _, d, _ = result
                        if best is None or d < best['error_m']:
                            best = {
                                'xyz': [round(float(v), 4) for v in pt],
                                'error_m': round(float(d), 3),
                                'cam_a': source_cams[i],
                                'cam_b': source_cams[j],
                                'n_cams': len(source_cams),
                            }
                    except Exception as e:
                        pass

            if best is None:
                self.send_json({'error': 'Triangulation failed'}, 400)
                return

            # Save to landmarks. update_landmark() snaps xyz[2] if z_constraint
            # is set on this landmark (single source of truth — see gtamapdata.py).
            meta = md.landmarks_meta.get(lm_name, {})
            md.update_landmark(lm_name, best['xyz'],
                source_cameras=source_cams,
                error_m=best['error_m'],
                zone=meta.get('zone', 'unknown'))
            # Reflect snap in the response so frontend shows the correct xyz
            zc = meta.get('z_constraint')
            if zc and zc.get('type') == 'fixed':
                best['xyz'][2] = round(float(zc['value']), 4)
                best['z_snapped'] = True
            ml.get_camera.cache_clear()
            print(f"Triangulated {lm_name}: xyz={best['xyz']}, err={best['error_m']}m")
            self.send_json(best)'''

SERVER_NEW_TRIANGULATE = '''        elif path == '/api/triangulate':
            lm_name = unquote(qs.get('lm', [''])[0])
            # Find all cams that see this landmark and are calibrated
            source_cams = []
            for cn, cp in md.pixels.items():
                if lm_name not in cp: continue
                if not md.cameras.get(cn, {}).get('xyz'): continue
                source_cams.append(cn)

            if len(source_cams) < 2:
                self.send_json({'error': f'Need 2+ calibrated cams, found {len(source_cams)}'}, 400)
                return

            # Item 3 (rlx roadmap): use closed-form N-rays solver
            # ml.intersect_rays(rays) instead of testing all 2-cam pairs.
            # Inputs: list of (origin, direction) tuples.
            # Outputs: (closest_point, distances) where distances[i] is the
            # perpendicular distance from ray[i] to the closest_point.
            try:
                rays = []
                used_cams = []
                for cn in source_cams:
                    cam = ml.get_camera(cn)
                    direction = cam.get_landmark_direction(lm_name)
                    rays.append((tuple(cam.xyz), tuple(direction)))
                    used_cams.append(cn)

                pt, distances = ml.intersect_rays(rays)
                # error_m = mean perpendicular distance across all rays
                # (gives a "how well do these rays converge" metric similar to
                # find_landmark's pair distance, but using all rays at once)
                error_m = float(distances.mean())
                # max distance per ray = useful for outlier identification
                worst_idx = int(distances.argmax())
                best = {
                    'xyz': [round(float(v), 4) for v in pt],
                    'error_m': round(error_m, 3),
                    'worst_cam': used_cams[worst_idx],
                    'worst_distance_m': round(float(distances[worst_idx]), 3),
                    'n_cams': len(used_cams),
                    'method': 'intersect_rays',
                }
            except Exception as e:
                self.send_json({'error': f'Triangulation failed: {e}'}, 400)
                return

            # Save to landmarks. update_landmark() snaps xyz[2] if z_constraint
            # is set on this landmark (single source of truth — see gtamapdata.py).
            meta = md.landmarks_meta.get(lm_name, {})
            md.update_landmark(lm_name, best['xyz'],
                source_cameras=source_cams,
                error_m=best['error_m'],
                zone=meta.get('zone', 'unknown'))
            # Reflect snap in the response so frontend shows the correct xyz
            zc = meta.get('z_constraint')
            if zc and zc.get('type') == 'fixed':
                best['xyz'][2] = round(float(zc['value']), 4)
                best['z_snapped'] = True
            ml.get_camera.cache_clear()
            print(f"Triangulated {lm_name}: xyz={best['xyz']}, "
                  f"err={best['error_m']}m (worst: {best['worst_cam']} "
                  f"@ {best['worst_distance_m']}m)")
            self.send_json(best)'''


# ── Update CLAUDE_CONTEXT.md ────────────────────────────────────────────────

CONTEXT_APPEND = """
### 2026-05-07 (afternoon) — Item 3: intersect_rays in /api/triangulate

Replaced the 2-rays best-pair triangulation in `/api/triangulate` with
the closed-form N-rays solver `intersect_rays()` that already existed in
`gtamaplib.py` line 2735 (written by rlx, was unused).

**Why :**
- Uses ALL rays simultaneously instead of testing pairs and picking best
- Closed-form analytical (instant, no iterations vs Nelder-Mead's 10000)
- More robust to degenerate cases (e.g. co-located LEAK cams)
- Returns per-ray perpendicular distance — exposes worst-cam outlier info

**Response now includes :**
- `error_m` : mean perpendicular distance across all rays
- `worst_cam` + `worst_distance_m` : useful for spotting bad observations

**Scope :** only `/api/triangulate` is changed. The Nelder-Mead
implementations in `tools/refine/batch_retriangulate_aiwe_fixed.py` and
`retriangulate_landmark.py` are intentionally kept — those use angular
loss which is more appropriate when cam-to-landmark distances vary
wildly (10m → 10km), and they handle batch refinement where the extra
seconds don't matter.

**Roadmap status :**
- Item 1 (z=0 flag) ✅
- Item 2 (precision flag) ⏸ blocked on rlx clarification
- Item 3 (intersect_rays) ✅ shipped this session (`/api/triangulate` only)
- Item 4 (other cam cones) ✅ shipped earlier today

**Next** : item 2 once rlx clarifies, or chasse aux outliers (top 12
observations >10' from the bundle adjust report).
"""

CONTEXT_OLD_NEXT = '''**Next** : item 3 (intersect_rays) — function already exists in
gtamaplib.py line 2735, just needs wiring into `/api/triangulate`,
`retriangulate_landmark.py`, `batch_retriangulate_aiwe_fixed.py`.'''

CONTEXT_NEW_NEXT = '''**Next** : item 3 done in part — see session log entry below.'''


# ── Apply ───────────────────────────────────────────────────────────────────

if not args.apply:
    print("═══════════════════════════════════════════════════════════════")
    print("  DRY-RUN")
    print("═══════════════════════════════════════════════════════════════\n")

print("── Patch 1/2 : tools/server.py ──")
res = patch_file(SERVER_PATH, [
    (SERVER_OLD_TRIANGULATE, SERVER_NEW_TRIANGULATE),
], marker_already_applied="'method': 'intersect_rays'")
print(f"  → {res}")

print("── Patch 2/2 : tools/CLAUDE_CONTEXT.md ──")
# Read, optionally update Next, append session log
with open(CONTEXT_PATH) as f:
    src = f.read()

if "Item 3: intersect_rays in /api/triangulate" in src:
    print("  → already_patched")
else:
    new_src = src
    if CONTEXT_OLD_NEXT in new_src:
        new_src = new_src.replace(CONTEXT_OLD_NEXT, CONTEXT_NEW_NEXT, 1)
    new_src = new_src.rstrip() + "\n" + CONTEXT_APPEND
    if args.apply:
        shutil.copy(CONTEXT_PATH, CONTEXT_PATH + '.bak_item3')
        with open(CONTEXT_PATH, 'w') as f:
            f.write(new_src)
    print("  → patched")

print()
if args.apply:
    print("✓ Patches appliqués")
    print("\n  Tests :")
    print("    1. Restart server :")
    print("       lsof -ti :8765 | xargs kill -9 2>/dev/null && python3 tools/server.py")
    print("    2. Open http://localhost:8765/calib.html")
    print("    3. Pick a cam, click 'Triangulate' on a landmark with 3+ source cams")
    print("    4. Check console output: should now log 'worst: <cam> @ <dist>m'")
else:
    print("Lance avec --apply pour exécuter.")
