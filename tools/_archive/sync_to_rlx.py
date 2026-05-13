#!/usr/bin/env python3
"""
sync_to_rlx.py — full sync to rlx upstream state

Replace cameras.json + landmarks.json + pixels.json entirely with rlx's
data. This adopts rlx's optimization as source of truth and discards
our local optimization work.

Steps:
  1. Save our unique landmarks to tools/_archive/our_unique_landmarks.json
     (for potential future PR to rlx)
  2. Replace cameras.json with rlx state (171 cams, schema-converted)
  3. Replace landmarks.json with rlx state (637 landmarks, schema-converted)
  4. Replace pixels.json with rlx state (126 cams with pixels)

Default: dry-run. Use --apply.
"""

import os, sys, json, argparse, shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RLX_DATA_DIR = '/tmp/rlx_data'

CAMS_PATH = os.path.join(REPO, 'gtamapdata', 'cameras.json')
LMS_PATH = os.path.join(REPO, 'gtamapdata', 'landmarks.json')
PIX_PATH = os.path.join(REPO, 'gtamapdata', 'pixels.json')

ARCHIVE_DIR = os.path.join(REPO, 'tools', '_archive')
OUR_UNIQUE_LMS_PATH = os.path.join(ARCHIVE_DIR, 'our_unique_landmarks.json')

SKIP_LANDMARKS = {
    'Minimap (TL)', 'Minimap (TR)', 'Minimap (BL)', 'Minimap (BR)',
    'Minimap (N)', 'Minimap (S)', 'Minimap (E)', 'Minimap (W)',
}


def to_list(v):
    """Recursively convert tuples to lists (preserves None)."""
    if isinstance(v, tuple):
        return [to_list(x) for x in v]
    if isinstance(v, list):
        return [to_list(x) for x in v]
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    sys.path.insert(0, RLX_DATA_DIR)
    import gtamapdata as md_rlx

    cams_yours = json.load(open(CAMS_PATH))
    lms_yours = json.load(open(LMS_PATH))
    pix_yours = json.load(open(PIX_PATH))

    print('Current state:')
    print(f'  cameras: {len(cams_yours)}')
    print(f'  landmarks: {len(lms_yours)}')
    print(f'  pixels keys: {len(pix_yours)}')
    print()
    print('rlx state:')
    print(f'  cameras: {len(md_rlx.cameras)}')
    print(f'  landmarks: {len(md_rlx.landmarks)}')
    print(f'  pixels keys: {len(md_rlx.pixels)}')
    print()

    # ─ Identify our unique landmarks (to save for future PR) ──────────────
    our_only_lms = {
        name: lm for name, lm in lms_yours.items()
        if name not in md_rlx.landmarks and lm.get('xyz')
    }
    print(f'Our unique landmarks (to save for archival): {len(our_only_lms)}')
    if our_only_lms:
        for n in sorted(our_only_lms.keys())[:5]:
            print(f'  {n}')
        if len(our_only_lms) > 5:
            print(f'  ... +{len(our_only_lms)-5} more')
    print()

    # ─ Plan summary ───────────────────────────────────────────────────────
    new_cam_count = len(md_rlx.cameras)
    new_lm_count = len(md_rlx.landmarks)
    # Pixels: count how many will be present after sync (skip Minimap UI refs)
    new_pix_total = 0
    new_pix_keys = 0
    for cam, pix in md_rlx.pixels.items():
        kept = {k: v for k, v in pix.items() if k not in SKIP_LANDMARKS}
        if kept:
            new_pix_keys += 1
            new_pix_total += len(kept)
    print(f'After sync:')
    print(f'  cameras: {new_cam_count}')
    print(f'  landmarks: {new_lm_count} (from rlx, schema-wrapped)')
    print(f'  pixels keys: {new_pix_keys} ({new_pix_total} total observations)')
    print(f'  Plus archive: {len(our_only_lms)} unique landmarks saved separately')
    print()

    if not args.apply:
        print('(dry-run — re-run with --apply)')
        return

    # ─ Save our unique landmarks first ────────────────────────────────────
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    with open(OUR_UNIQUE_LMS_PATH, 'w') as f:
        json.dump(our_only_lms, f, indent=2)
    print(f'✓ Saved {len(our_only_lms)} unique landmarks to {OUR_UNIQUE_LMS_PATH}')
    print()

    # ─ Backup current state ──────────────────────────────────────────────
    print('Backing up current state...')
    for path in [CAMS_PATH, LMS_PATH, PIX_PATH]:
        shutil.copy(path, path + '.bak_sync_to_rlx')
        print(f'  ✓ {path}.bak_sync_to_rlx')
    print()

    # ─ Build new cameras (rlx's schema is already compatible) ────────────
    print('Building new cameras...')
    new_cameras = {}
    for cam_name, rlx_cam in md_rlx.cameras.items():
        new_cameras[cam_name] = {
            'id': rlx_cam['id'],
            'player': to_list(rlx_cam['player']),
            'xyz': to_list(rlx_cam['xyz']),
            'ypr': to_list(rlx_cam['ypr']),
            'fov': to_list(rlx_cam['fov']),
            'size': to_list(rlx_cam['size']),
            'source': rlx_cam['source'],
        }
    print(f'  ✓ {len(new_cameras)} cameras')

    # ─ Build new landmarks (wrap rlx's tuples in our schema) ─────────────
    print('Building new landmarks...')
    new_landmarks = {}
    for lm_name, xyz in md_rlx.landmarks.items():
        new_landmarks[lm_name] = {
            'xyz': to_list(xyz),
            'source_cameras': [],  # rlx doesn't track this, leave empty
            'error_m': 0.0,
            'zone': 'unknown',
            'author': 'rlx',
        }
    print(f'  ✓ {len(new_landmarks)} landmarks')

    # ─ Build new pixels (skip Minimap UI refs) ───────────────────────────
    print('Building new pixels...')
    new_pixels = {}
    px_count = 0
    for cam_name, pix_dict in md_rlx.pixels.items():
        kept = {}
        for lm_name, xy in pix_dict.items():
            if lm_name in SKIP_LANDMARKS:
                continue
            kept[lm_name] = to_list(xy)
        if kept:
            new_pixels[cam_name] = kept
            px_count += len(kept)
    print(f'  ✓ {len(new_pixels)} pixel keys, {px_count} observations')
    print()

    # ─ Write all 3 files ─────────────────────────────────────────────────
    print('Writing files...')
    for path, data in [
        (CAMS_PATH, new_cameras),
        (LMS_PATH, new_landmarks),
        (PIX_PATH, new_pixels),
    ]:
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
        print(f'  ✓ {path}')
    print()

    # ─ Verify schema compat ──────────────────────────────────────────────
    print('Verifying schema...')
    try:
        sys.path.insert(0, REPO)
        if 'gtamapdata' in sys.modules:
            del sys.modules['gtamapdata']
        import gtamapdata as md_ours
        print(f'  ✓ Loaded OK: {len(md_ours.cameras)} cams, {len(md_ours.landmarks)} landmarks')
    except Exception as e:
        print(f'  ⚠ Schema validation error: {e}')
        print(f'  Revert with:')
        print(f'    cp {CAMS_PATH}.bak_sync_to_rlx {CAMS_PATH}')
        print(f'    cp {LMS_PATH}.bak_sync_to_rlx {LMS_PATH}')
        print(f'    cp {PIX_PATH}.bak_sync_to_rlx {PIX_PATH}')
        sys.exit(1)
    print()

    print('Done. Next steps:')
    print('  1. Restart server: lsof -ti:8765 | xargs kill -9; python3 tools/server.py')
    print('  2. Run bundle adjust: python3 tools/bundle_adjust.py')
    print('     (should converge to ~0\\' since rlx state is already optimized)')
    print('  3. Hard reload Safari, verify cams + landmarks look correct')
    print('  4. Pre-render minimaps: python3 tools/prerender_minimaps_fast.py')


if __name__ == '__main__':
    main()
